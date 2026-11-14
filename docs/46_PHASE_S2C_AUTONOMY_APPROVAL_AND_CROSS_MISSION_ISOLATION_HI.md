# Phase S2-C — Autonomous operation, owner-approval bridge, and cross-mission isolation (2026-11-14)

## Executive decision
The user requests an end-to-end autonomous cloud-only swarm that does not require routine user intervention, while allowing explicit owner approval for OAuth/permissions when genuinely required. They also require protection against interference from other GitHub projects and other ChatGPT threads.

This report defines the operating model and corrects assumptions using the live canonical repository inspection performed on 2026-11-14.

## Live repository inspection
Canonical repository: `manish91082-coder/zero-cost-internet-revenue-automation`
Default branch: `main`
Visibility: public
Owner permission observed: admin/push
Latest continuity blob at inspection: `bc18e471288ff73e1b6d014a1290502c7f2975e7`
Root contents observed: `PROJECT_CONTINUITY.md`, `README.md`, `config/`, `docs/`, `scripts/`.
The `.github/workflows/` directory returned 404 (not present at inspected branch). No GitHub Actions workflow is therefore evidenced in this live tree at inspection.
Config files observed: `mission_constitution.v1.json`, `research_swarm_roster.v1.json`, `category_destination_registry_p1_p2.v1.json`.
Scripts observed: only `extract_destination_occurrences.py`.
Thus the current canonical repo has governance/registry/research artifacts, but no checked-in swarm runtime, workflow, OAuth bridge, persistent task DB, or live agent execution evidenced by this inspection. Prior conversation summaries that mention other runtime files/workflows must not be assumed to describe this repository's current main branch; reconcile any such code only by exact repository/path/commit.

## Target autonomy model
The system should be autonomous for routine, reversible, internal work:
1. A deterministic scheduler/dispatcher wakes the mission.
2. Mission controller reads canonical constitution, checkpoint, queue and gate states.
3. It selects the next task from the frozen sequence and verifies preconditions.
4. Up to two read-only research workers run in parallel with scoped task leases.
5. Workers return structured evidence, source snapshots, confidence/status, hashes and provenance.
6. Validators check schema, source quality, duplication, policy and acceptance criteria.
7. A single publisher obtains the repository write lease, verifies the expected base commit, then writes one atomic, idempotent update.
8. A continuity reconciler fetches the written file/commit back, verifies remote blob SHA and updates mission checkpoint.
9. A watchdog detects stale heartbeat, expired leases, failed jobs, quota exhaustion and incomplete checkpoints, then retries or dispatches an eligible fallback.
10. A daily audit checks spend, permissions, failed runs, drift, backlog and revenue evidence.

Routine operation should not require a user prompt. The user should receive concise exception/approval requests only for gated actions or meaningful decisions.

## Approval bridge and Google identity
The supplied Google account identifier is an identity hint only. It is not an OAuth credential and must never be placed in source code, public logs, workflow files, prompts sent to public services, or repository config.
- Never request/store password, OTP, recovery code, browser cookies, refresh tokens or session exports in chat.
- Use official OAuth authorization-code flow with PKCE where a supported integration requires Google access. Request the minimum scopes, preferably read-only; separate scopes by service.
- The user must approve consent in the genuine provider-hosted browser page. The system must not imitate Google login, automate credential entry, scrape session state, or treat a logged-in browser as blanket authorization.
- Store tokens only in the provider's supported encrypted secret store; never print them. Refresh-token rotation, revocation and expiry must be handled.
- A permission request must name: exact service, exact account, scopes, purpose, data read/written, duration, revocation path, and whether a free-tier/billing card is required.
- Approval is specific and revocable. Approval for Google sign-in does not authorize GitHub, Cloudflare, payments, public publishing, KYC, legal terms, or purchases.
- If the connector cannot safely broker OAuth, stop at an approval-required state and provide the provider's official authorization route; do not invent a browser-control capability.
- Account creation, terms acceptance, billing activation, KYC, external submissions, outreach, publication, money movement and production deployment remain separately gated. A general statement that the user will approve requests is not blanket consent to those individual irreversible actions.

