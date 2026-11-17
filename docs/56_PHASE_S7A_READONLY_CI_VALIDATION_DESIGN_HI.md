# Phase S7-A — Read-only GitHub-hosted validation design (2026-11-17)

## Executive decision

**S7-A DESIGN COMPLETE / WORKFLOW NOT CREATED / NO RUNNER EXECUTED.**

S5 के real LangGraph package integration gate को सुरक्षित तरीके से पूरा करने के लिए S7 का छोटा, read-only हिस्सा आगे लाया जा रहा है। यह phase split S5→S6 dependency deadlock को हल करता है:

- S5 को actual `langgraph==1.2.22` package पर compile/invoke/pause/resume smoke test चाहिए।
- मौजूदा S5 phase boundary में GitHub Actions workflow बनाना निषिद्ध था।
- S6 read-only agents को S5 integration PASS होने तक रोकना है।
- S7 पहला phase है जिसमें CI/workflow allowed है।

इसलिए S7 को दो हिस्सों में विभाजित किया गया है:

- **S7-A:** केवल read-only validation workflow; कोई secret, repository write, publisher permission, deployment या cloud service नहीं।
- **S7-B:** S6 के बाद publisher-only write path, protected branch और mechanical single-writer enforcement।

यह design decision है। इस run में `.github/workflows/**` file नहीं बनाई गई।

## 1. Machine-readable contract

नया artifact: `config/s7a_readonly_ci_contract.v1.json`.

इसमें planned workflow path, trigger allowlist, standard runner, timeout, concurrency, minimal token permissions, no-secrets, no-artifacts/no-cache, dependency lock bootstrap और test list दर्ज हैं।

Contract blob SHA fetch-back के बाद continuity checkpoint में दर्ज होगा।

## 2. Runner and cost eligibility

GitHub की official billing documentation कहती है कि public repositories में standard GitHub-hosted runners का usage free है; larger runners charged होते हैं। इसलिए S7-A केवल standard `ubuntu-24.04` runner पर चलेगा, larger runner नहीं। कोई self-hosted runner नहीं।

S7-A में artifact upload और cache दोनों disabled रहेंगे। इससे artifact/cache storage billing path नहीं खुलेगा। कोई billing account activation, payment method या paid fallback नहीं।

Official references:
- GitHub Actions billing: https://docs.github.com/en/actions/concepts/billing-and-usage
- GitHub Actions billing details: https://docs.github.com/en/billing/concepts/product-billing/github-actions

## 3. Workflow security contract

Planned workflow: `.github/workflows/zcira-readonly-validation.yml`.

| Control | Locked value |
|---|---|
| Trigger | push to main + manual workflow_dispatch |
| Pull request | disabled |
| pull_request_target | disabled |
| Schedule | disabled in S7-A |
| Runner | ubuntu-24.04 standard GitHub-hosted |
| Timeout | 20 minutes |
| Concurrency | one running + one pending per branch group |
| cancel-in-progress | false |
| GITHUB_TOKEN | contents: read only; all unspecified permissions none |
| Secrets | none |
| OIDC/id-token | none |
| Repository writes | false |
| Artifacts/cache | disabled |
| Cloud deployment | false |

GitHub documents that specifying individual `permissions` makes unspecified token permissions `none`. Therefore the workflow will explicitly use only `contents: read`. It will not use `pull_request_target`, which GitHub documents as receiving read/write repository permissions by default.

GitHub concurrency permits at most one running and one pending job per group. A newer pending job can replace an older pending job; `cancel-in-progress: false` preserves the active validation run.

Official reference: https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax

No third-party Actions are required by the design. The runner can fetch the exact public repository commit using built-in Git and `GITHUB_SHA`; no write token is required.

## 4. Dependency lock bootstrap

Current repository inputs are not yet sufficient for secure CI:
- `requirements-test.txt` contains version ranges without hashes.
- `config/requirements-langgraph.txt` pins LangGraph 1.2.22 and its wheel hash, but does not yet lock the complete transitive dependency set.
- PyPI reports no provenance attestation for the LangGraph 1.2.22 release, so the published wheel SHA-256 must be enforced and transitive dependencies must be hash-locked.

Planned two-step process:

**A. Lock generation, no package installation**
1. Use Python 3.12 on the public runner.
2. Run pip resolution with `--dry-run --report`, `--ignore-installed` and `--only-binary=:all:`.
3. Parse the report with a standard-library script into a deterministic lock containing exact normalized names, versions and SHA-256 hashes.
4. Fail if any dependency has no binary wheel or no SHA-256.
5. Print the candidate lock in the job log/summary. Do not upload an artifact and do not commit from the workflow.

**B. Reproducible test run after lock is reviewed and committed**
1. Commit `config/requirements-ci-linux-py312.lock` through the canonical single writer.
2. Install only with `--require-hashes --only-binary=:all: --no-cache-dir`.
3. Run all deterministic tests, all 11 schema contracts, the 3 run-clock regression tests and the 3 real LangGraph integration tests.
4. No artifact upload, no cache, no repository write and no secrets.

Planned lock renderer: `scripts/render_pip_lock.py`. It is not created yet.

## 5. S7-A acceptance criteria

- Public standard runner only; no self-hosted/laptop/local runtime dependency.
- Workflow token is contents-read-only; no other permission.
- No secrets or OIDC.
- No fork PR trigger, no pull_request_target, no schedule.
- Concurrency group prevents parallel validation jobs.
- No artifacts/cache and no repository write.
- Dependency lock covers every transitive dependency with SHA-256.
- Full pytest and Draft 2020-12 validation pass.
- Actual LangGraph 1.2.22 StateGraph compile/invoke/pause/resume tests pass.
- Run logs confirm zero external actions and no paid route.

## 6. Phase sequence after the split

1. S5 adapter and mocked contract tests remain complete at the last verified baseline of 96 tests.
2. S7-A read-only validation workflow is the next implementation slice.
3. S5 real LangGraph package integration must PASS.
4. S6 read-only evidence workers can then begin.
5. S7-B publisher-only write enforcement and protected publication path follows S6.
6. S8 Cloudflare Worker/Cron/D1 remains separately gated by exact current no-billing eligibility and owner approval.
7. S9 seven-day read-only unattended pilot follows S8 acceptance tests.

## 7. Current status and non-actions

- S7-A contract: design only.
- Workflow file: not created.
- GitHub Actions runs: no S7-A run exists.
- LangGraph package installation: blocked in the available validation container by DNS/package-index unavailability.
- S5 real integration tests: committed, not executed.
- S6: blocked on S5 real integration PASS.
- No Cloudflare account/Worker/Cron/D1, no OAuth, no KYC, no terms acceptance, no billing/payment method, no deployment, no outreach/submission, no product build/list/publication.
- Spend ₹0; settled revenue evidence ₹0; commercial HOLD.

## 8. Decision

Proceed with S7-A only as a read-only validation layer. Do not combine it with the publisher. Do not grant write permissions to the test workflow. The workflow must never become an alternate repository writer. The only future writer remains the S7-B `evidence_publisher` role.
