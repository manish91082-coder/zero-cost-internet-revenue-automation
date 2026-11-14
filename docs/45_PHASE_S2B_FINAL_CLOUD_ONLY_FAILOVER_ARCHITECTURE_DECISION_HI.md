# Phase S2-B — Final hosting-free, laptop-independent, failover-first swarm architecture decision (2026-11-14)

## Executive decision

**GREEN for architecture selection and staged implementation design. NOT GREEN for unattended production deployment or revenue execution.**

The user explicitly requires no laptop dependency, ₹0 spend, open-source-first software, cloud execution, 24x7 continuity, and automatic failover when a provider is unavailable, blocked, or quota-exhausted. The design is therefore revised from a single-host assumption to a multi-provider, short-lived-job architecture.

A literal always-on VM/daemon plus unlimited free AI inference cannot be guaranteed at ₹0. No provider offers an unconditional contractual guarantee of unlimited free compute, uptime, inference, or automatic cross-provider migration. The approved engineering target is **24x7 continuity with bounded scheduled/event-driven execution, durable task state, independent scheduler paths, provider health checks, automatic failover, and safe pause/resume**. There may be gaps caused by platform scheduling delays, free-tier policy changes, quotas, account suspension, or provider outages. The system must never evade provider limits, create alternate identities, or shift to paid use.

## 1. Final selected architecture

### Control and execution plane

1. **Canonical control plane: GitHub public repository + GitHub Actions.**
   - Public standard GitHub-hosted runners are documented as free and unlimited for public repositories.
   - Use fresh, ephemeral Linux runners for bounded Python jobs. No laptop or self-hosted runner.
   - GitHub Actions is primary execution substrate, not a permanent daemon.
   - Use workflow_dispatch and repository_dispatch for recovery and external dispatch.
   - Workflow schedule is a convenience trigger only; not the sole scheduler.

2. **Independent scheduler/heartbeat: Cloudflare Workers Free Cron.**
   - Cron calls a small dispatcher/health handler, not the Python agent swarm.
   - The dispatcher checks due tasks and last successful heartbeat, then invokes the GitHub Actions workflow via a narrowly scoped GitHub token.
   - Free Worker limits: 100,000 requests/day, 10 ms CPU/invocation, 128 MB memory, 50 subrequests/request, five Cron Triggers/account (official docs updated Nov 13, 2026).
   - 10 ms CPU means no scraping, parsing, LangGraph execution, model inference or long task loops inside Workers.
   - Store only queue/lease/heartbeat metadata in D1. D1 Free limits: 10 databases/account, 500 MB/database, 5 GB/account, 50 read subqueries per Worker invocation; daily free quotas are 5M rows read and 100k rows written (check live docs before deployment).
   - Cloudflare outage or quota failure must leave the canonical task ledger recoverable in GitHub; no destructive queue mutation.

3. **Durable task and evidence state:**
   - Canonical immutable/versioned artifacts and task snapshots in GitHub.
   - D1 is a fast dispatch/lease mirror only, not the sole source of truth.
   - SQLite is used only in local CI job filesystem for deterministic unit/integration tests; no user laptop required and no claim that runner-local SQLite persists across jobs.
   - Use GitHub commit SHA + task IDs as durable checkpoint references.

4. **Agent orchestration:**
   - Python deterministic state machine and policy engine are authoritative.
   - LangGraph is selected as the preferred OSS orchestration adapter for resumable specialist workflows, interrupts and checkpointed graph execution. It runs inside ephemeral GitHub Actions jobs, not on Cloudflare Worker.
   - LangGraph checkpoint state must be persisted to D1/GitHub-compatible storage or serialized into a validated artifact before the runner exits. Never rely on ephemeral runner disk.
   - If LangGraph dependency/runtime fails, deterministic task runner remains able to continue non-LLM work.
   - Max two parallel research workers initially; one evidence publisher only.

