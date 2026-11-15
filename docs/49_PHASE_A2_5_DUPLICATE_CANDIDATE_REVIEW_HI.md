# Phase A2.5 — provenance-preserving duplicate-candidate review (2026-11-15)

## निर्णय

**A2.5 candidate-generation audit: COMPLETE / IDENTITY MERGES NOT AUTHORIZED.** 3,482 original source occurrences पर deterministic normalization चलाकर repeated-name और same-host candidates बनाए गए। हर source occurrence की category/shared-list identity, ordinal और line provenance analysis में सुरक्षित रखी गई। किसी row को हटाया, merge या overwrite नहीं किया गया।

## Source and scope

- Source archive: `02_complete-research-hi.md`, Library file_id `file_00000000c8088211912536fa0fe8badd`, version 1
- Archive SHA-256: `c61be12a55385d0780a6a5bdf45f2fc22086be9edf6bbba96e78cfb0726d1e5e`
- Embedded destination section SHA-256: `7e45078990d99d14e34a26befb3bde2b8260fc53f35c6000fbe20fb741a36a24`
- Input: 3,314 category-specific rows + 168 shared-list rows = 3,482 occurrences.
- Durable compact audit index: `config/destination_duplicate_review.v1.json`.

## Candidate results

| Candidate class | Groups | Occurrences | Excess occurrences | Interpretation |
|---|---:|---:|---:|---|
| Repeated normalized display name | 315 | 747 | 432 | Candidate identity repeats |
| Same normalized name + same host | 283 | 665 | 382 | High-confidence identity candidate; still no automatic merge |
| Same name, missing/conflicting host | 32 | 82 | 50 | Ambiguous; needs further evidence |
| Repeated host groups | 489 | 1,435 | 946 | Domain collision, not proof of duplicate platform |
| Repeated host groups with multiple display names | 298 | — | — | Product/service/alias review only |

Within the 283 strict same-name/same-host groups:
- 261 span more than one category ID.
- 40 include at least one shared-list occurrence.
- 0 contain repeated occurrences inside the same category ID.
- A category may reuse the same platform for different monetization routes; that is precisely why original occurrences must remain intact.

## Examples with exact source provenance

| Normalized identity candidate | Occurrences | Source references |
|---|---:|---|
| Gumroad / gumroad.com | 11 | #7, #13, #36, #37, #64, #65, #66, #67, #71, #236, shared list P |
| Etsy / etsy.com | 9 | #37, #64, #65, #66, #67, #71, #74, #78, #90 |
| Payhip / payhip.com | 6 | #37, #64, #65, #71, #236, shared list P |
| Whop / whop.com | 6 | #7, #33, #37, #65, #55, shared list P |
| LinkedIn / linkedin.com | 5 | #42, #62, #108, shared lists C and T |
| Turing / turing.com | 5 | #95, #111, #130, #170, #172 |
| Buy Me a Coffee / buymeacoffee.com | 4 | #55, #65, #167, shared list P |
| CGTrader / cgtrader.com | 4 | #14, #63, #67, #236 |
| Fab (Epic) / fab.com | 4 | #14, #63, #67, #236 |
| Instagram / instagram.com | 4 | #62, #79, #127, shared list C |

The compact JSON index stores the original source line and ordinal for every occurrence in these ten examples. It also records the normalization method and candidate counts.

## What is not a duplicate

A shared hostname does not prove a shared platform identity. The same GitHub, LinkedIn, Facebook, YouTube, Etsy, AWS or Telegram domain can expose distinct products, programmes, creator tools, directories, job surfaces, APIs or policy portals. The audit found 298 repeated-host groups containing multiple display names. These remain domain-collision candidates, not aliases.

Similarly, a repeated brand name can appear in multiple categories because the source intentionally lists different revenue paths. Those are repeated destination identities across categories, not duplicate rows to delete. Shared-list occurrences are separately retained because they have their own source-list ID and ordinal.

## Method limitations

- Name normalization is limited to Unicode NFKC, case-folding, trimming and whitespace collapse.
- Host normalization lowercases the host, removes a leading `www.`, and assumes HTTPS when no scheme is written.
- No public-suffix equivalence, redirect resolution, live URL check, parent-company inference, brand-alias inference or path equivalence was attempted.
- The full 3,482-row occurrence ledger and full 315-group output were reconstructed locally but not committed. The committed JSON is explicitly a compact audit index, not a complete destination ledger.
- Therefore a defensible unique-platform count is **NOT ESTABLISHED**. No number is estimated from hostname collisions.

## A2 closure decision

A2.4-B and A2.4-C are PASS; A2.5 duplicate-candidate generation is complete with provenance-preserving review rules. The full A2 destination registry is still not certified as a unique-identity registry. Any future identity resolution must preserve all 3,482 source occurrences and link them to canonical IDs rather than deleting rows.

Priority totals/order remain P1=3, P2=12, P3=24, P4=26, P5=55, B=81, M=18. Category #24 remains B. Next engineering phase: S3 versioned schemas and synthetic contract fixtures. Commercial gates and all no-spend/owner-approval controls remain unchanged.
