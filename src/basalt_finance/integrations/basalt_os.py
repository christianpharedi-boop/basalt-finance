from __future__ import annotations

import dataclasses
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from basalt.approval.core import ApprovalRequest, ApprovalService, ApprovalStatus
from basalt.audit.core import AuditEvent, AuditRepository
from basalt.domain import (
    ActionRequest,
    AgentIdentity,
    AgentPassport,
    AuthorizationDecision,
    AuthorizationEngine,
    Decision,
    DeterministicRiskEngine,
    Policy,
    PolicyRule,
)
from basalt.execution.core import ExecutionGateway, ExecutionOutcome, MockBankingConnector
from basalt.identity.enterprise import AuthenticatedPrincipal, StaticEnterpriseAdapter
from basalt.storage.actions import ActionLifecycle, ActionLifecycleRepository, LifecycleState


@dataclass(frozen=True)
class BasaltAdmission:
    request: ActionRequest
    identity: AgentIdentity
    passport: AgentPassport
    decision: AuthorizationDecision
    approval: ApprovalRequest | None
    lifecycle: ActionLifecycle


class BasaltOSControlPlane:
    """Production-oriented bridge around the user's hardened Basalt OS package.

    Basalt Finance owns protocol and financial-domain contracts. Basalt OS owns
    identity, delegated authority, deterministic authorization, independent
    approval, execution evidence, audit, and lifecycle persistence.
    """

    def __init__(self, *, sqlite_path: str = ":memory:") -> None:
        self.connection = sqlite3.connect(sqlite_path, check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        self.lifecycle_repository = ActionLifecycleRepository(self.connection)
        self.approvals = ApprovalService()
        self.audit = AuditRepository()
        self.connector = MockBankingConnector()
        self.execution = ExecutionGateway(self.connector)
        now = datetime.now(UTC)
        self.identity = AgentIdentity("treasury-agent-042", "example-bank", "basalt-finance", "production")
        self.passport = AgentPassport(
            passport_id=uuid4(),
            agent_id=self.identity.agent_id,
            organization=self.identity.organization,
            issuer="basalt-finance",
            capabilities=frozenset({"payment.initiate", "account.read"}),
            resources=frozenset({"corporate-account-001", "customer-001"}),
            transaction_max=Decimal(1000000),
            currencies=frozenset({"ZAR", "USD"}),
            approval_required_above=Decimal(100000),
            starts_at=now - timedelta(minutes=1),
            expires_at=now + timedelta(days=1),
        )
        self.policy = Policy(
            "basalt-finance-production-policy",
            "1",
            (
                PolicyRule(self.identity.agent_id, "payment.initiate", "corporate-account-001", Decision.ALLOW, Decimal(1000000)),
                PolicyRule(self.identity.agent_id, "account.read", "customer-001", Decision.ALLOW),
            ),
        )
        self.enterprise = StaticEnterpriseAdapter(
            {
                "basalt-finance-development-token": AuthenticatedPrincipal(
                    subject=self.identity.agent_id,
                    organization=self.identity.organization,
                    authentication_method="development-static",
                    assurance_level="development",
                    claims={"scope": "proposal:admit intent:settle approval:decide intent:execute"},
                )
            }
        )

    def authenticate(self, credential: str) -> AuthenticatedPrincipal:
        return self.enterprise.verify(credential)

    def admit(self, proposal: Any, credential: str) -> BasaltAdmission:
        principal = self.authenticate(credential)
        return self.admit_authenticated(proposal, principal.subject, principal.organization)

    def admit_authenticated(self, proposal: Any, agent_id: str, organization: str) -> BasaltAdmission:
        identity = AgentIdentity(agent_id, organization, "enterprise-identity", "production")
        if identity.agent_id != proposal.agent_id or identity.organization != proposal.tenant_id:
            raise PermissionError("authenticated principal does not match proposal")
        request = ActionRequest(
            agent_id=proposal.agent_id,
            action=proposal.action,
            resource=proposal.resource,
            amount=proposal.amount,
            currency=proposal.currency,
            parameters={key: str(value) for key, value in proposal.parameters.items()},
            request_id=proposal.proposal_id,
        )
        decision = AuthorizationEngine().evaluate(
            identity,
            self.passport,
            self.policy,
            request,
            DeterministicRiskEngine(),
        )
        lifecycle_state = {
            Decision.ALLOW: LifecycleState.AUTHORIZED,
            Decision.REQUIRE_APPROVAL: LifecycleState.REQUIRE_APPROVAL,
            Decision.DENY: LifecycleState.REJECTED,
        }[decision.decision]
        lifecycle = ActionLifecycle(
            request_id=request.request_id,
            agent_id=request.agent_id,
            idempotency_key=proposal.idempotency_key,
            fingerprint=f"{request.agent_id}:{request.action}:{request.resource}:{request.amount}:{request.currency}",
            state=lifecycle_state,
        )
        self.lifecycle_repository.save(lifecycle)
        approval = None
        if decision.decision is Decision.REQUIRE_APPROVAL:
            approval = self.approvals.create(request.request_id, request.agent_id)
        self.audit.append(
            AuditEvent(
                "PROPOSAL_ADMITTED",
                request.request_id,
                request.agent_id,
                decision.decision.value,
                attributes={"reason_code": decision.reason_code.value, "tenant_id": proposal.tenant_id},
            )
        )
        return BasaltAdmission(request, identity, self.passport, decision, approval, lifecycle)

    def authorize_after_approval(self, admission: BasaltAdmission) -> BasaltAdmission:
        """Promote a REQUIRE_APPROVAL admission after its approval is APPROVED."""
        if admission.approval is None:
            raise PermissionError("admission has no associated approval")
        if admission.approval.status is not ApprovalStatus.APPROVED:
            raise PermissionError("associated approval is not approved")
        promoted_decision = dataclasses.replace(admission.decision, decision=Decision.ALLOW)
        return dataclasses.replace(admission, decision=promoted_decision)

    def decide_approval(self, approval_id: UUID, approver_id: str, approve: bool, reason: str) -> ApprovalRequest:
        approval = self.approvals.decide(approval_id, approver_id, approve, reason)
        existing = self.lifecycle_repository.get(approval.action_request_id)
        if existing is None:
            raise RuntimeError("approval lifecycle record not found")
        next_state = LifecycleState.AUTHORIZED if approve else LifecycleState.REJECTED
        self.lifecycle_repository.save(existing.transition(next_state))
        self.audit.append(
            AuditEvent(
                "APPROVAL_DECIDED",
                approval.action_request_id,
                approver_id,
                approval.status.value,
                attributes={"reason": reason, "approval_id": str(approval.approval_id)},
            )
        )
        return approval

    def execute(self, admission: BasaltAdmission) -> ExecutionOutcome:
        if admission.decision.decision is not Decision.ALLOW:
            raise PermissionError("only an allowed admission may be executed")
        outcome = self.execution.execute(admission.request, admission.decision, admission.passport.passport_id)
        existing = self.lifecycle_repository.get(admission.request.request_id)
        if existing is not None:
            target = LifecycleState.VERIFIED if outcome.status == "VERIFIED" else LifecycleState.FAILED
            self.lifecycle_repository.save(existing.transition(LifecycleState.SUBMITTED).transition(LifecycleState.EXECUTED).transition(target))
        self.audit.append(
            AuditEvent(
                "EXECUTION_COMPLETED",
                admission.request.request_id,
                admission.request.agent_id,
                outcome.status,
                attributes={"evidence_digest": outcome.evidence.digest, "verification": outcome.evidence.verification_status},
            )
        )
        return outcome

    def close(self) -> None:
        self.connection.close()
