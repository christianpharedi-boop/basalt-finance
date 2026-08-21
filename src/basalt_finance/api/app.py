from __future__ import annotations

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated, Any
from uuid import UUID

from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field

from basalt_finance.governance.contracts import (
    AgentProposal,
    Decision,
    ExecutionIntent,
    GovernanceDecision,
    ReasonCode,
)
from basalt_finance.protocols.a2a.server import router as a2a_router
from basalt_finance.runtime import state


class AuthenticatedPrincipal(BaseModel):
    model_config = ConfigDict(frozen=True)

    agent_id: str
    tenant_id: str
    scopes: frozenset[str] = frozenset()


class AdmissionResponse(BaseModel):
    decision: GovernanceDecision
    intent: ExecutionIntent | None = None
    approval_id: UUID | None = None


class ApprovalDecisionInput(BaseModel):
    approver_id: str
    approve: bool
    reason: str = Field(min_length=1, max_length=1000)


class AgentCard(BaseModel):
    name: str = "Basalt Finance Governance Agent"
    description: str = "Governed financial policy, risk, and execution-intent services."
    version: str = "0.1.0"
    url: str
    capabilities: dict[str, bool] = {"streaming": True, "pushNotifications": False}
    skills: list[dict[str, Any]] = [
        {
            "id": "governed-proposal-admission",
            "name": "Governed proposal admission",
            "description": "Evaluate an untrusted financial action proposal against deterministic governance.",
            "tags": ["governance", "finance", "risk", "approval"],
        }
    ]
    authentication: dict[str, Any] = {"schemes": ["Bearer"]}



def authenticate(authorization: str | None = Header(default=None)) -> AuthenticatedPrincipal:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "AUTHENTICATION_REQUIRED", "message": "Bearer token required"},
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = authorization.removeprefix("Bearer ").strip()
    expected = os.getenv("BASALT_FINANCE_DEV_TOKEN", "basalt-finance-development-token")
    if token != expected:
        raise HTTPException(status_code=401, detail={"code": "AUTHENTICATION_FAILED"})
    return AuthenticatedPrincipal(
        agent_id="treasury-agent-042",
        tenant_id="example-bank",
        scopes=frozenset({"proposal:admit", "approval:decide", "intent:execute", "intent:settle"}),
    )


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    yield


app = FastAPI(
    title="Basalt Finance API",
    version="0.1.0",
    summary="Governed intelligent financial infrastructure",
    lifespan=lifespan,
)
app.include_router(a2a_router)


@app.get("/health", tags=["system"])
def health() -> dict[str, str]:
    return {"status": "ok", "service": "basalt-finance"}


@app.get("/.well-known/agent-card.json", response_model=AgentCard, tags=["a2a"])
def agent_card(request: Request) -> AgentCard:
    return AgentCard(url=str(request.base_url).rstrip("/") + "/a2a")


@app.post("/v1/proposals/admit", response_model=AdmissionResponse, tags=["governance"])
def admit_proposal(
    proposal: AgentProposal,
    principal: Annotated[AuthenticatedPrincipal, Depends(authenticate)],
) -> AdmissionResponse:
    if "proposal:admit" not in principal.scopes:
        raise HTTPException(status_code=403, detail={"code": "SCOPE_REQUIRED"})
    if proposal.agent_id != principal.agent_id:
        raise HTTPException(status_code=403, detail={"code": "IDENTITY_MISMATCH"})
    finance_decision = state.engine.evaluate(proposal, principal.tenant_id)
    try:
        hardened = state.basalt_os.admit_authenticated(proposal, principal.agent_id, principal.tenant_id)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail={"code": "BASALT_OS_IDENTITY_REJECTED", "message": str(exc)}) from exc
    if hardened.decision.decision.value != finance_decision.decision.value:
        finance_decision = GovernanceDecision(
            decision=Decision(hardened.decision.decision.value),
            reason_code=ReasonCode(hardened.decision.reason_code.value) if hardened.decision.reason_code.value in ReasonCode._value2member_map_ else ReasonCode.POLICY_DENIED,
            proposal_id=proposal.proposal_id,
            agent_id=proposal.agent_id,
            tenant_id=proposal.tenant_id,
            action=proposal.action,
            resource=proposal.resource,
            policy_id=hardened.decision.policy_id,
            policy_version=hardened.decision.policy_version,
            explanation=hardened.decision.explanation,
            risk_score=hardened.decision.risk_score,
        )
    state.admissions[proposal.proposal_id] = hardened
    if hardened.approval is not None:
        state.pending_by_approval[hardened.approval.approval_id] = proposal.proposal_id
    intent = state.engine.create_intent(proposal, finance_decision)
    if intent is not None:
        state.intents[intent.intent_id] = intent
        state.admissions[intent.intent_id] = hardened
    return AdmissionResponse(
        decision=finance_decision,
        intent=intent,
        approval_id=hardened.approval.approval_id if hardened.approval else None,
    )


