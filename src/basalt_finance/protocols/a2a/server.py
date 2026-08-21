from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, ValidationError

from basalt_finance.governance.contracts import A2ATask, A2ATaskState, AgentProposal
from basalt_finance.runtime import state


class A2AMessagePart(BaseModel):
    text: str | None = None
    data: dict[str, Any] | None = None


class A2AMessage(BaseModel):
    role: str = Field(pattern="^(user|agent)$")
    parts: list[A2AMessagePart] = Field(min_length=1)


class SendMessageRequest(BaseModel):
    message: A2AMessage
    context_id: str = Field(min_length=1, max_length=200)
    metadata: dict[str, Any] = Field(default_factory=dict)


class TaskStore:
    def __init__(self) -> None:
        self.tasks: dict[UUID, A2ATask] = {}

    def save(self, task: A2ATask) -> A2ATask:
        self.tasks[task.id] = task
        return task

    def get(self, task_id: UUID) -> A2ATask:
        try:
            return self.tasks[task_id]
        except KeyError as exc:
            raise HTTPException(status_code=404, detail={"code": "TASK_NOT_FOUND"}) from exc


tasks = TaskStore()
router = APIRouter(prefix="/a2a", tags=["a2a"])


@router.post("/message:send", response_model=A2ATask)
def send_message(payload: SendMessageRequest) -> A2ATask:
    text = " ".join(part.text or "" for part in payload.message.parts).strip()
    structured = next((part.data for part in payload.message.parts if part.data), None)
    task = A2ATask(
        context_id=payload.context_id,
        agent_id="basalt-finance-agent",
        tenant_id=str(payload.metadata.get("tenant_id", "unknown")),
        input_text=text or "structured-request",
        state=A2ATaskState.WORKING,
    )
    if structured is not None and structured.get("type") == "financial_proposal":
        try:
            proposal = AgentProposal.model_validate(structured["proposal"])
            decision = state.engine.evaluate(proposal, task.tenant_id)
            intent = state.engine.create_intent(proposal, decision)
            task = task.model_copy(
                update={
                    "state": A2ATaskState.COMPLETED,
                    "output": {
                        "decision": decision.model_dump(mode="json"),
                        "intent": intent.model_dump(mode="json") if intent else None,
                    },
                }
            )
        except ValidationError as exc:
            task = task.model_copy(update={"state": A2ATaskState.FAILED, "error": str(exc)})
    else:
        task = task.model_copy(
            update={
                "state": A2ATaskState.INPUT_REQUIRED,
                "output": {"message": "Provide a structured financial_proposal part to request governance evaluation."},
            }
        )
    return tasks.save(task)


@router.get("/tasks/{task_id}", response_model=A2ATask)
def get_task(task_id: UUID) -> A2ATask:
    return tasks.get(task_id)


@router.post("/tasks/{task_id}:cancel", response_model=A2ATask)
def cancel_task(task_id: UUID) -> A2ATask:
    task = tasks.get(task_id)
    if task.state in {A2ATaskState.COMPLETED, A2ATaskState.FAILED, A2ATaskState.CANCELED}:
        raise HTTPException(status_code=409, detail={"code": "TASK_NOT_CANCELABLE"})
    return tasks.save(task.model_copy(update={"state": A2ATaskState.CANCELED}))
