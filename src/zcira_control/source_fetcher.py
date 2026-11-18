from __future__ import annotations

import hashlib
import ipaddress
import json
import re
import urllib.parse
import urllib.robotparser
from dataclasses import dataclass
from datetime import datetime, timezone
from email.message import Message
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from typing import Callable, Mapping

from .policy import PROJECT_ID


class SourcePolicyError(ValueError):
    """A source URL or response violates the public-read policy."""


class SourceTransportError(RuntimeError):
    """A bounded public fetch failed without a usable HTTP response."""


@dataclass(frozen=True)
class SourceRecord:
    publisher: str
    evidence_grade: str = "B_OFFICIAL_SUPPORT"
    priority: str = "P1"


@dataclass(frozen=True)
class SourcePolicy:
    allowed_sources: Mapping[str, SourceRecord]
    max_response_bytes: int = 1_000_000
    robots_max_bytes: int = 65_536
    timeout_seconds: int = 15
    max_redirects: int = 3
    user_agent: str = "ZCIRA-ReadOnlyResearch/1.0"
    live_network_enabled: bool = False
    allowed_content_types: tuple[str, ...] = (
        "text/html", "text/plain", "application/json"
    )

    def __post_init__(self) -> None:
        if self.live_network_enabled:
            raise SourcePolicyError("live network is disabled until pinned TLS transport and egress controls are audited")
        if not self.allowed_sources:
            raise SourcePolicyError("source allowlist must not be empty")
        if self.max_response_bytes < 1 or self.max_response_bytes > 1_000_000:
            raise SourcePolicyError("max_response_bytes must be between 1 and 1000000")
        if self.robots_max_bytes < 1 or self.robots_max_bytes > 65_536:
            raise SourcePolicyError("robots_max_bytes must be between 1 and 65536")
        if self.timeout_seconds < 1 or self.timeout_seconds > 30:
            raise SourcePolicyError("timeout_seconds must be between 1 and 30")
        if self.max_redirects < 0 or self.max_redirects > 3:
            raise SourcePolicyError("max_redirects must be between 0 and 3")
        if not set(self.allowed_content_types).issubset({"text/html", "text/plain", "application/json"}):
            raise SourcePolicyError("only HTML, plain text and JSON content types are permitted")
        for domain, record in self.allowed_sources.items():
            if domain != domain.lower() or not re.fullmatch(r"[a-z0-9.-]+", domain):
                raise SourcePolicyError(f"invalid exact source domain: {domain!r}")
            if domain.startswith(".") or domain.endswith(".") or ".." in domain or "*" in domain:
                raise SourcePolicyError(f"wildcard or malformed source domain: {domain!r}")
            if not isinstance(record, SourceRecord) or not record.publisher:
                raise SourcePolicyError(f"invalid source record for {domain}")


@dataclass(frozen=True)
class TransportResponse:
    status_code: int
    headers: Mapping[str, str]
    body: bytes = b""
    final_url: str = ""
    too_large: bool = False


@dataclass(frozen=True)
class FetchOutcome:
    snapshot: dict
    raw_content: bytes | None
    status_code: int | None
    retry_after_seconds: int | None
    final_url: str | None
    error_code: str | None


# A future live transport must pin DNS to the TLS connection, disable proxies,
# enforce same-host redirects and byte/time limits, and return the final URL.
Transport = Callable[[str, SourcePolicy, int, str | None], TransportResponse]


