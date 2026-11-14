# Phase 24 — P1 Apify Tool Factory Gate-Validation Audit (Batch 2: India Payout & Settlement)
Audit date: 2026-11-14 (Asia/Kolkata)
Project ID: ZCIRA-2026-11-13
Status: RESEARCH IN PROGRESS / COMMERCIAL EXECUTION HOLD

## 1. Scope
This batch tests the India seller / payout / settlement leg for Apify Store, RapidAPI and ApyHub. It is documentary research only. No account was created, no KYC was initiated, no payout was tested, and no money was received. A payment provider's general India capability is not treated as proof that a specific marketplace has enabled that route for an Indian publisher.

## 2. Apify Store — payout route
Official Apify payout help states:
- Monthly cycle: invoice preparation days 1–10; invoice issued day 11; review/approval days 11–14; payments released days 21–25, with bank processing time varying.
- Minimum threshold: USD 20 for PayPal; USD 100 for wire transfer. KYC approval is required.
- Payout can be delayed/declined by receiving bank or PayPal; a failed/returned transaction is possible.
- Official Apify payout documentation states international wire transfers originate from Czech Republic via SWIFT and use SHA shared fees. Intermediary/recipient bank deductions typically range USD 10–50, dependent on destination/banks. PayPal is described as a lower-fee/faster alternative, but provider fees may apply.
- Apify documentation does not, in the reviewed pages, enumerate India as a guaranteed eligible creator payout country or confirm a successful Indian creator settlement. India availability for the specific Apify creator program remains UNKNOWN until Apify confirms the eligible rail and account profile in writing or a legitimate payout is successfully settled.
- Do not assume Wise is available merely because a general payout page lists it; confirm whether it is enabled for an India-based creator account.

Official references:
- https://help.apify.com/en/articles/10057167-how-developer-payouts-work
- https://docs.apify.com/actors/monetize/monthly-payouts
- https://docs.apify.com/legal/store-publishing-terms-and-conditions

India-side PayPal evidence:
- PayPal India says international-only receivers must verify PAN, add an Indian bank account, select a purpose code and describe the business; after identity confirmation, payments can be received and withdrawn to bank.
- PayPal India commercial fee page lists 4.40% plus fixed fee for international commercial receipts. Currency conversion charges may additionally affect net proceeds; exact conversion route/rate must be checked at transaction time.
- This establishes a general India PayPal receiving facility, not Apify's acceptance of Indian PayPal accounts. The platform-side compatibility remains unverified.

Official references:
- https://www.paypal.com/in/cshelp/article/how-do-i-receive-payments-through-paypal-help667
- https://www.paypal.com/in/business/paypal-business-fees

Apify assessment: payout threshold and process documented; Indian eligibility and actual settlement UNKNOWN. Wire deductions may be material at low payout sizes. No payout test was performed.

## 3. RapidAPI — payout route and fee conflict
Official RapidAPI provider documentation says:
- API providers are paid only via PayPal; no ACH or wire alternative is offered.
- Payout is in USD and is issued after the monthly collection/reconciliation period. Documentation example places receipt in the first week of the second month after the subscription month.
- The main Payouts & Finance documentation states a 20% marketplace fee.
- A RapidAPI Product Support article updated December 9, 2025 states a flat 25% marketplace fee, plus PayPal processing fee (example: 2% of payout, capped at USD 20). It also says disputes/refunds can reduce payout.
- These are contradictory official RapidAPI sources. The later dated support article suggests 25% is the newer rule, but it is not safe to overwrite the conflicting provider documentation without written confirmation from RapidAPI. Model both scenarios only as sensitivities; do not select one as contractually confirmed.
- PayPal India supports international commercial receipts subject to PAN, Indian bank, purpose code and business details; fee page lists 4.40% + fixed fee for international receipts. However, successful RapidAPI-to-Indian-PayPal payout and subsequent bank settlement are not directly evidenced.

Official references:
- https://docs.rapidapi.com/v2.0/docs/payouts-and-finance
- https://rapidapi.zendesk.com/hc/en-us/articles/19308532866068-How-are-payouts-calculated
- https://rapidapi.zendesk.com/hc/en-us/articles/11432098898580-What-payment-methods-are-available-for-payouts
- https://www.paypal.com/in/cshelp/article/how-do-i-receive-payments-through-paypal-help667
- https://www.paypal.com/in/business/paypal-business-fees

RapidAPI assessment: PayPal route is structurally plausible for international India receipts but platform acceptance/settlement is untested; fee remains contractually conflicted. Status UNKNOWN, not PASS.

## 4. ApyHub — Stripe Connect India compatibility
ApyHub's active Terms of Service (effective April 18, 2026) say publisher payouts are monthly via Stripe Connect and show an 85/15 publisher split. This does not itself prove every country is onboardable.

