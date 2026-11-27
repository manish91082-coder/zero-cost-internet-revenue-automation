from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from zcira_control.langgraph_checkpoint_saver import (
    CheckpointAsyncUnsupported,
    CheckpointContractError,
    LangGraphCheckpointSaver,
)
from zcira_control.policy import CANONICAL_BRANCH, CANONICAL_REPO, ENVIRONMENT_NAMESPACE, PROJECT_ID, STATE_NAMESPACE
from zcira_control.state_repository import StateRepository, canonical_json


class FakeDurableStore:
    def __init__(self):
        self.head = "a" * 40
        self.snapshots = {self.head: {}}
        self.counter = 0

    def read_head(self):
        return self.head

    def read_file(self, path, ref=None):
        selected = ref or self.head
        return self.snapshots.get(selected, {}).get(path)

    def commit_files(self, expected_head_sha, files, message):
        if expected_head_sha != self.head:
            raise RuntimeError("stale fake Git head")
        self.counter += 1
        material = f"{expected_head_sha}:{self.counter}:{message}:{canonical_json(dict(files))}"
        commit_sha = hashlib.sha1(material.encode("utf-8")).hexdigest()
        snapshot = dict(self.snapshots[self.head])
        snapshot.update(files)
        self.snapshots[commit_sha] = snapshot
        self.head = commit_sha
        return {"commit_sha": commit_sha}


def make_saver(run_id="zcira-run-saver-test-001", now=None):
    now = now or datetime.now(timezone.utc).replace(microsecond=0)
    store = FakeDurableStore()
    repository = StateRepository(store)
    repository.initialize(now)
    lease, lease_head = repository.acquire_writer_lease("s5-checkpointer-test", now, ttl_seconds=900)
    saver = LangGraphCheckpointSaver(
        repository,
        lease["lease_id"],
        lease_head,
        run_id,
        now_fn=lambda: now,
        schema_dir=ROOT / "schemas" / "v1",
        policy_path=ROOT / "config" / "s5_checkpoint_policy.v1.json",
    )
    return store, repository, lease, saver, now


def make_checkpoint(checkpoint_id, now, channel_values=None):
    values = channel_values or {"completed_task_ids": []}
    return {
        "v": 2,
        "id": checkpoint_id,
        "ts": now.isoformat().replace("+00:00", "Z"),
        "channel_values": values,
        "channel_versions": {key: 1 for key in values},
        "versions_seen": {"__start__": {}},
        "pending_sends": [],
    }


def make_config(run_id="zcira-run-saver-test-001", checkpoint_id=None):
    configurable = {"thread_id": run_id, "checkpoint_ns": ""}
    if checkpoint_id is not None:
        configurable["checkpoint_id"] = checkpoint_id
    return {"configurable": configurable}


def test_checkpoint_roundtrip_pending_write_order_and_list():
    _, _, _, saver, now = make_saver()
    checkpoint_id = "00000000-0000-6000-8000-000000000001"
    checkpoint = make_checkpoint(checkpoint_id, now, {"completed_task_ids": ["seed"], "status": "RUNNING"})
    config = make_config()
    written_config = saver.put(config, checkpoint, {"source": "input", "step": 0}, {"completed_task_ids": 1, "status": 1})
    assert written_config["configurable"]["checkpoint_id"] == checkpoint_id

    saver.put_writes(written_config, [("completed_task_ids", ["z"])], "task-z", "z/path")
    saver.put_writes(written_config, [("completed_task_ids", ["a"])], "task-a", "a/path")

    restored = saver.get_tuple(written_config)
    assert restored is not None
    assert restored.checkpoint["channel_values"]["completed_task_ids"] == ["seed"]
    assert restored.pending_writes == [
        ("task-a", "completed_task_ids", ["a"]),
        ("task-z", "completed_task_ids", ["z"]),
    ]
    listed = list(saver.list(make_config()))
    assert len(listed) == 1
    assert listed[0].checkpoint["id"] == checkpoint_id


