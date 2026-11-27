# Phase S6-B2 — GitHub-hosted runner egress-control feasibility audit (2026-11-19)

## Executive decision

**S6-B1 PINNED TLS TRANSPORT: PASS. S6-B2 PROVIDER-MANAGED EGRESS FIREWALL: NOT AVAILABLE ON THE SELECTED STANDARD RUNNER. LIVE NETWORK: HOLD.**

The selected runtime remains the public repository's standard \`ubuntu-24.04\` GitHub-hosted runner. Official GitHub documentation says GitHub-hosted runners have public-internet access by default. GitHub does not provide a per-job provider-managed egress firewall for this standard runner class.

## 1. Official documentation findings

1. GitHub's private-networking overview states that GitHub-hosted runners have public internet access by default. The supported private-networking approaches include API Gateway/WireGuard overlays and Azure VNET, but those are separate network architectures, not a standard-runner egress policy toggle:
   https://docs.github.com/en/actions/concepts/runners/private-networking

2. GitHub's standard runner reference warns that the outbound IP ranges are shared across GitHub customers and that allowlisting the full ranges broadens access to unrelated workloads. It recommends static-IP larger runners or self-hosted runners instead:
   https://docs.github.com/en/actions/reference/runners/github-hosted-runners

3. Static IP ranges are a larger-runner feature. GitHub's documentation says larger runners are available to organizations and enterprises on GitHub Team or GitHub Enterprise Cloud; static IP assignment requires GitHub Enterprise Cloud:
   https://docs.github.com/en/actions/how-tos/manage-runners/larger-runners/manage-larger-runners
   https://docs.github.com/en/actions/reference/runners/larger-runners

4. GitHub's Azure private-networking documentation says private networking applies to larger runners; standard GitHub-hosted runners are not supported:
   https://docs.github.com/en/enterprise-cloud%40latest/admin/configuring-settings/configuring-private-networking-for-hosted-compute-products/about-azure-private-networking-for-github-hosted-runners-in-your-enterprise

## 2. Zero-cost eligibility decision

| Candidate | Egress isolation | Zero-cost fit | Decision |
|---|---|---|---|
| Standard public GitHub runner | No provider-managed per-job egress firewall | Public standard compute is the selected free route, but egress isolation is not supplied | Keep for deterministic tests only |
| Larger runner with static IP | Static IP allowlisting available | Requires paid/Enterprise plan eligibility; not established as ₹0 | NOT ELIGIBLE |
| Larger runner + Azure VNET | Network policy can be controlled in VNET | Requires larger-runner eligibility and Azure subscription/network resources | NOT ELIGIBLE |
| Self-hosted runner | Owner-controlled firewall possible | Explicitly prohibited as a runtime dependency | REJECTED |
| Runner-local firewall/network namespace | Technically possible as defense-in-depth | No new paid service required, but not provider-managed and not yet audited | CANDIDATE ONLY |

The full GitHub Actions IP ranges are not an acceptable substitute for exact egress control because they are shared with unrelated GitHub workloads. A list of GitHub IP ranges is also not a stable per-runner identity.

## 3. Security and operational disposition

