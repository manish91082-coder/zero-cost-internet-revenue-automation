# Phase S4-B — durable Git-backed state, writer lease और checkpoint CAS (2026-11-16)

## Executive decision

**S4-B IMPLEMENTATION PUBLISHED / STATIC CONTRACT PREFLIGHT PASS / PYTEST NOT EXECUTED / CLOUD NOT DEPLOYED.**

S4 के in-memory lease और checkpoint logic को Git-backed durable-state adapter तक बढ़ाया गया है। Runtime के लिए laptop, desktop, self-hosted runner, SQLite persistence या paid service आवश्यक नहीं है। Adapter Python standard library पर आधारित है और GitHub Git Data API को injected transport के माध्यम से उपयोग करता है।

यह अभी repository engineering है, live swarm नहीं। Adapter ने इस run में GitHub write API, token, Actions runner या किसी cloud service को call नहीं किया।

## 1. Published artifacts

| Artifact | Purpose |
|---|---|
| `src/zcira_control/github_state.py` | GitHub Git Data API transport, expected-head check, atomic multi-file commit, non-force branch-ref update, fetch-head verification |
| `src/zcira_control/state_repository.py` | Content-addressed state objects, canonical JSON, manifest digest, generation, lease acquire/release, expiry recovery, read-back verification |
| `schemas/v1/state_manifest.schema.json` | Durable state manifest contract |
| `state/manifest.v1.json` | Empty generation-0 bootstrap manifest |
| `state/README.md` | Public state directory policy; no secrets or owner identity data |
| `tests/test_github_state.py` | Fake GitHub transport tests for atomic commit, stale head, non-fast-forward race and path allowlist |
| `tests/test_state_persistence.py` | Fake durable store tests for initialization, single writer, atomic release, expiry recovery and tamper detection |
| `tests/fixtures/s3_v1/valid_state_manifest.json` | Synthetic valid manifest fixture |
| `tests/test_contract_schemas.py` | State manifest schema and negative-case registration |
| `config/mission_registry.v1.json` | `state/**` added to the ZCIRA-only path allowlist |
| `config/mission_isolation_policy.v1.json` | Cross-thread enforcement status corrected to cooperative-only |
| `config/schema_contract_manifest.v1.json` | State manifest contract registered |

## 2. Durable persistence model

1. `state/manifest.v1.json` is the canonical pointer. It records the fixed mission/repository/branch/namespaces, generation, previous commit SHA, object references, active writer lease ID, kill-switch state, zero-spend invariant and SHA-256 digest.
2. State objects are immutable and content-addressed under `state/objects/<sha256>.json`. A manifest entry binds kind + object ID + schema version + path + content hash. A changed object creates a new blob; it does not overwrite the old object history.
3. Every transition creates one Git commit containing all new objects and the new manifest. The Git Data API flow is: read current head → create blobs → create tree based on the expected head tree → create commit with that exact parent → update `refs/heads/main` with `force=false` → verify the branch head.
4. If the head changes before the write, the preflight rejects it. If a concurrent sibling commit wins between commit creation and ref update, GitHub's non-fast-forward rejection becomes `BranchHeadConflict`. No force push or silent overwrite is permitted.
5. The writer lease is itself a versioned state object. Acquisition commits the active lease and updates the manifest. The publisher's final artifact/state commit updates the objects and releases the lease atomically. If a process crashes, the lease remains until expiry; a later writer can mark it EXPIRED and acquire a new lease using a fresh head.
6. A writer must publish against the exact commit SHA returned by lease acquisition. Any intervening commit makes the lease head stale and publication fails closed.
7. Transaction bounds: maximum 100 JSON files, maximum 512 KB per file and 2 MB total. The adapter can write only `state/manifest.v1.json` and SHA-256 content-addressed object paths.

## 3. Cross-thread isolation: exact security boundary

The durable lock is **cooperative, not yet a mechanically enforced security boundary**. Any client that has direct write permission and deliberately bypasses the adapter could still attempt a write.