class _VisibleTextParser(HTMLParser):
    _HIDDEN = {"script", "style", "noscript", "template", "svg"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.hidden_depth = 0
        self.title_depth = 0
        self.title_parts: list[str] = []
        self.text_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        tag = tag.lower()
        if tag in self._HIDDEN:
            self.hidden_depth += 1
        if tag == "title":
            self.title_depth += 1

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in self._HIDDEN and self.hidden_depth:
            self.hidden_depth -= 1
        if tag == "title" and self.title_depth:
            self.title_depth -= 1

    def handle_data(self, data: str) -> None:
        if self.title_depth:
            self.title_parts.append(data)
        if self.hidden_depth == 0:
            self.text_parts.append(data)


def _utc_iso(value: datetime) -> str:
    if value.tzinfo is None:
        raise SourcePolicyError("clock must return a timezone-aware datetime")
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def load_source_policy(path) -> SourcePolicy:
    """Load and strictly validate the versioned exact-host source allowlist."""
    from pathlib import Path

    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SourcePolicyError(f"source policy cannot be read: {type(exc).__name__}") from None
    if not isinstance(data, dict) or data.get("schema_version") != "1.0.0" or data.get("project_id") != PROJECT_ID:
        raise SourcePolicyError("source policy identity/version mismatch")
    required_false = (
        "allow_subdomains", "proxies_enabled", "cookies_enabled", "authentication_enabled",
        "javascript_execution_enabled", "automatic_retries", "access_control_bypass", "dns_pinning",
    )
    if data.get("exact_host_allowlist") is not True or data.get("robots_required") is not True:
        raise SourcePolicyError("exact-host allowlist and robots checks are mandatory")
    if data.get("dns_preflight_global_only") is not True or data.get("live_network_enabled") is not False:
        raise SourcePolicyError("live network remains disabled until DNS pinning and egress controls are audited")
    if any(data.get(key) is not False for key in required_false):
        raise SourcePolicyError("source policy attempts to enable a prohibited capability")
    entries = data.get("allowed_sources")
    if not isinstance(entries, list) or not entries:
        raise SourcePolicyError("allowed_sources must be a non-empty array")
    allowed: dict[str, SourceRecord] = {}
    for item in entries:
        if not isinstance(item, dict):
            raise SourcePolicyError("source allowlist entry must be an object")
        domain = item.get("domain")
        publisher = item.get("publisher")
        grade = item.get("default_evidence_grade", "B_OFFICIAL_SUPPORT")
        priority = item.get("priority")
        if not isinstance(domain, str) or not isinstance(publisher, str) or not publisher.strip():
            raise SourcePolicyError("source allowlist domain/publisher is invalid")
        if grade not in {"A_PRIMARY_OFFICIAL", "B_OFFICIAL_SUPPORT", "C_SECONDARY", "D_UNVERIFIED"}:
            raise SourcePolicyError("source allowlist evidence grade is invalid")
        if priority not in {"P1", "P2"}:
            raise SourcePolicyError("initial source worker allowlist is restricted to P1/P2")
        if domain in allowed:
            raise SourcePolicyError(f"duplicate source domain: {domain}")
        allowed[domain] = SourceRecord(publisher.strip(), grade, priority)
    return SourcePolicy(
        allowed_sources=allowed,
        max_response_bytes=data.get("max_response_bytes", 1_000_000),
        robots_max_bytes=data.get("robots_max_bytes", 65_536),
        timeout_seconds=data.get("timeout_seconds", 15),
        max_redirects=data.get("max_redirects", 3),
        user_agent=data.get("user_agent", "ZCIRA-ReadOnlyResearch/1.0"),
        live_network_enabled=data.get("live_network_enabled", False),
        allowed_content_types=tuple(data.get("allowed_content_types", ["text/html", "text/plain", "application/json"])),
    )


def _validate_url(url: str, policy: SourcePolicy, same_host: str | None = None) -> str:
    if not isinstance(url, str) or not url or any(ord(ch) < 32 for ch in url):
        raise SourcePolicyError("source URL is invalid")
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme.lower() != "https":
        raise SourcePolicyError("only HTTPS public sources are permitted")
    if parsed.username is not None or parsed.password is not None:
        raise SourcePolicyError("URL credentials are prohibited")
    try:
        port = parsed.port
    except ValueError:
        raise SourcePolicyError("invalid URL port") from None
    if port not in (None, 443):
        raise SourcePolicyError("only the standard HTTPS port is permitted")
    host = (parsed.hostname or "").lower()
    if not host:
        raise SourcePolicyError("source URL has no hostname")
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        raise SourcePolicyError("IP-literal source URLs are prohibited")
    if host not in policy.allowed_sources:
        raise SourcePolicyError("source hostname is not in the exact allowlist")
    if same_host is not None and host != same_host:
        raise SourcePolicyError("cross-host redirect is prohibited")
    sensitive = {"token", "access_token", "api_key", "apikey", "key", "password", "code", "auth", "session", "email"}
    if any(key.lower() in sensitive for key, _ in urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)):
        raise SourcePolicyError("sensitive query parameter is prohibited")
    return host


def _canonical_url(url: str, host: str) -> str:
    parsed = urllib.parse.urlsplit(url)
    return urllib.parse.urlunsplit(("https", host, parsed.path or "/", parsed.query, ""))


def _header(headers: Mapping[str, str], name: str) -> str | None:
    target = name.lower()
    for key, value in headers.items():
        if key.lower() == target:
            return value
    return None


