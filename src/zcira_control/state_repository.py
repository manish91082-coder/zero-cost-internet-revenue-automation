from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Mapping, Protocol

from .checkpoints import StaleCheckpoint
from .github_state import validate_state_path
from .leases import validate_lease
from .policy import (
    CANONICAL_CODE_BRANCH,
    CANONICAL_STATE_BRANCH,
    LEGACY_STATE_NAMESPACE,
    CANONICAL_REPO,
    ENVIRONMENT_NAMESPACE,
    PROJECT_ID,
    SINGLE_WRITER_ROLE,
    STATE_NAMESPACE,
    PolicyError,
    validate_git_sha,
)


MANIFEST_PATH = "state/manifest.v1.json"
OBJECT_PREFIX = "state/objects/"
OBJECT_ID_FIELDS = {
    "task": "task_id",
    "evidence": "evidence_id",
    "source_snapshot": "snapshot_id",
    "gate_decision": "decision_id",
    "run_state": "run_id",
    "agent_message": "message_id",
    "approval": "approval_id",
    "quota_ledger": "provider_id",
    "resource_lease": "lease_id",
    "state_event": "event_id",
    "langgraph_checkpoint": "checkpoint_id",
    "langgraph_pending_writes": "pending_write_id",
}
OBJECT_KINDS = set(OBJECT_ID_FIELDS)


class StateNotInitialized(RuntimeError):
    pass


class LeaseBusy(RuntimeError):
    pass


class StateIntegrityError(RuntimeError):
    pass


class DurableStateStore(Protocol):
    def read_head(self) -> str:
        ...

    def read_file(self, path: str, ref: str | None = None) -> str | None:
        ...

    def commit_files(self, expected_head_sha: str, files: Mapping[str, str], message: str) -> dict[str, Any]:
        ...


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _iso(value: datetime) -> str:
    if value.tzinfo is None:
        raise PolicyError("state timestamps must include a timezone")
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _parse_time(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, TypeError, ValueError):
        raise StateIntegrityError("invalid state timestamp") from None
    if parsed.tzinfo is None:
        raise StateIntegrityError("state timestamp has no timezone")
    return parsed.astimezone(timezone.utc)


def _manifest_digest_payload(manifest: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in manifest.items() if key != "state_digest"}


def compute_state_digest(manifest: Mapping[str, Any]) -> str:
    return sha256_text(canonical_json(_manifest_digest_payload(manifest)))


