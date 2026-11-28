import copy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DIR = ROOT / "schemas" / "v1"
FIXTURE_DIR = ROOT / "tests" / "fixtures" / "s3_v1"
CONFIG_DIR = ROOT / "config"

SCHEMA_FILES = {
    "task": "task.schema.json",
    "evidence": "evidence.schema.json",
    "source_snapshot": "source_snapshot.schema.json",
    "source_snapshot_envelope": "source_snapshot_envelope.schema.json",
    "source_worker_proposal": "source_worker_proposal.schema.json",
    "gate_decision": "gate_decision.schema.json",
    "run_state": "run_state.schema.json",
    "agent_message": "agent_message.schema.json",
    "approval": "approval.schema.json",
    "quota_ledger": "quota_ledger.schema.json",
    "resource_lease": "resource_lease.schema.json",
    "mission_registry": "mission_registry.schema.json",
    "state_manifest": "state_manifest.schema.json",
    "langgraph_checkpoint": "langgraph_checkpoint.schema.json",
    "langgraph_pending_writes": "langgraph_pending_writes.schema.json",
}
FIXTURES = {
    "task": "valid_task.json",
    "evidence": "valid_evidence.json",
    "source_snapshot": "valid_source_snapshot.json",
    "source_snapshot_envelope": "valid_source_snapshot_envelope.json",
    "source_worker_proposal": "valid_source_worker_proposal.json",
    "gate_decision": "valid_gate_decision.json",
    "run_state": "valid_run_state.json",
    "agent_message": "valid_agent_message.json",
    "approval": "valid_approval_pending.json",
    "quota_ledger": "valid_quota_ledger.json",
    "resource_lease": "valid_resource_lease.json",
    "mission_registry": "valid_mission_registry.json",
    "state_manifest": "valid_state_manifest.json",
    "langgraph_checkpoint": "valid_langgraph_checkpoint.json",
    "langgraph_pending_writes": "valid_langgraph_pending_writes.json",
}

def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))

def schema_for(name):
    schema = load_json(SCHEMA_DIR / SCHEMA_FILES[name])
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())

def fixture_for(name):
    if name == "mission_registry":
        return load_json(CONFIG_DIR / "mission_registry.v1.json")
    return load_json(FIXTURE_DIR / FIXTURES[name])

@pytest.mark.parametrize("name", list(SCHEMA_FILES))
def test_valid_fixture_passes(name):
    schema_for(name).validate(fixture_for(name))

def assert_rejected(name, value):
    errors = list(schema_for(name).iter_errors(value))
    assert errors, f"{name} unexpectedly accepted an invalid contract"

def test_cross_mission_task_is_rejected():
    value = copy.deepcopy(fixture_for("task"))
    value["mission_id"] = "OTHER-MISSION"
    assert_rejected("task", value)

def test_external_publish_action_is_rejected_from_task():
    value = copy.deepcopy(fixture_for("task"))
    value["allowed_actions"].append("PUBLISH")
    assert_rejected("task", value)

def test_unknown_gate_cannot_be_promoted_to_release():
    value = copy.deepcopy(fixture_for("gate_decision"))
    value["overall_status"] = "PASS"
    value["release_authorized"] = True
    value["owner_approval_id"] = "approval-not-real-fixture"
    assert_rejected("gate_decision", value)

def test_wildcard_oauth_scope_is_rejected():
    value = copy.deepcopy(fixture_for("approval"))
    value["scopes"] = ["*"]
    assert_rejected("approval", value)

def test_paid_fallback_is_rejected():
    value = copy.deepcopy(fixture_for("quota_ledger"))
    value["paid_fallback_allowed"] = True
    assert_rejected("quota_ledger", value)

def test_billing_required_provider_cannot_be_approved():
    value = copy.deepcopy(fixture_for("quota_ledger"))
    value["billing_required"] = True
    value["approved_for_use"] = True
    assert_rejected("quota_ledger", value)

def test_open_circuit_breaker_cannot_remain_approved():
    value = copy.deepcopy(fixture_for("quota_ledger"))
    value["circuit_breaker"]["state"] = "OPEN"
    value["approved_for_use"] = True
    assert_rejected("quota_ledger", value)