def _retry_after(headers: Mapping[str, str], now: datetime) -> int | None:
    raw = _header(headers, "retry-after")
    if not raw:
        return None
    if raw.strip().isdigit():
        return min(86_400, int(raw.strip()))
    try:
        when = parsedate_to_datetime(raw)
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        return min(86_400, max(0, int((when - now).total_seconds())))
    except (TypeError, ValueError, OverflowError):
        return None


def _content_type(headers: Mapping[str, str]) -> tuple[str, str]:
    raw = _header(headers, "content-type") or ""
    if not raw.strip():
        return "", "utf-8"
    message = Message()
    message["content-type"] = raw
    return message.get_content_type().lower(), message.get_content_charset() or "utf-8"


def _extract_text(body: bytes, content_type: str, charset: str) -> tuple[str, str]:
    try:
        decoded = body.decode(charset, errors="replace")
    except LookupError:
        decoded = body.decode("utf-8", errors="replace")
    if content_type == "text/html":
        parser = _VisibleTextParser()
        parser.feed(decoded)
        title = re.sub(r"\s+", " ", " ".join(parser.title_parts)).strip()
        text = re.sub(r"\s+", " ", " ".join(parser.text_parts)).strip()
        return title, text
    if content_type == "application/json":
        try:
            payload = json.loads(decoded)
            title = payload.get("title") or payload.get("name") or "" if isinstance(payload, dict) else ""
        except (json.JSONDecodeError, AttributeError):
            title = ""
        return str(title).strip(), re.sub(r"\s+", " ", decoded).strip()
    return "", re.sub(r"\s+", " ", decoded).strip()


def _snapshot(
    url: str,
    host: str,
    record: SourceRecord,
    now: datetime,
    status: str,
    body: bytes = b"",
    headers: Mapping[str, str] | None = None,
    page_title: str = "",
    excerpt: str = "",
) -> dict:
    digest = hashlib.sha256(body).hexdigest()
    snapshot_seed = f"{url}\n{status}\n{digest}".encode("utf-8")
    snapshot_id = "snapshot-" + hashlib.sha256(snapshot_seed).hexdigest()[:32]
    last_updated = None
    modified = _header(headers or {}, "last-modified")
    if modified:
        try:
            parsed = parsedate_to_datetime(modified)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            last_updated = _utc_iso(parsed)
        except (TypeError, ValueError, OverflowError):
            last_updated = None
    return {
        "schema_version": "1.0.0",
        "project_id": PROJECT_ID,
        "snapshot_id": snapshot_id,
        "source_url": url,
        "source_domain": host,
        "publisher": record.publisher,
        "page_title": (page_title or record.publisher or host)[:300],
        "captured_at": _utc_iso(now),
        "last_updated_at": last_updated,
        "content_sha256": digest,
        "excerpt": excerpt[:2000],
        "fetch_status": status,
        "trust_boundary": "UNTRUSTED_DATA_ONLY",
        "access_mode": "PUBLIC_READ_ONLY",
        "access_control_bypass": False,
        "content_ref": None,
    }


