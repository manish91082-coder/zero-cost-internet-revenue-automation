# Phase S7-B — Single-writer metadata evidence publisher core

**तिथि:** 2026-11-22  
**Project:** ZCIRA-2026-11-13  
**स्थिति:** CORE IMPLEMENTED / GITHUB ACTIONS ACCEPTANCE PENDING / PUBLISHER NOT DEPLOYED

## 1. इस increment का उद्देश्य

S6-D के LangGraph source-worker proposals को canonical GitHub state ledger में केवल एक cooperative evidence_publisher writer के माध्यम से persist करने का bounded, idempotent और content-addressed core बनाना। यह increment repository-only engineering है। कोई publisher workflow, write token, cloud service या live source execution सक्रिय नहीं किया गया।

## 2. Implemented artifacts

- src/zcira_control/evidence_publisher.py
  - Versioned source-worker proposal, snapshot envelope, task, evidence और run-state schema validation।
  - Exact source-domain allowlist, publisher name, priority और source-task provenance matching।
  - Original task URL hash और query/fragment-stripped canonical snapshot URL consistency।
  - Raw-body, secret और sensitive-key rejection।
  - Snapshot और worker-proposal canonical JSON SHA-256 path generation।
  - Source capture task को केवल publication के बाद COMPLETED करना।
  - अलग adversarial_auditor evidence-review task को QUEUED करना।
  - Run state को PARTIAL रखना; original started_at preserve करना; reviewer PENDING, commercial gate UNKNOWN।
  - अधिकतम दो proposals प्रति atomic transaction।
  - Exact duplicate retry पर evidence duplication रोकना; conflicting task/idempotency reuse reject करना।
- src/zcira_control/github_state.py
  - केवल state manifest, state objects, metadata snapshots और worker proposals के exact content-addressed JSON paths स्वीकार।
  - हर content-addressed path का SHA-256 content से मिलान।
- src/zcira_control/state_repository.py
  - commit_and_release(..., extra_files=...) से evidence files, state objects, run/task updates, manifest और writer-lease release को एक Git commit में शामिल करना।
  - प्रत्येक file का exact commit-ref fetch-back verification।
  - Evidence extra files के लिए 64 KiB per-file और 256 KiB per-transaction bound।
- config/s7b_publisher_policy.v1.json
  - Fail-closed publisher policy और deployment/write-permission flags।
- config/mission_registry.v1.json
  - केवल evidence/snapshots/sha256/*.json और evidence/proposals/sha256/*.json paths की allowlisting।
- .github/workflows/zcira-readonly-validation.yml
  - इन content-addressed evidence paths में बदलाव पर read-only CI trigger।

## 3. Atomic publication transaction

एक सफल synthetic publication transaction में निम्न सभी सामग्री एक ही expected-parent, non-force Git commit में जाती है:

1. Metadata-only snapshot envelope: evidence/snapshots/sha256/<sha256>.json
2. Complete worker proposal: evidence/proposals/sha256/<sha256>.json
3. source_snapshot state object
4. evidence state object
5. Source task का publication-complete state
6. Independent evidence-review task, status QUEUED
7. Run state, status PARTIAL
8. Released writer lease object
9. Updated state manifest

StateRepository commit के बाद प्रत्येक changed file को exact commit SHA से पढ़कर byte-for-byte verify करता है। Branch-head mismatch या non-fast-forward race पर publication reject होता है; force push नहीं होता।

## 4. Idempotency और review boundary

- Task ID तथा task idempotency key अनिवार्य।
- समान task, समान immutable snapshot/evidence और समान proposal का retry evidence दोबारा नहीं बनाता; writer lease release होता है।
- समान task ID पर अलग idempotency key या अलग immutable content reject होता है।
- Source capture task का COMPLETED अर्थ केवल capture-and-persistence task complete है; यह buyer demand, payout, licensing, economics या commercial approval नहीं है।
- Publisher नया review task queue करता है। Reviewer verdict PENDING और commercial gate UNKNOWN ही रहते हैं।
- Publisher किसी commercial gate को PASS नहीं कर सकता।

## 5. नए tests

- tests/test_github_state.py: 2 नए exact evidence-path और SHA-256 tests।
- tests/test_state_persistence.py: 2 नए atomic extra-file persistence और rejection tests।
- tests/test_evidence_publisher.py: 7 publisher tests, जिनमें atomic publication, fetch-back, review-task queueing, run-clock preservation, duplicate retry, conflicting idempotency, gate-promotion rejection, raw-body rejection, source allowlist और stale lease cases शामिल हैं।

कुल 11 नए tests commit किए गए। पिछले verified baseline GitHub Actions run 44860401524 में 180 passed, 1 expected skip और 6 subtests थे। यदि सभी नए tests pass हों तो अपेक्षित full-suite संख्या 191 passed होगी; यह वर्तमान run का observed result नहीं है।

## 6. CI observation status

- Latest code/config commits push-triggered read-only validation workflow की path filters में आते हैं।
- GitHub combined commit status endpoint ने latest checkpoint के लिए कोई legacy status context नहीं लौटाया।
- उपलब्ध fetch_commit_workflow_runs connector केवल PR-triggered runs लौटाता है; इस push-triggered run का run ID/job result इस read surface से अभी independently प्राप्त नहीं हुआ।
- इसलिए S7-B acceptance PENDING OBSERVATION है। 191 tests PASS होने का दावा नहीं किया जा रहा।
- अगला कदम: push-triggered S7-A run को GitHub Actions dashboard/API से exact run ID और job logs सहित verify करना; failure होने पर root-cause fix करके नया full hash-locked run प्राप्त करना।

## 7. अभी भी निषिद्ध / अनुपस्थित

- Publisher GitHub Actions workflow: नहीं बनाया/सक्रिय नहीं।
- contents:write token या secret: नहीं जोड़ा।
- Branch protection/ruleset: verified नहीं।
- Actual GitHub evidence publication/fetch-back: नहीं हुआ; fetch-back अभी synthetic store tests और code path में है।
- Live source network: बंद; S6-B2 egress audit HOLD।
- Cloudflare Worker/Cron/D1: deployed नहीं।
- LangGraph durable checkpointer: अभी नहीं।
- कोई external action, account, KYC, legal terms, billing, commercial build/listing या spend नहीं।

## 8. वित्तीय और mission invariants

- Spend cap: ₹0; spend incurred: ₹0।
- Settled revenue evidence: ₹0।
- Paid fallback/provider routes: disabled।
- Maximum parallel read-only research workers: 2।
- Single writer role: evidence_publisher।
- P1/P2/P3/P4/P5/B/M क्रम और Category #24=B अपरिवर्तित।
- पाँच commercial gates में UNKNOWN कभी PASS नहीं है।
- Commercial execution: HOLD।

## 9. अगला gate

1. Exact push-triggered S7-A run result और logs प्राप्त करें।
2. 11 नए tests सहित full hash-locked suite PASS कराएँ।
3. GitHub atomic commit path के fetch-back और CAS race tests का audit करें।
4. Branch protection/ruleset की वास्तविक स्थिति independently verify करें।
5. उसके बाद भी publisher workflow/contents-write activation अलग owner-approval gate रहेगा। कोई cloud deployment या live source execution इस report से अधिकृत नहीं है।
