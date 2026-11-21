# Phase S6-D — LangGraph source-worker node integration

**Project:** ZCIRA-2026-11-13  
**Status:** IMPLEMENTED / GITHUB CI ACCEPTANCE PENDING  
**Scope:** Synthetic-transport-only, metadata-only, read-only LangGraph source-worker integration. No live source requests or repository publication.

## 1. Preflight and controlling sources

Before implementation, the current `PROJECT_CONTINUITY.md`, the S2-B cloud-only architecture decision, the S1 machine-readable roster and roster report, S6-B2 egress feasibility report, S6-C metadata snapshot report, S6 source-worker policy, and the controlling Library archive `02_complete-research-hi.md` version 1 were reopened.

The controlling archive was materialized and re-hashed:
- Size: 1,402,707 bytes
- SHA-256: `c61be12a55385d0780a6a5bdf45f2fc22086be9edf6bbba96e78cfb0726d1e5`
- Destination-section canonical hash remains `7e45078990d99d14e34a26befb3de2b8260fc53f35c6000fbe20fb741a36a24`

The 219 category IDs, 3,482 source occurrence slots, eight shared lists, 168 shared-list entries, 213 explicit cross-reference edges, P1/P2/P3/P4/P5/B/M order and Category #24=B are unchanged. Occurrence slots are not asserted to be unique platform identities.

## 2. Implementation

### New executor

`src/zcira_control/langgraph_source_worker.py`

- Builds a source-task executor from injected, versioned task/source-snapshot/evidence/envelope/proposal schemas.
- Requires an explicit transport factory.
- Accepts only transports marked `is_test_transport=True`.
- Refuses any source policy with `live_network_enabled`, `dns_pinning`, or `egress_controls_audited` set true. This is intentional while S6-B2 remains HOLD.
- Runs the existing read-only `run_source_snapshot_task`.
- Builds a metadata-only immutable envelope and validates it against the S6-C schema.
- Replaces the evidence excerpt with the envelope's redacted excerpt before producing the proposal.
- Computes a canonical proposal SHA-256.
- Does not return raw response bytes.

### LangGraph node

`src/zcira_control/langgraph_adapter.py`

- `build_langgraph_graph` accepts an optional injected source-worker executor.
- When supplied, the graph adds `source_workers` between planning and checkpoint proposal.
- `source_worker_execution_enabled` is an explicit boolean and defaults to disabled when absent.
- Only selected `source_snapshot` tasks assigned to the two official source-worker roles are eligible.
- The node independently enforces the two-worker maximum.
- Worker exceptions are converted to bounded error codes; no automatic retries are introduced.
- Worker proposals remain `PENDING` for review and `UNKNOWN` for commercial gates.
- A batch proposal is produced for the future S7-B publisher, with a digest and `write_authorized=false` / `write_performed=false`.
- Tasks are deliberately not marked completed merely because a proposal was produced.

### Proposal contract

- `schemas/v1/source_worker_proposal.schema.json`
- `tests/fixtures/s3_v1/valid_source_worker_proposal.json`
- Registered as the thirteenth versioned schema/fixture in `config/schema_contract_manifest.v1.json`.
- Added schema negative cases for raw-body persistence, worker writes, and non-completed tasks carrying evidence.

### Tests added

`tests/test_langgraph_source_worker.py` adds nine focused cases:
1. Metadata-only proposal and digest/path invariants.
2. Real LangGraph graph with at most two selected source workers.
3. Worker execution disabled by default.
4. Robots disallow produces blocked metadata and no evidence.
5. Live-network policy is refused.
6. Non-test transport is refused.
7. Raw payload returned by an injected executor is rejected.
8. Tampered batch digest is rejected.
9. Raw content injected into a proposal is rejected.

The existing contract suite adds one new valid-fixture parameter case and two negative contract tests.

## 3. Critical limitations

- The S6-D executor accepts synthetic test transports only. No live DNS, TLS, HTTP or public website request was made.
- S6-B2 provider-managed egress controls remain unaudited; `live_network_execution_enabled=false`, `dns_pinning=false`, `egress_controls_audited=false`.
- The LangGraph graph has no durable checkpointer. The source-worker batch is an in-memory, read-only publisher proposal only. It is not yet a committed checkpoint and does not make worker outputs durably resumable.
- S7-B must validate each proposal again, persist immutable metadata envelopes and evidence proposals through the single writer, fetch the exact Git object back, verify SHA-256/canonical JSON/schema, then update task/run state atomically.
- No model provider is called. No account, KYC, terms, billing, deployment, external submission, outreach, security test, commercial build, listing or spend occurred.

## 4. Acceptance status

The implementation and tests are committed. GitHub Actions acceptance for the latest S6-D code/config checkpoint has not yet been independently observed in this run. Therefore:
- S6-D code: IMPLEMENTED
- S6-D CI: PENDING / NOT CLAIMED PASS
- S6-D live source execution: DISABLED
- S6-D durable worker checkpoint: PENDING S7-B

Do not infer test success from the existence of the workflow or commit.

## 5. Financial and commercial ledger

- Spend authorized/incurred: ₹0
- Settled revenue evidence: ₹0
- Commercial execution: HOLD
- Five commercial gates remain mandatory and UNKNOWN is never PASS.
- No priority/category/source count has been changed.

## 6. Next sequence

1. Observe the latest GitHub Actions result for the S6-D head and fix any failures.
2. Re-run the complete hash-locked suite until a successful run is tied to the final code SHA.
3. Only then proceed to S7-B single-writer publisher: schema validation, idempotency, atomic Git commit, expected-head compare-and-swap, fetch-back verification, and no raw third-party body persistence.
4. Keep live source fetching disabled until an independently audited zero-cost egress-control design exists.
5. S8 cloud scheduling/deployment remains behind exact no-cost eligibility and owner approval; S9 remains not started.
