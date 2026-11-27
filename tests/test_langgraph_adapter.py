import hashlib
import importlib.util
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from jsonschema import Draft202012Validator, FormatChecker
from zcira_control.langgraph_adapter import (
    LangGraphUnavailable,
    StateError,
    TaskLeaseBusy,
    build_langgraph_graph,
    create_graph_nodes,
    invoke_graph,
    prepare_resume_input,
)
from zcira_control.policy import (
    CANONICAL_BRANCH, CANONICAL_REPO, ENVIRONMENT_NAMESPACE, PROJECT_ID,
    STATE_NAMESPACE, PolicyError,
)

NOW = "2026-11-17T03:30:00Z"
SHA = "a" * 40

MISSION = {
    "project_id": PROJECT_ID, "mission_id": PROJECT_ID, "canonical_repo": CANONICAL_REPO,
    "branch": CANONICAL_BRANCH, "environment_namespace": ENVIRONMENT_NAMESPACE, "state_namespace": STATE_NAMESPACE,
    "max_parallel_research_workers": 2, "single_writer_role": "evidence_publisher", "spend_cap_inr": 0,
    "paid_fallback_allowed": False, "trial_credit_dependency_allowed": False, "shared_state_with_other_missions": False,
    "cross_mission_write_allowed": False, "active": True,
    "allowed_paths": ["PROJECT_CONTINUITY.md", "README.md", "docs/**", "config/**", "schemas/**", "tests/**", "scripts/**", "requirements-test.txt", "src/**", "state/**"],
    "denied_paths": [".github/workflows/**", "secrets/**", "private/**"],
    "allowed_action_classes": ["READ_PUBLIC", "PARSE_PUBLIC", "HASH_PUBLIC", "CREATE_INTERNAL_DRAFT", "WRITE_REPO_VALIDATED"],
    "denied_action_classes": ["PURCHASE", "PAID_FALLBACK", "BILLING_ENABLE", "ACCOUNT_CREATE", "KYC", "ACCEPT_TERMS", "CONTACT_EXTERNAL", "SUBMIT", "SECURITY_TEST", "PUBLISH_PRODUCT", "WALLET_SIGN", "TRANSFER_FUNDS"],
}

def make_task(task_id, priority="P1", requires_llm=False, publisher=False):
    task = {
        "project_id": PROJECT_ID, "mission_id": PROJECT_ID, "canonical_repo": CANONICAL_REPO, "branch": CANONICAL_BRANCH,
        "task_id": task_id, "idempotency_key": hashlib.sha256(task_id.encode()).hexdigest(),
        "priority": priority, "category_id": 1, "status": "QUEUED", "created_at": NOW, "updated_at": NOW,
        "attempt_count": 0, "max_attempts": 2, "allowed_actions": ["READ_PUBLIC"],
        "external_actions_allowed": False, "paid_provider_routes_enabled": False,
        "parameters": {"requires_llm": requires_llm},
    }
    if publisher:
        task["assigned_role"] = "evidence_publisher"
        task["allowed_actions"] = ["WRITE_REPO_VALIDATED"]
        task["parameters"] = {"target_path": "docs/s5-draft.md"}
    return task

def free_llm_provider(state="CLOSED"):
    return {
        "provider_type": "LLM", "provider_plan": "FREE", "verified_free": True,
        "billing_required": False, "payment_method_required": False, "trial_credit_dependency": False,
        "paid_fallback_allowed": False, "approved_for_use": state == "CLOSED",
        "circuit_breaker": {"state": state, "failure_count": 0, "opened_at": None, "next_retry_at": None, "reason": None},
    }

def make_state(tasks, **overrides):
    state = {
        "project_id": PROJECT_ID, "mission_id": PROJECT_ID, "canonical_repo": CANONICAL_REPO,
        "branch": CANONICAL_BRANCH, "environment_namespace": ENVIRONMENT_NAMESPACE, "state_namespace": STATE_NAMESPACE,
        "mission_context": MISSION, "run_id": "zcira-run-s5-test-001", "now": NOW, "tasks": tasks,
        "provider_records": [], "active_leases": [], "completed_task_ids": [], "blocked_task_ids": [],
        "base_commit_sha": SHA, "executor": "test_sandbox_non_runtime", "run_mode": "READ_ONLY_RESEARCH",
        "kill_switch": False, "cancel_requested": False,
    }
    state.update(overrides)
    return state