def test_other_repository_lease_is_rejected():
    value = copy.deepcopy(fixture_for("resource_lease"))
    value["canonical_repo"] = "another-owner/another-repo"
    assert_rejected("resource_lease", value)

def test_research_worker_cannot_hold_repository_write_lease():
    value = copy.deepcopy(fixture_for("resource_lease"))
    value["holder_role"] = "official_source_worker_a"
    value["write_access"] = True
    assert_rejected("resource_lease", value)

def test_cross_mission_shared_state_is_rejected():
    value = copy.deepcopy(fixture_for("mission_registry"))
    value["shared_state_with_other_missions"] = True
    assert_rejected("mission_registry", value)

def test_agent_cannot_mutate_policy():
    value = copy.deepcopy(fixture_for("agent_message"))
    value["policy_mutation_allowed"] = True
    assert_rejected("agent_message", value)

def test_source_snapshot_cannot_bypass_access_controls():
    value = copy.deepcopy(fixture_for("source_snapshot"))
    value["access_control_bypass"] = True
    assert_rejected("source_snapshot", value)

def test_kill_switch_requires_paused_run_state():
    value = copy.deepcopy(fixture_for("run_state"))
    value["kill_switch"] = True
    value["status"] = "RUNNING"
    assert_rejected("run_state", value)

def test_public_fixtures_contain_no_secret_or_personal_identity_fields():
    forbidden = {"password", "secret", "access_token", "refresh_token", "cookie", "private_key", "email", "otp", "recovery_code"}
    paths = list(FIXTURE_DIR.glob("*.json")) + [CONFIG_DIR / "mission_registry.v1.json"]
    for path in paths:
        obj = load_json(path)
        def walk(node):
            if isinstance(node, dict):
                for key, value in node.items():
                    assert key.casefold() not in forbidden, f"forbidden field {key} in {path}"
                    walk(value)
            elif isinstance(node, list):
                for value in node:
                    walk(value)
        walk(obj)

def test_unknown_billing_requirement_cannot_be_approved():
    value = copy.deepcopy(fixture_for("approval"))
    value["zero_cost_eligible"] = True
    value["status"] = "APPROVED"
    value["decision_at"] = "2026-11-15T03:30:00Z"
    assert_rejected("approval", value)

def test_unverified_provider_cannot_be_approved():
    value = copy.deepcopy(fixture_for("quota_ledger"))
    value["verified_free"] = False
    value["approved_for_use"] = True
    assert_rejected("quota_ledger", value)

def test_non_http_source_url_is_rejected():
    value = copy.deepcopy(fixture_for("source_snapshot"))
    value["source_url"] = "ftp://example.org/public-file"
    assert_rejected("source_snapshot", value)

def test_mission_registry_cannot_enable_trial_credit_dependency():
    value = copy.deepcopy(fixture_for("mission_registry"))
    value["trial_credit_dependency_allowed"] = True
    assert_rejected("mission_registry", value)

def test_repository_write_task_requires_evidence_publisher_role():
    value = copy.deepcopy(fixture_for("task"))
    value["allowed_actions"] = ["WRITE_REPO_VALIDATED"]
    value["assigned_role"] = "official_source_worker_a"
    assert_rejected("task", value)
    value["assigned_role"] = "evidence_publisher"
    schema_for("task").validate(value)

def test_state_manifest_active_lease_requires_matching_lease_object():
    value = copy.deepcopy(fixture_for("state_manifest"))
    value["active_writer_lease_id"] = "lease-abc123"
    assert_rejected("state_manifest", value)

def test_state_manifest_cannot_enable_paid_provider_routes():
    value = copy.deepcopy(fixture_for("state_manifest"))
    value["paid_provider_routes_enabled"] = True
    assert_rejected("state_manifest", value)


def test_source_worker_proposal_cannot_persist_raw_body_or_publish():
    value = copy.deepcopy(fixture_for("source_worker_proposal"))
    value["raw_body_persisted"] = True
    assert_rejected("source_worker_proposal", value)
    value = copy.deepcopy(fixture_for("source_worker_proposal"))
    value["write_performed"] = True
    assert_rejected("source_worker_proposal", value)


