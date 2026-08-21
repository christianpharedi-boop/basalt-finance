from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from .contracts import (
    AgentProposal,
    Decision,
    ExecutionIntent,
    GovernanceDecision,
    ReasonCode,
)


@dataclass(frozen=True)
class Policy:
    policy_id: str
    version: str
    tenant_id: str
    allowed_actions: frozenset[str]
    allowed_resources: frozenset[str]
    currencies: frozenset[str]
    transaction_limit: Decimal
    approval_above: Decimal | None = None


class ToolRegistry:
    def __init__(self) -> None:
        self._actions: dict[tuple[str, str], set[str]] = {}

    def register(self, tenant_id: str, agent_id: str, action: str) -> None:
        self._actions.setdefault((tenant_id, agent_id), set()).add(action)

    def is_registered(self, proposal: AgentProposal) -> bool:
        return proposal.action in self._actions.get((proposal.tenant_id, proposal.agent_id), set())


class GovernanceEngine:
    def __init__(self, policy: Policy, registry: ToolRegistry) -> None:
        self.policy = policy
        self.registry = registry

    def evaluate(self, proposal: AgentProposal, authenticated_tenant: str) -> GovernanceDecision:
        if proposal.tenant_id != authenticated_tenant:
            return self._decision(proposal, Decision.DENY, ReasonCode.TENANT_MISMATCH, "tenant does not match authenticated context")
        if not self.registry.is_registered(proposal):
            return self._decision(proposal, Decision.DENY, ReasonCode.TOOL_NOT_REGISTERED, "action is not registered for this agent and tenant")
        if proposal.amount < 0:
            return self._decision(proposal, Decision.DENY, ReasonCode.INVALID_AMOUNT, "amount must be non-negative")
        if proposal.action not in self.policy.allowed_actions or proposal.resource not in self.policy.allowed_resources:
            return self._decision(proposal, Decision.DENY, ReasonCode.POLICY_DENIED, "policy does not permit this action or resource")
        if proposal.currency not in self.policy.currencies:
            return self._decision(proposal, Decision.DENY, ReasonCode.CURRENCY_NOT_ALLOWED, "currency is not permitted by policy")
        if proposal.amount > self.policy.transaction_limit:
            return self._decision(proposal, Decision.DENY, ReasonCode.RISK_DENIED, "amount exceeds the policy risk ceiling", 90)
        if self.policy.approval_above is not None and proposal.amount > self.policy.approval_above:
            return self._decision(proposal, Decision.REQUIRE_APPROVAL, ReasonCode.APPROVAL_REQUIRED, "independent approval is required", 20)
        return self._decision(proposal, Decision.ALLOW, ReasonCode.ALLOWED, "all deterministic governance checks passed")

    def create_intent(self, proposal: AgentProposal, decision: GovernanceDecision) -> ExecutionIntent | None:
        if decision.decision is not Decision.ALLOW:
            return None
        return ExecutionIntent(
            proposal_id=proposal.proposal_id,
            action=proposal.action,
            resource=proposal.resource,
            amount=proposal.amount,
            currency=proposal.currency,
        )

    def _decision(
        self,
        proposal: AgentProposal,
        decision: Decision,
        reason_code: ReasonCode,
        explanation: str,
        risk_score: int = 0,
    ) -> GovernanceDecision:
        return GovernanceDecision(
            decision=decision,
            reason_code=reason_code,
            proposal_id=proposal.proposal_id,
            agent_id=proposal.agent_id,
            tenant_id=proposal.tenant_id,
            action=proposal.action,
            resource=proposal.resource,
            policy_id=self.policy.policy_id,
            policy_version=self.policy.version,
            explanation=explanation,
            risk_score=risk_score,
        )