def make_run_state(pending_ids):
    return {
        "project_id": PROJECT_ID, "mission_id": PROJECT_ID, "canonical_repo": CANONICAL_REPO,
        "branch": CANONICAL_BRANCH, "environment_namespace": ENVIRONMENT_NAMESPACE, "state_namespace": STATE_NAMESPACE,
        "status": "RUNNING", "pending_task_ids": list(pending_ids), "completed_task_ids": [], "blocked_task_ids": [],
        "latest_commit_sha": SHA, "base_commit_sha": SHA, "run_id": "zcira-run-s5-test-001", "kill_switch": False,
    }

def make_task_lease(lease_id, task_id, expires_at):
    return {
        "schema_version": "1.0.0", "project_id": PROJECT_ID, "lease_id": lease_id, "mission_id": PROJECT_ID,
        "canonical_repo": CANONICAL_REPO, "branch": CANONICAL_BRANCH, "environment_namespace": ENVIRONMENT_NAMESPACE,
        "state_namespace": STATE_NAMESPACE, "resource_key": "task:" + task_id, "lease_kind": "TASK_EXECUTION",
        "task_id": task_id, "holder_id": "worker-a", "holder_role": "official_source_worker_a", "write_access": False,
        "cross_mission_share_allowed": False, "status": "ACTIVE", "acquired_at": "2026-11-17T03:00:00Z",
        "expires_at": expires_at, "released_at": None, "base_commit_sha": SHA,
        "idempotency_key": "b" * 64,
    }

class FakeCompiledGraph:
    def __init__(self, builder):
        self.builder = builder

    def invoke(self, initial_state):
        state = dict(initial_state)
        state.update(self.builder.nodes["admission"](state))
        route_fn, path_map = self.builder.conditional["admission"]
        route = route_fn(state)
        target = path_map[route]
        if target == "plan":
            state.update(self.builder.nodes["plan"](state))
        state.update(self.builder.nodes["checkpoint_proposal"](state))
        return state

class FakeStateGraph:
    def __init__(self, state_type):
        self.state_type = state_type
        self.nodes = {}
        self.edges = []
        self.conditional = {}
        self.compiled_with_checkpointer = False

    def add_node(self, name, node):
        self.nodes[name] = node

    def add_edge(self, start, end):
        self.edges.append((start, end))

    def add_conditional_edges(self, source, route_fn, path_map):
        self.conditional[source] = (route_fn, path_map)

    def compile(self, checkpointer=None):
        self.compiled_with_checkpointer = checkpointer is not None
        return FakeCompiledGraph(self)

FACTORY = SimpleNamespace(StateGraph=FakeStateGraph, START="START", END="END")

