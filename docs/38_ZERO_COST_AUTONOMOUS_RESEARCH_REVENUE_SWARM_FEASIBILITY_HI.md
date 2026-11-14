# Zero-Cost Autonomous Research & Revenue Swarm — Feasibility and Reference Architecture
Audit date: 2026-11-14 (Asia/Kolkata)
Project ID: ZCIRA-2026-11-13
Status: ARCHITECTURE RESEARCH / NO IMPLEMENTATION OR COMMERCIAL EXECUTION AUTHORIZED

## 1. Executive decision

**Decision: FEASIBLE WITH BOUNDED AUTONOMY; NOT FEASIBLE TO GUARANTEE UNLIMITED CLOUD AI INFERENCE AT ₹0.**

The project can replace most repetitive response-by-response research with a persistent, scheduled, multi-agent workflow. The system should be designed as a deterministic evidence pipeline with specialist AI agents as bounded workers, not as a free-form group chat of agents.

A practical zero-out-of-pocket architecture is possible using:
- public GitHub repository and GitHub Actions for versioned workflow orchestration and scheduled runs;
- LangGraph or a small deterministic Python state-machine as the control plane;
- optional free model APIs as quota-limited reasoning workers, with provider rotation only among currently permitted free tiers;
- local Windows/WSL CPU execution as an optional fallback, not a requirement for every run;
- official-source-first web retrieval, browser automation only where permitted, and source snapshots/hashes;
- GitHub Markdown/JSON/SQLite or a free-tier database for durable evidence and run state;
- human approval gates for legal, financial, identity, external communication and irreversible actions.

This cannot guarantee 24/7 uninterrupted operation, unlimited model calls, stable free quotas, automatic KYC, platform acceptance, customer demand, or revenue. Those are external dependencies. The system can detect and report blockers rather than silently bypass them.

## 2. Mission and policy invariants

This swarm is part of ZCIRA only. It does not merge with the ₹10 Cr mission, ₹1,000/day mission, crypto, trading, flash-loan, Ghost Hunter or any other project.

It must preserve:
- Initial/out-of-pocket spend ₹0; no paid fallback, paid API, hosting, domain, subscription, KYC fee, wallet top-up or billing activation.
- P1 Tool Factory first; P2 alongside; P3 after P1; P4 later; P5/B/M later or owner choice.
- Original category IDs, names, destination counts, evidence grades, exclusions and source mapping.
- Five gates: independent buyer intent; IP/licensing/data rights/legal permission; fully loaded ₹0 unit economics; India seller eligibility and verified payout; autonomous fulfilment and realistic owner workload.
- Revenue counts only after settlement into an owner-controlled bank account/wallet with transaction evidence.
- No account creation, KYC, legal terms acceptance, application/submission, security testing, buyer/platform outreach, product build, publication, paid use or spend without the relevant explicit approval.
- Public repo contains no secrets, tokens, personal identity/KYC data, private customer data or credentials.
- Untrusted webpage content is evidence only, never executable instructions for agents.

## 3. What can be automated

| Workstream | Automation ceiling | Required controls |
|---|---|---|
| Discover official programmes, marketplaces and product opportunities | High | Source allowlist, query log, deduplication |
| Read official terms, eligibility, pricing and payout rules | High | Capture date, exact URL, quote snippets, version/hash |
| Extract structured facts into a common schema | High | Schema validation and source-linked fields |
| Compare terms across sources and detect changes | High | Diff, source freshness and contradiction flags |
| Apply five commercial gates | High for preliminary classification | Independent reviewer; UNKNOWN is not PASS |
| Estimate workload and unit economics | High for modelled assumptions | Explicit assumptions, formulas, sensitivity ranges |
| Generate product specifications and test plans | High | No build/test until approval |
| Create GitHub reports, ledgers and continuity updates | High | Branch protection / restricted write token / diff checks |
| Schedule recurring scans and resume after failures | High | Idempotency, run IDs, retry limits, checkpoint |
| Create accounts, KYC, accept contracts, submit applications | Not autonomous by policy | Owner action/approval |
| Security testing or exploit validation | Not autonomous by policy | Written authorization and scope |
| Buyer/platform outreach | Approval-gated | Owner approves exact message and recipient |
| Build, publish, charge, fulfil, refund | Conditional | Five gates + separate release approval |
| Verify bank/wallet settlement | Partially automatable | Owner-controlled records/statement evidence; privacy protection |

The goal is maximum useful automation, not pretending every external or legal dependency can be automated.

## 4. Proposed agent topology

