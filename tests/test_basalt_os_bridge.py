from decimal import Decimal
from uuid import uuid4

import pytest

from basalt_finance.governance.contracts import AgentProposal
from basalt_finance.integrations.basalt_os import BasaltOSControlPlane


def proposal(amount: str = "50000") -> AgentProposal:
    return AgentProposal(
        proposal_id=uuid4(),
        agent_id="treasury-agent-042",
        tenant_id="example-bank",
        action="payment.initiate",
        resource="corporate-account-001",
        amount=Decimal(amount),
        currency="ZAR",
        idempotency_key=f"bridge-{uuid4()}",
        correlation_id="bridge-test",
    )


def test_basalt_os_admits_and_executes_with_verified_evidence() -> None:
    control = BasaltOSControlPlane()
    admission = control.admit(proposal(), "basalt-finance-development-token")
    assert admission.decision.decision.value == "ALLOW"
    outcome = control.execute(admission)
    assert outcome.status == "VERIFIED"
    assert outcome.evidence.verify_integrity()
    assert control.lifecycle_repository.get(admission.request.request_id).state.value == "VERIFIED"
    control.close()


def test_basalt_os_requires_independent_approval_and_rejects_self_approval() -> None:
    control = BasaltOSControlPlane()
    admission = control.admit(proposal("100001"), "basalt-finance-development-token")
    assert admission.approval is not None
    with pytest.raises(ValueError, match="cannot approve"):
        control.decide_approval(admission.approval.approval_id, "treasury-agent-042", True, "self approval")
    approved = control.decide_approval(admission.approval.approval_id, "operator-001", True, "dual-control approval")
    assert approved.status.value == "APPROVED"
    assert control.lifecycle_repository.get(admission.request.request_id).state.value == "AUTHORIZED"
    control.close()


def test_basalt_os_rejects_tenant_mismatch() -> None:
    control = BasaltOSControlPlane()
    mismatched = proposal().model_copy(update={"tenant_id": "other-bank"})
    with pytest.raises(PermissionError, match="does not match"):
        control.admit(mismatched, "basalt-finance-development-token")
    control.close()


def test_authorize_after_approval_uses_authoritative_decision_record() -> None:
    control = BasaltOSControlPlane()
    admission = control.admit(proposal("100001"), "basalt-finance-development-token")
    assert admission.approval is not None
    approval = control.decide_approval(admission.approval.approval_id, "operator-002", True, "dual-control")
    promoted = control.authorize_after_approval(admission, approval)
    assert promoted.approval is approval
    assert promoted.decision.decision.value == "ALLOW"
    assert control.execute(promoted).status == "VERIFIED"
    control.close()
