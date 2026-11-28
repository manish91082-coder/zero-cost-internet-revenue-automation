from __future__ import annotations

import re
from fnmatch import fnmatchcase
from pathlib import PurePosixPath
from datetime import datetime, timezone
from typing import Any, Mapping

PROJECT_ID = "ZCIRA-2026-11-13"
CANONICAL_REPO = "manish91082-coder/zero-cost-internet-revenue-automation"
CANONICAL_CODE_BRANCH = "main"
CANONICAL_STATE_BRANCH = "evidence-ledger"
CANONICAL_BRANCH = CANONICAL_CODE_BRANCH
ENVIRONMENT_NAMESPACE = "zcira-readonly-research"
LEGACY_STATE_NAMESPACE = "zcira-2026-11-13/main"
STATE_NAMESPACE = "zcira-2026-11-13/evidence-ledger"
PRIORITY_ORDER = ("P1", "P2", "P3", "P4", "P5", "B", "M")
PRIORITY_RANK = {value: index for index, value in enumerate(PRIORITY_ORDER)}
MAX_PARALLEL_RESEARCH_WORKERS = 2
SINGLE_WRITER_ROLE = "evidence_publisher"
SPEND_CAP_INR = 0
ALLOWED_TASK_ACTIONS = frozenset({
    "READ_PUBLIC",
    "PARSE_PUBLIC",
    "HASH_PUBLIC",
    "CREATE_INTERNAL_DRAFT",
    "WRITE_REPO_VALIDATED",
})
GATE_NAMES = (
    "buyer_demand",
    "ip_licensing_data_rights",
    "zero_cost_economics",
    "india_seller_eligibility_settlement",
    "autonomous_fulfilment_workload",
)
SHA256_RE = re.compile(r"^[a-f0-9]{64}$")
SHA1_RE = re.compile(r"^[a-f0-9]{40}$")


class PolicyError(ValueError):
    """Raised when a task, mission, or action violates locked policy."""


def validate_mission_context(context: Mapping[str, Any]) -> None:
    expected = {
        "project_id": PROJECT_ID,
        "mission_id": PROJECT_ID,
        "canonical_repo": CANONICAL_REPO,
        "branch": CANONICAL_CODE_BRANCH,
        "state_branch": CANONICAL_STATE_BRANCH,
        "environment_namespace": ENVIRONMENT_NAMESPACE,
        "state_namespace": STATE_NAMESPACE,
        "max_parallel_research_workers": MAX_PARALLEL_RESEARCH_WORKERS,
        "single_writer_role": SINGLE_WRITER_ROLE,
        "spend_cap_inr": SPEND_CAP_INR,
        "paid_fallback_allowed": False,
        "trial_credit_dependency_allowed": False,
        "shared_state_with_other_missions": False,
        "cross_mission_write_allowed": False,
        "active": True,
    }
    for key, value in expected.items():
        if context.get(key) != value:
            raise PolicyError(f"mission context mismatch: {key}")
    allowed = context.get("allowed_action_classes")
    denied = context.get("denied_action_classes")
    if not isinstance(allowed, list) or not set(allowed).issubset(ALLOWED_TASK_ACTIONS):
        raise PolicyError("mission action allowlist is invalid")
    required_denials = {"PAID_FALLBACK", "BILLING_ENABLE", "ACCOUNT_CREATE", "KYC", "ACCEPT_TERMS", "CONTACT_EXTERNAL", "SUBMIT", "SECURITY_TEST", "PUBLISH_PRODUCT", "WALLET_SIGN", "TRANSFER_FUNDS"}
    if not isinstance(denied, list) or not required_denials.issubset(set(denied)):
        raise PolicyError("mission action denylist is incomplete")
    if not isinstance(context.get("allowed_paths"), list) or not isinstance(context.get("denied_paths"), list):
        raise PolicyError("mission path allowlist/denylist is missing")



def validate_repo_path(path: str, context: Mapping[str, Any]) -> None:
    """Validate a repository-relative path against mission allow/deny patterns."""
    if not isinstance(path, str) or not path or path.startswith("/") or "\\" in path:
        raise PolicyError("repository path must be relative POSIX path")
    normalized = str(PurePosixPath(path))
    if normalized != path or ".." in PurePosixPath(path).parts or "." in PurePosixPath(path).parts:
        raise PolicyError("repository path traversal or non-canonical path")
    if any(fnmatchcase(path, pattern) for pattern in context["denied_paths"]):
        raise PolicyError("repository path is explicitly denied")
    if not any(fnmatchcase(path, pattern) for pattern in context["allowed_paths"]):
        raise PolicyError("repository path is outside the mission allowlist")


