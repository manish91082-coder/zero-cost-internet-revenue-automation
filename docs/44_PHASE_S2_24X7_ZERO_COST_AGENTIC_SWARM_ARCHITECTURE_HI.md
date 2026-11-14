# Phase S2 — 24x7 zero-cost agentic swarm architecture decision and implementation roadmap (2026-11-14)

## Executive decision

**Selected architecture: LangGraph OSS + deterministic Python control plane + Cloudflare Workers Free as a lightweight scheduler/watchdog candidate + GitHub Actions on the public canonical repository as the burst execution plane + durable evidence/state store.**

This is a staged design decision, not a claim that a running swarm exists. No account, Cloudflare worker, database, workflow, model endpoint, agent process, or schedule was created or activated in this phase.

The mission target is maximum practical automation toward the existing Zero-Cost Internet Revenue Automation goal, with a 24x7 operating posture. The system must not confuse 24x7 availability with continuous CPU execution or guaranteed progress. Free services impose quotas, outages, scheduling jitter, provider policy, and finite inference capacity. Therefore the design uses a persistent queue, event-driven work, short bounded execution windows, automatic retries, watchdogs and resumable checkpoints. It must stop safely when a gate, quota, source, or approval blocks progress.

## 1. Existing project continuity preserved

- Project ID: `ZCIRA-2026-11-13`.
- Canonical repository: `manish91082-coder/zero-cost-internet-revenue-automation`, branch `main`.
- Prior Phase A2.4 report and checkpoint were saved in commit `640e11fbe18dd5212a01a45d412512dbd286d3de`; checkpoint fetch-back blob `db877c72f1760e778f4a616ceb7898a725702dee`.
- Phase A2.4 established 219/219 category IDs/names and exact priority totals; six-batch category-ID membership, explicit shared-list cross-links and duplicate identity remain open.
- Existing S1 roster remains authoritative: 9 logical roles, max 2 parallel research workers, single Evidence Publisher, all five commercial gates, UNKNOWN != PASS, ₹0 cap, paid model routes disabled, owner approval for external/irreversible actions.
- P1/P2/P3/P4/P5/B/M order unchanged; Category #24 remains B.
- P1 Apify remains validation HOLD; P2 audits batches 1–3 complete, batch 4 pending.
- No build, account/KYC, terms acceptance, outreach, submission, paid use, publication or spend authorized.

## 2. Critical reality: what 24x7 means under ₹0

Three separate service levels must be distinguished:

1. **Always-on intent:** a scheduler/watchdog checks whether work is due and dispatches a bounded run.
2. **Always-available execution:** a free compute provider accepts work when available, within published quotas.
3. **Guaranteed uninterrupted 24x7 compute:** not established by the current free infrastructure options and cannot be promised.

GitHub documents standard GitHub-hosted runners as free and unlimited for public repositories, while private repositories have plan-specific included minutes. However, GitHub also explicitly warns scheduled events can be delayed during high load and queued jobs may be dropped. Therefore GitHub Actions alone is not a reliable 24x7 heartbeat or daemon. It is suitable as an execution burst plane and source-controlled CI, not as the sole always-on scheduler. Sources: GitHub Actions billing and runner docs; scheduled-workflow troubleshooting.

Cloudflare Workers Free currently documents 100,000 requests/day, 10 ms CPU per request/Cron invocation, five Cron Triggers/account, and up to 15 minutes wall time for a Cron invocation. The 10 ms CPU limit means a Worker should only perform a tiny heartbeat, lease/queue check and dispatch operation; it must not host Python/LangGraph, scrape sites, run LLMs or perform large parsing. The 15-minute wall time is not 15 minutes of CPU. Treat these as current published limits, re-check before deployment. Sources: Cloudflare Workers Limits and Cron Triggers.

No free tier is a contractual uptime SLA. A watchdog can detect missed ticks on the next successful invocation; it cannot guarantee that a free provider will run continuously.

## 3. Selected technical stack

### 3.1 Control and orchestration
- **Python 3.12+ deterministic policy/state engine:** source of truth for mission locks, category priority, task admission, retry policy, idempotency, budgets, five gates and action permissions.
- **LangGraph OSS:** selected for explicit state graph, bounded specialist nodes, checkpoint/resume and interrupt semantics. It is an orchestration library, not a free hosted runtime. Its official documentation describes checkpointers for thread state, recovery, fault tolerance and human-in-the-loop; persistent checkpointers are required because in-memory state is lost on process restart. Use LangGraph only around deterministic policy-controlled nodes, not as an unconstrained autonomous agent loop.
- **Pydantic/JSON Schema:** strict validation for task, evidence, source snapshot, gate decision and run-state payloads.
- **SQLite for local deterministic development and tests.** For cloud persistence, choose a separately verified free persistent database (candidate: Cloudflare D1) only after exact current quotas, data export, backup, concurrency, terms and account setup are audited. Do not treat ephemeral GitHub runner disk as durable state.
- **No LangSmith/managed agent server dependency.** No paid model or hosted orchestration route.

