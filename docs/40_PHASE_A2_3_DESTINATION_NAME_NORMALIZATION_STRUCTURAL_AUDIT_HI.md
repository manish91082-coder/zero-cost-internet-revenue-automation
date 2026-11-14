# Phase A2.3 — Destination name normalization: structural extraction audit (2026-11-14)

## निर्णय
स्थिति: IN PROGRESS / SOURCE STRUCTURE RECONCILIATION REQUIRED. इस increment में source archive को दोबारा materialize करके वास्तविक embedded `plan/destinations-hi.md` content पर structural extraction चलाया गया। इसे 3,482 destination names की completed normalization या deduplication नहीं माना जा सकता।

## पुनः खोला गया controlling source
- Library source: `02_complete-research-hi.md`, file_id `file_00000000c8088211912536fa0fe8badd`, version 1.
- Embedded destinations section: SHA-256 `37607f76d56cd4d7810ff48d33956adc95de68899170377af54475e624c15281`.
- Extracted embedded section size: 727,941 bytes (source archive size 1,049,050 characters in current materialized UTF-8 text representation; do not treat character count as byte count).
- Source's own stated total: 219 categories / 3,482 destination slots, six batches.

## Structural extraction result
- Detailed numbered category headings detected by the current strict heading patterns: 178.
- Sum of destination counts declared in those 178 detailed headings: 2,747.
- Difference from source total: 735 slots not yet accounted for by this strict heading pass.
- Eight shared lists previously count-reconciled: 168 slots (A=24, B=16, C=31, P=23, F=26, G=16, T=20, L=12).
- Even after accounting for shared-list slots, 567 slots remain outside the 178 detected detailed category headings.
- Therefore the current parser does NOT yet establish a complete 219-category section map. The 41-category difference cannot be silently interpreted as zero-destination categories or mapped to shared lists without source-level evidence.
- The source contains summary tables, narrative/batch sections, category-specific sections and shared lists with differing heading formats. The strict heading pass is a discovery aid, not a complete parser.

## Integrity rules retained
1. Preserve original category IDs and names exactly; no renumbering or priority changes.
2. Preserve each destination's literal display name, URL/domain, notes, [S]/[V]/[K] marker and source context.
3. Keep category-specific destination rows distinct from shared-list rows.
4. A shared-list reference is attached to a category only where the source explicitly records that mapping; batch-level proximity is not a mapping.
5. Do not merge duplicate-looking names until identity evidence supports the merge. Retain aliases and every source occurrence.
6. Do not count 3,482 slots as unique platforms.
7. Do not use model knowledge to fill missing names or URLs.

## Phase A2.3 status
- Source re-opened: PASS.
- Source section identified and hash matched to Phase A2.2 record: PASS.
- Strict detailed-heading extraction: 178 records / 2,747 declared slots.
- Complete 219-category structural reconciliation: OPEN.
- Destination row extraction and field normalization: OPEN.
- Shared-list-to-category provenance mapping: OPEN.
- Evidence-backed deduplication and unique identity count: NOT STARTED.
- Destination-level audit status and five-gate revalidation: NOT STARTED.

## Ledger and permissions
- Spend authorized: ₹0; spend incurred: ₹0.
- Settled revenue evidenced: ₹0.
- Accounts/KYC/submissions/outreach: 0.
- Product build/test/publication: 0.
- Commercial execution: HOLD.
- No external contact, registration, legal acceptance, submission, build, test, listing, publication or paid action occurred.

## Next exact action
Phase A2.3-B: build a tolerant source parser against all six batch formats and the eight shared lists. Reconcile every one of the 219 category IDs against the controlling Appendix A and destination document; account for all 3,314 category-specific slots plus 168 shared-list slots. Emit a machine-readable raw-occurrence ledger first, with source line/section provenance. Only then normalize names and deduplicate.