def validate_task(task: Mapping[str, Any], context: Mapping[str, Any]) -> None:
    validate_mission_context(context)
    if task.get("project_id") != PROJECT_ID or task.get("mission_id") != PROJECT_ID:
        raise PolicyError("task belongs to another mission")
    if task.get("canonical_repo", CANONICAL_REPO) != CANONICAL_REPO:
        raise PolicyError("task targets a non-canonical repository")
    if task.get("branch", CANONICAL_BRANCH) != CANONICAL_BRANCH:
        raise PolicyError("task targets a non-canonical branch")
    required = ("task_id", "priority", "status", "created_at", "idempotency_key", "allowed_actions")
    missing = [key for key in required if key not in task]
    if missing:
        raise PolicyError(f"task missing required fields: {', '.join(missing)}")
    priority = task.get("priority")
    if priority not in PRIORITY_RANK:
        raise PolicyError("unknown or changed priority")
    if task.get("category_id") == 24 and priority != "B":
        raise PolicyError("Category 24 is locked at priority B")
    if task.get("external_actions_allowed") is not False:
        raise PolicyError("external actions are not allowed in a task")
    if task.get("paid_provider_routes_enabled") is not False:
        raise PolicyError("paid provider routes must remain disabled")
    if task.get("max_attempts") != 2:
        raise PolicyError("max_attempts must remain 2")
    attempt_count = task.get("attempt_count", 0)
    if not isinstance(attempt_count, int) or attempt_count < 0 or attempt_count > 2:
        raise PolicyError("attempt_count outside policy")
    role = task.get("assigned_role")
    if role is not None and role not in {
        "mission_controller", "discovery_worker", "official_source_worker_a",
        "official_source_worker_b", "eligibility_payout_agent", "ip_licensing_agent",
        "economics_workload_agent", "adversarial_auditor", SINGLE_WRITER_ROLE,
    }:
        raise PolicyError("unknown agent role")
    actions = task.get("allowed_actions", [])
    if not isinstance(actions, list) or not set(actions).issubset(ALLOWED_TASK_ACTIONS) or not set(actions).issubset(set(context["allowed_action_classes"])):
        raise PolicyError("task contains an unapproved action class")
    if task.get("status") not in {"QUEUED", "LEASED", "RUNNING", "BLOCKED", "COMPLETED", "FAILED", "DEAD_LETTER", "CANCELLED"}:
        raise PolicyError("unknown task status")
    if "WRITE_REPO_VALIDATED" in actions:
        if role != SINGLE_WRITER_ROLE:
            raise PolicyError("only evidence_publisher may request validated repository writes")
        target_path = task.get("parameters", {}).get("target_path")
        validate_repo_path(target_path, context)
    key = task.get("idempotency_key", "")
    if not isinstance(key, str) or not SHA256_RE.fullmatch(key):
        raise PolicyError("idempotency_key must be a SHA-256 hex digest")


def evaluate_commercial_release(
    gates: Mapping[str, Mapping[str, Any]],
    owner_approval: Mapping[str, Any] | None,
    expected_action: str,
    expected_target: str,
    now: datetime,
) -> dict[str, Any]:
    """Evaluate the five gates and exact approval record; never execute the action."""
    missing = [name for name in GATE_NAMES if name not in gates]
    if missing:
        return {"overall_status": "UNKNOWN", "release_authorized": False, "reason": "MISSING_GATES", "missing": missing}
    statuses = {name: gates[name].get("status") for name in GATE_NAMES}
    if any(status == "FAIL" for status in statuses.values()):
        return {"overall_status": "FAIL", "release_authorized": False, "reason": "A_GATE_FAILED"}
    if any(status != "PASS" for status in statuses.values()):
        return {"overall_status": "HOLD", "release_authorized": False, "reason": "UNKNOWN_OR_HOLD_IS_NOT_PASS"}
    if not isinstance(owner_approval, Mapping):
        return {"overall_status": "PASS", "release_authorized": False, "reason": "EXACT_OWNER_APPROVAL_REQUIRED"}
    required = {
        "mission_id": PROJECT_ID,
        "requested_action": expected_action,
        "target_resource": expected_target,
        "billing_requirement": "NO_BILLING_REQUIRED",
        "zero_cost_eligible": True,
        "spend_cap_inr": 0,
        "paid_fallback_allowed": False,
        "automatic_external_action_allowed": False,
        "approval_is_exact_scope_only": True,
        "cannot_override_zero_cost_or_prohibited_actions": True,
        "status": "APPROVED",
    }
    for key, value in required.items():
        if owner_approval.get(key) != value:
            return {"overall_status": "PASS", "release_authorized": False, "reason": f"APPROVAL_MISMATCH_{key.upper()}"}
    expires_at = owner_approval.get("expires_at")
    try:
        expiry = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
    except (AttributeError, TypeError, ValueError):
        return {"overall_status": "PASS", "release_authorized": False, "reason": "APPROVAL_EXPIRY_INVALID"}
    if expiry.tzinfo is None or now.tzinfo is None or expiry.astimezone(timezone.utc) <= now.astimezone(timezone.utc):
        return {"overall_status": "PASS", "release_authorized": False, "reason": "APPROVAL_EXPIRED_OR_TIMEZONE_INVALID"}
    if not owner_approval.get("approval_id"):
        return {"overall_status": "PASS", "release_authorized": False, "reason": "APPROVAL_ID_MISSING"}
    scopes = owner_approval.get("scopes")
    if not isinstance(scopes, list) or not scopes or any(not isinstance(scope, str) or not scope.strip() or "*" in scope for scope in scopes):
        return {"overall_status": "PASS", "release_authorized": False, "reason": "APPROVAL_SCOPE_INVALID"}
    if not isinstance(owner_approval.get("target_service"), str) or not owner_approval["target_service"].strip():
        return {"overall_status": "PASS", "release_authorized": False, "reason": "APPROVAL_SERVICE_MISSING"}
    return {
        "overall_status": "PASS",
        "release_authorized": True,
        "reason": "ALL_GATES_PASS_AND_EXACT_APPROVAL_VALID",
        "approval_id": owner_approval["approval_id"],
        "external_action_performed": False,
    }


def validate_git_sha(value: str | None, allow_none: bool = False) -> None:
    if allow_none and value is None:
        return
    if not isinstance(value, str) or not SHA1_RE.fullmatch(value):
        raise PolicyError("Git commit SHA must be 40 lowercase hex characters")