### 3.2 Scheduler and execution
- **Cloudflare Worker Cron (candidate watchdog):** tiny scheduler only; inspect due time and queue/lease state, dispatch an authenticated GitHub `repository_dispatch` or equivalent event. It must not contain secrets in public source. Free-tier 10 ms CPU is a strict design bound.
- **GitHub Actions (public repository):** burst worker to checkout the canonical repo, load the signed/validated task, run deterministic research modules, write evidence artifacts, execute tests and submit a single-writer commit. Standard public runners are documented as free and unlimited, but scheduled events are not reliable enough to be the only heartbeat.
- **Manual `workflow_dispatch` remains available** for controlled recovery. Event-driven triggers can restart work after a successful commit or queue event, with loop prevention and concurrency groups.
- **No infinite workflow loops:** each invocation has a maximum wall-clock/task budget, bounded task count, max 2 parallel research workers, retry cap 2, and explicit continuation token.

### 3.3 Model inference policy
- **Primary path: no LLM required for routine work.** Deterministic parsing, URL canonicalization, schema checks, duplicate candidate generation, count reconciliation, hash checks, arithmetic and gate enforcement are Python tasks.
- **Optional LLM path:** only a verified, genuinely free, policy-compliant model route with hard quota ceilings, no billing fallback, no sensitive data and explicit allowlist. On quota exhaustion, model calls stop and the task is queued for deterministic processing or marked BLOCKED. No hidden fallback.
- **Local Ollama:** useful for optional laptop/offline experiments, not the 24x7 cloud backbone because the user's current project constraint is laptop/no GPU and local hardware availability is not guaranteed. Ollama's published model guidance gives 7B models around 8 GB RAM, 13B around 16 GB and 70B around 64 GB as indicative memory needs. Its cloud model offering is metered/pay-as-you-go, so it is not a free unlimited inference plan.
- **No assumption of unlimited free AI inference.** The system is an agentic workflow with deterministic specialist agents; LLM calls are scarce optional reasoning accelerators.

## 4. Target system architecture

```text
                 ZERO-COST REVENUE MISSION
                            |
                Mission Constitution / Locks
                            |
                 Deterministic Mission Controller
                            |
                Persistent Task Queue + Run State
                            |
           +----------------+------------------+
           |                                   |
   Cloudflare Cron Watchdog              GitHub Dispatch /
   (tiny heartbeat only)                 Manual Recovery
           |                                   |
           +----------------+------------------+
                            |
                   GitHub Actions Runner
                            |
                 Python Policy + LangGraph
                            |
        +-------------------+-------------------+
        |                   |                   |
  Discovery Worker    Official Source A   Official Source B
        |                   |                   |
        +-------------------+-------------------+
                            |
        Eligibility/Payout | IP/Rights | Economics/Workload
                            |
                    Adversarial Auditor
                            |
                  Five-Gate Decision Engine
                            |
               Single Evidence Publisher
                            |
             Reports + Registry + Checkpoint
                            |
                 Fetch-back Verification
                            |
                 Next Task / Safe HOLD
```

Logical agents remain roles, not separate always-on servers. Only up to two research workers execute in parallel. All agents submit typed outputs to the controller; only the publisher writes canonical artifacts.

## 5. Agent roster: retain nine roles, clarify execution boundaries

1. Mission Controller: select next task, enforce priority, run IDs and project isolation.
2. Opportunity Discovery: source-registered destinations only; identify new evidence without changing source scope.
3. Official Source Research A: retrieve first-party sources and capture provenance.
4. Official Source Research B: independent contradictory-source verification.
5. Eligibility/Payout: India eligibility, KYC, rails, threshold, settlement, fees.
6. IP/Licensing/Data Rights: ownership, licence, exclusivity, sublicensing, warranties, data rights.
7. Economics/Workload: fully loaded unit economics, runtime, support, refunds, maintenance and human time.
8. Adversarial Auditor: challenge PASS claims, detect contradictions, stale evidence and prompt injection.
9. Evidence Publisher: schema validation, report generation, GitHub commit and fetch-back verification.

