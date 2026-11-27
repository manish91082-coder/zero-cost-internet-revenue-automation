# Phase S5 — versioned LangGraph checkpoint and pending-write schema contracts

**तिथि:** 2026-11-27  
**Project:** ZCIRA-2026-11-13  
**स्थिति:** SCHEMA CONTRACTS PUBLISHED / EXACT-HEAD READ-ONLY CI PASS / NATIVE SAVER PENDING / NO DEPLOYMENT

## 1. Canonical preflight

- Canonical repository: `manish91082-coder/zero-cost-internet-revenue-automation`; branch `main`.
- Preflight main HEAD: `1fd7467b7b166da08702acd08d5965ff6a262ff0`.
- Re-read `PROJECT_CONTINUITY.md`, final cloud-only architecture decision `docs/45`, research swarm roster/control contract `docs/42`, S5 durable checkpoint design `docs/71`, retained writer-lease report `docs/72`, S7-B3 Git Data integrity report `docs/70`, current S5 policy and schema contract manifest.
- Controlling Library archive: `02_complete-research-hi.md`, version 1, 1,402,707 bytes; SHA-256 `c61be12a55385d0780a6a5bdf45f2fc22086be9edf6bbba96e78cfb0726d1e5`. The archive header identifies its legacy source project; ZCIRA uses only the already reconciled and registered category/destination data. No legacy project scope was imported.
- A2.4-B: 219/219 category IDs in six batches; missing/extra/duplicate IDs zero.
- A2.4-C: 8/8 shared lists, 168/168 entries and 213 explicit cross-reference edges.
- A2.5: 3,482 source occurrences; 315 repeated-name groups, 283 same-name/same-host candidates, 32 ambiguous groups. No identity merge; unique-platform count NOT ESTABLISHED.
- Priority order remains P1/P2/P3/P4/P5/B/M; Category #24 remains B.

## 2. New versioned contracts

Added two Draft 2020-12 schemas:

1. `schemas/v1/langgraph_checkpoint.schema.json`
   - Project and run/thread identity envelope.
   - Fixed empty `checkpoint_ns`.
   - Bounded checkpoint index 1–16.
   - Checkpoint ID, parent checkpoint ID and timestamp.
   - Explicit checkpoint fields and `SwarmGraphState` channel allowlist.
   - Metadata and channel-version structures.

2. `schemas/v1/langgraph_pending_writes.schema.json`
   - Project/run/thread/checkpoint binding.
   - Content-derived pending-write identity field.
   - Per-task identity and bounded task path.
   - 1–64 write records per batch.
   - Reserved LangGraph negative indexes -1 through -4 and ordinary indexes 0–63.
   - Explicit state-channel and reserved control-channel allowlist.

The manifest JSON Schema now recognizes `langgraph_checkpoint` and `langgraph_pending_writes`. The runtime `OBJECT_ID_FIELDS` map binds them respectively to `checkpoint_id` and `pending_write_id`. The schema contract manifest and S5 machine-readable policy now record the published schema paths and the fact that the native saver is still pending.

## 3. Contract-test coverage

Extended `tests/test_contract_schemas.py` with both new contracts and valid fixtures. Added negative/compatibility cases for:

- New object kinds accepted by the state-manifest schema.
- Unknown state channel rejected.
- Cross-mission checkpoint rejected.
- Non-empty checkpoint namespace rejected.
- Pending-write index outside the bounded range rejected.
- More than 64 records in a pending-write batch rejected.

The full test suite validates both new schemas and fixtures. These tests establish schema-level contracts only; they do not prove runtime cross-field equality, canonical JSON serialization, payload byte accounting, secret/raw-body scanning, idempotency, pending-write ordering, writer lease enforcement or graph recovery. Those remain native-saver acceptance tests.

## 4. Exact commit and fetch-back

- Schema/code commit: `46afca7cfa35931522cbb9b080eda75b67854a72`.
- Tree: `2ebefee32e0f7879b155d655cea342c0c2ea60e4`.
- All ten changed artifacts were fetched from the exact commit ref. Every returned Git blob SHA matched the SHA returned when the blob was created.

