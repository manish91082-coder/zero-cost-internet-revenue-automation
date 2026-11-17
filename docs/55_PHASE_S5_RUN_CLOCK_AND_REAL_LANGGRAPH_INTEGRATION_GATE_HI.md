# Phase S5 — Run-clock correctness और real LangGraph integration gate (2026-11-17)

## Executive status

**S5 CORE HARDENED / MOCK CONTRACT BASELINE PASS 96 (historical) / 3 NEW REGRESSION TESTS NOT EXECUTED / 3 REAL-LANGGRAPH INTEGRATION TESTS COMMITTED BUT NOT EXECUTED / S5 PARTIAL.**

यह increment केवल canonical ZCIRA repository में code और test artifacts बदलता है। कोई workflow, cloud service, account, model provider, secret, OAuth permission या external runtime activate नहीं किया गया।

## 1. Continuity and source verification

इस increment से पहले पढ़े/verify किए गए controlling artifacts:

- `PROJECT_CONTINUITY.md` — current fetched blob `ce897e230f82570be88a9b1ef06c61f965de5a03`.
- Cloud-only architecture decision `docs/45_PHASE_S2B_FINAL_CLOUD_ONLY_FAILOVER_ARCHITECTURE_DECISION_HI.md` — blob `fe395806fd9a877dd696e21dbb7da5fed4fc1d8c`.
- S1 roster `config/research_swarm_roster.v1.json` — blob `2d6cf0c2e2f6113e4da5d362fef200e83a4e6444`.
- S4-B report `docs/53_PHASE_S4B_DURABLE_GIT_STATE_AND_WRITER_LEASE_HI.md` — current blob `722db8f54715a55feb6d9352fb65063bb792fe76`.
- S5 contract report `docs/54_PHASE_S5_LANGGRAPH_ADAPTER_CONTRACT_HI.md` — source report remains the controlling S5 design record.
- Controlling Library source archive `02_complete-research-hi.md`, version 1, full SHA-256 `c61be12a55385d0780a6a5bdf45f2fc22086be9edf6bbba96e78cfb0726d1e5e`; the materialized bytes were independently hashed in this run.

A2.4-B, A2.4-C and A2.5 source reconciliations are unchanged: 219/219 category IDs, 8 shared lists / 168 entries / 213 explicit category-to-list edges, 3,482 source occurrence slots. No destination row was deleted or merged; unique platform count remains NOT ESTABLISHED. Priority order/counts and Category #24=B remain locked.

## 2. Correctness defect found and fixed

Static review of the real LangGraph adapter found a run-clock semantic defect:

- The graph wrote `finished_at=now` even when the checkpoint status was `QUEUED` or `PAUSED` and pending tasks remained.
- Resume input did not carry the original `started_at`, so a resumed run could appear to have started again.

Changes in `src/zcira_control/langgraph_adapter.py`:

1. `started_at` is now carried through the run state and preserved across resume.
2. A future `started_at` is rejected.
3. `finished_at` remains null for QUEUED and PAUSED runs and for PARTIAL runs that still have pending work.
4. `finished_at` is set only for terminal COMPLETED/FAILED states, or PARTIAL with no remaining pending task IDs.

Three regression tests were added to `tests/test_langgraph_adapter.py`:
- queued run keeps `finished_at=null` and preserves original start;
- completed run records a finish timestamp;
- resumed run preserves the original start timestamp.

These three new tests are **committed but not yet executed**. The previously verified 96-test result remains the last executed baseline; it must not be reported as 99 passing.

## 3. Real LangGraph package integration harness

New file: `tests/test_langgraph_runtime_integration.py`.

It contains three real-package tests, skipped when LangGraph is absent:

1. Exact package version `langgraph==1.2.22`, actual `StateGraph` compile/invoke and maximum-two-worker plan.
2. Actual graph pause path when the kill switch is active.
3. Resume from a publisher-shaped run-state fixture while preserving completed task IDs and original run clock.

The harness performs no model call, network request, repository write, account action or external contact. It uses the real LangGraph library only for graph construction/execution; durable persistence remains the separate Git-backed publisher contract. It does not use LangGraph Agent Server, CLI, Studio, LangSmith or hosted deployment.