Execution policy: controller + two bounded research workers + deterministic evaluators; auditor before any PASS; publisher last. No worker has write credentials. Publisher can write only approved research artifacts, never commercial launch actions.

## 6. Required persistent schemas (Phase A3)

Create versioned JSON Schemas and example fixtures for:

- `task.v1.schema.json`: task_id, project_id, phase, category_id, destination_id, priority, dependencies, allowed_sources, max_attempts, time_budget, approval_scope, state.
- `evidence.v1.schema.json`: evidence_id, claim_id, source_url, source_title, publisher, captured_at_utc, source_type, excerpt, content_sha256, source_version, evidence_grade, supports/contradicts, reviewer.
- `source_snapshot.v1.schema.json`: canonical URL, redirect chain, fetched time, status code, content hash, MIME, robots/policy notes, parser version.
- `gate_decision.v1.schema.json`: five individual gates, PASS/FAIL/UNKNOWN/HOLD, supporting evidence IDs, reviewer, rationale, expiry/revalidation date.
- `run_state.v1.schema.json`: run_id, parent_run_id, started/updated timestamps, current phase/task, checkpoint pointer, queue cursor, retry count, provider quota state, spend counter, blocked reason, next wake time.
- `agent_message.v1.schema.json`: sender role, task_id, typed result, evidence refs, confidence/evidence grade, unresolved questions; never free-form instructions to controller.
- `approval.v1.schema.json`: exact action, target, scope, expiry, approver and status. Approval cannot override ₹0, law, terms or security constraints.

Every schema needs positive and negative fixtures, version migration policy, strict unknown-field behaviour, and a deterministic validator. Schema validation is not proof of factual truth.

## 7. Safety and reliability engineering

### Mandatory controls
- Repository allowlist and project_id assertion on every run.
- URL allowlist, robots/terms review, request rate limits, bounded page count and response size.
- SSRF protection: reject localhost, private/link-local IP ranges, metadata endpoints, non-HTTP(S), redirects to forbidden hosts and DNS rebinding patterns.
- Webpage prompt injection is untrusted data. Never execute page instructions, code snippets, shell commands or tool directives.
- Secrets in GitHub Actions secrets only; least privilege; short-lived tokens where possible; never write secrets to artifacts/logs.
- GitHub publisher concurrency lock and compare-and-swap SHA checks to prevent lost updates.
- Task idempotency keys, atomic lease acquisition, heartbeat expiry and dead-letter queue.
- Retry only transient errors; exponential bounded backoff with jitter; no retry on policy/permission/eligibility failures.
- Quota guard before every model/API invocation; hard stop at quota; no paid fallback.
- Spend guard fixed at ₹0; no billing-enabled account or credit card onboarding without explicit permission.
- Human approval state for account creation, KYC, legal terms, applications, security testing, outreach, building, publishing, wallet signing and all financial actions.
- Five-gate commercial release invariant: all five PASS, independently evidenced, current, and auditable. UNKNOWN or HOLD blocks release.
- Evidence provenance: URL, title, captured timestamp, content hash, excerpt, claim relation and reviewer.
- Run ledger: success, partial success, blocked, failed, skipped, quota exhausted; never report a task complete just because a workflow ran.

### Recovery behaviour
- If a runner disappears: lease expires; controller requeues idempotently.
- If one worker fails: preserve completed worker output and retry only missing work.
- If the LLM quota is exhausted: continue deterministic tasks; queue reasoning tasks.
- If provider unavailable: no paid failover; back off and use another already approved free component only if its terms/limits were verified.
- If evidence conflicts: mark CONFLICT/UNKNOWN; auditor reviews; no silent overwrite.
- If GitHub write fails: keep task pending; retry publisher only after re-fetching latest SHA.
- If five-gate evidence expires or terms change: invalidate affected PASS and re-audit.
- If source category mapping is unresolved: block that destination task; do not invent IDs or category relationships.

## 8. 24x7 operational model