## Cross-project and cross-thread isolation
Treat each mission as an independent security and execution domain, even when the same human owner operates it.
Required mission identity tuple:
`mission_id + canonical_repo + branch + environment_namespace + state_namespace + credential_scope`.
For this project use `ZCIRA-2026-11-13` and canonical repo `manish91082-coder/zero-cost-internet-revenue-automation`.
Controls:
- No implicit cross-repository writes. Every task carries a hard allowlist of repository and paths.
- No shared writable Cloudflare D1 database, bucket, queue, KV namespace, or Worker environment across missions. If account-level resource sharing is unavoidable, use separate database/namespace identifiers and scoped service tokens; otherwise keep resources separate.
- GitHub Actions concurrency group must include mission ID and workflow purpose. Use `cancel-in-progress: false` for stateful publishing and migrations; use explicit leases and idempotency for retries.
- Single-writer rule per canonical repository: workers read-only; publisher alone writes; acquire lease, compare expected base SHA, write, fetch back, release lease.
- Each task uses unique `task_id`, `idempotency_key`, lease owner, expiry, attempt count and immutable input checkpoint.
- Never let two ChatGPT threads independently publish to the same file. Threads are advisory/coordination surfaces; the repository checkpoint and lease are authoritative. A thread must fetch latest checkpoint before proposing or writing.
- Use branch isolation for experiments. Only the mission publisher may update `main`; merge only after CI and evidence validation.
- Use least-privilege GitHub App installation or narrowly scoped fine-grained token per repository. Do not reuse a broad personal access token across missions. Public repository visibility does not make secrets or write scopes safe.
- Add a machine-readable mission registry and resource registry so the controller rejects unknown repo, branch, namespace or secret identifiers.
- Global resource arbitration: record provider quotas, concurrency and rate limits per account. Allocate budgets fairly; do not bypass rate limits with alternate accounts, identities or proxies. A shared provider outage may affect multiple missions, but must not corrupt their state.
- A kill switch is mission-scoped and a global owner kill switch should stop all dispatch while preserving checkpoints.

## Automatic failover
- Primary execution candidate: GitHub Actions public runner for bounded ephemeral jobs, subject to workflow implementation and live verification.
- Independent watchdog candidate: Cloudflare Worker Cron, limited to lightweight heartbeat/dispatch only; not Python/LangGraph/model inference.
- Canonical durable audit/checkpoint: Git history and versioned artifacts; D1 may be a non-authoritative queue/lease mirror only after no-billing eligibility is verified.
- Failover may move only to an independently verified, permitted, free resource. It must not evade a provider block or quota.
- When all eligible free compute is unavailable, preserve queue/checkpoint and enter `PAUSED_NO_ELIGIBLE_FREE_EXECUTOR`. When all model providers are unavailable, continue deterministic work and mark model-dependent tasks `BLOCKED_NO_FREE_MODEL`.
- No claim of guaranteed 100% uptime, exact-minute scheduling, always-on daemon, or unlimited free inference.

## Autonomy boundaries
Can proceed autonomously after implementation and tests: public-source read-only research, source capture, parsing, deduplication proposals, evidence grading, deterministic calculations, internal report drafting, schema validation, repository checkpoint commits within the approved path allowlist.
Must request exact owner approval: OAuth scopes, account creation, accepting terms, billing/payment method, KYC, production cloud deployment where account/terms are involved, contacting people/platforms, bounty/grant submissions, publishing/listing products, external data writes, financial transactions, or any action with legal/reputational/financial consequence.
No approval request should be needed for ordinary internal read-only work.

## Implementation sequence
S2-C (this document): autonomy/approval/isolation design.
S3: versioned JSON schemas for task, evidence, source snapshot, gate decision, run state, agent message, approval, resource lease, mission registry and quota ledger; validate with synthetic fixtures.
S4: deterministic controller, queue, lease, idempotency, checkpoint and policy tests.
S5: LangGraph adapter, resumable state and human approval interrupts; deterministic path remains functional without LLM.
S6: read-only workers and official-source evidence capture.
S7: single publisher, GitHub API commit/fetch-back verification and CI.
S8: Cloudflare watchdog/dispatch only after no-cost account/terms eligibility and explicit deployment approval; failover and cross-mission collision tests.
S9: bounded unattended read-only pilot with alerts and rollback.
S10: expansion only in frozen P1/P2/P3/P4 order and only after gates.

## Current status and owner-impact
- This report is design/governance only.
- No new OAuth, account, secret, cloud resource, workflow, agent, deployment, billing, KYC or external submission was created.
- No new permission was requested or assumed.
- User routine intervention target: none for ordinary internal research after implementation; owner intervention remains necessary for exact gated actions.
- Spend authorized/incurred: ₹0. Settled revenue evidence: ₹0.
- Swarm production status remains NOT IMPLEMENTED / NOT DEPLOYED.
- Next engineering action: S3 schemas and synthetic collision/approval fixtures, while source registry A2.4-B/C/A2.5 reconciliation continues. Do not skip the original mission priority sequence.
