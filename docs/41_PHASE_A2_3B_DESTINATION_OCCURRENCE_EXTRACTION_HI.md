# Phase A2.3-B — Source-faithful destination occurrence extraction (2026-11-14)

## परिणाम
**Extraction validation: PASS at declared-row level.** मूल embedded `plan/destinations-hi.md` में 219 category sections और 8 shared-list sections से सभी numbered table rows निकाले गए। हर section का extracted row count उसके heading में घोषित count से मेल खाता है।

| माप | स्रोत में घोषित | निकाली गई rows |
|---|---:|---:|
| 219 category-specific sections | 3,314 | 3,314 |
| 8 shared lists | 168 | 168 |
| **कुल** | **3,482** | **3,482** |

- Category section IDs: 219 unique IDs; duplicate category IDs: 0.
- Shared-list IDs: A, B, C, P, F, G, T, L.
- Notes में marker occurrences: [S]=199, [V]=662, [K]=658. ये occurrence counts हैं, unique destinations की संख्या नहीं; एक row में एक से अधिक markers हो सकते हैं।
- प्रत्येक occurrence में original category/shared-list ID, section name, ordinal, display name, site field, purpose, notes, source heading line और source row line सुरक्षित हैं।
- कोई deduplication, URL verification, current eligibility judgement या inferred shared-list/category mapping नहीं किया गया।

## Parser correction
Phase A2.3 के पहले strict heading pass ने 178 headings पकड़े थे क्योंकि उसने सीमित heading shapes को पकड़ा था। अब tolerant heading pattern ने `— N destinations` और `— N अपनी destinations` दोनों रूपों को पकड़ा, तथा अगली Markdown heading पर section boundary बंद की। परिणाम 219/219 category sections और 8/8 shared lists है। इसलिए पिछला 567-slot gap parser false-negative था, source data deficit नहीं।

## Hash-scope discrepancy, खुला reconciliation item
- पहले continuity record में embedded section hash `37607f76d56cd4d7810ff48d33956adc95de68899170377af54475e624c15281` दर्ज था।
- इस extraction run ने start heading सहित और end marker को छोड़कर निकाले गए text पर SHA-256 `7e45078990d99d14e34a26befb3bde2b8260fc53f35c6000fbe20fb741a36a24` निकाला।
- ये दोनों hash अभी समान नहीं हैं। सम्भव है कि पूर्व hash का byte-boundary/normalization scope अलग हो; इसे अनुमान से resolve नहीं किया गया। Source archive file identity/version स्थिर है, पर hash-scope reconciliation खुला है।

## Artifacts
- Parser: `scripts/extract_destination_occurrences.py`
- Parser output: `destination_occurrences.v1.json` (लगभग 2 MB; parser से पुनर्निर्माण योग्य)। Generated JSON इस increment में repository में commit नहीं किया गया क्योंकि connector contents API से बड़े generated payload को सुरक्षित रूप से transfer/verify करने का उपयुक्त मार्ग स्थापित नहीं हुआ।
- इसलिए full occurrence JSON को अभी durable repository artifact नहीं माना जाएगा।

## अभी शेष
1. Hash scope को exact source byte slicing से reconcile करना।
2. Original Appendix A के 219 IDs/names/priorities से category identity cross-check करना।
3. Six batch membership counts 27/27/41/51/38/35 को category IDs से reconcile करना।
4. Eight shared lists की batch-summary tables में explicit references से category-to-shared-list mapping बनाना; proximity से mapping नहीं।
5. Duplicate identity candidates की provenance-preserving review; तभी unique platform count निकालना।
6. फिर A3 schemas और destination-level gate research.

## Mission ledger
Spend authorized/incurred ₹0; settled revenue evidence ₹0; accounts/KYC/submissions/outreach/build/test/publication 0; commercial execution HOLD. P1/P2/P3/P4 order and category priorities unchanged.

## Parser integrity correction (same phase)
- Initial committed parser revision had over-escaped regex patterns. This was caught during fetch-back inspection before treating the script as a valid executable artifact.
- Corrected parser commit: `2177293acd5371e7e74fe9cad9b7b93de6fec950`. The committed parser now uses normal Python raw-regex escapes for whitespace, category numbers and [S]/[V]/[K] markers.
- Extraction counts above are from the independently executed corrected extraction logic, not from the defective initial parser revision. The corrected committed script must still be run against the original archive as a final executable reproduction test.