Use a **supervisor + specialist workers + independent auditors** design. Do not let all agents independently browse and write to GitHub. The supervisor assigns bounded tasks; workers return structured evidence; auditors challenge it; one writer commits approved artifacts.

### Core agents

1. **Mission Controller / Orchestrator** — loads PROJECT_CONTINUITY.md and policy manifest; selects the next unfinished task; enforces project boundaries and category order.
2. **Opportunity Discovery Agent** — discovers candidates only within the locked category/destination registry; does not invent new categories.
3. **Official Source Research Agents (2 parallel workers)** — retrieve primary official pages, terms, FAQs, legal/payout documents; produce URL, page title, capture time and evidence excerpts.
4. **Eligibility & India Payout Agent** — checks country eligibility, seller type, KYC, payout rail, thresholds, timing, FX and bank settlement. Missing evidence stays UNKNOWN.
5. **IP / Licensing / Data Rights Agent** — checks ownership, third-party data, licences, sublicensing, exclusivity, warranties, indemnity and retention.
6. **Unit Economics Agent** — computes all-in variable/fixed costs, compute, API, proxies, hosting, payment, FX, refunds, support, maintenance, taxes where in scope and human labour; applies ₹0 constraint.
7. **Demand & Market Evidence Agent** — separates demonstrated buyer intent from traffic, popularity, historical awards and platform claims; records interviews/LOIs only when owner-authorized.
8. **Automation & Workload Agent** — estimates human minutes, exception rates, maintenance and fulfilment feasibility.
9. **Adversarial Reviewer / Red Team** — attempts to falsify every PASS, searches contradictory terms and stale sources; cannot change evidence.
10. **Evidence Editor / GitHub Publisher** — validates schema, citations, duplicate IDs, diffs and checkpoint; only agent with repository write access.
11. **Revenue Reconciliation Agent** — records gross/fees/net/settlement date/reference only from owner-authorized evidence; no estimated award is revenue.
12. **Human Approval Gate** — a workflow state, not an LLM agent. Pauses on account/KYC/legal acceptance/submission/contact/build/publication/spend/financial actions.

For reliability, use 2 independent source workers plus 1 adversarial reviewer for high-impact claims. Avoid 10 agents all asking the same model to repeat one another: that multiplies token usage without creating independent evidence.

## 5. Reference architecture

```text
GitHub main (mission constitution + destination registry + evidence ledger)
              |
        Scheduler / Queue
   GitHub Actions cron + manual dispatch
              |
       Mission Controller
              |
     Task Planner / State Graph
              |
   +----------+-----------+------------------+
   |          |           |                  |
Discovery  Official     Gate/Economics   Workload/IP
Agent      Research     Agents            Agents
   |          |           |                  |
   +----------+-----------+------------------+
              |
       Evidence Normalizer
   (URL, title, timestamp, excerpt, hash,
    claim, confidence, status, category ID)
              |
       Independent Adversarial Audit
              |
        Decision Engine
    PASS / FAIL / UNKNOWN / HOLD
              |
      Approval / Safety Firewall
        |                 |
   Research-only      Owner approval
        |                 |
   GitHub report     approved bounded action
        |                 |
   Checkpoint + audit log + next queue item
```

Recommended implementation pattern:
- Keep workflow transitions deterministic and explicit.
- Each task has stable task_id, category_id, destination_id, status, attempts, sources, evidence, reviewer verdict and next_action.
- Use idempotent task execution. A retry must not create duplicate reports, messages or submissions.
- Use a lease/lock for one writer and one active run per task.
- Store raw source snapshots or extracted text with SHA-256 and capture time where terms/version matter.
- Store only public evidence in the public repo. Secrets are not stored in GitHub files or logs.
- Use JSON Schema validation before Markdown generation.
- Agent outputs are proposals; the deterministic gate engine decides status from evidence completeness.

## 6. Framework and tool assessment

### 6.1 LangGraph — preferred orchestration candidate
Official LangGraph documentation describes it as a low-level runtime for long-running, stateful agents with durable execution, persistence, streaming and human-in-the-loop. It supports deterministic nodes alongside LLM-driven nodes and does not require LangChain. This fits the project's resumability and approval workflow. It is open-source software, but self-hosting still requires compute and model inference.

### 6.2 CrewAI — viable alternative for specialist crews
CrewAI's official OSS materials describe role-based agents, Crews, Flows, checkpointing and async collaboration. It can express specialist teams quickly. However, for this project's strict audit trail and deterministic gate engine, a flow/state-machine must remain authoritative; role-play output alone is not sufficient evidence.