def test_duplicate_checkpoint_and_pending_write_are_idempotent_but_conflicts_fail_closed():
    store, _, _, saver, now = make_saver()
    checkpoint_id = "00000000-0000-6000-8000-000000000002"
    checkpoint = make_checkpoint(checkpoint_id, now, {"completed_task_ids": ["same"]})
    config = make_config()
    saved = saver.put(config, checkpoint, {"source": "input"}, {"completed_task_ids": 1})
    head_after_checkpoint = store.read_head()
    assert saver.put(config, checkpoint, {"source": "input"}, {"completed_task_ids": 1}) == saved
    assert store.read_head() == head_after_checkpoint

    saver.put_writes(saved, [("completed_task_ids", ["same"])], "task-same", "node")
    head_after_write = store.read_head()
    saver.put_writes(saved, [("completed_task_ids", ["same"])], "task-same", "node")
    assert store.read_head() == head_after_write
    with pytest.raises(CheckpointContractError):
        saver.put_writes(saved, [("completed_task_ids", ["different"])], "task-same", "node")
    changed = make_checkpoint(checkpoint_id, now, {"completed_task_ids": ["different"]})
    with pytest.raises(CheckpointContractError):
        saver.put(config, changed, {"source": "input"}, {"completed_task_ids": 1})


def test_wrong_thread_unknown_channel_and_sensitive_fields_are_rejected():
    _, _, _, saver, now = make_saver()
    checkpoint_id = "00000000-0000-6000-8000-000000000003"
    with pytest.raises(CheckpointContractError):
        saver.put(make_config("zcira-run-other-001"), make_checkpoint(checkpoint_id, now), {}, {})

    bad_channel = make_checkpoint(checkpoint_id, now, {"unknown_channel": "x"})
    with pytest.raises(CheckpointContractError):
        saver.put(make_config(), bad_channel, {}, {})

    bad_secret = make_checkpoint(checkpoint_id, now, {"completed_task_ids": []})
    with pytest.raises(CheckpointContractError):
        saver.put(make_config(), bad_secret, {"api_key": "never-persist"}, {})


def test_non_json_values_and_oversized_checkpoint_are_rejected():
    _, _, _, saver, now = make_saver()
    checkpoint_id = "00000000-0000-6000-8000-000000000004"
    non_json = make_checkpoint(checkpoint_id, now, {"completed_task_ids": [("tuple", "forbidden")]})
    with pytest.raises(CheckpointContractError):
        saver.put(make_config(), non_json, {}, {})
    oversized = make_checkpoint(checkpoint_id, now, {"completed_task_ids": ["x" * 270000]})
    with pytest.raises(CheckpointContractError):
        saver.put(make_config(), oversized, {}, {})


def test_delete_and_async_operations_fail_closed_without_mutation():
    store, _, _, saver, _ = make_saver()
    head = store.read_head()
    with pytest.raises(CheckpointContractError):
        saver.delete_thread("zcira-run-saver-test-001")
    with pytest.raises(CheckpointAsyncUnsupported):
        import asyncio
        asyncio.run(saver.aget_tuple(make_config()))
    assert store.read_head() == head


def test_new_saver_resumes_after_old_lease_expires():
    store, repository, lease, saver1, now = make_saver()
    checkpoint_id = "00000000-0000-6000-8000-000000000005"
    config = make_config()
    saver1.put(config, make_checkpoint(checkpoint_id, now, {"completed_task_ids": ["durable"]}), {}, {"completed_task_ids": 1})

    later = now + timedelta(seconds=901)
    repository2 = StateRepository(store)
    lease2, lease_head2 = repository2.acquire_writer_lease("s5-checkpointer-runner-2", later, ttl_seconds=900)
    saver2 = LangGraphCheckpointSaver(
        repository2,
        lease2["lease_id"],
        lease_head2,
        "zcira-run-saver-test-001",
        now_fn=lambda: later,
        schema_dir=ROOT / "schemas" / "v1",
        policy_path=ROOT / "config" / "s5_checkpoint_policy.v1.json",
    )
    restored = saver2.get_tuple(config)
    assert restored is not None
    assert restored.checkpoint["channel_values"]["completed_task_ids"] == ["durable"]


