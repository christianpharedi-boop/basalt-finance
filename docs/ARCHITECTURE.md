# Basalt Finance Architecture

## Design thesis

Basalt Finance is not a chatbot attached to a bank. It is a **governed intelligence and financial-control platform**. Agent runtimes may interpret language, retrieve information, and propose actions. The control plane resolves authority, evaluates deterministic policy and risk, enforces approval, creates controlled intents, and records evidence. A ledger or downstream connector remains the source of truth for financial effects.

## Trust boundary

```text
External agent / LangGraph / A2A client
                  |
                  v
       AgentProposal: typed, untrusted intent
                  |
                  v
           ToolRegistry admission
                  |
                  v
       Tenant + identity context resolution
                  |
                  v
  Deterministic policy + risk + compliance checks
                  |
       +----------+-----------+
       |                      |
     DENY          REQUIRE_APPROVAL / ALLOW
                                  |
                                  v
                     Controlled ExecutionIntent
                                  |
                                  v
                     VaultEq / ZeroClose adapter
                                  |
                                  v
                   Verification + reconciliation
                                  |
                                  v
                        Evidence + audit trail
```

## Protocol surfaces

### REST API

The REST API is the canonical operational interface. It provides stable versioned routes, OpenAPI schemas, correlation identifiers, authentication hooks, typed request models, and deterministic response envelopes. The API must remain thin: business rules belong in the governance and financial-domain services, not in route functions.

### MCP

The MCP server exposes narrowly scoped tools and, later, governed resources and prompts. Every tool must be authenticated, tenant-aware, registered, rate-limited where appropriate, and routed through the same proposal and governance service used by REST and A2A. The MCP specification defines JSON-RPC-based stateful communication and server features including tools, resources, prompts, progress, cancellation, and error reporting [1]. Its security guidance requires explicit user consent, data protection, and caution around tool execution [1].

Basalt Finance must therefore treat tool metadata and model-generated tool calls as untrusted input. MCP authorization should use the protocol’s HTTP authorization model when exposed remotely, with OAuth resource metadata and least-privilege scopes [2].

### A2A

A2A is the inter-agent collaboration surface. Basalt Finance publishes an agent card, accepts messages, creates or returns tasks, and exposes task state. The current A2A implementation is intentionally narrow and compatible in shape with the standard; the next milestone should adopt the official Python SDK and validate the implementation against the protocol inspector.

The A2A model is appropriate for Basalt Finance because it separates agent interoperability from internal implementation. A2A defines agent cards, messages, parts, artifacts, stateful tasks, streaming, push notifications, and multiple bindings including HTTP/JSON, JSON-RPC, and gRPC [3]. Basalt Finance must never disclose hidden model reasoning, internal memory, or unrestricted tools through A2A. It should exchange only declared capabilities, structured proposals, task status, and verifiable artifacts.

## Financial composition

The first composed financial vertical should be treasury and controlled payments. Basalt OS contributes governance, passports, policy, approvals, memory, evidence, and audit. VaultEq contributes double-entry accounting, integer minor units, idempotency, KYC/AML, payments, and reconciliation. ZeroClose contributes treasury orchestration and settlement workflows. SureClose contributes operational controls, recovery handling, and auditable workflow patterns.

The integration rule is strict: **VaultEq computes financial truth; Basalt Finance governs whether an action may be proposed and under what conditions; ZeroClose coordinates external settlement; verification confirms the resulting state.** No LLM or A2A peer may calculate or mutate accounting truth directly.

## Milestones

| Milestone | Outcome |
|---|---|
| M1 | Typed governance core, REST API, MCP proposal tool, A2A agent card and task boundary |
| M2 | VaultEq ledger adapter, durable idempotency, audit/evidence persistence, and treasury read models |
| M3 | ZeroClose settlement-intent adapter, approval service, reconciliation workers, and failure recovery |
| M4 | A2A 1.0 SDK integration, streaming, task persistence, push-notification controls, and protocol conformance tests |
| M5 | Enterprise identity, operator dual control, policy lifecycle, observability, threat testing, and deployment assurance |

## References

[1]: https://modelcontextprotocol.io/specification/2025-06-18 — Model Context Protocol specification.

[2]: https://modelcontextprotocol.io/specification/draft/basic/authorization — MCP HTTP authorization specification.

[3]: https://github.com/a2aproject/A2A/blob/main/docs/specification.md — Agent2Agent protocol specification.
