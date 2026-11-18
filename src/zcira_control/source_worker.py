from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping
from urllib.parse import urlsplit

from jsonschema import Draft202012Validator, FormatChecker

from .policy import validate_task
from .source_fetcher import FetchOutcome, SourcePolicy, Transport, fetch_public_source


@dataclass(frozen=True)
class SourceWorkerResult:
    status: str
    snapshot: dict
    evidence_proposal: dict | None
    raw_content: bytes | None
    status_code: int | None
    retry_after_seconds: int | None
    reason: str | None


def run_source_snapshot_task(
    task: Mapping[str, Any],
    mission_context: Mapping[str, Any],
    source_policy: SourcePolicy,
    task_schema: Mapping[str, Any],
    source_snapshot_schema: Mapping[str, Any],
    evidence_schema: Mapping[str, Any],
    *,
    transport: Transport | None = None,
    now: datetime | None = None,
) -> SourceWorkerResult:
    """Execute one public-read source task; never writes, submits or calls an LLM."""
    validate_task(task, mission_context)
    Draft202012Validator(task_schema, format_checker=FormatChecker()).validate(task)
    if task.get("task_type") != "source_snapshot":
        raise ValueError("task_type must be source_snapshot")
    if task.get("assigned_role") not in {"official_source_worker_a", "official_source_worker_b"}:
        raise ValueError("task is not assigned to an official source worker")
    allowed = set(task.get("allowed_actions", []))
    if not {"READ_PUBLIC", "PARSE_PUBLIC", "HASH_PUBLIC"}.issubset(allowed):
        raise ValueError("source task lacks required read/parse/hash actions")
    if task.get("external_actions_allowed") is not False or task.get("paid_provider_routes_enabled") is not False:
        raise ValueError("source worker rejects external actions and paid provider routes")
    parameters = task.get("parameters")
    if not isinstance(parameters, Mapping) or not isinstance(parameters.get("source_url"), str):
        raise ValueError("source task requires parameters.source_url")
    source_host = (urlsplit(parameters["source_url"]).hostname or "").lower()
    source_record = source_policy.allowed_sources.get(source_host)
    if source_record is None:
        raise ValueError("source task host is not in the exact source allowlist")
    if task.get("priority") != source_record.priority:
        raise ValueError("task priority does not match the locked source priority")

    outcome: FetchOutcome = fetch_public_source(
        parameters["source_url"], source_policy, transport=transport, now=now
    )
    Draft202012Validator(source_snapshot_schema, format_checker=FormatChecker()).validate(outcome.snapshot)
    if outcome.snapshot["fetch_status"] != "CAPTURED":
        status = "BLOCKED" if outcome.snapshot["fetch_status"] == "BLOCKED_BY_POLICY" else "PARTIAL"
        return SourceWorkerResult(
            status, outcome.snapshot, None, outcome.raw_content,
            outcome.status_code, outcome.retry_after_seconds, outcome.error_code
        )

    excerpt = outcome.snapshot["excerpt"][:1500]
    if not excerpt:
        return SourceWorkerResult(
            "PARTIAL", outcome.snapshot, None, outcome.raw_content,
            outcome.status_code, outcome.retry_after_seconds, "NO_EVIDENCE_EXCERPT"
        )
    digest = outcome.snapshot["content_sha256"]
    evidence_id = "evidence-" + hashlib.sha256(
        f"{task['task_id']}:{outcome.snapshot['snapshot_id']}".encode("utf-8")
    ).hexdigest()[:32]
    source_row_ref = parameters.get("source_row_ref")
    source_line = parameters.get("source_line")
    archive_sha = parameters.get("archive_sha256")
    if not isinstance(source_row_ref, str):
        source_row_ref = None
    if not isinstance(source_line, int) or isinstance(source_line, bool) or source_line < 1:
        source_line = None
    if not isinstance(archive_sha, str) or not re.fullmatch(r"[a-f0-9]{64}", archive_sha):
        archive_sha = None
    captured_at = now or datetime.now(timezone.utc)
    if captured_at.tzinfo is None:
        raise ValueError("clock must return a timezone-aware datetime")
    created_at = captured_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    source_record = source_policy.allowed_sources[outcome.snapshot["source_domain"]]
    evidence = {
        "schema_version": "1.0.0",
        "project_id": outcome.snapshot["project_id"],
        "evidence_id": evidence_id,
        "claim_id": f"source-capture:{outcome.snapshot['source_domain']}:{digest[:16]}",
        "task_id": task["task_id"],
        "category_id": task.get("category_id"),
        "destination_id": task.get("destination_id"),
        "claim": "The allowlisted public source page was captured and SHA-256 hashed; substantive commercial gate status remains UNKNOWN.",
        "source_snapshot_ids": [outcome.snapshot["snapshot_id"]],
        "evidence_excerpt": excerpt,
        "evidence_grade": source_record.evidence_grade,
        "reviewer_verdict": "PENDING",
        "gate_status": "UNKNOWN",
        "source_provenance": {
            "source_row_ref": source_row_ref,
            "source_line": source_line,
            "archive_sha256": archive_sha,
        },
        "model_provider": None,
        "created_at": created_at,
    }
    Draft202012Validator(evidence_schema, format_checker=FormatChecker()).validate(evidence)
    return SourceWorkerResult(
        "COMPLETED", outcome.snapshot, evidence, outcome.raw_content,
        outcome.status_code, outcome.retry_after_seconds, None
    )
