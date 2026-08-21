from __future__ import annotations

import os
from decimal import Decimal
from uuid import UUID

from basalt_finance.governance.contracts import ExecutionIntent
from basalt_finance.governance.engine import GovernanceEngine, Policy, ToolRegistry
from basalt_finance.integrations.adapters import VaultEqAdapter, ZeroCloseAdapter
from basalt_finance.integrations.basalt_os import BasaltOSControlPlane


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
        self.admissions: dict[UUID, object] = {}
        self.basalt_os = BasaltOSControlPlane(sqlite_path=os.getenv("BASALT_FINANCE_CONTROL_DB", ":memory:"))
        self.ledger: VaultEqAdapter | None = None
        self.treasury: ZeroCloseAdapter | None = None
        if os.getenv("BASALT_FINANCE_ENABLE_REPOSITORY_INTEGRATIONS", "false").lower() == "true":
            organization_id = os.getenv("BASALT_FINANCE_ORGANIZATION_ID", "example-bank")
            ledger_db = os.getenv("BASALT_FINANCE_LEDGER_DB", "basalt-finance.db")
            self.ledger = VaultEqAdapter(organization_id, ledger_db)
            self.treasury = ZeroCloseAdapter(organization_id, ledger=self.ledger)


state = RuntimeState()
