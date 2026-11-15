from __future__ import annotations

from typing import Any, Mapping

from .policy import PolicyError

BLOCKING_CIRCUIT_STATES = frozenset({"NOT_VERIFIED", "OPEN", "BLOCKED"})


def provider_eligibility(provider: Mapping[str, Any]) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    if provider.get("provider_plan") != "FREE": reasons.append("PLAN_NOT_FREE")
    if provider.get("verified_free") is not True: reasons.append("FREE_TIER_NOT_VERIFIED")
    if provider.get("billing_required") is True: reasons.append("BILLING_REQUIRED")
    if provider.get("payment_method_required") is True: reasons.append("PAYMENT_METHOD_REQUIRED")
    if provider.get("trial_credit_dependency") is not False: reasons.append("TRIAL_CREDIT_DEPENDENCY")
    if provider.get("paid_fallback_allowed") is not False: reasons.append("PAID_FALLBACK_ENABLED")
    if provider.get("approved_for_use") is not True: reasons.append("PROVIDER_NOT_APPROVED")
    circuit_obj = provider.get("circuit_breaker")
    if not isinstance(circuit_obj, Mapping):
        reasons.append("CIRCUIT_STATE_MISSING")
        circuit = None
    else:
        circuit = circuit_obj.get("state")
    if circuit in BLOCKING_CIRCUIT_STATES: reasons.append(f"CIRCUIT_{circuit}")
    if circuit != "CLOSED": reasons.append("CIRCUIT_NOT_CLOSED")
    return (not reasons, reasons)


def record_failure(circuit: Mapping[str, Any], threshold: int = 3) -> dict[str, Any]:
    if threshold < 1:
        raise PolicyError("circuit threshold must be positive")
    state = dict(circuit)
    if state.get("state") in {"BLOCKED", "NOT_VERIFIED"}:
        return state
    failures = int(state.get("failure_count", 0)) + 1
    state["failure_count"] = failures
    if failures >= threshold:
        state["state"] = "OPEN"
    return state


def record_successful_probe(circuit: Mapping[str, Any]) -> dict[str, Any]:
    state = dict(circuit)
    if state.get("state") != "HALF_OPEN":
        raise PolicyError("successful probe is only valid in HALF_OPEN state")
    state["state"] = "CLOSED"
    state["failure_count"] = 0
    state["opened_at"] = None
    state["next_retry_at"] = None
    state["reason"] = None
    return state
