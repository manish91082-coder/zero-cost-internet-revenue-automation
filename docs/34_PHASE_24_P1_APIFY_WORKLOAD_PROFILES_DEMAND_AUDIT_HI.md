# Phase 24 — P1 Apify Gate Audit (Batch 4: Workload Profiles, Unit Economics & Demand Reality)
Audit date: 2026-11-14 (Asia/Kolkata)
Project ID: ZCIRA-2026-11-13
Status: RESEARCH ONLY / COMMERCIAL EXECUTION HOLD

## 1. Scope and safety
This batch models three hypothetical Actor workload classes using published Apify unit rates. These are engineering estimates, not measured runs, demand forecasts, or revenue claims. No account, KYC, Actor, test run, listing, customer contact, publication, paid use, or spend occurred. Spend remains ₹0.

## 2. Verified pricing mechanics and material update
Official Apify pricing documentation currently lists FREE-tier unit rates: compute $0.20/CU; residential proxy $8/GB; SERP proxy $2.50/1,000 SERPs; external transfer $0.20/GB; internal transfer $0.05/GB; dataset reads $0.0004/1,000 and writes $0.005/1,000; KV reads $0.005/1,000 and writes/lists $0.05/1,000; request-queue reads $0.004/1,000 and writes $0.01/1,000. Higher customer tiers receive lower rates. [Source: https://docs.apify.com/actors/monetize/pricing-and-costs]

Current official docs say PPE creator profit is 0.8 × event revenue minus applicable platform usage costs. Only paid-plan user revenue/costs count toward this calculation; free-plan users do not create creator revenue and Apify covers their platform usage costs. Single-tenant PPE Actors do not make the creator cover users' platform usage; multi-tenant Server Actor runs for paying users are deducted from creator payout. [Source: https://docs.apify.com/actors/monetize/pricing-and-costs]

The PPE documentation describes a synthetic apify-actor-start event. Apify covers the compute cost for the first five seconds of each run when this event is enabled; the default event price is $0.00005 and scales by allocated RAM. This is a narrow startup-cost relief, not free full-run compute. [Source: https://docs.apify.com/actors/monetize/pay-per-event]

Important source-version discrepancy: the currently indexed Store Publishing Terms search result reports an update date of 15 September 2026 and describes promotional-user payout based on the highest configured discount tier, while the fetched canonical terms page currently rendered a 20 February 2026 version and did not contain that later clause. Do not silently reconcile these versions. Obtain written confirmation from Apify and archive the live terms/version before any future acceptance or publication. Canonical page: https://docs.apify.com/legal/store-publishing-terms-and-conditions

## 3. Workload profiles (illustrative, no execution)

Compute formula: CU = allocated RAM in GB × runtime in hours. Compute cost = CU × $0.20 at FREE tier. All examples assume no discount tier, no free five-second startup relief, and no test measurement.

| Profile | Assumed workload per event | Compute | Compute cost |
|---|---|---:|---:|
| A. Lightweight deterministic utility | 0.5 GB RAM × 2 min; user-provided input; no external calls; 1,000 output records; short retention | 0.0167 CU | $0.00333 |
| B. File/data transformation | 1 GB RAM × 3 min; 10 MB input; no external API/proxy; 5,000 output records; short retention | 0.0500 CU | $0.01000 |
| C. External web automation / scraper | 2 GB RAM × 10 min; 100 SERPs; 0.1 GB residential proxy; 0.1 GB external transfer; 1,000 output records | 0.3333 CU | $0.06667 |

### Variable platform cost estimates
- A: compute $0.00333 + 1,000 dataset writes $0.000005 = approximately $0.00334/event, excluding all other costs.
- B: compute $0.01000 + 5,000 dataset writes $0.000025 + 0.01 GB external transfer $0.002 = approximately $0.01203/event, excluding all other costs.
- C: compute $0.06667 + residential proxy $0.80 + 100 SERPs $0.25 + 0.1 GB external transfer $0.02 + 1,000 dataset writes $0.000005 = approximately $1.13667/event, excluding all other costs.

For PPE where creator bears these platform costs, event price required merely to cover those costs after the 80% share is cost / 0.8:
- A: approximately $0.00418/event.
- B: approximately $0.01504/event.
- C: approximately $1.42084/event.

These are bare platform-cost break-even floors only. They exclude refunds, unpaid invoices, payout/FX charges, support, maintenance, compliance, taxes, monitoring, model calls, development time, and demand/acquisition costs. They are not recommended retail prices and not profit forecasts.

## 4. Design implications
1. Best engineering candidate for later validation: deterministic user-input transformation or validation with no scraping, no residential proxy, no LLM/API dependency, bounded RAM/runtime, low output volume, and no persistent storage requirement.
2. Scraper/automation class is structurally expensive at the illustrative proxy usage. A $1 event cannot cover the modelled platform costs after Apify's 80% share. Avoid proxy-heavy products unless users explicitly bear platform usage and the value proposition/demand is independently proven.
3. Prefer single-tenant PPE architecture over multi-tenant Server Actor where technically and contractually appropriate, because official docs state the creator is not responsible for users' platform usage costs in single-tenant PPE. This does not remove the 20% platform commission, payout deductions/refunds, or the need to verify exact configuration.
4. Use strict input caps, memory caps, runtime bounds, idempotency, visible billable outputs, spend limits and synthetic startup event only if a later approved test plan exists.
5. No free-tier credit should be treated as sustainable zero-cost infrastructure. A finite allowance is a subsidy/credit, not zero marginal cost.

## 5. Demand / earnings evidence
Apify's own marketing and creator stories establish that some creators earn money, not the median outcome for a new entrant. An independent research page, Does It Pay? (updated November 2026 according to search index), reports its analysis of 3,338 Apify developer accounts with paid listings: median developer had 5 users across paid listings in the last 30 days; top 10% accounted for about 93% of users; about 3.7% had 1,000+ users. It estimates the developer payout split only under an explicitly untested assumption that payouts follow user counts. Therefore those are independent estimates, not audited payout records, not a verified median creator income, and not proof of demand for our proposed tools. Source: https://www.doesitpay.org/selling-ai-agents-and-gpts/research/

The same research reports Apify's public claim of $1.6m paid out in one month and 4,500 community developers, but the platform does not publish a creator-level median payout in the evidence reviewed. Dividing the pool by developers would produce an arithmetic mean, not a median, and is not a defensible earnings forecast. No buyer interviews, deposits, LOIs, paid pilots, or demand tests exist for our proposed tools.

## 6. Five-gate status
| Gate | Status | Reason |
|---|---|---|
| 1. Independent buyer intent | UNKNOWN / NOT PASSED | No product-specific buyer evidence; marketplace-wide activity does not prove demand for our tools |
| 2. IP, licensing, data rights, legal | UNKNOWN / NOT PASSED | No chosen product/data-source matrix or dependency provenance review; terms-version discrepancy needs clarification |
| 3. Fully loaded ₹0 unit economics | FAIL | Metered compute/proxy/transfer/storage costs exist; free credit is finite; support, refunds, payout, compliance and labour not fully zero |
| 4. India seller eligibility and verified payout | UNKNOWN / NOT PASSED | KYC and payout thresholds documented, but India-specific creator eligibility and successful India bank settlement not verified |
| 5. Autonomous fulfilment and owner workload | FAIL / NOT PASSED | No workload measured; terms require maintenance and timely issue responses; support/monitoring automation unproven |

Overall: P1 remains PRIORITY-1 CANDIDATE / VALIDATION HOLD. No build, listing, registration, publication, outreach, paid use or spend.

## 7. Batch 4 decisions and next work
- Candidate design priority: Profile A/B deterministic utilities, not Profile C proxy-heavy scraping.
- Gate 3 remains FAIL; do not re-label cost-recovery from customer revenue as zero-cost operations.
- Obtain written Apify clarification on (a) current Store Terms version, (b) promotional user payout calculation, (c) single-tenant PPE versus multi-tenant deductions, (d) India creator onboarding and bank settlement, and (e) whether any platform-side free tier can support commercial customer runs without creator-funded spend.
- Complete a product-level IP/data-rights matrix and dependency provenance template before choosing any Actor concept.
- Run no tests until a separate no-spend test protocol proves there can be no billing, overage, KYC, account, or payment obligation.
- In parallel, audit P2 bounty/grant destinations from the locked original plan for current active status, eligibility, prize terms, IP assignment, submission burden and India payout. Do not submit anything without explicit owner approval or written standing permission.

## 8. Sources
- Apify pricing and costs: https://docs.apify.com/actors/monetize/pricing-and-costs
- Apify PPE model: https://docs.apify.com/actors/monetize/pay-per-event
- Apify Store publishing terms: https://docs.apify.com/legal/store-publishing-terms-and-conditions
- Apify publishing requirements: https://docs.apify.com/actors/publishing/publish
- Apify payout timeline and thresholds: https://help.apify.com/en/articles/10057167-how-developer-payouts-work
- Independent Apify marketplace research: https://www.doesitpay.org/selling-ai-agents-and-gpts/research/

---
Audit boundary: Research and mathematical modelling only. Spend incurred ₹0. Settled revenue evidenced ₹0.
