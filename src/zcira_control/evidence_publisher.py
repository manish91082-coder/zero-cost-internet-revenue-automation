from __future__ import annotations

import copy
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlsplit, urlunsplit

from jsonschema import Draft202012Validator, FormatChecker

from .checkpoints import StaleCheckpoint
from .policy import PolicyError, PROJECT_ID, SINGLE_WRITER_ROLE
from .state_repository import StateRepository, canonical_json, sha256_text


STATE_SCHEMA_FILES = {
    "task": "task.schema.json",
    "evidence": "evidence.schema.json",
    "source_snapshot": "source_snapshot.schema.json",
    "gate_decision": "gate_decision.schema.json",
    "run_state": "run_state.schema.json",
    "agent_message": "agent_message.schema.json",
    "approval": "approval.schema.json",
    "quota_ledger": "quota_ledger.schema.json",
    "mission_registry": "mission_registry.schema.json",
}

FORBIDDEN_KEYS = {
    "raw_body", "raw_content", "response_body", "page_body", "body_bytes",
    "content_bytes", "html_bytes", "cookies", "authorization", "access_token",
    "refresh_token", "password", "secret", "private_key", "email", "phone",
    "otp", "recovery_code",
}

SAFE_SOURCE_ACTIONS = {"READ_PUBLIC", "PARSE_PUBLIC", "HASH_PUBLIC"}
SOURCE_ROLES = {"official_source_worker_a", "official_source_worker_b"}

# Evidence grades are claim-level assessments. A source's configured default is
# the maximum authority it can support; reviewers/workers may conservatively downgrade.
EVIDENCE_GRADE_RANK = {
    "D_UNVERIFIED": 1,
    "C_SECONDARY": 2,
    "B_OFFICIAL_SUPPORT": 3,
    "A_PRIMARY_OFFICIAL": 4,
}


class PublisherError(RuntimeError):
    """A worker proposal cannot safely be published to the canonical ledger."""


class IdempotencyConflict(PublisherError):
    """A task or immutable evidence identity was reused with different content."""


