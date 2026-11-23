# Phase S7-B — ambiguous commit response recovery and read-only reconciliation

**तिथि:** 2026-11-23  
**Project:** ZCIRA-2026-11-13  
**स्थिति:** IMPLEMENTED / FULL READ-ONLY CI PASS / NOT DEPLOYED

## 1. Reliability problem addressed

A Git commit can be durably applied to the canonical branch while the caller loses the HTTP response. The caller then cannot know whether the write succeeded. Blind retry can create duplicate evidence, while treating the timeout as a definite failure can leave a completed task unrecognized.

The atomic publisher transaction already stores the task, snapshot, evidence, run-state and released lease in one commit. This increment adds an explicit read-only reconciliation path.

## 2. New API

`src/zcira_control/evidence_publisher.py` now exposes:

`EvidencePublisher.reconcile_batch(proposals, source_tasks)`

It:
- accepts one or two proposals only;
- validates exact task/proposal/source provenance through the existing preparation path;
- reads the canonical manifest and immutable objects;
- checks task idempotency key and completed status;
- checks exact source-snapshot/evidence object identities;
- fetches metadata snapshot/proposal files at the current head and compares exact canonical bytes;
- returns `NOT_PUBLISHED` when no batch task is durably completed;
- returns `ALREADY_PUBLISHED` only when every task in the batch is fully present and exact;
- fails closed on partial publication, mismatched immutable content or reused task identity;
- never acquires/releases a lease, creates a commit or writes a file.

The return object explicitly states `write_performed=false` and `external_action_performed=false`.

## 3. Fault-injection test

`tests/test_evidence_publisher.py` extends the fake durable store with a controlled fault: it advances the canonical head and persists the atomic commit, then raises a simulated `TimeoutError` before the caller receives the result.

The regression test proves:
1. Before publication, reconciliation returns `NOT_PUBLISHED` and performs no write.
2. The simulated response is lost after the atomic commit has already persisted.
3. The canonical manifest contains a completed source task, exactly one snapshot and one evidence object, and no active writer lease.
4. Read-only reconciliation returns `ALREADY_PUBLISHED` without a write.
5. A later lease/retry returns `ALREADY_PUBLISHED` and creates no duplicate snapshot/evidence object.

This is a deterministic fake-store fault-injection test, not a live GitHub write.

## 4. GitHub Actions validation

- Code commit: `dd8a5df2a3d0fe4347fcb9bd4df917d048f3c3bf`.
- Test commit: `2a5877e3354c6c768354f1741822be10a4466ce8`.
- Latest policy/roster head: `24e333db73df42b026cb3037bc890bb3a5079822`.
- Code test run [45106414426](https://github.com/manish91082-coder/zero-cost-internet-revenue-automation/actions/runs/45106414426): SUCCESS.
- Policy metadata run [45106524678](https://github.com/manish91082-coder/zero-cost-internet-revenue-automation/actions/runs/45106524678): SUCCESS.
- Latest roster/config run [45106527512](https://github.com/manish91082-coder/zero-cost-internet-revenue-automation/actions/runs/45106527512): SUCCESS.
- Full suite: **194 passed, 1 expected skip, 6 subtests passed**.
- Runner: `ubuntu-24.04`; Python 3.12.3; 47 SHA-256 hash-locked packages; `pip check` no broken requirements; real LangGraph integration 3 passed.

The single skip is the expected “LangGraph package missing” fallback test because LangGraph is installed in this validation environment.

## 5. Current boundaries

- Fake durable store only; no live Git Data API write or production evidence publication.
- Publisher workflow remains disabled; no contents:write runtime token or private key.
- Branch protection remains NOT ENABLED; main metadata previously showed `protected=false` and rulesets collection empty.
- S6-B2 egress audit remains HOLD; live source requests remain zero.
- Cloudflare Worker/Cron/D1 not deployed; no scheduled agent process; S9 pilot not started.
- Spend ₹0; settled revenue evidence ₹0; no account/KYC/legal acceptance/billing/external outreach/submission/product listing.

## 6. Next action

Continue the S7-B Git Data API transport/CAS/fetch-back audit using fake transport and explicit ambiguity tests. Actual write integration remains gated on owner-controlled branch ruleset and publisher credential isolation. Continue S6-B2 no-cost egress feasibility before any live source requests. Keep the publisher and cloud runtime disabled.
