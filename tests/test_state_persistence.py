import hashlib
import json
import sys
import unittest
from pathlib import Path
from datetime import datetime, timedelta, timezone

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from zcira_control.checkpoints import StaleCheckpoint
from zcira_control.policy import PolicyError
from zcira_control.state_repository import (
    LeaseBusy, StateIntegrityError, StateRepository, canonical_json,
    compute_state_digest, validate_manifest,
)


NOW = datetime(2026, 11, 16, 2, 32, 16, tzinfo=timezone.utc)


class FakeDurableStore:
    def __init__(self):
        self.head = "a" * 40
        self.snapshots = {self.head: {}}

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
        new_sha = hashlib.sha1(payload.encode()).hexdigest()
        snapshot = dict(self.snapshots[self.head])
        snapshot.update(files)
        self.snapshots[new_sha] = snapshot
        self.head = new_sha
        return {"base_commit_sha": expected_head_sha, "commit_sha": new_sha}


def validate_event(kind, payload):
    if kind != "state_event" or payload.get("schema_version") != "1.0.0" or not payload.get("event_id"):
        raise PolicyError("invalid synthetic state event")


class StateRepositoryTests(unittest.TestCase):
    def setUp(self):
        self.store = FakeDurableStore()
        self.repo = StateRepository(self.store, object_validator=validate_event)
        self.repo.initialize(NOW)

    def test_initial_manifest_is_valid_and_empty(self):
        head, manifest = self.repo.load()
        self.assertEqual(manifest["generation"], 0)
        self.assertEqual(manifest["objects"], [])
        self.assertIsNone(manifest["active_writer_lease_id"])
        self.assertEqual(manifest["state_digest"], compute_state_digest(manifest))

    def test_writer_lease_blocks_second_writer_and_release_is_atomic(self):
        lease, lock_head = self.repo.acquire_writer_lease("publisher-run-1", NOW, ttl_seconds=300)
        with self.assertRaises(LeaseBusy):
            self.repo.acquire_writer_lease("publisher-run-2", NOW + timedelta(seconds=1), ttl_seconds=300)

        event = {"schema_version": "1.0.0", "event_id": "evt-1", "event": "artifact-published"}
        final_head = self.repo.commit_and_release(
            lease["lease_id"], lock_head,
            [("state_event", "evt-1", event)],
            NOW + timedelta(seconds=2),
            "test publish and release",
        )
        head, manifest = self.repo.load()
        self.assertEqual(head, final_head)
        self.assertIsNone(manifest["active_writer_lease_id"])
        self.assertEqual(manifest["generation"], 2)
        stored = self.repo.load_object("state_event", "evt-1", head, manifest)
        self.assertEqual(stored, event)
        released = self.repo.load_object("resource_lease", lease["lease_id"], head, manifest)
        self.assertEqual(released["status"], "RELEASED")

    def test_expired_lease_is_marked_and_replaced_by_new_lease(self):
        old, _ = self.repo.acquire_writer_lease("publisher-old", NOW, ttl_seconds=30)
        new, new_head = self.repo.acquire_writer_lease("publisher-new", NOW + timedelta(seconds=31), ttl_seconds=300)
        head, manifest = self.repo.load()
        self.assertEqual(head, new_head)
        self.assertEqual(manifest["active_writer_lease_id"], new["lease_id"])
        old_state = self.repo.load_object("resource_lease", old["lease_id"], head, manifest)
        self.assertEqual(old_state["status"], "EXPIRED")

    def test_stale_lock_head_cannot_publish(self):
        lease, lock_head = self.repo.acquire_writer_lease("publisher-run", NOW, ttl_seconds=300)
        concurrent_sha = "c" * 40
        self.store.snapshots[concurrent_sha] = dict(self.store.snapshots[self.store.head])
        self.store.head = concurrent_sha
        with self.assertRaises(StaleCheckpoint):
            self.repo.release_writer_lease(lease["lease_id"], lock_head, NOW + timedelta(seconds=1))

    def test_manifest_digest_detects_tampering(self):
        _, manifest = self.repo.load()
        manifest["kill_switch"] = True
        with self.assertRaises(StateIntegrityError):
            validate_manifest(manifest)

    def test_non_lease_objects_require_a_validator(self):
        no_validator_repo = StateRepository(self.store)
        lease, lock_head = no_validator_repo.acquire_writer_lease("publisher-run", NOW + timedelta(seconds=1), ttl_seconds=300)
        with self.assertRaises(PolicyError):
            no_validator_repo.commit_and_release(
                lease["lease_id"], lock_head,
                [("state_event", "evt-2", {"schema_version": "1.0.0", "event_id": "evt-2"})],
                NOW + timedelta(seconds=2),
                "should fail closed",
            )


if __name__ == "__main__":
    unittest.main()
