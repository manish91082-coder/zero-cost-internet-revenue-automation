"""Real LangGraph integration gate.

These tests are skipped when the optional pinned package is absent. S7 CI must
install the hash-locked dependency and execute this module on a GitHub-hosted
ephemeral runner. This module never performs network, model, repository or
account actions.
"""
import importlib.metadata
import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

from zcira_control.langgraph_adapter import build_langgraph_graph, invoke_graph, prepare_resume_input
from test_langgraph_adapter import MISSION, make_state, make_task
from zcira_control.policy import CANONICAL_STATE_BRANCH

LANGGRAPH_AVAILABLE = importlib.util.find_spec("langgraph") is not None


@unittest.skipUnless(
    LANGGRAPH_AVAILABLE,
    "requires the exact optional dependency langgraph==1.2.22; run in S7 ephemeral CI",
)
class RealLangGraphRuntimeIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        actual = importlib.metadata.version("langgraph")
        if actual != "1.2.22":
            raise AssertionError(f"expected langgraph==1.2.22, found {actual}")
        cls.graph = build_langgraph_graph(MISSION)

    def test_real_stategraph_compiles_and_invokes_bounded_plan(self):
        tasks = [
            make_task("zcira-real-a", "P1"),
            make_task("zcira-real-b", "P2"),
            make_task("zcira-real-c", "P3"),
        ]
        result = invoke_graph(
            self.graph,
            make_state(tasks, executor="github_actions_ephemeral"),
        )
        self.assertEqual(result["selected_task_ids"], ["zcira-real-a", "zcira-real-b"])
        self.assertEqual(len(result["research_plan"]), 2)
        self.assertFalse(result["write_performed"])
        self.assertFalse(result["checkpoint_proposal"]["write_authorized"])
        self.assertFalse(result["checkpoint_proposal"]["write_performed"])

    def test_real_stategraph_pause_branch_respects_kill_switch(self):
        result = invoke_graph(
            self.graph,
            make_state(
                [make_task("zcira-real-paused")],
                executor="github_actions_ephemeral",
                kill_switch=True,
            ),
        )
        self.assertEqual(result["status"], "PAUSED")
        self.assertEqual(result["pause_reason"], "KILL_SWITCH_ACTIVE")
        self.assertEqual(result["research_plan"], [])
        self.assertIsNone(result["checkpoint_proposal"]["payload"]["finished_at"])

    def test_real_stategraph_resume_preserves_progress_and_run_clock(self):
        first_task = make_task("zcira-real-completed", "P1")
        second_task = make_task("zcira-real-pending", "P2")
        first_task["status"] = "COMPLETED"
        original_started_at = "2026-11-17T03:00:00Z"
        run_state = {
            "project_id": MISSION["project_id"],
            "mission_id": MISSION["mission_id"],
            "canonical_repo": MISSION["canonical_repo"],
            "branch": CANONICAL_STATE_BRANCH,
            "environment_namespace": "zcira-readonly-research",
            "state_namespace": "zcira-2026-11-13/main",
            "status": "QUEUED",
            "started_at": original_started_at,
            "pending_task_ids": [second_task["task_id"]],
            "completed_task_ids": [first_task["task_id"]],
            "blocked_task_ids": [],
            "latest_commit_sha": "a" * 40,
            "base_commit_sha": "a" * 40,
            "run_id": "zcira-run-real-resume-001",
            "kill_switch": False,
        }
        resumed = prepare_resume_input(
            run_state,
            [first_task, second_task],
            MISSION,
            [],
            [],
            "2026-11-17T03:30:00Z",
            executor="github_actions_ephemeral",
        )
        self.assertEqual(resumed["started_at"], original_started_at)
        self.assertEqual(resumed["completed_task_ids"], [first_task["task_id"]])
        self.assertEqual([task["task_id"] for task in resumed["tasks"]], [second_task["task_id"]])
        result = invoke_graph(self.graph, resumed)
        payload = result["checkpoint_proposal"]["payload"]
        self.assertEqual(payload["started_at"], original_started_at)
        self.assertIsNone(payload["finished_at"])
        self.assertEqual(result["selected_task_ids"], [second_task["task_id"]])


if __name__ == "__main__":
    unittest.main()
