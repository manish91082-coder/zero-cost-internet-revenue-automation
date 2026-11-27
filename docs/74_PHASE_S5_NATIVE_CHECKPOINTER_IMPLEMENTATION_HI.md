# Phase S5 — native JSON-only LangGraph checkpointer implementation

**तिथि:** 2026-11-27  
**Project:** ZCIRA-2026-11-13  
**स्थिति:** NATIVE SAVER IMPLEMENTED / EXACT-HEAD CI PENDING / NO DEPLOYMENT

## 1. Canonical preflight and immutable mission scope

- Canonical repository: `manish91082-coder/zero-cost-internet-revenue-automation`; branch: `main`.
- Preflight HEAD: `337db20197cfa3982b80e103b2b1dd99cb87b68b`.
- Re-read: `PROJECT_CONTINUITY.md`, S2-B ADR `docs/45`, roster contract `docs/42`, machine-readable roster, S5 design/schema/retained-lease reports `docs/71`, `docs/72`, `docs/73`, S6-B2 egress report `docs/63`, and S7-B3 Git Data integrity report `docs/70`.
- Controlling Library archive `02_complete-research-hi.md`, version 1: 1,402,707 bytes; materialized SHA-256 `c61be12a55385d0780a6a5bdf45f2fc22086be9edf6bbba96e78cfb0726d1e5` (exact byte hash verified).
- A2.4-B: 219/219 category IDs across six batches; zero missing/extra/duplicate IDs. A2.4-C: 8/8 shared lists, 168/168 rows, 213 explicit edges. A2.5: 3,482 occurrences, 315 repeated-name groups, 283 same-name/same-host candidates, 32 ambiguous groups; no identity merge; unique-platform count NOT ESTABLISHED.
- Priority order P1/P2/P3/P4/P5/B/M and Category #24=B unchanged.

## 2. Failed exact-head acceptance attempts and root cause

Three successive read-only CI attempts exposed two separate compatibility gaps:
- Run [45932116752](https://github.com/manish91082-coder/zero-cost-internet-revenue-automation/actions/runs/45932116752): 1 failed, 219 passed, 1 expected skip, 9 subtests. The checkpoint channel schema rejected LangGraph's `__start__` input channel.
- Run [45932263476](https://github.com/manish91082-coder/zero-cost-internet-revenue-automation/actions/runs/45932263476): after the checkpoint-channel correction, pending-write channel validation still failed.
- Run [45932408839](https://github.com/manish91082-coder/zero-cost-internet-revenue-automation/actions/runs/45932408839): same pending-write failure. Job log showed the failing START task path `~__pregel_pull, __start__`.

The second failure is not a user-state channel. LangGraph's StateGraph creates internal routing channels using the `branch:to:{target}` form; these are control-flow writes, not fields in `SwarmGraphState`. A state-only channel enum therefore rejects a legitimate START/edge write. Upstream StateGraph source: https://github.com/langchain-ai/langgraph/blob/main/libs/langgraph/langgraph/graph/state.py

## 3. Corrective implementation

### 3.1 Exact graph-node binding

`LangGraphCheckpointSaver.bind_graph_nodes()` now binds a bounded set of 1–32 lowercase node names from the compiled graph. Duplicate, malformed, oversized or changed node sets are rejected.

`build_langgraph_graph(..., checkpointer=...)` invokes this binding before graph compilation when the supplied saver exposes the binding method.

### 3.2 Narrow routing-channel permission

The saver now accepts:
- Existing `SwarmGraphState` channels.
- Explicit LangGraph special write channels in the pinned `WRITES_IDX_MAP`.
- `__start__` as a checkpoint/input channel.
- `branch:to:{node}` only when `node` is in the exact graph-bound node set.
- `branch:to:__end__` as the one fixed terminal target.

Unknown branch targets remain rejected. The JSON Schema constrains route syntax; runtime binding provides the stricter exact-node check. No wildcard routing channel is accepted.

### 3.3 Regression coverage

- Added runtime test proving route writes fail before binding, pass for a bound node, and fail for an unbound target.
- Added schema tests for valid bounded route syntax and malformed target syntax.
- Real LangGraph two-saver interruption/resume test now binds the exact `node_a` / `node_b` graph node set before invocation.
- Existing JSON-only serialization, identity, byte, lease, pending-write order/idempotency and append-only deletion controls remain unchanged.

## 4. Scope and safety boundary

This is code/schema/test work only. The saver uses the existing FakeDurableStore in CI. No live Git Data API write, publisher credential, live source fetch, model call, cloud deployment, account action, KYC, legal acceptance, outreach, product build/listing or spend occurred.

S6-B2 egress remains HOLD; live source requests remain disabled. S7 publisher isolation and live write remain disabled. S8 Cloudflare is not deployed. S9 unattended pilot is not started. Commercial execution remains HOLD; spend ₹0; settled revenue evidence ₹0.

## 5. Exact-head validation

This report records the implementation checkpoint before the new commit-triggered S7-A validation. The new code/schema/tests are **CI PENDING** until the exact pushed head has a completed successful run and the decoded job log is inspected. A push or a queued run is not a PASS.

## 6. Next action

1. Observe the exact-head read-only S7-A run.
2. If it passes, fetch back every changed artifact and record the exact run/job/log counts in this report, S5 policy and `PROJECT_CONTINUITY.md`.
3. If it fails, inspect the decoded job log, correct only the demonstrated contract mismatch, and rerun. Do not bypass channel, schema, quota or approval controls.
4. After native checkpointer acceptance, continue separate S6-B2 egress and S7 publisher-isolation gates. Do not enable source fetching, live publishing, S8 deployment or S9 pilot.
