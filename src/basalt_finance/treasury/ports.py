from __future__ import annotations

from typing import Protocol
from uuid import UUID

from basalt_finance.governance.contracts import ExecutionIntent


class SettlementInstruction:
    def __init__(self, instruction_id: UUID, status: str, verification_required: bool = True) -> None:
        self.instruction_id = instruction_id
        self.status = status
        self.verification_required = verification_required


class TreasuryPort(Protocol):
    def create_settlement_instruction(
        self, intent: ExecutionIntent, idempotency_key: str
    ) -> SettlementInstruction:
        """Create a settlement instruction after governance has produced an intent."""

    def verify_settlement(self, instruction_id: UUID) -> bool:
        """Verify settlement state independently of request acceptance."""