5. **Model inference:**
   - No model provider is designated as always-free or guaranteed.
   - Model gateway uses an allowlist of providers only after current official quota, India eligibility, data policy, commercial use and billing requirements are verified.
   - Provider quota exhausted/unavailable => circuit breaker opens; task tries a different independently verified free provider only if that provider is approved and available. If none, switch to deterministic mode or mark BLOCKED_NO_FREE_MODEL.
   - Never use paid API, trial credits, personal ChatGPT UI as API, unapproved proxy, shared credentials, or account rotation to bypass quotas.
   - Model provider failover cannot bypass rate limits or policy restrictions.

## 2. Failover topology

| Failure | Primary response | Alternate / recovery | Safety behavior |
|---|---|---|---|
| GitHub scheduled trigger delayed/dropped | Cloudflare Cron heartbeat detects stale heartbeat | Cloudflare calls GitHub workflow_dispatch/repository_dispatch | Duplicate-safe idempotency key |
| Cloudflare unavailable/quota exhausted | GitHub scheduled workflow and manual dispatch continue | Resume from GitHub task ledger | No dependency on D1 for source-of-truth |
| GitHub Actions unavailable | Cloudflare retains pending task state and records outage | Retry GitHub dispatch after backoff; manual owner dispatch if prolonged | No alternative host activated unless separately verified |
| D1 unavailable/quota exhausted | Use last verified GitHub task snapshot | Rebuild D1 mirror from GitHub ledger when restored | No task loss, no over-limit retries |
| LangGraph runtime failure | Deterministic Python task runner | Resume node/task from persisted state | Model-free fallback |
| LLM provider A unavailable/quota exhausted | Open provider circuit breaker | Approved free provider B, then C | No paid fallback; no quota evasion |
| All LLM providers unavailable | Deterministic extraction, validation, queue management | Hold only LLM-dependent tasks | No false evidence or guessed claims |
| Research source blocked/changed | Mark source unavailable and preserve prior snapshot | Another official source or destination-specific alternate source | No proxy/VPN/restriction bypass |
| Worker timeout/crash | Lease expires and task returns to retry queue | Resume from last verified checkpoint | Idempotency prevents duplicate publication |
| Repository publisher failure | Keep validated artifact pending | Retry with current SHA / conflict reconciliation | Never report uncommitted data as saved |

**Important:** provider failover means approved independent services, not creating multiple accounts or circumventing a provider's fair-use/rate limits. No failover path may introduce spend.

## 3. Provider selection audit

### APPROVED FOR DESIGN (not deployed)
- **GitHub Actions public standard runners:** best primary execution substrate because the repository is already public and GitHub documents standard public-repository runner usage as free/unlimited. The runner is ephemeral; job duration and platform limits still apply. Scheduled workflows can be delayed/dropped and public repo schedules can be disabled after 60 days of inactivity; therefore not sole scheduler.
- **Cloudflare Workers Free + Cron + D1:** best lightweight independent heartbeat/dispatcher candidate. Free Cron is supported. The 10 ms CPU limit disqualifies it from being the agent runtime. D1 is a queue metadata mirror, not sole durable ledger.
- **LangGraph OSS:** selected orchestration library candidate, not a hosting provider. MIT license. No provider runtime guarantee implied.