def test_branch_route_channel_requires_exact_compiled_node_binding():
    _, _, _, saver, now = make_saver()
    checkpoint_id = "00000000-0000-6000-8000-000000000006"
    saved = saver.put(make_config(), make_checkpoint(checkpoint_id, now), {}, {})

    with pytest.raises(CheckpointContractError):
        saver.put_writes(saved, [("branch:to:node_a", None)], "route-task-a", "~__pregel_pull, __start__")

    saver.bind_graph_nodes(("node_a",))
    saver.put_writes(saved, [("branch:to:node_a", None)], "route-task-a", "~__pregel_pull, __start__")
    restored = saver.get_tuple(saved)
    assert restored is not None
    assert restored.pending_writes == [("route-task-a", "branch:to:node_a", None)]

    with pytest.raises(CheckpointContractError):
        saver.put_writes(saved, [("branch:to:node_b", None)], "route-task-b", "~__pregel_pull, __start__")
    with pytest.raises(CheckpointContractError):
        saver.bind_graph_nodes(("node_b",))


def test_real_langgraph_interrupt_resume_across_two_saver_instances():
    from langgraph.graph import END, START, StateGraph

    from zcira_control.langgraph_adapter import SwarmGraphState

    now = datetime.now(timezone.utc).replace(microsecond=0)
    run_id = "zcira-run-crash-resume-001"
    store = FakeDurableStore()
    repository1 = StateRepository(store)
    repository1.initialize(now)
    lease1, head1 = repository1.acquire_writer_lease("s5-ephemeral-runner-1", now, ttl_seconds=900)
    saver1 = LangGraphCheckpointSaver(
        repository1, lease1["lease_id"], head1, run_id,
        now_fn=lambda: now, schema_dir=ROOT / "schemas" / "v1",
        policy_path=ROOT / "config" / "s5_checkpoint_policy.v1.json",
    )
    saver1.bind_graph_nodes(("node_a", "node_b"))

    calls = {"node_a": 0, "node_b": 0}

    def node_a(state):
        calls["node_a"] += 1
        return {"completed_task_ids": list(state.get("completed_task_ids", [])) + ["node-a"]}

    def node_b(state):
        calls["node_b"] += 1
        return {"completed_task_ids": list(state.get("completed_task_ids", [])) + ["node-b"]}

    builder = StateGraph(SwarmGraphState)
    builder.add_node("node_a", node_a)
    builder.add_node("node_b", node_b)
    builder.add_edge(START, "node_a")
    builder.add_edge("node_a", "node_b")
    builder.add_edge("node_b", END)

    config = {"configurable": {"thread_id": run_id, "checkpoint_ns": ""}}
    initial = {
        "project_id": PROJECT_ID,
        "mission_id": PROJECT_ID,
        "canonical_repo": CANONICAL_REPO,
        "branch": CANONICAL_BRANCH,
        "environment_namespace": ENVIRONMENT_NAMESPACE,
        "state_namespace": STATE_NAMESPACE,
        "run_id": run_id,
        "completed_task_ids": [],
    }
    graph1 = builder.compile(checkpointer=saver1, interrupt_before=["node_b"])
    graph1.invoke(initial, config)
    assert calls == {"node_a": 1, "node_b": 0}

    later = now + timedelta(seconds=901)
    repository2 = StateRepository(store)
    lease2, head2 = repository2.acquire_writer_lease("s5-ephemeral-runner-2", later, ttl_seconds=900)
    saver2 = LangGraphCheckpointSaver(
        repository2, lease2["lease_id"], head2, run_id,
        now_fn=lambda: later, schema_dir=ROOT / "schemas" / "v1",
        policy_path=ROOT / "config" / "s5_checkpoint_policy.v1.json",
    )
    saver2.bind_graph_nodes(("node_a", "node_b"))
    graph2 = builder.compile(checkpointer=saver2)
    resumed = graph2.invoke(None, config)
    assert calls == {"node_a": 1, "node_b": 1}
    assert resumed["completed_task_ids"] == ["node-a", "node-b"]
