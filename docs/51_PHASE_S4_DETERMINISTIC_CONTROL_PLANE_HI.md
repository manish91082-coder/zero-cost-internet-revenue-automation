# Phase S4 - deterministic Python control plane core (2026-11-15)

## Executive result

**S4 CORE IMPLEMENTED / UNIT TESTS PASS / CLOUD RUNTIME NOT DEPLOYED.**

A pure Python control plane has been added to the canonical repository. It has no external API calls, model dependency, database dependency or paid package dependency. It computes decisions and plans only. It does not execute tasks, contact providers, publish products, alter accounts or deploy infrastructure.

## Published implementation

| File | Responsibility |
|---|---|
| `src/zcira_control/policy.py` | Mission identity, repository/branch lock, fixed priority, Category #24=B, action allowlist, path allowlist, five-gate and exact-approval evaluation |
| `src/zcira_control/queue.py` | Deterministic read-only research planning, max two tasks, idempotency de-duplication and separate single-publisher selection |
| `src/zcira_control/leases.py` | Mission-bound lease validation, expiry, one writer, resource-key lock and idempotent lease collision check |
| `src/zcira_control/quota.py` | Free-tier eligibility, billing/payment/trial/paid-route denial and provider circuit breaker |
| `src/zcira_control/checkpoints.py` | Git SHA validation and compare-and-swap rejection of stale branch checkpoints |
| `scripts/zcira_control.py` | Offline CLI with `validate-task` and `plan`; explicitly reports `execution_performed=false` |
| `tests/test_control_plane.py` | Standard-library unit tests |

## Deterministic policy implemented

1. Only project `ZCIRA-2026-11-13`, repository `manish91082-coder/zero-cost-internet-revenue-automation`, branch `main` and the fixed mission namespaces are accepted.
2. Priority order remains P1, P2, P3, P4, P5, B, M. Category #24 is hard-locked to B.
3. Spend cap remains ₹0. Paid provider routes and trial-credit dependency are rejected.
4. The mission registry must be active and its allowed/denied action and path lists must be complete.
5. Research planning returns at most two queued read-only tasks, sorted by priority, UTC creation time and task ID. Duplicate idempotency keys are selected once.
6. Publisher tasks are excluded from the research batch. A separate publisher selector returns at most one task and only when no active same-mission writer lease exists.
7. Repository writes require the `evidence_publisher` role and a path inside the mission allowlist. Workflow, secrets and private paths remain denied.
8. Only the evidence publisher can hold `repo-main-single-writer`. Active lease conflicts, expiry, mission/repository/namespace mismatch and lease-ID content collisions are rejected.
9. A provider is eligible only when its free tier is verified, billing and payment method are not required, trial credits are not required, paid fallback is false, and the circuit is CLOSED. HALF_OPEN is probe-only, not normal work. Three consecutive failures open the circuit.
10. A stale base SHA is rejected by compare-and-swap. The engine never silently overwrites a newer checkpoint.
11. Commercial release requires all five gates PASS plus an exact, unexpired owner-approval record matching mission, action, target, zero-cost status and scope. UNKNOWN/HOLD never passes. The decision function explicitly reports `external_action_performed=false`.

## Tests and dry-run

Executed in an isolated tool container, not on the user's laptop:

- Standard-library unit tests: **27/27 passed**.
- CLI synthetic plan: returned two tasks in P1 then P2 order, with `execution_performed=false`.
- Negative checks covered mission mismatch, Category #24 priority drift, external action, paid route, path traversal, denied workflow path, wrong writer role, two-worker overflow, duplicate idempotency, UNKNOWN gate, missing/expired/wrong-target approval, single-writer collision, expired lease, stale checkpoint, unverified/billing/trial/paid provider, HALF_OPEN/OPEN circuit behavior.

The tests were run against the local implementation source used to prepare the committed code. The repository files were fetched back after each commit. This is not a GitHub Actions run and does not prove cloud execution.

## Current limits

- The control plane is a deterministic library and offline CLI, not a running service.
- Task queue persistence, lease persistence, GitHub artifact checkpoint I/O, GitHub branch-head API compare-and-swap, retry scheduler and durable dead-letter queue are not implemented yet.
- No LangGraph adapter, source workers, publisher workflow, GitHub Actions workflow, Cloudflare Worker/Cron/D1 or automatic failover deployment exists.
- No OAuth login, Google consent request, account creation, KYC, terms acceptance, billing setup or cloud deployment occurred.
- No model inference was used. The deterministic core remains operational without any model provider.

## Phase status and next step

- S4 deterministic policy, queue planner, lease and quota logic: CORE COMPLETE.
- S4 durable checkpoint and persistence adapter: PENDING.
- S4 GitHub API compare-and-swap integration: PENDING.
- S5 LangGraph adapter: NOT STARTED.
- S6 read-only evidence workers: NOT STARTED.
- S7 single-writer publisher and CI: NOT STARTED.
- S8 Cloudflare heartbeat/dispatch and failover tests: NOT STARTED.
- S9 unattended read-only pilot: NOT STARTED.

Next: S4-B durable state bundle and checkpoint adapter with strict mission namespace, canonical JSON hashing, idempotent resume and branch-head compare-and-swap interface. Keep all network writes outside the pure core and behind the single publisher. No deployment before zero-billing eligibility and explicit approval.
