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
