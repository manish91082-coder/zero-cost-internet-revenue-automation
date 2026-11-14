# Phase A2.4 — Appendix A category identity, priority and source-hash reconciliation (2026-11-14)

## निष्कर्ष

**Appendix A ↔ destination headings identity check: PASS (219/219).** मूल Library archive `02_complete-research-hi.md` (file_id `file_00000000c8088211912536fa0fe8badd`, version 1) को दोबारा materialize करके embedded `plan/destinations-hi.md` और `plan/final-plan-hi.md` के Appendix A की तुलना की गई।

| जाँच | परिणाम |
|---|---:|
| Appendix A category rows | 219 |
| Destination category headings | 219 |
| IDs missing from destination headings | 0 |
| Extra destination heading IDs | 0 |
| Same-ID category-name mismatches | 0 |
| Destination category-specific slots | 3,314 |
| Declared source rows reproduced | 3,314 |

सभी 219 IDs और नाम exact match हैं। तुलना literal source labels पर हुई; कोई spelling correction, renumbering या inferred mapping नहीं की गई।

## Priority reconciliation

Appendix A के मूल priority labels का पुनर्गणन:

| Priority | Source count | Recomputed |
|---|---:|---:|
| P1 | 3 | 3 |
| P2 | 12 | 12 |
| P3 | 24 | 24 |
| P4 | 26 | 26 |
| P5 | 55 | 55 |
| B | 81 | 81 |
| M | 18 | 18 |
| **Total** | **219** | **219** |

P1/P2/P3/P4/P5/B/M का क्रम यथावत है। Category #24 “AI कर्मचारी किराये पर” Appendix A में **B** ही है। कोई category priority बदली या promote नहीं की गई।

## Embedded destination-section hash discrepancy: RESOLVED

दोनों historical hashes अलग extraction scopes से बने थे:

- पहले दर्ज hash: `37607f76d56cd4d7810ff48d33956adc95de68899170377af54475e624c15281` — इसका byte-boundary/normalization scope पुरानी notes में स्पष्ट नहीं था।
- Corrected parser का exact scope: `7e45078990d99d14e34a26befb3bde2b8260fc53f35c6000fbe20fb741a36a24` — start heading `# भाग 7: `plan/destinations-hi.md`` सहित और end marker `<!-- SOURCE END: plan/destinations-hi.md -->` को छोड़कर, UTF-8 text का SHA-256।

उसी स्पष्ट scope को source archive पर फिर लागू करने से दूसरा hash reproducibly प्राप्त हुआ। अतः यह source-content conflict नहीं, **hash-scope documentation mismatch** था। आगे canonical extraction-scope hash केवल `7e45078990d99d14e34a26befb3bde2b8260fc53f35c6000fbe20fb741a36a24` रहेगा। पुराने hash को historical record के रूप में रखा गया है, overwrite नहीं किया गया।

## अभी क्या PASS नहीं हुआ

1. **Six-batch category membership:** मूल summary में batch counts/slot totals हैं: 27/447, 27/644, 41/567, 51/752, 38/617, 35/455. इस inspected material में batch-wise category-ID roster का स्पष्ट, machine-readable mapping अभी प्रमाणित नहीं हुआ। केवल aggregate counts से category membership अनुमानित नहीं की जाएगी।
2. **Shared-list mapping:** A/B/C/P/F/G/T/L की 168 rows सुरक्षित हैं। Category-to-shared-list mapping तभी बनेगी जब source में explicit cross-reference मिले; पास-पास रखी गई tables से mapping infer नहीं होगी।
3. **Duplicate identity:** 3,482 source occurrence slots अभी भी unique platform count नहीं हैं। Identity/alias merge audit अगला अलग चरण है।
4. **Durable occurrence ledger:** लगभग 2 MB JSON occurrence ledger अभी local reconstruction है; repository में committed artifact नहीं माना जाएगा।

## अगला क्रम

- A2.4-B: source के batch-summary और category narrative में explicit batch-ID evidence तलाशकर 219 categories की batch membership को reconcile करना; जहाँ source केवल aggregate count देता है वहाँ status UNKNOWN रखना।
- A2.4-C: आठ shared lists के सभी explicit category cross-references निकालना; unresolved rows को unmapped रखना।
- A2.5: duplicate candidate review, original occurrence provenance और aliases सुरक्षित रखते हुए; unique count तभी जब identity evidence पर्याप्त हो।
- इसके बाद A3 task/evidence/source-snapshot/run-state schemas.

## Mission ledger

Project ID `ZCIRA-2026-11-13`; canonical repo `manish91082-coder/zero-cost-internet-revenue-automation`; spend authorized/incurred ₹0; settled revenue evidence ₹0; accounts/KYC/submissions/outreach/build/test/publication 0; commercial execution HOLD. कोई external action नहीं हुआ।
