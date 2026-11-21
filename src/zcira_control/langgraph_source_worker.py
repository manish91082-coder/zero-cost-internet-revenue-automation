from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Any, Callable, Mapping

from jsonschema import Draft202012Validator, FormatChecker

from .policy import PROJECT_ID, SINGLE_WRITER_ROLE, validate_mission_context
from .snapshot_envelope import build_metadata_snapshot_envelope, canonical_json_bytes
from .source_fetcher import SourcePolicy
from .source_worker import run_source_snapshot_task


class SourceWorkerNodeError(ValueError):
    """A source-worker node cannot safely construct a publisher proposal."""


def build_source_worker_executor(
    mission_context: Mapping[str, Any],
    source_policy: SourcePolicy,
    task_schema: Mapping[str, Any],
    source_snapshot_schema: Mapping[str, Any],
    evidence_schema: Mapping[str, Any],
    envelope_schema: Mapping[str, Any],
    proposal_schema: Mapping[str, Any],
    *,
    transport_factory: Callable[[Mapping[str, Any]], Any],
    now_factory: Callable[[], datetime] | None = None,
) -> Callable[[Mapping[str, Any]], dict[str, Any]]:
    """Build an injected, test-transport-only executor for a LangGraph source node.

    This S6-D implementation deliberately refuses live transports. The current
    standard GitHub runner has no audited provider-managed per-job egress
    firewall, so live_network_enabled, dns_pinning and egress_controls_audited
    must all remain false. S6-D produces proposals only; S7-B owns persistence.
    """
    validate_mission_context(mission_context)
    if not callable(transport_factory):
        raise SourceWorkerNodeError("an explicit transport factory is required")
    if (
        source_policy.live_network_enabled
        or source_policy.dns_pinning
        or source_policy.egress_controls_audited
    ):
        raise SourceWorkerNodeError("S6-D test executor refuses live-network policy")
    for schema in (
        task_schema,
        source_snapshot_schema,
        evidence_schema,
        envelope_schema,
        proposal_schema,
    ):
        if not isinstance(schema, Mapping):
            raise SourceWorkerNodeError("all five versioned schemas are required")
        Draft202012Validator.check_schema(dict(schema))

    allowed_hosts = tuple(sorted(source_policy.allowed_sources))

    def execute(task: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(task, Mapping):
            raise SourceWorkerNodeError("source task must be an object")
        transport = transport_factory(task)
        if getattr(transport, "is_test_transport", False) is not True:
            raise SourceWorkerNodeError("S6-D accepts synthetic test transports only")

        captured_at = now_factory() if now_factory is not None else None
        result = run_source_snapshot_task(
            task,
            mission_context,
            source_policy,
            task_schema,
            source_snapshot_schema,
            evidence_schema,
            transport=transport,
            now=captured_at,
        )

        raw_content = result.raw_content
        parameters = task.get("parameters", {})
        provenance = {
            "category_id": task.get("category_id"),
            "destination_id": task.get("destination_id"),
            "source_row_ref": parameters.get("source_row_ref"),
            "source_line": parameters.get("source_line"),
            "archive_sha256": parameters.get("archive_sha256"),
        }
        envelope = build_metadata_snapshot_envelope(
            result.snapshot,
            raw_content,
            allowed_hosts=allowed_hosts,
            snapshot_schema=source_snapshot_schema,
            envelope_schema=envelope_schema,
            provenance=provenance,
            http_status=result.status_code,
        )

        evidence = None
        if result.evidence_proposal is not None:
            evidence = dict(result.evidence_proposal)
            # Persist only the redacted, bounded excerpt from the envelope.
            evidence["evidence_excerpt"] = envelope.payload["excerpt"][:1500]
            Draft202012Validator(
                evidence_schema,
                format_checker=FormatChecker(),
            ).validate(evidence)
        if result.status == "COMPLETED" and evidence is None:
            raise SourceWorkerNodeError("completed source task has no evidence proposal")
        if result.status != "COMPLETED" and evidence is not None:
            raise SourceWorkerNodeError("non-completed source task cannot carry evidence")

        unsigned = {
            "schema_version": "1.0.0",
            "project_id": PROJECT_ID,
            "task_id": task["task_id"],
            "idempotency_key": task["idempotency_key"],
            "assigned_role": task["assigned_role"],
            "result_status": result.status,
            "snapshot_id": envelope.payload["snapshot_id"],
            "source_snapshot_envelope": envelope.payload,
            "source_snapshot_content_ref": envelope.content_ref,
            "source_snapshot_storage_path": envelope.storage_path,
            "source_snapshot_envelope_sha256": envelope.envelope_sha256,
            "evidence_proposal": evidence,
            "raw_body_persisted": False,
            "write_performed": False,
            "requires_s7_publisher": True,
            "reviewer_verdict": "PENDING",
            "commercial_gate_status": "UNKNOWN",
        }
        proposal = dict(unsigned)
        proposal["proposal_sha256"] = hashlib.sha256(
            canonical_json_bytes(unsigned)
        ).hexdigest()
        Draft202012Validator(
            proposal_schema,
            format_checker=FormatChecker(),
        ).validate(proposal)

        digest = envelope.envelope_sha256
        if (
            envelope.content_ref != f"sha256:{digest}"
            or envelope.storage_path != f"evidence/snapshots/sha256/{digest}.json"
        ):
            raise SourceWorkerNodeError("snapshot content reference/path mismatch")

        # Do not return or retain raw response bytes in the graph state.
        del raw_content
        del result
        return proposal

    return execute
