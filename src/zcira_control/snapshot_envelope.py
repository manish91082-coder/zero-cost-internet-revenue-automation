from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass
from typing import Any, Iterable, Mapping
from urllib.parse import urlsplit, urlunsplit

from jsonschema import Draft202012Validator, FormatChecker


PROJECT_ID = "ZCIRA-2026-11-13"
CANONICALIZATION = "ZCIRA_JSON_CANONICAL_V1"
MAX_RAW_BODY_BYTES = 1_000_000
MAX_EXCERPT_CHARS = 2_000
STORAGE_PREFIX = "evidence/snapshots/sha256/"

_EMAIL_RE = re.compile(r"(?i)(?<![A-Z0-9._%+-])[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}(?![A-Z0-9.-])")
_INDIA_PHONE_RE = re.compile(r"(?<!\d)(?:\+?91[\s().-]?)?[6-9]\d{9}(?!\d)")
_INTL_PHONE_RE = re.compile(r"(?<!\w)\+\d(?:[\s().-]*\d){7,14}(?!\w)")
_SECRET_ASSIGNMENT_RE = re.compile(
    r"(?i)\b(?:bearer|api[_ -]?key|access[_ -]?token|refresh[_ -]?token|secret|password)\b"
    r"\s*[:=]?\s*[\"']?[A-Za-z0-9._~+/=-]{8,}"
)
_KNOWN_TOKEN_RE = re.compile(
    r"(?i)\b(?:gh[pousr]_[A-Za-z0-9_]{20,}|sk-[A-Za-z0-9_-]{20,}|AKIA[0-9A-Z]{16})\b"
)
_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_SPACE_RE = re.compile(r"\s+")


class SnapshotEnvelopeError(ValueError):
    """A source snapshot cannot be safely canonicalized or verified."""


@dataclass(frozen=True)
class SnapshotEnvelope:
    payload: dict[str, Any]
    canonical_bytes: bytes
    envelope_sha256: str
    content_ref: str
    storage_path: str


def canonical_json_bytes(value: Mapping[str, Any]) -> bytes:
    """Return the single canonical UTF-8 JSON representation used by ZCIRA."""
    if not isinstance(value, Mapping):
        raise SnapshotEnvelopeError("canonical JSON input must be an object")
    try:
        return json.dumps(
            dict(value),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeEncodeError):
        raise SnapshotEnvelopeError("canonical JSON serialization failed") from None


def _clean_text(value: Any, limit: int) -> str:
    if not isinstance(value, str):
        raise SnapshotEnvelopeError("persisted text fields must be strings")
    text = unicodedata.normalize("NFC", value)
    text = _CONTROL_RE.sub(" ", text)
    text = _EMAIL_RE.sub("[REDACTED_EMAIL]", text)
    text = _INDIA_PHONE_RE.sub("[REDACTED_PHONE]", text)
    text = _INTL_PHONE_RE.sub("[REDACTED_PHONE]", text)
    text = _SECRET_ASSIGNMENT_RE.sub("[REDACTED_SECRET]", text)
    text = _KNOWN_TOKEN_RE.sub("[REDACTED_TOKEN]", text)
    text = _SPACE_RE.sub(" ", text).strip()
    return text[:limit]


def _safe_source_url(raw_url: Any, source_domain: Any, allowed_hosts: set[str]) -> tuple[str, str]:
    if not isinstance(raw_url, str) or not raw_url or any(ord(ch) < 32 for ch in raw_url):
        raise SnapshotEnvelopeError("source URL is invalid")
    try:
        parsed = urlsplit(raw_url)
        port = parsed.port
    except ValueError:
        raise SnapshotEnvelopeError("source URL authority is invalid") from None
    host = (parsed.hostname or "").lower()
    domain = source_domain.lower() if isinstance(source_domain, str) else ""
    if parsed.scheme.lower() != "https":
        raise SnapshotEnvelopeError("only HTTPS source URLs may be persisted")
    if parsed.username is not None or parsed.password is not None:
        raise SnapshotEnvelopeError("URL credentials are prohibited")
    if port not in (None, 443):
        raise SnapshotEnvelopeError("only the standard HTTPS port may be persisted")
    if not host or host != domain or host not in allowed_hosts:
        raise SnapshotEnvelopeError("source URL host must exactly match the approved source domain")
    if "*" in host or host.endswith(".") or ".." in host:
        raise SnapshotEnvelopeError("wildcard or malformed source hostname")
    # Query and fragment values are deliberately omitted from public metadata.
    safe_url = urlunsplit(("https", host, parsed.path or "/", "", ""))
    return safe_url, hashlib.sha256(raw_url.encode("utf-8")).hexdigest()