def validate_manifest(manifest: Mapping[str, Any]) -> None:
    required = {
        "schema_version", "project_id", "mission_id", "canonical_repo", "branch",
        "environment_namespace", "state_namespace", "generation", "previous_commit_sha",
        "updated_at", "objects", "active_writer_lease_id", "kill_switch",
        "paid_provider_routes_enabled", "spend_cap_inr", "state_digest",
    }
    if set(manifest.keys()) != required:
        raise StateIntegrityError("state manifest fields do not match the versioned contract")
    constants = {
        "schema_version": "1.0.0",
        "project_id": PROJECT_ID,
        "mission_id": PROJECT_ID,
        "canonical_repo": CANONICAL_REPO,
        "branch": CANONICAL_STATE_BRANCH,
        "environment_namespace": ENVIRONMENT_NAMESPACE,
        "state_namespace": STATE_NAMESPACE,
        "paid_provider_routes_enabled": False,
        "spend_cap_inr": 0,
    }
    for key, expected in constants.items():
        if manifest.get(key) != expected:
            raise StateIntegrityError(f"state manifest scope or policy mismatch: {key}")
    generation = manifest.get("generation")
    if not isinstance(generation, int) or isinstance(generation, bool) or generation < 0:
        raise StateIntegrityError("state generation must be a non-negative integer")
    previous = manifest.get("previous_commit_sha")
    if previous is not None:
        try:
            validate_git_sha(previous)
        except PolicyError:
            raise StateIntegrityError("previous commit SHA is invalid") from None
    _parse_time(manifest.get("updated_at"))
    if not isinstance(manifest.get("objects"), list):
        raise StateIntegrityError("manifest objects must be an array")
    seen: set[tuple[str, str]] = set()
    for entry in manifest["objects"]:
        if not isinstance(entry, Mapping) or set(entry.keys()) != {"kind", "object_id", "path", "sha256", "schema_version"}:
            raise StateIntegrityError("manifest object reference is malformed")
        if entry["kind"] not in OBJECT_KINDS:
            raise StateIntegrityError("manifest contains an unknown object kind")
        if not isinstance(entry["object_id"], str) or not entry["object_id"]:
            raise StateIntegrityError("manifest object ID is empty")
        if not isinstance(entry["sha256"], str) or len(entry["sha256"]) != 64:
            raise StateIntegrityError("manifest object hash is invalid")
        if any(ch not in "0123456789abcdef" for ch in entry["sha256"]):
            raise StateIntegrityError("manifest object hash is invalid")
        if entry["path"] != f"{OBJECT_PREFIX}{entry['sha256']}.json":
            raise StateIntegrityError("object path must be content-addressed")
        if entry["schema_version"] != "1.0.0":
            raise StateIntegrityError("unsupported object schema version")
        key = (entry["kind"], entry["object_id"])
        if key in seen:
            raise StateIntegrityError("duplicate object identity in manifest")
        seen.add(key)
    active_id = manifest.get("active_writer_lease_id")
    if active_id is not None and ("resource_lease", active_id) not in seen:
        raise StateIntegrityError("active writer lease is not referenced by the manifest")
    if not isinstance(manifest.get("kill_switch"), bool):
        raise StateIntegrityError("kill switch must be boolean")
    if manifest.get("state_digest") != compute_state_digest(manifest):
        raise StateIntegrityError("state manifest digest mismatch")


def make_initial_manifest(now: datetime) -> dict[str, Any]:
    manifest = {
        "schema_version": "1.0.0",
        "project_id": PROJECT_ID,
        "mission_id": PROJECT_ID,
        "canonical_repo": CANONICAL_REPO,
        "branch": CANONICAL_STATE_BRANCH,
        "environment_namespace": ENVIRONMENT_NAMESPACE,
        "state_namespace": STATE_NAMESPACE,
        "generation": 0,
        "previous_commit_sha": None,
        "updated_at": _iso(now),
        "objects": [],
        "active_writer_lease_id": None,
        "kill_switch": False,
        "paid_provider_routes_enabled": False,
        "spend_cap_inr": 0,
    }
    manifest["state_digest"] = compute_state_digest(manifest)
    validate_manifest(manifest)
    return manifest


