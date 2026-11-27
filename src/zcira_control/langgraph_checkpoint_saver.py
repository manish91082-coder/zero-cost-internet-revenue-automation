from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Iterator, Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, NamedTuple

from jsonschema import Draft202012Validator, FormatChecker, ValidationError

from .checkpoints import StaleCheckpoint
from .langgraph_adapter import SwarmGraphState
from .leases import lease_is_active, validate_lease
from .policy import PROJECT_ID, PolicyError, validate_git_sha
from .state_repository import StateIntegrityError, StateRepository, canonical_json, sha256_text

try:
    from langgraph.checkpoint.base import (
        BaseCheckpointSaver,
        CheckpointTuple,
        WRITES_IDX_MAP,
        get_checkpoint_metadata,
        writes_sort_key,
    )

    LANGGRAPH_CHECKPOINT_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised only in minimal environments
    LANGGRAPH_CHECKPOINT_AVAILABLE = False

    class BaseCheckpointSaver:  # type: ignore[no-redef]
        def __init__(self, *, serde: Any = None) -> None:
            self.serde = serde

    class CheckpointTuple(NamedTuple):  # type: ignore[no-redef]
        config: dict[str, Any]
        checkpoint: dict[str, Any]
        metadata: dict[str, Any]
        parent_config: dict[str, Any] | None = None
        pending_writes: list[tuple[str, str, Any]] | None = None

    WRITES_IDX_MAP = {
        "__error__": -1,
        "__scheduled__": -2,
        "__interrupt__": -3,
        "__resume__": -4,
    }

    def get_checkpoint_metadata(config: Mapping[str, Any], metadata: Mapping[str, Any]) -> dict[str, Any]:
        return dict(metadata)

    def writes_sort_key(task_path: str, task_id: str = "", idx: int = 0) -> tuple[str, str, int]:
        return (task_path, task_id, idx)


RUN_ID_RE = re.compile(r"^zcira-run-[a-z0-9][a-z0-9-]{2,80}$")
CHECKPOINT_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
ALLOWED_CHANNELS = frozenset(SwarmGraphState.__annotations__)
LANGGRAPH_INTERNAL_CHANNELS = frozenset({"__start__"})
CHECKPOINT_CHANNELS = ALLOWED_CHANNELS | LANGGRAPH_INTERNAL_CHANNELS
SPECIAL_CHANNELS = frozenset(WRITES_IDX_MAP)
NODE_NAME_RE = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")
MAX_GRAPH_NODES = 32
ROUTE_CHANNEL_PREFIX = "branch:to:"
TERMINAL_ROUTE_CHANNEL = "branch:to:__end__"
CHECKPOINT_KIND = "langgraph_checkpoint"
PENDING_WRITES_KIND = "langgraph_pending_writes"
FORBIDDEN_KEY_EXACT = {
    "password", "email", "phone", "phonenumber", "address", "otp",
    "recoverycode", "rawbody", "body", "sourcebody", "pagebody",
    "responsebody", "rawhtml", "htmlbody", "fulldocument", "fullpage",
    "contentbytes", "binarypayload", "customerdata", "personaldata",
}
FORBIDDEN_KEY_PARTS = (
    "password", "secret", "token", "credential", "privatekey",
    "apikey", "authorization", "cookie", "recoverycode",
)


class CheckpointContractError(RuntimeError):
    """A checkpoint violates the ZCIRA persistence, scope or safety contract."""


class CheckpointAsyncUnsupported(NotImplementedError):
    """Asynchronous graph execution is intentionally disabled in ZCIRA S5."""


class LangGraphCheckpointUnavailable(RuntimeError):
    """The pinned optional LangGraph checkpoint runtime is not installed."""


def _reject_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON constant is forbidden: {value}")


def _no_duplicate_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON object key is forbidden: {key}")
        result[key] = value
    return result