### CONDITIONAL / SECONDARY
- **Supabase Free:** optional evidence/query mirror only, not primary scheduler or sole state store. Official docs say free projects can pause after one week of low activity; Edge Functions have 150-second wall time and 2-second CPU time on Free. It introduces another account and service dependency. Not needed in first deployment.
- **Hugging Face Spaces CPU Basic:** not selected as always-on compute. Default CPU Basic sleeps after 48 hours inactivity; paid hardware required to prevent deactivation. Static Spaces are free but cannot host the agent runtime.
- **Render Free Web Services:** rejected for always-on runtime. Free web service sleeps after 15 minutes without inbound traffic, local filesystem is ephemeral, free Postgres expires after 30 days, and workspace free instance hours are limited to 750/month; outbound bandwidth overage may bill.
- **Deno Deploy:** rejected for strategic architecture because official docs state Deno Deploy will be sunset in April 2027, despite a $0 tier. Do not build a long-lived mission dependency on a sunset platform.
- **Google Cloud Free Tier:** excluded under strict zero-billing/no-card-risk policy because a Cloud Billing account is required and usage above free quotas on a paid billing account is billed. Free trial credits are not a sustainable ₹0 resource.
- **Oracle Cloud Always Free:** not selected. Card/identity/account verification and account suspension/availability risk need separate audit; not needed given the public GitHub + Cloudflare design.
- **n8n:** not selected as core runtime. It adds hosting and license/usage questions and does not solve compute or free model inference.
- **Fly.io/paid VMs/Render paid/Modal paid/any trial credit:** excluded from ₹0 baseline.

## 4. Scheduling and 24x7 semantics

The system will not run one infinite loop. It will use bounded invocations:
- Cloudflare Cron heartbeat target every 5–15 minutes (schedule chosen after quota test).
- GitHub scheduled workflow as secondary periodic trigger, with stale-run recovery.
- GitHub dispatch on demand for queued task batches.
- Each run leases at most a bounded batch, max two concurrent research workers, and hard time/request/output limits.
- Heartbeat records last successful dispatch, last worker completion, queue age, quota state and provider health.
- Missing heartbeat triggers a recovery dispatch, not an assumption of liveness.
- Backoff and jitter avoid request storms; circuit breakers stop repeated failing providers.
- Dead-letter queue preserves exhausted tasks and reason.
- One daily full continuity reconciliation validates canonical GitHub HEAD, state artifacts, task progress, and five-gate ledger.

This provides operational continuity, not a contractual 100% uptime SLA or exact execution every five minutes.

## 5. Security, identity, billing and approval

- No personal laptop or local machine is part of runtime, scheduling or recovery.
- No self-hosted runner.
- GitHub token: minimum required permissions; stored only as encrypted repository secret; workflow permissions read-only by default; write permissions only for publisher job.
- Cloudflare secret: only the minimum GitHub dispatch credential; never print it or commit it.
- Separate read-only workers from publisher.
- No arbitrary PR workflow from forks can access secrets.
- Protect main branch and validate all artifacts before publisher.
- Spend guard: never add payment method or enable paid plan/overage. If a platform requires payment method for activation, mark that provider NOT ELIGIBLE until explicit owner decision; no automatic fallback to paid tier.
- Account creation, KYC, legal terms acceptance, outreach, submissions, build/list/publish, wallet signing and external commitments remain owner approval-gated.
- Public web content is untrusted evidence, not agent instructions.
- Kill switch blocks dispatch, workers and publishing.
- Data minimization: no personal/customer/identity data in public repository.

## 6. Agentic swarm structure

The S1 nine-role roster remains valid. The roles are logical work assignments, not nine always-running model instances:
1. Mission Controller: deterministic.
2. Opportunity Discovery.
3. Official Source Research A.
4. Independent Official Source Research B.
5. India Eligibility/Payout.
6. IP/Licensing/Data Rights.
7. Unit Economics/Workload.
8. Adversarial Auditor.
9. Evidence Publisher (single writer).

A task can pass through specialist nodes in LangGraph. No agent can alter mission priority, release gates, provider allowlist, spend cap or its own permissions. At most two research workers parallel until acceptance tests and quota data support expansion.

## 7. Final deployment phases

