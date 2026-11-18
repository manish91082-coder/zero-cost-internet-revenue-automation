# Phase S7-A — Read-only validation workflow और hash-lock renderer implementation (2026-11-18)

## Executive status

**S7-A WORKFLOW + RENDERER IMPLEMENTED / 8 RENDERER UNIT TESTS PASS IN EPHEMERAL ENGINEERING SANDBOX / GITHUB-HOSTED RUN PENDING / FULL ACCEPTANCE NOT YET ESTABLISHED.**

यह increment केवल canonical ZCIRA repository में repository engineering है। कोई Cloudflare resource, external account, OAuth scope, billing, model provider, commercial product या publisher write credential activate नहीं किया गया।

## 1. Continuity and controlling-source verification

इस increment से पहले canonical main head e05577aa3fe2156667381010dfd000403f7bd448 verify किया गया। Parent checkpoint PROJECT_CONTINUITY.md blob 83af09266516c5d1ac302cf085174a21bbb79ff3 था।

दोबारा पढ़े गए controlling artifacts:

- docs/45_PHASE_S2B_FINAL_CLOUD_ONLY_FAILOVER_ARCHITECTURE_DECISION_HI.md, blob fe395806fd9a877dd696e21dbb7da5fed4fc1d8c.
- config/research_swarm_roster.v1.json, blob 2d6cf0c2e2f6113e4da5d362fef200e83a4e6444.
- docs/53_PHASE_S4B_DURABLE_GIT_STATE_AND_WRITER_LEASE_HI.md, blob 722db8f54715a55feb6d9352fb65063bb792fe76.
- docs/54_PHASE_S5_LANGGRAPH_ADAPTER_CONTRACT_HI.md, blob 384c625be26fef7439a5b2faa3cdc44150fcaf61.
- docs/55_PHASE_S5_RUN_CLOCK_AND_REAL_LANGGRAPH_INTEGRATION_GATE_HI.md, blob 517370b2c181a06ad7f77f87efcb5d05176f9e2d.
- docs/56_PHASE_S7A_READONLY_CI_VALIDATION_DESIGN_HI.md, blob 11a7dddab1927d6e12210636c3eff980f2820ccd.
- config/s7a_readonly_ci_contract.v1.json, parent blob 4e02968fbe8ab390e4b146b76619d375ec7830a8.
- Controlling Library source archive 02_complete-research-hi.md, version 1, 1,402,707 bytes, SHA-256 c61be12a55385d0780a6a5bdf45f2fc22086be9edf6bbba96e78cfb0726d1e5e. The canonical embedded destinations-section extraction scope was independently recomputed as 7e45078990d99d14e34a26befb3bde2b8260fc53f35c6000fbe20fb741a36a24.

A2 remains unchanged: 219 category IDs; six-batch membership; 8 shared lists / 168 entries / 213 explicit cross-reference edges; 3,482 provenance-preserved source occurrence slots. No occurrence was deleted or merged. Unique platform count remains NOT ESTABLISHED. Priority order P1/P2/P3/P4/P5/B/M and Category #24=B remain locked.

## 2. New dependency lock renderer

Created scripts/render_pip_lock.py.

It is standard-library-only and does not install packages or access the network. It converts a pip JSON install report into deterministic requirements lines after enforcing:

- exact package name/version and normalized-name uniqueness;
- SHA-256 for every selected artifact;
- HTTPS wheel URL on the PyPI distribution host files.pythonhosted.org;
- rejection of source distributions, other hosts, missing hashes and conflicting duplicate package records;
- exact match of the LangGraph 1.2.22 wheel SHA-256 against the original pinned requirements file;
- stable sorted output and a source-report SHA-256 in the generated header.

Created tests/test_render_pip_lock.py with eight cases: valid deterministic output, missing hash, unapproved host, source distribution, wrong LangGraph hash, conflicting duplicate, empty report and unpinned expected requirement.

Development validation: 8/8 tests passed in an isolated assistant engineering container using the standard-library unittest runner. This was not an owner laptop, not a project runtime, not GitHub Actions and not the full test suite.

## 3. Important pip hash-mode defect prevented