- The repository's machine-readable mission policy now records: cooperative Git-CAS adapter implemented but not deployed.
- Repository rulesets endpoint returned an empty list at inspection.
- Branch-protection endpoint returned HTTP 403 `Resource not accessible by integration`; therefore branch-protection status is UNKNOWN, not PASS and not asserted absent.
- No `.github/workflows/` directory is present in the checked root.
- Actions runs endpoint returned 0 workflow runs.
- The GitHub connector's write permission has not been reduced or scoped to a single ChatGPT thread. Threads do not automatically share a lock.
- Until S7, only the canonical ZCIRA publisher thread should write this repository. Other project repositories remain out of scope and untouched.

Mechanical exclusion requires the later S7 publisher-only credential/workflow, serialized concurrency and protected publication path. Those controls have not been configured.

## 4. Validation evidence

- GitHub fetch-back succeeded for every newly created or updated file; exact blob SHA values are recorded in the run checkpoint.
- Static preflight parsed the new schema, fixture, mission registry and schema manifest as JSON. Fixture fields exactly match all required state-manifest fields with no extras; the state-manifest contract is registered and `state/**` is allowlisted.
- The new state-manifest schema passed Draft 2020-12 meta-schema validation in an isolated Python validator; its empty generation-0 fixture passed; two adversarial mutations (active lease without a matching object, and paid provider routes enabled) were rejected. This validation covers the new state-manifest contract only, not all 11 contracts.
- Eleven new Python test methods are committed across the two S4-B test modules.
- **The eleven new pytest tests have NOT been executed.** The current repo has no Actions workflow, and the available isolated tool container could not resolve the public GitHub host for cloning. No full repository pytest run or CI run is claimed.
- The earlier S4 core's 27/27 standard-library tests remain historical evidence from the previous checkpoint; they were not rerun against this expanded tree.

## 5. Current state bootstrap

- Manifest: `state/manifest.v1.json`
- Generation: 0
- State objects: 0
- Active writer lease: none
- Pending tasks: none persisted
- Agent runs: none
- This bootstrap is an empty durable-state container, not evidence that a scheduler or agent has run.

## 6. Runtime and approval status

- GitHub Actions swarm workflow: NOT CONFIGURED.
- Cloudflare Worker/Cron/D1: NOT CREATED OR DEPLOYED.
- LangGraph adapter: NOT STARTED.
- Read-only source agents: NOT RUNNING.
- Provider circuit-breaker runtime integration: NOT STARTED.
- OAuth or Google consent: NOT REQUESTED.
- No token, email address, password, cookie, KYC, payment or customer data was written to the repository.
- No account creation, legal acceptance, billing/payment-method activation, deployment, external contact, submission, product build, publication or spend occurred.
- Spend authorized/incurred: ₹0. Settled revenue evidenced: ₹0. Commercial execution: HOLD.

## 7. Remaining S4-B exit conditions

1. Execute the committed Python tests against the exact fetched repository tree in a verified ephemeral environment.
2. Run Draft 2020-12 validation against all 11 contracts and fixtures; add state-manifest digest and active-lease reference tests.
3. Add a real GitHub API integration test only in a disposable test repository or mocked transport. Do not write test state to the canonical mission repository.
4. Verify that concurrent ref updates fail without force push and that fetch-back verifies each committed object.
5. Keep the canonical manifest empty until a runtime is approved and a valid publisher lease is acquired.

Only after S4-B tests pass should S5 LangGraph adapter work begin. S7 remains responsible for CI, publisher-only write credentials and mechanical branch/write isolation. S8 deployment still requires separate verified no-billing eligibility and exact owner approval.

## 8. Locked invariants

P1/P2/P3/P4/P5/B/M order is unchanged; Category #24 remains B. Maximum two read-only research workers; one publisher. Paid routes and trial-credit dependency remain false. UNKNOWN is never PASS. Five commercial gates remain mandatory. The original 3,482 source slots remain occurrence counts, not a unique-platform count. No project outside ZCIRA is included.


## 9. Official API reference

GitHub's official guide describes the Git Database write sequence used by this adapter: read the current commit/tree, create blobs, create a tree, create a commit with the current commit as parent, then update the branch reference:
https://docs.github.com/en/rest/guides/using-the-rest-api-to-interact-with-your-git-database

This documents the object flow; it does not replace live integration tests, repository protection or owner approval.
