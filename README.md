# Basalt Finance

Basalt Finance is a governed intelligent financial infrastructure platform for South Africa and the wider African market. It combines the control-plane principles of **Basalt OS** with deterministic financial computation from **VaultEq**, policy-driven treasury orchestration from **ZeroClose**, auditable operational workflows from **SureClose**, and provenance and evidence patterns from **Cerevia**, **CoreSignal**, **OysterBox**, and **Funeral OS**.

> Intelligent agents may propose. Basalt Finance decides, controls, verifies, and records.

## Current milestone

The repository currently provides a first vertical slice with a typed governance core, a polished FastAPI surface, a governed proposal endpoint, an MCP tool boundary, and an A2A-shaped HTTP interface with agent-card discovery and stateful tasks.

| Surface | Current capability |
|---|---|
| REST API | Health, agent-card discovery, proposal admission, and intent retrieval |
| Governance | Tenant-aware tool registration, deterministic policy, risk ceilings, approval thresholds, and execution intents |
| MCP | Governed financial proposal-admission tool using the Python MCP SDK when installed |
| A2A | Agent card, message submission, task retrieval, cancellation, structured proposal delegation |
| Financial core | Typed contracts and an adapter boundary prepared for VaultEq and ZeroClose integration |

## Repository composition

| Source repository | Basalt Finance role |
|---|---|
| [Basalt OS](https://github.com/christianpharedi-boop/basalt-os) | Identity, delegated authority, deterministic governance, approval, evidence, audit, memory, and compliance control plane |
| [VaultEq](https://github.com/christianpharedi-boop/vaulteq) | Double-entry ledger, idempotency, payments, KYC/AML, and reconciliation truth |
| [ZeroClose](https://github.com/christianpharedi-boop/zeroclose) | Treasury orchestration, settlement intent, and reconciliation workflows |
| [SureClose](https://github.com/christianpharedi-boop/sureclose) | Auditable operational workflows, controls, role separation, and recovery patterns |
| [Funeral OS](https://github.com/christianpharedi-boop/funeral-os) | South African compliance-first vertical patterns and regulated operational design |
| [Cerevia](https://github.com/christianpharedi-boop/cerevia) | Evidence infrastructure and traceable computation |
| [CoreSignal](https://github.com/christianpharedi-boop/coresignal) | Provenance, admission checks, data-quality gates, and reproducible evidence chains |
| [OysterBox](https://github.com/christianpharedi-boop/oystetbox) | Transferable provenance-first architecture and integrity controls |
| [OrbitVault Core](https://github.com/christianpharedi-boop/OrbitVault-Core) | Explainable deterministic engine, trace envelopes, REST, API-key discipline, and MCP implementation patterns |

## Run locally

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e '.[dev,a2a]'
pytest -q
ruff check src tests
mypy src
uvicorn basalt_finance.api.app:app --reload
```

The API exposes OpenAPI documentation at `/docs`, an A2A agent card at `/.well-known/agent-card.json`, and the A2A HTTP surface below `/a2a`.

The development bearer token is `basalt-finance-development-token`. It is a local-development fixture only and must be replaced by an injected enterprise identity adapter before deployment.

## Protocol direction

The MCP surface will follow the official MCP model of tools, resources, prompts, consent, and authorization. The A2A surface will align with the current A2A 1.0 data model and task semantics, including agent cards, messages, tasks, artifacts, streaming, and future push notifications. Neither protocol is allowed to bypass Basalt Finance governance.

## Non-custodial boundary

The current milestone does not hold funds, connect to a core banking system, or perform settlement. It creates controlled execution intents. Financial truth will be delegated to VaultEq-compatible ledger adapters, while downstream execution will remain outside the governance core and must return independently verifiable state.
