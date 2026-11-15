# Phase A2.4-C — shared-list/category cross-reference reconciliation (2026-11-15)

## निर्णय

<badge>PASS</badge> **8/8 shared lists और source में छपे category cross-references निकाले गए।** Mapping केवल उन्हीं category rows से बनाई गई है जिनकी batch summary table में स्पष्ट `साझा सूचियाँ` column है। Batch-level proximity या category sequence से कोई mapping नहीं बनाई गई।

## आठ shared lists

| ID | Source list | Declared / extracted rows | Heading line |
|---|---|---:|---:|
| A | Ad networks | 24 / 24 | 5412 |
| B | Free hosting / program runtime | 16 / 16 | 5441 |
| C | Free audience/reach channels | 31 / 31 | 5462 |
| P | Payment methods | 23 / 23 | 5498 |
| F | Freelance marketplaces | 26 / 26 | 7282 |
| G | Directories / listings | 16 / 16 | 7313 |
| T | B2B trade directories | 20 / 20 | 8479 |
| L | Local classifieds | 12 / 12 | 8504 |
| **Total** | | **168 / 168** | |

## Explicit category references

- **A (6 categories):** #20, #51, #52, #59, #60, #61
- **B (21):** #20, #51, #52, #59, #60, #61, #81, #82, #83, #84, #85, #86, #115, #174, #199, #200, #227, #232, #88, #18, #23
- **C (70):** #20, #21, #25, #51, #52, #53, #59, #60, #61, #74, #78, #79, #81, #82, #83, #84, #85, #86, #115, #199, #200, #227, #232, #55, #56, #104, #105, #106, #107, #108, #109, #110, #111, #112, #113, #114, #117, #123, #125, #126, #127, #128, #131, #132, #133, #134, #88, #90, #92, #95, #101, #198, #201, #203, #209, #218, #219, #220, #221, #225, #228, #18, #23, #24, #76, #179, #182, #190, #244, #245
- **P (32):** #21, #25, #59, #60, #74, #78, #79, #115, #232, #55, #56, #58, #104, #105, #106, #107, #108, #123, #125, #126, #127, #128, #135, #90, #213, #18, #22, #23, #24, #76, #190, #244
- **F (25):** #103, #104, #106, #107, #109, #110, #111, #113, #114, #116, #117, #118, #119, #120, #121, #122, #123, #124, #129, #93, #24, #231, #233, #238, #239
- **G (36):** #104, #105, #106, #107, #108, #109, #110, #111, #112, #113, #114, #118, #120, #121, #124, #129, #131, #132, #133, #134, #88, #93, #96, #101, #102, #202, #207, #210, #217, #222, #24, #231, #233, #238, #239, #245
- **T (9):** #90, #96, #99, #211, #212, #213, #214, #215, #216
- **L (14):** #92, #102, #203, #204, #205, #206, #207, #208, #209, #210, #214, #218, #223, #226

Total explicit category-to-list edges: **213**. A category may reference multiple lists; these are not 213 unique categories.

## Source interpretation rules

- Batch 2, 4, 5 and 6 summary tables have an explicit shared-list column. A dash in those rows means no shared-list reference was printed for that category in that table.
- Batch 1 and 3 summary tables do not have that column. For those batches the mapping state is `NOT_LISTED`, not a proven negative. No absence is inferred.
- Batch 2 introduces A/B/C/P (94 slots); Batch 4 introduces F/G (42 slots); Batch 5 introduces T/L (32 slots). Batch 6 introduces no new list and explicitly points back to prior lists where applicable.
- Later references to an earlier shared list do not create new occurrence slots. Eight list bodies remain 168 rows total.

## Important invariant

Category #24 explicitly references F, G, C and P. This does **not** change its original priority: it remains **B**. The complete P1/P2/P3/P4/P5/B/M order and counts remain unchanged.

## Boundary and next step

This phase closes A2.4-C. It does not merge list rows with category rows and does not establish a unique-platform count. Next: A2.5 provenance-preserving duplicate-candidate review; retain every original category/list occurrence and mark all identity merges as review-only.