def _provenance(value: Mapping[str, Any] | None) -> dict[str, Any]:
    value = {} if value is None else value
    if not isinstance(value, Mapping):
        raise SnapshotEnvelopeError("provenance must be an object")
    allowed = {"category_id", "destination_id", "source_row_ref", "source_line", "archive_sha256"}
    if set(value) - allowed:
        raise SnapshotEnvelopeError("provenance contains unknown fields")
    category_id = value.get("category_id")
    if category_id is not None and (
        isinstance(category_id, bool) or not isinstance(category_id, int) or not 1 <= category_id <= 245
    ):
        raise SnapshotEnvelopeError("category_id must be null or an integer from 1 to 245")
    destination_id = value.get("destination_id")
    source_row_ref = value.get("source_row_ref")
    for field_name, field_value in (("destination_id", destination_id), ("source_row_ref", source_row_ref)):
        if field_value is not None and (
            not isinstance(field_value, str) or not field_value.strip() or len(field_value) > 512
        ):
            raise SnapshotEnvelopeError(f"{field_name} must be null or a non-empty string up to 512 characters")
    source_line = value.get("source_line")
    if source_line is not None and (
        isinstance(source_line, bool) or not isinstance(source_line, int) or source_line < 1
    ):
        raise SnapshotEnvelopeError("source_line must be null or a positive integer")
    archive_sha256 = value.get("archive_sha256")
    if archive_sha256 is not None and (
        not isinstance(archive_sha256, str) or not re.fullmatch(r"[a-f0-9]{64}", archive_sha256)
    ):
        raise SnapshotEnvelopeError("archive_sha256 must be null or a lowercase SHA-256 digest")
    return {
        "category_id": category_id,
        "destination_id": destination_id,
        "source_row_ref": source_row_ref,
        "source_line": source_line,
        "archive_sha256": archive_sha256,
    }


