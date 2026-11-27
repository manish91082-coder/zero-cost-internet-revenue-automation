# Phase S5 — native JSON-only LangGraph checkpointer implementation

**तिथि:** 2026-11-27  
**Project:** ZCIRA-2026-11-13  
**स्थिति:** NATIVE SAVER CORE + EDGE CASES PASS / FULL BASE CONFORMANCE NOT CLAIMED / NO DEPLOYMENT

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

## 5. First corrective CI result and second demonstrated gap

The first routing-channel correction was committed at `2ea9aec1c439cbdd533c3d8acd0f0f40b14d4dec`. Exact-head run [45933219636](https://github.com/manish91082-coder/zero-cost-internet-revenue-automation/actions/runs/45933219636) completed **FAILURE**: 222 passed, 1 failed, 1 expected skip, 9 subtests. The decoded failure moved past `put_writes` and identified `checkpoint.channel_values` containing `branch:to:node_a`; the checkpoint schema still had a state-only `propertyNames.enum`. This confirmed that LangGraph route channels must be handled in both checkpoint snapshots and pending writes.

The second correction now applies the bounded route pattern to checkpoint `channel_values` as well as pending writes, and the Python validator accepts route channels only after exact graph-node binding. A new test proves a route channel is rejected before binding and accepted after binding in a checkpoint snapshot.

## 6. Exact-head validation — observed PASS

- Exact code head: `c01d8e46fe6355fcfe43a5f9c995816ff5db882d`.
- GitHub Actions run: [45933402182](https://github.com/manish91082-coder/zero-cost-internet-revenue-automation/actions/runs/45933402182); job: `140290971295`; conclusion: **SUCCESS**.
- Runner: `ubuntu-24.04`; Python: `3.12.3`; LangGraph: `1.2.22`; hash-locked packages installed: 47.
- `pip check`: `No broken requirements found`.
- Real LangGraph runtime integration: **3 passed**.
- Full pytest: **225 passed, 1 expected skip, 9 subtests passed**; 0 failures.
- Decoded job log confirms the full hash-locked validation step completed. The expected skip is the LangGraph-missing fallback test, because the pinned LangGraph package is installed.
- This is read-only CI against FakeDurableStore. It does not prove live Git Data API write, production publisher isolation, source egress safety or cloud deployment.
- Exact fetch-back for the code/schema/test commit `c01d8e46fe6355fcfe43a5f9c995816ff5db882d` returned the committed blob SHAs recorded in the continuity log. The policy/report/continuity metadata update is a separate documentation/config commit.

**Acceptance boundary:** synchronous core methods `put`, `put_writes`, `get_tuple`, and bounded `list` are implemented and exact-head CI-tested. `delete_thread` and async methods remain disabled fail-closed; therefore full `BaseCheckpointSaver` conformance is **NOT CLAIMED**.

## 7. Next action

1. Observe the exact-head read-only S7-A run.
2. If it passes, fetch back every changed artifact and record the exact run/job/log counts in this report, S5 policy and `PROJECT_CONTINUITY.md`.
3. If it fails, inspect the decoded job log, correct only the demonstrated contract mismatch, and rerun. Do not bypass channel, schema, quota or approval controls.
4. After native checkpointer acceptance, continue separate S6-B2 egress and S7 publisher-isolation gates. Do not enable source fetching, live publishing, S8 deployment or S9 pilot.


## 8. Current disposition after code CI

The native saver core is accepted for the deterministic FakeDurableStore test harness only. Do not interpret this as permission to activate a live publisher. The next S5 work is a separate edge-case review (idempotent retry timestamp handling, zero-limit listing semantics, exact graph binding tests) before S5 is frozen. S6-B2 egress, S7 mechanical writer isolation, S8 deployment and S9 unattended pilot remain independently blocked by their existing gates.


## 9. Additional S5 edge-case hardening — observed PASS

A post-pass code review found three edge cases and closed them before S5 core freeze:
1. A retry of the same pending-write identity at a later clock time generated a different `created_at`, so a logically identical retry could be rejected as conflicting. Duplicate comparison now excludes only `created_at`; all identity, task, path and write content fields remain exact. Conflicting content still fails closed.
2. `list(limit=0)` previously entered the loop and could emit one item. It now returns an empty iterator after validating the arguments.
3. The adapter's `build_langgraph_graph(..., checkpointer=...)` node-binding hook lacked a direct test. The FakeStateGraph now accepts the checkpointer argument and a recorder test verifies the exact node set is bound before compile.

Added tests cover clock-advanced retry idempotency, conflicting content, zero-limit listing and adapter-level node binding. The code-only changes are committed separately; their exact-head CI is pending. Existing accepted code-head run 45933402182 remains the last observed PASS until the new run completes.


Exact-head edge-hardening validation:
- Commit: `49ebf122b198855d6f3ecaf87d7b225985233c09`.
- GitHub Actions run: [45933633563](https://github.com/manish91082-coder/zero-cost-internet-revenue-automation/actions/runs/45933633563); job `140291698070`; SUCCESS.
- Python 3.12.3; LangGraph 1.2.22; 47 hash-locked packages; pip check clean.
- Real LangGraph runtime integration: 3 passed.
- Full pytest: **228 passed, 1 expected skip, 9 subtests passed, 0 failures**.
- The expected skip is the LangGraph-missing fallback test because the pinned runtime is installed.
- Exact fetch-back SHA values for the six changed artifacts are recorded in the canonical commit/continuity history; no live Git Data write was made.

S5 disposition: synchronous JSON-only saver core, route binding, crash/resume harness and reviewed edge cases PASS in FakeDurableStore CI. Full `BaseCheckpointSaver` conformance remains false because `delete_thread` and async methods are deliberately disabled fail-closed. Production publisher activation remains blocked.


### Policy metadata validation

The policy/report/continuity metadata commit `f9ec51dc79caa355bdb5758f81b87a1851a377a3` passed run [45933726265](https://github.com/manish91082-coder/zero-cost-internet-revenue-automation/actions/runs/45933726265), job `140291995234`: SUCCESS; 228 passed, 1 expected skip, 9 subtests, 47 hash-locked packages, pip check clean, 3 LangGraph runtime tests passed.
