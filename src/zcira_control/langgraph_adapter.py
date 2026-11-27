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
MAX_TASKS_PER_GRAPH = 100
MAX_PROVIDER_RECORDS = 20
MAX_ACTIVE_LEASES = 100
MAX_RUN_TASK_HISTORY = 1000


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
    started_at: str
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
    source_worker_execution_enabled: bool
    source_worker_proposals: list[dict[str, Any]]
    source_worker_status: str
    source_worker_errors: list[dict[str, Any]]
    source_worker_batch_proposal: dict[str, Any]
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
    validate_mission_context(state.get("mission_context", {}))
    if not isinstance(state.get("run_id"), str) or not RUN_ID_RE.fullmatch(state["run_id"]):
        raise PolicyError("LangGraph run_id is invalid")
    if state.get("executor") not in {"github_actions_ephemeral", "test_sandbox_non_runtime"}:
        raise PolicyError("LangGraph executor is not approved")
    now_dt = _parse_now(state.get("now"))
    started_at = state.get("started_at")
    if started_at is not None and _parse_now(started_at) > now_dt:
        raise PolicyError("LangGraph started_at cannot be later than now")
    validate_git_sha(state.get("base_commit_sha"), allow_none=True)
    for key in ("tasks", "provider_records", "active_leases", "completed_task_ids", "blocked_task_ids"):
        if not isinstance(state.get(key), list):
            raise PolicyError(f"LangGraph envelope field {key} must be an array")
    if len(state["tasks"]) > MAX_TASKS_PER_GRAPH:
        raise PolicyError("LangGraph task batch exceeds the 100-task bound")
    if len(state["provider_records"]) > MAX_PROVIDER_RECORDS:
        raise PolicyError("LangGraph provider registry exceeds the 20-record bound")
    if len(state["active_leases"]) > MAX_ACTIVE_LEASES:
        raise PolicyError("LangGraph active lease set exceeds the 100-record bound")
    if any(len(state[key]) > MAX_RUN_TASK_HISTORY for key in ("completed_task_ids", "blocked_task_ids")):
        raise PolicyError("LangGraph run history exceeds the 1000-ID bound")
    task_ids = []
    for task in state["tasks"]:
        if not isinstance(task, Mapping):
            raise PolicyError("LangGraph task entries must be objects")
        validate_task(task, state["mission_context"])
        task_id = task.get("task_id")
        if not isinstance(task_id, str) or not task_id:
            raise PolicyError("LangGraph task ID is invalid")
        task_ids.append(task_id)
        parameters = task.get("parameters", {})
        if not isinstance(parameters, Mapping):
            raise PolicyError("task parameters must be an object")
        if "requires_llm" in parameters and not isinstance(parameters["requires_llm"], bool):
            raise PolicyError("parameters.requires_llm must be boolean")
    if len(task_ids) != len(set(task_ids)):
        raise PolicyError("LangGraph task IDs must be unique")
    for key in ("provider_records", "active_leases"):
        if any(not isinstance(item, Mapping) for item in state[key]):
            raise PolicyError(f"LangGraph {key} entries must be objects")
    for key in ("completed_task_ids", "blocked_task_ids"):
        values = state[key]
        if any(not isinstance(item, str) or not item for item in values) or len(values) != len(set(values)):
            raise PolicyError(f"LangGraph {key} must contain unique non-empty IDs")
    for key in ("kill_switch", "cancel_requested"):
        if not isinstance(state.get(key), bool):
            raise PolicyError(f"LangGraph envelope field {key} must be boolean")
    if "source_worker_execution_enabled" in state and not isinstance(state["source_worker_execution_enabled"], bool):
        raise PolicyError("source_worker_execution_enabled must be boolean")


def _has_eligible_free_llm(records: list[dict[str, Any]]) -> bool:
    return any(
        record.get("provider_type") == "LLM" and provider_eligibility(record)[0]
        for record in records
    )


def _contains_forbidden_source_payload_key(value: Any) -> bool:
    forbidden = {
        "raw_content", "raw_body", "raw_body_bytes", "body_bytes", "page_bytes",
        "cookies", "authorization", "access_token", "refresh_token", "private_key",
        "secret", "password",
    }
    if isinstance(value, Mapping):
        for key, child in value.items():
            if str(key).casefold() in forbidden or _contains_forbidden_source_payload_key(child):
                return True
    elif isinstance(value, list):
        return any(_contains_forbidden_source_payload_key(child) for child in value)
    return False