## 4. Package integrity and execution blocker

Official PyPI currently lists LangGraph 1.2.22, released 14 Nov 2026, MIT, Python >=3.10. The published wheel SHA-256 is `0f8ebec55a58667e40474a0e55bdb4f06a8c7a1d98cde2b7c8d996a2ee78fe3f`, matching the repository's direct-package hash pin.

PyPI's release page reports **no provenance attestation** for the 1.2.22 wheel. The direct wheel hash is recorded, but a complete transitive dependency lock with hashes is still required before production use.

A package-install attempt in the available isolated validation container failed because DNS resolution for the package index was unavailable. The wheel download also could not be completed from that environment. This is an environment/network limitation, not evidence that the package itself is broken. No local owner device was used and no project runtime depends on that container.

The existing sequence says not to add `.github/workflows/**` until S7. Therefore this run did not create a workflow merely to force a package install. The actual package integration gate remains pending a verified GitHub-hosted ephemeral test runner with a hash-locked dependency set.

## 5. Dependency-order issue and safe resolution

There is a sequencing dependency:

- S5 requires a real package compile/invoke/resume smoke test on a verified ephemeral runner.
- The current S5 phase boundary prohibits creating GitHub Actions workflows.
- S6 is explicitly blocked until S5's real integration passes.
- S7 is currently the first phase allowed to create CI.

Do not bypass this by silently creating a workflow in S5. The safe next implementation is a **read-only S7-A validation workflow** with no secrets, no write permissions, no artifacts that mutate the repository, no cloud deployment and a serialized concurrency group. It should:
- install only hash-locked dependencies;
- run the full existing test suite plus the three new regression tests;
- install the exact LangGraph wheel with its verified hash;
- run the three real LangGraph integration tests;
- upload no credential and perform no repository write.

After this read-only validation workflow proves the actual package integration, proceed to S6. Complete S7-B later for publisher-only write permissions, branch protection and mechanical single-writer enforcement. This is a proposed phase split, not an implemented workflow.

## 6. Current verified status

| Item | Status |
|---|---|
| S4-B durable-state mocked tests | PASS, historical verified baseline |
| S5 mocked graph tests | PASS 24, historical verified baseline |
| Combined executed tests before this increment | 96 passed |
| New run-clock regression tests | 3 committed, NOT EXECUTED |
| Real LangGraph integration harness | 3 committed, NOT EXECUTED |
| Exact package installation in this tool environment | BLOCKED by DNS/network |
| Full transitive hash lock | PENDING |
| GitHub Actions CI | NOT CONFIGURED |
| Cloudflare Worker/Cron/D1 | NOT DEPLOYED |
| LangGraph runtime in cloud | NOT RUNNING |
| Live research agents | 0 |
| Durable state manifest | generation 0, zero objects, no active lease |

## 7. Financial, legal and commercial ledger

- Spend authorized/incurred: ₹0.
- Settled revenue evidence: ₹0.
- Account creation/KYC/legal terms acceptance/OAuth consent/billing/payment method: none.
- Cloud deployment, external submission, buyer/platform outreach, product build or publication: none.
- Five commercial gates remain mandatory; UNKNOWN is never PASS.
- Commercial execution remains HOLD.

## 8. Next exact actions

1. Verify fetch-back blobs for the adapter, regression tests, integration harness and policy.
2. Update the canonical continuity checkpoint with the exact new commit and test status.
3. Resolve S7-A read-only validation workflow sequencing and dependency lock.
4. Run real LangGraph compile/invoke/resume tests on the public GitHub-hosted ephemeral runner.
5. Only after S5 real integration passes, begin S6 read-only evidence workers.
6. Retain S7-B publisher-only write isolation as a later gate; do not deploy Cloudflare before its independent no-billing and owner-approval checks.

## 9. Official package references

- PyPI release: https://pypi.org/project/langgraph/1.2.22/
- StateGraph compile reference: https://reference.langchain.com/python/langgraph/graph/state/StateGraph/compile
- LangGraph checkpointing reference: https://langchain-ai.github.io/langgraph/reference/checkpoints/
