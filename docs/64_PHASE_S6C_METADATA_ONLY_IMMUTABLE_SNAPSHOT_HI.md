# Phase S6-C — Metadata-only immutable source snapshot envelope (2026-11-20)

## निर्णय

**S6-C का deterministic envelope builder, Draft 2020-12 schema, canonical serialization, detached SHA-256 content reference और publisher fetch-back verifier implement किए गए हैं। GitHub Actions acceptance run अभी pending है। Live source fetch, publisher writes और cloud deployment बंद हैं।**

## 1. Source और continuity preflight

- Canonical main parent: `2880b4fc60b1aeaa872584a54bb495f090816ea2`.
- Canonical repository: `manish91082-coder/zero-cost-internet-revenue-automation`.
- Latest continuity, S2-B architecture report 45, S1 roster report 42, S6 reports 60–63 and the controlling Library archive were reopened.
- Controlling archive `02_complete-research-hi.md`, Library version 1: 1,402,707 bytes; SHA-256 `c61be12a55385d0780a6a5bdf45f2fc22086be9edf6bbba96e78cfb0726d1e5e`, independently verified from the materialized original bytes.
- Destination section hash: `7e45078990d99d14e34a26befb3de2b8260fc53f35c6000fbe20fb741a36a24`.
- Source strategy remains 219 categories / 3,482 occurrence slots, six batches; 8 shared lists / 168 entries / 213 explicit edges; priority order P1/P2/P3/P4/P5/B/M unchanged; Category #24 remains B. Unique platform count is not established.

## 2. New implementation

- `src/zcira_control/snapshot_envelope.py`
  - Validates the existing source snapshot and new envelope schemas.
  - Verifies transient raw bytes against the source snapshot SHA-256 and 1 MB hard limit.
  - Produces metadata only; raw page bytes are not returned in the envelope.
  - Persists no query string or fragment; records a SHA-256 of the original URL for correlation.
  - Normalizes persisted text to Unicode NFC, removes control characters, redacts common email, Indian/international phone and labelled/known-token patterns, and caps excerpt at 2,000 characters.
  - Preserves category/destination/source-row/line/archive provenance.
  - Uses deterministic UTF-8 JSON with sorted keys, compact separators and no non-finite values.
  - Computes detached envelope SHA-256, `sha256:<digest>` content reference and future path `evidence/snapshots/sha256/<digest>.json`.
  - Includes `verify_snapshot_envelope_bytes` for future publisher fetch-back: digest, canonical bytes and schema must all match.
- `schemas/v1/source_snapshot_envelope.schema.json`: new Draft 2020-12 metadata-only contract.
- `tests/test_snapshot_envelope.py`: 16 focused tests, including raw-body exclusion, URL query removal, redaction, digest mismatch, host/scheme/credential rejection, provenance, deterministic canonicalization and fetch-back tamper detection.
- `tests/fixtures/s3_v1/valid_source_snapshot_envelope.json`: valid fixture.
- Existing schema contract test and manifest now include the 12th contract.
- `config/s6_snapshot_envelope_policy.v1.json`: machine-readable storage/redaction/publisher policy.
- Existing S6 worker policy records that publisher integration is still pending.

## 3. Storage and copyright boundary

- Full third-party HTML/JSON page bodies are not written to the public repository by default.
- Raw bytes are transient input to digest/size verification only; Python does not guarantee secure memory erasure, so this is a non-persistence control, not a forensic memory-wipe guarantee.
- Only bounded metadata, a redacted excerpt, source provenance and hashes are eligible for a future publisher.
- The digest-derived path is a proposed immutable repository path; no file was written under `evidence/snapshots/` and no GitHub publisher was invoked in this phase.
- A source licence or written permission remains necessary before retaining full raw source content. The default does not retain it.

## 4. Security boundaries

- `live_network_enabled=false`, `dns_pinning=false`, `egress_controls_audited=false` remain unchanged.
- No live DNS, TLS or public HTTP request was made.
- Source text remains `UNTRUSTED_DATA_ONLY`.
- Reviewer verdict remains `PENDING`; commercial gate remains `UNKNOWN`.
- Worker repository write remains false; only the canonical writer may publish future envelopes.
- No LLM/model provider is called by this deterministic builder.

## 5. Validation status at commit time

- The new 16 focused tests and 12th schema fixture are committed and will be validated by the existing read-only GitHub Actions workflow.
- GitHub Actions result is pending at report creation. Do not claim PASS until the run completes and logs are inspected.
- No publisher fetch-back against a real GitHub blob has occurred; only the deterministic verifier contract and synthetic tests are implemented.
- S6-C is implementation-complete pending CI, not a deployed persistence service.

## 6. Financial and external-action ledger

Spend authorized/incurred ₹0; settled revenue evidenced ₹0. No account, OAuth, KYC, legal acceptance, billing, cloud deployment, external submission, outreach, security test, commercial build or publication. Commercial execution remains HOLD.

## 7. Next gate

After the exact commit's GitHub Actions suite passes, S6-D should connect the metadata envelope builder to resumable LangGraph source-worker nodes while preserving the current disabled live-network policy. S7-B publisher-only enforcement remains separate and must precede any future snapshot publication.


## 8. First acceptance run and test-fixture correction

- Initial S6-C GitHub Actions run: 44668064760, URL https://github.com/manish91082-coder/zero-cost-internet-revenue-automation/actions/runs/44668064760, head `e20cd2a04d761264f5724f1d1f3140a8e5ab07fc`, conclusion FAILURE.
- Dependency installation succeeded: all 47 hash-locked packages installed, `pip check` passed; real LangGraph integration 3/3 passed.
- Full pytest: 164 passed, 4 failed, 1 expected skip, 6 subtests passed.
- All four failures were traced to the new test harness, not a failed transport or state-control test:
  1. Three tests passed override keywords `provenance` or `http_status` through a helper that also supplied hard-coded defaults, producing duplicate-keyword TypeError.
  2. The excerpt-limit test supplied 2,500 characters even though the upstream source-snapshot schema correctly limits its excerpt to 2,000; validation therefore failed before the envelope's stricter 1,800-character cap could be exercised.
- Corrected the helper to pop/resolve overrides before calling the builder. The excerpt test now supplies a schema-valid 2,000-character input and asserts the 1,800-character envelope cap.
- No production source-worker, pinned TLS or deterministic control-plane code was changed by this correction. The corrected test suite is pending a new GitHub Actions run; S6-C remains PENDING until that run passes.
