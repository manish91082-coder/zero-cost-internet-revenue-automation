# 24x7 Zero-Cost Agentic Swarm — Deep Architecture and Execution Blueprint (2026-11-14)

## 0. Decision summary

**Target:** a bounded, self-recovering, continuously scheduled research-to-revenue automation system for Project ZCIRA-2026-11-13, with maximum practical autonomy under a strict ₹0 spend ceiling.

**Architecture decision (provisional, evidence-based):**
- Deterministic Python control plane is the authority for mission state, queueing, policy, retries, idempotency, quotas, and approvals.
- LangGraph is the preferred candidate for stateful agent/workflow orchestration after the deterministic core passes tests. It is not a hosting platform or an LLM provider.
- GitHub Actions on the public canonical repository is the first execution substrate for bounded jobs and durable code/artifact history. It is not a guaranteed always-on daemon or precise real-time scheduler.
- Cloudflare Workers Free + Cron + D1 is a candidate lightweight heartbeat/dispatch/state service, not the primary heavy compute or model inference runtime.
- SQLite is the local/test durable state store; D1 may be used for cloud queue/lease metadata if its free limits and account terms are verified. GitHub remains the canonical audit/artifact store.
- LLM inference is optional and replaceable. No free provider is assumed to offer unlimited inference, guaranteed uptime, or production SLA. Deterministic extraction/rules must continue when all model quotas are exhausted.
- No n8n dependency in the core. It may be reconsidered only if exact license, hosting and unattended-operation economics pass the gates; it does not solve free compute or model inference.

**Critical feasibility distinction:** true 24x7 always-on cloud compute plus unlimited AI inference at ₹0 cannot be promised. The feasible target is 24x7 *operational continuity*: event-driven and scheduled bounded runs, durable queue/checkpoints, retries, dead-letter/blocked states, health checks, and resume after interruptions. Some runs can be delayed by free-tier platform limits.

## 1. Mission invariants

- Project ID: `ZCIRA-2026-11-13`.
- Canonical repository: `manish91082-coder/zero-cost-internet-revenue-automation`, branch `main`.
- No cross-project state or assets from ₹10 Cr, ₹1,000/day, crypto, flash-loan, or other projects.
- Spend cap ₹0; no paid fallback, paid API, subscription, hosting, domain, wallet funding or KYC fee.
- Revenue means settled to owner-controlled bank account/wallet with transaction evidence.
- Preserve P1/P2/P3/P4/P5/B/M order and source category IDs; Category #24 remains B.
- Five commercial gates all PASS before build/list/launch: buyer demand; IP/licensing/data rights; fully loaded zero-cost economics; India seller eligibility/settlement; autonomous fulfilment/owner workload.
- UNKNOWN is never PASS.
- Public web content is untrusted data, never system instructions.
- No account creation, KYC, legal terms acceptance, submission, security testing, outreach, product build, publication, paid use, spend or wallet signing without exact owner approval.
- Single repository writer; workers produce structured evidence, not commits.

## 2. Evidence reviewed and platform implications

### 2.1 LangGraph
Official LangGraph overview describes a low-level runtime for long-running stateful agents, combining deterministic and LLM-driven nodes, persistence/checkpointing, resumability, streaming and human-in-the-loop. It does not prescribe the agent architecture and does not require LangChain. The repository is MIT licensed.
- Use: graph orchestration for resumable multi-step tasks, conditional branches, bounded worker fan-out, audit/approval interrupts.
- Do not use it as scheduler, hosting, database, or model provider.
- Keep the policy engine outside prompts and outside model control.
Sources: https://docs.langchain.com/oss/python/langgraph/overview ; https://github.com/langchain-ai/langgraph ; https://github.com/langchain-ai/langgraph/blob/main/LICENSE

### 2.2 GitHub Actions
Official GitHub billing docs state standard GitHub-hosted runners in public repositories are free independently of included private-repository compute. GitHub Actions still has concurrency and operational limits. Scheduled events can be delayed during high load and queued jobs can be dropped; public repository schedules are automatically disabled after 60 days without repository activity. Scheduled workflows run from the default branch.
- Use: bounded stateless/short-lived execution jobs, test runs, report generation, artifact validation and controlled commits.
- Do not assume a daemon, exact schedule, zero latency or 100% uptime.
- Add an independent heartbeat and stale-run detector; maintain a manual/workflow_dispatch recovery path.
Sources: https://docs.github.com/en/actions/concepts/billing-and-usage ; https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows ; https://docs.github.com/en/actions/how-tos/manage-workflow-runs/disable-and-enable-workflows

