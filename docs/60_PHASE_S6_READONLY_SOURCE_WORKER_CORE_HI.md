# Phase S6-A — Read-only source snapshot worker core (2026-11-18)

## Executive status

**S6 CORE IMPLEMENTED / 20 UNIT TESTS PASS IN EPHEMERAL ENGINEERING SANDBOX / LIVE NETWORK DISABLED / GITHUB VALIDATION PENDING.**

This increment adds a deterministic source-capture policy layer and a specialist worker. It does not create a live crawler, scheduler, model agent or publisher.

## 1. Source policy

Created config/source_domain_policy.v1.json with an exact-host allowlist limited to the original P1/P2 research domains:

- P1: docs.apify.com, apify.com, rapidapi.com, apyhub.com.
- P2: nlnet.nl, wordfence.com, 0din.ai, metaculus.com, superteam.fun, unifiedpatents.com, primeintellect.ai.

No wildcard or subdomain expansion. Domain allowlisting is not a claim that every page on a marketplace host is primary evidence; source content remains untrusted. Default grades are A only for the official Apify documentation host and B for the other official platform/support hosts.

Limits: 1 MB page body, 64 KiB robots.txt, 15-second transport timeout contract, maximum three same-host redirects, HTTPS only, HTML/plain text/JSON only. Sensitive query parameters, IP-literal URLs, userinfo and non-standard ports are rejected.

## 2. Robots, rate-limit and trust controls

The policy requires robots.txt evaluation before a page snapshot. A 404/410 robots file is treated as unavailable under the standard robots model; 401/403/429/5xx or a disallow rule fail closed. A 429 returns Retry-After to the controller and does not trigger an automatic retry. Page 403 is blocked. Cross-host final URLs, oversized responses and unsupported content types are blocked.

HTML parsing strips script/style/noscript/template/svg text. Raw bytes are SHA-256 hashed. Public page text is marked UNTRUSTED_DATA_ONLY and is never treated as agent instructions.

## 3. Worker contract

Created src/zcira_control/source_fetcher.py and src/zcira_control/source_worker.py.

The source worker:
- validates the task against the existing task schema and deterministic mission policy;
- accepts only source_snapshot tasks assigned to official_source_worker_a or official_source_worker_b;
- requires READ_PUBLIC, PARSE_PUBLIC and HASH_PUBLIC;
- rejects paid routes, external actions, publisher writes and priority drift;
- validates source_snapshot and evidence objects against their Draft 2020-12 schemas;
- emits evidence proposals with reviewer_verdict=PENDING, gate_status=UNKNOWN and model_provider=null;
- returns raw page bytes only in memory. content_ref remains null until the S7-B publisher can persist and verify the immutable content blob.

## 4. Deliberate live-network block

No live network transport is shipped or enabled. The worker accepts only an explicitly marked deterministic test transport. The source policy requires live_network_enabled=false and dns_pinning=false. A future live transport must pin the resolved public IP to the TLS connection, validate certificate/SNI, enforce same-host redirects, disable proxies and apply egress controls. DNS preflight alone is not sufficient protection against rebinding.

No public source was fetched in this phase. Robots/HTTP behaviors were tested only with deterministic fixtures. No account, cookie, credential, model call or external contact was used.

## 5. Tests and policy reconciliation

Added tests/test_source_fetcher.py and tests/test_source_worker.py. 20/20 tests passed in an isolated assistant engineering sandbox. These are not yet the GitHub Actions result; the next push-triggered S7-A run must validate them.

The S7-A workflow path had been denied by the original mission registry. This was reconciled narrowly: only .github/workflows/zcira-readonly-validation.yml is now in the mission allowlist. The broad workflow deny rule was removed; every other workflow path remains outside the allowlist and is rejected. The control-plane test fixture now enforces this exact exception.

## 6. Actual state and next actions

- S5 real LangGraph integration: PASS, 3/3 tests; full suite 109 passed / 1 expected skip on run 44228822825.
- S6 source worker core: implemented; GitHub validation pending.
- S6 live network: DISABLED.
- S6 workers scheduled/executed: 0.
- S7-B publisher-only enforcement: not started.
- S8 Cloudflare Worker/Cron/D1: not deployed.
- Durable source content_ref: null pending publisher.
- Spend ₹0; settled revenue evidence ₹0; commercial HOLD.

Next: run S7-A against this S6 increment; then design and test a pinned TLS transport and durable raw-source blob persistence before any live public fetch. Only after those gates may two read-only research workers be enabled.
