from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Any, Callable, Mapping, TypedDict

from .leases import lease_is_active, validate_lease
from .policy import (
    CANONICAL_BRANCH,
    CANONICAL_REPO,
    ENVIRONMENT_NAMESPACE,
    MAX_PARALLEL_RESEARCH_WORKERS,
    PROJECT_ID,
    SINGLE_WRITER_ROLE,
    STATE_NAMESPACE,
    PolicyError,
    validate_git_sha,
    validate_mission_context,
    validate_task,
)
from .queue import plan_batch, plan_publisher_task
from .quota import provider_eligibility


RUN_ID_RE = re.compile(r"^zcira-run-[a-z0-9][a-z0-9-]{2,80}$")
RUN_STATUSES = {"QUEUED", "RUNNING", "COMPLETED", "PARTIAL", "PAUSED", "FAILED"}


class LangGraphUnavailable(RuntimeError):
    """Raised when the optional LangGraph runtime is not installed."""


class TaskLeaseBusy(RuntimeError):
    """A prior task execution lease is still active; do not duplicate the task."""


class StateError(RuntimeError):
    """A graph result violates the read-only adapter contract."""


class SwarmGraphState(TypedDict, total=False):
    project_id: str
    mission_id: str
    canonical_repo: str
    branch: str
    environment_namespace: str
    state_namespace: str
    mission_context: dict[str, Any]
    run_id: str
    now: str
    tasks: list[dict[str, Any]]
    provider_records: list[dict[str, Any]]
    active_leases: list[dict[str, Any]]
    completed_task_ids: list[str]
    blocked_task_ids: list[str]
    base_commit_sha: str | None
    executor: str
    run_mode: str
    kill_switch: bool
    cancel_requested: bool
    status: str
    pause_reason: str | None
    research_plan: list[dict[str, Any]]
    selected_task_ids: list[str]
    pending_task_ids: list[str]
    blocked_reasons: dict[str, str]
    publisher_candidate: dict[str, Any] | None
    publisher_handoff: dict[str, Any] | None
    checkpoint_proposal: dict[str, Any]
    write_performed: bool


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _parse_now(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, TypeError, ValueError):
        raise PolicyError("graph now must be an ISO-8601 timestamp") from None
    if parsed.tzinfo is None:
        raise PolicyError("graph now must include a timezone")
    return parsed.astimezone(timezone.utc)


def validate_run_envelope(state: Mapping[str, Any]) -> None:
    expected = {
        "project_id": PROJECT_ID,
        "mission_id": PROJECT_ID,
        "canonical_repo": CANONICAL_REPO,
        "branch": CANONICAL_BRANCH,
        "environment_namespace": ENVIRONMENT_NAMESPACE,
        "state_namespace": STATE_NAMESPACE,
        "run_mode": "READ_ONLY_RESEARCH",
    }
    for key, value in expected.items():
        if state.get(key) != value:
            raise PolicyError(f"LangGraph envelope scope mismatch: {key}")
    if not isinstance(state.get("run_id"), str) or not RUN_ID_RE.fullmatch(state["run_id"]):
        raise PolicyError("LangGraph run_id is invalid")
    if state.get("executor") not in {"github_actions_ephemeral", "test_sandbox_non_runtime"}:
        raise PolicyError("LangGraph executor is not approved")
    _parse_now(state.get("now"))
    validate_git_sha(state.get("base_commit_sha"), allow_none=True)
    for key in ("tasks", "provider_records", "active_leases", "completed_task_ids", "blocked_task_ids"):
        if not isinstance(state.get(key), list):
            raise PolicyError(f"LangGraph envelope field {key} must be an array")
    for key in ("kill_switch", "cancel_requested"):
        if not isinstance(state.get(key), bool):
            raise PolicyError(f"LangGraph envelope field {key} must be boolean")
    validate_mission_context(state.get("mission_context", {}))


def _has_eligible_free_llm(records: list[dict[str, Any]]) -> bool:
    return any(
        record.get("provider_type") == "LLM" and provider_eligibility(record)[0]
        for record in records
    )


