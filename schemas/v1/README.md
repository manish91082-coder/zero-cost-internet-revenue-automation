# ZCIRA S3 schema contracts

Version 1.0.0 contracts for deterministic task control and bounded read-only research.

- All contracts are scoped to project `ZCIRA-2026-11-13` and canonical repository `manish91082-coder/zero-cost-internet-revenue-automation`.
- Schema validation is necessary, not sufficient. The deterministic policy engine must still enforce leases, expiry, path allowlists, owner approvals, provider health and five-gate decisions.
- Public source content is always `UNTRUSTED_DATA_ONLY`.
- Task actions are restricted to public read, parsing, hashing, internal draft creation and validated repository publication.
- Paid routes, spend, billing activation and automatic external actions are structurally denied.
- Repository writes are reserved for the single `evidence_publisher` role.
- JSON Schema does not by itself validate temporal ordering, GitHub branch-head compare-and-swap, quota consumption, signature authenticity or external OAuth consent. Those require deterministic runtime checks and later acceptance tests.
- The schema version is immutable once used by persisted tasks. Breaking changes require a new schema version and migration plan.

## S4-B durable state manifest

- `state_manifest.schema.json` defines the canonical mission state pointer and its content-addressed object references.
- State transitions are stored as immutable JSON objects under `state/objects/`; `state/manifest.v1.json` points to the latest object versions.
- The manifest carries a canonical SHA-256 digest, generation number, previous Git commit SHA, kill-switch state and active writer lease ID.
- GitHub Git Data API writes create one multi-file commit and update `main` with `force=false`; stale or concurrent branch heads fail closed.
- This adapter is repo code only. It is not wired to Actions, does not hold a token in the repository, and has not been deployed or run against GitHub write APIs.


## S6-C metadata-only source snapshot envelope

- Contract: `source_snapshot_envelope.schema.json`.
- Canonical JSON: UTF-8, sorted keys, compact separators and no NaN; publisher/title/excerpt text is NFC-normalized and control characters are removed.
- Envelope SHA-256 is detached from the canonical payload; `content_ref` is `sha256:<digest>` and the future publisher path is `evidence/snapshots/sha256/<digest>.json`.
- The raw page body is used only for digest/size verification and is not part of the returned envelope or persisted JSON.
- Query strings and fragments are omitted from the persisted URL; a SHA-256 of the original URL preserves an audit correlation without storing query values.
- Bounded excerpts and titles use the versioned redaction policy. Source text remains `UNTRUSTED_DATA_ONLY`; reviewer verdict is PENDING and commercial gate is UNKNOWN.
- The fetch-back verifier checks the SHA-256, exact canonical byte representation and schema after a future publisher retrieves the stored blob.
- This is a contract and deterministic code path, not a live crawler or publisher deployment. Live source networking remains disabled.
