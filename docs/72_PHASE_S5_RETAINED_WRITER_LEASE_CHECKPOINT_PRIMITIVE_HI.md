# Phase S5 — retained writer-lease checkpoint transition primitive

**तिथि:** 2026-11-26  
**Project:** ZCIRA-2026-11-13  
**स्थिति:** RETAINED-LEASE PRIMITIVE IMPLEMENTED / READ-ONLY CI PASS / NATIVE CHECKPOINTER PENDING / NO DEPLOYMENT

## 1. Canonical preflight

- Canonical repository: `manish91082-coder/zero-cost-internet-revenue-automation`; branch `main`.
- Preflight main HEAD: `50ae9f2ea1a12d58d4b38dc59151e999e9dd2f20`.
- Re-read: `PROJECT_CONTINUITY.md`, S2-B cloud-only architecture decision (`docs/45`), S1 roster contract (`docs/42`), machine-readable roster, S5 adapter/checkpoint policies, S5 durable-checkpoint design (`docs/71`), S6-B2 egress report (`docs/63`), S7-B2 publisher-isolation report (`docs/68`), S7-B ambiguous-commit report (`docs/69`) and S7-B3 Git Data integrity report (`docs/70`).
- Controlling Library archive: `02_complete-research-hi.md`, version 1, 1,402,707 bytes; previously materialized SHA-256 `c61be12a55385d0780a6a5bdf45f2fc22086be9edf6bbba96e78cfb0726d1e5`. The current archive was reopened through Files and its source index/ledger was read. Its legacy source-project heading is not the ZCIRA mission; only the explicitly registered category/destination source data is used here.
- A2.4-B: 219/219 category IDs across six batches; no missing, extra or duplicate IDs.
- A2.4-C: 8/8 shared lists, 168/168 entries, 213 explicit cross-reference edges.
- A2.5: 3,482 source occurrences; 315 repeated-name groups, 283 same-name/same-host candidates and 32 ambiguous groups. No identity merge; unique-platform count remains NOT ESTABLISHED.
- Priority order remains P1/P2/P3/P4/P5/B/M; Category #24 remains B. No scope or source ID was changed.

## 2. Defect closed in this increment

The existing `StateRepository` could acquire a repository writer lease and later atomically publish/release it, but it had no transition that committed one durable checkpoint while keeping the same single-writer lease active for the next checkpoint.

Without that transition, a native LangGraph saver could not safely perform repeated write-through checkpoint commits under one retained publisher lease.

## 3. Implementation

Added `StateRepository.commit_under_lease()` in `src/zcira_control/state_repository.py`.

The method:

1. Requires a timezone-aware timestamp and a bounded integer TTL (30–3,600 seconds; boolean values are rejected).
2. Requires the exact current branch head to equal the supplied lease commit SHA.
3. Rejects an active kill switch, wrong/inactive lease and expired lease.
4. Prevents the caller from replacing the canonical resource-lease object.
5. Refreshes expiry to at least `now + ttl_seconds` without shortening a later existing expiry.
6. Recomputes the lease idempotency digest after the expiry change.
7. Commits the caller's immutable state objects and refreshed lease in one manifest transition.
8. Retains the same `active_writer_lease_id` in the next manifest.
9. Returns the exact new commit SHA; the existing store performs commit fetch-back verification. The caller must use that SHA for its next transition. Stale head is rejected; no force push or blind retry is introduced.

The default checkpoint transition TTL is 900 seconds, consistent with the locked S5 policy. Finalization remains a separate `release_writer_lease()` transition after the last durable checkpoint/evidence commit.

## 4. Regression tests

Added five tests in `tests/test_state_persistence.py`:

- `test_commit_under_lease_retains_and_refreshes_writer_lease`: checkpoint state and active lease remain in the manifest; expiry and idempotency digest refresh; a second writer remains blocked; the same lease can then be released using the returned head.
- `test_commit_under_lease_rejects_stale_head_without_mutation`.
- `test_commit_under_lease_rejects_expired_lease_without_mutation`.
- `test_commit_under_lease_rejects_lease_replacement_by_caller`.
- `test_commit_under_lease_rejects_invalid_ttl` (three invalid TTL subcases).

These are deterministic `FakeDurableStore` tests. They do not call GitHub's live Git Data API and do not publish production evidence.

## 5. Exact commits and fetch-back