The existing config/requirements-langgraph.txt contains a direct --hash option for LangGraph, while requirements-test.txt still uses version ranges. Pip's hash-checking mode is global to a requirements installation; combining those files directly in the candidate resolver would require every test dependency to be exact-pinned and hashed before a lock exists.

The bootstrap workflow therefore:

1. Makes a temporary copy of the LangGraph requirements file with only the direct --hash option removed.
2. Runs pip --dry-run --report --ignore-installed --only-binary=:all:; no package installation occurs.
3. Feeds the resulting report to the renderer.
4. The renderer checks the resolved LangGraph 1.2.22 wheel hash against the original, unchanged hash-pinned file.

This avoids weakening the final lock: once the candidate is reviewed and committed, installation uses --require-hashes for every package.

## 4. Read-only GitHub Actions workflow created

Created .github/workflows/zcira-readonly-validation.yml.

Security and cost controls:

| Control | Implemented value |
|---|---|
| Trigger | push to main; manual workflow_dispatch |
| Schedule / PR / pull_request_target | disabled |
| Runner | ubuntu-24.04 standard GitHub-hosted |
| Permissions | contents: read only; unspecified permissions none |
| Checkout | unauthenticated public git fetch of exact triggering SHA; no checkout action |
| Secrets / OIDC | none |
| Third-party Actions | none |
| Repository write / publisher token | none |
| Artifacts / cache | disabled |
| Cloud deployment | none |
| Timeout | 20 minutes |
| Concurrency | one running and one pending per ref; active job not cancelled |

The workflow's only external network use is the unauthenticated public source fetch from GitHub and public PyPI package-index/wheel retrieval. No model endpoint, external API, account, paid service or customer data is contacted.

### Two fail-closed execution modes

If the reviewed hash lock is absent: run the eight renderer unit tests, resolve a candidate lock in pip dry-run mode, validate the pinned LangGraph wheel hash and print the candidate in the workflow log/step summary. Do not install packages, do not run full pytest, and do not commit anything automatically. Result label: BOOTSTRAP_ONLY_NOT_ACCEPTANCE.

If the reviewed lock exists: install only with --require-hashes --only-binary=:all:, run pip check, then run the full pytest suite. The three real LangGraph integration tests will be active because the pinned package is installed. The workflow still has no repository write permission.

The workflow does not run on a schedule. This is a bounded validation path, not a 24x7 swarm scheduler.

## 5. Actual status at checkpoint creation

- Renderer: created; 8 unit tests pass in isolated engineering sandbox.
- Workflow file: created, but the first GitHub-hosted run has not yet been verified.
- Candidate dependency lock: not generated/committed yet.
- Full pytest: not executed by this workflow yet.
- Historical full-suite baseline: 96 passed, before the three new run-clock tests, three real-package tests and eight renderer tests. Do not report 110 as passing.
- Real LangGraph 1.2.22 integration: pending.
- S6 evidence workers: blocked until actual LangGraph integration PASS.
- S7-B publisher-only enforcement: not started.
- Cloudflare Worker/Cron/D1: not deployed.
- Durable state: generation 0, zero objects, no active lease; no live queue or agent.

## 6. Mission and financial invariants

- P1/P2/P3/P4/P5/B/M priority order unchanged; Category #24 remains B.
- Maximum two parallel read-only research workers; one publisher role.
- Paid provider routes and trial-credit dependencies remain disabled.
- Spend authorized/incurred: ₹0.
- Settled revenue evidenced: ₹0.
- No accounts, KYC, legal acceptance, OAuth, billing/payment method, cloud service deployment, outreach, submission, product build, publication or wallet action.
- All five commercial gates remain mandatory; UNKNOWN is not PASS; commercial execution HOLD.

## 7. Next exact actions

1. Verify the new commit and fetch-back blobs.
2. Inspect the first push-triggered S7-A run. If it is bootstrap-only, review the candidate lock from the job log and commit it only after every package/version/hash/host passes review.
3. Let the subsequent push trigger the hash-locked full test suite.
4. Proceed to S6 only after the actual LangGraph compile/invoke/pause/resume integration passes.
