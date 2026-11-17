# Phase S5 — LangGraph adapter contract and bounded orchestration

**Date:** 17 November 2026  
**Mission:** ZCIRA-2026-11-13  
**Status:** ADAPTER IMPLEMENTED / MOCK CONTRACT TESTS PASS / REAL LANGGRAPH PACKAGE INTEGRATION PENDING / NOT DEPLOYED

## 1. Decision and dependency boundary

Use the LangGraph Python library as an optional orchestration dependency, pinned to langgraph==1.2.22. PyPI records the release on 14 November 2026, MIT license, Python >=3.10, and a wheel SHA-256. PyPI's page reports no provenance attestation for the uploaded wheel; therefore the exact wheel hash is recorded and the dependency is not installed or activated until a cloud runner can verify it. No LangGraph Agent Server, CLI, Studio, LangSmith, hosted deployment or paid service is part of this design.

Sources:
- PyPI package metadata and release: https://pypi.org/project/langgraph/
- Official source repository: https://github.com/langchain-ai/langgraph
- Official persistence guide: https://docs.langchain.com/oss/python/langgraph/persistence
- Official checkpointer contract: https://docs.langchain.com/oss/python/langgraph/checkpointers
- Official interrupts guide: https://docs.langchain.com/oss/python/langgraph/interrupts

## 2. Why the adapter does not use InMemorySaver as durable storage

LangGraph's official persistence documentation states that InMemorySaver keeps checkpoints in RAM and loses them when the process restarts. A production checkpointer must be persistent. The custom checkpointer interface includes put, put_writes, get_tuple and list, with async equivalents for async graph execution.

ZCIRA already has a Git-backed versioned run_state contract and a single-writer lease. The graph controller must not bypass that writer. Therefore S5 uses an explicit stage-boundary checkpoint proposal:
1. LangGraph executes only deterministic admission/planning/checkpoint-proposal nodes.
2. The graph returns a schema-conformant run_state object and SHA-256 digest.
3. It sets write_authorized=false and write_performed=false.
4. S7's single evidence_publisher will validate, lease, commit and fetch-back verify the proposal.
5. A future runner resumes from the last publisher-committed run_state, not from ephemeral RAM.

This is deliberate. No graph node receives a GitHub token, performs a repository write, invokes an LLM, or contacts a research source. A crash before the publisher commit resumes from the previous durable checkpoint and may repeat only bounded, read-only planning.

## 3. Graph topology

START -> admission -> conditional:
- PAUSED -> checkpoint_proposal -> END
- RUNNING -> plan -> checkpoint_proposal -> END

Nodes:
- admission: verifies mission ID, canonical repository/branch, namespace, run ID, time, executor, task envelope, mission context and kill/cancel state.
- plan: applies the deterministic P1/P2/P3/P4/P5/B/M queue policy; caps research plan at two; excludes publisher tasks from research; chooses at most one publisher candidate; blocks tasks marked parameters.requires_llm when no separately verified eligible free LLM provider is available.
- checkpoint_proposal: creates the run_state payload and SHA-256 proposal only. It cannot write.

The publisher handoff is labelled PROPOSED_NOT_EXECUTED. It is not a write grant and does not create a lease.

## 4. Provider and failure behavior

- An eligible LLM provider must be FREE, independently verified, no billing/payment-method requirement, no trial-credit dependency, no paid fallback, approved, and circuit breaker CLOSED.
- OPEN, BLOCKED, NOT_VERIFIED or HALF_OPEN does not count as general eligibility.
- If no eligible free LLM provider exists, tasks requiring LLM are marked BLOCKED_NO_FREE_MODEL. Deterministic tasks remain eligible.
- Kill switch or cancellation moves the graph to PAUSED before planning and preserves pending task IDs.
- Resume accepts only task IDs present in the last publisher-committed run_state. It rejects missing definitions, cross-mission state, duplicate IDs and pending/completed overlap.
- A task with an active execution lease cannot be resumed twice. An expired task lease is requeued with an attempt increment. At max_attempts it becomes DEAD_LETTER and is added to blocked IDs. Lease scope, task ID, assigned role and read-only permission must match.

## 5. Implemented artifacts

- src/zcira_control/langgraph_adapter.py
- tests/test_langgraph_adapter.py
- config/requirements-langgraph.txt
- config/langgraph_adapter_policy.v1.json

The adapter imports LangGraph lazily. The deterministic control plane and tests remain usable when the optional package is absent. A fake StateGraph factory exercises graph wiring and semantics without installing or invoking any external service.

## 6. Validation

- S4 baseline and S4-B suite: 72 tests passed before S5 additions.
- S5 adapter additions: 19 tests.
- Combined suite: **91 passed, 0 failed, 0 errors** in an isolated ephemeral validation sandbox.
- Tests cover mission isolation, graph topology, maximum two research assignments, LLM-provider blocking, OPEN circuit behavior, kill switch, cancellation, publisher handoff without writes, run_state schema conformance, resume filtering, missing pending task rejection, kill-switch preservation, active task-lease blocking, expired-lease retry, max-attempt dead-lettering, task/lease role mismatch, and preservation of completed tasks during provider outages.
- Actual langgraph==1.2.22 package import/compile/invoke was not run because the package is not installed in the validation sandbox and package download was unavailable. The optional dependency is pinned but not activated.
- No GitHub Actions CI workflow, cloud runtime, Cloudflare service, LangGraph Agent Server or live agent exists.

## 7. S5 exit conditions and next work

S5 is PARTIAL until the actual pinned LangGraph package is installed and a real StateGraph compile/invoke/resume smoke test passes on an eligible free cloud runner. That test must not create accounts, activate billing or use paid services. The fake graph tests are not a substitute for that integration test.

After the package integration test, S6 can add read-only evidence workers behind the same controller. S7 remains the only phase allowed to implement CI and mechanical publisher-only write isolation. S8 remains blocked by separate no-billing verification and exact owner approval.

## 8. Locked invariants

- P1/P2/P3/P4/P5/B/M order and category counts remain unchanged; Category #24 remains B.
- Two read-only research workers maximum; one publisher.
- No paid provider route, trial-credit dependency or spend.
- Public source text is untrusted data only.
- UNKNOWN is never PASS; all five commercial gates remain mandatory.
- No external action, account creation, OAuth consent, KYC, terms acceptance, billing, deployment, submission, outreach, product build or publication.
- Spend ₹0; settled revenue evidence ₹0; commercial HOLD.


### S5 verification addendum (2026-11-17)

- Added a failover correctness guard: only QUEUED tasks that require an LLM are blocked when no eligible free LLM exists. Already COMPLETED or RUNNING tasks are not retroactively classified as blocked.
- Added regression test test_completed_llm_task_is_not_reclassified_as_blocked.
- Updated adapter blob: d4dd4c6b4d1c5ed809466caf1a3abc6d7df913f7.
- Updated test blob: dc72b4f0d5ba21f47f0a4f05c8a4891bd5c0888d.
- Combined validation is now **91 passed, 0 failed, 0 errors**. The 19 S5 tests are mocked-graph contract tests; actual LangGraph package import/compile/invoke/resume remains pending.