def _validate_source_worker_proposal(proposal: Mapping[str, Any], task: Mapping[str, Any]) -> None:
    if not isinstance(proposal, Mapping):
        raise StateError("source worker proposal must be an object")
    if _contains_forbidden_source_payload_key(proposal):
        raise StateError("source worker proposal contains raw content or sensitive fields")
    expected = {
        "schema_version": "1.0.0",
        "project_id": PROJECT_ID,
        "task_id": task.get("task_id"),
        "idempotency_key": task.get("idempotency_key"),
        "assigned_role": task.get("assigned_role"),
        "raw_body_persisted": False,
        "write_performed": False,
        "requires_s7_publisher": True,
        "reviewer_verdict": "PENDING",
        "commercial_gate_status": "UNKNOWN",
    }
    for key, value in expected.items():
        if proposal.get(key) != value:
            raise StateError(f"source worker proposal invariant failed: {key}")
    if proposal.get("result_status") not in {"COMPLETED", "PARTIAL", "BLOCKED"}:
        raise StateError("source worker result status is invalid")
    if proposal.get("assigned_role") not in {"official_source_worker_a", "official_source_worker_b"}:
        raise StateError("source worker proposal role is invalid")
    envelope = proposal.get("source_snapshot_envelope")
    if not isinstance(envelope, Mapping):
        raise StateError("source worker proposal lacks a snapshot envelope")
    digest = proposal.get("source_snapshot_envelope_sha256")
    if not isinstance(digest, str) or not re.fullmatch(r"[a-f0-9]{64}", digest):
        raise StateError("source worker envelope digest is invalid")
    retention = envelope.get("retention")
    raw_digest = envelope.get("raw_body_sha256")
    raw_size = envelope.get("raw_body_size_bytes")
    if not isinstance(retention, Mapping):
        raise StateError("source worker snapshot retention metadata is missing")
    if (
        proposal.get("source_snapshot_content_ref") != f"sha256:{digest}"
        or proposal.get("source_snapshot_storage_path") != f"evidence/snapshots/sha256/{digest}.json"
        or envelope.get("snapshot_id") != proposal.get("snapshot_id")
        or envelope.get("trust_boundary") != "UNTRUSTED_DATA_ONLY"
        or envelope.get("access_mode") != "PUBLIC_READ_ONLY"
        or envelope.get("access_control_bypass") is not False
        or envelope.get("reviewer_verdict") != "PENDING"
        or envelope.get("commercial_gate_status") != "UNKNOWN"
        or retention.get("raw_body_persisted") is not False
        or retention.get("full_page_mirroring") is not False
        or not isinstance(raw_digest, str)
        or not re.fullmatch(r"[a-f0-9]{64}", raw_digest)
        or isinstance(raw_size, bool)
        or not isinstance(raw_size, int)
        or not 0 <= raw_size <= 1_000_000
    ):
        raise StateError("source worker snapshot envelope violates its metadata-only contract")
    evidence = proposal.get("evidence_proposal")
    if proposal.get("result_status") == "COMPLETED":
        if not isinstance(evidence, Mapping):
            raise StateError("completed source proposal must include evidence")
        if evidence.get("reviewer_verdict") != "PENDING" or evidence.get("gate_status") != "UNKNOWN" or evidence.get("model_provider") is not None:
            raise StateError("source evidence proposal changed the review or model boundary")
    elif evidence is not None:
        raise StateError("non-completed source proposal cannot include evidence")
    unsigned = dict(proposal)
    recorded_digest = unsigned.pop("proposal_sha256", None)
    if recorded_digest != sha256_text(canonical_json(unsigned)):
        raise StateError("source worker proposal digest mismatch")


