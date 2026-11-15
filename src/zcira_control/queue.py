from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable, Mapping

from .policy import MAX_PARALLEL_RESEARCH_WORKERS, PRIORITY_RANK, SINGLE_WRITER_ROLE, PolicyError, validate_task
from .leases import lease_is_active


def _time_key(value: str) -> str:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise PolicyError("created_at must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise PolicyError("created_at must include a timezone")
    return parsed.astimezone(timezone.utc).isoformat()


def plan_batch(
    tasks: Iterable[Mapping[str, Any]],
    mission_context: Mapping[str, Any],
    max_parallel: int = MAX_PARALLEL_RESEARCH_WORKERS,
) -> list[dict[str, Any]]:
    """Return a deterministic read-only research plan. No task is executed or leased."""
    if max_parallel != MAX_PARALLEL_RESEARCH_WORKERS:
        raise PolicyError("parallel worker limit is locked at two")
    eligible: list[dict[str, Any]] = []
    for raw in tasks:
        task = dict(raw)
        validate_task(task, mission_context)
        if task.get("status") != "QUEUED":
            continue
        if task.get("assigned_role") == SINGLE_WRITER_ROLE or "WRITE_REPO_VALIDATED" in task.get("allowed_actions", []):
            continue
        task["_created_sort"] = _time_key(task.get("created_at"))
        eligible.append(task)
    eligible.sort(key=lambda item: (PRIORITY_RANK[item["priority"]], item["_created_sort"], item["task_id"]))
    selected: list[dict[str, Any]] = []
    seen_idempotency: set[str] = set()
    for task in eligible:
        key = task["idempotency_key"]
        if key in seen_idempotency:
            continue
        seen_idempotency.add(key)
        selected.append(task)
        if len(selected) >= MAX_PARALLEL_RESEARCH_WORKERS:
            break
    for task in selected:
        task.pop("_created_sort", None)
    return selected


def plan_publisher_task(
    tasks: Iterable[Mapping[str, Any]],
    mission_context: Mapping[str, Any],
    active_leases: Iterable[Mapping[str, Any]],
    now: datetime,
) -> dict[str, Any] | None:
    """Select at most one repository-writer task, and only when its lease is free."""
    if any(lease.get("resource_key") == "repo-main-single-writer" and lease.get("project_id") == mission_context.get("project_id") and lease.get("canonical_repo") == mission_context.get("canonical_repo") and lease.get("state_namespace") == mission_context.get("state_namespace") and lease_is_active(lease, now) for lease in active_leases):
        return None
    candidates: list[dict[str, Any]] = []
    for raw in tasks:
        task = dict(raw)
        validate_task(task, mission_context)
        if task.get("status") != "QUEUED":
            continue
        if task.get("assigned_role") != SINGLE_WRITER_ROLE or "WRITE_REPO_VALIDATED" not in task.get("allowed_actions", []):
            continue
        task["_created_sort"] = _time_key(task.get("created_at"))
        candidates.append(task)
    candidates.sort(key=lambda item: (PRIORITY_RANK[item["priority"]], item["_created_sort"], item["task_id"]))
    if not candidates:
        return None
    selected = candidates[0]
    selected.pop("_created_sort", None)
    return selected