def test_non_completed_source_worker_proposal_cannot_claim_evidence():
    value = copy.deepcopy(fixture_for("source_worker_proposal"))
    value["result_status"] = "BLOCKED"
    assert_rejected("source_worker_proposal", value)


def test_state_manifest_accepts_langgraph_object_kinds():
    value = copy.deepcopy(fixture_for("state_manifest"))
    value["objects"].extend([
        {
            "kind": "langgraph_checkpoint",
            "object_id": "00000000-0000-6000-8000-000000000001",
            "path": "state/objects/" + "a" * 64 + ".json",
            "sha256": "a" * 64,
            "schema_version": "1.0.0",
        },
        {
            "kind": "langgraph_pending_writes",
            "object_id": "b" * 64,
            "path": "state/objects/" + "b" * 64 + ".json",
            "sha256": "b" * 64,
            "schema_version": "1.0.0",
        },
    ])
    schema_for("state_manifest").validate(value)


def test_langgraph_checkpoint_accepts_bounded_branch_route_channel():
    value = copy.deepcopy(fixture_for("langgraph_checkpoint"))
    value["checkpoint"]["channel_values"]["branch:to:node_a"] = None
    schema_for("langgraph_checkpoint").validate(value)


def test_langgraph_checkpoint_rejects_malformed_branch_route_channel():
    value = copy.deepcopy(fixture_for("langgraph_checkpoint"))
    value["checkpoint"]["channel_values"]["branch:to:node.a"] = None
    assert_rejected("langgraph_checkpoint", value)


def test_langgraph_checkpoint_rejects_unknown_state_channel():
    value = copy.deepcopy(fixture_for("langgraph_checkpoint"))
    value["checkpoint"]["channel_values"]["raw_source_body"] = "must-not-persist"
    assert_rejected("langgraph_checkpoint", value)


def test_langgraph_checkpoint_rejects_other_mission():
    value = copy.deepcopy(fixture_for("langgraph_checkpoint"))
    value["project_id"] = "OTHER-MISSION"
    assert_rejected("langgraph_checkpoint", value)


def test_langgraph_checkpoint_requires_empty_namespace():
    value = copy.deepcopy(fixture_for("langgraph_checkpoint"))
    value["checkpoint_ns"] = "other"
    assert_rejected("langgraph_checkpoint", value)


def test_langgraph_pending_writes_accepts_bounded_branch_route_channel():
    value = copy.deepcopy(fixture_for("langgraph_pending_writes"))
    value["writes"] = [{"channel": "branch:to:node_a", "index": 0, "value": None}]
    schema_for("langgraph_pending_writes").validate(value)


def test_langgraph_pending_writes_rejects_malformed_branch_route_channel():
    value = copy.deepcopy(fixture_for("langgraph_pending_writes"))
    value["writes"] = [{"channel": "branch:to:node.a", "index": 0, "value": None}]
    assert_rejected("langgraph_pending_writes", value)


def test_langgraph_pending_writes_rejects_invalid_index():
    value = copy.deepcopy(fixture_for("langgraph_pending_writes"))
    value["writes"][0]["index"] = 64
    assert_rejected("langgraph_pending_writes", value)


def test_langgraph_pending_writes_rejects_more_than_64_records():
    value = copy.deepcopy(fixture_for("langgraph_pending_writes"))
    value["writes"] = value["writes"] * 65
    assert_rejected("langgraph_pending_writes", value)

@pytest.mark.parametrize("name", ["state_manifest", "run_state", "resource_lease"])
def test_durable_state_objects_are_pinned_to_evidence_ledger(name):
    value = copy.deepcopy(fixture_for(name))
    assert value["branch"] == "evidence-ledger"
    value["branch"] = "main"
    assert_rejected(name, value)


def test_mission_registry_separates_code_and_state_branches():
    value = copy.deepcopy(fixture_for("mission_registry"))
    assert value["branch"] == "main"
    assert value["state_branch"] == "evidence-ledger"
    value["state_branch"] = "main"
    assert_rejected("mission_registry", value)


def test_repository_writer_lease_uses_evidence_ledger_resource_key():
    value = copy.deepcopy(fixture_for("resource_lease"))
    value["resource_key"] = "repo-main-single-writer"
    assert_rejected("resource_lease", value)
