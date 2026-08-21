from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class Decision(StrEnum):
    ALLOW = "ALLOW"
    DENY = "DENY"
    REQUIRE_APPROVAL = "REQUIRE_APPROVAL"


class ReasonCode(StrEnum):
    ALLOWED = "ALLOWED"
    IDENTITY_MISMATCH = "IDENTITY_MISMATCH"
    TOOL_NOT_REGISTERED = "TOOL_NOT_REGISTERED"
    TENANT_MISMATCH = "TENANT_MISMATCH"
    POLICY_DENIED = "POLICY_DENIED"
    RISK_DENIED = "RISK_DENIED"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
    INVALID_AMOUNT = "INVALID_AMOUNT"
    CURRENCY_NOT_ALLOWED = "CURRENCY_NOT_ALLOWED"


class AgentProposal(BaseModel):
    """Untrusted intent proposed by an agent; never contains authority."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    proposal_id: UUID = Field(default_factory=uuid4)
    agent_id: str = Field(min_length=1, max_length=200)
    tenant_id: str = Field(min_length=1, max_length=200)
    action: str = Field(min_length=1, max_length=200)
    resource: str = Field(min_length=1, max_length=400)
    amount: Decimal = Field(ge=0)
    currency: str = Field(min_length=3, max_length=12)
    parameters: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str = Field(min_length=1, max_length=200)
    correlation_id: str = Field(min_length=1, max_length=200)


class GovernanceDecision(BaseModel):
    model_config = ConfigDict(frozen=True)

    decision: Decision
    reason_code: ReasonCode
    proposal_id: UUID
    agent_id: str
    tenant_id: str
    action: str
    resource: str
    policy_id: str
    policy_version: str
    explanation: str
    evaluated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    risk_score: int = Field(ge=0, le=100)


class ExecutionIntent(BaseModel):
    model_config = ConfigDict(frozen=True)

    intent_id: UUID = Field(default_factory=uuid4)
    proposal_id: UUID
    decision: Literal[Decision.ALLOW] = Decision.ALLOW
    action: str
    resource: str
    amount: Decimal = Field(ge=0)
    currency: str
    verification_requirements: tuple[str, ...] = ("downstream_state", "audit_evidence")


class A2ATaskState(StrEnum):
    SUBMITTED = "submitted"
    WORKING = "working"
    INPUT_REQUIRED = "input-required"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"
    REJECTED = "rejected"


class A2ATask(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID = Field(default_factory=uuid4)
    context_id: str = Field(min_length=1)
    state: A2ATaskState = A2ATaskState.SUBMITTED
    agent_id: str
    tenant_id: str
    input_text: str = Field(min_length=1)
    output: dict[str, Any] | None = None
    error: str | None = None