class StateRepository:
    """Git-backed immutable-object store with a CAS-protected manifest and writer lease.

    Each state transition is one Git commit. The manifest points to immutable,
    content-addressed objects. A writer must acquire a lease commit, then publish
    and release that lease in one later atomic commit based on the exact lease head.
    """

    def __init__(
        self,
        store: DurableStateStore,
        object_validator: Callable[[str, Mapping[str, Any]], None] | None = None,
    ):
        self.store = store
        self.object_validator = object_validator

    def initialize(self, now: datetime, message: str = "zcira: initialize durable state") -> str:
        head = self.store.read_head()
        existing = self.store.read_file(MANIFEST_PATH, ref=head)
        if existing is not None:
            raise StateIntegrityError("state manifest already exists")
        manifest = make_initial_manifest(now)
        result = self.store.commit_files(head, {MANIFEST_PATH: canonical_json(manifest)}, message)
        self._verify_commit(result["commit_sha"], {MANIFEST_PATH: canonical_json(manifest)})
        return result["commit_sha"]

    def bootstrap_empty_ledger(
        self,
        now: datetime,
        message: str = "zcira: bootstrap empty evidence ledger",
    ) -> str:
        """Replace only an inherited generation-zero main manifest on an owner-created ledger branch.

        This method never creates a branch. The caller must first create the
        evidence-ledger branch through an owner-approved repository operation.
        Non-empty, leased, killed, malformed or digest-invalid legacy state is
        rejected. The old main commit remains immutable in Git history.
        """
        if now.tzinfo is None:
            raise PolicyError("ledger bootstrap time must include a timezone")
        store_branch = getattr(self.store, "branch", CANONICAL_STATE_BRANCH)
        if store_branch != CANONICAL_STATE_BRANCH:
            raise PolicyError("empty-ledger bootstrap is restricted to evidence-ledger")
        head = self.store.read_head()
        raw = self.store.read_file(MANIFEST_PATH, ref=head)
        if raw is None:
            raise StateNotInitialized("inherited main bootstrap manifest is missing")
        try:
            legacy = json.loads(raw)
        except json.JSONDecodeError:
            raise StateIntegrityError("inherited main manifest is not valid JSON") from None
        required = {
            "schema_version", "project_id", "mission_id", "canonical_repo", "branch",
            "environment_namespace", "state_namespace", "generation", "previous_commit_sha",
            "updated_at", "objects", "active_writer_lease_id", "kill_switch",
            "paid_provider_routes_enabled", "spend_cap_inr", "state_digest",
        }
        if not isinstance(legacy, Mapping) or set(legacy.keys()) != required:
            raise StateIntegrityError("inherited main manifest does not match the exact legacy contract")
        legacy_constants = {
            "schema_version": "1.0.0",
            "project_id": PROJECT_ID,
            "mission_id": PROJECT_ID,
            "canonical_repo": CANONICAL_REPO,
            "branch": CANONICAL_CODE_BRANCH,
            "environment_namespace": ENVIRONMENT_NAMESPACE,
            "state_namespace": LEGACY_STATE_NAMESPACE,
            "paid_provider_routes_enabled": False,
            "spend_cap_inr": 0,
        }
        for key, expected in legacy_constants.items():
            if legacy.get(key) != expected:
                raise StateIntegrityError(f"inherited main manifest mismatch: {key}")
        generation = legacy.get("generation")
        if (
            not isinstance(generation, int)
            or isinstance(generation, bool)
            or generation != 0
            or legacy.get("previous_commit_sha") is not None
            or legacy.get("objects") != []
            or legacy.get("active_writer_lease_id") is not None
            or legacy.get("kill_switch") is not False
        ):
            raise StateIntegrityError("only an untouched generation-zero empty main manifest may be migrated")
        _parse_time(legacy.get("updated_at"))
        if legacy.get("state_digest") != compute_state_digest(legacy):
            raise StateIntegrityError("inherited main manifest digest mismatch")

        next_manifest = make_initial_manifest(now)
        next_manifest["previous_commit_sha"] = head
        next_manifest["state_digest"] = compute_state_digest(next_manifest)
        validate_manifest(next_manifest)
        files = {MANIFEST_PATH: canonical_json(next_manifest)}
        result = self.store.commit_files(head, files, message)
        self._verify_commit(result["commit_sha"], files)
        return result["commit_sha"]

    def load(self) -> tuple[str, dict[str, Any]]:
        head = self.store.read_head()
        raw = self.store.read_file(MANIFEST_PATH, ref=head)
        if raw is None:
            raise StateNotInitialized("durable state manifest is not initialized")
        try:
            manifest = json.loads(raw)
        except json.JSONDecodeError:
            raise StateIntegrityError("state manifest is not valid JSON") from None
        validate_manifest(manifest)
        if manifest["active_writer_lease_id"] is not None:
            self.load_object("resource_lease", manifest["active_writer_lease_id"], head, manifest)
        return head, manifest

    def load_object(
        self,
        kind: str,
        object_id: str,
        head: str | None = None,
        manifest: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        if kind not in OBJECT_KINDS:
            raise StateIntegrityError("unknown state object kind")
        if head is None or manifest is None:
            head, manifest = self.load()
        matches = [entry for entry in manifest["objects"] if entry["kind"] == kind and entry["object_id"] == object_id]
        if len(matches) != 1:
            raise StateIntegrityError("state object reference is missing or ambiguous")
        reference = matches[0]
        raw = self.store.read_file(reference["path"], ref=head)
        if raw is None or sha256_text(raw) != reference["sha256"]:
            raise StateIntegrityError("content-addressed state object failed hash verification")
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            raise StateIntegrityError("state object is not valid JSON") from None
        if canonical_json(payload) != raw:
            raise StateIntegrityError("state object is not canonical JSON")
        return payload

    def acquire_writer_lease(
        self,
        holder_id: str,
        now: datetime,
        ttl_seconds: int = 300,
    ) -> tuple[dict[str, Any], str]:
        if not isinstance(holder_id, str) or not holder_id.strip() or len(holder_id) > 120:
            raise PolicyError("writer holder ID must be non-empty and bounded")
        if now.tzinfo is None:
            raise PolicyError("writer lease time must include a timezone")
        if not isinstance(ttl_seconds, int) or ttl_seconds < 30 or ttl_seconds > 3600:
            raise PolicyError("writer lease TTL must be between 30 and 3600 seconds")
        head, manifest = self.load()
        if manifest["kill_switch"]:
            raise PolicyError("kill switch blocks writer lease acquisition")

        pending_objects: list[tuple[str, str, Mapping[str, Any]]] = []
        active_id = manifest["active_writer_lease_id"]
        if active_id is not None:
            previous = self.load_object("resource_lease", active_id, head, manifest)
            if previous.get("status") == "ACTIVE" and _parse_time(previous["expires_at"]) > now.astimezone(timezone.utc):
                raise LeaseBusy("repository writer lease is still active")
            previous["status"] = "EXPIRED"
            previous["released_at"] = None
            pending_objects.append(("resource_lease", active_id, previous))

        acquired = _iso(now)
        expires = _iso(now + timedelta(seconds=ttl_seconds))
        lease_seed = {
            "project_id": PROJECT_ID,
            "holder_id": holder_id.strip(),
            "base_commit_sha": head,
            "acquired_at": acquired,
            "expires_at": expires,
        }
        lease_id = "lease-" + sha256_text(canonical_json(lease_seed))[:32]
        lease = {
            "schema_version": "1.0.0",
            "project_id": PROJECT_ID,
            "lease_id": lease_id,
            "mission_id": PROJECT_ID,
            "canonical_repo": CANONICAL_REPO,
            "branch": CANONICAL_STATE_BRANCH,
            "environment_namespace": ENVIRONMENT_NAMESPACE,
            "state_namespace": STATE_NAMESPACE,
            "resource_key": "repo-evidence-ledger-single-writer",
            "lease_kind": "REPOSITORY_SINGLE_WRITER",
            "task_id": "zcira-system-writer-lease",
            "holder_id": holder_id.strip(),
            "holder_role": SINGLE_WRITER_ROLE,
            "write_access": True,
            "cross_mission_share_allowed": False,
            "status": "ACTIVE",
            "acquired_at": acquired,
            "expires_at": expires,
            "released_at": None,
            "base_commit_sha": head,
        }
        lease["idempotency_key"] = sha256_text(canonical_json(lease))
        validate_lease(lease, now)
        pending_objects.append(("resource_lease", lease_id, lease))
        commit_sha = self._commit_transition(
            head,
            manifest,
            pending_objects,
            active_writer_lease_id=lease_id,
            now=now,
            message="zcira: acquire repository writer lease",
        )
        return lease, commit_sha

    def commit_under_lease(
        self,
        lease_id: str,
        lease_commit_sha: str,
        objects: list[tuple[str, str, Mapping[str, Any]]],
        now: datetime,
        message: str,
        ttl_seconds: int = 900,
        extra_files: Mapping[str, str] | None = None,
    ) -> str:
        """Commit a checkpoint while retaining and refreshing the active writer lease.

        The exact current branch head must equal lease_commit_sha. The lease remains
        referenced by the next manifest and is refreshed in the same atomic commit
        as the supplied immutable state objects. A caller must use the returned
        commit SHA for the next transition; stale heads are never retried.
        """
        validate_git_sha(lease_commit_sha)
        if now.tzinfo is None:
            raise PolicyError("writer lease time must include a timezone")
        if (
            not isinstance(ttl_seconds, int)
            or isinstance(ttl_seconds, bool)
            or ttl_seconds < 30
            or ttl_seconds > 3600
        ):
            raise PolicyError("writer lease TTL must be between 30 and 3600 seconds")
        if not isinstance(objects, list):
            raise PolicyError("lease-bound state objects must be a list")
        if any(kind == "resource_lease" for kind, _, _ in objects):
            raise PolicyError("checkpoint caller cannot replace the active writer lease")

        head, manifest = self.load()
        if head != lease_commit_sha:
            raise StaleCheckpoint("writer lease head is stale; re-fetch before checkpoint commit")
        if manifest["kill_switch"]:
            raise PolicyError("kill switch blocks checkpoint publication")
        if manifest["active_writer_lease_id"] != lease_id:
            raise PolicyError("writer lease is not the active canonical lease")

        lease = self.load_object("resource_lease", lease_id, head, manifest)
        validate_lease(lease, now)
        if (
            lease.get("status") != "ACTIVE"
            or _parse_time(lease["expires_at"]) <= now.astimezone(timezone.utc)
        ):
            raise PolicyError("writer lease expired before checkpoint publication")

        refreshed = dict(lease)
        requested_expiry = now + timedelta(seconds=ttl_seconds)
        current_expiry = _parse_time(lease["expires_at"])
        refreshed["expires_at"] = _iso(max(requested_expiry, current_expiry))
        unsigned_lease = dict(refreshed)
        unsigned_lease.pop("idempotency_key", None)
        refreshed["idempotency_key"] = sha256_text(canonical_json(unsigned_lease))

        pending_objects = list(objects)
        pending_objects.append(("resource_lease", lease_id, refreshed))
        return self._commit_transition(
            head,
            manifest,
            pending_objects,
            active_writer_lease_id=lease_id,
            now=now,
            message=message,
            extra_files=extra_files,
        )

    def commit_and_release(
        self,
        lease_id: str,
        lease_commit_sha: str,
        objects: list[tuple[str, str, Mapping[str, Any]]],
        now: datetime,
        message: str,
        extra_files: Mapping[str, str] | None = None,
    ) -> str:
        validate_git_sha(lease_commit_sha)
        head, manifest = self.load()
        if head != lease_commit_sha:
            raise StaleCheckpoint("writer lease head is stale; re-fetch before publication")
        if manifest["kill_switch"]:
            raise PolicyError("kill switch blocks publication")
        if manifest["active_writer_lease_id"] != lease_id:
            raise PolicyError("writer lease is not the active canonical lease")
        lease = self.load_object("resource_lease", lease_id, head, manifest)
        validate_lease(lease, now)
        if lease.get("status") != "ACTIVE" or _parse_time(lease["expires_at"]) <= now.astimezone(timezone.utc):
            raise PolicyError("writer lease expired before publication")

        pending_objects = list(objects)
        released = dict(lease)
        released["status"] = "RELEASED"
        released["released_at"] = _iso(now)
        pending_objects.append(("resource_lease", lease_id, released))
        return self._commit_transition(
            head,
            manifest,
            pending_objects,
            active_writer_lease_id=None,
            now=now,
            message=message,
            extra_files=extra_files,
        )
    def release_writer_lease(
        self,
        lease_id: str,
        lease_commit_sha: str,
        now: datetime,
        message: str = "zcira: release repository writer lease",
    ) -> str:
        return self.commit_and_release(lease_id, lease_commit_sha, [], now, message)

    def _commit_transition(
        self,
        expected_head: str,
        current_manifest: Mapping[str, Any],
        objects: list[tuple[str, str, Mapping[str, Any]]],
        active_writer_lease_id: str | None,
        now: datetime,
        message: str,
        extra_files: Mapping[str, str] | None = None,
    ) -> str:
        current_head = self.store.read_head()
        if current_head != expected_head:
            raise StaleCheckpoint("branch head changed before state transition")
        references = {
            (entry["kind"], entry["object_id"]): dict(entry)
            for entry in current_manifest["objects"]
        }
        files: dict[str, str] = {}
        for kind, object_id, payload in objects:
            if kind not in OBJECT_KINDS or not isinstance(object_id, str) or not object_id:
                raise PolicyError("state object kind or ID is invalid")
            if not isinstance(payload, Mapping):
                raise PolicyError("state object payload must be an object")
            material = dict(payload)
            if material.get("schema_version") != "1.0.0":
                raise PolicyError("state object schema version is not supported")
            if material.get(OBJECT_ID_FIELDS[kind]) != object_id:
                raise PolicyError("state object ID does not match its manifest key")
            if kind == "resource_lease":
                validate_lease(material, now)
            elif self.object_validator is None:
                raise PolicyError("a schema validator is required before persisting non-lease objects")
            else:
                self.object_validator(kind, material)
            raw = canonical_json(material)
            digest = sha256_text(raw)
            path = f"{OBJECT_PREFIX}{digest}.json"
            files[path] = raw
            references[(kind, object_id)] = {
                "kind": kind,
                "object_id": object_id,
                "path": path,
                "sha256": digest,
                "schema_version": "1.0.0",
            }

        extra_total = 0
        for path, raw in (extra_files or {}).items():
            validate_state_path(path)
            if not path.startswith(("evidence/snapshots/sha256/", "evidence/proposals/sha256/")):
                raise PolicyError("publisher extra files are restricted to evidence snapshot/proposal paths")
            if path in files or path == MANIFEST_PATH:
                raise PolicyError("publisher extra file collides with a state object or manifest")
            if not isinstance(raw, str):
                raise PolicyError("publisher extra file must be UTF-8 JSON text")
            size = len(raw.encode("utf-8"))
            if size > 65_536:
                raise PolicyError("one evidence metadata object exceeds 64 KiB")
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                raise PolicyError("publisher extra file is not valid JSON") from None
            if not isinstance(parsed, Mapping) or canonical_json(parsed) != raw:
                raise PolicyError("publisher extra file must be a canonical JSON object")
            digest = sha256_text(raw)
            expected_path = path.rsplit("/", 1)[0] + "/" + digest + ".json"
            if path != expected_path:
                raise PolicyError("publisher extra path must match the content SHA-256")
            extra_total += size
            if extra_total > 262_144:
                raise PolicyError("publisher evidence batch exceeds 256 KiB")
            files[path] = raw

        next_manifest = {
            "schema_version": "1.0.0",
            "project_id": PROJECT_ID,
            "mission_id": PROJECT_ID,
            "canonical_repo": CANONICAL_REPO,
            "branch": CANONICAL_STATE_BRANCH,
            "environment_namespace": ENVIRONMENT_NAMESPACE,
            "state_namespace": STATE_NAMESPACE,
            "generation": current_manifest["generation"] + 1,
            "previous_commit_sha": expected_head,
            "updated_at": _iso(now),
            "objects": sorted(references.values(), key=lambda item: (item["kind"], item["object_id"])),
            "active_writer_lease_id": active_writer_lease_id,
            "kill_switch": current_manifest["kill_switch"],
            "paid_provider_routes_enabled": False,
            "spend_cap_inr": 0,
        }
        next_manifest["state_digest"] = compute_state_digest(next_manifest)
        validate_manifest(next_manifest)
        files[MANIFEST_PATH] = canonical_json(next_manifest)
        result = self.store.commit_files(expected_head, files, message)
        self._verify_commit(result["commit_sha"], files)
        return result["commit_sha"]

    def _verify_commit(self, commit_sha: str, files: Mapping[str, str]) -> None:
        validate_git_sha(commit_sha)
        for path, expected in files.items():
            actual = self.store.read_file(path, ref=commit_sha)
            if actual != expected:
                raise StateIntegrityError(f"GitHub fetch-back mismatch for {path}")
