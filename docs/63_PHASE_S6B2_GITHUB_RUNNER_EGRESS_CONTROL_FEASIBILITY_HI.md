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