| Artifact | Commit | Fetched-back blob SHA |
|---|---|---|
| `src/zcira_control/state_repository.py` | `5f7e57513453ae4c501b34ca8713dca36c90c27e` | `e1c5894a50bdee5ea54b55337e091623abaf5f2c` |
| `tests/test_state_persistence.py` | `efcf51eeb951b5a58d6891ccd97affa8c881a748` | `eb25efafd5032dc1582dc4b73c7016db8d9e0657` |
| `config/s5_checkpoint_policy.v1.json` | `cdf3ac466ea2e48e29fdba4db751c809d6091ded` | `53e17cf1342ed984a2f93100fd2c80f24340f028` |
| `config/langgraph_adapter_policy.v1.json` | `d2fd3212c73c20e381b90d1c69e0ba15bb26ce8c` | `6f600cf519e997c13059c108a27893527fad8077` |
| `config/research_swarm_roster.v1.json` | `bf4a5add27d08dda8f1252001d7add52c8725f47` | `641aae77e095ded898866e815e110740555bb79f` |

Every changed source/config/test file was fetched from canonical `main`; returned blob SHA and exact content matched the submitted content.

## 6. GitHub Actions acceptance — observed

Three push-triggered S7-A read-only validations were observed:

- Code/test head `efcf51eeb951b5a58d6891ccd97affa8c881a748`: run [45748064728](https://github.com/manish91082-coder/zero-cost-internet-revenue-automation/actions/runs/45748064728), SUCCESS.
- S5 policy head `d2fd3212c73c20e381b90d1c69e0ba15bb26ce8c`: run [45748177348](https://github.com/manish91082-coder/zero-cost-internet-revenue-automation/actions/runs/45748177348), SUCCESS.
- Roster/config head `bf4a5add27d08dda8f1252001d7add52c8725f47`: run [45748309672](https://github.com/manish91082-coder/zero-cost-internet-revenue-automation/actions/runs/45748309672), SUCCESS.

Exact decoded job log for the latest run:

- Runner: `ubuntu-24.04`.
- Python: `3.12.3`.
- Hash-locked packages installed: 47.
- `pip check`: `No broken requirements found`.
- Real LangGraph runtime integration: 3 passed.
- Full suite: **205 passed, 1 expected skip, 9 subtests passed**.
- Expected skip: the LangGraph-missing fallback test, because the pinned LangGraph package is installed in this CI environment.

The latest roster/config validation was run 45748309672 on the exact roster commit above. This remains read-only CI validation, not a swarm run.

## 7. Explicit limitations

- Native `BaseCheckpointSaver` implementation: NOT IMPLEMENTED.
- Checkpoint and pending-write schemas/fixtures: PENDING.
- Graph-level `thread_id=run_id` crash/resume integration: PENDING.
- Pending-write ordering/idempotency and checkpoint history tests: PENDING.
- `delete_thread` logical tombstone semantics: PENDING; physical deletion/history rewrite remains prohibited.
- Live Git Data API write: NOT TESTED.
- Production evidence publication: NOT PERFORMED.
- Publisher workflow/write credential: DISABLED / NOT CREATED.
- Main branch protection/ruleset: NOT ENABLED.
- S6-B2 live egress: HOLD; live source requests remain zero.
- Cloudflare Worker/Cron/D1: NOT DEPLOYED.
- S9 unattended pilot: NOT STARTED.
- No runtime agent or scheduled swarm execution is active.

## 8. Next sequential work

1. Add Draft 2020-12 schemas and valid/negative fixtures for `langgraph_checkpoint` and `langgraph_pending_writes`; extend the manifest object-kind allowlist without changing existing schema meanings.
2. Implement the canonical-JSON-only synchronous `BaseCheckpointSaver` adapter backed by `StateRepository`; reject pickle/arbitrary objects/secrets/raw source body and enforce run/thread/size/count bounds.
3. Implement `put`, `put_writes`, `get_tuple` and bounded `list` with immutable identities, deterministic pending-write order and exact fetch-back.
4. Add real pinned-package crash-after-node/resume tests across two separate saver instances and a simulated ephemeral-runner boundary.
5. Keep `delete_thread` fail-closed until logical tombstone semantics are separately designed and tested; do not claim full BaseCheckpointSaver conformance prematurely.
6. Run the complete hash-locked read-only S7-A CI suite.
7. Continue S6-B2 egress and S7-B publisher-isolation gates separately. No live source request, publisher activation or S8 deployment before exact eligibility and approvals.

## 9. Mission and safety ledger

- Spend authorized/incurred: ₹0.
- Verified settled revenue: ₹0.
- Accounts/KYC/legal acceptance/billing/deployment/security testing/outreach/submissions/product build/listing/wallet signing: 0.
- Paid provider routes: disabled.
- Commercial release: HOLD until all five gates independently PASS.
- No local laptop/desktop/server is a runtime dependency.
