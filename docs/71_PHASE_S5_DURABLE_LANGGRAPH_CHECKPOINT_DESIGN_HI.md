# Phase S5 — Durable LangGraph checkpoint architecture और S6-B2 zero-cost egress revalidation

**तिथि:** 2026-11-25  
**Project:** ZCIRA-2026-11-13  
**स्थिति:** CHECKPOINT DESIGN LOCKED / IMPLEMENTATION PENDING / NO DEPLOYMENT

## 1. Canonical preflight

- Repository: `manish91082-coder/zero-cost-internet-revenue-automation`; branch `main`.
- Preflight main HEAD: `a55a01002ce2472faf6d4f79b67dfb357de34237`; base tree: `5fac582ca56405885bac7622f97c3726a024bfbd`.
- Re-read: `PROJECT_CONTINUITY.md`, S2-B architecture decision, S1 roster, S6-B2 egress report, S7-B2 publisher-isolation design, S7-B ambiguous-commit report और S7-B3 Git Data integrity report.
- Controlling Library archive `02_complete-research-hi.md`: 1,402,707 bytes; SHA-256 `c61be12a55385d0780a6a5bdf45f2fc22086be9edf6bbba96e78cfb0726d1e5`. Materialized bytes पर SHA-256 पुनर्गणना exact match।
- A2.4-B: 219/219 category IDs छह batches में; missing/extra/duplicate IDs शून्य।
- A2.4-C: 8/8 shared lists, 168/168 entries, 213 explicit cross-reference edges।
- A2.5: 3,482 source occurrences; 315 repeated-name groups, 283 same-name/same-host candidates, 32 ambiguous groups; कोई identity merge नहीं; unique-platform count NOT ESTABLISHED।
- P1/P2/P3/P4/P5/B/M क्रम और Category #24=B अपरिवर्तित।

## 2. Latest वास्तविक CI स्थिति

