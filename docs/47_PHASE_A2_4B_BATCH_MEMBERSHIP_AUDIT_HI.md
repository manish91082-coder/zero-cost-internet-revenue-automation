# Phase A2.4-B — छह batches की category-ID membership reconciliation (2026-11-15)

## निर्णय

<badge>PASS</badge> **219/219 category IDs का छह source batches में exact assignment मिला।** इस बार केवल batch totals नहीं, बल्कि हर batch की अपनी summary table में लिखे category-ID rows निकाले गए। IDs का कोई अनुमान, क्रम-आधारित विभाजन या Appendix A से batch inference नहीं किया गया।

## Controlling source और reproducibility

- मूल Library archive: `02_complete-research-hi.md`, file_id `file_00000000c8088211912536fa0fe8badd`, version 1
- पूरे archive का SHA-256: `c61be12a55385d0780a6a5bdf45f2fc22086be9edf6bbba96e78cfb0726d1e5e`
- Embedded `plan/destinations-hi.md` section SHA-256: `7e45078990d99d14e34a26befb3bde2b8260fc53f35c6000fbe20fb741a36a24`
- Category summary source line ranges: Batch 1: 4683–4713; Batch 2: 5376–5406; Batch 3: 6293–6337; Batch 4: 7224–7278; Batch 5: 8434–8475; Batch 6: 9407–9445
- Prior identity check: `docs/43_PHASE_A2_4_APPENDIX_A_IDENTITY_PRIORITY_HASH_RECONCILIATION_HI.md` already confirmed Appendix A ↔ destination headings 219/219 exact.

## Batch reconciliation

| Batch | Category IDs | Category count | Category-specific slots | Newly introduced shared lists | New shared slots | Total source slots |
|---|---|---:|---:|---|---:|---:|
| 1 | Source IDs in registry | 27 | 447 | None | 0 | 447 |
| 2 | Source IDs in registry | 27 | 550 | A, B, C, P | 94 | 644 |
| 3 | Source IDs in registry | 41 | 567 | None | 0 | 567 |
| 4 | Source IDs in registry | 51 | 710 | F, G | 42 | 752 |
| 5 | Source IDs in registry | 38 | 585 | T, L | 32 | 617 |
| 6 | Source IDs in registry | 35 | 455 | None | 0 | 455 |
| **Total** | **219 unique IDs** | **219** | **3,314** | **8 lists** | **168** | **3,482** |

The category ID arrays and exact source row provenance are preserved in `config/destination_batch_shared_map.v1.json`.

## Integrity checks

- Six source summary tables contain 27, 27, 41, 51, 38 and 35 category rows respectively.
- Total summary rows: 219.
- Unique category IDs: 219.
- Missing IDs against the 219 destination headings: 0.
- Extra IDs: 0.
- Duplicate IDs across batches: 0.
- Summary-row category labels vs same-ID destination headings: 219/219 exact.
- Per-category declared destination rows remain 3,314/3,314; this phase does not alter the prior parser result.
- Batch-specific source slot arithmetic reproduces all six totals exactly. Batch 2 adds 94 newly introduced shared-list rows; Batch 4 adds 42; Batch 5 adds 32. Existing shared-list references in later batches are references, not new slot additions.

## Boundary

This closes A2.4-B only. It does not deduplicate platforms, validate current destination URLs, prove commercial eligibility or change any source priority. The 3,482 count remains source occurrence slots, not unique platform identities. Priority totals remain P1=3, P2=12, P3=24, P4=26, P5=55, B=81, M=18; Category #24 remains B.

## Next

A2.4-C: extract only the explicit category-to-shared-list cross-references in source summary tables, then A2.5 duplicate-candidate review with all source occurrences preserved.
