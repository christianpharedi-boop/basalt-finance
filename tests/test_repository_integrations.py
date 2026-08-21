from decimal import Decimal
from pathlib import Path

from basalt_finance.governance.contracts import ExecutionIntent
from basalt_finance.integrations.adapters import VaultEqAdapter, ZeroCloseAdapter


def intent() -> ExecutionIntent:
    return ExecutionIntent(
        proposal_id="00000000-0000-0000-0000-000000000001",
        action="payment.initiate",
        resource="corporate-account-001",
        amount=Decimal("125.00"),
        currency="ZAR",
    )


def test_vaulteq_adapter_posts_and_verifies(tmp_path: Path) -> None:
    adapter = VaultEqAdapter("basalt-test", str(tmp_path / "ledger.db"))
    result = adapter.post_controlled_intent(intent(), "integration-key-1")
    assert result.status == "POSTED"
    assert result.amount == Decimal("125.00")
    assert adapter.verify(result.journal_entry_id)
    adapter.close()


def test_zeroclose_adapter_records_controlled_settlement() -> None:
    adapter = ZeroCloseAdapter("basalt-test")
    result = adapter.create_settlement_instruction(intent(), "integration-settlement-1")
    assert result.status == "RECORDED"
    assert result.verification_required
    assert adapter.verify_settlement(result.instruction_id)