def create_graph_nodes(mission_context: Mapping[str, Any]) -> dict[str, Callable[[SwarmGraphState], dict[str, Any]]]:
    """Create deterministic nodes. No model, network, filesystem or repository write is called."""
    validate_mission_context(mission_context)

    def admission(state: SwarmGraphState) -> dict[str, Any]:
        validate_run_envelope(state)
        completed = set(state.get("completed_task_ids", []))
        blocked = set(state.get("blocked_task_ids", []))
        pending = [
            task["task_id"] for task in state["tasks"]
            if task.get("status") == "QUEUED"
            and task.get("task_id") not in completed
            and task.get("task_id") not in blocked
        ]
        if state["kill_switch"]:
            return {"status": "PAUSED", "pause_reason": "KILL_SWITCH_ACTIVE", "research_plan": [], "selected_task_ids": [], "pending_task_ids": pending}
        if state["cancel_requested"]:
            return {"status": "PAUSED", "pause_reason": "CANCEL_REQUESTED", "research_plan": [], "selected_task_ids": [], "pending_task_ids": pending}
        return {"status": "RUNNING", "pause_reason": None}

    def plan(state: SwarmGraphState) -> dict[str, Any]:
        if state.get("status") != "RUNNING":
            return {}
        now = _parse_now(state["now"])
        tasks = [dict(task) for task in state["tasks"]]
        blocked = list(dict.fromkeys(state.get("blocked_task_ids", [])))
        blocked_reasons = dict(state.get("blocked_reasons", {}))
        llm_available = _has_eligible_free_llm(state["provider_records"])

        research_candidates: list[dict[str, Any]] = []
        for task in tasks:
            requires_llm = task.get("parameters", {}).get("requires_llm") is True
            if task.get("status") == "QUEUED" and requires_llm and not llm_available:
                task_id = task.get("task_id")
                if task_id:
                    blocked.append(task_id)
                    blocked_reasons[task_id] = "BLOCKED_NO_FREE_MODEL"
            else:
                research_candidates.append(task)

        blocked = list(dict.fromkeys(blocked))
        research_plan = plan_batch(research_candidates, mission_context)
        selected_ids = [task["task_id"] for task in research_plan]
        completed = set(state.get("completed_task_ids", []))
        blocked_set = set(blocked)
        pending = [
            task["task_id"] for task in tasks
            if task.get("status") == "QUEUED"
            and task.get("task_id") not in completed
            and task.get("task_id") not in blocked_set
        ]
        publisher_tasks = [
            task for task in tasks
            if task.get("task_id") not in blocked_set
        ]
        publisher_candidate = plan_publisher_task(
            publisher_tasks, mission_context, state["active_leases"], now
        )
        if blocked:
            status = "PARTIAL"
        elif pending:
            status = "QUEUED"
        else:
            status = "COMPLETED"
        handoff = None
        if publisher_candidate is not None:
            handoff = {
                "status": "PROPOSED_NOT_EXECUTED",
                "task_id": publisher_candidate["task_id"],
                "assigned_role": SINGLE_WRITER_ROLE,
                "requires_s7_publisher": True,
                "write_performed": False,
            }
        return {
            "status": status,
            "research_plan": research_plan,
            "selected_task_ids": selected_ids,
            "pending_task_ids": pending,
            "blocked_task_ids": blocked,
            "blocked_reasons": blocked_reasons,
            "publisher_candidate": publisher_candidate,
            "publisher_handoff": handoff,
        }

    def checkpoint_proposal(state: SwarmGraphState) -> dict[str, Any]:
        now = state["now"]
        base_sha = state.get("base_commit_sha")
        run_state = {
            "schema_version": "1.0.0",
            "project_id": PROJECT_ID,
            "run_id": state["run_id"],
            "mission_id": PROJECT_ID,
            "canonical_repo": CANONICAL_REPO,
            "branch": CANONICAL_BRANCH,
            "environment_namespace": ENVIRONMENT_NAMESPACE,
            "state_namespace": STATE_NAMESPACE,
            "status": state.get("status", "PAUSED"),
            "executor": state["executor"],
            "run_mode": "READ_ONLY_RESEARCH",
            "started_at": now,
            "last_heartbeat_at": now,
            "finished_at": now,
            "current_task_id": None,
            "pending_task_ids": state.get("pending_task_ids", []),
            "completed_task_ids": state.get("completed_task_ids", []),
            "blocked_task_ids": state.get("blocked_task_ids", []),
            "base_commit_sha": base_sha,
            "latest_commit_sha": base_sha,
            "max_parallel_research_workers": MAX_PARALLEL_RESEARCH_WORKERS,
            "single_writer_role": SINGLE_WRITER_ROLE,
            "paid_provider_routes_enabled": False,
            "spend_cap_inr": 0,
            "kill_switch": bool(state["kill_switch"]),
        }
        payload_sha = sha256_text(canonical_json(run_state))
        proposal = {
            "kind": "run_state",
            "object_id": state["run_id"],
            "payload": run_state,
            "payload_sha256": payload_sha,
            "writer_role_required": SINGLE_WRITER_ROLE,
            "write_authorized": False,
            "write_performed": False,
        }
        return {
            "checkpoint_proposal": proposal,
            "write_performed": False,
        }

    return {
        "admission": admission,
        "plan": plan,
        "checkpoint_proposal": checkpoint_proposal,
    }