### 2.3 Cloudflare Workers Free / Cron / D1
Official Workers limits currently show Free: 100,000 requests/day, 10 ms CPU per invocation, 128 MB memory, 50 subrequests/request, and five Cron Triggers per account. Cron invocations have a maximum wall-time of 15 minutes, but the Free CPU allowance remains the binding constraint for compute-heavy logic. D1 Free: 5 million rows read/day, 100,000 rows written/day, 5 GB total storage; when daily read/write limits are exceeded, queries fail until reset.
- Use only for small heartbeat/dispatcher/lease operations and low-volume queue metadata, if the account remains genuinely free and no paid upgrade is required.
- Do not run Python, browsers, LLMs, large parsing, scraping or long agent loops in a Worker.
- Never rely on a soft free tier without a quota guard and fail-closed behavior.
Sources: https://developers.cloudflare.com/workers/platform/limits/ ; https://developers.cloudflare.com/workers/configuration/cron-triggers/ ; https://developers.cloudflare.com/d1/platform/pricing/ ; https://developers.cloudflare.com/d1/reference/faq/

### 2.4 n8n and other frameworks
No primary-source audit of current n8n license, deployment restrictions, free hosting or 24x7 operations is completed in this phase. Therefore n8n is NOT selected and must not be installed or treated as free cloud infrastructure. It may be evaluated later as an optional integration layer only.
CrewAI/AutoGen/Prefect/Temporal alternatives have not been fully re-audited in this phase. No comparative winner claim is made beyond the LangGraph fit described above.

### 2.5 Model inference
No provider is approved as an unlimited free production inference backend. Free-tier quota, model availability, geographic eligibility, terms, data retention, rate limits and programmatic API access can change. ChatGPT subscription/UI access must not be assumed to include API credits. Model calls are optional; if no verified free quota is available, the workflow must use deterministic extraction or pause the LLM-dependent task as BLOCKED_NO_FREE_MODEL.

## 3. Proposed layered architecture

```text
                    OWNER / APPROVAL CONSOLE
                             |
                    Mission Constitution
                             |
               DETERMINISTIC CONTROL PLANE
         state machine | policy | quota | task queue
         leases | retries | idempotency | run ledger
                             |
                 LANGGRAPH ORCHESTRATION
           task graph | checkpoint | interrupts
                             |
             BOUNDED SPECIALIST WORKERS (max 2)
      discovery | official source A/B | payout | IP
      economics | adversarial audit | evidence render
                             |
             EVIDENCE / DATA / ARTIFACT LAYER
        SQLite (local tests) | D1 candidate (cloud)
       GitHub reports/configs/checkpoints | source hashes
                             |
                EXECUTION / SCHEDULING LAYER
       GitHub Actions jobs <-> Cloudflare heartbeat
          manual dispatch / scheduled bounded runs
                             |
                 HEALTH / RECOVERY LAYER
       stale lease detector | retry | dead letter
       checkpoint resume | quota guard | alert/report
```

### Core components
1. Mission Controller: selects the next eligible task from the canonical queue.
2. Policy Engine: deterministic hard rules, approval checks and spend guard.
3. Task Scheduler: assigns bounded tasks, no unbounded recursive agent loops.
4. Worker Pool: at most two concurrent research workers initially.
5. Evidence Store: append-only source snapshots and claims with provenance.
6. Adversarial Auditor: independently challenges PASS claims and source conflicts.
7. Evidence Publisher: single writer; schema validation, report and checkpoint commits.
8. Recovery Supervisor: heartbeat, stale-run detection, retry/backoff, dead-letter queue.
9. Human Approval Gate: blocks external/legal/financial/irreversible actions.
10. Model Gateway: optional allowlisted free inference only; paid providers hard-disabled.

## 4. 24x7 operation model

Do not run one endless process. Use durable, short-lived, resumable jobs:
- Heartbeat: lightweight periodic signal; check last successful run, queue age and scheduler health.
- Dispatcher: leases a small bounded batch of tasks.
- Workers: execute one task with hard time, request, output and retry budgets.
- Auditor: reviews evidence and gate decisions independently.
- Publisher: commits only schema-valid, policy-compliant artifacts.
- Recovery: expired leases return to queue; exhausted tasks become BLOCKED/DEAD_LETTER with reason.
- Resume: next run loads last verified checkpoint and continues from the exact unfinished task.