def _utc_iso(value: datetime) -> str:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise PolicyError("publisher timestamps must be timezone-aware")
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _reject_sensitive_keys(value: Any, path: str = "$") -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            normalized = re.sub(r"[^a-z0-9]", "", str(key).casefold())
            if normalized in {re.sub(r"[^a-z0-9]", "", item) for item in FORBIDDEN_KEYS}:
                raise PublisherError(f"forbidden sensitive/raw field at {path}.{key}")
            _reject_sensitive_keys(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _reject_sensitive_keys(child, f"{path}[{index}]")


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PublisherError(f"publisher policy/schema cannot be read: {type(exc).__name__}") from None
    if not isinstance(value, dict):
        raise PublisherError("publisher policy/schema must be a JSON object")
    return value


def build_state_object_validator(schema_dir: str | Path):
    """Build the validator used by StateRepository for all non-lease objects."""
    root = Path(schema_dir)
    validators: dict[str, Draft202012Validator] = {}
    for kind, filename in STATE_SCHEMA_FILES.items():
        schema = _load_json(root / filename)
        Draft202012Validator.check_schema(schema)
        validators[kind] = Draft202012Validator(schema, format_checker=FormatChecker())

    def validate(kind: str, payload: Mapping[str, Any]) -> None:
        validator = validators.get(kind)
        if validator is None:
            raise PolicyError(f"no versioned state-object schema is registered for {kind}")
        errors = list(validator.iter_errors(dict(payload)))
        if errors:
            first = errors[0]
            location = ".".join(str(part) for part in first.absolute_path)
            raise PolicyError(f"state object schema rejected {kind} at {location or '$'}")

    return validate


class EvidencePublisher:
    """Single-writer-only, metadata-only publisher; no network or model calls.

    The caller must acquire the canonical repository writer lease first. This
    class only builds a bounded atomic Git transaction and delegates the exact
    parent-SHA compare-and-swap plus fetch-back verification to StateRepository.
    """

    def __init__(
        self,
        state_repository: StateRepository,
        schema_dir: str | Path,
        allowed_sources: Mapping[str, Mapping[str, Any]],
    ):
        if not isinstance(state_repository, StateRepository):
            raise PublisherError("a canonical StateRepository is required")
        if not isinstance(allowed_sources, Mapping) or not allowed_sources:
            raise PublisherError("an exact source-domain allowlist is required")
        self.state_repository = state_repository
        self.allowed_sources = dict(allowed_sources)
        for domain, record in self.allowed_sources.items():
            if (
                not isinstance(domain, str)
                or domain != domain.lower()
                or not re.fullmatch(r"[a-z0-9.-]+", domain)
                or domain.startswith(".")
                or domain.endswith(".")
                or ".." in domain
                or "*" in domain
                or not isinstance(record, Mapping)
                or not isinstance(record.get("publisher"), str)
                or record.get("priority") not in {"P1", "P2"}
                or record.get("evidence_grade") not in EVIDENCE_GRADE_RANK
            ):
                raise PublisherError("source allowlist must contain exact P1/P2 hosts and publisher records")

        root = Path(schema_dir)
        self.validators: dict[str, Draft202012Validator] = {}
        for name in (
            "task", "evidence", "source_snapshot", "run_state",
            "source_snapshot_envelope", "source_worker_proposal",
        ):
            schema = _load_json(root / f"{name}.schema.json")
            Draft202012Validator.check_schema(schema)
            self.validators[name] = Draft202012Validator(schema, format_checker=FormatChecker())

        # The publisher owns validation for task/evidence/snapshot/run objects.
        self.state_repository.object_validator = build_state_object_validator(root)

    @classmethod
    def from_repository(
        cls,
        state_repository: StateRepository,
        repository_root: str | Path,
    ) -> "EvidencePublisher":
        root = Path(repository_root)
        policy = _load_json(root / "config" / "source_domain_policy.v1.json")
        required_false = (
            "allow_subdomains", "proxies_enabled", "cookies_enabled",
            "authentication_enabled", "javascript_execution_enabled",
            "automatic_retries", "access_control_bypass", "dns_pinning",
            "live_network_enabled", "egress_controls_audited",
        )
        if policy.get("project_id") != PROJECT_ID or policy.get("exact_host_allowlist") is not True:
            raise PublisherError("source-domain policy identity or exact-host rule mismatch")
        if any(policy.get(key) is not False for key in required_false):
            raise PublisherError("publisher refuses a source policy with live access or bypass capabilities")
        entries = policy.get("allowed_sources")
        if not isinstance(entries, list):
            raise PublisherError("source-domain allowlist is malformed")
        allowed: dict[str, dict[str, Any]] = {}
        for item in entries:
            if not isinstance(item, dict) or not isinstance(item.get("domain"), str):
                raise PublisherError("source-domain entry is malformed")
            domain = item["domain"]
            if domain in allowed:
                raise PublisherError("source-domain allowlist contains duplicate hosts")
            allowed[domain] = {
                "publisher": item.get("publisher"),
                "priority": item.get("priority"),
                "evidence_grade": item.get("default_evidence_grade"),
            }
        return cls(state_repository, root / "schemas" / "v1", allowed)

    def _validate(self, schema_name: str, value: Mapping[str, Any]) -> None:
        validator = self.validators[schema_name]
        errors = list(validator.iter_errors(dict(value)))
        if errors:
            first = errors[0]
            location = ".".join(str(part) for part in first.absolute_path)
            raise PublisherError(f"{schema_name} schema rejected payload at {location or '$'}")

    def _prepare_proposal(
        self,
        proposal: Mapping[str, Any],
        source_task: Mapping[str, Any],
    ) -> dict[str, Any]:
        if not isinstance(proposal, Mapping) or not isinstance(source_task, Mapping):
            raise PublisherError("proposal and source task must be objects")
        self._validate("source_worker_proposal", proposal)
        self._validate("task", source_task)
        if proposal.get("project_id") != PROJECT_ID or source_task.get("project_id") != PROJECT_ID:
            raise PublisherError("cross-mission publication is prohibited")
        if proposal.get("result_status") != "COMPLETED" or proposal.get("evidence_proposal") is None:
            raise PublisherError("only completed source captures with an evidence proposal may be published")
        if (
            proposal.get("raw_body_persisted") is not False
            or proposal.get("write_performed") is not False
            or proposal.get("requires_s7_publisher") is not True
            or proposal.get("reviewer_verdict") != "PENDING"
            or proposal.get("commercial_gate_status") != "UNKNOWN"
        ):
            raise PublisherError("worker proposal violates the read-only/pending-review boundary")
        if source_task.get("task_type") != "source_snapshot":
            raise PublisherError("source task type must be source_snapshot")
        if source_task.get("assigned_role") not in SOURCE_ROLES:
            raise PublisherError("source task is not assigned to an approved read-only worker")
        if source_task.get("assigned_role") != proposal.get("assigned_role"):
            raise PublisherError("proposal role does not match the assigned source task")
        if source_task.get("task_id") != proposal.get("task_id"):
            raise PublisherError("proposal task ID does not match the source task")
        if source_task.get("idempotency_key") != proposal.get("idempotency_key"):
            raise PublisherError("proposal idempotency key does not match the source task")
        if source_task.get("status") not in {"QUEUED", "LEASED", "RUNNING", "COMPLETED"}:
            raise PublisherError("source task is not in a publishable execution state")
        if (
            source_task.get("external_actions_allowed") is not False
            or source_task.get("paid_provider_routes_enabled") is not False
            or not SAFE_SOURCE_ACTIONS.issubset(set(source_task.get("allowed_actions", [])))
            or "WRITE_REPO_VALIDATED" in set(source_task.get("allowed_actions", []))
        ):
            raise PublisherError("source task contains an unsafe action capability")

        envelope = proposal.get("source_snapshot_envelope")
        evidence = proposal.get("evidence_proposal")
        if not isinstance(envelope, Mapping) or not isinstance(evidence, Mapping):
            raise PublisherError("completed proposal requires an envelope and evidence object")
        self._validate("source_snapshot_envelope", envelope)
        self._validate("evidence", evidence)
        _reject_sensitive_keys(proposal)

        domain = envelope.get("source_domain")
        source_record = self.allowed_sources.get(domain)
        if source_record is None:
            raise PublisherError("snapshot source domain is not in the exact current allowlist")
        if envelope.get("publisher") != source_record.get("publisher"):
            raise PublisherError("snapshot publisher does not match the source allowlist")
        source_ceiling = source_record.get("evidence_grade")
        claim_grade = evidence.get("evidence_grade")
        if (
            source_ceiling not in EVIDENCE_GRADE_RANK
            or claim_grade not in EVIDENCE_GRADE_RANK
            or EVIDENCE_GRADE_RANK[claim_grade] > EVIDENCE_GRADE_RANK[source_ceiling]
        ):
            raise PublisherError("claim evidence grade exceeds the source authority ceiling")
        if source_task.get("priority") != source_record.get("priority"):
            raise PublisherError("source task priority does not match the source allowlist")

        source_url = envelope.get("source_url")
        try:
            parsed_url = urlsplit(source_url)
        except (TypeError, ValueError):
            raise PublisherError("snapshot source URL is invalid") from None
        if (
            parsed_url.scheme != "https"
            or parsed_url.hostname != domain
            or parsed_url.username is not None
            or parsed_url.password is not None
            or parsed_url.query
            or parsed_url.fragment
            or parsed_url.port not in (None, 443)
        ):
            raise PublisherError("snapshot URL is not a canonical allowlisted HTTPS URL")

        parameters = source_task.get("parameters", {})
        if not isinstance(parameters, Mapping) or not isinstance(parameters.get("source_url"), str):
            raise PublisherError("source task has no source URL parameter")
        try:
            task_url = urlsplit(parameters["source_url"])
            task_host = (task_url.hostname or "").lower()
            task_port = task_url.port
        except ValueError:
            raise PublisherError("source task URL is invalid") from None
        if (
            task_url.scheme != "https"
            or task_host != domain
            or task_url.username is not None
            or task_url.password is not None
            or task_port not in (None, 443)
        ):
            raise PublisherError("source task URL is not the allowlisted HTTPS host")
        expected_safe_url = urlunsplit(("https", domain, task_url.path or "/", "", ""))
        if (
            envelope.get("source_url") != expected_safe_url
            or envelope.get("source_url_sha256") != sha256_text(parameters["source_url"])
        ):
            raise PublisherError("snapshot URL canonicalization/hash does not match the original task URL")

        provenance = envelope.get("provenance", {})
        if not isinstance(provenance, Mapping):
            raise PublisherError("snapshot provenance must be an object")
        for field in ("category_id", "destination_id"):
            if source_task.get(field) != provenance.get(field):
                raise PublisherError(f"snapshot provenance mismatch: {field}")
        for field in ("source_row_ref", "source_line", "archive_sha256"):
            if parameters.get(field) != provenance.get(field):
                raise PublisherError(f"snapshot source provenance mismatch: {field}")

        retention = envelope.get("retention", {})
        if (
            not isinstance(retention, Mapping)
            or retention.get("mode") != "METADATA_ONLY"
            or retention.get("raw_body_persisted") is not False
            or retention.get("full_page_mirroring") is not False
            or retention.get("query_and_fragment_persisted") is not False
        ):
            raise PublisherError("snapshot retention policy is not metadata-only")

        snapshot_id = proposal.get("snapshot_id")
        digest = sha256_text(canonical_json(envelope))
        expected_snapshot_path = f"evidence/snapshots/sha256/{digest}.json"
        if (
            envelope.get("snapshot_id") != snapshot_id
            or proposal.get("source_snapshot_envelope_sha256") != digest
            or proposal.get("source_snapshot_content_ref") != f"sha256:{digest}"
            or proposal.get("source_snapshot_storage_path") != expected_snapshot_path
        ):
            raise PublisherError("snapshot content reference, path or digest mismatch")

        unsigned = {key: value for key, value in proposal.items() if key != "proposal_sha256"}
        expected_proposal_hash = sha256_text(canonical_json(unsigned))
        if proposal.get("proposal_sha256") != expected_proposal_hash:
            raise PublisherError("source-worker proposal digest mismatch")

        if (
            evidence.get("task_id") != proposal.get("task_id")
            or evidence.get("source_snapshot_ids") != [snapshot_id]
            or evidence.get("category_id") != provenance.get("category_id")
            or evidence.get("destination_id") != provenance.get("destination_id")
            or evidence.get("evidence_excerpt") != envelope.get("excerpt", "")[:1500]
            or evidence.get("reviewer_verdict") != "PENDING"
            or evidence.get("gate_status") != "UNKNOWN"
            or evidence.get("model_provider") is not None
        ):
            raise PublisherError("evidence proposal does not match its source snapshot or pending-review policy")
        evidence_provenance = evidence.get("source_provenance", {})
        if not isinstance(evidence_provenance, Mapping):
            raise PublisherError("evidence source provenance must be an object")
        for field in ("source_row_ref", "source_line", "archive_sha256"):
            if evidence_provenance.get(field) != provenance.get(field):
                raise PublisherError(f"evidence provenance mismatch: {field}")

        snapshot_raw = canonical_json(envelope)
        proposal_raw = canonical_json(proposal)
        proposal_file_digest = sha256_text(proposal_raw)
        proposal_path = f"evidence/proposals/sha256/{proposal_file_digest}.json"

        snapshot_object = {
            "schema_version": "1.0.0",
            "project_id": PROJECT_ID,
            "snapshot_id": snapshot_id,
            "source_url": envelope["source_url"],
            "source_domain": envelope["source_domain"],
            "publisher": envelope["publisher"],
            "page_title": envelope["page_title"],
            "captured_at": envelope["captured_at"],
            "last_updated_at": envelope["last_updated_at"],
            "content_sha256": envelope["raw_body_sha256"],
            "excerpt": envelope["excerpt"],
            "fetch_status": envelope["fetch_status"],
            "trust_boundary": "UNTRUSTED_DATA_ONLY",
            "access_mode": "PUBLIC_READ_ONLY",
            "access_control_bypass": False,
            "content_ref": f"sha256:{digest}",
        }
        self._validate("source_snapshot", snapshot_object)

        return {
            "proposal": dict(proposal),
            "source_task": dict(source_task),
            "envelope": dict(envelope),
            "evidence": dict(evidence),
            "snapshot_object": snapshot_object,
            "snapshot_digest": digest,
            "snapshot_raw": snapshot_raw,
            "snapshot_path": expected_snapshot_path,
            "proposal_digest": proposal_file_digest,
            "proposal_raw": proposal_raw,
            "proposal_path": proposal_path,
        }

    def _existing_object(
        self,
        kind: str,
        object_id: str,
        head: str,
        manifest: Mapping[str, Any],
    ) -> dict[str, Any] | None:
        matches = [
            item for item in manifest.get("objects", [])
            if item.get("kind") == kind and item.get("object_id") == object_id
        ]
        if not matches:
            return None
        return self.state_repository.load_object(kind, object_id, head, manifest)

    def _assert_same_or_absent(
        self,
        kind: str,
        object_id: str,
        payload: Mapping[str, Any],
        head: str,
        manifest: Mapping[str, Any],
    ) -> bool:
        existing = self._existing_object(kind, object_id, head, manifest)
        if existing is None:
            return False
        if canonical_json(existing) != canonical_json(payload):
            raise IdempotencyConflict(f"{kind} identity already exists with different immutable content: {object_id}")
        return True

    def reconcile_batch(
        self,
        *,
        proposals: list[Mapping[str, Any]],
        source_tasks: Mapping[str, Mapping[str, Any]],
    ) -> dict[str, Any]:
        """Read-only reconciliation after an ambiguous publisher commit response."""
        if not isinstance(proposals, list) or not 1 <= len(proposals) <= 2:
            raise PublisherError("reconciliation accepts one or two proposals per bounded batch")
        if not isinstance(source_tasks, Mapping):
            raise PublisherError("source_tasks must map exact task IDs to task objects")

        head, manifest = self.state_repository.load()
        statuses: dict[str, str] = {}
        seen_tasks: set[str] = set()
        for proposal in proposals:
            if not isinstance(proposal, Mapping):
                raise PublisherError("reconciliation proposal must be an object")
            task_id = proposal.get("task_id")
            if not isinstance(task_id, str) or not task_id or task_id in seen_tasks:
                raise PublisherError("reconciliation batch has a missing or duplicate task ID")
            seen_tasks.add(task_id)
            source_task = source_tasks.get(task_id)
            if source_task is None:
                raise PublisherError("reconciliation is missing the exact source task")
            item = self._prepare_proposal(proposal, source_task)
            existing_task = self._existing_object("task", task_id, head, manifest)
            if existing_task is None:
                statuses[task_id] = "ABSENT"
                continue
            if existing_task.get("idempotency_key") != proposal.get("idempotency_key"):
                raise IdempotencyConflict("task ID was reused with a different idempotency key")
            if existing_task.get("status") != "COMPLETED":
                statuses[task_id] = str(existing_task.get("status", "UNKNOWN"))
                continue

            snapshot_id = item["envelope"]["snapshot_id"]
            evidence_id = item["evidence"]["evidence_id"]
            if (
                snapshot_id not in existing_task.get("source_snapshot_ids", [])
                or evidence_id not in existing_task.get("evidence_ids", [])
            ):
                raise IdempotencyConflict("completed task references different immutable evidence")
            if not self._assert_same_or_absent(
                "source_snapshot", snapshot_id, item["snapshot_object"], head, manifest
            ):
                raise IdempotencyConflict("completed task is missing its immutable source-snapshot object")
            if not self._assert_same_or_absent(
                "evidence", evidence_id, item["evidence"], head, manifest
            ):
                raise IdempotencyConflict("completed task is missing its immutable evidence object")
            stored_snapshot = self.state_repository.store.read_file(item["snapshot_path"], ref=head)
            stored_proposal = self.state_repository.store.read_file(item["proposal_path"], ref=head)
            if stored_snapshot != item["snapshot_raw"] or stored_proposal != item["proposal_raw"]:
                raise IdempotencyConflict("completed task's immutable evidence files do not match the retry")
            statuses[task_id] = "PUBLISHED"

        published = [task_id for task_id, status in statuses.items() if status == "PUBLISHED"]
        if len(published) == len(proposals):
            return {
                "status": "ALREADY_PUBLISHED",
                "commit_sha": head,
                "task_ids": published,
                "task_statuses": statuses,
                "external_action_performed": False,
                "write_performed": False,
            }
        if not published:
            return {
                "status": "NOT_PUBLISHED",
                "commit_sha": head,
                "task_statuses": statuses,
                "active_writer_lease_id": manifest.get("active_writer_lease_id"),
                "external_action_performed": False,
                "write_performed": False,
            }
        raise PublisherError("batch reconciliation found partial publication; fail closed")

    def publish_batch(
        self,
        *,
        lease_id: str,
        lease_commit_sha: str,
        proposals: list[Mapping[str, Any]],
        source_tasks: Mapping[str, Mapping[str, Any]],
        run_state: Mapping[str, Any],
        now: datetime,
        message: str = "zcira: publish validated metadata-only evidence batch",
    ) -> dict[str, Any]:
        if not isinstance(proposals, list) or not 1 <= len(proposals) <= 2:
            raise PublisherError("publisher accepts one or two proposals per bounded transaction")
        if not isinstance(source_tasks, Mapping):
            raise PublisherError("source_tasks must map exact task IDs to task objects")
        now_iso = _utc_iso(now)
        self._validate("run_state", run_state)
        if (
            run_state.get("project_id") != PROJECT_ID
            or run_state.get("kill_switch") is not False
            or run_state.get("paid_provider_routes_enabled") is not False
            or run_state.get("spend_cap_inr") != 0
            or run_state.get("max_parallel_research_workers") != 2
            or run_state.get("single_writer_role") != SINGLE_WRITER_ROLE
            or run_state.get("status") in {"PAUSED", "COMPLETED", "FAILED"}
        ):
            raise PublisherError("run state violates the active read-only publisher policy")

        head, manifest = self.state_repository.load()
        if head != lease_commit_sha:
            raise StaleCheckpoint("publisher lease checkpoint is not the current canonical branch head")
        if manifest.get("kill_switch") is not False:
            raise PublisherError("durable kill switch blocks publication")
        if manifest.get("active_writer_lease_id") != lease_id:
            raise PublisherError("publisher does not hold the active canonical writer lease")

        prepared: list[dict[str, Any]] = []
        seen_tasks: set[str] = set()
        seen_snapshots: set[str] = set()
        seen_evidence: set[str] = set()
        for proposal in proposals:
            task_id = proposal.get("task_id") if isinstance(proposal, Mapping) else None
            if not isinstance(task_id, str) or task_id in seen_tasks:
                raise PublisherError("batch contains a missing or duplicate task ID")
            seen_tasks.add(task_id)
            source_task = source_tasks.get(task_id)
            if source_task is None:
                raise PublisherError("publisher is missing the exact source task for a proposal")
            item = self._prepare_proposal(proposal, source_task)
            snapshot_id = item["envelope"]["snapshot_id"]
            evidence_id = item["evidence"]["evidence_id"]
            if snapshot_id in seen_snapshots or evidence_id in seen_evidence:
                raise PublisherError("batch contains duplicate snapshot or evidence identities")
            seen_snapshots.add(snapshot_id)
            seen_evidence.add(evidence_id)
            prepared.append(item)

        # Prefer the already-persisted run state so stale caller state cannot
        # erase completed tasks or reset the original run clock.
        run_id = run_state["run_id"]
        current_run = self._existing_object("run_state", run_id, head, manifest)
        base_run = copy.deepcopy(current_run if current_run is not None else dict(run_state))
        if base_run.get("started_at") != run_state.get("started_at"):
            if current_run is None:
                raise PublisherError("run start clock changed during publication")
        if base_run.get("kill_switch") is not False or base_run.get("status") in {"PAUSED", "COMPLETED", "FAILED"}:
            raise PublisherError("persisted run state is paused or terminal")

        new_items: list[dict[str, Any]] = []
        duplicate_items: list[dict[str, Any]] = []
        for item in prepared:
            proposal = item["proposal"]
            task_id = proposal["task_id"]
            existing_task = self._existing_object("task", task_id, head, manifest)
            if existing_task is not None:
                if existing_task.get("idempotency_key") != proposal.get("idempotency_key"):
                    raise IdempotencyConflict("task ID was reused with a different idempotency key")
                if existing_task.get("status") == "COMPLETED":
                    snapshot_id = item["envelope"]["snapshot_id"]
                    evidence_id = item["evidence"]["evidence_id"]
                    if (
                        snapshot_id not in existing_task.get("source_snapshot_ids", [])
                        or evidence_id not in existing_task.get("evidence_ids", [])
                    ):
                        raise IdempotencyConflict("completed task points to different immutable evidence")
                    if not self._assert_same_or_absent("source_snapshot", snapshot_id, item["snapshot_object"], head, manifest):
                        raise IdempotencyConflict("completed task is missing its immutable source-snapshot state object")
                    if not self._assert_same_or_absent("evidence", evidence_id, item["evidence"], head, manifest):
                        raise IdempotencyConflict("completed task is missing its immutable evidence state object")
                    stored_snapshot = self.state_repository.store.read_file(item["snapshot_path"], ref=head)
                    stored_proposal = self.state_repository.store.read_file(item["proposal_path"], ref=head)
                    if stored_snapshot != item["snapshot_raw"] or stored_proposal != item["proposal_raw"]:
                        raise IdempotencyConflict("completed task's immutable evidence files do not match the retry")
                    duplicate_items.append(item)
                    continue
            if existing_task is None and item["source_task"].get("status") == "COMPLETED":
                raise PublisherError("a completed source task must already exist in the canonical state manifest")
            if existing_task is not None and item["source_task"].get("status") == "COMPLETED" and existing_task.get("status") != "COMPLETED":
                raise PublisherError("caller task state conflicts with the canonical task state")
            new_items.append(item)

        if not new_items:
            released_head = self.state_repository.release_writer_lease(
                lease_id, lease_commit_sha, now,
                message="zcira: release writer lease after idempotent duplicate batch",
            )
            return {
                "status": "ALREADY_PUBLISHED",
                "commit_sha": released_head,
                "duplicate_task_ids": [item["proposal"]["task_id"] for item in duplicate_items],
                "published_task_ids": [],
                "snapshot_paths": [],
                "proposal_paths": [],
                "external_action_performed": False,
            }

        objects: list[tuple[str, str, Mapping[str, Any]]] = []
        extra_files: dict[str, str] = {}
        completed_task_ids: list[str] = []
        review_task_ids: list[str] = []
        for item in new_items:
            proposal = item["proposal"]
            source_task = copy.deepcopy(item["source_task"])
            task_id = proposal["task_id"]
            snapshot_id = proposal["snapshot_id"]
            evidence = item["evidence"]
            evidence_id = evidence["evidence_id"]

            self._assert_same_or_absent("source_snapshot", snapshot_id, item["snapshot_object"], head, manifest)
            self._assert_same_or_absent("evidence", evidence_id, evidence, head, manifest)

            source_task["status"] = "COMPLETED"
            source_task["updated_at"] = now_iso
            source_task["source_snapshot_ids"] = sorted(set(source_task.get("source_snapshot_ids", [])) | {snapshot_id})
            source_task["evidence_ids"] = sorted(set(source_task.get("evidence_ids", [])) | {evidence_id})
            source_task["lease_id"] = None
            source_task["checkpoint"] = None
            self._validate("task", source_task)

            review_task_id = "zcira-review-" + snapshot_id.removeprefix("snapshot-")
            review_idempotency = sha256_text(canonical_json({
                "project_id": PROJECT_ID,
                "task_id": review_task_id,
                "snapshot_sha256": item["snapshot_digest"],
                "evidence_id": evidence_id,
            }))
            review_task = {
                "schema_version": "1.0.0",
                "project_id": PROJECT_ID,
                "mission_id": PROJECT_ID,
                "task_id": review_task_id,
                "idempotency_key": review_idempotency,
                "task_type": "evidence_review",
                "priority": source_task["priority"],
                "category_id": source_task["category_id"],
                "destination_id": source_task["destination_id"],
                "status": "QUEUED",
                "created_at": now_iso,
                "updated_at": now_iso,
                "attempt_count": 0,
                "max_attempts": 2,
                "allowed_actions": [],
                "external_actions_allowed": False,
                "paid_provider_routes_enabled": False,
                "parameters": {
                    "source_task_id": task_id,
                    "snapshot_content_ref": f"sha256:{item['snapshot_digest']}",
                    "snapshot_storage_path": item["snapshot_path"],
                    "proposal_content_ref": f"sha256:{item['proposal_digest']}",
                    "proposal_storage_path": item["proposal_path"],
                    "evidence_id": evidence_id,
                    "review_mode": "METADATA_ONLY_INTERNAL",
                },
                "source_snapshot_ids": [snapshot_id],
                "evidence_ids": [evidence_id],
                "lease_id": None,
                "checkpoint": None,
                "assigned_role": "adversarial_auditor",
            }
            self._validate("task", review_task)
            self._assert_same_or_absent("task", review_task_id, review_task, head, manifest)

            objects.extend([
                ("source_snapshot", snapshot_id, item["snapshot_object"]),
                ("evidence", evidence_id, evidence),
                ("task", task_id, source_task),
                ("task", review_task_id, review_task),
            ])
            extra_files[item["snapshot_path"]] = item["snapshot_raw"]
            extra_files[item["proposal_path"]] = item["proposal_raw"]
            completed_task_ids.append(task_id)
            review_task_ids.append(review_task_id)

        pending = set(base_run.get("pending_task_ids", []))
        completed = set(base_run.get("completed_task_ids", []))
        for task_id in completed_task_ids:
            if task_id not in pending and base_run.get("current_task_id") != task_id:
                raise PublisherError("source task is not pending/current in the canonical run state")
            pending.discard(task_id)
            completed.add(task_id)
        pending.update(review_task_ids)
        base_run["pending_task_ids"] = sorted(pending)
        base_run["completed_task_ids"] = sorted(completed)
        if base_run.get("current_task_id") in set(completed_task_ids):
            base_run["current_task_id"] = None
        base_run["status"] = "PARTIAL"
        base_run["finished_at"] = None
        base_run["last_heartbeat_at"] = now_iso
        base_run["latest_commit_sha"] = lease_commit_sha
        self._validate("run_state", base_run)
        objects.append(("run_state", run_id, base_run))

        final_head = self.state_repository.commit_and_release(
            lease_id,
            lease_commit_sha,
            objects,
            now,
            message,
            extra_files=extra_files,
        )
        verified_head, verified_manifest = self.state_repository.load()
        if verified_head != final_head or verified_manifest.get("active_writer_lease_id") is not None:
            raise PublisherError("publisher commit did not become the verified unlocked canonical head")
        return {
            "status": "PUBLISHED",
            "commit_sha": final_head,
            "duplicate_task_ids": [item["proposal"]["task_id"] for item in duplicate_items],
            "published_task_ids": completed_task_ids,
            "queued_review_task_ids": review_task_ids,
            "snapshot_paths": [item["snapshot_path"] for item in new_items],
            "proposal_paths": [item["proposal_path"] for item in new_items],
            "run_id": run_id,
            "run_status": base_run["status"],
            "external_action_performed": False,
        }