def fetch_public_source(
    url: str,
    policy: SourcePolicy,
    *,
    transport: Transport | None = None,
    now: datetime | None = None,
) -> FetchOutcome:
    """Process one allowlisted public page through an explicitly injected transport.

    A live network transport is intentionally not shipped/enabled in this phase.
    The future transport must pin DNS results to the TLS connection, validate
    redirects, disable proxies, and enforce the byte/timeout limits. Tests inject
    deterministic responses. No cookies, credentials, JavaScript, automatic
    retry or repository writes are used; page bytes remain untrusted data.
    """
    captured_at = now or datetime.now(timezone.utc)
    if captured_at.tzinfo is None:
        raise SourcePolicyError("clock must return a timezone-aware datetime")
    if transport is None or getattr(transport, "is_test_transport", False) is not True:
        raise SourcePolicyError("LIVE_NETWORK_DISABLED_PENDING_PINNED_TLS_TRANSPORT_AND_EGRESS_AUDIT")
    fetch = transport
    host = _validate_url(url, policy)
    record = policy.allowed_sources[host]
    canonical = _canonical_url(url, host)
    robots_url = f"https://{host}/robots.txt"
    try:
        robots = fetch(robots_url, policy, policy.robots_max_bytes, host)
        if not robots.final_url:
            raise SourcePolicyError("ROBOTS_FINAL_URL_MISSING")
        _validate_url(robots.final_url, policy, host)
        if robots.too_large or len(robots.body) > policy.robots_max_bytes:
            raise SourcePolicyError("ROBOTS_FILE_TOO_LARGE")
        if robots.status_code in (404, 410):
            robots_allowed = True
        elif robots.status_code in (401, 403, 429) or robots.status_code >= 500:
            retry = _retry_after(robots.headers, captured_at)
            status = "UNAVAILABLE" if robots.status_code == 429 else "BLOCKED_BY_POLICY"
            snap = _snapshot(canonical, host, record, captured_at, status)
            return FetchOutcome(snap, None, robots.status_code, retry, robots.final_url, "ROBOTS_ACCESS_RESTRICTED")
        elif 200 <= robots.status_code < 300:
            parser = urllib.robotparser.RobotFileParser()
            parser.set_url(robots_url)
            parser.parse(robots.body.decode("utf-8", errors="replace").splitlines())
            robots_allowed = parser.can_fetch(policy.user_agent, canonical)
        else:
            snap = _snapshot(canonical, host, record, captured_at, "BLOCKED_BY_POLICY")
            return FetchOutcome(snap, None, robots.status_code, None, robots.final_url, "ROBOTS_STATUS_UNSUPPORTED")
        if not robots_allowed:
            snap = _snapshot(canonical, host, record, captured_at, "BLOCKED_BY_POLICY")
            return FetchOutcome(snap, None, robots.status_code, None, robots.final_url, "ROBOTS_DISALLOW")
    except SourcePolicyError as exc:
        snap = _snapshot(canonical, host, record, captured_at, "BLOCKED_BY_POLICY")
        return FetchOutcome(snap, None, None, None, None, str(exc))
    except SourceTransportError as exc:
        snap = _snapshot(canonical, host, record, captured_at, "ERROR")
        return FetchOutcome(snap, None, None, None, None, str(exc))

    try:
        response = fetch(canonical, policy, policy.max_response_bytes, host)
        if not response.final_url:
            raise SourcePolicyError("SOURCE_FINAL_URL_MISSING")
        _validate_url(response.final_url, policy, host)
    except SourcePolicyError as exc:
        snap = _snapshot(canonical, host, record, captured_at, "BLOCKED_BY_POLICY")
        return FetchOutcome(snap, None, None, None, None, str(exc))
    except SourceTransportError as exc:
        snap = _snapshot(canonical, host, record, captured_at, "ERROR")
        return FetchOutcome(snap, None, None, None, None, str(exc))

    if response.status_code == 429:
        snap = _snapshot(canonical, host, record, captured_at, "UNAVAILABLE", headers=response.headers)
        return FetchOutcome(snap, None, response.status_code, _retry_after(response.headers, captured_at), response.final_url, "HTTP_429_NO_RETRY")
    if response.status_code in (401, 403):
        snap = _snapshot(canonical, host, record, captured_at, "BLOCKED_BY_POLICY", headers=response.headers)
        return FetchOutcome(snap, None, response.status_code, None, response.final_url, "HTTP_ACCESS_RESTRICTED")
    if response.status_code in (404, 410):
        snap = _snapshot(canonical, host, record, captured_at, "UNAVAILABLE", headers=response.headers)
        return FetchOutcome(snap, None, response.status_code, None, response.final_url, "HTTP_NOT_FOUND")
    if not 200 <= response.status_code < 300:
        snap = _snapshot(canonical, host, record, captured_at, "ERROR", headers=response.headers)
        return FetchOutcome(snap, None, response.status_code, _retry_after(response.headers, captured_at), response.final_url, "HTTP_STATUS_ERROR")
    if response.too_large or len(response.body) > policy.max_response_bytes:
        snap = _snapshot(canonical, host, record, captured_at, "BLOCKED_BY_POLICY", headers=response.headers)
        return FetchOutcome(snap, None, response.status_code, None, response.final_url, "RESPONSE_SIZE_LIMIT")

    content_type, charset = _content_type(response.headers)
    if content_type not in policy.allowed_content_types:
        snap = _snapshot(canonical, host, record, captured_at, "BLOCKED_BY_POLICY", headers=response.headers)
        return FetchOutcome(snap, None, response.status_code, None, response.final_url, "CONTENT_TYPE_NOT_ALLOWED")
    title, visible_text = _extract_text(response.body, content_type, charset)
    if not visible_text:
        snap = _snapshot(canonical, host, record, captured_at, "UNAVAILABLE", response.body, response.headers, title)
        return FetchOutcome(snap, response.body, response.status_code, None, response.final_url, "NO_VISIBLE_TEXT")
    snap = _snapshot(canonical, host, record, captured_at, "CAPTURED", response.body, response.headers, title, visible_text)
    return FetchOutcome(snap, response.body, response.status_code, None, response.final_url, None)
