# Phase 24 — P1 Apify Tool Factory Gate-Validation Audit (Batch 1)
Audit date: 2026-11-14 (Asia/Kolkata)
Project ID: ZCIRA-2026-11-13
Status: RESEARCH IN PROGRESS / COMMERCIAL EXECUTION HOLD

## 1. Scope and controls
This is a research-only audit of the integrated plan's P1 Tool Factory candidate. It does not authorize account creation, Actor construction, API publication, listing, registration, customer outreach, paid usage, or spend. The source strategy's P1 order is preserved: Apify Store first, with RapidAPI and ApyHub as separate distribution routes. Phase 23 Category 24 remains closed and classified B; no category reprioritization is made.

Hard constraints remain:
- Authorized spend ₹0; incurred spend ₹0.
- No paid APIs, hosting, domain, subscription, KYC fee, wallet top-up, or paid fallback.
- Revenue is counted only after settlement into an owner-controlled account with transaction evidence.
- All five gates must pass before any commercial execution.

## 2. Official-source findings

### 2.1 Apify Store
Official Apify Store Publishing Terms (page last updated February 20, 2026; checked 2026-11-14):
- Monetization options: Monthly Rental, Pay per Result, Pay per Event.
- Creator remuneration: 80% of user-paid Actor fees. Pay-per-result/event remuneration may be reduced by the relevant Actor platform usage costs depending on configuration.
- KYC is mandatory before any payout. The terms list government ID, proof of address, tax documentation and potentially beneficial ownership information.
- Minimum payout: USD 20 for PayPal; USD 100 for other payout options. Below-threshold balances roll over, but balances continuously below threshold for 12 months may be forfeited.
- Monthly invoice is generated after month-end; creator has 3 days to approve/dispute.
- Creator retains IP in Actor but grants Apify a worldwide, non-exclusive, royalty-free license to host, store, run, display, market and distribute the Actor.
- Actor must be maintained. Creator must respond to reported issues within 14 days and urgent Apify emails within 3 business days.
- Actor naming/branding must not imply unauthorized affiliation. Unofficial third-party service Actors require a clear disclaimer. Copying another Actor/readme/code is prohibited.
- Publishing documentation does not establish a blanket prohibition on AI-generated Actor code. It also does not grant rights to third-party code/data. AI-generated components must be reviewed for originality, licensing, accuracy, security and third-party terms.
- Official payout docs describe PayPal, Wise and other payout methods, but no verified India-specific creator eligibility/settlement evidence was found in this audit. KYC completion alone is not proof that an Indian bank payout succeeds.

Official references:
- https://docs.apify.com/legal/store-publishing-terms-and-conditions
- https://docs.apify.com/actors/monetize
- https://docs.apify.com/actors/monetize/monthly-payouts
- https://docs.apify.com/actors/monetize/pricing-and-costs
- https://docs.apify.com/actors/publishing/publish

### 2.2 RapidAPI
Official provider payout documentation says payouts are made only through PayPal, in USD. Provider payout schedule delays settlement until the subsequent payout month. The official source set contains a fee discrepancy:
- RapidAPI Payouts & Finance documentation states a 20% marketplace fee.
- A December 9, 2025 RapidAPI support article states a flat 25% fee plus PayPal processing fees (country-dependent).
This conflict must be resolved in writing before any economics model. India PayPal receipt/withdrawal and bank settlement are not verified here.

Official references:
- https://docs.rapidapi.com/v2/docs/payouts-and-finance
- https://docs.rapidapi.com/v2.0/docs/payment-settings
- https://rapidapi.zendesk.com/hc/en-us/articles/19308532866068-How-are-payouts-calculated
- https://rapidapi.zendesk.com/hc/en-us/articles/17777288883988-API-Provider-Payout-Schedule

### 2.3 ApyHub
ApyHub Terms effective April 18, 2026 state an 85/15 publisher revenue split, monthly payout, and Stripe Connect. They also require the publisher to own or have rights to publish the API and prohibit verbatim resale/re-exposure of raw API access.
A separate affiliate agreement dated October 26, 2026 describes 20% commission in months 1–6 and 30% in months 7–18, paid monthly within 15 business days after month-end, with EUR 100 minimum and bank transfer via FirstPromoter. This affiliate route is not the same as API publisher payouts and must not be conflated.
India Stripe Connect publisher onboarding and successful payout settlement are unverified.

Official references:
- https://apyhub.com/terms
- https://apyhub.com/affiliate-terms

## 3. Five-gate status (preliminary)
| Gate | Status | Evidence / reason |
|---|---|---|
| 1. Independent buyer intent / demonstrated demand | UNKNOWN | No project-specific buyer interviews, LOIs, pre-orders, deposits, paid pilots, conversion data or demand evidence for our proposed tools. Marketplace existence is not proof of demand. |
| 2. IP, licensing, data rights and legal permission | UNKNOWN | Apify publishing rules and IP responsibilities are documented; no specific Actor/product design or data-source license matrix exists yet. AI-generated code is not shown to be categorically banned, but each dependency/data source needs rights verification. |
| 3. Fully loaded ₹0 unit economics | FAIL (current evidence) | Apify platform usage can be deducted from creator revenue; test usage consumes prepaid usage. Hosting, compute, proxies, storage, monitoring, support, refunds and maintenance are not proven to remain at ₹0 under commercial load. |
| 4. India seller eligibility and verified payout settlement | UNKNOWN | Apify KYC and payout thresholds are documented, but India-specific payout availability and actual bank settlement are not verified. RapidAPI is PayPal-only; India settlement still unverified. ApyHub uses Stripe Connect for publishers; India eligibility unverified. |
| 5. Autonomous fulfilment and realistic owner workload | FAIL (current evidence) | Apify requires maintenance and issue response within stated deadlines. No tested zero-touch fulfilment, monitoring, support, incident, refund or escalation workflow exists. |

## 4. Distribution route comparison
- Apify Store: strongest documented Actor-native monetization path (80% share, subject to usage costs), but India payout, real zero-cost economics and buyer demand remain unproven.
- RapidAPI: payout dependency on PayPal and conflicting official marketplace fee documentation make it unsuitable for approval until clarified.
- ApyHub: publisher split is documented, but Stripe Connect India eligibility and payout route remain unverified. Affiliate terms are a separate model.

## 5. Decision
P1 remains PRIORITY-1 CANDIDATE / VALIDATION HOLD.
No route passes all five gates. No Actor/product is approved. No account creation, build, listing, registration, publication, outreach, paid use or spending is authorized.
No revenue has been earned or settled; ₹0 spend remains the ledger position.

## 6. Required next evidence
1. Obtain written confirmation from Apify of India individual/company creator eligibility, available payout rails for India, tax/KYC documents and actual bank settlement route.
2. Resolve RapidAPI 20% vs 25% marketplace fee discrepancy and confirm India PayPal payout/withdrawal eligibility.
3. Obtain ApyHub confirmation of India-based publisher Stripe Connect onboarding and bank payout availability, separately from affiliate terms.
4. Build a fully itemized zero-cost resource model for a candidate Actor, including development/testing, runtime, proxies, storage, logs, monitoring, support, refunds and maintenance. Do not assume free quotas are commercially sustainable.
5. Gather buyer-intent evidence for specific candidate tools without outreach until a separate authorization/gate plan permits it.
6. Identify source/data licenses and IP provenance for each proposed Actor function.

## 7. Evidence quality note
This report records official platform documentation and explicit unknowns. Platform-level fees, payout rails, free tiers and marketplace availability are not treated as evidence of actual earnings. No median creator earnings or project-specific demand figures were found in the reviewed sources; none are inferred.
