import unittest
import hashlib
import sys
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from zcira_control.checkpoints import StaleCheckpoint, compare_and_swap_checkpoint
from zcira_control.leases import acquire_lease
from zcira_control.policy import (
    CANONICAL_REPO, ENVIRONMENT_NAMESPACE, PROJECT_ID, STATE_NAMESPACE,
    PolicyError, evaluate_commercial_release, validate_mission_context, validate_task, validate_repo_path,
)
from zcira_control.queue import plan_batch, plan_publisher_task
from zcira_control.quota import provider_eligibility, record_failure, record_successful_probe

NOW = datetime(2026, 11, 15, 3, 0, tzinfo=timezone.utc)
SHA = "a" * 40

MISSION = {
    "project_id": PROJECT_ID, "mission_id": PROJECT_ID, "canonical_repo": CANONICAL_REPO,
    "branch": "main", "environment_namespace": ENVIRONMENT_NAMESPACE, "state_namespace": STATE_NAMESPACE,
    "max_parallel_research_workers": 2, "single_writer_role": "evidence_publisher", "spend_cap_inr": 0,
    "paid_fallback_allowed": False, "trial_credit_dependency_allowed": False, "shared_state_with_other_missions": False, "cross_mission_write_allowed": False,
    "active": True, "allowed_paths": ["PROJECT_CONTINUITY.md", "docs/**", "config/**", "schemas/**", "tests/**", "scripts/**", "src/**", "requirements-test.txt", ".github/workflows/zcira-readonly-validation.yml"],
    "denied_paths": ["secrets/**", "private/**"],
    "allowed_action_classes": ["READ_PUBLIC", "PARSE_PUBLIC", "HASH_PUBLIC", "CREATE_INTERNAL_DRAFT", "WRITE_REPO_VALIDATED"],
    "denied_action_classes": ["PURCHASE", "PAID_FALLBACK", "BILLING_ENABLE", "ACCOUNT_CREATE", "KYC", "ACCEPT_TERMS", "CONTACT_EXTERNAL", "SUBMIT", "SECURITY_TEST", "PUBLISH_PRODUCT", "WALLET_SIGN", "TRANSFER_FUNDS"],
}

def make_task(task_id="zcira-task-001", priority="P1", created="2026-11-15T02:00:00Z", key=None, category_id=1):
    return {
        "project_id": PROJECT_ID, "mission_id": PROJECT_ID, "canonical_repo": CANONICAL_REPO, "branch": "main",
        "task_id": task_id, "idempotency_key": key or hashlib.sha256(task_id.encode()).hexdigest(),
        "priority": priority, "category_id": category_id, "status": "QUEUED", "created_at": created,
        "attempt_count": 0, "max_attempts": 2, "allowed_actions": ["READ_PUBLIC"],
        "external_actions_allowed": False, "paid_provider_routes_enabled": False,
    }

def make_lease(lease_id="lease-1", holder="evidence_publisher", write=True, status="ACTIVE", expiry="2026-11-15T04:00:00Z"):
    return {
        "project_id": PROJECT_ID, "mission_id": PROJECT_ID, "canonical_repo": CANONICAL_REPO, "branch": "main",
        "environment_namespace": ENVIRONMENT_NAMESPACE, "state_namespace": STATE_NAMESPACE,
        "lease_id": lease_id, "resource_key": "repo-main-single-writer", "lease_kind": "REPOSITORY_SINGLE_WRITER",
        "task_id": "zcira-task-001", "holder_id": "worker-1", "holder_role": holder, "write_access": write,
        "cross_mission_share_allowed": False, "status": status, "acquired_at": "2026-11-15T02:00:00Z",
        "expires_at": expiry, "base_commit_sha": SHA,
    }

def make_approval():
    return {
        "approval_id": "approval-exact-action-1", "mission_id": PROJECT_ID,
        "requested_action": "PUBLISH_PRODUCT", "target_resource": "apify-store/actor-xyz",
        "billing_requirement": "NO_BILLING_REQUIRED", "zero_cost_eligible": True,
        "spend_cap_inr": 0, "paid_fallback_allowed": False,
        "automatic_external_action_allowed": False, "approval_is_exact_scope_only": True,
        "cannot_override_zero_cost_or_prohibited_actions": True, "status": "APPROVED", "target_service": "apify-store", "scopes": ["actor.publish.draft"],
        "expires_at": "2026-11-16T03:00:00Z",
    }

def make_provider():
    return {
        "provider_plan": "FREE", "verified_free": True, "billing_required": False,
        "payment_method_required": False, "trial_credit_dependency": False, "paid_fallback_allowed": False,
        "approved_for_use": True, "circuit_breaker": {"state": "CLOSED", "failure_count": 0,
        "opened_at": None, "next_retry_at": None, "reason": None},
    }

