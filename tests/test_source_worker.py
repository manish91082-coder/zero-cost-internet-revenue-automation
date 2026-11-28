import json
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from zcira_control.source_fetcher import SourcePolicy, SourceRecord, TransportResponse
from zcira_control.source_worker import run_source_snapshot_task

NOW = datetime(2026, 11, 18, 3, 30, tzinfo=timezone.utc)
ROBOTS = b"User-agent: *\nAllow: /\n"
PAGE = b"<html><head><title>Apify actor docs</title></head><body><p>Actor runtime and lifecycle details.</p></body></html>"

ROOT_REPO = "manish91082-coder/zero-cost-internet-revenue-automation"
MISSION = {
    "project_id": "ZCIRA-2026-11-13", "mission_id": "ZCIRA-2026-11-13",
    "canonical_repo": ROOT_REPO, "branch": "main", "state_branch": "evidence-ledger",
    "environment_namespace": "zcira-readonly-research", "state_namespace": "zcira-2026-11-13/evidence-ledger",
    "max_parallel_research_workers": 2, "single_writer_role": "evidence_publisher", "spend_cap_inr": 0,
    "paid_fallback_allowed": False, "trial_credit_dependency_allowed": False,
    "shared_state_with_other_missions": False, "cross_mission_write_allowed": False, "active": True,
    "allowed_paths": ["PROJECT_CONTINUITY.md", "docs/**", "config/**", "schemas/**", "tests/**", "scripts/**", "src/**", "requirements-test.txt", ".github/workflows/zcira-readonly-validation.yml"],
    "denied_paths": ["secrets/**", "private/**"],
    "allowed_action_classes": ["READ_PUBLIC", "PARSE_PUBLIC", "HASH_PUBLIC", "CREATE_INTERNAL_DRAFT", "WRITE_REPO_VALIDATED"],
    "denied_action_classes": ["PURCHASE", "PAID_FALLBACK", "BILLING_ENABLE", "ACCOUNT_CREATE", "KYC", "ACCEPT_TERMS", "CONTACT_EXTERNAL", "SUBMIT", "SECURITY_TEST", "PUBLISH_PRODUCT", "WALLET_SIGN", "TRANSFER_FUNDS"],
}


def make_task():
    return {
        "schema_version": "1.0.0", "project_id": "ZCIRA-2026-11-13", "mission_id": "ZCIRA-2026-11-13",
        "task_id": "zcira-source-snapshot-001", "idempotency_key": "a" * 64,
        "task_type": "source_snapshot", "priority": "P1", "category_id": 1,
        "destination_id": "apify-docs-actors", "status": "QUEUED",
        "created_at": "2026-11-18T03:00:00Z", "updated_at": "2026-11-18T03:00:00Z",
        "attempt_count": 0, "max_attempts": 2,
        "allowed_actions": ["READ_PUBLIC", "PARSE_PUBLIC", "HASH_PUBLIC"],
        "external_actions_allowed": False, "paid_provider_routes_enabled": False,
        "parameters": {"source_url": "https://docs.apify.com/platform/actors", "source_row_ref": "category-1:destination-1"},
        "source_snapshot_ids": [], "evidence_ids": [], "lease_id": None, "checkpoint": None,
        "assigned_role": "official_source_worker_a",
    }


class FakeTransport:
    is_test_transport = True

    def __init__(self, responses):
        self.responses = list(responses)

    def __call__(self, url, policy, max_bytes, same_host):
        return self.responses.pop(0)


class SourceWorkerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.task_schema = json.loads((ROOT / "schemas/v1/task.schema.json").read_text())
        cls.snapshot_schema = json.loads((ROOT / "schemas/v1/source_snapshot.schema.json").read_text())
        cls.evidence_schema = json.loads((ROOT / "schemas/v1/evidence.schema.json").read_text())

    def test_creates_pending_evidence_with_unknown_gate_and_untrusted_boundary(self):
        policy = SourcePolicy({"docs.apify.com": SourceRecord("Apify Documentation", "A_PRIMARY_OFFICIAL", "P1")})
        fake = FakeTransport([
            TransportResponse(200, {}, ROBOTS, "https://docs.apify.com/robots.txt"),
            TransportResponse(200, {"content-type": "text/html"}, PAGE, "https://docs.apify.com/platform/actors"),
        ])
        result = run_source_snapshot_task(make_task(), MISSION, policy, self.task_schema, self.snapshot_schema, self.evidence_schema, transport=fake, now=NOW)
        self.assertEqual(result.status, "COMPLETED")
        self.assertEqual(result.snapshot["fetch_status"], "CAPTURED")
        self.assertEqual(result.evidence_proposal["reviewer_verdict"], "PENDING")
        self.assertEqual(result.evidence_proposal["gate_status"], "UNKNOWN")
        self.assertIsNone(result.evidence_proposal["model_provider"])
        self.assertEqual(result.evidence_proposal["source_snapshot_ids"], [result.snapshot["snapshot_id"]])
        self.assertEqual(result.raw_content, PAGE)

    def test_rejects_non_source_task(self):
        task = make_task(); task["task_type"] = "public_source_research"
        policy = SourcePolicy({"docs.apify.com": SourceRecord("Apify Documentation")})
        with self.assertRaises(Exception):
            run_source_snapshot_task(task, MISSION, policy, self.task_schema, self.snapshot_schema, self.evidence_schema, transport=FakeTransport([]), now=NOW)

    def test_rejects_wrong_agent_role(self):
        task = make_task(); task["assigned_role"] = "evidence_publisher"
        policy = SourcePolicy({"docs.apify.com": SourceRecord("Apify Documentation")})
        with self.assertRaises(Exception):
            run_source_snapshot_task(task, MISSION, policy, self.task_schema, self.snapshot_schema, self.evidence_schema, transport=FakeTransport([]), now=NOW)

    def test_rejects_priority_drift_from_source_registry(self):
        task = make_task(); task["priority"] = "P2"
        policy = SourcePolicy({"docs.apify.com": SourceRecord("Apify Documentation", "A_PRIMARY_OFFICIAL", "P1")})
        with self.assertRaises(ValueError):
            run_source_snapshot_task(task, MISSION, policy, self.task_schema, self.snapshot_schema, self.evidence_schema, transport=FakeTransport([]), now=NOW)

    def test_blocked_source_never_creates_evidence(self):
        policy = SourcePolicy({"docs.apify.com": SourceRecord("Apify Documentation")})
        fake = FakeTransport([TransportResponse(200, {}, b"User-agent: *\nDisallow: /\n", "https://docs.apify.com/robots.txt")])
        result = run_source_snapshot_task(make_task(), MISSION, policy, self.task_schema, self.snapshot_schema, self.evidence_schema, transport=fake, now=NOW)
        self.assertEqual(result.status, "BLOCKED")
        self.assertIsNone(result.evidence_proposal)
        self.assertIsNone(result.raw_content)

    def test_rejects_write_or_paid_actions(self):
        policy = SourcePolicy({"docs.apify.com": SourceRecord("Apify Documentation")})
        task = make_task(); task["allowed_actions"] = ["READ_PUBLIC", "PARSE_PUBLIC", "HASH_PUBLIC", "WRITE_REPO_VALIDATED"]
        with self.assertRaises(Exception):
            run_source_snapshot_task(task, MISSION, policy, self.task_schema, self.snapshot_schema, self.evidence_schema, transport=FakeTransport([]), now=NOW)
        task = make_task(); task["paid_provider_routes_enabled"] = True
        with self.assertRaises(Exception):
            run_source_snapshot_task(task, MISSION, policy, self.task_schema, self.snapshot_schema, self.evidence_schema, transport=FakeTransport([]), now=NOW)


if __name__ == "__main__":
    unittest.main()