| Artifact | Verified blob SHA |
|---|---|
| `src/zcira_control/state_repository.py` | `0710ec0893b44c02c936cb57fd4227d7043021e3` |
| `schemas/v1/state_manifest.schema.json` | `77b2ee6a419ee8bf468fc92135292453451ed5ed` |
| `config/schema_contract_manifest.v1.json` | `cbd6aeed10890cd381766b33b587d80face0fa45` |
| `config/s5_checkpoint_policy.v1.json` | `84a24dfc64a128306f1de19af059e4ecd5b9068e` |
| `tests/test_contract_schemas.py` | `28fe489afbf537edfd98711a3efa094dbee78f88` |
| `schemas/v1/README.md` | `8904222f447292739d71e079db567e257d2c9c90` |
| `schemas/v1/langgraph_checkpoint.schema.json` | `fbb39c1b3ce2961df9535e53e015182dcec78ab9` |
| `schemas/v1/langgraph_pending_writes.schema.json` | `ac4d9776149f1cd5c6b8479e8494812eb1e55d60` |
| `tests/fixtures/s3_v1/valid_langgraph_checkpoint.json` | `21243bcb53e232e187f3007d3df46a5912335690` |
| `tests/fixtures/s3_v1/valid_langgraph_pending_writes.json` | `e08a6d4bb7803929cd4b0785741a11b4c3baf744` |

## 5. Exact-head GitHub Actions evidence

- Workflow: `ZCIRA S7-A read-only validation`.
- Run: [45930981211](https://github.com/manish91082-coder/zero-cost-internet-revenue-automation/actions/runs/45930981211).
- Tested head: `46afca7cfa35931522cbb9b080eda75b67854a72`.
- Job: `140283285807`; conclusion SUCCESS.
- Runner: `ubuntu-24.04`; Python `3.12.3`.
- 47 SHA-256-locked packages installed; `pip check`: no broken requirements.
- Real LangGraph integration: 3 passed.
- Full suite: **213 passed, 1 expected skip, 9 subtests passed**.

This was an ephemeral, read-only CI validation. It did not execute the swarm, call a model, fetch live source pages, perform a live Git Data API write or deploy any runtime.

## 6. Current S5 boundary

- Retained writer-lease transition: IMPLEMENTED / CI PASS.
- Checkpoint and pending-write schema contracts: PUBLISHED / exact-head CI PASS.
- State manifest object-kind allowlist: UPDATED.
- Native JSON-only `BaseCheckpointSaver`: NOT IMPLEMENTED.
- Runtime schema-validator composition: PENDING.
- `put`, `put_writes`, `get_tuple`, bounded `list`: NOT IMPLEMENTED.
- Cross-field run/thread/checkpoint identity enforcement: PENDING.
- Recursive secret, PII, raw-source-body and non-JSON rejection: PENDING.
- Per-checkpoint, per-batch and per-run byte accounting: PENDING.
- Pending-write idempotency/order restoration: PENDING.
- Crash/resume across separate saver instances and expired-lease reacquisition: NOT TESTED.
- `delete_thread`, prune and history rewrite: DISABLED; append-only Git history remains mandatory.
- Async graph execution: DISABLED.

## 7. Next sequential implementation

1. Implement a strict JSON serializer/validator that accepts only JSON-native primitives, lists and string-keyed objects; reject NaN/Infinity, bytes, sets, tuples, arbitrary objects and dangerous key names.
2. Add a synchronous `BaseCheckpointSaver` adapter backed only by `StateRepository` and `commit_under_lease`; compose the checkpoint schemas into the repository object validator.
3. Implement `put`, `put_writes`, `get_tuple` and bounded `list` with exact run/thread/namespace binding, content identity, duplicate idempotency, conflicting-write rejection, sorted pending writes, 16-checkpoint/256-KiB/64-KiB/4-MiB bounds and fetch-back before return.
4. Make deletion, pruning, thread copying and async methods fail closed.
5. Add fake Git transport tests and a pinned LangGraph graph interruption/resume test using two saver instances and a simulated runner boundary; prove a completed node is not re-executed.
6. Run the full hash-locked CI and update the policy only from observed run evidence.

No account, KYC, legal acceptance, billing, cloud deployment, security testing, external contact, submission, product build/listing, wallet signing or spend occurred. Live source fetch remains disabled; publisher write isolation remains disabled; S8 is not deployed; S9 is not started. Spend ₹0; settled revenue evidence ₹0; commercial execution HOLD.
