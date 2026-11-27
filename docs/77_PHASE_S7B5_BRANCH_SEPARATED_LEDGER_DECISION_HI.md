# Phase S7-B5 — branch-separated evidence-ledger architecture decision

**तिथि:** 2026-11-27  
**स्थिति:** DESIGN LOCKED / CODE MIGRATION PENDING / NO LIVE SETTINGS CHANGED

## 1. Decision

The canonical repository remains `manish91082-coder/zero-cost-internet-revenue-automation`. Split trusted code from mutable runtime state:

- `main`: trusted code, schemas, workflows, policies, research archive and continuity.
- `evidence-ledger`: data-only manifest, writer leases, immutable state objects, source-snapshot metadata, evidence proposals and audit objects.

This is a branch inside the same canonical repository, not a second repository or a runtime dependency.

## 2. Why the prior one-branch publisher bypass design is rejected

The live repository currently has only `main`; it reports `protected=false`, and the rulesets endpoint is empty. The detailed branch-protection endpoint is inaccessible to the connected integration (403).

Official GitHub docs establish:
- Branch/tag rulesets are available on public repositories with GitHub Free.
- Push rulesets are available for GitHub Team in internal/private repositories; file-path restrictions are push-rule features.
- A bypass actor can bypass rules in its ruleset; `Restrict updates` allows only bypass actors to push.

Therefore, a publisher App with repository-wide Contents write that bypasses the main ruleset is not a mechanically isolated single-writer design. Public GitHub Free cannot be assumed to enforce path-level push restrictions on main.

Sources:
- https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets
- https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/creating-rulesets-for-a-repository

## 3. Locked branch and ruleset design

### 3.1 Branch roles

| Branch | Content | Writer |
|---|---|---|
| `main` | Code, schemas, workflows, policies, research archive | Owner/admin only |
| `evidence-ledger` | State manifest, leases, immutable objects, evidence snapshots/proposals | Dedicated Publisher App only |

The publisher App is never a bypass actor on main.

### 3.2 Layered rulesets

1. Global branch creation: only owner/admin may create branches. Owner creates `evidence-ledger` once.
2. Main code branch: restrict updates to owner/admin; require PR and S7-A status; block force pushes and deletion.
3. Ledger update rule: restrict updates to the dedicated Publisher App; this is the only ruleset where the App is a bypass actor.
4. Ledger history rule: block force pushes and deletion in a separate ruleset where the App has no bypass.
5. Tag creation/update/deletion: owner/admin only.

Rulesets aggregate. The separate ledger history ruleset must continue to apply even though the App bypasses the ledger update rule.

## 4. Least-privilege application split

### Publisher App (one content writer)

- Repository selection: only this repository.
- Permissions: Metadata read, Contents read/write.
- Explicitly absent: Workflows write, Actions write, Administration, Secrets, Deployments, OIDC, Packages, Pull Requests.
- Bypass: ledger update ruleset only; never main.
- Cannot create branches; cannot force-push or delete ledger branch.
- Installation token scoped to this repository and minimum permissions; token TTL is one hour.

GitHub documents `workflows` as a separate permission for modifying workflow files. It must remain absent from the Publisher App.

### Dispatcher App (trigger only, not a writer)

- Permissions: Metadata read + Actions write.
- No Contents, Workflows, Administration or Secrets permission.
- May dispatch the trusted publisher workflow; cannot write repository content.
- Its private key would be held only by the future Cloudflare Worker secret store after owner approval.

This separates scheduling from publication: the dispatcher can request a run but cannot write state; the publisher can write the ledger but cannot change workflows or main.

Sources:
- https://docs.github.com/en/enterprise-cloud@latest/rest/apps/apps
- https://docs.github.com/en/enterprise-cloud@latest/actions/reference/workflows-and-actions/workflow-syntax

## 5. Trusted workflow boundary

- Publisher workflow source is `main` only.
- Publisher job receives the Publisher App key only after owner-controlled secret placement.
- It writes to `evidence-ledger`, then fetches back the exact commit and validates all object SHA-256 values, manifest digest, schema and CAS ancestry.
- Read-only CI is loaded from `main`, fetches the exact ledger commit as data, and never checks out or executes ledger-branch code.
- Scheduled read-only audit runs from main. The Dispatcher App can only invoke workflow_dispatch; it has no Contents permission.
- Public source text remains untrusted evidence, never instructions.

## 6. Current state and migration risk

Observed main branch state:
- Only branch: `main`.
- `state/manifest.v1.json`: generation 0, zero objects, no active writer lease.
- No evidence/snapshot directory exists.
- State README and manifest currently describe `main`; code and schemas hard-lock state to main.

Therefore, the initial ledger branch can be a new data-only branch with an empty generation-0 manifest. No content-addressed object migration is required. The old main-branch bootstrap manifest must be retired only after the new branch is created and exact fetch-back passes.

## 7. Required code-only S7-B5A work

1. Add `CANONICAL_CODE_BRANCH=main` and `CANONICAL_STATE_BRANCH=evidence-ledger`.
2. Parameterize/lock `GitHubGitDataStore` to the state branch, with no fallback to main.
3. Update `state_manifest`, `writer_lease` and `run_state` branch/namespace contracts; task and source-code branch remains main.
4. Update mission registry, isolation policy, S5 checkpoint policy and publisher policy.
5. Add FakeTransport tests proving state reads/writes target only evidence-ledger and never main; test stale-head, CAS, ambiguous-response and exact fetch-back on that branch.
6. Add an empty-ledger bootstrap/migration dry-run. Do not create the branch or perform a live migration in this phase.

## 8. Owner approval and zero-cost boundary

Exact owner approval is required before:
- Creating `evidence-ledger`.
- Creating/editing branch rulesets.
- Registering/installing Publisher or Dispatcher Apps.
- Storing any private key or secret.
- Enabling publisher workflow or Cloudflare dispatcher.
- Performing live Git Data writes or deployment.

No settings, branches, Apps, secrets, credentials, billing or deployments were changed in this increment. S6-B2 egress remains HOLD; S8 is undeployed; S9 is not started. Spend ₹0; settled revenue evidence ₹0.

## 9. Next action

Proceed with S7-B5A branch-aware state-store and schema code plus FakeTransport tests only. The branch migration remains an owner-controlled action.


## 10. Exact-head policy validation

The design/policy commit `b328b7d84370df1eeb8a476e157ddc82242c1e96` passed read-only GitHub Actions run [45934801142](https://github.com/manish91082-coder/zero-cost-internet-revenue-automation/actions/runs/45934801142), job `140295416686`: **228 passed, 1 expected skip, 9 subtests passed, 0 failures**; 47 hash-locked packages; Python 3.12.3; LangGraph 1.2.22; pip check clean; 3 LangGraph runtime tests passed. The exact commit and three changed artifacts were fetched back with matching Git blob SHAs. This does not validate or enable any live branch/ruleset/App permission.