class LangGraphAdapterTests(unittest.TestCase):
    def setUp(self):
        self.graph = build_langgraph_graph(MISSION, FACTORY)

    def test_graph_has_only_deterministic_nodes_and_no_checkpointer(self):
        builder = self.graph.builder
        self.assertEqual(set(builder.nodes), {"admission", "plan", "checkpoint_proposal"})
        self.assertIn(("START", "admission"), builder.edges)
        self.assertIn(("plan", "checkpoint_proposal"), builder.edges)
        self.assertIn(("checkpoint_proposal", "END"), builder.edges)
        self.assertEqual(builder.conditional["admission"][1], {"plan": "plan", "checkpoint": "checkpoint_proposal"})

    def test_graph_binds_checkpointer_to_exact_compiled_nodes(self):
        class BindingRecorder:
            def bind_graph_nodes(self, node_names):
                self.node_names = tuple(node_names)

        recorder = BindingRecorder()
        graph = build_langgraph_graph(MISSION, FACTORY, checkpointer=recorder)
        self.assertEqual(recorder.node_names, ("admission", "plan", "checkpoint_proposal"))
        self.assertTrue(graph.builder.compiled_with_checkpointer)

    def test_research_plan_is_bounded_to_two(self):
        tasks = [make_task("zcira-task-a", "P1"), make_task("zcira-task-b", "P2"), make_task("zcira-task-c", "P3")]
        result = invoke_graph(self.graph, make_state(tasks))
        self.assertEqual(len(result["research_plan"]), 2)
        self.assertEqual(result["selected_task_ids"], ["zcira-task-a", "zcira-task-b"])
        self.assertEqual(result["status"], "QUEUED")

    def test_no_free_llm_blocks_only_llm_tasks(self):
        tasks = [make_task("zcira-deterministic", "P1"), make_task("zcira-needs-llm", "P1", requires_llm=True)]
        result = invoke_graph(self.graph, make_state(tasks))
        self.assertEqual(result["selected_task_ids"], ["zcira-deterministic"])
        self.assertEqual(result["blocked_task_ids"], ["zcira-needs-llm"])
        self.assertEqual(result["blocked_reasons"]["zcira-needs-llm"], "BLOCKED_NO_FREE_MODEL")
        self.assertEqual(result["status"], "PARTIAL")

    def test_completed_llm_task_is_not_reclassified_as_blocked(self):
        task = make_task("zcira-completed-llm", "P1", requires_llm=True)
        task["status"] = "COMPLETED"
        result = invoke_graph(self.graph, make_state([task]))
        self.assertEqual(result["blocked_task_ids"], [])
        self.assertEqual(result["pending_task_ids"], [])
        self.assertEqual(result["status"], "COMPLETED")

    def test_eligible_free_llm_allows_llm_task(self):
        tasks = [make_task("zcira-needs-llm", "P1", requires_llm=True)]
        result = invoke_graph(self.graph, make_state(tasks, provider_records=[free_llm_provider()]))
        self.assertEqual(result["selected_task_ids"], ["zcira-needs-llm"])
        self.assertEqual(result["blocked_task_ids"], [])

    def test_open_circuit_breaker_does_not_count_as_eligible_provider(self):
        tasks = [make_task("zcira-needs-llm", "P1", requires_llm=True)]
        result = invoke_graph(self.graph, make_state(tasks, provider_records=[free_llm_provider("OPEN")]))
        self.assertEqual(result["blocked_reasons"]["zcira-needs-llm"], "BLOCKED_NO_FREE_MODEL")

    def test_kill_switch_pauses_and_preserves_pending_tasks(self):
        tasks = [make_task("zcira-task-a")]
        result = invoke_graph(self.graph, make_state(tasks, kill_switch=True))
        self.assertEqual(result["status"], "PAUSED")
        self.assertEqual(result["pause_reason"], "KILL_SWITCH_ACTIVE")
        self.assertEqual(result["pending_task_ids"], ["zcira-task-a"])
        self.assertEqual(result["research_plan"], [])

    def test_cancel_request_pauses_without_planning(self):
        tasks = [make_task("zcira-task-a")]
        result = invoke_graph(self.graph, make_state(tasks, cancel_requested=True))
        self.assertEqual(result["status"], "PAUSED")
        self.assertEqual(result["pause_reason"], "CANCEL_REQUESTED")
        self.assertEqual(result["research_plan"], [])

    def test_publisher_is_handed_off_but_never_executed(self):
        publisher = make_task("zcira-publisher-task", publisher=True)
        result = invoke_graph(self.graph, make_state([publisher]))
        self.assertIsNotNone(result["publisher_candidate"])
        self.assertEqual(result["publisher_handoff"]["status"], "PROPOSED_NOT_EXECUTED")
        self.assertFalse(result["publisher_handoff"]["write_performed"])
        self.assertFalse(result["checkpoint_proposal"]["write_performed"])
        self.assertFalse(result["write_performed"])
        self.assertEqual(result["research_plan"], [])

    def test_checkpoint_proposal_matches_run_state_contract(self):
        result = invoke_graph(self.graph, make_state([make_task("zcira-task-a")]))
        proposal = result["checkpoint_proposal"]
        self.assertEqual(proposal["kind"], "run_state")
        self.assertFalse(proposal["write_authorized"])
        schema_path = ROOT / "schemas" / "v1" / "run_state.schema.json"
        schema = __import__("json").loads(schema_path.read_text(encoding="utf-8"))
        Draft202012Validator(schema, format_checker=FormatChecker()).validate(proposal["payload"])
        self.assertEqual(proposal["payload_sha256"], hashlib.sha256(
            __import__("json").dumps(proposal["payload"], ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest())

    def test_resume_uses_only_publisher_committed_pending_ids(self):
        tasks = [make_task("zcira-task-a"), make_task("zcira-task-b"), make_task("zcira-task-c")]
        result = invoke_graph(self.graph, make_state(tasks, completed_task_ids=["zcira-task-old"]))
        run_state = result["checkpoint_proposal"]["payload"]
        run_state["pending_task_ids"] = ["zcira-task-b", "zcira-task-c"]
        resumed = prepare_resume_input(run_state, tasks, MISSION, [], [], NOW)
        self.assertEqual([t["task_id"] for t in resumed["tasks"]], ["zcira-task-b", "zcira-task-c"])
        self.assertEqual(resumed["completed_task_ids"], ["zcira-task-old"])
        self.assertEqual(resumed["base_commit_sha"], SHA)

    def test_active_task_lease_blocks_duplicate_resume(self):
        task = make_task("zcira-task-a")
        task["status"] = "RUNNING"
        task["assigned_role"] = "official_source_worker_a"
        task["lease_id"] = "lease-task-a"
        lease = make_task_lease("lease-task-a", "zcira-task-a", "2026-11-17T04:00:00Z")
        run_state = make_run_state(["zcira-task-a"])
        with self.assertRaises(TaskLeaseBusy):
            prepare_resume_input(run_state, [task], MISSION, [], [lease], NOW)

    def test_expired_task_lease_requeues_with_attempt_increment(self):
        task = make_task("zcira-task-a")
        task["status"] = "RUNNING"
        task["assigned_role"] = "official_source_worker_a"
        task["lease_id"] = "lease-task-a"
        lease = make_task_lease("lease-task-a", "zcira-task-a", "2026-11-17T03:20:00Z")
        run_state = make_run_state(["zcira-task-a"])
        resumed = prepare_resume_input(run_state, [task], MISSION, [], [lease], NOW)
        self.assertEqual(resumed["tasks"][0]["status"], "QUEUED")
        self.assertEqual(resumed["tasks"][0]["attempt_count"], 1)
        self.assertIsNone(resumed["tasks"][0]["lease_id"])

    def test_expired_task_at_max_attempts_moves_to_dead_letter(self):
        task = make_task("zcira-task-a")
        task["status"] = "RUNNING"
        task["assigned_role"] = "official_source_worker_a"
        task["lease_id"] = "lease-task-a"
        task["attempt_count"] = 2
        lease = make_task_lease("lease-task-a", "zcira-task-a", "2026-11-17T03:20:00Z")
        run_state = make_run_state(["zcira-task-a"])
        resumed = prepare_resume_input(run_state, [task], MISSION, [], [lease], NOW)
        self.assertEqual(resumed["tasks"], [])
        self.assertIn("zcira-task-a", resumed["blocked_task_ids"])

    def test_task_lease_cannot_cross_task_or_gain_write_access(self):
        task = make_task("zcira-task-a")
        task["status"] = "RUNNING"
        task["assigned_role"] = "official_source_worker_a"
        task["lease_id"] = "lease-task-a"
        lease = make_task_lease("lease-task-a", "zcira-other-task", "2026-11-17T03:20:00Z")
        with self.assertRaises(PolicyError):
            prepare_resume_input(make_run_state(["zcira-task-a"]), [task], MISSION, [], [lease], NOW)
        lease = make_task_lease("lease-task-a", "zcira-task-a", "2026-11-17T03:20:00Z")
        lease["write_access"] = True
        with self.assertRaises(PolicyError):
            prepare_resume_input(make_run_state(["zcira-task-a"]), [task], MISSION, [], [lease], NOW)

    def test_resume_rejects_missing_pending_task(self):
        run_state = {
            "project_id": PROJECT_ID, "mission_id": PROJECT_ID, "canonical_repo": CANONICAL_REPO,
            "branch": CANONICAL_BRANCH, "environment_namespace": ENVIRONMENT_NAMESPACE, "state_namespace": STATE_NAMESPACE,
            "status": "QUEUED", "pending_task_ids": ["zcira-missing"], "completed_task_ids": [], "blocked_task_ids": [],
            "latest_commit_sha": SHA, "base_commit_sha": SHA, "run_id": "zcira-run-s5-test-001", "kill_switch": False,
        }
        with self.assertRaises(PolicyError):
            prepare_resume_input(run_state, [], MISSION, [], [], NOW)

    def test_resume_preserves_kill_switch(self):
        run_state = {
            "project_id": PROJECT_ID, "mission_id": PROJECT_ID, "canonical_repo": CANONICAL_REPO,
            "branch": CANONICAL_BRANCH, "environment_namespace": ENVIRONMENT_NAMESPACE, "state_namespace": STATE_NAMESPACE,
            "status": "PAUSED", "pending_task_ids": [], "completed_task_ids": [], "blocked_task_ids": [],
            "latest_commit_sha": SHA, "base_commit_sha": SHA, "run_id": "zcira-run-s5-test-001", "kill_switch": True,
        }
        resumed = prepare_resume_input(run_state, [], MISSION, [], [], NOW)
        self.assertTrue(resumed["kill_switch"])

    def test_cross_mission_run_envelope_fails_closed(self):
        state = make_state([make_task("zcira-task-a")], mission_id="OTHER-MISSION")
        with self.assertRaises(PolicyError):
            invoke_graph(self.graph, state)

    def test_task_batch_limit_is_enforced(self):
        tasks = [make_task(f"zcira-task-{i:03d}") for i in range(101)]
        with self.assertRaises(PolicyError):
            invoke_graph(self.graph, make_state(tasks))

    def test_duplicate_task_ids_are_rejected(self):
        task = make_task("zcira-duplicate-task")
        with self.assertRaises(PolicyError):
            invoke_graph(self.graph, make_state([task, dict(task)]))

    def test_requires_llm_flag_must_be_boolean(self):
        task = make_task("zcira-bad-llm-flag")
        task["parameters"]["requires_llm"] = "true"
        with self.assertRaises(PolicyError):
            invoke_graph(self.graph, make_state([task]))

    def test_invoke_rejects_tampered_checkpoint_digest(self):
        base_graph = self.graph
        class TamperedGraph:
            def invoke(self, state):
                result = base_graph.invoke(state)
                result["checkpoint_proposal"]["payload_sha256"] = "0" * 64
                return result
        with self.assertRaises(StateError):
            invoke_graph(TamperedGraph(), make_state([make_task("zcira-task-a")]))

    def test_invoke_rejects_write_authorized_checkpoint(self):
        base_graph = self.graph
        class WriteGraph:
            def invoke(self, state):
                result = base_graph.invoke(state)
                result["checkpoint_proposal"]["write_authorized"] = True
                return result
        with self.assertRaises(StateError):
            invoke_graph(WriteGraph(), make_state([make_task("zcira-task-a")]))

    def test_missing_langgraph_dependency_is_reported_without_fallback(self):
        if importlib.util.find_spec("langgraph") is not None:
            self.skipTest("LangGraph package is installed in this environment")
        with self.assertRaises(LangGraphUnavailable):
            build_langgraph_graph(MISSION)


    def test_queued_run_keeps_finished_at_null_and_preserves_started_at(self):
        task = make_task("zcira-open-run")
        state = make_state([task], now="2026-11-17T03:30:00Z", started_at="2026-11-17T03:00:00Z")
        result = invoke_graph(self.graph, state)
        payload = result["checkpoint_proposal"]["payload"]
        self.assertEqual(payload["status"], "QUEUED")
        self.assertEqual(payload["started_at"], "2026-11-17T03:00:00Z")
        self.assertIsNone(payload["finished_at"])

    def test_completed_run_sets_finished_at(self):
        task = make_task("zcira-completed-run")
        task["status"] = "COMPLETED"
        result = invoke_graph(self.graph, make_state([task]))
        payload = result["checkpoint_proposal"]["payload"]
        self.assertEqual(payload["status"], "COMPLETED")
        self.assertEqual(payload["finished_at"], NOW)

    def test_resume_preserves_original_run_started_at(self):
        task = make_task("zcira-resume-start-time")
        run_state = make_run_state([task["task_id"]])
        run_state["started_at"] = "2026-11-17T03:00:00Z"
        resumed = prepare_resume_input(
            run_state, [task], MISSION, [], [], "2026-11-17T03:30:00Z",
            executor="test_sandbox_non_runtime",
        )
        self.assertEqual(resumed["started_at"], "2026-11-17T03:00:00Z")
        result = invoke_graph(self.graph, resumed)
        payload = result["checkpoint_proposal"]["payload"]
        self.assertEqual(payload["started_at"], "2026-11-17T03:00:00Z")
        self.assertIsNone(payload["finished_at"])

if __name__ == "__main__":
    unittest.main()
