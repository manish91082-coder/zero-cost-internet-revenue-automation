import hashlib
import json
import sys
import unittest
from pathlib import Path
from datetime import datetime, timedelta, timezone

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from zcira_control.checkpoints import StaleCheckpoint
from zcira_control.policy import (
    CANONICAL_CODE_BRANCH, CANONICAL_REPO, ENVIRONMENT_NAMESPACE,
    LEGACY_STATE_NAMESPACE, PROJECT_ID, PolicyError,
)
from zcira_control.state_repository import (
    LeaseBusy, StateIntegrityError, StateRepository, canonical_json,
    compute_state_digest, validate_manifest, MANIFEST_PATH,
)


NOW = datetime(2026, 11, 16, 2, 32, 16, tzinfo=timezone.utc)


class FakeDurableStore:
    def __init__(self):
        self.head = "a" * 40
        self.branch = "evidence-ledger"
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



def make_legacy_main_manifest():
    value = {
        "schema_version": "1.0.0",
        "project_id": PROJECT_ID,
        "mission_id": PROJECT_ID,
        "canonical_repo": CANONICAL_REPO,
        "branch": CANONICAL_CODE_BRANCH,
        "environment_namespace": ENVIRONMENT_NAMESPACE,
        "state_namespace": LEGACY_STATE_NAMESPACE,
        "generation": 0,
        "previous_commit_sha": None,
        "updated_at": "2026-11-16T02:32:16Z",
        "objects": [],
        "active_writer_lease_id": None,
        "kill_switch": False,
        "paid_provider_routes_enabled": False,
        "spend_cap_inr": 0,
    }
    value["state_digest"] = compute_state_digest(value)
    return value