def create_graph_nodes(
    mission_context: Mapping[str, Any],
    source_worker_executor: Callable[[Mapping[str, Any]], Mapping[str, Any]] | None = None,
) -> dict[str, Callable[[SwarmGraphState], dict[str, Any]]]:
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
        started_at = state.get("started_at") or now
        now_dt = _parse_now(now)
        if _parse_now(started_at) > now_dt:
            raise PolicyError("checkpoint started_at cannot be later than now")
        status = state.get("status", "PAUSED")
        pending_ids = state.get("pending_task_ids", [])
        is_terminal = status in {"COMPLETED", "FAILED"} or (status == "PARTIAL" and not pending_ids)
        finished_at = now if is_terminal else None
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
            "started_at": started_at,
            "last_heartbeat_at": now,
            "finished_at": finished_at,
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
        source_proposals = state.get("source_worker_proposals", [])
        if not isinstance(source_proposals, list) or len(source_proposals) > MAX_PARALLEL_RESEARCH_WORKERS:
            raise StateError("source worker proposal batch exceeds the two-worker bound")
        source_batch = {
            "kind": "source_worker_batch",
            "schema_version": "1.0.0",
            "project_id": PROJECT_ID,
            "run_id": state["run_id"],
            "base_commit_sha": base_sha,
            "proposals": source_proposals,
            "proposals_sha256": sha256_text(canonical_json(source_proposals)),
            "writer_role_required": SINGLE_WRITER_ROLE,
            "write_authorized": False,
            "write_performed": False,
        }
        return {
            "checkpoint_proposal": proposal,
            "source_worker_batch_proposal": source_batch,
            "write_performed": False,
        }

    nodes = {
        "admission": admission,
        "plan": plan,
        "checkpoint_proposal": checkpoint_proposal,
    }
    if source_worker_executor is not None:
        if not callable(source_worker_executor):
            raise PolicyError("source_worker_executor must be callable")

        def source_workers(state: SwarmGraphState) -> dict[str, Any]:
            if (
                state.get("status") in {"PAUSED", "FAILED", "COMPLETED"}
                or state.get("kill_switch") is True
                or state.get("cancel_requested") is True
            ):
                return {"source_worker_proposals": [], "source_worker_errors": [], "source_worker_status": "NOT_RUN"}
            if state.get("source_worker_execution_enabled", False) is not True:
                return {"source_worker_proposals": [], "source_worker_errors": [], "source_worker_status": "DISABLED_BY_DEFAULT"}
            candidates = [
                task for task in state.get("research_plan", [])
                if task.get("task_type") == "source_snapshot"
            ]
            if len(candidates) > MAX_PARALLEL_RESEARCH_WORKERS:
                raise StateError("source worker node received more than two selected tasks")
            if not candidates:
                return {"source_worker_proposals": [], "source_worker_errors": [], "source_worker_status": "NO_SOURCE_TASKS"}
            proposals: list[dict[str, Any]] = []
            errors: list[dict[str, str]] = []
            for task in candidates:
                try:
                    if task.get("assigned_role") not in {"official_source_worker_a", "official_source_worker_b"}:
                        raise StateError("source task role is not allowlisted")
                    candidate = source_worker_executor(task)
                    _validate_source_worker_proposal(candidate, task)
                    proposals.append(dict(candidate))
                except Exception as exc:
                    errors.append({"task_id": str(task.get("task_id", "")), "error_code": type(exc).__name__})
            if errors and proposals:
                status = "PARTIAL"
            elif errors:
                status = "FAILED"
            else:
                status = "PROPOSALS_READY_NOT_PUBLISHED"
            return {"source_worker_proposals": proposals, "source_worker_errors": errors, "source_worker_status": status}

        nodes["source_workers"] = source_workers
    return nodes


def _route_after_admission(state: SwarmGraphState) -> str:
    return "checkpoint" if state.get("status") == "PAUSED" else "plan"


