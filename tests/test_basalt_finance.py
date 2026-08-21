from decimal import Decimal
from uuid import uuid4

from fastapi.testclient import TestClient

from basalt_finance.api.app import app
from basalt_finance.governance.contracts import AgentProposal, Decision, ReasonCode
from basalt_finance.runtime import state

TOKEN_HEADERS = {"Authorization": "Bearer basalt-finance-development-token"}


def proposal(amount: str = "50000") -> AgentProposal:
    return AgentProposal(
        agent_id="treasury-agent-042",
        tenant_id="example-bank",
        action="payment.initiate",
        resource="corporate-account-001",
        amount=Decimal(amount),
        currency="ZAR",
        idempotency_key=f"test-{uuid4()}",
        correlation_id="test-correlation",
    )


def test_governance_allows_registered_action() -> None:
    result = state.engine.evaluate(proposal(), "example-bank")
    assert result.decision is Decision.ALLOW
    assert result.reason_code is ReasonCode.ALLOWED


def test_governance_requires_approval_above_threshold() -> None:
    result = state.engine.evaluate(proposal("100001"), "example-bank")
    assert result.decision is Decision.REQUIRE_APPROVAL
    assert result.reason_code is ReasonCode.APPROVAL_REQUIRED


def test_governance_denies_wrong_tenant() -> None:
    result = state.engine.evaluate(proposal(), "other-bank")
    assert result.decision is Decision.DENY
    assert result.reason_code is ReasonCode.TENANT_MISMATCH


def test_http_proposal_admission_creates_intent() -> None:
    response = TestClient(app).post("/v1/proposals/admit", headers=TOKEN_HEADERS, json=proposal().model_dump(mode="json"))
    assert response.status_code == 200
    payload = response.json()
    assert payload["decision"]["decision"] == "ALLOW"
    assert payload["intent"]["verification_requirements"]


def test_http_proposal_requires_authentication() -> None:
    response = TestClient(app).post("/v1/proposals/admit", json=proposal().model_dump(mode="json"))
    assert response.status_code == 401


def test_a2a_structured_proposal_task_completes() -> None:
    candidate = proposal().model_dump(mode="json")
    response = TestClient(app).post(
        "/a2a/message:send",
        json={
            "context_id": "ctx-1",
            "message": {"role": "user", "parts": [{"data": {"type": "financial_proposal", "proposal": candidate}}]},
            "metadata": {"tenant_id": "example-bank"},
        },
    )
    assert response.status_code == 200
    assert response.json()["state"] == "completed"


def test_agent_card_is_discoverable() -> None:
    response = TestClient(app).get("/.well-known/agent-card.json")
    assert response.status_code == 200
    assert response.json()["name"] == "Basalt Finance Governance Agent"


def test_http_approval_and_controlled_execution_path() -> None:
    client = TestClient(app)
    candidate = proposal("100001").model_dump(mode="json")
    admitted = client.post("/v1/proposals/admit", headers=TOKEN_HEADERS, json=candidate)
    assert admitted.status_code == 200
    admission = admitted.json()
    assert admission["decision"]["decision"] == "REQUIRE_APPROVAL"
    approval_id = admission["approval_id"]
    self_approval = client.post(
        f"/v1/approvals/{approval_id}/decide",
        headers=TOKEN_HEADERS,
        json={"approver_id": "treasury-agent-042", "approve": True, "reason": "not allowed"},
    )
    assert self_approval.status_code == 403
    approved = client.post(
        f"/v1/approvals/{approval_id}/decide",
        headers=TOKEN_HEADERS,
        json={"approver_id": "operator-001", "approve": True, "reason": "independent dual-control approval"},
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "APPROVED"
