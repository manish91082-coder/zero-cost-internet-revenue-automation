# Phase S7-B3 — GitHub Git Data transport content-integrity और ambiguous ref-update recovery

**तिथि:** 2026-11-24  
**Project:** ZCIRA-2026-11-13  
**स्थिति:** IMPLEMENTED / FAKE-TRANSPORT GITHUB ACTIONS CI PASS / NOT DEPLOYED

## 1. Preflight और canonical scope

- Canonical repository: `manish91082-coder/zero-cost-internet-revenue-automation`; branch: `main`.
- इस increment से पहले `PROJECT_CONTINUITY.md`, S2-B architecture decision (`docs/45`), research swarm roster, S7-B publisher policy, S7-B2 isolation design (`docs/68`), S7-B ambiguous-commit report (`docs/69`) और A2.4-B/C/A2.5 reports पुनः पढ़े गए।
- Controlling Library source archive: `02_complete-research-hi.md`, version 1; SHA-256 `c61be12a55385d0780a6a5bdf45f2fc22086be9edf6bbba96e78cfb0726d1e5`; embedded destination section SHA-256 `7e45078990d99d14e34a26befb3bde2b8260fc53f35c6000fbe20fb741a36a24`.
- A2.4-B: छह batches में 219/219 category IDs; missing/extra/duplicate IDs शून्य।
- A2.4-C: 8/8 shared lists, 168/168 list rows, 213 explicit category-to-list edges।
- A2.5: 3,482 original source occurrences; 315 repeated-name groups, 283 same-name/same-host candidate groups, 32 ambiguous groups; identity merges अधिकृत नहीं। Unique-platform count स्थापित नहीं।
- P1/P2/P3/P4/P5/B/M क्रम और Category #24=B अपरिवर्तित।

## 2. वास्तविक defect और सुधार

पूर्व `GitHubGitDataStore.read_file()` GitHub Contents API के base64 payload को `validate=False` से decode करता था और response का Git blob SHA जाँचता नहीं था। इससे malformed base64 के कुछ गैर-alphabet characters चुपचाप ignore हो सकते थे और transport response integrity अधूरी थी।

### Read path

अब:
1. Content field का type अनिवार्य रूप से string है।
2. केवल ASCII space/tab/CR/LF हटाए जाते हैं ताकि GitHub का line-wrapped base64 स्वीकार हो।
3. `base64.b64decode(..., validate=True)` हर अन्य गैर-base64 character reject करता है।
4. API response में valid 40-character Git blob SHA अनिवार्य है।
5. Raw decoded bytes से Git object SHA-1 पुनर्गणित होता है: `SHA1("blob " + byte_length + NUL + raw_bytes)`।
6. Calculated और returned Git blob SHA समान होना चाहिए।
7. UTF-8 decode अलग से verify होता है।

यह Git object integrity check है। Evidence content-addressed paths का project-level SHA-256 contract इससे अलग और अपरिवर्तित है।

### Write path

- `POST /git/blobs` के बाद returned blob SHA को locally calculated Git blob SHA से मिलाया जाता है।
- Mismatch पर tree/commit/ref publication आगे नहीं बढ़ती।

### Ambiguous ref-update recovery

`PATCH /git/refs/heads/main` पर network status 0 या HTTP 5xx के बाद blind retry नहीं होता। Store canonical branch head को read करता है:

| Observed main head | निर्णय |
|---|---|
| Proposed commit SHA | Update लागू हुआ; normal fetch-back verification जारी |
| Original expected parent SHA | Update लागू नहीं हुआ; मूल error लौटाएँ, automatic retry नहीं |
| कोई अन्य SHA | `BranchHeadConflict`; fail closed और reconcile/refetch आवश्यक |

409/422 non-fast-forward conflicts पहले की तरह reject होते हैं। Force push निषिद्ध है।

## 3. छह नए regression tests

`tests/test_github_state.py` में कुल 15 test methods हैं। इस increment में छह नए tests जोड़े गए:

1. Wrapped base64 स्वीकार हो और Git blob SHA verify हो।
2. Invalid base64 reject हो, silently ignored न हो।
3. Git blob SHA mismatch reject हो।
4. Blob-creation API का गलत SHA reject हो।
5. Ref update server पर लागू होने के बाद response खो जाए तो canonical head से applied state पहचानी जाए।
6. Ref update server तक लागू होने से पहले response खो जाए तो old head सुरक्षित रहे और original error लौटे।

सभी छह tests `FakeTransport` पर deterministic fault injection हैं। कोई production Git Data API write नहीं हुआ।

## 4. GitHub Actions validation — observed PASS

- Read-integrity code/test commit: `666a556bc27ca49b6669fdf3b9da54a6a117d60a`; run [45318339096](https://github.com/manish91082-coder/zero-cost-internet-revenue-automation/actions/runs/45318339096): SUCCESS।
- Write-blob SHA और ambiguous ref-update recovery code/test commit: `305803d97ce962e48c8a85038fabeee47bef5642`; run [45318412657](https://github.com/manish91082-coder/zero-cost-internet-revenue-automation/actions/runs/45318412657): SUCCESS।
- Final full suite: **200 passed, 1 expected skip, 6 subtests passed**।
- Runner: `ubuntu-24.04`; Python `3.12.3`; 47 SHA-256 hash-locked packages; `pip check`: no broken requirements; real LangGraph integration: 3 passed।
- Expected skip: LangGraph-missing fallback test, क्योंकि इस run में LangGraph installed था।

## 5. Repository governance और operational boundaries

वर्तमान live repository read:
- `GET /branches/main`: `protected=false`, `protection.enabled=false`।
- Repository rulesets: empty array।
- Dedicated branch-protection endpoint: connected integration से 403, इसलिए उस endpoint का detailed protection object उपलब्ध नहीं।
- S7-A workflow: केवल `contents:read`; publisher workflow, write token, App key और OIDC मौजूद/सक्रिय नहीं।

इसलिए writer lease अभी cooperative coordination है, mechanical permission boundary नहीं। कोई live publisher credential या branch ruleset सक्रिय नहीं किया गया।

## 6. Current status

- S5 LangGraph synthetic integration: PASS।
- S6-A/C/D deterministic worker/snapshot/graph tests: recorded PASS।
- S6-B2 live egress audit: HOLD; DNS pinning और provider/runner egress controls independently audited नहीं; live source requests 0।
- S7-A read-only CI: PASS।
- S7-B fake Git Data transport content integrity और ambiguous ref-update recovery: PASS।
- S7-B live Git Data API write/fetch-back: NOT TESTED।
- Publisher-only mechanical isolation: NOT ENABLED।
- S8 Cloudflare Worker/Cron/D1: NOT DEPLOYED।
- S9 unattended pilot: NOT STARTED।
- Spend ₹0; settled revenue evidence ₹0; commercial execution HOLD।

## 7. Next actions

1. S7-B live write remains blocked until exact owner-approved publisher identity, branch protection/ruleset and credential isolation exist; no production evidence write as a first integration test.
2. Continue S6-B2 zero-cost egress feasibility without enabling live source fetching or performing unapproved security tests.
3. Design durable LangGraph checkpoint serialization to canonical Git state; runner-local SQLite/disk is never durable.
4. Only after these gates and exact owner approvals, proceed to S8 Cloudflare eligibility and failover acceptance; then S9 limited read-only pilot.


## 8. Final policy/roster checkpoint validation

- Publisher policy, swarm roster और continuity checkpoint का atomic metadata commit: `a2c3c5d656975c0077d5bc4ec8409cf6f8da8bfc`.
- उसी exact metadata/config checkpoint पर GitHub Actions run [45318600997](https://github.com/manish91082-coder/zero-cost-internet-revenue-automation/actions/runs/45318600997): SUCCESS।
- Run 63: **200 passed, 1 expected skip, 6 subtests passed**; pip check PASS; LangGraph integration 3 PASS।
- इसलिए code/test acceptance run 62 और उसके बाद का policy/roster checkpoint validation run 63 दोनों observed PASS हैं। कोई live Git Data API write या production publisher activation नहीं हुई।