| Phase | Deliverable | Exit gate |
|---|---|---|
| S1 | Roster + constitution | COMPLETE |
| S2 | This cloud-only failover architecture and provider decision | COMPLETE as design |
| S3 | Versioned task/evidence/source/run/approval/quota schemas | Not started |
| S4 | Deterministic Python controller, policy engine, queue, leases, retries, circuit breakers | Offline CI tests pass |
| S5 | LangGraph adapter and durable checkpoint persistence | Crash/resume, interrupt/resume, idempotency tests pass |
| S6 | Read-only evidence workers and source adapters | Prompt-injection, provenance, conflict tests pass |
| S7 | Single-writer publisher + CI validation + secret scan | Fetch-back and duplicate-commit tests pass |
| S8 | Cloudflare heartbeat/dispatcher + D1 mirror + GitHub dispatch | No-cost billing/quota, missed-run and provider-outage tests pass |
| S9 | Limited 7-day read-only unattended pilot | Zero spend, no policy breach, recovery evidence, quality threshold |
| S10 | Expand by source-locked priority order | P1 first, P2 alongside, P3 after P1, P4 later |

No production green light until S3-S9 exit gates are independently verified. No commercial green light until all five commercial gates pass.

## 8. Current dashboard / actual status

- Canonical repository checkpoint was fetched and verified before this decision.
- Architecture report v1 was fetched back; its limitations are superseded by this v2 decision record.
- Existing ChatGPT task automation "Advance Zero-Cost Revenue Mission" is enabled, scheduled daily 08:30 Asia/Kolkata, but dashboard reports no recorded run yet. This automation is a ChatGPT task, not the swarm runtime and not proof of cloud execution.
- No GitHub Actions swarm workflow exists in the checked checkpoint.
- No Cloudflare Worker/Cron/D1 deployment exists.
- No LangGraph runtime is implemented.
- No agent process is running.
- No model provider is wired into the swarm.
- No tests have yet validated cloud failover.
- No laptop is required or permitted as an execution dependency.
- No platform account creation, billing setup, KYC, terms acceptance or external deployment was performed in this phase.

## 9. Final status decision

**GREEN:** architecture direction is selected for implementation planning: GitHub Actions public runners + Cloudflare Cron/D1 lightweight independent dispatcher + deterministic Python control plane + LangGraph adapter + provider-agnostic free model gateway + GitHub as canonical audit ledger.

**AMBER:** free cloud services have quotas and can change terms; the exact no-card/no-billing account eligibility must be confirmed before deployment. Failover can provide resilience, not infinite capacity.

**RED / NOT APPROVED:** claim of guaranteed 24x7 always-on compute, unlimited free LLM inference, fully autonomous commercial execution, or production readiness. None is supported by evidence today.

## 10. Sources (official primary documentation)

- GitHub Actions standard public runners and workflow syntax: https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax
- GitHub Actions billing: https://docs.github.com/en/actions/concepts/billing-and-usage
- Cloudflare Workers Free limits (last updated Nov 13, 2026): https://developers.cloudflare.com/workers/platform/limits/
- Cloudflare Cron Triggers (last updated Nov 12, 2026): https://developers.cloudflare.com/workers/configuration/cron-triggers/
- Cloudflare D1 limits: https://developers.cloudflare.com/d1/platform/limits/
- Supabase Free pausing: https://supabase.com/docs/guides/platform/free-project-pausing
- Supabase Edge Function limits: https://supabase.com/docs/guides/functions/limits
- Hugging Face Spaces sleep: https://huggingface.co/docs/hub/spaces-gpus
- Render Free services: https://render.com/docs/free
- Deno Deploy sunset: https://docs.deno.com/deploy/usage/
- Google Cloud billing account requirement: https://docs.cloud.google.com/free/docs/free-cloud-features
- LangGraph OSS overview: https://docs.langchain.com/oss/python/langgraph/overview
- LangGraph MIT license: https://github.com/langchain-ai/langgraph/blob/main/LICENSE

## 11. Mission ledger

Project ID `ZCIRA-2026-11-13`; canonical repo unchanged; spend authorized/incurred ₹0; settled revenue evidence ₹0; no account creation/KYC/terms acceptance/deployment/worker execution/tests/outreach/submission/build/publication; commercial execution HOLD. No laptop dependency.