### 6.3 Microsoft AutoGen — do not select for new production build
The official repository now says AutoGen is archived and no longer maintained, warns against production use, and points new users to Microsoft Agent Framework. Microsoft Agent Framework reached 1.0 GA on April 2, 2026, according to Microsoft's announcement. It is a possible alternative but would add framework complexity; do not adopt without a separate fit/license/dependency review.

### 6.4 LiteLLM — optional provider abstraction
LiteLLM offers a unified OpenAI-compatible interface to 100+ model providers, retries/fallbacks and a self-hosted gateway. Useful only if free provider routing becomes complex. It does not make paid inference free; disable all paid routes and enforce a hard provider allowlist/budget ceiling of zero.

### 6.5 Playwright — browser automation
Playwright supports Chromium, Firefox and WebKit automation and has an MCP integration for AI agents. Use for public pages and permitted workflows, with domain allowlists, read-only default, download limits and explicit approval before any login, form submission or external action. Robots/terms, access controls and programme scope still apply.

### 6.6 n8n — not the default
n8n Community Edition is free to self-host, but it is under the Sustainable Use License, not OSI open source. Its own FAQ distinguishes internal workflow use from hosted/customer-configurable automation, which can require a commercial licence. Since the future business model is not yet fixed, prefer permissively licensed components or conduct a use-case-specific license review before adopting n8n.

## 7. Zero-cost compute and model strategy

### Tier A — deterministic work (default)
Use Python scripts, HTTP retrieval where permitted, HTML parsing, diffing, hashing, JSON schema, SQLite and GitHub API. These tasks do not need an LLM. This is the main lever for reducing inference demand.

### Tier B — free hosted model APIs (opportunistic)
- Gemini API: official pricing page lists a free tier with limited model access and free input/output tokens. The same page states free-tier content may be used to improve Google products. Therefore use only non-sensitive public data, check current model-specific quotas, and do not assume production-grade availability.
- OpenRouter free variants: current official free-model page states 20 requests/minute and 50 requests/day; the higher 1,000/day cap requires at least $10 purchased credits, which is forbidden here. Some other $0 models have provider-specific limits. Use as a small optional pool, not the system backbone.
- Hugging Face Inference Providers: current pricing docs list $0.10/month free-user credits, subject to change. This is a small trial allowance, not sustainable compute; do not rely on it as the primary engine.

Provider policy:
- Maintain an allowlist of explicitly $0 providers/models.
- Disable credit purchase, billing enablement and paid fallback.
- Add per-provider daily request/token caps and a global hard stop.
- If free quota is exhausted, queue the task for later or use deterministic/local fallback. Never silently switch to paid inference.
- Do not send confidential, personal, KYC, account or customer data to consumer/free model tiers.

### Tier C — local CPU fallback
Ollama or another local runtime can run open-weight models on the existing Windows/WSL laptop without per-token API charges, but compute is not literally costless: electricity, RAM, disk, CPU time and latency remain. With no GPU, use small quantized models for extraction, classification, draft summaries and schema repair; use deterministic code for legal/economic calculations and require source citations. Local models are not a substitute for high-confidence legal interpretation or independent primary evidence. Exact viable model size must be benchmarked on the actual laptop RAM/CPU before selection.

## 8. Free scheduling, persistence and storage

### GitHub Actions
Official GitHub documentation says standard GitHub-hosted runner usage is free for public repositories and for self-hosted runners. This makes a public repository suitable for scheduled research workflows, subject to GitHub Actions limits, fair-use/Terms of Service, concurrency and runtime constraints. Keep all secrets out of logs and public artifacts. Use least-privilege GitHub App/PAT permissions and short-lived tokens where possible.

### Cloudflare Workers / Cron / D1 (optional)
Official Workers Free limits currently include 100,000 requests/day, 10 ms CPU per request, 128 MB memory and five Cron Triggers/account. This is suitable for lightweight scheduling/webhooks, not for long-running browser research or LLM orchestration.
Cloudflare D1 free limits include 10 databases, 500 MB per database, 5 GB total account storage and 50 read subrequests per Worker invocation; over-limit operations fail until quota reset or plan change. It can serve as a small structured ledger, but GitHub + SQLite may be simpler and less vendor-dependent initially.
Cron Triggers run on UTC. Convert schedule deliberately and do not assume India local time in cron expressions.

### Recommended initial persistence
- GitHub: controlling documents, reports, immutable evidence references, schema, registry, audit log and continuity checkpoint.
- SQLite: transient task queue/cache and local state during a run; export deterministic JSON/Markdown to GitHub.
- Optional D1 only after a need for remote shared state is proven. No dependency on a paid database.

