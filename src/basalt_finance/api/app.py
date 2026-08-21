from __future__ import annotations

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated, Any
from uuid import UUID

from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict

from basalt_finance.governance.contracts import (
    AgentProposal,
    ExecutionIntent,
    GovernanceDecision,
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
    return AuthenticatedPrincipal(agent_id="treasury-agent-042", tenant_id="example-bank", scopes=frozenset({"proposal:admit"}))


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
    decision = state.engine.evaluate(proposal, principal.tenant_id)
    intent = state.engine.create_intent(proposal, decision)
    if intent is not None:
        state.intents[intent.intent_id] = intent
    return AdmissionResponse(decision=decision, intent=intent)


@app.get("/v1/intents/{intent_id}", response_model=ExecutionIntent, tags=["governance"])
def get_intent(intent_id: UUID, _: Annotated[AuthenticatedPrincipal, Depends(authenticate)]) -> ExecutionIntent:
    intent = state.intents.get(intent_id)
    if intent is None:
        raise HTTPException(status_code=404, detail={"code": "INTENT_NOT_FOUND"})
    return intent


def main() -> None:
    import uvicorn

    uvicorn.run("basalt_finance.api.app:app", host="127.0.0.1", port=8000, reload=False)
