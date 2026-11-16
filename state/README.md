# ZCIRA durable state

This directory contains public, non-secret, mission-scoped runtime state.

- `manifest.v1.json` is the canonical pointer to the latest immutable state objects.
- Content-addressed objects are stored below `objects/` and are referenced by SHA-256.
- State changes must use the Git Data API adapter with an expected main-branch SHA and a non-force ref update.
- The repository writer lease is cooperative until a publisher-only credential and protected publication path are configured.
- Do not store owner email, OAuth tokens, passwords, cookies, customer data, KYC documents, payment details or secrets here.
- The initial manifest is empty (generation 0). No tasks, active leases, agent runs or cloud runtime are implied by this bootstrap file.
