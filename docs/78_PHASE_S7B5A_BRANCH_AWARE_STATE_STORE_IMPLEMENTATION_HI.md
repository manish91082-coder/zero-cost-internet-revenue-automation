# Phase S7-B5A - Branch-aware state store implementation and CI acceptance

तारीख: 28 नवम्बर 2026  
Project: ZCIRA-2026-11-13  
Canonical repository: manish91082-coder/zero-cost-internet-revenue-automation

## 1. Executive decision

S7-B5A का code-only implementation और exact-head GitHub-hosted CI acceptance PASS हुआ। Trusted code branch और mutable data ledger के बीच software-enforced separation मौजूद है:

- main: trusted source code, schemas, policies, tests और workflows.
- evidence-ledger: canonical state manifest, writer leases, run state, immutable LangGraph checkpoints और metadata-only evidence.

यह branch अभी बनाया नहीं गया है। Repository configuration, branch rulesets, GitHub Apps, secrets, publisher workflow activation और live Git Data writes अभी भी HOLD हैं। इसे production publisher या deployed ledger नहीं कहा जा सकता।

## 2. Preflight evidence

इस increment से पहले निम्न canonical records दोबारा पढ़े गए:

- PROJECT_CONTINUITY.md
- docs/45 architecture decision record
- docs/42 roster contract और config/research_swarm_roster.v1.json
- docs/74 से docs/77 तक के नवीनतम S5/S6/S7 reports
- controlling Library source archive 02_complete-research-hi.md, version 1

Archive SHA-256: c61be12a55385d0780a6a5bdf45f2fc22086be9edf6bbba96e78cfb0726d1e5.

Source reconciliation और locked mission order में कोई बदलाव नहीं:
- A2.4-B: 219/219 category IDs, six explicit batches.
- A2.4-C: 8/8 shared lists, 168/168 entries, 213 explicit cross-reference edges.
- A2.5: 3,482 source occurrence slots, 315 repeated-name groups, 32 ambiguous identity groups; कोई identity merge नहीं.
- Priority order P1/P2/P3/P4/P5/B/M और Category #24=B यथावत.

## 3. Implemented code boundary

### 3.1 Branch constants

src/zcira_control/policy.py अब स्पष्ट रूप से अलग करता है:
- CANONICAL_CODE_BRANCH = main
- CANONICAL_STATE_BRANCH = evidence-ledger
- CANONICAL_BRANCH केवल backward-compatible code-branch alias है.
- State namespace zcira-2026-11-13/evidence-ledger.
- Legacy namespace केवल generation-zero migration validation के लिए zcira-2026-11-13/main.

Task definitions, source code और graph execution envelope main पर ही रहते हैं। State manifest, resource leases और run-state records evidence-ledger पर pinned हैं।

### 3.2 GitHubGitDataStore branch lock

GitHubGitDataStore का default branch evidence-ledger है। Explicit main या कोई अन्य branch constructor में reject होता है। State path allowlist केवल manifest, content-addressed state objects और metadata-only evidence snapshots/proposals को स्वीकार करती है।

Symbolic main read अस्वीकार है। Historical commit SHA को भी blind trust नहीं किया जाता। GET /compare/{commit_sha}...evidence-ledger से पुष्टि होती है कि commit current ledger head का ancestor है। केवल ahead और identical स्वीकार होते हैं; behind, diverged, unknown response और API error fail-closed हैं। Cache key exact (commit_sha, observed_head_sha) है, ताकि branch head बदलने पर ancestry फिर जाँची जाए।

### 3.3 Durable StateRepository और LangGraph

StateRepository अब manifest और lease payload में branch=evidence-ledger लिखता है। Repository writer resource key repo-evidence-ledger-single-writer है। leases.py और queue.py भी इसी key और branch को validate करते हैं।

LangGraph adapter:
- graph/task envelope का code branch main रखता है;
- persisted run_state को evidence-ledger पर pin करता है;
- resume पर run-state branch और namespace mismatch reject करता है.

state_manifest, resource_lease, run_state और mission_registry schemas तथा fixtures अपडेट हुए। Mission registry में branch=main और state_branch=evidence-ledger दोनों अलग-अलग अनिवार्य हैं।

### 3.4 Empty legacy bootstrap

StateRepository.bootstrap_empty_ledger() जोड़ा गया। यह branch create नहीं करता और automatic रूप से invoke नहीं होता। Owner-created evidence-ledger branch पर inherited main manifest को तभी replace कर सकता है जब:
- exact legacy schema और project/repository identity match हों;
- legacy branch और namespace main वाले हों;
- generation ठीक 0 हो;
- previous commit SHA null हो;
- objects खाली हों;
- active writer lease null हो;
- kill switch false हो;
- paid provider routes false और spend cap ₹0 हो;
- canonical state digest valid हो.

