import copy
import hashlib
import json
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from zcira_control.checkpoints import StaleCheckpoint
from zcira_control.evidence_publisher import (
    EvidencePublisher,
    IdempotencyConflict,
    PublisherError,
)
from zcira_control.policy import PolicyError
from zcira_control.state_repository import StateRepository, canonical_json


NOW = datetime(2026, 11, 22, 2, 0, 0, tzinfo=timezone.utc)
SCHEMA_DIR = ROOT / "schemas" / "v1"
FIXTURE_DIR = ROOT / "tests" / "fixtures" / "s3_v1"
SOURCE_URL = "https://docs.apify.com/platform/actors"
ARCHIVE_SHA = "c" * 64
IDEMPOTENCY = "a" * 64
ALLOWED_SOURCES = {
    "docs.apify.com": {
        "publisher": "Apify Documentation",
        "priority": "P1",
        "evidence_grade": "A_PRIMARY_OFFICIAL",
    }
}


class FakeDurableStore:
    def __init__(self):
        self.head = "a" * 40
        self.snapshots = {self.head: {}}
        self.commit_count = 0
        self.raise_after_commit_once = False

    def read_head(self):
        return self.head

    def read_file(self, path, ref=None):
        commit = self.head if ref is None or ref == "main" else ref
        return self.snapshots.get(commit, {}).get(path)

    def commit_files(self, expected_head_sha, files, message):
        if expected_head_sha != self.head:
            raise StaleCheckpoint("stale fake head")
        payload = json.dumps(
            {"parent": expected_head_sha, "message": message, "files": sorted(files.items())},
            sort_keys=True,
            ensure_ascii=False,
        )
        new_sha = hashlib.sha1(payload.encode("utf-8")).hexdigest()
        snapshot = dict(self.snapshots[self.head])
        snapshot.update(files)
        self.snapshots[new_sha] = snapshot
        self.head = new_sha
        self.commit_count += 1
        if self.raise_after_commit_once:
            self.raise_after_commit_once = False
            raise TimeoutError("simulated response loss after durable commit")
        return {"base_commit_sha": expected_head_sha, "commit_sha": new_sha}