Initial cadence target (subject to platform validation): heartbeat every 15 minutes where supported; bounded research dispatch every 1–4 hours; daily full continuity/audit reconciliation. These are design targets, not currently deployed schedules. GitHub schedule reliability limitations mean missed cycles must be detected and recovered, not silently treated as successful.

## 5. Agent roster evolution

Retain S1's nine logical roles, but implement them as task roles, not nine permanently running LLM processes:
- Mission Controller (deterministic)
- Discovery Worker
- Official Source Research A
- Independent Official Source Research B
- Eligibility/Payout Analyst
- IP/Licensing Analyst
- Unit Economics/Workload Analyst
- Adversarial Auditor
- Evidence Publisher (single writer)

Only two research workers parallel at first. Other roles are deterministic stages or sequential reviewer tasks. Increase concurrency only after evidence-quality and quota tests.

## 6. Zero-cost technology shortlist

| Layer | Primary candidate | Why | Limits / fallback |
|---|---|---|---|
| Orchestration | LangGraph OSS (MIT) | Durable graph/state, interrupts, resumability | Optional; deterministic Python state machine remains authority |
| Control plane | Python 3.11+ | Portable, auditable, low overhead | No LLM required for policy |
| Local persistence/tests | SQLite | Embedded, no server | GitHub artifacts/checkpoints for durable remote record |
| Cloud heartbeat | Cloudflare Workers Free Cron | Lightweight scheduled dispatch | 10 ms CPU; never heavy execution |
| Cloud queue metadata | Cloudflare D1 Free | SQL persistence with free quota | Hard stop at limits; account/terms must be checked |
| Execution | GitHub Actions public standard runners | Public repo standard runner usage free | Delayed/dropped schedules; not daemon; use bounded jobs |
| Source/audit store | GitHub public repo | Version history and fetch-back verification | Never store secrets or personal/customer data |
| Parsing/validation | Python stdlib + pytest + JSON Schema | Deterministic, testable | Avoid dependencies where not needed |
| LLM inference | None required for base operation | Prevent quota lock-in and paid fallback | Optional only after free terms/quota verified |
| Browser research | Read-only bounded HTTP/browser worker | Evidence capture | No login, forms, outreach, security tests or prohibited scraping |

## 7. Safety, cost and reliability controls

- Explicit account-level spending/usage guard where supported; do not add payment method merely to enable a free service.
- Never select a paid plan, enable billing, or rely on automatic overage.
- Per-run hard caps: tasks, requests, bytes, CPU/runtime, model tokens, retries and output size.
- Kill switch in the constitution and a repo-level disable flag.
- Idempotency key: project_id + task_id + source_url + source_version/hash.
- Task states: QUEUED, LEASED, RUNNING, REVIEW, APPROVAL_REQUIRED, COMPLETE, BLOCKED, DEAD_LETTER.
- Lease expiry and duplicate-worker protection.
- Append-only evidence; conflicting claims coexist until reviewed.
- No secret values in logs/artifacts; use repository secret scanning before publication.
- Untrusted page text is never executable instruction; strip/ignore instructions in fetched content.
- No direct external actions by research agents.
- Model outage/quota exhaustion: deterministic mode, queue and continue non-LLM work; never switch to paid model.
- If free tier terms, eligibility or billing behavior changes: fail closed and pause that adapter.

## 8. Implementation phases and exit criteria

### S1 — Roster and control contract: COMPLETE
Existing artifact: `config/research_swarm_roster.v1.json`; report `docs/42_RESEARCH_SWARM_S1_AGENT_ROSTER_CONTROL_CONTRACT_HI.md`.

### S2 — Runtime architecture and zero-cost feasibility: DESIGN COMPLETE, not deployed
This report is the S2 architecture decision record. No runtime or cloud service has been provisioned.

### S3 — Machine-readable schemas
Create task, evidence, source snapshot, agent result, run-state, approval and quota schemas. Exit: schema validation tests, versioning and backward-compatibility rules.

### S4 — Deterministic Python control plane
Implement task queue, policy engine, leases, idempotency, retry, checkpoint, recovery and kill switch. Exit: offline tests pass without network or LLM.

