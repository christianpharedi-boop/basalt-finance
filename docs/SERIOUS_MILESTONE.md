# Basalt Finance Serious Milestone

## What changed

Basalt Finance now uses the refreshed Basalt OS package as an active control-plane dependency rather than only mirroring its concepts. The bridge is implemented in `basalt_finance.integrations.basalt_os.BasaltOSControlPlane`.

| Control | Basalt OS implementation now used |
|---|---|
| Enterprise identity | `EnterpriseIdentityAdapter` and `StaticEnterpriseAdapter` boundary |
| Agent identity | `AgentIdentity` derived from the authenticated principal |
| Delegated authority | `AgentPassport` with capabilities, resources, amount, currency, validity, and approval limits |
| Deterministic authorization | `AuthorizationEngine`, `Policy`, `PolicyRule`, and `DeterministicRiskEngine` |
| Approval | `ApprovalService` with requester self-approval rejection and mandatory reasons |
| Lifecycle | `ActionLifecycleRepository` backed by SQLite and explicit state transitions |
| Execution | `ExecutionGateway` with connector boundary and independent verification |
| Evidence | Digest-bearing `EvidenceRecord` with integrity verification |
| Audit | `AuditRepository` events for admission, approval, and execution |

## Operational path

```text
REST / MCP / A2A request
          |
          v
Typed AgentProposal
          |
          v
Enterprise identity + tenant match
          |
          v
Basalt OS passport + policy + deterministic risk
          |
     +----+----+
     |         |
   DENY   REQUIRE_APPROVAL
     |         |
     |    independent operator decision
     |         |
     +----+----+
          |
          v
Controlled ExecutionIntent
          |
          v
Basalt OS ExecutionGateway
          |
          v
Verification + EvidenceRecord + AuditEvent
          |
          v
VaultEq / ZeroClose / SureClose adapters
```

The API exposes three sensitive operations separately. `POST /v1/proposals/admit` admits untrusted intent and returns an approval identifier when required. `POST /v1/approvals/{approval_id}/decide` requires an independent approver and a reason. `POST /v1/intents/{intent_id}/execute` executes only a previously allowed and stored admission through the Basalt OS execution gateway. Settlement remains a separate operation through `POST /v1/intents/{intent_id}/settle`.

MCP and A2A structured financial proposals also call the Basalt OS bridge. They return the hardened decision and lifecycle state alongside the public Basalt Finance decision so protocol clients can observe governance status without receiving internal implementation details.

## Verification

The milestone currently passes **13 tests**, Ruff, and mypy. The tests cover real Basalt OS admission, passport and policy enforcement, independent approval, self-approval rejection, lifecycle persistence, evidence digest verification, tenant mismatch, REST proposal admission, REST approval decisions, MCP/A2A routing, and VaultEq/ZeroClose integration.

## Production qualification

The control-plane bridge is ready for controlled integration testing. Production deployment still requires replacing the development static identity adapter with a real enterprise identity provider, persisting approvals and audit events in production storage, configuring operator roles and dual control, using a production connector rather than the current mock execution connector, and completing independent security, privacy, resilience, and regulatory review.

The default development token remains a fixture. It must never be used for a live financial deployment.
