# Phase S7-B correction — claim-level evidence grade ceiling and CI acceptance

**तिथि:** 2026-11-23  
**Project:** ZCIRA-2026-11-13  
**स्थिति:** CODE + FULL READ-ONLY CI PASS / PUBLISHER NOT DEPLOYED

## 1. Actual failures observed and corrected

| Run | Head | Result | Root cause |
|---|---|---|---|
| [44978005047](https://github.com/manish91082-coder/zero-cost-internet-revenue-automation/actions/runs/44978005047) | `916ac33e9ca19ac383996c750faa96ca67f31792` | 189 passed, 3 failed, 1 skipped | Publisher incorrectly required claim grade to equal source default grade |
| [45105528580](https://github.com/manish91082-coder/zero-cost-internet-revenue-automation/actions/runs/45105528580) | `90b0f2e8016ef201bcea21c3ffe073c84bac93d6` | 191 passed, 1 failed, 1 skipped | Test searched substring `raw_body`, incorrectly matching legitimate digest/size metadata keys |
| [45105568160](https://github.com/manish91082-coder/zero-cost-internet-revenue-automation/actions/runs/45105568160) | `c1c2a237a9d795776638cf80914196a46de260ea` | 192 passed, 1 failed, 1 skipped | Same over-broad raw-body assertion |

### Root cause 1: claim grade vs source authority

`default_evidence_grade` is the maximum source authority ceiling, not a mandatory grade for every claim. A primary official source can contain a weak or not-yet-verified claim. The claim may legitimately be downgraded.

Implemented ordering:
`D_UNVERIFIED < C_SECONDARY < B_OFFICIAL_SUPPORT < A_PRIMARY_OFFICIAL`.

A claim grade at or below the source ceiling is allowed. A claim above the source ceiling, or an unknown policy grade, is rejected. Production source policy was not relaxed.

### Root cause 2: raw-body test false positive

The metadata envelope legitimately contains `raw_body_sha256`, `raw_body_size_bytes` and `raw_body_persisted=false`. The previous substring assertion treated the substring `raw_body` as proof that the raw page body itself was persisted.

The test now parses JSON and checks exact forbidden keys `raw_body` / `raw_content`, while asserting the retention flag is false. The publisher's recursive sensitive/raw-field rejection remains unchanged.

## 2. Corrected implementation and regression coverage

- `src/zcira_control/evidence_publisher.py`: grade rank map, source-policy grade validation, claim-grade ceiling check.
- `tests/test_evidence_publisher.py`: positive conservative downgrade path; negative B-ceiling/A-claim test; production source grade assertion; exact raw-payload key checks.
- `config/s7b_publisher_policy.v1.json`: claim-grade ceiling semantics, ₹0/approval boundaries and CI acceptance record.
- `config/research_swarm_roster.v1.json`: publisher core status updated to CI PASS / not deployed.
- No source domain, category, priority or commercial gate was promoted.

## 3. Final GitHub Actions acceptance

<badge>PASS</badge>

- Final code/test head: `7388b8a69ceb75e7a5488de40b83128fb6e31e84`
- Run: [45105601988](https://github.com/manish91082-coder/zero-cost-internet-revenue-automation/actions/runs/45105601988)
- Runner: `ubuntu-24.04`
- Python: 3.12.3
- Hash-locked packages: 47
- `pip check`: PASS
- Real LangGraph integration: 3 PASS
- Full pytest: **193 passed, 1 expected skip, 6 subtests passed**.

The updated policy metadata checkpoint `f17638453f869bfb629aa7456380d03b5ddfa538` also passed run [45105698068](https://github.com/manish91082-coder/zero-cost-internet-revenue-automation/actions/runs/45105698068) with the same result.

The latest roster/config checkpoint `569bf3f0936f38e12ecd9b25f989052ad5f4adb1` passed run [45105701263](https://github.com/manish91082-coder/zero-cost-internet-revenue-automation/actions/runs/45105701263): **193 passed, 1 expected skip, 6 subtests passed**.

## 4. What PASS does and does not mean

PASS covers deterministic code, schema validation, synthetic-store publisher transactions, fake GitHub transport Git Data API sequencing/CAS race tests and fetch-back logic under tests.

It does **not** mean:
- A live GitHub Git Data API write was performed.
- Production evidence was published.
- Publisher has a write token or contents:write workflow.
- Branch protection is enabled.
- A cloud swarm or source worker is running.

GitHub branch metadata reports `protected=false` and `protection.enabled=false`; the repository rulesets collection is empty. Branch protection is therefore **NOT ENABLED / CONFIRMED**. The connected integration cannot read the dedicated protection endpoint (403), but the branch object and rulesets response establish the state.

## 5. Current blockers and safety state

- S6-B2 egress controls: HOLD; live source fetching remains disabled.
- LangGraph durable checkpointer: not implemented.
- Publisher write workflow and write credential isolation: not enabled.
- Actual Git Data API write/fetch-back integration: not performed.
- Cloudflare Worker/Cron/D1: not deployed.
- Seven-day unattended pilot: not started.
- No account, KYC, legal acceptance, billing, external outreach, submissions, product build/listing or spend.
- Spend ₹0; settled revenue evidence ₹0; commercial execution HOLD.

## 6. Mission invariants and next action

- Maximum two read-only research workers; one cooperative publisher.
- P1/P2/P3/P4/P5/B/M order unchanged; Category #24 remains B.
- Five commercial gates remain mandatory; UNKNOWN is never PASS.
- A2.4-B/C and A2.5 remain complete; 3,482 is source occurrence slots, not unique platform identities.

Next: continue the S7-B publisher write-isolation design and a no-production-write Git Data API audit. Do not activate a publisher workflow or create write credentials until the exact owner approval and mechanical isolation requirements are satisfied. Keep live source access disabled until S6-B2 is independently resolved.
