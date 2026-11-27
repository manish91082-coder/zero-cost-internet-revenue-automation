# Phase S7-B4 — publisher isolation revalidation and branch-separated ledger candidate

**तिथि:** 2026-11-27  
**स्थिति:** PUBLISHER CORE CI PASS / LIVE PUBLISHER HOLD / ISOLATION REDESIGN REQUIRED

## 1. Exact observed repository state

Canonical repository: manish91082-coder/zero-cost-internet-revenue-automation  
Observed main HEAD: fc5ab96a2cdcf02c7050b8a2ba5f11afe57d31ac

- Branch metadata: protected=false.
- Repository rulesets endpoint: empty array.
- Detailed branch-protection endpoint: HTTP 403 to the connected integration; this is an access limitation, not a protection pass.
- S7-A workflow: workflow-level and job-level permissions are contents:read.
- Publisher policy: publisher workflow disabled; GitHub contents write permission disabled; live Git Data API write not tested; production evidence publication not performed.
- No App, private key, repository secret, write token, branch ruleset or publisher workflow was created or enabled in this increment.

Latest exact-head full suite:
- Run 45934000236 / job 140292879898: SUCCESS.
- Python 3.12.3; 47 hash-locked packages; pip check clean.
- 228 passed, 1 expected skip, 9 subtests passed; 0 failures.
- This validates FakeTransport and deterministic publisher core only, not live permissions or real Git Data writes.

## 2. GitHub Free ruleset capability recheck

Official GitHub documentation states:
- Branch/tag rulesets are available on public repositories with GitHub Free.
- Repository admin or a custom role with edit-repository-rules permission is required to create/edit rulesets.
- Push rulesets are available for GitHub Team in internal/private repositories.
- The "Restrict file paths" rule is a push-rule feature.

Sources:
- https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets
- https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/creating-rulesets-for-a-repository

## 3. Corrective design finding

The earlier S7-B2 candidate proposed a dedicated publisher GitHub App as a bypass actor on the main branch while relying on application-level path allowlists to keep it away from source/workflow/config files.

That is not a mechanically complete isolation boundary:
- A ruleset bypass actor bypasses rules in that ruleset.
- A GitHub App Contents write token is repository-wide, not path-scoped.
- Public GitHub Free cannot be assumed to use push-rule path restrictions.
- Therefore a compromised App key could write code/workflow/config paths on main even if the normal publisher code never does so.

Decision: do not activate the single-main-branch App-bypass design.

## 4. Safer candidate: separate code and evidence-ledger branches

Candidate only; not implemented or activated.

| Branch | Role | Update authority |
|---|---|---|
| main | Trusted code, schemas, workflows, policy | Owner/admin; publisher App is NOT a bypass actor |
| evidence-ledger | Manifest, state objects, source snapshots, proposals, evidence metadata | Dedicated publisher App only |

Candidate controls:
1. Owner creates evidence-ledger once; publisher App cannot create arbitrary branches.
2. A main ruleset blocks direct publisher updates to code/config/workflow branch.
3. An evidence-ledger ruleset restricts updates to the dedicated App; block force pushes and deletion using separately layered rules where the App is not a bypass actor.
4. The trusted publisher workflow is loaded from main only and receives the App credential only in its publisher job/environment.
5. Ledger contents are data-only and treated as untrusted input; no code or workflow from the ledger branch is executed.
6. Read-only CI fetches trusted code from main and the exact ledger commit as data, validates schema/hash/provenance, and never checks out ledger code.
7. GitHub App permissions remain Metadata read + Contents read/write only; no Administration, Actions, Secrets, Workflows, Packages, Deployments or OIDC permissions.
8. The App is never a bypass actor on main.

### Required code work before any activation

Current code hard-locks the state store and manifest to main:
- `GitHubGitDataStore.__init__` rejects any branch other than `CANONICAL_BRANCH`.
- `validate_manifest` requires `branch=main`.
- State-manifest schema and policy fixtures also lock main.

S7-B5 must introduce separate code-branch and state-ledger-branch constants, a strict allowed state branch, versioned manifest migration tests, and FakeTransport-only branch isolation tests. No live branch migration is permitted in that engineering phase.

## 5. Owner and spend boundary

Branch creation, ruleset configuration, GitHub App creation/installation, secret placement and live publisher activation remain exact-owner approval gates. No settings, branch, credential, token, account, billing or deployment changes were made.

S6-B2 egress remains HOLD. S8 Cloudflare remains undeployed. S9 unattended pilot remains not started. Spend ₹0; settled revenue evidence ₹0.

## 6. Next action

Proceed with S7-B5 branch-separated ledger adapter design and FakeTransport tests only. Preserve main as trusted code, keep publisher disabled, and do not create the evidence-ledger branch or configure rulesets until the owner-controlled setup is explicitly approved.