def _route_after_admission(state: SwarmGraphState) -> str:
    return "checkpoint" if state.get("status") == "PAUSED" else "plan"


def build_langgraph_graph(
    mission_context: Mapping[str, Any],
    graph_factory: Any | None = None,
) -> Any:
    """Build the optional LangGraph graph. The graph has no built-in in-memory checkpointer."""
    if graph_factory is None:
        try:
            from langgraph.graph import END, START, StateGraph
        except ImportError as exc:
            raise LangGraphUnavailable(
                "Install the pinned optional dependency from config/requirements-langgraph.txt"
            ) from exc
    else:
        END = graph_factory.END
        START = graph_factory.START
        StateGraph = graph_factory.StateGraph

    nodes = create_graph_nodes(mission_context)
    builder = StateGraph(SwarmGraphState)
    for name, node in nodes.items():
        builder.add_node(name, node)
    builder.add_edge(START, "admission")
    builder.add_conditional_edges(
        "admission",
        _route_after_admission,
        {"plan": "plan", "checkpoint": "checkpoint_proposal"},
    )
    builder.add_edge("plan", "checkpoint_proposal")
    builder.add_edge("checkpoint_proposal", END)
    return builder.compile()


def invoke_graph(graph: Any, initial_state: Mapping[str, Any]) -> dict[str, Any]:
    """Invoke a bounded planning graph; durable checkpoint persistence is a separate publisher handoff."""
    result = graph.invoke(dict(initial_state))
    proposal = result.get("checkpoint_proposal")
    if not isinstance(proposal, Mapping) or proposal.get("write_performed") is not False:
        raise StateError("graph did not return a read-only checkpoint proposal")
    return result


