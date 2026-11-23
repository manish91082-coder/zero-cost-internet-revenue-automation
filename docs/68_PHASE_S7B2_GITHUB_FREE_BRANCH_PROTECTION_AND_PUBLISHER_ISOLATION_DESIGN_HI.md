# Phase S7-B2 — GitHub Free branch protection and publisher isolation design

**तिथि:** 2026-11-23  
**Project:** ZCIRA-2026-11-13  
**स्थिति:** OFFICIAL-DOC RESEARCH COMPLETE / DESIGN ONLY / SETTINGS NOT CHANGED

## 1. Current repository state — directly observed

- Repository is public: `manish91082-coder/zero-cost-internet-revenue-automation`.
- Main branch metadata: `protected=false`, `protection.enabled=false`.
- Repository rulesets endpoint: empty array.
- Existing S7-A workflow: `contents: read` at workflow and job level; no secrets, OIDC or write token.
- Current S7-A run on latest roster/config head `569bf3f0936f38e12ecd9b25f989052ad5f4adb1`: run `45105701263`, SUCCESS, 193 passed, 1 expected skip, 6 subtests.
- No publisher write workflow or publisher credential exists.

## 2. Zero-cost eligibility finding

GitHub's current documentation says branch protection and repository rulesets are available for public repositories on GitHub Free. This is not inherently a paid-plan blocker. Ruleset creation/editing requires repository admin access or the custom `edit repository rules` permission.

Official references:
- Branch protection availability: https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches
- Rulesets availability and bypass actors: https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets
- Ruleset REST permissions: https://docs.github.com/en/rest/authentication/permissions-required-for-fine-grained-personal-access-tokens
- GITHUB_TOKEN: https://docs.github.com/en/actions/concepts/security/github_token
- Workflow permissions: https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax

The connected GitHub integration cannot read the dedicated branch-protection endpoint (403) and no rulesets exist. This is an authorization gap, not evidence that GitHub Free lacks the feature.

## 3. Token model and event semantics

### Read-only CI

S7-A remains:
- `permissions: contents: read`
- standard GitHub-hosted runner
- no secrets or OIDC
- exact commit SHA fetch and detached checkout
- no repository writes

### Publisher candidate

GitHub automatically creates a unique, repository-scoped `GITHUB_TOKEN` for each job; it expires when the job ends or reaches its effective maximum lifetime. Per-job permissions can be set to least privilege.

However, a commit pushed using `GITHUB_TOKEN` does not normally trigger another push workflow. `workflow_dispatch` and `repository_dispatch` are documented exceptions. Therefore a future publisher must either:
1. perform its own post-commit validation in the same job and explicitly verify the resulting commit; or
2. use a separately approved GitHub App installation token for the publisher, which can trigger a push workflow, while keeping the token confined to the publisher job.

Do not give S7-A write permissions. Do not add a personal access token to the repository.

## 4. Recommended isolation design — not activated

Preferred future path, subject to exact owner approval and a tested permission matrix:

1. Create one dedicated GitHub App for this repository only.
2. Runtime permissions: repository Metadata read and Contents read/write only; add no Administration, Actions, Secrets, Workflows, Packages, Deployments or OIDC permissions to the runtime installation.
3. Install it only on the canonical ZCIRA repository.
4. Keep the private key in a GitHub Actions secret/environment; never place it in source code, ChatGPT messages, public artifacts or logs.
5. Use the App integration as the only designated bypass actor in a main-branch ruleset, with a narrowly scoped publisher workflow and application-level state/evidence path allowlist.
6. The publisher workflow must run only from trusted `main`, with a single concurrency group, exact expected-head CAS, no force push, atomic commit, fetch-back verification and fail-closed behavior.
7. All non-publisher workflows remain `contents: read`. No other workflow receives the App private key.
8. Protect workflow/code/config paths against publisher writes. Any code/workflow change must go through a separately controlled change path; do not let an evidence publisher modify `.github/**`, `src/**`, `config/**`, `schemas/**` or dependency locks.
9. If App-based push events are used, S7-A must run on evidence-path pushes and verify the exact pushed commit. If `GITHUB_TOKEN` is used instead, implement an explicit `repository_dispatch`/same-job validation path because push-triggered workflows are suppressed.

### Important limitation

A branch ruleset bypass actor bypasses rules in that ruleset. Therefore the dedicated App must be trusted and its key must be available only to the one publisher workflow. The current connected ChatGPT GitHub integration is not a per-thread permission boundary. This design reduces ordinary thread collision risk only after ruleset enforcement and credential isolation are actually configured and tested.

## 5. Minimum ruleset candidate

Target: `refs/heads/main`.

- Enforcement: active.
- Restrict updates to the designated publisher integration.
- Block force pushes.
- Block deletions.
- Require a successful S7-A status check for code/config changes where the selected ruleset flow supports it.
- Protect workflow and policy files from publisher writes.
- No general repository-role bypass actor.
- No automatic bypass for ordinary ChatGPT connector writes.

Exact rule composition and bypass semantics must be verified against the current GitHub UI/API before activation. Do not guess an integration actor ID.

## 6. Owner permission boundary

No settings were changed. No App was created or installed. No private key or secret was generated. No token or admin scope was requested from a tool.

The eventual one-time owner-controlled setup would require:
- repository admin access in the browser to create the ruleset and install/configure the App;
- approval of the exact App installation permissions;
- direct placement of the private key into the intended GitHub Actions secret, without disclosing it to ChatGPT.

A temporary Administration:write credential should not be stored in the runtime. If the owner prefers not to create an App or secret, keep publisher deployment HOLD and use read-only research plus deterministic repo-only engineering.

## 7. Current operational status

- S7-B publisher core and S7-A CI: PASS.
- Live Git Data API write: NOT TESTED.
- Publisher workflow: DISABLED / NOT CREATED.
- Branch protection: NOT ENABLED / CONFIRMED.
- S6-B2 live egress controls: HOLD; live source requests 0.
- S8 Cloudflare Worker/Cron/D1: NOT DEPLOYED.
- S9 unattended pilot: NOT STARTED.
- Spend ₹0; settled revenue evidence ₹0.
- No account, KYC, legal acceptance, billing, outreach, submission, product build/listing or external commitment.

## 8. Next engineering action

Continue repo-only S7-B publisher acceptance: test the Git Data API transport contract, exact state/evidence path allowlist, expected-head conflict, atomic commit and fetch-back behavior using fake transport only. Keep the live publisher disabled until the owner-controlled App/ruleset setup is approved and independently verified. Then resume S6-B2 egress and durable LangGraph checkpoint work before S8.
