from __future__ import annotations

from decimal import Decimal
from typing import Protocol
from uuid import UUID

from basalt_finance.governance.contracts import ExecutionIntent


class LedgerPostResult:
    def __init__(self, journal_entry_id: UUID, status: str, amount: Decimal, currency: str) -> None:
        self.journal_entry_id = journal_entry_id
        self.status = status
        self.amount = amount
        self.currency = currency


class LedgerPort(Protocol):
    def post_controlled_intent(self, intent: ExecutionIntent, idempotency_key: str) -> LedgerPostResult:
        """Post a governed effect to the authoritative financial ledger."""

    def verify(self, journal_entry_id: UUID) -> bool:
        """Verify the durable resulting state independently of submission success."""