- Latest main HEAD: `a55a01002ce2472faf6d4f79b67dfb357de34237` (documentation-only child of the tested code/config head).
- Latest successful push-triggered validation run: [45318600997](https://github.com/manish91082-coder/zero-cost-internet-revenue-automation/actions/runs/45318600997).
- Tested code/config head: `a2c3c5d656975c0077d5bc4ec8409cf6f8da8bfc`.
- Job: `138191370528`; runner `ubuntu-24.04`; run conclusion `success`.
- Recorded full suite: **200 passed, 1 expected skip, 6 subtests passed**; 47 SHA-256-locked packages; `pip check` PASS; real LangGraph integration 3 PASS.
- यह S7-A read-only validation है, swarm execution नहीं। Current workflow में push और manual dispatch हैं; scheduled swarm trigger या publisher job नहीं।

## 3. वास्तविक S5 durability gap

Code inspection में:
- `build_langgraph_graph()` अभी `builder.compile()` बिना checkpointer के करता है।
- `invoke_graph()` अभी `graph.invoke()` को run-scoped `thread_id` config के बिना call करता है।
- Existing `StateRepository` में immutable state objects, manifest, CAS, writer lease, `commit_and_release` और exact fetch-back हैं।
- Existing repository writer lease एक publication transaction के बाद release होता है; graph के प्रत्येक checkpoint के बीच lease बनाए रखने/renew करने का method अभी नहीं है।
- Existing state object kinds में `langgraph_checkpoint` और `langgraph_pending_writes` नहीं हैं।

इसलिए मौजूदा run-state proposal को native LangGraph durable checkpointer कहना सही नहीं होगा। S5 graph integration PASS है, durable graph persistence अभी implement नहीं हुई।

## 4. चुना गया checkpoint design

### 4.1 LangGraph contract

Pinned runtime `langgraph==1.2.22` के लिए implementation `langgraph.checkpoint.base.BaseCheckpointSaver` contract के अनुरूप होगी। Core synchronous execution path:
- `put`: super-step checkpoint save।
- `put_writes`: node/task pending writes save।
- `get_tuple`: checkpoint, parent config और pending writes restore।
- `list`: bounded checkpoint history।

`BaseCheckpointSaver` also exposes `delete_thread`. Because the canonical Git ledger is append-only, physical deletion/history rewrite is not allowed in this phase. The initial adapter will fail closed for `delete_thread`; therefore **full BaseCheckpointSaver conformance will not be claimed** until a separately reviewed logical-tombstone behavior is implemented and tested. Async methods remain disabled.

LangGraph में `thread_id` checkpoint thread की primary identity है; ZCIRA में इसे exact `run_id` से bind करेंगे। `checkpoint_ns` fixed empty string रहेगा। Async graph execution इस चरण में निषिद्ध रहेगी। Official interface reference: https://reference.langchain.com/python/langgraph.checkpoint/base/BaseCheckpointSaver

### 4.2 Canonical storage

- Backend: existing `StateRepository`; no runner-local SQLite durability.
- New manifest object kinds: `langgraph_checkpoint`, `langgraph_pending_writes`.
- New versioned Draft 2020-12 schemas और valid/negative fixtures आवश्यक।
- Objects उसी immutable `state/objects/<sha256>.json` namespace में रहेंगे और manifest से reference होंगे।
- `put_writes` तथा `put` write-through होंगे; हर successful method return से पहले Git commit fetch-back verified होना चाहिए।
- Pending writes task ID/path के साथ store और deterministic order में restore होंगे।
- Duplicate same-content writes idempotent; same identity पर different content fail-closed।

### 4.3 Single-writer boundary

- Graph/checkpointer केवल उसी bounded publisher execution के भीतर चलेगा जो `evidence_publisher` role का active lease रखता है।
- Read-only source workers को GitHub write token या App private key नहीं मिलेगा।
- अगले code increment में `StateRepository.commit_under_lease()` और lease refresh जोड़ना होगा, ताकि checkpoint commits के बीच एक ही writer lease सक्रिय रहे।
- Proposed bounds: graph runtime 600 seconds; writer lease TTL 900 seconds, हर checkpoint commit पर refresh; अधिकतम 16 checkpoints/run; 256 KiB/checkpoint; 64 KiB pending-write batch; 4 MiB total/run।
- Runner समाप्त/क्रैश होने पर अगली execution canonical manifest से last verified checkpoint पढ़ेगी। Expired lease के बाद ही नया publisher lease लिया जाएगा।
- Stale SHA पर कोई force push या blind retry नहीं।

### 4.4 Serialization और retention

- Canonical JSON only; pickle fallback और arbitrary object reconstruction निषिद्ध।
- केवल allowlisted `SwarmGraphState` channels।
- Raw page bytes, credentials, tokens, secrets, personal/customer data reject।
- Raw third-party source body persist नहीं होगी; metadata-only envelope ही रहेगा।
- Checkpoint history append-only। `delete_thread`/prune इस phase में disabled; कोई Git history rewrite नहीं।

### 4.5 Acceptance tests

1. Pinned LangGraph package पर वास्तविक `BaseCheckpointSaver` compatibility।
2. Node A complete, Node B checkpoint/pending write durable, runner interruption, नए ephemeral invocation में same `thread_id` से resume; completed node दोबारा execute न हो।
3. Pending-write order, parent checkpoint, list/before/limit और checkpoint ID restore।
4. Duplicate put/write idempotency; conflicting content rejection।
5. Wrong mission/thread, stale head, expired lease, kill-switch, oversized payload, non-JSON/pickle, secret/raw-body rejection।
6. Fake Git transport atomic commits, lost-response recovery और exact commit-ref fetch-back।
7. `delete_thread` fail-closed test: no Git mutation and no claim of physical erasure; logical tombstone design remains a separate gate.
8. Full hash-locked S7-A CI pass।

## 5. S6-B2 egress revalidation

- GitHub public standard runners public repositories में free/unlimited standard compute देते हैं, लेकिन shared hosted runners default रूप से public internet access रखते हैं। Standard runner class में provider-managed per-job egress firewall उपलब्ध नहीं।
- GitHub shared runner IP ranges unrelated workloads के साथ shared हैं; इन्हें allowlist करना secure per-job isolation नहीं है। Static IP/larger-runner और Azure VNET विकल्प selected ₹0 standard-runner path के लिए eligible नहीं।
- Official docs: https://docs.github.com/en/actions/concepts/runners/private-networking ; https://docs.github.com/en/actions/reference/runners/github-hosted-runners
- Cloudflare Workers Free: current official limits में 100,000 requests/day, Cron CPU 10 ms/invocation, 128 MB memory, 50 subrequests/request और पाँच Cron Triggers/account। यह lightweight heartbeat/dispatcher को support करता है, source crawler या LangGraph runtime को नहीं।
- D1 Free: 5 million rows read/day, 100,000 rows written/day, 5 GB total storage. Daily quotas exceed होने पर queries fail; free quota को paid auto-fallback नहीं माना जाएगा।
- Official docs: https://developers.cloudflare.com/workers/platform/limits/ ; https://developers.cloudflare.com/workers/configuration/cron-triggers/ ; https://developers.cloudflare.com/d1/platform/pricing/
- Cloudflare account/payment-method/no-billing eligibility अभी account-level पर verify नहीं हुई। कोई account creation, terms acceptance, billing activation या deployment नहीं।
- Runner-local firewall/network namespace का कोई test नहीं किया गया; यह security testing होगा और exact owner approval के बिना नहीं होगा।

**Disposition:** `dns_pinning=false`, `egress_controls_audited=false`, `live_network_enabled=false`; live source requests 0। Cloudflare केवल future heartbeat/dispatch candidate; D1 केवल non-authoritative mirror।

## 6. Current operational ledger

- S5 real LangGraph graph integration: PASS।
- Native durable LangGraph checkpointer: DESIGN LOCKED / NOT IMPLEMENTED।
- S6-A/C/D deterministic synthetic/code gates: recorded PASS।
- S6-B2 live egress: HOLD।
- S7-B3 Git Data transport: FakeTransport CI PASS; live Git Data API write NOT TESTED।
- Publisher workflow/credential isolation: disabled।
- Main branch protection: `protected=false`; rulesets empty।
- S8 Cloudflare Worker/Cron/D1: not deployed।
- S9 seven-day unattended pilot: not started।
- Runtime agents/scheduled swarm: none.
- Spend ₹0; settled revenue evidence ₹0; commercial execution HOLD।

## 7. Next sequential work

1. Implement retained-lease state transition and lease-refresh tests.
2. Add checkpoint/pending-write schemas, fixtures and manifest object kinds.
3. Implement the JSON-only native `BaseCheckpointSaver` adapter.
4. Add actual LangGraph crash/resume integration tests on the pinned package; run full CI.
5. Keep live Git writes disabled until owner-controlled publisher identity/ruleset/credential isolation is approved and verified.
6. Keep live source fetching disabled until a separately approved, audited ₹0 egress design exists.
7. Only after these gates, proceed to S8 Cloudflare eligibility/heartbeat tests, then S9 read-only pilot.

**No account/KYC/terms/billing/deployment/security testing/outreach/submission/product build/listing or spend was performed.**


## 8. Post-report validation checkpoint

- The design/config/continuity commit was validated by GitHub Actions run [45536463105](https://github.com/manish91082-coder/zero-cost-internet-revenue-automation/actions/runs/45536463105), job 138944152923, on exact head `6b3310435490afde778e4c03d801dbcd4b9bdbd6`.
- Actual decoded job log: hash-locked installation of 47 packages succeeded; `pip check` reported no broken requirements; 3 real LangGraph integration tests passed; full pytest: **200 passed, 1 skipped, 6 subtests passed**.
- Run conclusion SUCCESS. This is still S7-A read-only validation only; no live Git Data API write, source fetch, publisher credential or cloud deployment.


## 9. Exact-head validation of the conformance correction

- GitHub Actions run [45536603459](https://github.com/manish91082-coder/zero-cost-internet-revenue-automation/actions/runs/45536603459) on exact head `3d5b1999324e1ff6332ed0e446e41639f93a71ca`: SUCCESS.
- Job `138944626185`: 47 hash-locked packages installed; pip check clean; real LangGraph integration 3 passed; full pytest **200 passed, 1 skipped, 6 subtests passed**.
- The log confirms the final policy and roster JSON were accepted by the current read-only workflow. No runtime code or deployment changed.


## 10. Final exact-head metadata validation

- After the roster and adapter-policy validation pointers were refreshed, GitHub Actions run [45536698778](https://github.com/manish91082-coder/zero-cost-internet-revenue-automation/actions/runs/45536698778) on exact head `b20a95f3c188c99fc289d9b3fd941ff6c7d3f7bd` completed SUCCESS.
- Job `138944944252`: 47 hash-locked packages; pip check clean; 3 real LangGraph integration tests passed; full pytest **200 passed, 1 skipped, 6 subtests passed**.
- The machine-readable roster/policy keep the preceding run ID to avoid a self-referential commit/run pointer loop; this continuity/report record is the exact-head run evidence.
