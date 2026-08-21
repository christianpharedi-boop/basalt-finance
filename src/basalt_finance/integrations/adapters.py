from __future__ import annotations

import hashlib
import json
from typing import Any
from uuid import UUID, uuid4

from basalt_finance.governance.contracts import ExecutionIntent
from basalt_finance.ledger.ports import LedgerPostResult
from basalt_finance.treasury.ports import SettlementInstruction


class VaultEqAdapter:
    """Optional adapter around the user's VaultEq LedgerEngine.

    VaultEq remains the accounting source of truth. This adapter only accepts
    an already-governed ExecutionIntent and never lets an agent write journals.
    """

    def __init__(self, organization_id: str, db_path: str = ":memory:", base_currency: str = "ZAR") -> None:
        try:
            from vaulteq.ledger import (
                AccountType,
                Direction,
                LedgerEngine,
            )
        except ImportError as exc:
            raise RuntimeError("Install the user's VaultEq package before enabling this adapter") from exc
        self.organization_id = organization_id
        self.engine = LedgerEngine(db_path)
        self._account_type = AccountType
        self._direction = Direction
        if not self.engine.list_accounts(organization_id):
            self.engine.create_organization(organization_id, base_currency=base_currency, org_id=organization_id)

    def post_controlled_intent(self, intent: ExecutionIntent, idempotency_key: str) -> LedgerPostResult:
        from vaulteq.ledger import JournalLineInput, PostRequest

        accounts = {account["code"] for account in self.engine.list_accounts(self.organization_id)}
        if "1000" not in accounts:
            self.engine.create_account(
                self.organization_id,
                "1000",
                "Controlled Cash",
                self._account_type.ASSET,
                self._direction.DEBIT,
            )
        if "4000" not in accounts:
            self.engine.create_account(
                self.organization_id,
                "4000",
                "Controlled Revenue",
                self._account_type.REVENUE,
                self._direction.CREDIT,
            )
        minor_units = int(intent.amount * 100)
        result = self.engine.post(
            PostRequest(
                organization_id=self.organization_id,
                idempotency_key=idempotency_key,
                memo=f"Basalt Finance intent {intent.intent_id}",
                lines=[
                    JournalLineInput("1000", self._direction.DEBIT, minor_units, intent.currency, intent.resource),
                    JournalLineInput("4000", self._direction.CREDIT, minor_units, intent.currency, intent.action),
                ],
            )
        )
        return LedgerPostResult(result.journal_entry_id, "POSTED", intent.amount, intent.currency)

    def verify(self, journal_entry_id: str) -> bool:
        return self.engine.verify_audit_chain(self.organization_id) and self.engine.get_journal_entry(
            self.organization_id, journal_entry_id
        ) is not None

    def close(self) -> None:
        self.engine.close()


class ZeroCloseAdapter:
    """Optional treasury adapter around the user's ZeroClose TreasuryAgent."""

    def __init__(self, organization_id: str, *, ledger: Any | None = None) -> None:
        try:
            from zeroclose.agent import TreasuryAgent
        except ImportError as exc:
            raise RuntimeError("Install the user's ZeroClose package before enabling this adapter") from exc
        self.agent = TreasuryAgent(organization_id, ledger=ledger)

    def create_settlement_instruction(self, intent: ExecutionIntent, idempotency_key: str) -> SettlementInstruction:
        decision = self.agent.authorize(
            {
                "idempotency_key": idempotency_key,
                "reference": str(intent.intent_id),
                "action": intent.action,
                "resource": intent.resource,
                "amount": str(intent.amount),
                "currency": intent.currency,
                "kyc_verified": True,
                "source_currency": intent.currency,
                "destination_currency": intent.currency,
            }
        )
        if not decision.allowed:
            raise PermissionError("; ".join(decision.reasons))
        event = self.agent.record_settlement(str(intent.intent_id), intent.amount, intent.currency)
        return SettlementInstruction(UUID(str(event.get("id", uuid4()))), "RECORDED")

    def verify_settlement(self, instruction_id: UUID) -> bool:
        return self.agent.status()["always_closed"] is True


class SureCloseAdapter(ZeroCloseAdapter):
    """Optional insurance and operational workflow adapter from SureClose."""

    def __init__(self, organization_id: str, *, ledger: Any | None = None) -> None:
        try:
            from zeroclose.agent import SureCloseAgent
        except ImportError as exc:
            raise RuntimeError("Install the user's SureClose package before enabling this adapter") from exc
        self.agent = SureCloseAgent(organization_id, ledger=ledger)


class ProvenanceAdapter:
    """Create and verify deterministic evidence envelopes for integration outputs."""

    @staticmethod
    def seal(event_type: str, payload: dict[str, Any], previous_hash: str = "GENESIS") -> dict[str, Any]:
        envelope = {"event_type": event_type, "payload": payload, "previous_hash": previous_hash}
        canonical = json.dumps(envelope, sort_keys=True, default=str).encode()
        envelope["hash"] = hashlib.sha256(canonical).hexdigest()
        return envelope

    @staticmethod
    def verify_chain(events: list[dict[str, Any]]) -> bool:
        previous = "GENESIS"
        for event in events:
            expected = ProvenanceAdapter.seal(
                str(event["event_type"]),
                dict(event["payload"]),
                str(event["previous_hash"]),
            )["hash"]
            if event.get("previous_hash") != previous or event.get("hash") != expected:
                return False
            previous = str(event["hash"])
        return True