def prepare_resume_input(
    run_state: Mapping[str, Any],
    tasks: list[dict[str, Any]],
    mission_context: Mapping[str, Any],
    provider_records: list[dict[str, Any]],
    active_leases: list[dict[str, Any]],
    now: str,
    executor: str = "test_sandbox_non_runtime",
    cancel_requested: bool = False,
) -> dict[str, Any]:
    """Rebuild a bounded invocation from a publisher-committed run_state.

    Expired task leases are re-queued with a bounded attempt increment. Active
    leases block duplicate execution. Missing or cross-mission lease evidence
    fails closed.
    """
    validate_mission_context(mission_context)
    if run_state.get("project_id") != PROJECT_ID or run_state.get("mission_id") != PROJECT_ID:
        raise PolicyError("resume state belongs to another mission")
    if run_state.get("canonical_repo") != CANONICAL_REPO or run_state.get("branch") != CANONICAL_BRANCH:
        raise PolicyError("resume state targets another repository or branch")
    if run_state.get("environment_namespace") != ENVIRONMENT_NAMESPACE or run_state.get("state_namespace") != STATE_NAMESPACE:
        raise PolicyError("resume state namespace mismatch")
    if run_state.get("status") not in RUN_STATUSES:
        raise PolicyError("resume state status is invalid")
    pending_ids = run_state.get("pending_task_ids")
    completed_ids = run_state.get("completed_task_ids")
    blocked_ids = run_state.get("blocked_task_ids")
    if not all(isinstance(value, list) for value in (pending_ids, completed_ids, blocked_ids)):
        raise PolicyError("resume task ID lists are invalid")
    if any(not isinstance(item, str) or not item for values in (pending_ids, completed_ids, blocked_ids) for item in values):
        raise PolicyError("resume task IDs must be non-empty strings")
    if len(pending_ids) != len(set(pending_ids)):
        raise PolicyError("resume pending task IDs contain duplicates")
    if set(pending_ids) & (set(completed_ids) | set(blocked_ids)):
        raise PolicyError("resume task cannot be pending and completed/blocked")
    by_id = {task.get("task_id"): dict(task) for task in tasks}
    if len(by_id) != len(tasks):
        raise PolicyError("resume task definitions contain duplicate IDs")
    missing = set(pending_ids) - set(by_id)
    if missing:
        raise PolicyError("resume checkpoint references missing task definitions")

    lease_by_id: dict[str, dict[str, Any]] = {}
    for lease in active_leases:
        if not isinstance(lease, Mapping) or not isinstance(lease.get("lease_id"), str):
            raise PolicyError("resume lease record is malformed")
        if lease["lease_id"] in lease_by_id:
            raise PolicyError("resume lease IDs are duplicated")
        lease_by_id[lease["lease_id"]] = dict(lease)

    now_dt = _parse_now(now)
    resumed_tasks: list[dict[str, Any]] = []
    next_blocked = list(blocked_ids)
    for task_id in pending_ids:
        task = by_id[task_id]
        status = task.get("status")
        if status == "QUEUED":
            if task.get("lease_id") is not None:
                raise PolicyError("queued task cannot retain a previous lease ID")
            validate_task(task, mission_context)
            resumed_tasks.append(task)
            continue
        if status not in {"LEASED", "RUNNING"}:
            raise PolicyError("pending checkpoint references a non-resumable task status")
        lease_id = task.get("lease_id")
        lease = lease_by_id.get(lease_id)
        if lease is None:
            raise PolicyError("leased task has no matching lease evidence")
        lease_for_validation = dict(lease)
        lease_active = lease_is_active(lease, now_dt)
        if lease.get("status") == "ACTIVE" and not lease_active:
            lease_for_validation["status"] = "EXPIRED"
        validate_lease(lease_for_validation, now_dt)
        if (
            lease.get("lease_kind") != "TASK_EXECUTION"
            or lease.get("task_id") != task_id
            or lease.get("resource_key") != f"task:{task_id}"
            or lease.get("write_access") is not False
            or task.get("assigned_role") is None
            or lease.get("holder_role") != task.get("assigned_role")
        ):
            raise PolicyError("task lease scope, holder role or read-only permission mismatch")
        if lease_active:
            raise TaskLeaseBusy("task execution lease is still active; retry after expiry")
        attempts = task.get("attempt_count", 0)
        max_attempts = task.get("max_attempts", 2)
        if attempts >= max_attempts:
            task["status"] = "DEAD_LETTER"
            next_blocked.append(task_id)
            continue
        task["status"] = "QUEUED"
        task["lease_id"] = None
        task["attempt_count"] = attempts + 1
        validate_task(task, mission_context)
        resumed_tasks.append(task)

    base_sha = run_state.get("latest_commit_sha") or run_state.get("base_commit_sha")
    validate_git_sha(base_sha, allow_none=True)
    return {
        "project_id": PROJECT_ID,
        "mission_id": PROJECT_ID,
        "canonical_repo": CANONICAL_REPO,
        "branch": CANONICAL_BRANCH,
        "environment_namespace": ENVIRONMENT_NAMESPACE,
        "state_namespace": STATE_NAMESPACE,
        "mission_context": dict(mission_context),
        "run_id": run_state.get("run_id"),
        "now": now,
        "tasks": resumed_tasks,
        "provider_records": provider_records,
        "active_leases": active_leases,
        "completed_task_ids": list(completed_ids),
        "blocked_task_ids": list(dict.fromkeys(next_blocked)),
        "base_commit_sha": base_sha,
        "executor": executor,
        "run_mode": "READ_ONLY_RESEARCH",
        "kill_switch": bool(run_state.get("kill_switch", False)),
        "cancel_requested": cancel_requested,
    }