class StateRepositoryTests(unittest.TestCase):
    def setUp(self):
        self.store = FakeDurableStore()
        self.repo = StateRepository(self.store, object_validator=validate_event)
        self.repo.initialize(NOW)

    def test_empty_ledger_bootstrap_migrates_only_legacy_generation_zero_manifest(self):
        legacy = make_legacy_main_manifest()
        legacy_raw = canonical_json(legacy)
        legacy_head = self.store.read_head()
        self.store.snapshots[legacy_head][MANIFEST_PATH] = legacy_raw

        migrated_head = self.repo.bootstrap_empty_ledger(NOW + timedelta(seconds=1))
        head, manifest = self.repo.load()

        self.assertEqual(head, migrated_head)
        self.assertEqual(manifest["branch"], "evidence-ledger")
        self.assertEqual(manifest["state_namespace"], "zcira-2026-11-13/evidence-ledger")
        self.assertEqual(manifest["generation"], 0)
        self.assertEqual(manifest["objects"], [])
        self.assertEqual(manifest["previous_commit_sha"], legacy_head)
        self.assertEqual(self.store.read_file(MANIFEST_PATH, ref=legacy_head), legacy_raw)

    def test_empty_ledger_bootstrap_rejects_nonempty_or_advanced_legacy_state(self):
        legacy = make_legacy_main_manifest()
        legacy["generation"] = 1
        legacy["state_digest"] = compute_state_digest(legacy)
        old_head = self.store.read_head()
        self.store.snapshots[old_head][MANIFEST_PATH] = canonical_json(legacy)
        with self.assertRaises(StateIntegrityError):
            self.repo.bootstrap_empty_ledger(NOW + timedelta(seconds=1))
        self.assertEqual(self.store.read_head(), old_head)

    def test_empty_ledger_bootstrap_rejects_bad_legacy_digest(self):
        legacy = make_legacy_main_manifest()
        legacy["state_digest"] = "0" * 64
        old_head = self.store.read_head()
        self.store.snapshots[old_head][MANIFEST_PATH] = canonical_json(legacy)
        with self.assertRaises(StateIntegrityError):
            self.repo.bootstrap_empty_ledger(NOW + timedelta(seconds=1))
        self.assertEqual(self.store.read_head(), old_head)

    def test_empty_ledger_bootstrap_rejects_non_ledger_store(self):
        self.store.branch = "main"
        old_head = self.store.read_head()
        with self.assertRaises(PolicyError):
            self.repo.bootstrap_empty_ledger(NOW + timedelta(seconds=1))
        self.assertEqual(self.store.read_head(), old_head)

    def test_initial_manifest_is_valid_and_empty(self):
        head, manifest = self.repo.load()
        self.assertEqual(manifest["generation"], 0)
        self.assertEqual(manifest["objects"], [])
        self.assertIsNone(manifest["active_writer_lease_id"])
        self.assertEqual(manifest["state_digest"], compute_state_digest(manifest))

    def test_commit_under_lease_retains_and_refreshes_writer_lease(self):
        lease, lock_head = self.repo.acquire_writer_lease(
            "publisher-checkpoint-run", NOW, ttl_seconds=30
        )
        original_expiry = datetime.fromisoformat(lease["expires_at"].replace("Z", "+00:00"))
        checkpoint_time = NOW + timedelta(seconds=5)
        event = {
            "schema_version": "1.0.0",
            "event_id": "evt-checkpoint-1",
            "event": "langgraph-checkpoint-committed",
        }

        checkpoint_head = self.repo.commit_under_lease(
            lease["lease_id"],
            lock_head,
            [("state_event", event["event_id"], event)],
            checkpoint_time,
            "test retained checkpoint lease",
            ttl_seconds=900,
        )

        head, manifest = self.repo.load()
        self.assertEqual(head, checkpoint_head)
        self.assertEqual(manifest["active_writer_lease_id"], lease["lease_id"])
        refreshed = self.repo.load_object("resource_lease", lease["lease_id"], head, manifest)
        self.assertEqual(refreshed["status"], "ACTIVE")
        self.assertGreater(
            datetime.fromisoformat(refreshed["expires_at"].replace("Z", "+00:00")),
            original_expiry,
        )
        self.assertEqual(
            refreshed["idempotency_key"],
            hashlib.sha256(
                canonical_json({
                    key: value for key, value in refreshed.items()
                    if key != "idempotency_key"
                }).encode("utf-8")
            ).hexdigest(),
        )
        self.assertEqual(
            self.repo.load_object("state_event", event["event_id"], head, manifest),
            event,
        )
        with self.assertRaises(LeaseBusy):
            self.repo.acquire_writer_lease(
                "publisher-second-run",
                checkpoint_time + timedelta(seconds=1),
                ttl_seconds=300,
            )

        released_head = self.repo.release_writer_lease(
            lease["lease_id"],
            checkpoint_head,
            checkpoint_time + timedelta(seconds=2),
        )
        _, released_manifest = self.repo.load()
        self.assertEqual(self.store.read_head(), released_head)
        self.assertIsNone(released_manifest["active_writer_lease_id"])

    def test_commit_under_lease_rejects_stale_head_without_mutation(self):
        lease, lock_head = self.repo.acquire_writer_lease(
            "publisher-stale-checkpoint", NOW, ttl_seconds=300
        )
        concurrent_sha = "d" * 40
        self.store.snapshots[concurrent_sha] = dict(self.store.snapshots[self.store.head])
        self.store.head = concurrent_sha
        event = {"schema_version": "1.0.0", "event_id": "evt-stale", "event": "must-not-commit"}

        with self.assertRaises(StaleCheckpoint):
            self.repo.commit_under_lease(
                lease["lease_id"], lock_head,
                [("state_event", event["event_id"], event)],
                NOW + timedelta(seconds=1),
                "reject stale checkpoint",
            )
        self.assertEqual(self.store.read_head(), concurrent_sha)

    def test_commit_under_lease_rejects_expired_lease_without_mutation(self):
        lease, lock_head = self.repo.acquire_writer_lease(
            "publisher-expired-checkpoint", NOW, ttl_seconds=30
        )
        event = {"schema_version": "1.0.0", "event_id": "evt-expired", "event": "must-not-commit"}

        with self.assertRaises(PolicyError):
            self.repo.commit_under_lease(
                lease["lease_id"], lock_head,
                [("state_event", event["event_id"], event)],
                NOW + timedelta(seconds=31),
                "reject expired checkpoint lease",
            )
        self.assertEqual(self.store.read_head(), lock_head)

    def test_commit_under_lease_rejects_lease_replacement_by_caller(self):
        lease, lock_head = self.repo.acquire_writer_lease(
            "publisher-lease-override", NOW, ttl_seconds=300
        )
        with self.assertRaises(PolicyError):
            self.repo.commit_under_lease(
                lease["lease_id"], lock_head,
                [("resource_lease", lease["lease_id"], lease)],
                NOW + timedelta(seconds=1),
                "reject caller lease override",
            )
        self.assertEqual(self.store.read_head(), lock_head)

    def test_commit_under_lease_rejects_invalid_ttl(self):
        lease, lock_head = self.repo.acquire_writer_lease(
            "publisher-invalid-ttl", NOW, ttl_seconds=300
        )
        for invalid_ttl in (True, 0, 3601):
            with self.subTest(ttl_seconds=invalid_ttl):
                with self.assertRaises(PolicyError):
                    self.repo.commit_under_lease(
                        lease["lease_id"], lock_head, [],
                        NOW + timedelta(seconds=1),
                        "reject invalid lease refresh TTL",
                        ttl_seconds=invalid_ttl,
                    )
        self.assertEqual(self.store.read_head(), lock_head)

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

    def test_commit_and_release_publishes_evidence_file_atomically_with_manifest(self):
        lease, lock_head = self.repo.acquire_writer_lease("publisher-evidence", NOW, ttl_seconds=300)
        envelope = {"kind": "metadata-only", "snapshot_id": "snapshot-test"}
        raw = canonical_json(envelope)
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        path = f"evidence/snapshots/sha256/{digest}.json"
        event = {"schema_version": "1.0.0", "event_id": "evt-evidence", "event": "evidence-published"}
        final_head = self.repo.commit_and_release(
            lease["lease_id"],
            lock_head,
            [("state_event", "evt-evidence", event)],
            NOW + timedelta(seconds=1),
            "atomic evidence publication test",
            extra_files={path: raw},
        )
        head, manifest = self.repo.load()
        self.assertEqual(head, final_head)
        self.assertIsNone(manifest["active_writer_lease_id"])
        self.assertEqual(self.store.read_file(path, ref=final_head), raw)
        stored_event = self.repo.load_object("state_event", "evt-evidence", head, manifest)
        self.assertEqual(stored_event, event)

    def test_extra_files_reject_wrong_hash_and_non_evidence_paths(self):
        lease, lock_head = self.repo.acquire_writer_lease("publisher-invalid", NOW, ttl_seconds=300)
        raw = canonical_json({"kind": "metadata-only"})
        bad_hash_path = "evidence/snapshots/sha256/" + ("f" * 64) + ".json"
        with self.assertRaises(PolicyError):
            self.repo.commit_and_release(
                lease["lease_id"], lock_head, [], NOW + timedelta(seconds=1),
                "reject wrong evidence digest", extra_files={bad_hash_path: raw},
            )
        head, manifest = self.repo.load()
        self.assertEqual(head, lock_head)
        self.assertEqual(manifest["active_writer_lease_id"], lease["lease_id"])
        with self.assertRaises(PolicyError):
            self.repo.commit_and_release(
                lease["lease_id"], lock_head, [], NOW + timedelta(seconds=1),
                "reject non-evidence path", extra_files={"config/secret.json": raw},
            )

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