def build_metadata_snapshot_envelope(
    snapshot: Mapping[str, Any],
    raw_content: bytes | None,
    *,
    allowed_hosts: Iterable[str],
    snapshot_schema: Mapping[str, Any],
    envelope_schema: Mapping[str, Any],
    provenance: Mapping[str, Any] | None = None,
    http_status: int | None = None,
    max_raw_body_bytes: int = MAX_RAW_BODY_BYTES,
    max_excerpt_chars: int = MAX_EXCERPT_CHARS,
) -> SnapshotEnvelope:
    """Build a metadata-only immutable envelope; never return or persist page bytes."""
    if not isinstance(snapshot, Mapping):
        raise SnapshotEnvelopeError("source snapshot must be an object")
    if not isinstance(snapshot_schema, Mapping) or not isinstance(envelope_schema, Mapping):
        raise SnapshotEnvelopeError("both JSON Schemas are required")
    try:
        Draft202012Validator.check_schema(dict(snapshot_schema))
        Draft202012Validator.check_schema(dict(envelope_schema))
        Draft202012Validator(dict(snapshot_schema), format_checker=FormatChecker()).validate(dict(snapshot))
    except Exception as exc:
        raise SnapshotEnvelopeError(f"source snapshot schema validation failed: {type(exc).__name__}") from None

    if isinstance(max_raw_body_bytes, bool) or not isinstance(max_raw_body_bytes, int) or not 1 <= max_raw_body_bytes <= MAX_RAW_BODY_BYTES:
        raise SnapshotEnvelopeError("max_raw_body_bytes is outside the hard limit")
    if isinstance(max_excerpt_chars, bool) or not isinstance(max_excerpt_chars, int) or not 1 <= max_excerpt_chars <= MAX_EXCERPT_CHARS:
        raise SnapshotEnvelopeError("max_excerpt_chars is outside the hard limit")

    hosts = set()
    for host in allowed_hosts:
        if not isinstance(host, str) or not host or host != host.lower() or "*" in host or host.endswith("."):
            raise SnapshotEnvelopeError("allowed_hosts must contain exact lowercase hostnames")
        hosts.add(host)
    if not hosts:
        raise SnapshotEnvelopeError("allowed_hosts must not be empty")

    source_url, source_url_sha256 = _safe_source_url(
        snapshot.get("source_url"), snapshot.get("source_domain"), hosts
    )
    if raw_content is not None and not isinstance(raw_content, bytes):
        raise SnapshotEnvelopeError("raw_content must be bytes or None")
    body = b"" if raw_content is None else raw_content
    if len(body) > max_raw_body_bytes:
        raise SnapshotEnvelopeError("raw source body exceeds the configured hard limit")
    if snapshot.get("fetch_status") == "CAPTURED" and raw_content is None:
        raise SnapshotEnvelopeError("CAPTURED snapshots require ephemeral raw bytes for digest verification")
    raw_body_sha256 = hashlib.sha256(body).hexdigest()
    if snapshot.get("content_sha256") != raw_body_sha256:
        raise SnapshotEnvelopeError("raw body SHA-256 does not match the source snapshot")

    if http_status is not None and (
        isinstance(http_status, bool) or not isinstance(http_status, int) or not 100 <= http_status <= 599
    ):
        raise SnapshotEnvelopeError("http_status must be null or an integer from 100 to 599")

    payload = {
        "schema_version": "1.0.0",
        "project_id": PROJECT_ID,
        "snapshot_id": snapshot["snapshot_id"],
        "source_url": source_url,
        "source_url_sha256": source_url_sha256,
        "source_domain": snapshot["source_domain"],
        "publisher": _clean_text(snapshot["publisher"], 200),
        "page_title": _clean_text(snapshot["page_title"], 300),
        "captured_at": snapshot["captured_at"],
        "last_updated_at": snapshot["last_updated_at"],
        "http_status": http_status,
        "body_digest_algorithm": "SHA-256",
        "raw_body_sha256": raw_body_sha256,
        "raw_body_size_bytes": len(body),
        "excerpt": _clean_text(snapshot["excerpt"], max_excerpt_chars),
        "fetch_status": snapshot["fetch_status"],
        "trust_boundary": "UNTRUSTED_DATA_ONLY",
        "access_mode": "PUBLIC_READ_ONLY",
        "access_control_bypass": False,
        "reviewer_verdict": "PENDING",
        "commercial_gate_status": "UNKNOWN",
        "provenance": _provenance(provenance),
        "retention": {
            "mode": "METADATA_ONLY",
            "raw_body_persisted": False,
            "raw_body_disposition": "EPHEMERAL_HASH_PARSE_DISCARD",
            "query_and_fragment_persisted": False,
            "full_page_mirroring": False,
            "excerpt_redaction_policy": "ZCIRA_REDACTION_V1",
        },
        "canonicalization": CANONICALIZATION,
    }
    try:
        Draft202012Validator(dict(envelope_schema), format_checker=FormatChecker()).validate(payload)
    except Exception as exc:
        raise SnapshotEnvelopeError(f"metadata envelope schema validation failed: {type(exc).__name__}") from None

    canonical_bytes = canonical_json_bytes(payload)
    if len(canonical_bytes) > 16_384:
        raise SnapshotEnvelopeError("metadata envelope exceeds the 16 KiB persistence limit")
    digest = hashlib.sha256(canonical_bytes).hexdigest()
    return SnapshotEnvelope(
        payload=payload,
        canonical_bytes=canonical_bytes,
        envelope_sha256=digest,
        content_ref=f"sha256:{digest}",
        storage_path=f"{STORAGE_PREFIX}{digest}.json",
    )


def verify_snapshot_envelope_bytes(
    content: bytes,
    expected_sha256: str,
    *,
    envelope_schema: Mapping[str, Any],
) -> dict[str, Any]:
    """Verify publisher fetch-back bytes, digest, canonical form and schema."""
    if not isinstance(content, bytes):
        raise SnapshotEnvelopeError("fetch-back content must be bytes")
    if not isinstance(expected_sha256, str) or not re.fullmatch(r"[a-f0-9]{64}", expected_sha256):
        raise SnapshotEnvelopeError("expected_sha256 must be a lowercase SHA-256 digest")
    actual = hashlib.sha256(content).hexdigest()
    if actual != expected_sha256:
        raise SnapshotEnvelopeError("fetch-back SHA-256 mismatch")
    try:
        payload = json.loads(content.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise SnapshotEnvelopeError("fetch-back content is not valid UTF-8 JSON") from None
    if not isinstance(payload, dict) or canonical_json_bytes(payload) != content:
        raise SnapshotEnvelopeError("fetch-back JSON is not in canonical form")
    try:
        Draft202012Validator.check_schema(dict(envelope_schema))
        Draft202012Validator(dict(envelope_schema), format_checker=FormatChecker()).validate(payload)
    except Exception as exc:
        raise SnapshotEnvelopeError(f"fetch-back schema validation failed: {type(exc).__name__}") from None
    return payload
