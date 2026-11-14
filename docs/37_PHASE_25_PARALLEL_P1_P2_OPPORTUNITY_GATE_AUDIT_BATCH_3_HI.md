# Phase 25 — Parallel P1/P2 Opportunity Gate Audit (Batch 3)
Audit date: 2026-11-14 (Asia/Kolkata)
Project ID: ZCIRA-2026-11-13
Status: RESEARCH ONLY / NO SUBMISSIONS / NO COMMERCIAL EXECUTION

## 1. Scope and non-negotiable controls
This batch continues directly from PROJECT_CONTINUITY.md and docs/36. The P2 destination set and category IDs are preserved exactly: PATROLL; Solana India grant; Superteam agent listings; Wordfence; Vesuvius; Metaculus (free only); NLnet; 0din; Gray Swan; Devpost; Kaggle; Prime Intellect only if paid bounties reappear. IDs #138,139,141,142,143,144,145,147,155,162,164,170. No category remapping.
No account creation, KYC, legal terms acceptance, proposal, application, submission, security test, patent research submission, buyer/platform outreach, build, publication, paid use, wallet funding or spend occurred.

## 2. Critical correction: Apify canonical terms version
The live canonical URL https://docs.apify.com/legal/store-publishing-terms-and-conditions now explicitly renders "Last updated: September 15, 2026". This matches the official preview pages. The prior Batch 2 statement that the canonical page rendered February 20, 2026 was based on an older fetched page snapshot and is superseded by the current canonical page. Version discrepancy is now CLOSED in favour of Sep 15, 2026 as the current published canonical terms.
The current canonical terms confirm:
- Creator payout is 80% of user fees less applicable Platform usage costs for corresponding Actor runs, as configured.
- Promotional Users (coupon, hackathon, free trial, Apify promotional credit) are paid using the highest Store Discount Tier configured for the Actor, irrespective of actual spend tier/price; Apify determines Promotional User status.
- Monthly invoice after calendar month; creator has 3 days to approve/dispute, otherwise deemed approved.
- Minimum payout $20 PayPal / $100 other methods; below-threshold balance rolls over, but a balance below threshold for 12 continuous months is forfeited.
- KYC is mandatory for Verified Creator payout.
- Creator retains IP but grants Apify worldwide, non-exclusive, royalty-free rights to host, store, run, display, market and distribute Actor.
- Creator bears third-party service costs; maintenance best-effort required; issues must be addressed within 14 days and urgent Apify email within 3 business days.
Official canonical source: https://docs.apify.com/legal/store-publishing-terms-and-conditions
Supporting official preview source: https://www.pr-2205.preview.docs.apify.com/legal/store-publishing-terms-and-conditions
Important: this resolves document version only. It does not establish India creator eligibility, India bank settlement, zero-cost operation, or product-specific buyer demand. P1 gate statuses unchanged.

## 3. P2 destination findings

### 3.1 PATROLL — identity clarified; one live named contest
PATROLL is not a cybersecurity bug bounty programme. Unified Patents describes it as a crowdsourced prior-art contest platform: researchers find prior art against patents owned/asserted by patent assertion entities/non-practicing entities; submissions include prior-art evidence and invalidity claim charts.
A Unified Patents news post dated Oct 19, 2026 announces a named $2,000 cash-prize contest seeking prior art on at least claim 1 of US Patent 10,397,374 (IOENGINE, LLC), with contest expiry Nov 21, 2026. PATROLL researchers must use Pearl to generate claim charts; each researcher can generate up to 30 invalidity claim charts/month. Claim charts must address every limitation of challenged claim and may require multiple prior-art references.
Official sources:
- https://www.unifiedpatents.com/insights?offset=1792587600527
- https://patroll.unifiedpatents.com/researcher-agreement
- https://patroll.unifiedpatents.com/terms-of-use
- https://support.unifiedpatents.com/hc/en-us/articles/115002498773-How-to-submit-a-PATROLL-Contest-response
- https://support.unifiedpatents.com/hc/en-us/categories/115000269874-PATROLL
Researcher Agreement states participant must be legal resident of country of residence and age of majority. It allows only one account. Taxpayer identification, payment information and additional tax documents may be required. Contest winner and award amount/distribution are at company's sole discretion; contest may be changed/terminated without award. No cash equivalent guaranteed. Terms grant Unified Patents a royalty-free, irrevocable, perpetual, worldwide, exclusive, fully sublicensable licence to use, modify, adapt, publish, distribute and create derivative works from submitted content. Prize/payment terms depend on individual contest and researcher agreement.
Disposition: NAMED LIVE CONTEST / HIGH IP-RIGHTS RISK / PAYOUT UNKNOWN. India is not explicitly excluded in the retrieved researcher agreement, but India bank settlement and exact contest rules/payment schedule are not verified. Do not enter until full contest-specific terms, payment rail, IP licence implications and owner approval are reviewed. Not passive income; requires substantial human patent prior-art and claim-chart work.