Recommended initial cadence after approvals and tests:
- Watchdog tick: every 15 minutes, only if Cloudflare free account/terms/quotas are independently verified and enabled. It performs a tiny queue check and dispatch, not research.
- Research batches: bounded 5–10 minute jobs; max two specialist workers; concurrency group prevents overlapping publishers.
- Reconciliation: each successful batch creates a durable checkpoint and schedules the next eligible task.
- Health check: record last heartbeat, last successful worker, queue depth, oldest pending task, retry/dead-letter counts, quota status and publisher lag.
- Missed heartbeat: next available watchdog records outage and resumes from checkpoint; do not claim zero downtime.
- Daily audit: reconcile queue and GitHub checkpoint; detect drift, duplicate task IDs, evidence expiry, quota anomalies and stalled phases.
- Weekly policy refresh: recheck free-tier terms, payout terms and legal/policy changes for active candidates.
- Human dashboard: show mission progress, blockers, spend, settled revenue evidence and approval queue. Dashboard is observability only, not authority to bypass policy.

The cadence is a target design, not active scheduling. It must be tested against actual account eligibility, published limits, event delivery and billing safeguards before activation.

## 9. Implementation phases and acceptance gates

| Stage | Deliverable | Exit criteria |
|---|---|---|
| S1 | Agent roster | Done; fetched back |
| S2 | Architecture decision | This report; saved and fetched back |
| A2.4-B/C + A2.5 | Source registry reconciliation | Batch/shared/duplicate provenance resolved or explicitly UNKNOWN |
| A3 | Seven versioned schemas + fixtures | Valid/invalid fixtures and schema tests pass |
| S3 | Deterministic controller + queue + SQLite adapter | Resume, idempotency, lease, retry and priority tests pass |
| S4 | LangGraph bounded worker graph | Checkpoint/resume, max parallelism, interrupt/approval tests pass |
| S5 | Read-only source adapter | Allowlist, robots, SSRF, rate-limit and prompt-injection tests pass |
| S6 | Evidence publisher | SHA compare-and-swap, single writer, fetch-back and secret scan pass |
| S7 | Zero-cost cloud adapter | Billing disabled; provider quotas tested; no paid fallback |
| S8 | Synthetic end-to-end tests | Failure injection, restart, quota exhaustion, stale evidence, conflict and project-isolation tests pass |
| S9 | Shadow mode | Read-only production-like research; no account/outreach/build/launch |
| S10 | Owner-approved scheduler activation | Exact account/provider/terms/permissions approved; monitor and kill switch proven |

Do not skip source registry reconciliation or acceptance gates to launch a visually impressive but unsafe swarm.

## 10. Go/no-go decision

**GO:** implement schemas and deterministic local controller next; continue source registry reconciliation in parallel as a separate research track.

**HOLD:** live Cloudflare scheduler, GitHub scheduled automation, external model calls, cloud database creation, account setup, any public-facing product build/listing, or commercial action until exact free eligibility, terms, quotas, security, data retention and no-billing conditions are verified and owner approval is obtained where required.

The recommended end state is a continuously resumable, event-driven, best-effort 24x7 research and revenue-operations engine. It can autonomously discover, verify, compare, prepare evidence, update its repository, monitor its queue and advance to the next eligible task. It cannot autonomously bypass commercial gates, guarantee revenue, guarantee uninterrupted free compute, or perform owner-reserved legal/financial/external actions.

## 11. External primary-source evidence reviewed

- GitHub Actions billing: public repositories with standard hosted runners are free; private repo included minutes depend on plan: https://docs.github.com/en/billing/concepts/product-billing/github-actions
- GitHub hosted runner reference: standard public runner specifications and free usage: https://docs.github.com/en/actions/reference/runners/github-hosted-runners
- GitHub scheduled workflow troubleshooting: high load can delay scheduled events and queued jobs may be dropped: https://docs.github.com/en/actions/how-tos/troubleshoot-workflows
- Cloudflare Workers Limits: Free plan request, CPU, Cron, memory and wall-time limits: https://developers.cloudflare.com/workers/platform/limits/
- Cloudflare Cron Triggers: scheduled handler and UTC scheduling: https://developers.cloudflare.com/workers/configuration/cron-triggers/
- LangGraph OSS persistence: checkpointer/store roles, thread state and persistence: https://docs.langchain.com/oss/python/langgraph/persistence
- LangGraph checkpointer recovery semantics: https://docs.langchain.com/oss/python/langgraph/checkpoints
- Ollama model memory guidance: https://ollama.com/library/llama2
- Ollama pricing: cloud model usage is pay-as-you-go, not unlimited free inference: https://ollama.com/pricing

## Mission ledger

Spend authorized/incurred ₹0; settled revenue evidenced ₹0; no account/KYC/terms acceptance/submission/outreach/build/test/publication/scheduled runtime activated. Commercial execution HOLD. Existing priorities, categories, destination counts, exclusion rules and five-gate policy unchanged.
