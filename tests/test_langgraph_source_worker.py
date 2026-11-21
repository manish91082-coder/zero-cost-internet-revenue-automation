"""S6-D LangGraph source-worker node tests.

All transports are synthetic test doubles. This module never performs live
network requests, model calls, repository writes or external actions.
"""
import hashlib
import importlib.util
import json
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

from zcira_control.langgraph_adapter import StateError, build_langgraph_graph, invoke_graph
from zcira_control.langgraph_source_worker import (
    SourceWorkerNodeError,
    build_source_worker_executor,
)
from zcira_control.source_fetcher import SourcePolicy, SourceRecord
from test_langgraph_adapter import MISSION, make_state
from test_source_worker import FakeTransport, make_task, NOW, ROBOTS, PAGE

LANGGRAPH_AVAILABLE = importlib.util.find_spec("langgraph") is not None
SOURCE_POLICY = SourcePolicy({
    "docs.apify.com": SourceRecord(
        "Apify Documentation",
        "A_PRIMARY_OFFICIAL",
        "P1",
    )
})


def load_json(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def make_source_task(task_id="zcira-source-snapshot-001", role="official_source_worker_a", priority="P1"):
    task = make_task()
    task["task_id"] = task_id
    task["idempotency_key"] = hashlib.sha256(task_id.encode("utf-8")).hexdigest()
    task["assigned_role"] = role
    task["priority"] = priority
    task["created_at"] = "2026-11-18T03:00:00Z"
    task["updated_at"] = "2026-11-18T03:00:00Z"
    return task


def make_executor(transport_factory=None, policy=SOURCE_POLICY):
    if transport_factory is None:
        transport_factory = lambda task: FakeTransport([
            TransportResponseForTests(200, {}, ROBOTS, "https://docs.apify.com/robots.txt"),
            TransportResponseForTests(200, {"content-type": "text/html"}, PAGE, "https://docs.apify.com/platform/actors"),
        ])
    return build_source_worker_executor(
        MISSION,
        policy,
        load_json("schemas/v1/task.schema.json"),
        load_json("schemas/v1/source_snapshot.schema.json"),
        load_json("schemas/v1/evidence.schema.json"),
        load_json("schemas/v1/source_snapshot_envelope.schema.json"),
        load_json("schemas/v1/source_worker_proposal.schema.json"),
        transport_factory=transport_factory,
        now_factory=lambda: NOW,
    )


class TransportResponseForTests:
    def __new__(cls, status_code, headers, body, final_url, too_large=False):
        from zcira_control.source_fetcher import TransportResponse
        return TransportResponse(status_code, headers, body, final_url, too_large)


@unittest.skipUnless(LANGGRAPH_AVAILABLE, "requires the pinned LangGraph package installed by S7-A")
class LangGraphSourceWorkerTests(unittest.TestCase):
    def test_executor_returns_metadata_only_proposal_with_verified_digests(self):
        task = make_source_task()
        proposal = make_executor()(task)
        self.assertEqual(proposal["result_status"], "COMPLETED")
        self.assertEqual(proposal["task_id"], task["task_id"])
        self.assertEqual(proposal["source_snapshot_content_ref"], "sha256:" + proposal["source_snapshot_envelope_sha256"])
        self.assertEqual(
            proposal["source_snapshot_storage_path"],
            "evidence/snapshots/sha256/" + proposal["source_snapshot_envelope_sha256"] + ".json",
        )
        self.assertFalse(proposal["raw_body_persisted"])
        self.assertFalse(proposal["write_performed"])
        self.assertTrue(proposal["requires_s7_publisher"])
        self.assertEqual(proposal["reviewer_verdict"], "PENDING")
        self.assertEqual(proposal["commercial_gate_status"], "UNKNOWN")
        self.assertEqual(proposal["evidence_proposal"]["gate_status"], "UNKNOWN")
        self.assertNotIn("raw_content", proposal)
        self.assertNotIn("body", proposal)

    def test_graph_executes_at_most_two_source_workers_and_never_completes_tasks(self):
        calls = []
        def transport_factory(task):
            calls.append(task["task_id"])
            return FakeTransport([
                TransportResponseForTests(200, {}, ROBOTS, "https://docs.apify.com/robots.txt"),
                TransportResponseForTests(200, {"content-type": "text/html"}, PAGE, "https://docs.apify.com/platform/actors"),
            ])
        executor = make_executor(transport_factory=transport_factory)
        graph = build_langgraph_graph(MISSION, source_worker_executor=executor)
        tasks = [
            make_source_task("zcira-source-a", "official_source_worker_a"),
            make_source_task("zcira-source-b", "official_source_worker_b"),
            make_source_task("zcira-source-c", "official_source_worker_a"),
        ]
        state = make_state(tasks, now="2026-11-20T03:30:00Z", source_worker_execution_enabled=True)
        result = invoke_graph(graph, state)
        self.assertEqual(len(calls), 2)
        self.assertEqual(len(result["source_worker_proposals"]), 2)
        self.assertEqual(result["source_worker_status"], "PROPOSALS_READY_NOT_PUBLISHED")
        self.assertEqual(result["completed_task_ids"], [])
        self.assertEqual(len(result["pending_task_ids"]), 3)
        self.assertFalse(result["source_worker_batch_proposal"]["write_authorized"])
        self.assertFalse(result["source_worker_batch_proposal"]["write_performed"])
        self.assertEqual(
            result["source_worker_batch_proposal"]["proposals_sha256"],
            hashlib.sha256(json.dumps(result["source_worker_proposals"], ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest(),
        )

    def test_source_worker_execution_is_disabled_by_default(self):
        calls = []
        executor = make_executor(transport_factory=lambda task: calls.append(task["task_id"]))
        graph = build_langgraph_graph(MISSION, source_worker_executor=executor)
        result = invoke_graph(graph, make_state([make_source_task()]))
        self.assertEqual(calls, [])
        self.assertEqual(result["source_worker_status"], "DISABLED_BY_DEFAULT")
        self.assertEqual(result["source_worker_proposals"], [])

    def test_robots_disallow_produces_blocked_metadata_without_evidence(self):
        task = make_source_task()
        executor = make_executor(transport_factory=lambda task: FakeTransport([
            TransportResponseForTests(200, {}, b"User-agent: *\\nDisallow: /\\n", "https://docs.apify.com/robots.txt"),
        ]))
        proposal = executor(task)
        self.assertEqual(proposal["result_status"], "BLOCKED")
        self.assertEqual(proposal["evidence_proposal"], None)
        self.assertEqual(proposal["source_snapshot_envelope"]["fetch_status"], "BLOCKED_BY_POLICY")
        self.assertFalse(proposal["raw_body_persisted"])

    def test_executor_refuses_live_network_policy(self):
        live_policy = SourcePolicy(
            {"docs.apify.com": SourceRecord("Apify Documentation", "A_PRIMARY_OFFICIAL", "P1")},
            live_network_enabled=True,
            dns_pinning=True,
            egress_controls_audited=True,
        )
        with self.assertRaises(SourceWorkerNodeError):
            make_executor(policy=live_policy)

    def test_executor_refuses_transport_without_test_marker(self):
        executor = make_executor(transport_factory=lambda task: object())
        with self.assertRaises(SourceWorkerNodeError):
            executor(make_source_task())

    def test_graph_rejects_executor_output_with_raw_payload(self):
        def malicious_executor(task):
            return {"raw_content": "not allowed"}
        graph = build_langgraph_graph(MISSION, source_worker_executor=malicious_executor)
        result = invoke_graph(
            graph,
            make_state([make_source_task()], now="2026-11-20T03:30:00Z", source_worker_execution_enabled=True),
        )
        self.assertEqual(result["source_worker_status"], "FAILED")
        self.assertEqual(result["source_worker_proposals"], [])
        self.assertEqual(result["source_worker_errors"][0]["error_code"], "StateError")

    def test_invoke_rejects_tampered_batch_digest(self):
        graph = build_langgraph_graph(MISSION, source_worker_executor=make_executor())
        base = graph
        class TamperedGraph:
            def invoke(self, state):
                result = base.invoke(state)
                result["source_worker_batch_proposal"]["proposals_sha256"] = "0" * 64
                return result
        with self.assertRaises(StateError):
            invoke_graph(
                TamperedGraph(),
                make_state([make_source_task()], now="2026-11-20T03:30:00Z", source_worker_execution_enabled=True),
            )

    def test_invoke_rejects_raw_content_in_tampered_proposal(self):
        graph = build_langgraph_graph(MISSION, source_worker_executor=make_executor())
        base = graph
        class TamperedGraph:
            def invoke(self, state):
                result = base.invoke(state)
                proposal = result["source_worker_proposals"][0]
                proposal["raw_content"] = "forbidden"
                unsigned = dict(proposal)
                unsigned.pop("proposal_sha256", None)
                proposal["proposal_sha256"] = hashlib.sha256(
                    json.dumps(unsigned, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
                ).hexdigest()
                proposals = result["source_worker_proposals"]
                result["source_worker_batch_proposal"]["proposals"] = proposals
                result["source_worker_batch_proposal"]["proposals_sha256"] = hashlib.sha256(
                    json.dumps(proposals, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
                ).hexdigest()
                return result
        with self.assertRaises(StateError):
            invoke_graph(
                TamperedGraph(),
                make_state([make_source_task()], now="2026-11-20T03:30:00Z", source_worker_execution_enabled=True),
            )


if __name__ == "__main__":
    unittest.main()