नया ledger manifest parent के रूप में inherited branch head सुरक्षित रखता है। Non-empty या modified legacy state reject होता है। यह व्यवहार FakeDurableStore tests में synthetic रूप से प्रमाणित है, live branch पर नहीं।

## 4. Exact-head CI evidence

PASS

GitHub Actions run: 46103503398  
Job: 140851005008  
Commit: 5cde956e596f7533f37e11a8b4e1965d7f52f7a7

Exact workflow run:
https://github.com/manish91082-coder/zero-cost-internet-revenue-automation/actions/runs/46103503398

- Runner: ubuntu-24.04 standard GitHub-hosted.
- Python: 3.12.3.
- LangGraph: 1.2.22.
- Hash-locked packages: 47.
- pip check: PASS, no broken requirements.
- Real LangGraph runtime integration: 3 passed.
- Full suite: 240 passed, 1 skipped, 9 subtests passed.
- Git Data branch and commit-ancestry behavior: FakeTransport tests only.
- Bootstrap behavior: FakeDurableStore synthetic tests only.

पहले दो exact-head runs में test fixture mismatches मिले:
- Run 46103124196: LangGraph resume fixture में पुराना main namespace.
- Run 46103199673: दो mission contexts में state_branch missing और checkpoint-chain closure diagnostic की आवश्यकता.

Fixtures और tests ठीक किए गए। Run 46103359605 में 238 passed, 1 skipped, 9 subtests हुए। इसके बाद commit-SHA ancestry enforcement और दो अतिरिक्त FakeTransport tests जोड़े गए। अंतिम run 46103503398 exact-head पर PASS हुआ।

## 5. Fetch-back verification

Code implementation commits:
- 9880ae13e4f3a7fc573103bd13e7e6b7a5705924
- 4b33dfe0643d69a9fffbb452dd6e29b144541652
- 4807adc7222860012d7d3b883625cf2cfdd4fd73
- 5cde956e596f7533f37e11a8b4e1965d7f52f7a7

सभी बदले हुए code/schema/config/test artifacts को GitHub से दोबारा fetch करके exact blob SHA मिलाया गया। 34 unique paths के 35 fetch-back checks में mismatch नहीं मिला।

Representative blob SHAs:
- src/zcira_control/github_state.py: f701ed7cc835baab6d901cc36e7b9da6ddc88e13
- src/zcira_control/state_repository.py: ab2f2b445f2cfaa3789f718344b74152580a2feb
- src/zcira_control/policy.py: 5af09a5fdd4e6a253b2b3396216c26139074db9c
- src/zcira_control/leases.py: 71ce219ac6cfd123fc97b90ff27ee016f3bdeeaa
- src/zcira_control/langgraph_adapter.py: 530564e09937855960dca3adcb0d6b5f1d2e1078
- schemas/v1/state_manifest.schema.json: 186f3e9abe6308b7a62603f877148821f0bf12c5
- schemas/v1/resource_lease.schema.json: 177f7b700bee85083d648e526730613eb7ab084a
- schemas/v1/run_state.schema.json: cc16d06d3dfc0c79cad2c407c3d778639bd86fc2
- tests/test_github_state.py: bd35fff29768911f81cf9426a56697a53f682541
- tests/test_state_persistence.py: 5d216f2c057fad6cc05aaeb78047013e0abc7f19
- tests/test_contract_schemas.py: 844f6df2f1889eb11998937be464f42060be25a4

## 6. Actual repository and runtime status

Observed GitHub branch list contains only main, with protected=false. Rulesets endpoint returns an empty list. The branch-protection detail endpoint is not accessible to the integration (403). No evidence-ledger branch exists.

- Live Git Data API writes: 0.
- Publisher workflow enabled: false.
- Publisher/dispatcher GitHub Apps created or installed: 0.
- Secrets or credentials configured: 0.
- Cloudflare deployment: 0.
- Live source requests: 0.
- Runtime research agents: 0.
- Scheduled swarm executions: 0.
- Spend: ₹0.
- Verified settled revenue: ₹0.
- Commercial execution: HOLD; five gates have not all been proven PASS.

S6-B2 provider-managed egress remains HOLD. S8 Cloudflare heartbeat/dispatch is not deployed. S9 unattended pilot has not started.

## 7. Next sequential gate

S7-B5A code-only implementation is complete. The next step is not automatic deployment. It is owner-controlled repository setup:
1. Owner creates evidence-ledger once from the current main head.
2. Owner applies main and ledger rulesets; publisher App must never bypass main.
3. After branch exists, perform read-only exact-head bootstrap preflight and fetch-back.
4. Only after exact approval and credential-scope review may the single-writer publisher workflow perform a first ledger write.

No account creation, App installation, secret creation, billing, Cloudflare deployment, external contact, product build/listing or commercial action is authorized by this code-only increment.
