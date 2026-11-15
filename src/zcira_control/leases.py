from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable, Mapping

from .policy import (
    CANONICAL_BRANCH,
    CANONICAL_REPO,
    ENVIRONMENT_NAMESPACE,
    PROJECT_ID,
    SINGLE_WRITER_ROLE,
    STATE_NAMESPACE,
    PolicyError,
    validate_git_sha,
)


def _parse_time(value: str) -> datetime:
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise PolicyError("lease timestamp must be ISO-8601") from exc
    if result.tzinfo is None:
        raise PolicyError("lease timestamp must include a timezone")
    return result.astimezone(timezone.utc)


def lease_is_active(lease: Mapping[str, Any], now: datetime) -> bool:
    if now.tzinfo is None:
        raise PolicyError("lease comparison time must include a timezone")
    return lease.get("status") == "ACTIVE" and _parse_time(lease["expires_at"]) > now.astimezone(timezone.utc)


def validate_lease(lease: Mapping[str, Any], now: datetime) -> None:
    expected = {
        "project_id": PROJECT_ID,
        "mission_id": PROJECT_ID,
        "canonical_repo": CANONICAL_REPO,
        "branch": CANONICAL_BRANCH,
        "environment_namespace": ENVIRONMENT_NAMESPACE,
        "state_namespace": STATE_NAMESPACE,
        "cross_mission_share_allowed": False,
    }
    for key, value in expected.items():
        if lease.get(key) != value:
            raise PolicyError(f"lease scope mismatch: {key}")
    if lease.get("lease_kind") not in {"REPOSITORY_SINGLE_WRITER", "TASK_EXECUTION"}:
        raise PolicyError("unknown lease kind")
    if lease.get("status") not in {"ACTIVE", "RELEASED", "EXPIRED", "CONFLICTED"}:
        raise PolicyError("unknown lease status")
    if now.tzinfo is None:
        raise PolicyError("lease validation time must include a timezone")
    if lease.get("lease_kind") == "REPOSITORY_SINGLE_WRITER":
        if lease.get("resource_key") != "repo-main-single-writer":
            raise PolicyError("repository writer lease must use the canonical resource key")
        if lease.get("holder_role") != SINGLE_WRITER_ROLE or lease.get("write_access") is not True:
            raise PolicyError("only evidence_publisher may hold the repository single-writer lease")
    elif lease.get("write_access") is True and lease.get("holder_role") != SINGLE_WRITER_ROLE:
        raise PolicyError("research workers are read-only")
    if _parse_time(lease["expires_at"]) <= _parse_time(lease["acquired_at"]):
        raise PolicyError("lease expiry must be later than acquisition")
    if lease.get("status") == "ACTIVE" and _parse_time(lease["expires_at"]) <= now.astimezone(timezone.utc):
        raise PolicyError("active lease is already expired")
    validate_git_sha(lease.get("base_commit_sha"), allow_none=True)


def acquire_lease(
    existing: Iterable[Mapping[str, Any]], proposed: Mapping[str, Any], now: datetime
) -> dict[str, Any]:
    candidate = dict(proposed)
    validate_lease(candidate, now)
    for lease in existing:
        same_scope = (lease.get("project_id"), lease.get("canonical_repo"), lease.get("state_namespace")) == (candidate.get("project_id"), candidate.get("canonical_repo"), candidate.get("state_namespace"))
        if same_scope and lease.get("resource_key") == candidate.get("resource_key") and lease_is_active(lease, now):
            if lease.get("lease_id") != candidate.get("lease_id"):
                raise PolicyError("resource already has an active lease")
            if dict(lease) != candidate:
                raise PolicyError("lease idempotency collision: same lease ID has different content")
    return candidate