@app.post("/v1/approvals/{approval_id}/decide", tags=["approvals"])
def decide_approval(
    approval_id: UUID,
    payload: ApprovalDecisionInput,
    principal: Annotated[AuthenticatedPrincipal, Depends(authenticate)],
) -> dict[str, Any]:
    if "approval:decide" not in principal.scopes:
        raise HTTPException(status_code=403, detail={"code": "APPROVAL_SCOPE_REQUIRED"})
    if payload.approver_id == principal.agent_id:
        raise HTTPException(status_code=403, detail={"code": "REQUESTER_CANNOT_APPROVE"})
    try:
        approval = state.basalt_os.decide_approval(approval_id, payload.approver_id, payload.approve, payload.reason)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail={"code": "APPROVAL_REJECTED", "message": str(exc)}) from exc
    intent_id: UUID | None = None
    proposal_id = state.pending_by_approval.pop(approval_id, None)
    if approval.status.value == "APPROVED":
        admission = state.admissions.get(proposal_id) if proposal_id else None
        if admission is not None:
            assert proposal_id is not None
            authorized = state.basalt_os.authorize_after_approval(admission, approval)
            intent = ExecutionIntent(
                proposal_id=proposal_id,
                action=authorized.request.action,
                resource=authorized.request.resource,
                amount=authorized.request.amount,
                currency=authorized.request.currency,
            )
            state.intents[intent.intent_id] = intent
            state.admissions[intent.intent_id] = authorized
            intent_id = intent.intent_id
    return {
        "approval_id": str(approval.approval_id),
        "action_request_id": str(approval.action_request_id),
        "status": approval.status.value,
        "approver_id": approval.approver_id,
        "reason": approval.reason,
        "intent_id": str(intent_id) if intent_id else None,
    }


@app.post("/v1/intents/{intent_id}/execute", tags=["execution"])
def execute_intent(
    intent_id: UUID,
    principal: Annotated[AuthenticatedPrincipal, Depends(authenticate)],
) -> dict[str, Any]:
    if "intent:execute" not in principal.scopes:
        raise HTTPException(status_code=403, detail={"code": "EXECUTION_SCOPE_REQUIRED"})
    admission = state.admissions.get(intent_id)
    if admission is None:
        raise HTTPException(status_code=404, detail={"code": "ADMISSION_NOT_FOUND"})
    outcome = state.basalt_os.execute(admission)
    return {
        "status": outcome.status,
        "payment": outcome.result.__dict__ if outcome.result else None,
        "verification": outcome.verification.__dict__ if outcome.verification else None,
        "evidence": outcome.evidence.__dict__,
    }


@app.get("/v1/intents/{intent_id}", response_model=ExecutionIntent, tags=["governance"])
def get_intent(intent_id: UUID, _: Annotated[AuthenticatedPrincipal, Depends(authenticate)]) -> ExecutionIntent:
    intent = state.intents.get(intent_id)
    if intent is None:
        raise HTTPException(status_code=404, detail={"code": "INTENT_NOT_FOUND"})
    return intent


@app.post("/v1/intents/{intent_id}/settle", tags=["settlement"])
def settle_intent(
    intent_id: UUID,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
    _: Annotated[AuthenticatedPrincipal, Depends(authenticate)],
) -> dict[str, Any]:
    intent = state.intents.get(intent_id)
    if intent is None:
        raise HTTPException(status_code=404, detail={"code": "INTENT_NOT_FOUND"})
    if state.ledger is None or state.treasury is None:
        raise HTTPException(status_code=503, detail={"code": "REPOSITORY_INTEGRATIONS_DISABLED"})
    ledger_result = state.ledger.post_controlled_intent(intent, idempotency_key)
    settlement = state.treasury.create_settlement_instruction(intent, idempotency_key)
    return {
        "status": "SETTLEMENT_RECORDED",
        "intent_id": str(intent_id),
        "ledger": {
            "journal_entry_id": ledger_result.journal_entry_id,
            "status": ledger_result.status,
            "verified": state.ledger.verify(ledger_result.journal_entry_id),
        },
        "treasury": {
            "instruction_id": str(settlement.instruction_id),
            "status": settlement.status,
            "verified": state.treasury.verify_settlement(settlement.instruction_id),
        },
    }


def main() -> None:
    import uvicorn

    uvicorn.run("basalt_finance.api.app:app", host="127.0.0.1", port=8000, reload=False)
