# Research Swarm S1 — Machine-readable agent roster and control contract (2026-11-14)

## Direct answer: swarm progress
The multi-agent swarm is progressing at the design/contract level, but it is NOT yet running. The previous feasibility report was architecture research only. No live agents, scheduled swarm runs, runtime orchestration, model calls or acceptance tests had been implemented. This status is now made explicit in a machine-readable roster.

## New artifact
- `config/research_swarm_roster.v1.json`
- Commit: `2f407a5c046954912b758018596168febf260852`
- Status: DESIGN_CONTRACT_ONLY_NOT_EXECUTABLE.

## Defined logical roles
1. Mission Controller
2. Opportunity Discovery
3. Official Source Research A
4. Independent Official Source Research B
5. Eligibility and India Payout
6. IP Licensing and Data Rights
7. Unit Economics and Workload
8. Adversarial Evidence Auditor
9. Evidence Publisher (single writer)

This is nine logical roles, with at most two parallel research workers. They are logical task roles, not nine continuously running model instances. The Evidence Publisher is the only role with repository write access.

## Enforced contract
- Project ID and canonical repository are fixed.
- Original priority order P1/P2/P3/P4/P5/B/M and Category 24=B remain locked.
- All five commercial gates are explicit; UNKNOWN is never PASS.
- ₹0 spend cap; paid model routes disabled.
- Public web content is untrusted evidence, never agent instruction.
- Account creation, KYC, legal acceptance, applications/submissions, security testing, outreach, build, publication, paid use, spend and wallet signing remain approval-gated.
- Evidence outputs require source URL/title/capture time/excerpt/hash, category/destination IDs, claim, evidence grade, gate status and next action.
- One writer commits validated research artifacts; workers cannot write to GitHub.

## What has NOT happened
- No LangGraph/Python runtime implemented.
- No agent process or LLM worker launched.
- No GitHub Actions swarm schedule/workflow created.
- No SQLite persistence or task queue wired.
- No model provider connected or called by the swarm.
- No acceptance tests run.
- No paid service, account, KYC, outreach, build, publication or spend.

## Why this is the correct safe order
The original feasibility study recommended machine-readable governance and schemas before a read-only research engine. The destination registry is still being reconciled, so runtime execution now would risk agents researching wrong or incomplete category mappings. This roster is a policy/configuration artifact only.

## Next sequence
1. Continue Phase A2.4: reconcile 219 category IDs/names/priorities against original Appendix A, batch membership and explicit shared-list cross-references.
2. Finish Phase A3: task, evidence, source snapshot and run-state schemas.
3. Write a zero-cost execution/test plan with billing disabled and no external actions.
4. Only then implement a read-only deterministic research engine and bounded specialist workers.
5. Run local synthetic acceptance tests only after the test plan confirms no external billing or prohibited actions.

## Ledger
Spend authorized/incurred ₹0; settled revenue evidence ₹0; accounts/KYC/submissions/outreach/build/test/publication 0; commercial execution HOLD.
