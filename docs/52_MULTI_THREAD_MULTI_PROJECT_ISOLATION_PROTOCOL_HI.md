# Multi-thread and multi-project isolation protocol (2026-11-15)

## Decision

Other ChatGPT threads and other GitHub projects do not automatically share a single execution context. They can still collide through a shared GitHub account, the same repository/branch, shared Cloudflare or other cloud account quotas, or overlapping credentials. Separate repositories prevent ordinary file-level collisions, but they do **not** guarantee separate account-level quotas.

This ZCIRA project is now assigned a strict mission namespace and one-writer protocol. The machine-readable policy is `config/mission_isolation_policy.v1.json`.

## Conflict matrix

| Situation | Direct risk | Required control |
|---|---|---|
| Other project, separate repository and separate cloud account | Low file-level risk | Keep mission ID, repo, branch, secrets and state namespace separate |
| Other project, separate repository but same GitHub owner | Shared API/rate-limit contention remains possible | Owner-level resource ledger before parallel high-volume automation |
| Other project, same Cloudflare account | Account-level Worker/Cron/D1 limits can be shared | One quota ledger across projects; no assumption that per-project limits multiply |
| Two ChatGPT threads writing this same repo/main | High stale-head and overwrite risk | One writer lease, branch-head compare-and-swap, one publisher |
| Two threads writing different branches of this repo | Drift and merge conflict | Canonical main branch; no ad hoc feature branch without approval |
| Different threads doing read-only research | Low repository risk | Research outputs are evidence proposals; only canonical publisher writes |
| Same Google email used at multiple services | Authentication identity is shared, permissions are not | Separate OAuth consent per app, provider, exact scope and duration |

## How the cross-thread lock must work

1. Every thread first reads the latest `PROJECT_CONTINUITY.md`, canonical branch head, mission registry and writer-lock state.
2. A thread without a valid writer lease may perform read-only research and prepare a draft, but may not update canonical files.
3. The single publisher acquires a short-lived writer lease by committing the lease state against the exact current main-branch SHA.
4. The branch update uses compare-and-swap. If another thread has advanced main, the stale writer loses and must re-fetch. It must never force-push or silently overwrite.
5. The publisher writes only within the mission path allowlist, then releases the lease with another compare-and-swap commit.
6. If a writer crashes, the lease expires. A new writer may acquire only after checking the latest head and confirming expiry.
7. GitHub Actions later adds a repository concurrency group and protected-branch checks. This protects workflows, while the branch-head compare-and-swap protects direct GitHub API writes.

**Important limitation:** S4 currently has pure/in-memory lease and compare-and-swap logic. The durable writer-lock file, branch protection and GitHub Actions concurrency group are not implemented/configured yet. Therefore the protocol is designed and partly coded, but cross-thread write exclusion is not yet mechanically enforced. Until S4-B/S7 complete, this canonical writer must be the only thread making ZCIRA repository writes.

## How other projects remain independent

- Each project keeps a unique mission ID, canonical repository, canonical branch, environment namespace and state namespace.
- No task, evidence, lease, checkpoint, credential or artifact may be reused across mission IDs.
- No shared state or cross-mission write is permitted.
- A project may read public documentation, but it cannot write another project's repository.
- Shared account quotas are a separate concern. Before running multiple cloud swarms under the same owner account, a global resource ledger must record each provider's account-level quota, current consumption, reservations and circuit state. That ledger is design-only and is not created in this ZCIRA-only work.
- This mission will not inspect, edit or take ownership of the user's other project repositories. Their own canonical threads and repositories remain separate.

## Google login and owner permission

The same email address can identify the owner at multiple services, but it is not a universal authorization token. Google sign-in and OAuth consent are separate from GitHub, Cloudflare and other providers. A consent grant is tied to a specific application and requested scopes.

When an integration genuinely becomes necessary, the request must state:
- exact provider and application;
- exact OAuth scopes, preferably read-only;
- what data will be read or changed;
- purpose and duration;
- whether billing, payment method, KYC or legal acceptance is required;
- how access can be revoked.

No email address, password, OAuth token, cookie or recovery code is stored in this public repository. No broad Google consent is requested now. If a provider requires billing/payment method or unknown obligations, it remains ineligible under the ₹0 rule even if a login or consent screen is available.

## Current ZCIRA protection status

- Present: unique mission registry, canonical repository/branch, state and environment namespaces, cross-mission sharing/writes set false, scoped path allowlist, deterministic single-writer role, in-memory lease checks and branch-head compare-and-swap function.
- Not yet present: durable writer-lock state, branch protection, GitHub Actions concurrency group, global owner resource ledger, cross-project quota coordinator.
- Current root still has no `.github/workflows/` directory. No cloud worker or runtime is deployed.

## Implementation order

1. **S4-B:** persist task/lease/checkpoint state and implement a durable main-branch writer-lock protocol using expected-head SHA.
2. **S7:** add GitHub Actions concurrency group, least-privilege permissions, protected-branch/PR publication and automated lock checks after acceptance tests.
3. **Cross-project resource ledger:** design separately and do not create another repository or cloud account until owner approval is explicitly requested and the free-tier/no-billing eligibility is verified.

This approach allows other projects to continue in their own repositories. The protection boundary is the mission/repository namespace plus a single-writer protocol, not the email address or the ChatGPT chat thread.