Stripe's official India marketplace/Connect guidance states:
- Stripe services in India are invite-only.
- Connect cross-border funds flows are restricted. In the documented matrix, a non-India, non-US platform generally cannot pay an India connected account through destination charges; the supported exceptions depend on the exact charge type, application fee, account agreement and funds flow.
- Stripe's support page specifically says it generally does not support transfers from non-India platforms to India-based Stripe accounts; it identifies US platforms as supported for this functionality.
- Stripe's India Connect onboarding requirements are configuration- and capability-specific. The India requirements page documents distinct individual, sole-proprietor and company structures for relevant configurations; this does not remove the platform-country/funds-flow restriction.
- Stripe India accounts receive payouts only in INR. ApyHub is ApyHub B.V. (Netherlands) according to its terms, so an ordinary Netherlands-platform-to-India-connected-account payout is not established as supported. ApyHub would need to confirm an approved exception, alternative payout architecture or explicit Indian publisher route.
- Stripe also publishes pricing for Connect in India; where a platform uses a fee-bearing configuration, account/payout charges may apply. ApyHub's own publisher agreement and fee allocation must be checked. No ₹0 assumption is allowed.

Official references:
- https://apyhub.com/terms
- https://support.stripe.com/questions/stripe-india-support-for-marketplaces
- https://support.stripe.com/questions/support-for-money-transfers-from-international-platforms-to-india-based-stripe-accounts
- https://support.stripe.com/questions/onboarding-requirements-for-stripe-connect-in-india
- https://support.stripe.com/questions/payout-currency-for-stripe-accounts-in-india
- https://stripe.com/in/connect/pricing

ApyHub assessment: high-risk payout incompatibility indicator for an India-based publisher under ordinary Stripe Connect flows. Treat as FAIL for the currently documented standard route / UNKNOWN for any ApyHub-specific exception until written confirmation. Do not open a Stripe account or incur onboarding cost.

## 5. India payout comparison
| Platform | Published payout route | India-side compatibility evidence | Current decision |
|---|---|---|---|
| Apify | PayPal / wire; thresholds $20 / $100 | PayPal India can receive international business payments after PAN, bank, purpose code and KYC; Apify India creator acceptance not confirmed. SWIFT fees can be $10–$50. | UNKNOWN |
| RapidAPI | PayPal only, USD | PayPal India supports international receipts; RapidAPI-to-India account acceptance and actual settlement untested. Marketplace fee conflict 20% vs 25%. | UNKNOWN |
| ApyHub | Stripe Connect monthly | Stripe documents restrictions for non-India platforms paying India connected accounts; ApyHub Netherlands-to-India standard route not established. | FAIL for standard documented route; UNKNOWN pending written exception |

## 6. Five-gate status update
1. Buyer intent: UNKNOWN. No specific buyer evidence for proposed tools.
2. IP/licensing/data/legal: UNKNOWN. Product-specific source and rights matrix not completed.
3. Fully loaded ₹0 economics: FAIL on current evidence. Apify wire fee deductions ($10–$50 typical intermediary/recipient deductions) and PayPal international receipt fees (4.40% + fixed fee) show payout is not cost-free at the net-settlement layer; runtime and fulfilment costs remain unresolved. RapidAPI fees also apply.
4. India seller eligibility and verified payout settlement: UNKNOWN overall. Apify and RapidAPI routes are plausible but untested; ApyHub standard Stripe Connect route has a documented incompatibility indicator.
5. Autonomous fulfilment: FAIL on current evidence. Maintenance, support and incident response are not proven fully unattended.

## 7. Decision
No platform passes all five gates. P1 remains PRIORITY-1 CANDIDATE / VALIDATION HOLD. No account creation, KYC, Actor build, API listing, publication, customer outreach, paid use or spend is authorized.
Spend authorized/incurred: ₹0 / ₹0. Settled revenue evidenced: ₹0.

## 8. Next required work
1. Obtain written Apify confirmation for India creator eligibility, PayPal/Wise/SWIFT methods, acceptable legal entity type, KYC/tax documents, payout currency and any India-specific restrictions.
2. Obtain written RapidAPI confirmation of the applicable marketplace fee (20% or 25%), India PayPal acceptance, minimum payout, processing fee and expected settlement path.
3. Ask ApyHub whether Indian publishers can be onboarded under its Netherlands Stripe Connect configuration; request the exact Stripe Connect charge type, service agreement, cross-border flow, fees and India bank settlement method. Do not assume an exception.
4. Continue with the zero-cost runtime and support economics model only after the payout routes are sufficiently narrowed.
5. Preserve research-only status; no outreach to buyers or platform applications without separate authorization.
