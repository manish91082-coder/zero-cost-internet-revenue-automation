# Phase S6-B1 — Pinned-IP TLS transport implementation (2026-11-19)

## Executive decision

**S6-B1 TRANSPORT IMPLEMENTED / AUTOMATED TEST VALIDATION PENDING / LIVE NETWORK DISABLED.**

This increment adds a standard-library HTTPS transport that binds the TCP connection to a resolved numeric public IP while retaining the exact allowlisted hostname for TLS SNI and certificate hostname verification. It is intentionally not enabled for live source collection.

## 1. Canonical source and mission revalidation

The controlling Library archive \`02_complete-research-hi.md\`, version 1, was reopened from the Library and its full SHA-256 verified:

- Archive size: 1,402,707 bytes.
- Archive SHA-256: \`c61be12a55385d0780a6a5bdf45f2fc22086be9edf6bbba96e78cfb0726d1e5e\`.
- Embedded destination section canonical scope (heading \`# भाग 7: plan/destinations-hi.md\` through immediately before its SOURCE END marker): \`7e45078990d99d14e34a26befb3bde2b8260fc53f35c6000fbe20fb741a36a24\`.
- Original six batches: 219 categories and 3,482 source occurrence slots.
- P1/P2/P3/P4/P5/B/M priority order unchanged.
- Category #24 remains B.
- The exact Appendix A and destination source sections remain controlling; no platform/category mapping was changed in S6-B1.

## 2. Pinned-IP connection design

New module: \`src/zcira_control/pinned_tls_transport.py\`.

The transport:

1. Resolves the exact allowlisted hostname once per transport instance/task.
2. Rejects the complete DNS answer set if any returned address is private, loopback, link-local, multicast, reserved, unspecified, scoped or otherwise non-global.
3. Pins one public numeric IP for the whole task. It does not retry against another IP.
4. Opens the TCP socket directly to the numeric IP, avoiding a second hostname lookup at connect time.
5. Uses \`ssl.create_default_context()\`, requires CERT_REQUIRED and hostname checking, enforces TLS 1.2 or newer, and disables TLS compression.
6. Keeps the original hostname as SNI and the certificate-verification name.
7. Sends only GET with a fixed small header set. No proxy, cookie, authentication, JavaScript, custom Host header or credential forwarding.
8. Handles redirects manually: HTTPS, exact same hostname, standard port 443, maximum three redirects.
9. Rejects non-identity content encoding; checks Content-Length and streamed bytes; uses a bounded deadline.
10. Does not retry HTTP 429/403 or transport failures.

One transport instance is restricted to one exact hostname, so robots.txt and the requested page share the same DNS pin. A worker must construct one transport instance per source task.

## 3. Explicit activation gates

The source policy now carries three independent booleans:

- \`dns_pinning\`
- \`egress_controls_audited\`
- \`live_network_enabled\`

A pinned transport is accepted by the source-fetch pipeline only when all three are true. The checked-in \`config/source_domain_policy.v1.json\` keeps all three false. The S6 worker policy also keeps live execution disabled.

**Why live fetching remains disabled:** application-level DNS pinning is not the same as a runner-level egress firewall. The standard GitHub-hosted runner currently has no demonstrated per-job outbound allowlist in this repository. The existing validation workflow needs GitHub and PyPI access; no restrictive egress rule has yet been implemented or proven without breaking runner control-plane traffic. The transport code alone is not sufficient to claim an egress audit.

The transport can be unit-tested with injected fake resolver, socket and HTTP connection factories. The new tests do not open a real network socket.

## 4. New tests

New file: \`tests/test_pinned_tls_transport.py\`.

Coverage includes:
- DNS pin reuse and one-host-per-task restriction.
- IPv4/IPv6 public address handling.
- Private, loopback, link-local, multicast and mixed public/private DNS rejection.
- Direct numeric-IP TCP connection with original hostname SNI.
- Certificate and hostname verification requirements.
- TLS 1.2 minimum and compression disablement.
- Full source-fetch pipeline using only fake DNS/socket/HTTP dependencies.
- Same-host redirect, cross-host redirect, HTTPS downgrade and redirect-count rejection.
- Content-Length and streamed byte limits.
- Compressed-response rejection.
- HTTP 429 Retry-After with no retry.
- Checked-in policy gate remains disabled.

The existing source-fetcher unit tests were extended to validate the new policy flags. GitHub Actions is expected to run the full hash-locked suite after this commit; no test result is claimed before that run completes.

## 5. Actual status and next gate

- Pinned-IP TLS transport code: committed candidate.
- Fake-network unit tests: committed candidate; GitHub execution pending.
- Source worker live network: DISABLED.
- Public source requests by this worker in this increment: 0.
- Durable raw-source snapshots: not implemented; S6-C remains pending.
- Runner-level egress restrictions: NOT AUDITED.
- Source workers scheduled/running: 0.
- S7-B publisher: not started.
- S8 Cloudflare Worker/Cron/D1: not deployed.
- Spend: ₹0; settled revenue evidence: ₹0; commercial execution HOLD.

Next: S6-B2 runner egress-control feasibility audit, then S6-C durable content-addressed snapshots and fetch-back verification. Do not flip the live-network flags until the egress gate is independently evidenced and the durable snapshot path is ready.
