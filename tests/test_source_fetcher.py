import hashlib
import unittest
from datetime import datetime, timezone
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from zcira_control.source_fetcher import (
    SourcePolicy, SourcePolicyError, SourceRecord, SourceTransportError,
    TransportResponse, fetch_public_source, load_source_policy,
)

NOW = datetime(2026, 11, 18, 3, 30, tzinfo=timezone.utc)
POLICY = SourcePolicy({"docs.apify.com": SourceRecord("Apify Documentation", "A_PRIMARY_OFFICIAL", "P1")})
URL = "https://docs.apify.com/platform/actors"
ROBOTS = b"User-agent: *\nAllow: /\n"
HTML = b"<html><head><title>Actor docs</title><script>ignore this</script></head><body><h1>Actor lifecycle</h1><p>Public facts.</p></body></html>"


class FakeTransport:
    is_test_transport = True

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def __call__(self, url, policy, max_bytes, same_host):
        self.calls.append((url, max_bytes, same_host))
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


class SourceFetcherTests(unittest.TestCase):
    def test_captures_robots_allowed_html_and_hashes_raw_bytes(self):
        fake = FakeTransport([
            TransportResponse(200, {"content-type": "text/plain"}, ROBOTS, "https://docs.apify.com/robots.txt"),
            TransportResponse(200, {"content-type": "text/html; charset=utf-8", "last-modified": "Tue, 17 Nov 2026 10:00:00 GMT"}, HTML, URL),
        ])
        result = fetch_public_source(URL, POLICY, transport=fake, now=NOW)
        self.assertEqual(result.snapshot["fetch_status"], "CAPTURED")
        self.assertEqual(result.snapshot["page_title"], "Actor docs")
        self.assertNotIn("ignore this", result.snapshot["excerpt"])
        self.assertEqual(result.snapshot["content_sha256"], hashlib.sha256(HTML).hexdigest())
        self.assertIsNone(result.snapshot["content_ref"])
        self.assertEqual(result.snapshot["trust_boundary"], "UNTRUSTED_DATA_ONLY")
        self.assertEqual(len(fake.calls), 2)

    def test_robots_disallow_blocks_page_request(self):
        fake = FakeTransport([TransportResponse(200, {}, b"User-agent: *\nDisallow: /platform/\n", "https://docs.apify.com/robots.txt")])
        result = fetch_public_source(URL, POLICY, transport=fake, now=NOW)
        self.assertEqual(result.snapshot["fetch_status"], "BLOCKED_BY_POLICY")
        self.assertEqual(result.error_code, "ROBOTS_DISALLOW")
        self.assertEqual(len(fake.calls), 1)

    def test_robots_429_returns_retry_after_without_page_request(self):
        fake = FakeTransport([TransportResponse(429, {"retry-after": "120"}, b"", "https://docs.apify.com/robots.txt")])
        result = fetch_public_source(URL, POLICY, transport=fake, now=NOW)
        self.assertEqual(result.snapshot["fetch_status"], "UNAVAILABLE")
        self.assertEqual(result.retry_after_seconds, 120)
        self.assertEqual(len(fake.calls), 1)

    def test_page_403_is_blocked_without_retry(self):
        fake = FakeTransport([
            TransportResponse(404, {}, b"", "https://docs.apify.com/robots.txt"),
            TransportResponse(403, {}, b"", URL),
        ])
        result = fetch_public_source(URL, POLICY, transport=fake, now=NOW)
        self.assertEqual(result.snapshot["fetch_status"], "BLOCKED_BY_POLICY")
        self.assertEqual(result.error_code, "HTTP_ACCESS_RESTRICTED")

    def test_unlisted_host_is_rejected_before_transport(self):
        fake = FakeTransport([])
        with self.assertRaises(SourcePolicyError):
            fetch_public_source("https://example.com/page", POLICY, transport=fake, now=NOW)
        self.assertEqual(fake.calls, [])

    def test_http_and_sensitive_query_urls_are_rejected(self):
        fake = FakeTransport([])
        with self.assertRaises(SourcePolicyError):
            fetch_public_source("http://docs.apify.com/page", POLICY, transport=fake, now=NOW)
        with self.assertRaises(SourcePolicyError):
            fetch_public_source("https://docs.apify.com/page?access_token=x", POLICY, transport=fake, now=NOW)

    def test_cross_host_redirect_is_rejected(self):
        fake = FakeTransport([
            TransportResponse(200, {}, ROBOTS, "https://docs.apify.com/robots.txt"),
            TransportResponse(200, {"content-type": "text/plain"}, b"facts", "https://example.com/redirected"),
        ])
        result = fetch_public_source(URL, POLICY, transport=fake, now=NOW)
        self.assertEqual(result.snapshot["fetch_status"], "BLOCKED_BY_POLICY")
        self.assertIn("allowlist", result.error_code)

    def test_binary_content_type_is_blocked(self):
        fake = FakeTransport([
            TransportResponse(404, {}, b"", "https://docs.apify.com/robots.txt"),
            TransportResponse(200, {"content-type": "application/octet-stream"}, b"binary", URL),
        ])
        result = fetch_public_source(URL, POLICY, transport=fake, now=NOW)
        self.assertEqual(result.snapshot["fetch_status"], "BLOCKED_BY_POLICY")
        self.assertEqual(result.error_code, "CONTENT_TYPE_NOT_ALLOWED")

    def test_oversize_response_is_blocked(self):
        small_policy = SourcePolicy({"docs.apify.com": SourceRecord("Apify Documentation")}, max_response_bytes=4)
        fake = FakeTransport([
            TransportResponse(404, {}, b"", "https://docs.apify.com/robots.txt"),
            TransportResponse(200, {"content-type": "text/plain"}, b"12345", URL, too_large=True),
        ])
        result = fetch_public_source(URL, small_policy, transport=fake, now=NOW)
        self.assertEqual(result.snapshot["fetch_status"], "BLOCKED_BY_POLICY")
        self.assertEqual(result.error_code, "RESPONSE_SIZE_LIMIT")

    def test_robots_network_error_fails_closed(self):
        fake = FakeTransport([SourceTransportError("DNS_RESOLUTION_FAILED")])
        result = fetch_public_source(URL, POLICY, transport=fake, now=NOW)
        self.assertEqual(result.snapshot["fetch_status"], "ERROR")
        self.assertEqual(result.error_code, "DNS_RESOLUTION_FAILED")
        self.assertEqual(len(fake.calls), 1)

    def test_loads_versioned_exact_host_allowlist(self):
        loaded = load_source_policy(ROOT / "config/source_domain_policy.v1.json")
        self.assertIn("docs.apify.com", loaded.allowed_sources)
        self.assertNotIn("sub.docs.apify.com", loaded.allowed_sources)
        self.assertEqual(loaded.max_response_bytes, 1_000_000)

    def test_source_policy_rejects_wildcard_domains(self):
        with self.assertRaises(SourcePolicyError):
            SourcePolicy({"*.apify.com": SourceRecord("Wildcard")})

    def test_live_network_is_disabled_without_pinned_transport(self):
        with self.assertRaises(SourcePolicyError):
            fetch_public_source(URL, POLICY, now=NOW)

    def test_live_network_cannot_be_enabled_by_configuration_only(self):
        with self.assertRaises(SourcePolicyError):
            SourcePolicy({"docs.apify.com": SourceRecord("Apify Documentation")}, live_network_enabled=True)


if __name__ == "__main__":
    unittest.main()
