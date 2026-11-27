# Phase S6-B2 — alternate free-runtime and egress-isolation revalidation

**तिथि:** 2026-11-27  
**स्थिति:** NO VERIFIED THIRD ₹0 EGRESS-ISOLATED RUNTIME / LIVE NETWORK HOLD  
**Canonical repository:** manish91082-coder/zero-cost-internet-revenue-automation

## 1. Scope and preflight

This is an evidence-only revalidation of alternate public-cloud runtimes for the S6-B2 egress-control blocker. It does not change the S2-B architecture and does not authorize account creation, terms acceptance, billing, payment method, deployment, security testing, live source fetch or external outreach.

Controlling architecture remains:
- Public-repository GitHub Actions standard runners for bounded ephemeral Python execution.
- Cloudflare Workers Free Cron for lightweight heartbeat/dispatcher only.
- D1 as a non-authoritative queue/lease mirror.
- No heavy Python, model inference or source crawler inside Cloudflare Worker.
- GitHub versioned artifacts remain canonical evidence/checkpoint ledger.

## 2. Candidate assessment

### 2.1 GitHub Actions standard runner

Official GitHub documentation states that standard hosted runners have public internet access by default and are shared across customers. Azure VNET private networking gives outbound network-policy control, but it is available only for larger runners; standard runners are unsupported. The documented configuration requires GitHub Team/Enterprise eligibility and Azure VNET resources.

Decision: keep standard runners for deterministic CI only. No provider-managed per-job egress firewall exists on the selected standard runner. Larger runner/Azure VNET is not eligible under the current strict ₹0 constraint.

Sources:
- https://docs.github.com/en/enterprise-cloud@latest/actions/concepts/runners/private-networking
- https://docs.github.com/en/enterprise-cloud@latest/admin/configuring-settings/configuring-private-networking-for-hosted-compute-products/about-azure-private-networking-for-github-hosted-runners-in-your-enterprise

### 2.2 Cloudflare Containers / Sandbox

Cloudflare Sandbox/Container outbound handlers document allowed-host / denied-host controls and default-deny behavior when internet access is disabled. That is technically relevant to egress isolation, but it is not the selected Workers Free Cron product.

Official pricing sources conflict:
- Product-specific Containers pricing says Free=N/A and identifies the included resource allowances as part of the $5/month Workers Paid plan.
- The general Cloudflare plans page currently displays a Free allocation for Containers.

Decision: BLOCKED_OFFICIAL_PRICING_CONFLICT. No account-level eligibility, billing state or no-payment-method status has been verified. Because the product-specific page explicitly requires Workers Paid, do not assume the generic page is sufficient to activate a strict ₹0 runtime. No account creation or deployment.

Sources:
- https://developers.cloudflare.com/containers/guides/outbound-traffic/
- https://developers.cloudflare.com/containers/platform/pricing/
- https://www.cloudflare.com/plans/

### 2.3 Deno Deploy

Official pricing currently lists the Free plan as:
- 1,000,000 requests/month.
- 20 GiB egress/month.
- 10 active CPU hours/month.
- 150 GiB-hours memory/month.

Deno Deploy supports Deno.cron(), but official documentation also states:
- Free organizations pause applications after usage limits are exceeded.
- A credit card is required to lift restricted Free limits.
- Deno Deploy will be sunset in April 2027.

Decision: INELIGIBLE_LONG_TERM_FAILOVER. The card-verification condition conflicts with the strict no-payment-method rule for unrestricted free usage, and the announced sunset makes it unsuitable as a durable continuity dependency. No account or deployment.

Sources:
- https://deno.com/deploy/pricing
- https://docs.deno.com/deploy/changelog/

### 2.4 Cloudflare Workers Free

Workers Free remains a possible lightweight Cron/dispatcher path under the locked architecture. It is not an egress firewall for GitHub runners and must not be repurposed as a source-fetch proxy or heavy Python runtime. Account-level no-payment-method eligibility remains UNKNOWN because no account dashboard or activation was performed.

Decision: retain as a future candidate only; not deployed.

## 3. Machine policy disposition

Updated config/s6_transport_policy.v1.json with candidate-specific eligibility states, explicit Cloudflare pricing conflict, Deno sunset/card-verification conditions and the continuing live-network HOLD.

## 4. Final decision

No third independent, provider-managed, long-term egress-isolated runtime has been verified as eligible at ₹0.

Keep:
- dns_pinning=false
- egress_controls_audited=false
- live_network_enabled=false
- source_worker_pipeline_live_fetch_enabled=false
- Live source requests = 0

Offline/synthetic source-worker tests and metadata-only immutable snapshot processing may continue. Do not weaken egress policy, add paid fallback, create accounts, accept legal terms, configure billing, deploy, perform security testing, contact providers, or spend.

## 5. Next action

Proceed with S7 mechanical publisher isolation design and read-only CI review only. Keep live Git Data writes, publisher credential creation, Cloudflare deployment and S9 unattended pilot disabled until exact zero-cost eligibility and required owner approval are satisfied.