### 3.2 Vesuvius
Search did not identify an official Vesuvius security bounty or a named active paid contest matching the original P2 destination. Search results were dominated by unrelated Vesuvius plc corporate material. No authoritative active reward terms, scope, India eligibility or payout rail verified.
Disposition: UNKNOWN / HOLD. Preserve original destination; do not invent a programme or substitute unrelated entity.

### 3.3 Kaggle — named current example excluded
A currently listed "Predict Customer Value" competition (rf2026) has 22 days remaining in the indexed rules, but it is explicitly invitation-only and requires a Columbia email address; teams are not allowed. It therefore cannot be treated as an open India opportunity absent the required invitation and affiliation. Foundational rules say global participation is generally permitted subject to exclusions, prize documentation and local law, but the specific competition's Columbia-only invite gate controls.
Source: https://www.kaggle.com/competitions/rf2026/rules
The rules include no-purchase entry, but prize eligibility still requires invitation and compliance. Potential winners provide requested prize acceptance documents within two weeks; prize is awarded about 30 days after receipt of required documents. Taxes are winner responsibility. No India payout rail or prize amount for this named competition was established in the reviewed page.
Disposition: THIS NAMED EVENT NOT ELIGIBLE ON CURRENT EVIDENCE. Kaggle platform as a whole remains conditional only; no suitable open named competition with full India payout and IP terms found in this batch.

### 3.4 Gray Swan
Official Gray Swan article (June 24, 2025) reports Proving Ground weekly challenges starting June 25, 2025 and historical $370,000+ payments across global challenges. This is historic programme information, not proof of an open paid challenge on Nov 14, 2026. No current challenge rules, prize schedule, eligibility, India payout or payment terms were located in authoritative current sources.
Source: https://www.grayswan.ai/news/introducing-the-gray-swan-ai-proving-ground
Disposition: HISTORICAL PAYOUT SIGNAL ONLY / CURRENT PAID INVENTORY UNKNOWN / HOLD. Exclude employment listings.

### 3.5 Prime Intellect
Current official Security Policy states:
- Scope includes public-facing infrastructure and *.primeintellect.ai APIs.
- Reports must be sent only to security@primeintellect.ai with reproduction steps, impact assessment and evidence.
- Automated vulnerability scanning without prior written authorization, DoS/DDoS, social engineering, physical testing and actions risking unauthorized data access/modification/destruction are prohibited.
- Valid previously unknown vulnerabilities may be compensated at security team's discretion based on severity, report quality and impact; no fixed reward table.
- KYC may require legal name/address, government ID and tax information.
Source: https://www.primeintellect.ai/security
A separate Prime Protocol GitHub security document states there is currently no formal bug bounty programme, though significant responsible disclosures may be rewarded at discretion. This is a distinct protocol scope and should not be confused with the Prime Intellect AI public-facing security policy.
Source: https://github.com/PrimeIntellect-ai/protocol/blob/main/SECURITY.md
Disposition: DISCRETIONARY SECURITY DISCLOSURE ONLY / NO GUARANTEED REWARD / INDIA PAYOUT UNKNOWN. No testing or report sent.

### 3.6 Superteam Earn — exact opportunity economics and eligibility

#### A. Vaultline Security Audit Grants for Colosseum Projects
Listing details: 10 audit grants, up to 4,000 USDC each, but this is audit-service credit applied directly to Vaultline's audit, not cash. Eligible projects had to participate in Colosseum Hackathon, have near feature-complete Solana code and respond to audit findings. Applications closed Oct 31, 2026; winners announced Nov 2. Thus it is expired and not cash revenue.
Source: https://superteam.fun/earn/listing/vaultline-security-audit-grants-for-colosseum-projects-up-to-4000-usdc-each/
Disposition: EXPIRED / NON-CASH SERVICE CREDIT / EXCLUDE.

#### B. MozaikPay — Show us how you use MozaikPay
Global listing advertises $500 USDC total: $150 first, $125 second, $75 third, three $50 bonuses. Requires a 30–60 second Spanish TikTok/Reel, real MozaikPay account visible, sponsored disclosure, public account, and more than 50% of creator's audience located in Chile and Colombia combined. Must submit video link, audience analytics screenshot and MozaikPay username. Winner announcement Nov 19, 2026.
Source: https://superteam.fun/earn/listing/mozaikpay-video-chile-colombia/
Disposition: NOT A FIT ON CURRENT EVIDENCE. The required audience geography and real product account are not established; the task is a one-off creator campaign, not automated recurring revenue. Account setup, product availability, IP/usage rights and India payout would need verification. No participation.

#### C. Panta x NectarFi Trading Competition Bounty
Listing advertises 500 USDG total (100 USDG each for five winners). Requires signup on Panta, at least one trade of $1 or more on a NectarFi market, original content and audience distribution. Anti-bot/fake engagement prohibition. Content may be reviewed, shared, repurposed or amplified by Panta, NectarFi, SuperteamNG and ecosystem partners. Winner announcement Nov 26, 2026.
Source: https://superteam.fun/earn/listing/panta-x-nectarfi-trading-competition-bounty/
Disposition: REJECT UNDER ₹0 RULE because mandatory $1 trade requires capital; content reuse rights also require consideration. No account/trade/content created.