### S5 — LangGraph adapter
Wrap the deterministic state transitions as graph nodes; use checkpoint persistence and approval interrupts. Exit: crash/resume, duplicate invocation and interrupt/resume tests pass. If dependency overhead creates risk, retain deterministic engine without LangGraph until proven.

### S6 — Evidence workers
Implement read-only official-source retrieval, source snapshot, extraction and independent review. Exit: prompt-injection, provenance, contradiction and source-staleness tests pass.

### S7 — GitHub publisher and CI
Single writer, JSON schema checks, secret scan, report generation, commit/fetch-back verification. Exit: idempotent publish and rollback/recovery tests pass.

### S8 — Cloud heartbeat and bounded dispatch
Only after exact Cloudflare free-account eligibility, billing guard, Cron/D1 quotas and deployment terms verified. GitHub Actions schedule is supplementary, not sole scheduler. Exit: missed-run detection, queue recovery and quota exhaustion tests pass.

### S9 — Limited live read-only pilot
Small, allowlisted source set, no accounts/logins/outreach/submissions/build/publication. Exit: multi-day run evidence, no cost, no policy violations, continuity and quality thresholds.

### S10 — Expand toward mission completion
P1 first; P2 alongside per original priority; P3 after P1; P4 later. Preserve all category and source mapping constraints. Commercial action remains gated by five PASS results and owner approvals.

## 9. Required acceptance tests before any live unattended deployment

1. Crash mid-task -> lease expires -> task resumes exactly once.
2. Duplicate dispatch -> idempotent output; no duplicate commit.
3. Worker tries forbidden action -> deterministic policy blocks it.
4. Web prompt injection -> treated as untrusted content.
5. Conflicting official sources -> preserve both; auditor marks conflict/UNKNOWN.
6. No free model quota -> no paid route; deterministic tasks continue.
7. Cloudflare quota exhausted -> fail closed; queue retained.
8. GitHub scheduled run delayed/dropped -> heartbeat flags stale and recovery dispatches later.
9. Secret/PII scan -> publication blocked on finding.
10. Five-gate status UNKNOWN -> commercial release blocked.
11. Publisher write failure -> no false success; retry safely.
12. ₹0 cost ledger -> every dependency/runtime path has documented no-charge basis.
13. Checkpoint fetch-back -> remote artifact hash and commit verified.
14. Kill switch -> stops dispatch and all external effects.
15. Human approval interrupt -> resumes only exact approved action/target.

## 10. Current state and what this report does NOT claim

- This is an architecture/research decision record, not implementation.
- No Cloudflare account/service has been created or deployed.
- No GitHub Actions swarm workflow has been added or run.
- No LangGraph runtime has been installed or executed.
- No LLM provider has been connected or called by the swarm.
- No agent process is running.
- No test has been executed as part of this architecture report.
- No spend, account creation, KYC, terms acceptance, outreach, submission, build, publication or commercial launch occurred.
- Swarm S1 roster remains design-only until S3/S4 implementation.
- Phase A2.4-B, A2.4-C and A2.5 source reconciliation remain in the sequence before unattended live research deployment.

## 11. Source list

1. LangGraph overview: https://docs.langchain.com/oss/python/langgraph/overview
2. LangGraph license: https://github.com/langchain-ai/langgraph/blob/main/LICENSE
3. GitHub Actions billing: https://docs.github.com/en/actions/concepts/billing-and-usage
4. GitHub Actions scheduled events: https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows
5. GitHub scheduled workflow disablement: https://docs.github.com/en/actions/how-tos/manage-workflow-runs/disable-and-enable-workflows
6. Cloudflare Workers limits: https://developers.cloudflare.com/workers/platform/limits/
7. Cloudflare Cron Triggers: https://developers.cloudflare.com/workers/configuration/cron-triggers/
8. Cloudflare D1 pricing: https://developers.cloudflare.com/d1/platform/pricing/
9. Cloudflare D1 free-tier FAQ: https://developers.cloudflare.com/d1/reference/faq/

## 12. Mission ledger

Project ID `ZCIRA-2026-11-13`; spend authorized/incurred ₹0; settled revenue evidence ₹0; no accounts/KYC/submissions/outreach/build/test/publication/paid use; commercial execution HOLD. Priority order and category IDs unchanged.