def digest_text(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def build_fixture_batch():
    proposal = json.loads((FIXTURE_DIR / "valid_source_worker_proposal.json").read_text(encoding="utf-8"))
    envelope = proposal["source_snapshot_envelope"]
    envelope["source_url"] = SOURCE_URL
    envelope["source_url_sha256"] = digest_text(SOURCE_URL)
    envelope["provenance"] = {
        "category_id": 1,
        "destination_id": "apify-docs-actors",
        "source_row_ref": "category:1:destination:1",
        "source_line": 42,
        "archive_sha256": ARCHIVE_SHA,
    }
    envelope["excerpt"] = "Actor runtime and lifecycle details."
    envelope["publisher"] = "Apify Documentation"
    snapshot_digest = digest_text(canonical_json(envelope))
    proposal["source_snapshot_envelope_sha256"] = snapshot_digest
    proposal["source_snapshot_content_ref"] = f"sha256:{snapshot_digest}"
    proposal["source_snapshot_storage_path"] = f"evidence/snapshots/sha256/{snapshot_digest}.json"

    evidence = proposal["evidence_proposal"]
    evidence["evidence_excerpt"] = envelope["excerpt"][:1500]
    evidence["source_provenance"] = {
        "source_row_ref": "category:1:destination:1",
        "source_line": 42,
        "archive_sha256": ARCHIVE_SHA,
    }
    proposal["evidence_proposal"] = evidence
    proposal["idempotency_key"] = IDEMPOTENCY
    unsigned = {key: value for key, value in proposal.items() if key != "proposal_sha256"}
    proposal["proposal_sha256"] = digest_text(canonical_json(unsigned))

    task = json.loads((FIXTURE_DIR / "valid_task.json").read_text(encoding="utf-8"))
    task.update({
        "task_id": proposal["task_id"],
        "idempotency_key": IDEMPOTENCY,
        "task_type": "source_snapshot",
        "priority": "P1",
        "category_id": 1,
        "destination_id": "apify-docs-actors",
        "status": "RUNNING",
        "created_at": "2026-11-22T01:58:00Z",
        "updated_at": "2026-11-22T01:59:00Z",
        "attempt_count": 1,
        "allowed_actions": ["READ_PUBLIC", "PARSE_PUBLIC", "HASH_PUBLIC"],
        "external_actions_allowed": False,
        "paid_provider_routes_enabled": False,
        "parameters": {
            "source_url": SOURCE_URL,
            "source_row_ref": "category:1:destination:1",
            "source_line": 42,
            "archive_sha256": ARCHIVE_SHA,
        },
        "source_snapshot_ids": [],
        "evidence_ids": [],
        "lease_id": None,
        "checkpoint": None,
        "assigned_role": "official_source_worker_a",
    })

    run_state = json.loads((FIXTURE_DIR / "valid_run_state.json").read_text(encoding="utf-8"))
    run_state.update({
        "run_id": "zcira-run-s7b-publisher-test-001",
        "status": "RUNNING",
        "executor": "test_sandbox_non_runtime",
        "run_mode": "READ_ONLY_RESEARCH",
        "started_at": "2026-11-22T01:55:00Z",
        "last_heartbeat_at": "2026-11-22T01:59:00Z",
        "finished_at": None,
        "current_task_id": task["task_id"],
        "pending_task_ids": [],
        "completed_task_ids": [],
        "blocked_task_ids": [],
        "base_commit_sha": "a" * 40,
        "latest_commit_sha": "a" * 40,
        "kill_switch": False,
    })
    return proposal, task, run_state


class EvidencePublisherTests(unittest.TestCase):
    def setUp(self):
        self.store = FakeDurableStore()
        self.state = StateRepository(self.store)
        self.publisher = EvidencePublisher(self.state, SCHEMA_DIR, ALLOWED_SOURCES)
        self.state.initialize(NOW)
        self.proposal, self.source_task, self.run_state = build_fixture_batch()

    def acquire(self, now=NOW + timedelta(seconds=1)):
        return self.state.acquire_writer_lease("s7b-test-publisher", now, ttl_seconds=300)

    def publish(self, proposal=None, task=None, run_state=None, now=NOW + timedelta(seconds=2)):
        lease, lock_head = self.acquire(now - timedelta(seconds=1))
        return self.publisher.publish_batch(
            lease_id=lease["lease_id"],
            lease_commit_sha=lock_head,
            proposals=[proposal or copy.deepcopy(self.proposal)],
            source_tasks={self.source_task["task_id"]: task or copy.deepcopy(self.source_task)},
            run_state=run_state or copy.deepcopy(self.run_state),
            now=now,
        )

    def test_publish_is_atomic_metadata_only_and_queues_independent_review(self):
        result = self.publish()
        self.assertEqual(result["status"], "PUBLISHED")
        self.assertFalse(result["external_action_performed"])
        self.assertEqual(self.store.head, result["commit_sha"])

        head, manifest = self.state.load()
        self.assertEqual(head, result["commit_sha"])
        self.assertIsNone(manifest["active_writer_lease_id"])
        self.assertEqual(len(result["snapshot_paths"]), 1)
        self.assertEqual(len(result["proposal_paths"]), 1)

        snapshot_path = result["snapshot_paths"][0]
        proposal_path = result["proposal_paths"][0]
        snapshot_raw = self.store.read_file(snapshot_path, ref=head)
        proposal_raw = self.store.read_file(proposal_path, ref=head)
        self.assertIsNotNone(snapshot_raw)
        self.assertIsNotNone(proposal_raw)
        self.assertEqual(digest_text(snapshot_raw), snapshot_path.rsplit("/", 1)[1][:-5])
        self.assertEqual(digest_text(proposal_raw), proposal_path.rsplit("/", 1)[1][:-5])
        snapshot_payload = json.loads(snapshot_raw)
        proposal_payload = json.loads(proposal_raw)
        self.assertNotIn("raw_body", snapshot_payload)
        self.assertNotIn("raw_content", snapshot_payload)
        self.assertIs(snapshot_payload["retention"]["raw_body_persisted"], False)
        self.assertNotIn("raw_body", proposal_payload)
        self.assertNotIn("raw_content", proposal_payload)

        source_task = self.state.load_object("task", self.source_task["task_id"], head, manifest)
        self.assertEqual(source_task["status"], "COMPLETED")
        self.assertEqual(source_task["source_snapshot_ids"], [self.proposal["snapshot_id"]])
        self.assertEqual(source_task["evidence_ids"], [self.proposal["evidence_proposal"]["evidence_id"]])

        review_id = result["queued_review_task_ids"][0]
        review_task = self.state.load_object("task", review_id, head, manifest)
        self.assertEqual(review_task["status"], "QUEUED")
        self.assertEqual(review_task["assigned_role"], "adversarial_auditor")
        self.assertEqual(review_task["allowed_actions"], [])

        run = self.state.load_object("run_state", result["run_id"], head, manifest)
        self.assertEqual(run["status"], "PARTIAL")
        self.assertIsNone(run["finished_at"])
        self.assertEqual(run["started_at"], self.run_state["started_at"])
        self.assertEqual(run["completed_task_ids"], [self.source_task["task_id"]])
        self.assertEqual(run["pending_task_ids"], [review_id])

        snapshot_object = self.state.load_object("source_snapshot", self.proposal["snapshot_id"], head, manifest)
        evidence_object = self.state.load_object(
            "evidence", self.proposal["evidence_proposal"]["evidence_id"], head, manifest
        )
        self.assertEqual(snapshot_object["content_ref"], self.proposal["source_snapshot_content_ref"])
        self.assertEqual(evidence_object["gate_status"], "UNKNOWN")
        self.assertEqual(evidence_object["reviewer_verdict"], "PENDING")

    def test_ambiguous_commit_response_recovers_as_already_published(self):
        before = self.store.commit_count
        not_published = self.publisher.reconcile_batch(
            proposals=[copy.deepcopy(self.proposal)],
            source_tasks={self.source_task["task_id"]: copy.deepcopy(self.source_task)},
        )
        self.assertEqual(not_published["status"], "NOT_PUBLISHED")
        self.assertFalse(not_published["write_performed"])
        self.assertEqual(self.store.commit_count, before)

        lease, lock_head = self.acquire()
        self.store.raise_after_commit_once = True
        with self.assertRaises(TimeoutError):
            self.publisher.publish_batch(
                lease_id=lease["lease_id"],
                lease_commit_sha=lock_head,
                proposals=[copy.deepcopy(self.proposal)],
                source_tasks={self.source_task["task_id"]: copy.deepcopy(self.source_task)},
                run_state=copy.deepcopy(self.run_state),
                now=NOW + timedelta(seconds=2),
            )

        committed_head, committed_manifest = self.state.load()
        self.assertIsNone(committed_manifest["active_writer_lease_id"])
        committed_task = self.state.load_object(
            "task", self.source_task["task_id"], committed_head, committed_manifest
        )
        self.assertEqual(committed_task["status"], "COMPLETED")
        self.assertEqual(
            len([item for item in committed_manifest["objects"] if item["kind"] == "source_snapshot"]),
            1,
        )
        self.assertEqual(
            len([item for item in committed_manifest["objects"] if item["kind"] == "evidence"]),
            1,
        )
        reconciled = self.publisher.reconcile_batch(
            proposals=[copy.deepcopy(self.proposal)],
            source_tasks={self.source_task["task_id"]: copy.deepcopy(self.source_task)},
        )
        self.assertEqual(reconciled["status"], "ALREADY_PUBLISHED")
        self.assertEqual(reconciled["commit_sha"], committed_head)
        self.assertFalse(reconciled["write_performed"])
        self.assertFalse(reconciled["external_action_performed"])

        retry_lease, retry_head = self.acquire(NOW + timedelta(minutes=2))
        recovered = self.publisher.publish_batch(
            lease_id=retry_lease["lease_id"],
            lease_commit_sha=retry_head,
            proposals=[copy.deepcopy(self.proposal)],
            source_tasks={self.source_task["task_id"]: copy.deepcopy(self.source_task)},
            run_state=copy.deepcopy(self.run_state),
            now=NOW + timedelta(minutes=2, seconds=1),
        )
        self.assertEqual(recovered["status"], "ALREADY_PUBLISHED")
        self.assertEqual(recovered["duplicate_task_ids"], [self.source_task["task_id"]])
        self.assertEqual(recovered["snapshot_paths"], [])
        self.assertEqual(recovered["proposal_paths"], [])
        final_head, final_manifest = self.state.load()
        self.assertIsNone(final_manifest["active_writer_lease_id"])
        self.assertEqual(
            len([item for item in final_manifest["objects"] if item["kind"] == "source_snapshot"]),
            1,
        )
        self.assertEqual(
            len([item for item in final_manifest["objects"] if item["kind"] == "evidence"]),
            1,
        )
        self.assertNotEqual(final_head, committed_head)

    def test_retry_is_idempotent_and_does_not_duplicate_evidence(self):
        first = self.publish(now=NOW + timedelta(seconds=2))
        _, manifest_before = self.state.load()
        object_count_before = len(manifest_before["objects"])
        commit_count_before = self.store.commit_count

        lease, lock_head = self.acquire(NOW + timedelta(minutes=2))
        second = self.publisher.publish_batch(
            lease_id=lease["lease_id"],
            lease_commit_sha=lock_head,
            proposals=[copy.deepcopy(self.proposal)],
            source_tasks={self.source_task["task_id"]: copy.deepcopy(self.source_task)},
            run_state=copy.deepcopy(self.run_state),
            now=NOW + timedelta(minutes=2, seconds=1),
        )
        _, manifest_after = self.state.load()
        self.assertEqual(second["status"], "ALREADY_PUBLISHED")
        self.assertEqual(second["duplicate_task_ids"], [self.source_task["task_id"]])
        self.assertEqual(len(manifest_after["objects"]), object_count_before + 1)
        self.assertEqual(self.store.commit_count, commit_count_before + 2)
        self.assertNotEqual(first["commit_sha"], second["commit_sha"])
        self.assertIsNone(manifest_after["active_writer_lease_id"])

    def test_reused_task_id_with_different_idempotency_key_is_rejected(self):
        self.publish(now=NOW + timedelta(seconds=2))
        lease, lock_head = self.acquire(NOW + timedelta(minutes=2))
        proposal = copy.deepcopy(self.proposal)
        task = copy.deepcopy(self.source_task)
        proposal["idempotency_key"] = "b" * 64
        task["idempotency_key"] = "b" * 64
        unsigned = {key: value for key, value in proposal.items() if key != "proposal_sha256"}
        proposal["proposal_sha256"] = digest_text(canonical_json(unsigned))
        with self.assertRaises(IdempotencyConflict):
            self.publisher.publish_batch(
                lease_id=lease["lease_id"],
                lease_commit_sha=lock_head,
                proposals=[proposal],
                source_tasks={task["task_id"]: task},
                run_state=copy.deepcopy(self.run_state),
                now=NOW + timedelta(minutes=2, seconds=1),
            )

    def test_commercial_gate_promotion_is_rejected(self):
        proposal = copy.deepcopy(self.proposal)
        proposal["commercial_gate_status"] = "PASS"
        unsigned = {key: value for key, value in proposal.items() if key != "proposal_sha256"}
        proposal["proposal_sha256"] = digest_text(canonical_json(unsigned))
        with self.assertRaises(PublisherError):
            self.publish(proposal=proposal)

    def test_raw_body_field_is_rejected(self):
        proposal = copy.deepcopy(self.proposal)
        proposal["raw_body"] = "must never be persisted"
        with self.assertRaises(PublisherError):
            self.publish(proposal=proposal)

    def test_unlisted_source_domain_is_rejected(self):
        proposal = copy.deepcopy(self.proposal)
        envelope = proposal["source_snapshot_envelope"]
        envelope["source_domain"] = "unlisted.example"
        envelope["source_url"] = "https://unlisted.example/public"
        envelope["source_url_sha256"] = digest_text(envelope["source_url"])
        digest = digest_text(canonical_json(envelope))
        proposal["source_snapshot_envelope_sha256"] = digest
        proposal["source_snapshot_content_ref"] = f"sha256:{digest}"
        proposal["source_snapshot_storage_path"] = f"evidence/snapshots/sha256/{digest}.json"
        unsigned = {key: value for key, value in proposal.items() if key != "proposal_sha256"}
        proposal["proposal_sha256"] = digest_text(canonical_json(unsigned))
        with self.assertRaises(PublisherError):
            self.publish(proposal=proposal)

    def test_stale_writer_lease_head_is_rejected(self):
        lease, lock_head = self.acquire()
        concurrent = hashlib.sha1(b"concurrent-head").hexdigest()
        self.store.snapshots[concurrent] = dict(self.store.snapshots[self.store.head])
        self.store.head = concurrent
        with self.assertRaises(StaleCheckpoint):
            self.publisher.publish_batch(
                lease_id=lease["lease_id"],
                lease_commit_sha=lock_head,
                proposals=[copy.deepcopy(self.proposal)],
                source_tasks={self.source_task["task_id"]: copy.deepcopy(self.source_task)},
                run_state=copy.deepcopy(self.run_state),
                now=NOW + timedelta(seconds=2),
            )

    def test_claim_grade_cannot_exceed_source_authority_ceiling(self):
        self.publisher = EvidencePublisher(
            self.state,
            SCHEMA_DIR,
            {
                "docs.apify.com": {
                    "publisher": "Apify Documentation",
                    "priority": "P1",
                    "evidence_grade": "B_OFFICIAL_SUPPORT",
                }
            },
        )
        proposal = copy.deepcopy(self.proposal)
        proposal["evidence_proposal"]["evidence_grade"] = "A_PRIMARY_OFFICIAL"
        unsigned = {key: value for key, value in proposal.items() if key != "proposal_sha256"}
        proposal["proposal_sha256"] = digest_text(canonical_json(unsigned))
        with self.assertRaises(PublisherError):
            self.publish(proposal=proposal)

    def test_from_repository_uses_current_fail_closed_source_policy(self):
        publisher = EvidencePublisher.from_repository(self.state, ROOT)
        self.assertIn("docs.apify.com", publisher.allowed_sources)
        self.assertEqual(publisher.allowed_sources["docs.apify.com"]["priority"], "P1")
        self.assertEqual(
            publisher.allowed_sources["docs.apify.com"]["evidence_grade"],
            "A_PRIMARY_OFFICIAL",
        )


if __name__ == "__main__":
    unittest.main()
