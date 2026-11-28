# ZCIRA durable state

This directory on `main` retains the historical generation-zero bootstrap manifest only. It is not the canonical mutable runtime ledger.

- `state/manifest.v1.json` on `main` is a legacy empty bootstrap record and must never be used as a live state pointer.
- The canonical mutable state branch is `evidence-ledger`; its manifest and immutable objects are read/written only through the branch-locked Git Data API adapter.
- The state adapter rejects `main`, unknown branches, symbolic cross-branch refs and commit SHAs that are not ancestors of `evidence-ledger`. It has no fallback to the code branch.
- Content-addressed objects are stored below `objects/` and are referenced by SHA-256.
- Every state transition uses an expected evidence-ledger head and a non-force ref update.
- The repository writer lease is cooperative until a publisher-only credential and protected publication path are configured.
- Do not store owner email, OAuth tokens, passwords, cookies, customer data, KYC documents, payment details or secrets here.
- The inherited main manifest is eligible for migration only if it remains generation 0, has zero objects, no lease, no kill switch and a valid digest. The explicit bootstrap method never creates the branch and is not invoked automatically.
- No tasks, active leases, agent runs, live Git Data writes or cloud runtime are implied by the main-branch bootstrap file.