#### D. MultiHopper Build & Route Challenge
Listing currently shows $5,000 USDC prize pool (3,000/1,250/750) and advertises up to $50,000 plus revenue share, but prize pool is conditional and volume-driven. Requires shipping a working Solana product integrating MultiHopper, production onboarding, at least $100,000 qualifying production transaction volume per product, security/functionality/genuine-use review, live product/demo/repository and verified transaction evidence. Devnet volume does not count. Product integrations earn 0.25% of qualifying full-fee transfer volume; revenue share requires partner onboarding and agreed terms. Entry page itself notes draft terms and that dates/variable award support must be confirmed; it also says a project must integrate before submission.
Source: https://superteam.fun/earn/listing/multihopper-build-and-route-challenge-up-to-dollar50000-revenue-share-1
Disposition: NOT A ZERO-COST QUICK REVENUE ROUTE. Substantial product build, security review, production onboarding and customer transaction volume are prerequisites. It may be a later product/business route only if separate funding and costs are fully covered; currently HOLD and no build.

#### E. India payout reminder
Superteam India states partner projects pay contributors directly in USDC or the partner's native token; Superteam does not pay from its own treasury. A token prize is not automatically INR bank settlement.
Source: https://in.superteam.fun/
Disposition across all listings: no payout is counted as revenue until token is actually received in owner-controlled wallet and then, if the project requires bank revenue, successfully converted/settled with evidence and no unfunded cost.

## 4. Consolidated P2 status
| Destination | New verified result | Status |
|---|---|---|
| PATROLL | One live $2,000 prior-art contest, broad exclusive content licence, payment terms discretionary | CONDITIONAL / HIGH IP RISK |
| Vesuvius | No matching official paid programme found | UNKNOWN / HOLD |
| Kaggle | Named rf2026 event invitation-only and Columbia email required | NOT ELIGIBLE ON CURRENT EVIDENCE |
| Gray Swan | Historic $370k+ challenge payout; no current open paid rules verified | UNKNOWN / HOLD |
| Prime Intellect | Discretionary security reward; strict no-scan-without-authorization rules; KYC possible | CONDITIONAL / HOLD |
| Superteam Vaultline | Expired; audit service credit not cash | EXCLUDE |
| Superteam MozaikPay | Spanish video + >50% Chile/Colombia audience + real account | NOT FIT ON CURRENT EVIDENCE |
| Superteam Panta/NectarFi | Mandatory $1 trade; content reuse rights | REJECT UNDER ₹0 RULE |
| Superteam MultiHopper | Requires product, production onboarding, $100k volume; prize conditional | LATER / HOLD |

NLnet UOI remains paused as recorded in Batch 2. 0DIN and Wordfence remain conditional research-only bounty routes with India payout unverified. Metaculus remains human forecast-only, not automation. No P2 route passes all five gates.

## 5. P1 Apify gate status after current canonical terms correction
- Current canonical terms version: Sep 15, 2026, confirmed.
- Governing document version ambiguity: CLOSED.
- India creator eligibility: UNKNOWN.
- India payout/bank settlement: UNKNOWN.
- Fully loaded ₹0 economics: FAIL (metered platform/third-party usage and other operating obligations remain).
- Product-specific buyer demand: UNKNOWN.
- Autonomous fulfilment/workload: FAIL / not proven.
- IP/data rights: still requires product-level source/dependency/data provenance and legal review.
Overall P1: PRIORITY-1 CANDIDATE / VALIDATION HOLD. No account, KYC, Actor build, test, listing, publication or outreach.

## 6. Ledger
- Spend authorized: ₹0.
- Spend incurred: ₹0.
- Settled revenue evidenced: ₹0.
- Approved products: 0.
- Applications/submissions: 0.
- Accounts/KYC: 0.
- Outreach: 0.
- Build/test/publication: 0.
- Commercial execution: HOLD.

## 7. Next sequence
Phase 25 Batch 4:
1. Close remaining P2 evidence gaps without expanding the locked destination set: 0DIN payment rail/India eligibility, Wordfence India PayPal compatibility at programme level, Metaculus current named tournament prize/payment terms, Kaggle search for an open non-invitation competition with explicit cash prize and full terms, Gray Swan current programme status, Vesuvius identity/source ambiguity.
2. PATROLL: retrieve current live contest-specific rules and verify whether the Nov 21, 2026 contest remains open; evaluate exclusive perpetual IP licence and payment terms before any owner decision. Do not create researcher account or submit.
3. P1: current canonical terms version now settled; focus next on public official India creator payout eligibility, creator payout methods and zero-cost customer-run cost allocation. No platform contact without explicit authorization.
4. Preserve unknowns as UNKNOWN. No account, KYC, legal acceptance, submission, testing, outreach, build, publication, paid use or spend.

---
Audit boundary: official-source research only. No external contact, account, testing, build, submission or spend.