def _validate_json_native(value: Any, path: str = "$", depth: int = 0) -> None:
    if depth > 32:
        raise CheckpointContractError(f"JSON nesting exceeds the S5 limit at {path}")
    if value is None or isinstance(value, (bool, str, int)):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise CheckpointContractError(f"non-finite number is forbidden at {path}")
        return
    if isinstance(value, list):
        if len(value) > 4096:
            raise CheckpointContractError(f"JSON array exceeds the S5 item limit at {path}")
        for index, item in enumerate(value):
            _validate_json_native(item, f"{path}[{index}]", depth + 1)
        return
    if isinstance(value, dict):
        if len(value) > 4096:
            raise CheckpointContractError(f"JSON object exceeds the S5 item limit at {path}")
        for key, item in value.items():
            if not isinstance(key, str) or not key or len(key) > 256:
                raise CheckpointContractError(f"JSON object keys must be bounded non-empty strings at {path}")
            normalized = re.sub(r"[^a-z0-9]", "", key.casefold())
            if normalized in FORBIDDEN_KEY_EXACT or any(part in normalized for part in FORBIDDEN_KEY_PARTS):
                raise CheckpointContractError(f"secret, personal-data or raw-source field is forbidden at {path}.{key}")
            _validate_json_native(item, f"{path}.{key}", depth + 1)
        return
    raise CheckpointContractError(f"non-JSON Python value {type(value).__name__} is forbidden at {path}")


def _canonical_json(value: Any) -> str:
    _validate_json_native(value)
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _strict_clone(value: Any) -> Any:
    return json.loads(
        _canonical_json(value),
        parse_constant=_reject_constant,
        object_pairs_hook=_no_duplicate_pairs,
    )


class StrictJsonSerializer:
    """LangGraph serializer that supports JSON-native values only; no pickle or object reconstruction."""

    def dumps_typed(self, obj: Any) -> tuple[str, bytes]:
        return ("json", _canonical_json(obj).encode("utf-8"))

    def loads_typed(self, value: tuple[str, bytes]) -> Any:
        if not isinstance(value, tuple) or len(value) != 2 or value[0] != "json" or not isinstance(value[1], bytes):
            raise CheckpointContractError("only the canonical JSON serializer type is accepted")
        try:
            return json.loads(
                value[1].decode("utf-8", errors="strict"),
                parse_constant=_reject_constant,
                object_pairs_hook=_no_duplicate_pairs,
            )
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
            raise CheckpointContractError("stored checkpoint bytes are not strict UTF-8 JSON") from None