class ControlPlaneTests(unittest.TestCase):
    def test_mission_context_is_exact(self):
        validate_mission_context(MISSION)
        bad = dict(MISSION, canonical_repo="another/repo")
        with self.assertRaises(PolicyError): validate_mission_context(bad)

    def test_category_24_cannot_be_promoted(self):
        task = make_task(category_id=24, priority="P1")
        with self.assertRaises(PolicyError): validate_task(task, MISSION)

    def test_repository_path_allowlist_allows_only_s7a_workflow_and_blocks_other_workflows_and_traversal(self):
        validate_repo_path("docs/report.md", MISSION)
        validate_repo_path(".github/workflows/zcira-readonly-validation.yml", MISSION)
        with self.assertRaises(PolicyError): validate_repo_path(".github/workflows/zcira-publisher.yml", MISSION)
        with self.assertRaises(PolicyError): validate_repo_path("../other-repo/file", MISSION)

    def test_external_action_is_rejected(self):
        task = make_task()
        task["allowed_actions"] = ["PUBLISH"]
        with self.assertRaises(PolicyError): validate_task(task, MISSION)

    def test_repository_write_requires_publisher_role(self):
        task = make_task()
        task["allowed_actions"] = ["WRITE_REPO_VALIDATED"]
        with self.assertRaises(PolicyError): validate_task(task, MISSION)
        task["assigned_role"] = "evidence_publisher"
        task["parameters"] = {"target_path": "docs/report.md"}
        validate_task(task, MISSION)

    def test_paid_route_is_rejected(self):
        task = make_task()
        task["paid_provider_routes_enabled"] = True
        with self.assertRaises(PolicyError): validate_task(task, MISSION)

    def test_batch_uses_locked_priority_and_two_worker_limit(self):
        tasks = [make_task("zcira-p2", "P2"), make_task("zcira-p1a", "P1"), make_task("zcira-p1b", "P1")]
        planned = plan_batch(tasks, MISSION)
        self.assertEqual([x["task_id"] for x in planned], ["zcira-p1a", "zcira-p1b"])
        with self.assertRaises(PolicyError): plan_batch(tasks, MISSION, max_parallel=3)

    def test_research_batch_never_selects_publisher_task(self):
        publisher = make_task("zcira-publisher", "P1")
        publisher["assigned_role"] = "evidence_publisher"
        publisher["allowed_actions"] = ["WRITE_REPO_VALIDATED"]
        publisher["parameters"] = {"target_path": "docs/report.md"}
        research = make_task("zcira-research", "P2")
        planned = plan_batch([publisher, research], MISSION)
        self.assertEqual([x["task_id"] for x in planned], ["zcira-research"])

    def test_publisher_queue_is_single_and_blocked_by_active_lease(self):
        first = make_task("zcira-publisher-a", "P2")
        first["assigned_role"] = "evidence_publisher"
        first["allowed_actions"] = ["WRITE_REPO_VALIDATED"]
        first["parameters"] = {"target_path": "docs/report-a.md"}
        second = make_task("zcira-publisher-b", "P1")
        second["assigned_role"] = "evidence_publisher"
        second["allowed_actions"] = ["WRITE_REPO_VALIDATED"]
        second["parameters"] = {"target_path": "docs/report-b.md"}
        self.assertEqual(plan_publisher_task([first, second], MISSION, [], NOW)["task_id"], "zcira-publisher-b")
        self.assertIsNone(plan_publisher_task([first, second], MISSION, [make_lease()], NOW))

    def test_idempotent_tasks_are_not_selected_twice(self):
        key = "f" * 64
        tasks = [make_task("zcira-duplicate-b", "P2", key=key), make_task("zcira-duplicate-a", "P1", key=key)]
        planned = plan_batch(tasks, MISSION)
        self.assertEqual(len(planned), 1)
        self.assertEqual(planned[0]["task_id"], "zcira-duplicate-a")

    def test_unknown_gate_never_passes(self):
        gates = {name: {"status": "UNKNOWN"} for name in (
            "buyer_demand", "ip_licensing_data_rights", "zero_cost_economics",
            "india_seller_eligibility_settlement", "autonomous_fulfilment_workload")}
        result = evaluate_commercial_release(gates, make_approval(), "PUBLISH_PRODUCT", "apify-store/actor-xyz", NOW)
        self.assertFalse(result["release_authorized"])
        self.assertEqual(result["overall_status"], "HOLD")

    def test_all_gates_pass_without_owner_approval_still_holds_release(self):
        gates = {name: {"status": "PASS"} for name in (
            "buyer_demand", "ip_licensing_data_rights", "zero_cost_economics",
            "india_seller_eligibility_settlement", "autonomous_fulfilment_workload")}
        result = evaluate_commercial_release(gates, None, "PUBLISH_PRODUCT", "apify-store/actor-xyz", NOW)
        self.assertFalse(result["release_authorized"])
        self.assertEqual(result["reason"], "EXACT_OWNER_APPROVAL_REQUIRED")

    def test_all_gates_pass_and_exact_approval_reference_allows_release_decision(self):
        gates = {name: {"status": "PASS"} for name in (
            "buyer_demand", "ip_licensing_data_rights", "zero_cost_economics",
            "india_seller_eligibility_settlement", "autonomous_fulfilment_workload")}
        result = evaluate_commercial_release(gates, make_approval(), "PUBLISH_PRODUCT", "apify-store/actor-xyz", NOW)
        self.assertTrue(result["release_authorized"])
        self.assertFalse(result["external_action_performed"])

    def test_wrong_target_approval_is_rejected(self):
        gates = {name: {"status": "PASS"} for name in (
            "buyer_demand", "ip_licensing_data_rights", "zero_cost_economics",
            "india_seller_eligibility_settlement", "autonomous_fulfilment_workload")}
        result = evaluate_commercial_release(gates, make_approval(), "PUBLISH_PRODUCT", "another-target", NOW)
        self.assertFalse(result["release_authorized"])

    def test_expired_owner_approval_is_rejected(self):
        gates = {name: {"status": "PASS"} for name in (
            "buyer_demand", "ip_licensing_data_rights", "zero_cost_economics",
            "india_seller_eligibility_settlement", "autonomous_fulfilment_workload")}
        approval = make_approval(); approval["expires_at"] = "2026-11-14T03:00:00Z"
        result = evaluate_commercial_release(gates, approval, "PUBLISH_PRODUCT", "apify-store/actor-xyz", NOW)
        self.assertFalse(result["release_authorized"])

    def test_single_writer_lease_conflict_is_rejected(self):
        first = make_lease("lease-1")
        second = make_lease("lease-2")
        with self.assertRaises(PolicyError): acquire_lease([first], second, NOW)

    def test_expired_lease_does_not_block_new_writer(self):
        expired = make_lease("lease-old", status="EXPIRED", expiry="2026-11-15T02:30:00Z")
        proposed = make_lease("lease-new")
        result = acquire_lease([expired], proposed, NOW)
        self.assertEqual(result["lease_id"], "lease-new")

    def test_research_worker_cannot_hold_writer_lease(self):
        bad = make_lease("lease-worker", holder="official_source_worker_a", write=True)
        with self.assertRaises(PolicyError): acquire_lease([], bad, NOW)

    def test_stale_checkpoint_is_rejected(self):
        with self.assertRaises(StaleCheckpoint): compare_and_swap_checkpoint(SHA, "b" * 40, "c" * 40)

    def test_matching_checkpoint_is_accepted(self):
        self.assertEqual(compare_and_swap_checkpoint(SHA, SHA, "c" * 40), "c" * 40)

    def test_unverified_provider_is_not_eligible(self):
        provider = make_provider(); provider["verified_free"] = False
        self.assertFalse(provider_eligibility(provider)[0])

    def test_billing_or_payment_method_provider_is_not_eligible(self):
        provider = make_provider(); provider["payment_method_required"] = True
        self.assertFalse(provider_eligibility(provider)[0])

    def test_trial_credit_and_paid_fallback_are_not_eligible(self):
        provider = make_provider(); provider["trial_credit_dependency"] = True
        self.assertFalse(provider_eligibility(provider)[0])
        provider = make_provider(); provider["paid_fallback_allowed"] = True
        self.assertFalse(provider_eligibility(provider)[0])

    def test_half_open_circuit_is_probe_only_not_general_eligibility(self):
        provider = make_provider(); provider["circuit_breaker"]["state"] = "HALF_OPEN"
        self.assertFalse(provider_eligibility(provider)[0])

    def test_open_circuit_breaker_is_not_eligible(self):
        provider = make_provider(); provider["circuit_breaker"]["state"] = "OPEN"
        self.assertFalse(provider_eligibility(provider)[0])

    def test_circuit_breaker_opens_after_three_failures(self):
        state = {"state": "CLOSED", "failure_count": 0, "opened_at": None, "next_retry_at": None, "reason": None}
        state = record_failure(state); state = record_failure(state); state = record_failure(state)
        self.assertEqual(state["state"], "OPEN")

    def test_half_open_success_closes_circuit(self):
        state = {"state": "HALF_OPEN", "failure_count": 2, "opened_at": "x", "next_retry_at": "y", "reason": "probe"}
        result = record_successful_probe(state)
        self.assertEqual(result["state"], "CLOSED")
        self.assertEqual(result["failure_count"], 0)

if __name__ == "__main__":
    unittest.main()