- Do not enable live source fetching on the basis of application-level DNS pinning alone.
- Keep \`dns_pinning=false\`, \`egress_controls_audited=false\`, and \`live_network_enabled=false\` in the canonical source policy.
- No runner-local firewall, network namespace, proxy or egress bypass test was executed. This would require a separately reviewed security-control test plan and must not be claimed as audited.
- No live public source request was made by the S6 worker.
- No account, Enterprise upgrade, Azure subscription, billing, payment method or self-hosted runner was created or configured.
- The existing read-only validation workflow remains \`contents: read\`; it is not converted into a live crawler.

## 4. S6-C storage design adjustment

The original S6-C wording suggested durable raw-page storage. The safer default is revised to **metadata-only immutable evidence snapshots**:

- Persist canonical JSON containing source URL, exact host, publisher, capture time, last-modified time, HTTP status, raw-body SHA-256, bounded excerpt (maximum 2,000 characters), trust boundary and provenance.
- Do not persist complete third-party HTML/JSON page bodies by default. Their copyright/licence terms may not permit republication in a public repository.
- Keep raw bytes in memory only for hashing and parsing, then discard them.
- Store the canonical metadata envelope as a content-addressed Git object through the future single-writer publisher; \`content_ref\` points to that immutable envelope, while \`content_sha256\` remains the digest of the transient raw response bytes.
- Full raw content may be retained only when the exact source licence or written permission clearly allows it and the data contains no personal/customer information.
- No snapshot publication or GitHub write is performed by research workers.

This adjustment preserves reproducible evidence without turning the public repository into a mirror of copyrighted source pages.

## 5. S6-B acceptance status

- S6-B1 transport implementation: PASS.
- GitHub Actions run: https://github.com/manish91082-coder/zero-cost-internet-revenue-automation/actions/runs/44451628361
- Run ID: 44451628361; job ID: 135316732485; head: \`1c66b1c74af3d67100faf28450b103748c5bb342\`.
- 47 hash-locked packages; pip check PASS.
- Real LangGraph integration: 3 passed.
- Full pytest: 150 passed, 1 expected skip, 6 subtests passed.
- S6-B2 provider-managed egress isolation on standard runner: NOT AVAILABLE / not eligible.
- Runner-local egress controls: untested and unaudited.
- Live source fetch: disabled; 0 requests.
- S6-C metadata-only snapshot contract: next.

## 6. Next action

Proceed with S6-C metadata-only immutable snapshot envelope, canonical serialization, content hash and fetch-back contract. Keep raw third-party page bytes ephemeral by default. Do not enable live source fetching until a separately audited, zero-cost egress-control path exists.


## 7. Post-report canonical revalidation

After the S6-B2 report and policy update were committed, GitHub Actions run 44451871881 revalidated the exact checkpoint:

- URL: https://github.com/manish91082-coder/zero-cost-internet-revenue-automation/actions/runs/44451871881
- Head: \`137acb24160559c09e4bdae6920330ea32dad53d\`
- Conclusion: success.
- 47 hash-locked packages installed; \`pip check\` passed.
- Real LangGraph integration: 3 passed.
- Full pytest: 150 passed, 1 expected skip, 6 subtests passed.

This run validates the report/config checkpoint. It did not perform a live source request, egress firewall test, or cloud deployment.


## 8. 2026-11-27 alternate-runtime revalidation — no eligible egress-isolated ₹0 failover found

This addendum rechecks candidate runtimes without creating accounts, accepting terms, configuring billing, deploying, testing security controls or making live source requests.

### 8.1 GitHub Actions standard runner

Official GitHub documentation states that hosted runners have public-internet access by default and are shared across customers. Azure VNET networking provides outbound network-policy control, but it is available only for larger runners; standard runners are unsupported. The documented configuration requires GitHub Team/Enterprise eligibility and Azure VNET resources. This does not meet the current strict ₹0 standard-runner design.

Sources:
- https://docs.github.com/en/enterprise-cloud@latest/actions/concepts/runners/private-networking
- https://docs.github.com/en/enterprise-cloud@latest/admin/configuring-settings/configuring-private-networking-for-hosted-compute-products/about-azure-private-networking-for-github-hosted-runners-in-your-enterprise

### 8.2 Cloudflare Containers / Sandbox

Cloudflare Sandbox/Container outbound handlers document allowed-host / denied-host controls and default-deny behavior when internet access is disabled. This is technically relevant to egress isolation, but it is not the selected Workers Free Cron product.

Official pricing sources conflict:
- Product-specific Containers pricing says Free=N/A and that the included 25 GiB-hours / 375 vCPU-minutes / 200 GB-hours are part of the $5/month Workers Paid plan.
- The general Cloudflare plans page currently displays a Free allocation for Containers.

Decision: BLOCKED_OFFICIAL_PRICING_CONFLICT. No account-level eligibility, billing state or no-payment-method status has been verified. Because the product-specific page explicitly requires Workers Paid, do not assume the generic page is sufficient to activate a strict ₹0 runtime. No account creation or deployment.

Sources:
- https://developers.cloudflare.com/containers/guides/outbound-traffic/
- https://developers.cloudflare.com/containers/platform/pricing/
- https://www.cloudflare.com/plans/

### 8.3 Deno Deploy

Deno Deploy supports Deno.cron(), but its official pricing page lists the Free plan at 1 million requests/month, 20 GiB egress, 10 active CPU hours and 150 GiB-hours memory. The official changelog says free organizations pause applications after usage limits are exceeded and that linking a credit card is required to lift restricted Free limits. Deno's current docs also state that Deno Deploy will be sunset in April 2027.

This is not a durable independent failover for a long-lived 24x7 system and does not meet the no-payment-method constraint for unrestricted free limits. Mark INELIGIBLE_LONG_TERM_FAILOVER; no account or deployment.

Sources:
- https://deno.com/deploy/pricing
- https://docs.deno.com/deploy/changelog/

### 8.4 Cloudflare Workers Free

Workers Free remains a possible lightweight Cron/dispatcher path under the locked architecture. It is not an egress firewall for GitHub runners and must not be repurposed as a source-fetch proxy or heavy Python runtime. Account-level no-payment-method eligibility remains UNKNOWN because no account dashboard or activation was performed.

Decision: retain as a future candidate only; not deployed.

### 8.5 Decision

| Candidate | Decision |
|---|---|
| GitHub Actions standard | Keep bounded deterministic CI only; live source fetch remains HOLD |
| GitHub larger runner + Azure VNET | Reject under strict ₹0 / no paid resource rule |
| Cloudflare Workers Free | Keep as future lightweight heartbeat/dispatcher only; account-level no-payment-method eligibility UNKNOWN |
| Cloudflare Containers/Sandbox | Blocked by conflicting official pricing and explicit Workers Paid requirement in product docs |
| Deno Deploy | Reject as long-term failover; credit-card verification and April 2027 sunset |
| Runner-local firewall/network namespace | Not tested or audited; no security-test permission inferred |

No third independent, provider-managed, long-term, egress-isolated runtime has been verified as eligible at ₹0. Therefore:
- dns_pinning=false
- egress_controls_audited=false
- live_network_enabled=false
- live source requests = 0
- S6-B2 remains HOLD

Offline/synthetic evidence-worker tests and metadata-only snapshot work may continue. The architecture is not changed, no paid fallback is introduced, and no account, billing, legal, deployment or security-testing action is authorized.