def build_langgraph_graph(
    mission_context: Mapping[str, Any],
    graph_factory: Any | None = None,
    source_worker_executor: Callable[[Mapping[str, Any]], Mapping[str, Any]] | None = None,
    checkpointer: Any | None = None,
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

    nodes = create_graph_nodes(mission_context, source_worker_executor)
    if checkpointer is not None:
        bind_graph_nodes = getattr(checkpointer, "bind_graph_nodes", None)
        if callable(bind_graph_nodes):
            bind_graph_nodes(tuple(nodes.keys()))
    builder = StateGraph(SwarmGraphState)
    for name, node in nodes.items():
        builder.add_node(name, node)
    builder.add_edge(START, "admission")
    builder.add_conditional_edges(
        "admission",
        _route_after_admission,
        {"plan": "plan", "checkpoint": "checkpoint_proposal"},
    )
    if source_worker_executor is None:
        builder.add_edge("plan", "checkpoint_proposal")
    else:
        builder.add_edge("plan", "source_workers")
        builder.add_edge("source_workers", "checkpoint_proposal")
    builder.add_edge("checkpoint_proposal", END)
    return builder.compile(checkpointer=checkpointer) if checkpointer is not None else builder.compile()


def invoke_graph(
    graph: Any,
    initial_state: Mapping[str, Any],
    checkpoint_config: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Invoke a bounded planning graph, optionally with a run-bound durable checkpointer config."""
    if checkpoint_config is None:
        result = graph.invoke(dict(initial_state))
    else:
        configurable = checkpoint_config.get("configurable")
        if (
            not isinstance(configurable, Mapping)
            or configurable.get("thread_id") != initial_state.get("run_id")
            or configurable.get("checkpoint_ns", "") != ""
        ):
            raise StateError("checkpoint config must bind the exact run_id and empty checkpoint namespace")
        result = graph.invoke(dict(initial_state), dict(checkpoint_config))
    proposal = result.get("checkpoint_proposal")
    if not isinstance(proposal, Mapping):
        raise StateError("graph did not return a checkpoint proposal")
    payload = proposal.get("payload")
    if (
        proposal.get("kind") != "run_state"
        or proposal.get("writer_role_required") != SINGLE_WRITER_ROLE
        or proposal.get("write_authorized") is not False
        or proposal.get("write_performed") is not False
        or result.get("write_performed") is not False
        or not isinstance(payload, Mapping)
        or proposal.get("payload_sha256") != sha256_text(canonical_json(payload))
    ):
        raise StateError("graph checkpoint proposal violates the read-only publisher contract")
    source_batch = result.get("source_worker_batch_proposal")
    if not isinstance(source_batch, Mapping):
        raise StateError("graph did not return a source-worker batch proposal")
    source_proposals = source_batch.get("proposals")
    if (
        source_batch.get("kind") != "source_worker_batch"
        or source_batch.get("schema_version") != "1.0.0"
        or source_batch.get("project_id") != PROJECT_ID
        or source_batch.get("run_id") != result.get("run_id")
        or source_batch.get("writer_role_required") != SINGLE_WRITER_ROLE
        or source_batch.get("write_authorized") is not False
        or source_batch.get("write_performed") is not False
        or not isinstance(source_proposals, list)
        or len(source_proposals) > MAX_PARALLEL_RESEARCH_WORKERS
        or source_batch.get("proposals_sha256") != sha256_text(canonical_json(source_proposals))
    ):
        raise StateError("source-worker batch proposal violates the read-only publisher contract")
    tasks_by_id = {task.get("task_id"): task for task in initial_state.get("tasks", [])}
    if len({proposal.get("task_id") for proposal in source_proposals if isinstance(proposal, Mapping)}) != len(source_proposals):
        raise StateError("source-worker batch contains duplicate task proposals")
    for source_proposal in source_proposals:
        if not isinstance(source_proposal, Mapping):
            raise StateError("source-worker batch contains a non-object proposal")
        source_task = tasks_by_id.get(source_proposal.get("task_id"))
        if source_task is None:
            raise StateError("source-worker proposal references an unknown task")
        _validate_source_worker_proposal(source_proposal, source_task)
    handoff = result.get("publisher_handoff")
    if handoff is not None and (
        handoff.get("status") != "PROPOSED_NOT_EXECUTED"
        or handoff.get("write_performed") is not False
        or handoff.get("requires_s7_publisher") is not True
    ):
        raise StateError("publisher handoff violates the single-writer boundary")
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
    if len(pending_ids) > MAX_TASKS_PER_GRAPH or len(tasks) > MAX_TASKS_PER_GRAPH:
        raise PolicyError("resume task batch exceeds the 100-task bound")
    if len(provider_records) > MAX_PROVIDER_RECORDS or len(active_leases) > MAX_ACTIVE_LEASES:
        raise PolicyError("resume provider or lease registry exceeds its bound")
    if len(completed_ids) > MAX_RUN_TASK_HISTORY or len(blocked_ids) > MAX_RUN_TASK_HISTORY:
        raise PolicyError("resume task history exceeds the 1000-ID bound")
    if any(not isinstance(item, str) or not item for values in (pending_ids, completed_ids, blocked_ids) for item in values):
        raise PolicyError("resume task IDs must be non-empty strings")
    if len(pending_ids) != len(set(pending_ids)):
        raise PolicyError("resume pending task IDs contain duplicates")
    if set(pending_ids) & (set(completed_ids) | set(blocked_ids)):
        raise PolicyError("resume task cannot be pending and completed/blocked")
    if any(not isinstance(task, Mapping) for task in tasks):
        raise PolicyError("resume task definitions must be objects")
    by_id = {task.get("task_id"): dict(task) for task in tasks}
    if len(by_id) != len(tasks):
        raise PolicyError("resume task definitions contain duplicate IDs")
    for task in by_id.values():
        validate_task(task, mission_context)
        parameters = task.get("parameters", {})
        if not isinstance(parameters, Mapping):
            raise PolicyError("resume task parameters must be an object")
        if "requires_llm" in parameters and not isinstance(parameters["requires_llm"], bool):
            raise PolicyError("resume parameters.requires_llm must be boolean")
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
    started_at = run_state.get("started_at", now)
    if not isinstance(started_at, str) or _parse_now(started_at) > now_dt:
        raise PolicyError("resume started_at is missing, invalid or later than now")
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
        "started_at": started_at,
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