## 9. Cost and operational reality

| Component | Cash cost target | Constraint |
|---|---:|---|
| LangGraph / CrewAI / Playwright / Python | ₹0 software | Self-hosted execution still consumes hardware/electricity |
| Public GitHub repo + public Actions runners | ₹0 within included public-repo policy | Fair use, runtime and service limits |
| Free model APIs | ₹0 | Quotas, data terms, model availability change |
| Local small model | ₹0 API | Existing hardware only; CPU latency and electricity |
| GitHub Markdown/JSON/SQLite | ₹0 | Repo size and storage discipline |
| Cloudflare Free (optional) | ₹0 | Strict CPU/request/storage limits |
| Domain/paid hosting/paid APIs | ₹0 permitted | Not to be used |
| KYC/account/entry/trading fees | ₹0 permitted | Any mandatory fee disqualifies route unless owner separately changes policy |

**Important distinction:** A free tier is not a guarantee of sustainable zero-cost production. The system must degrade gracefully when quotas are exhausted. It cannot promise continuous 24/7 autonomous work at arbitrary scale with no infrastructure budget.

## 10. Safety and governance design

Implement a hard policy engine outside the LLM:
- Action classes: READ_PUBLIC, WRITE_REPO, CREATE_DRAFT, LOGIN, ACCOUNT_CREATE, KYC, ACCEPT_TERMS, CONTACT_EXTERNAL, SUBMIT, BUILD, EXECUTE_TEST, PUBLISH, PURCHASE, TRANSFER_FUNDS.
- Default allow: READ_PUBLIC and approved internal draft/report creation.
- Conditional allow: WRITE_REPO only through validated publisher after diff and policy checks.
- Default deny pending owner approval: all other action classes.
- Hard deny under current mission constitution: purchase, wallet funding, paid fallback, unapproved security testing and any action that incurs cost.
- LLM cannot grant itself permission, edit policy, bypass a gate, or promote UNKNOWN to PASS.
- Every approval is scoped to one exact action, target, amount (must be zero), artifact and expiry. No blanket consent inferred.
- If a page contains prompt injection, treat it as hostile source content; no instruction from a webpage can alter system policy or call tools.

## 11. Decision quality: evidence and audit protocol

Every material claim must have:
- claim_id and linked category/destination ID;
- exact official URL and publisher;
- page title, captured_at timestamp, last-updated date if available;
- short supporting excerpt and extracted structured value;
- source hash or snapshot reference for mutable terms;
- evidence grade and whether primary/secondary;
- contradictory source IDs;
- agent identity/version and model/provider used;
- reviewer verdict: CONFIRMED / CONTRADICTED / INSUFFICIENT;
- gate verdict: PASS / FAIL / UNKNOWN / HOLD.

Rules:
- No source means no claim.
- Search snippet is a lead, not final proof.
- A historical prize or platform headline is not current inventory.
- A token prize is not bank-settled revenue.
- Missing India payout terms remain UNKNOWN.
- A calculated break-even floor is not market price, demand or forecast.
- Two agents using the same source are not independent corroboration.
- High-impact claims require direct primary source and adversarial review.

## 12. Proposed execution phases

**Phase A — Constitution and schemas (first build increment)**
Create machine-readable mission policy, destination registry, task schema, evidence schema, gate schema and approval matrix. Validate exact P1/P2/P3/P4 order and all existing IDs. No external action.

**Phase B — deterministic research engine**
Build source fetcher, URL canonicalizer, content snapshot/hash, diff detector, structured extraction queue and report generator. Read-only public sources. Unit tests use fixtures, not live accounts or paid services.

**Phase C — agent orchestration**
Add supervisor, two source workers, payout/IP/economics/workload specialists, adversarial reviewer and evidence editor. Start with a small bounded crew, not dozens of agents. Use explicit task budgets and retry ceilings.

**Phase D — scheduled autonomous research**
Run GitHub Actions on a conservative schedule plus manual dispatch. Each run resumes from checkpoint, processes a fixed batch, writes reports and fetch-back verifies. On quota or source failure, pause/queue; no paid fallback.

**Phase E — five-gate decision engine**
Apply gates to the original locked destination registry. Produce an auditable PASS/FAIL/UNKNOWN/HOLD result and next action. Commercial execution remains disabled by default.

**Phase F — approved execution adapters**
Only after an opportunity passes all five gates and owner separately approves the exact action, add narrowly scoped adapters for platform workflow. KYC/legal acceptance remain human-operated. No automatic spend or wallet signing.

