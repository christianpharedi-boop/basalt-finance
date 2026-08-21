from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import UUID

from basalt_finance.governance.contracts import AgentProposal
from basalt_finance.runtime import state

try:
    from mcp.server.fastmcp import FastMCP
except ImportError:  # pragma: no cover - allows core package use without MCP extras
    FastMCP = None  # type: ignore[assignment,misc]


mcp = FastMCP("Basalt Finance") if FastMCP is not None else None


if mcp is not None:

    @mcp.tool()
    def admit_financial_proposal(
        proposal_id: str,
        agent_id: str,
        tenant_id: str,
        action: str,
        resource: str,
        amount: str,
        currency: str,
        idempotency_key: str,
        correlation_id: str,
        parameters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Evaluate an untrusted financial proposal through Basalt governance."""
        proposal = AgentProposal(
            proposal_id=UUID(proposal_id),
            agent_id=agent_id,
            tenant_id=tenant_id,
            action=action,
            resource=resource,
            amount=Decimal(amount),
            currency=currency,
            idempotency_key=idempotency_key,
            correlation_id=correlation_id,
            parameters=parameters or {},
        )
        hardened = state.basalt_os.admit_authenticated(proposal, agent_id, tenant_id)
        decision = state.engine.evaluate(proposal, tenant_id)
        intent = state.engine.create_intent(proposal, decision)
        return {
            "decision": decision.model_dump(mode="json"),
            "hardened_decision": {
                "decision": hardened.decision.decision.value,
                "reason_code": hardened.decision.reason_code.value,
                "lifecycle_state": hardened.lifecycle.state.value,
            },
            "intent": intent.model_dump(mode="json") if intent else None,
        }


def run_mcp() -> None:
    if mcp is None:
        raise RuntimeError("Install the MCP extra to run the Basalt Finance MCP server")
    mcp.run()
