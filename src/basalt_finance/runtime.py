from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from basalt_finance.governance.contracts import ExecutionIntent
from basalt_finance.governance.engine import GovernanceEngine, Policy, ToolRegistry


class RuntimeState:
    def __init__(self) -> None:
        self.registry = ToolRegistry()
        self.registry.register("example-bank", "treasury-agent-042", "payment.initiate")
        self.engine = GovernanceEngine(
            Policy(
                policy_id="basalt-finance-development",
                version="1",
                tenant_id="example-bank",
                allowed_actions=frozenset({"payment.initiate", "account.read"}),
                allowed_resources=frozenset({"corporate-account-001", "customer-001"}),
                currencies=frozenset({"ZAR", "USD"}),
                transaction_limit=Decimal(1000000),
                approval_above=Decimal(100000),
            ),
            self.registry,
        )
        self.intents: dict[UUID, ExecutionIntent] = {}


state = RuntimeState()