**Phase G — fulfilment and revenue reconciliation**
For approved product routes, automate delivery, monitoring, support triage and invoice/settlement evidence capture. Count revenue only after actual owner-controlled settlement. Refunds, chargebacks, costs and human work must reconcile.

## 13. Initial agent count and concurrency

Recommended starting point: 8 logical roles, not 8 permanently running servers:
- 1 controller;
- 2 independent research workers;
- 1 eligibility/payout specialist;
- 1 IP/licensing specialist;
- 1 unit economics/workload specialist;
- 1 adversarial auditor;
- 1 evidence publisher.

Workers execute sequentially or in small parallel batches depending on provider quotas. Add roles only when measured quality or throughput justifies them. The source research can be parallelized while final gate decisions remain serialized and deterministic.

## 14. Acceptance tests before any live deployment

- Resume test: terminate a run mid-task and resume without duplicate work.
- Idempotency test: rerun same task and prove no duplicate report/submission.
- Policy test: simulated prompts ask agents to create accounts, accept terms, contact, submit or spend; all must be blocked.
- Prompt-injection test: hostile webpage text cannot alter policy or invoke tools.
- Evidence test: unsupported claim must remain UNKNOWN.
- Contradiction test: conflicting official pages trigger review, not arbitrary selection.
- Quota test: provider returns 429/limit; task queues and no paid provider is called.
- Secret test: repository scan and log scan show no credentials or personal data.
- Gate test: any one failed/unknown gate prevents commercial execution.
- Revenue test: projected award or token balance is never counted as settled revenue.
- GitHub test: report and checkpoint fetch-back match committed blob hashes.
- Cost test: all tests run locally or on permitted free infrastructure with billing disabled; no hidden external service charge.

## 15. Feasibility verdict by goal

| Goal | Verdict |
|---|---|
| Stop repeating tiny manual research every response | FEASIBLE |
| Parallelize official-source research and independent audits | FEASIBLE |
| Maintain memory/continuity and resume from exact checkpoint | FEASIBLE |
| Automatically update GitHub reports/checkpoint | FEASIBLE with least-privilege credentials and tests |
| Run scheduled research on public GitHub Actions | FEASIBLE within service policy/limits |
| Use free LLM APIs as primary unlimited engine | NOT FEASIBLE / quota-dependent |
| Use local CPU models as fallback | FEASIBLE, performance to benchmark |
| Fully automate account/KYC/legal acceptance | NOT APPROPRIATE; human gate required |
| Guarantee every opportunity qualifies for India payout | NOT POSSIBLE; external eligibility |
| Guarantee buyer demand or revenue | NOT POSSIBLE; must be demonstrated |
| Guarantee 24/7 unlimited cloud execution at ₹0 | NOT FEASIBLE |
| Achieve maximum practical automation with owner approvals at critical points | FEASIBLE |

## 16. Recommended technical decision

Adopt **LangGraph + deterministic Python policy/state engine + Playwright read-only research + GitHub Actions + GitHub/SQLite evidence store** as the reference architecture. Keep CrewAI as an evaluated alternative, not a second orchestration layer. Use optional free Gemini/OpenRouter/Hugging Face quotas only as opportunistic workers; local CPU model as fallback after hardware benchmark. No n8n dependency initially because its Sustainable Use License needs a business-use fit review.

Do not start a broad autonomous build immediately. First create the constitution, schemas, test fixtures and read-only source pipeline. Then benchmark the actual machine and free model quotas. The system should earn permission to automate more by passing tests, not assume permission at design time.

## 17. Current project ledger and next action

Prior research remains at Phase 25 Batch 3. Phase 25 Batch 4 is still pending; this architecture study does not replace or reorder P1/P2/P3/P4.

- Spend authorized: ₹0.
- Spend incurred: ₹0.
- Settled revenue evidenced: ₹0.
- Approved products: 0.
- Accounts/KYC: 0.
- Submissions: 0.
- External outreach: 0.
- Product builds/tests/publications: 0.
- Commercial execution: HOLD.
- Architecture status: FEASIBLE DESIGN / IMPLEMENTATION NOT STARTED.

**Next recommended action:** Phase A — create the machine-readable constitution and registries, then Phase B read-only research engine. Preserve Phase 25 Batch 4 research as a parallel backlog item and do not mark it complete. No external actions or spend.

---
Research boundary: official public documentation and architecture analysis only. No accounts, KYC, terms acceptance, submissions, contact, build, test, publication, paid use or spend occurred.