class LangGraphCheckpointSaver(BaseCheckpointSaver):
    """Synchronous JSON-only LangGraph saver backed by the canonical Git StateRepository.

    The caller must supply an already acquired evidence_publisher lease. Each
    write-through operation commits under that same lease and updates the exact
    commit SHA required by the next transition. Runner-local files are never used
    for durability.
    """

    def __init__(
        self,
        repository: StateRepository,
        lease_id: str,
        lease_commit_sha: str,
        run_id: str,
        *,
        now_fn: Any | None = None,
        schema_dir: str | Path | None = None,
        policy_path: str | Path | None = None,
    ) -> None:
        if not LANGGRAPH_CHECKPOINT_AVAILABLE:
            raise LangGraphCheckpointUnavailable("install the pinned langgraph==1.2.22 dependency")
        if not isinstance(repository, StateRepository):
            raise CheckpointContractError("a canonical StateRepository instance is required")
        if not isinstance(run_id, str) or RUN_ID_RE.fullmatch(run_id) is None:
            raise CheckpointContractError("thread_id must be the exact ZCIRA run_id")
        validate_git_sha(lease_commit_sha)
        if not isinstance(lease_id, str) or not lease_id.startswith("lease-"):
            raise CheckpointContractError("an acquired canonical repository writer lease is required")

        self.repository = repository
        self.lease_id = lease_id
        self.lease_commit_sha = lease_commit_sha
        self.run_id = run_id
        self.now_fn = now_fn or (lambda: datetime.now(timezone.utc))
        self.allowed_node_names: frozenset[str] | None = None

        repo_root = Path(__file__).resolve().parents[2]
        selected_schema_dir = Path(schema_dir) if schema_dir is not None else repo_root / "schemas" / "v1"
        selected_policy_path = Path(policy_path) if policy_path is not None else repo_root / "config" / "s5_checkpoint_policy.v1.json"
        try:
            self.policy = json.loads(selected_policy_path.read_text(encoding="utf-8"))
            checkpoint_schema = json.loads((selected_schema_dir / "langgraph_checkpoint.schema.json").read_text(encoding="utf-8"))
            pending_schema = json.loads((selected_schema_dir / "langgraph_pending_writes.schema.json").read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            raise CheckpointContractError("versioned S5 policy and checkpoint schemas are required") from None
        if self.policy.get("project_id") != PROJECT_ID or self.policy.get("schema_version") != "1.0.0":
            raise CheckpointContractError("S5 policy scope or version mismatch")

        Draft202012Validator.check_schema(checkpoint_schema)
        Draft202012Validator.check_schema(pending_schema)
        self.validators = {
            CHECKPOINT_KIND: Draft202012Validator(checkpoint_schema, format_checker=FormatChecker()),
            PENDING_WRITES_KIND: Draft202012Validator(pending_schema, format_checker=FormatChecker()),
        }
        bounds = self.policy.get("bounds", {})
        self.max_checkpoints = int(bounds.get("max_checkpoints_per_run", 16))
        self.max_checkpoint_bytes = int(bounds.get("max_checkpoint_bytes", 262144))
        self.max_pending_batch_bytes = int(bounds.get("max_pending_write_batch_bytes", 65536))
        self.max_total_bytes = int(bounds.get("max_total_checkpoint_bytes_per_run", 4194304))
        self.max_pending_records = int(bounds.get("max_pending_write_records_per_checkpoint", 64))
        self.lease_ttl_seconds = int(bounds.get("writer_lease_ttl_seconds", 900))
        if (
            self.max_checkpoints != 16
            or self.max_checkpoint_bytes != 262144
            or self.max_pending_batch_bytes != 65536
            or self.max_total_bytes != 4194304
            or self.max_pending_records != 64
            or not 30 <= self.lease_ttl_seconds <= 3600
        ):
            raise CheckpointContractError("S5 bounds differ from the locked checkpoint policy")

        prior_validator = repository.object_validator

        def composed_validator(kind: str, payload: Mapping[str, Any]) -> None:
            if kind in self.validators:
                self._validate_object(kind, payload)
            elif prior_validator is not None:
                prior_validator(kind, payload)
            else:
                raise CheckpointContractError(f"no validator is registered for state object kind {kind}")

        repository.object_validator = composed_validator
        super().__init__(serde=StrictJsonSerializer())
        self._assert_lease()

    def bind_graph_nodes(self, node_names: Sequence[str]) -> None:
        """Bind routing-channel permissions to the exact compiled graph node set."""
        if not isinstance(node_names, Sequence) or isinstance(node_names, (str, bytes)):
            raise CheckpointContractError("compiled graph node names must be a bounded sequence")
        if not 1 <= len(node_names) <= MAX_GRAPH_NODES:
            raise CheckpointContractError("compiled graph must contain between 1 and 32 nodes")
        if any(not isinstance(name, str) or NODE_NAME_RE.fullmatch(name) is None for name in node_names):
            raise CheckpointContractError("compiled graph contains an invalid node name")
        candidate = frozenset(node_names)
        if len(candidate) != len(node_names):
            raise CheckpointContractError("compiled graph node names must be unique")
        if self.allowed_node_names is not None and self.allowed_node_names != candidate:
            raise CheckpointContractError("checkpoint saver cannot be rebound to a different graph node set")
        self.allowed_node_names = candidate

    def _is_allowed_pending_channel(self, channel: Any) -> bool:
        if not isinstance(channel, str):
            return False
        if channel in CHECKPOINT_CHANNELS or channel in SPECIAL_CHANNELS:
            return True
        if channel == TERMINAL_ROUTE_CHANNEL:
            return True
        if not channel.startswith(ROUTE_CHANNEL_PREFIX) or self.allowed_node_names is None:
            return False
        return channel[len(ROUTE_CHANNEL_PREFIX):] in self.allowed_node_names

    def _now(self) -> datetime:
        value = self.now_fn()
        if not isinstance(value, datetime) or value.tzinfo is None:
            raise CheckpointContractError("checkpoint clock must return a timezone-aware datetime")
        return value.astimezone(timezone.utc)

    def _assert_lease(self) -> tuple[str, dict[str, Any], datetime]:
        now = self._now()
        head, manifest = self.repository.load()
        if head != self.lease_commit_sha:
            raise StaleCheckpoint("checkpoint saver lease head is stale; re-fetch before continuing")
        if manifest["kill_switch"]:
            raise CheckpointContractError("kill switch blocks checkpoint access")
        if manifest["active_writer_lease_id"] != self.lease_id:
            raise CheckpointContractError("checkpoint saver does not hold the active canonical writer lease")
        lease = self.repository.load_object("resource_lease", self.lease_id, head, manifest)
        validate_lease(lease, now)
        if not lease_is_active(lease, now):
            raise CheckpointContractError("checkpoint saver writer lease is expired")
        return head, manifest, now

    def _validate_object(self, kind: str, payload: Mapping[str, Any]) -> None:
        if kind not in self.validators:
            raise CheckpointContractError("unsupported LangGraph state object kind")
        _validate_json_native(dict(payload))
        try:
            self.validators[kind].validate(dict(payload))
        except ValidationError as exc:
            raise CheckpointContractError(f"{kind} schema validation failed: {exc.message}") from None
        if payload.get("run_id") != self.run_id or payload.get("thread_id") != self.run_id:
            raise CheckpointContractError("checkpoint run_id and thread_id must equal the saver run_id")
        if payload.get("checkpoint_ns") != "":
            raise CheckpointContractError("only the empty checkpoint namespace is allowed")
        if kind == CHECKPOINT_KIND:
            checkpoint = payload.get("checkpoint")
            if not isinstance(checkpoint, Mapping) or checkpoint.get("id") != payload.get("checkpoint_id"):
                raise CheckpointContractError("checkpoint envelope ID must equal the LangGraph checkpoint ID")
            channels = checkpoint.get("channel_values")
            if not isinstance(channels, Mapping) or not set(channels).issubset(CHECKPOINT_CHANNELS):
                raise CheckpointContractError("checkpoint contains a channel outside SwarmGraphState")
        else:
            identity = {
                "project_id": PROJECT_ID,
                "run_id": payload.get("run_id"),
                "checkpoint_id": payload.get("checkpoint_id"),
                "task_id": payload.get("task_id"),
                "task_path": payload.get("task_path"),
            }
            expected_id = sha256_text(_canonical_json(identity))
            if payload.get("pending_write_id") != expected_id:
                raise CheckpointContractError("pending-write identity digest mismatch")
            for index, record in enumerate(payload.get("writes", [])):
                channel = record["channel"]
                if not self._is_allowed_pending_channel(channel):
                    safe_channel = channel[:128] if isinstance(channel, str) else type(channel).__name__
                    raise CheckpointContractError(f"pending write channel {safe_channel!r} is outside the S5 graph/state allowlist")
                if record["index"] != WRITES_IDX_MAP.get(channel, index):
                    raise CheckpointContractError("pending write index does not match LangGraph's reserved-index contract")

    def _config_parts(
        self,
        config: Mapping[str, Any],
        *,
        require_checkpoint_id: bool = False,
    ) -> tuple[str, str | None]:
        if not isinstance(config, Mapping) or not isinstance(config.get("configurable"), Mapping):
            raise CheckpointContractError("LangGraph config must contain a configurable object")
        configurable = config["configurable"]
        thread_id = configurable.get("thread_id")
        namespace = configurable.get("checkpoint_ns", "")
        checkpoint_id = configurable.get("checkpoint_id")
        if thread_id != self.run_id or namespace != "":
            raise CheckpointContractError("LangGraph thread must be bound to this run and the empty namespace")
        if checkpoint_id is not None and (not isinstance(checkpoint_id, str) or CHECKPOINT_ID_RE.fullmatch(checkpoint_id) is None):
            raise CheckpointContractError("checkpoint_id is invalid")
        if require_checkpoint_id and checkpoint_id is None:
            raise CheckpointContractError("this operation requires an existing checkpoint_id")
        return thread_id, checkpoint_id

    def _load_objects(
        self,
        kind: str,
        head: str,
        manifest: Mapping[str, Any],
    ) -> list[dict[str, Any]]:
        values: list[dict[str, Any]] = []
        for reference in manifest["objects"]:
            if reference["kind"] != kind:
                continue
            payload = self.repository.load_object(kind, reference["object_id"], head, manifest)
            self._validate_object(kind, payload)
            if payload["run_id"] == self.run_id:
                values.append(payload)
        return values

    def _run_objects(
        self,
        head: str,
        manifest: Mapping[str, Any],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        return (
            self._load_objects(CHECKPOINT_KIND, head, manifest),
            self._load_objects(PENDING_WRITES_KIND, head, manifest),
        )

    def _total_run_bytes(
        self,
        checkpoints: Sequence[Mapping[str, Any]],
        pending: Sequence[Mapping[str, Any]],
    ) -> int:
        return sum(len(_canonical_json(dict(item)).encode("utf-8")) for item in (*checkpoints, *pending))

    def _commit_object(self, kind: str, object_id: str, payload: Mapping[str, Any], message: str) -> None:
        head, _, now = self._assert_lease()
        commit_sha = self.repository.commit_under_lease(
            self.lease_id,
            head,
            [(kind, object_id, payload)],
            now,
            message,
            ttl_seconds=self.lease_ttl_seconds,
        )
        self.lease_commit_sha = commit_sha

    def put(
        self,
        config: Mapping[str, Any],
        checkpoint: Mapping[str, Any],
        metadata: Mapping[str, Any],
        new_versions: Mapping[str, Any],
    ) -> dict[str, Any]:
        _, parent_id = self._config_parts(config)
        checkpoint_value = _strict_clone(dict(checkpoint))
        checkpoint_id = checkpoint_value.get("id")
        if not isinstance(checkpoint_id, str) or CHECKPOINT_ID_RE.fullmatch(checkpoint_id) is None:
            raise CheckpointContractError("LangGraph checkpoint ID is invalid")
        if parent_id == checkpoint_id:
            raise CheckpointContractError("checkpoint cannot be its own parent")
        metadata_value = _strict_clone(dict(get_checkpoint_metadata(config, dict(metadata))))
        versions_value = _strict_clone(dict(new_versions))
        checkpoint_ts = checkpoint_value.get("ts")
        if not isinstance(checkpoint_ts, str):
            raise CheckpointContractError("checkpoint timestamp is required")

        head, manifest, _ = self._assert_lease()
        checkpoints, pending = self._run_objects(head, manifest)
        by_id = {item["checkpoint_id"]: item for item in checkpoints}
        if parent_id is not None and parent_id not in by_id:
            raise CheckpointContractError("parent checkpoint is not present in this run")
        existing = by_id.get(checkpoint_id)
        if existing is not None:
            candidate = {
                "schema_version": "1.0.0",
                "project_id": PROJECT_ID,
                "run_id": self.run_id,
                "thread_id": self.run_id,
                "checkpoint_ns": "",
                "checkpoint_id": checkpoint_id,
                "parent_checkpoint_id": parent_id,
                "checkpoint_index": existing["checkpoint_index"],
                "created_at": checkpoint_ts,
                "checkpoint": checkpoint_value,
                "metadata": metadata_value,
                "new_versions": versions_value,
            }
            self._validate_object(CHECKPOINT_KIND, candidate)
            if _canonical_json(candidate) != _canonical_json(existing):
                raise CheckpointContractError("same checkpoint identity was reused with different content")
            return {"configurable": {"thread_id": self.run_id, "checkpoint_ns": "", "checkpoint_id": checkpoint_id}}

        checkpoint_index = max((item["checkpoint_index"] for item in checkpoints), default=0) + 1
        if checkpoint_index > self.max_checkpoints:
            raise CheckpointContractError("maximum checkpoints per run exceeded")
        payload = {
            "schema_version": "1.0.0",
            "project_id": PROJECT_ID,
            "run_id": self.run_id,
            "thread_id": self.run_id,
            "checkpoint_ns": "",
            "checkpoint_id": checkpoint_id,
            "parent_checkpoint_id": parent_id,
            "checkpoint_index": checkpoint_index,
            "created_at": checkpoint_ts,
            "checkpoint": checkpoint_value,
            "metadata": metadata_value,
            "new_versions": versions_value,
        }
        self._validate_object(CHECKPOINT_KIND, payload)
        size = len(_canonical_json(payload).encode("utf-8"))
        if size > self.max_checkpoint_bytes:
            raise CheckpointContractError("checkpoint exceeds the 256 KiB limit")
        if self._total_run_bytes(checkpoints, pending) + size > self.max_total_bytes:
            raise CheckpointContractError("run checkpoint ledger exceeds the 4 MiB limit")
        self._commit_object(CHECKPOINT_KIND, checkpoint_id, payload, "zcira: persist LangGraph checkpoint")
        return {"configurable": {"thread_id": self.run_id, "checkpoint_ns": "", "checkpoint_id": checkpoint_id}}

    def put_writes(
        self,
        config: Mapping[str, Any],
        writes: Sequence[tuple[str, Any]],
        task_id: str,
        task_path: str = "",
    ) -> None:
        _, checkpoint_id = self._config_parts(config, require_checkpoint_id=True)
        if not isinstance(task_id, str) or not task_id or len(task_id) > 128:
            raise CheckpointContractError("pending-write task_id must be non-empty and bounded")
        if not isinstance(task_path, str) or len(task_path) > 512:
            raise CheckpointContractError("pending-write task_path must be bounded text")
        if not isinstance(writes, Sequence) or isinstance(writes, (str, bytes)):
            raise CheckpointContractError("pending writes must be a bounded sequence")
        if len(writes) == 0:
            return
        if len(writes) > self.max_pending_records:
            raise CheckpointContractError("pending-write batch exceeds 64 records")

        records: list[dict[str, Any]] = []
        for index, item in enumerate(writes):
            if not isinstance(item, (tuple, list)) or len(item) != 2:
                raise CheckpointContractError("each pending write must be a (channel, value) pair")
            channel, value = item
            if not self._is_allowed_pending_channel(channel):
                safe_channel = channel[:128] if isinstance(channel, str) else type(channel).__name__
                raise CheckpointContractError(f"pending write channel {safe_channel!r} is outside the S5 graph/state allowlist")
            write_index = WRITES_IDX_MAP.get(channel, index)
            if write_index < -4 or write_index > 63:
                raise CheckpointContractError("pending write index is outside the bounded range")
            records.append({"channel": channel, "index": write_index, "value": _strict_clone(value)})

        identity = {
            "project_id": PROJECT_ID,
            "run_id": self.run_id,
            "checkpoint_id": checkpoint_id,
            "task_id": task_id,
            "task_path": task_path,
        }
        pending_id = sha256_text(_canonical_json(identity))
        payload = {
            "schema_version": "1.0.0",
            "project_id": PROJECT_ID,
            "run_id": self.run_id,
            "thread_id": self.run_id,
            "checkpoint_ns": "",
            "checkpoint_id": checkpoint_id,
            "pending_write_id": pending_id,
            "task_id": task_id,
            "task_path": task_path,
            "created_at": self._now().isoformat().replace("+00:00", "Z"),
            "writes": records,
        }
        self._validate_object(PENDING_WRITES_KIND, payload)
        batch_size = len(_canonical_json(payload).encode("utf-8"))
        if batch_size > self.max_pending_batch_bytes:
            raise CheckpointContractError("pending-write batch exceeds the 64 KiB limit")

        head, manifest, _ = self._assert_lease()
        checkpoints, pending = self._run_objects(head, manifest)
        if checkpoint_id not in {item["checkpoint_id"] for item in checkpoints}:
            raise CheckpointContractError("pending writes reference a checkpoint outside this run")
        for existing in pending:
            if existing["checkpoint_id"] != checkpoint_id:
                continue
            if existing["task_id"] == task_id and existing["task_path"] != task_path:
                raise CheckpointContractError("same task_id cannot be rebound to another task_path")
            if existing["pending_write_id"] == pending_id:
                if _canonical_json(existing) != _canonical_json(payload):
                    raise CheckpointContractError("same pending-write identity was reused with different content")
                return
        existing_count = sum(
            len(item["writes"]) for item in pending if item["checkpoint_id"] == checkpoint_id
        )
        if existing_count + len(records) > self.max_pending_records:
            raise CheckpointContractError("maximum pending-write records per checkpoint exceeded")
        if self._total_run_bytes(checkpoints, pending) + batch_size > self.max_total_bytes:
            raise CheckpointContractError("run checkpoint ledger exceeds the 4 MiB limit")
        self._commit_object(PENDING_WRITES_KIND, pending_id, payload, "zcira: persist LangGraph pending writes")

    def _tuple_for(
        self,
        checkpoint_payload: Mapping[str, Any],
        pending_payloads: Sequence[Mapping[str, Any]],
    ) -> CheckpointTuple:
        checkpoint_id = checkpoint_payload["checkpoint_id"]
        writes: list[tuple[tuple[str, str, int], tuple[str, str, Any]]] = []
        for batch in pending_payloads:
            if batch["checkpoint_id"] != checkpoint_id:
                continue
            for record in batch["writes"]:
                key = writes_sort_key(batch["task_path"], batch["task_id"], record["index"])
                value = (batch["task_id"], record["channel"], record["value"])
                writes.append((key, value))
        writes.sort(key=lambda item: item[0])
        config = {"configurable": {"thread_id": self.run_id, "checkpoint_ns": "", "checkpoint_id": checkpoint_id}}
        parent_id = checkpoint_payload["parent_checkpoint_id"]
        parent_config = (
            {"configurable": {"thread_id": self.run_id, "checkpoint_ns": "", "checkpoint_id": parent_id}}
            if parent_id is not None else None
        )
        return CheckpointTuple(
            config=config,
            checkpoint=dict(checkpoint_payload["checkpoint"]),
            metadata=dict(checkpoint_payload["metadata"]),
            parent_config=parent_config,
            pending_writes=[item[1] for item in writes],
        )

    def get_tuple(self, config: Mapping[str, Any]) -> CheckpointTuple | None:
        _, checkpoint_id = self._config_parts(config)
        head, manifest, _ = self._assert_lease()
        checkpoints, pending = self._run_objects(head, manifest)
        if checkpoint_id is None:
            selected = max(checkpoints, key=lambda item: item["checkpoint_index"], default=None)
        else:
            selected = next((item for item in checkpoints if item["checkpoint_id"] == checkpoint_id), None)
        if selected is None:
            return None
        if selected["parent_checkpoint_id"] is not None and selected["parent_checkpoint_id"] not in {
            item["checkpoint_id"] for item in checkpoints
        }:
            raise StateIntegrityError("checkpoint parent reference is missing from the canonical run ledger")
        return self._tuple_for(selected, pending)

    def list(
        self,
        config: Mapping[str, Any] | None,
        *,
        filter: dict[str, Any] | None = None,
        before: Mapping[str, Any] | None = None,
        limit: int | None = None,
    ) -> Iterator[CheckpointTuple]:
        if config is None:
            raise CheckpointContractError("global checkpoint listing is disabled; an exact run thread is required")
        self._config_parts(config)
        if filter is not None and not isinstance(filter, Mapping):
            raise CheckpointContractError("checkpoint metadata filter must be an object")
        if limit is None:
            limit = self.max_checkpoints
        if not isinstance(limit, int) or isinstance(limit, bool) or limit < 0 or limit > self.max_checkpoints:
            raise CheckpointContractError("checkpoint list limit must be between zero and the S5 maximum")
        head, manifest, _ = self._assert_lease()
        checkpoints, pending = self._run_objects(head, manifest)
        before_index: int | None = None
        if before is not None:
            _, before_id = self._config_parts(before, require_checkpoint_id=True)
            before_item = next((item for item in checkpoints if item["checkpoint_id"] == before_id), None)
            if before_item is None:
                raise CheckpointContractError("before checkpoint is not present in this run")
            before_index = before_item["checkpoint_index"]
        selected = sorted(checkpoints, key=lambda item: item["checkpoint_index"], reverse=True)
        emitted = 0
        for item in selected:
            if before_index is not None and item["checkpoint_index"] >= before_index:
                continue
            if filter and any(item["metadata"].get(key) != value for key, value in filter.items()):
                continue
            yield self._tuple_for(item, pending)
            emitted += 1
            if emitted >= limit:
                break

    def delete_thread(self, thread_id: str) -> None:
        raise CheckpointContractError("delete_thread is disabled; canonical Git checkpoint history is append-only")

    def delete_for_runs(self, run_ids: Sequence[str]) -> None:
        raise CheckpointContractError("delete_for_runs is disabled; canonical Git checkpoint history is append-only")

    def copy_thread(self, source_thread_id: str, target_thread_id: str) -> None:
        raise CheckpointContractError("copy_thread is disabled; cross-thread state copying is not approved")

    def prune(self, threads: Sequence[str]) -> None:
        raise CheckpointContractError("prune is disabled; canonical Git checkpoint history is append-only")

    async def aget_tuple(self, config: Mapping[str, Any]) -> CheckpointTuple | None:
        raise CheckpointAsyncUnsupported("async graph execution is disabled by the S5 policy")

    async def alist(self, config: Mapping[str, Any] | None, **kwargs: Any) -> Any:
        raise CheckpointAsyncUnsupported("async graph execution is disabled by the S5 policy")

    async def aput(self, config: Mapping[str, Any], checkpoint: Mapping[str, Any], metadata: Mapping[str, Any], new_versions: Mapping[str, Any]) -> Any:
        raise CheckpointAsyncUnsupported("async graph execution is disabled by the S5 policy")

    async def aput_writes(self, config: Mapping[str, Any], writes: Sequence[tuple[str, Any]], task_id: str, task_path: str = "") -> None:
        raise CheckpointAsyncUnsupported("async graph execution is disabled by the S5 policy")

    async def adelete_thread(self, thread_id: str) -> None:
        raise CheckpointAsyncUnsupported("async graph execution is disabled by the S5 policy")

    async def adelete_for_runs(self, run_ids: Sequence[str]) -> None:
        raise CheckpointAsyncUnsupported("async graph execution is disabled by the S5 policy")

    async def acopy_thread(self, source_thread_id: str, target_thread_id: str) -> None:
        raise CheckpointAsyncUnsupported("async graph execution is disabled by the S5 policy")

    async def aprune(self, threads: Sequence[str]) -> None:
        raise CheckpointAsyncUnsupported("async graph execution is disabled by the S5 policy")
