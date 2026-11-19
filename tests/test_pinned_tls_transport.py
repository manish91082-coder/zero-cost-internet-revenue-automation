import ipaddress
import socket
import ssl
import unittest
from datetime import datetime, timezone
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from zcira_control.pinned_tls_transport import (
    PinnedTLSTransport,
    _PinnedHTTPSConnection,
)
from zcira_control.source_fetcher import (
    SourcePolicy,
    SourcePolicyError,
    SourceRecord,
    fetch_public_source,
    load_source_policy,
)

NOW = datetime(2026, 11, 18, 4, 0, tzinfo=timezone.utc)
HOST = "docs.apify.com"
URL = "https://docs.apify.com/platform/actors"
RECORD = SourceRecord("Apify Documentation", "A_PRIMARY_OFFICIAL", "P1")
PAGE_BODY = b"public facts"


def dns_answer(address):
    parsed = ipaddress.ip_address(address)
    family = socket.AF_INET if parsed.version == 4 else socket.AF_INET6
    sockaddr = (address, 443) if parsed.version == 4 else (address, 443, 0, 0)
    return (family, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", sockaddr)


class FakeResolver:
    def __init__(self, answers):
        self.answers = answers
        self.calls = []

    def __call__(self, host, port, family, socktype, proto):
        self.calls.append((host, port, family, socktype, proto))
        if isinstance(self.answers, Exception):
            raise self.answers
        return list(self.answers)


class FakeSocket:
    def __init__(self):
        self.timeout = None
        self.connected_to = None
        self.closed = False

    def settimeout(self, value):
        self.timeout = value

    def connect(self, address):
        self.connected_to = address

    def close(self):
        self.closed = True


class FakeContext:
    def __init__(self, check_hostname=True, verify_mode=ssl.CERT_REQUIRED):
        self.check_hostname = check_hostname
        self.verify_mode = verify_mode
        self.minimum_version = ssl.TLSVersion.TLSv1_2
        self.options = 0
        self.server_hostname = None
        self.wrapped_socket = None

    def wrap_socket(self, raw, server_hostname):
        self.server_hostname = server_hostname
        self.wrapped_socket = raw
        return raw


class FakeResponse:
    def __init__(self, status, headers=None, chunks=None):
        self.status = status
        self._headers = list((headers or {}).items())
        self._chunks = list(chunks or [])
        self.read_calls = 0
        self.closed = False

    def getheaders(self):
        return list(self._headers)

    def read(self, amount):
        self.read_calls += 1
        if not self._chunks:
            return b""
        chunk = self._chunks[0]
        result = chunk[:amount]
        remainder = chunk[amount:]
        if remainder:
            self._chunks[0] = remainder
        else:
            self._chunks.pop(0)
        return result

    def close(self):
        self.closed = True


class FakeConnection:
    def __init__(self, response):
        self.response = response
        self.requests = []
        self.sock = FakeSocket()
        self.closed = False

    def request(self, method, target, headers):
        self.requests.append((method, target, dict(headers)))

    def getresponse(self):
        return self.response

    def close(self):
        self.closed = True


class FakeConnectionFactory:
    def __init__(self, responses):
        self.responses = list(responses)
        self.connections = []
        self.targets = []

    def __call__(self, host, pinned_ip, timeout, context):
        if not self.responses:
            raise AssertionError("unexpected extra HTTP request")
        response = self.responses.pop(0)
        connection = FakeConnection(response)
        self.connections.append(connection)
        self.targets.append((host, pinned_ip, timeout, context))
        return connection


def live_test_policy():
    # The complete pipeline uses fake DNS, socket and HTTP dependencies only.
    # No public network socket is opened by these tests.
    return SourcePolicy(
        {HOST: RECORD},
        live_network_enabled=True,
        dns_pinning=True,
        egress_controls_audited=True,
    )


class PinnedTLSTransportTests(unittest.TestCase):
    def test_dns_pin_is_cached_for_one_exact_host_and_task(self):
        resolver = FakeResolver([dns_answer("8.8.8.8")])
        transport = PinnedTLSTransport(resolver=resolver)
        first = transport._resolve_and_pin(HOST)
        second = transport._resolve_and_pin(HOST)
        self.assertEqual(first, "8.8.8.8")
        self.assertEqual(second, first)
        self.assertEqual(len(resolver.calls), 1)

    def test_transport_instance_rejects_second_host(self):
        transport = PinnedTLSTransport(
            resolver=FakeResolver([dns_answer("8.8.8.8")])
        )
        transport._resolve_and_pin(HOST)
        with self.assertRaisesRegex(SourcePolicyError, "ONE_PINNED_TRANSPORT"):
            transport._resolve_and_pin("apify.com")

    def test_private_loopback_link_local_and_multicast_dns_are_rejected(self):
        for address in (
            "127.0.0.1",
            "10.0.0.1",
            "169.254.169.254",
            "::1",
            "fe80::1",
            "224.0.0.1",
        ):
            with self.subTest(address=address):
                transport = PinnedTLSTransport(
                    resolver=FakeResolver([dns_answer(address)])
                )
                with self.assertRaises(SourcePolicyError):
                    transport._resolve_and_pin(HOST)

    def test_mixed_public_and_private_dns_answers_reject_the_entire_set(self):
        resolver = FakeResolver(
            [dns_answer("8.8.8.8"), dns_answer("10.0.0.1")]
        )
        transport = PinnedTLSTransport(resolver=resolver)
        with self.assertRaisesRegex(SourcePolicyError, "DNS_NON_PUBLIC"):
            transport._resolve_and_pin(HOST)

    def test_dns_failure_does_not_fall_back_or_retry(self):
        resolver = FakeResolver(socket.gaierror("no resolver"))
        transport = PinnedTLSTransport(resolver=resolver)
        with self.assertRaisesRegex(Exception, "DNS_RESOLUTION_FAILED"):
            transport._resolve_and_pin(HOST)
        self.assertEqual(len(resolver.calls), 1)

    def test_tls_socket_connects_to_pinned_ip_but_uses_hostname_sni(self):
        raw = FakeSocket()
        context = FakeContext()
        calls = []

        def socket_factory(family, socktype):
            calls.append((family, socktype))
            return raw

        connection = _PinnedHTTPSConnection(
            HOST,
            "8.8.8.8",
            5,
            context,
            socket_factory=socket_factory,
        )
        connection.connect()
        self.assertEqual(calls, [(socket.AF_INET, socket.SOCK_STREAM)])
        self.assertEqual(raw.connected_to, ("8.8.8.8", 443))
        self.assertEqual(context.server_hostname, HOST)
        self.assertIs(connection.sock, raw)
        connection.close()

    def test_ipv6_pinned_socket_uses_ipv6_sockaddr(self):
        raw = FakeSocket()
        context = FakeContext()
        connection = _PinnedHTTPSConnection(
            HOST,
            "2606:4700:4700::1111",
            5,
            context,
            socket_factory=lambda family, socktype: raw,
        )
        connection.connect()
        self.assertEqual(raw.connected_to, ("2606:4700:4700::1111", 443, 0, 0))
        self.assertEqual(context.server_hostname, HOST)
        connection.close()

    def test_unverified_tls_context_is_rejected(self):
        transport = PinnedTLSTransport(
            context_factory=lambda: FakeContext(check_hostname=False)
        )
        with self.assertRaisesRegex(SourcePolicyError, "TLS_CERTIFICATE"):
            transport._build_tls_context()

    def test_tls_context_enforces_tls_1_2_or_newer_and_no_compression(self):
        transport = PinnedTLSTransport()
        context = transport._build_tls_context()
        self.assertGreaterEqual(context.minimum_version, ssl.TLSVersion.TLSv1_2)
        self.assertTrue(context.options & ssl.OP_NO_COMPRESSION)
        self.assertTrue(context.check_hostname)
        self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)

    def test_full_pipeline_uses_one_pin_for_robots_and_page_and_no_credentials(self):
        resolver = FakeResolver([dns_answer("8.8.8.8")])
        factory = FakeConnectionFactory([
            FakeResponse(404),
            FakeResponse(200, {"content-type": "text/plain", "content-length": "12"}, [PAGE_BODY]),
        ])
        transport = PinnedTLSTransport(
            resolver=resolver,
            connection_factory=factory,
        )
        result = fetch_public_source(
            URL, live_test_policy(), transport=transport, now=NOW
        )
        self.assertEqual(result.snapshot["fetch_status"], "CAPTURED")
        self.assertEqual(result.raw_content, PAGE_BODY)
        self.assertEqual(len(resolver.calls), 1)
        self.assertEqual([item[1] for item in factory.targets], ["8.8.8.8", "8.8.8.8"])
        for connection in factory.connections:
            method, target, headers = connection.requests[0]
            self.assertEqual(method, "GET")
            self.assertNotIn("Cookie", headers)
            self.assertNotIn("Authorization", headers)
            self.assertNotIn("Proxy-Authorization", headers)
            self.assertEqual(headers["Accept-Encoding"], "identity")
            self.assertEqual(headers["Connection"], "close")

    def test_same_host_redirect_is_followed_without_resolving_again(self):
        resolver = FakeResolver([dns_answer("8.8.8.8")])
        factory = FakeConnectionFactory([
            FakeResponse(404),
            FakeResponse(302, {"Location": "/final"}),
            FakeResponse(200, {"content-type": "text/plain"}, [b"final facts"]),
        ])
        transport = PinnedTLSTransport(
            resolver=resolver,
            connection_factory=factory,
        )
        result = fetch_public_source(
            URL, live_test_policy(), transport=transport, now=NOW
        )
        self.assertEqual(result.snapshot["fetch_status"], "CAPTURED")
        self.assertEqual(result.final_url, "https://docs.apify.com/final")
        self.assertEqual(len(resolver.calls), 1)
        self.assertEqual(
            [c.requests[0][1] for c in factory.connections],
            ["/robots.txt", "/platform/actors", "/final"],
        )

    def test_cross_host_redirect_fails_closed(self):
        resolver = FakeResolver([dns_answer("8.8.8.8")])
        factory = FakeConnectionFactory([
            FakeResponse(404),
            FakeResponse(302, {"Location": "https://example.com/"}),
        ])
        transport = PinnedTLSTransport(
            resolver=resolver,
            connection_factory=factory,
        )
        result = fetch_public_source(
            URL, live_test_policy(), transport=transport, now=NOW
        )
        self.assertEqual(result.snapshot["fetch_status"], "BLOCKED_BY_POLICY")
        self.assertIn("allowlist", result.error_code.lower())

    def test_https_downgrade_redirect_fails_closed(self):
        resolver = FakeResolver([dns_answer("8.8.8.8")])
        factory = FakeConnectionFactory([
            FakeResponse(404),
            FakeResponse(302, {"Location": "http://docs.apify.com/insecure"}),
        ])
        transport = PinnedTLSTransport(
            resolver=resolver,
            connection_factory=factory,
        )
        result = fetch_public_source(
            URL, live_test_policy(), transport=transport, now=NOW
        )
        self.assertEqual(result.snapshot["fetch_status"], "BLOCKED_BY_POLICY")

    def test_redirect_limit_is_enforced(self):
        resolver = FakeResolver([dns_answer("8.8.8.8")])
        redirects = [FakeResponse(302, {"Location": f"/r{i}"}) for i in range(4)]
        factory = FakeConnectionFactory([FakeResponse(404), *redirects])
        transport = PinnedTLSTransport(
            resolver=resolver,
            connection_factory=factory,
        )
        result = fetch_public_source(
            URL, live_test_policy(), transport=transport, now=NOW
        )
        self.assertEqual(result.snapshot["fetch_status"], "BLOCKED_BY_POLICY")
        self.assertEqual(result.error_code, "REDIRECT_LIMIT_EXCEEDED")

    def test_content_length_over_limit_is_rejected_without_reading_body(self):
        resolver = FakeResolver([dns_answer("8.8.8.8")])
        oversized = FakeResponse(200, {"content-length": "1000"}, [b"unused"])
        factory = FakeConnectionFactory([FakeResponse(404), oversized])
        transport = PinnedTLSTransport(
            resolver=resolver,
            connection_factory=factory,
        )
        result = fetch_public_source(
            URL, live_test_policy(), transport=transport, now=NOW
        )
        self.assertEqual(result.snapshot["fetch_status"], "BLOCKED_BY_POLICY")
        self.assertEqual(oversized.read_calls, 0)

    def test_streamed_body_over_limit_is_rejected(self):
        resolver = FakeResolver([dns_answer("8.8.8.8")])
        oversized = FakeResponse(
            200, {"content-type": "text/plain"}, [b"123456", b"789012"]
        )
        factory = FakeConnectionFactory([FakeResponse(404), oversized])
        transport = PinnedTLSTransport(
            resolver=resolver,
            connection_factory=factory,
        )
        small_policy = SourcePolicy(
            {HOST: RECORD},
            max_response_bytes=10,
            live_network_enabled=True,
            dns_pinning=True,
            egress_controls_audited=True,
        )
        result = fetch_public_source(URL, small_policy, transport=transport, now=NOW)
        self.assertEqual(result.snapshot["fetch_status"], "BLOCKED_BY_POLICY")
        self.assertEqual(result.error_code, "RESPONSE_SIZE_LIMIT")

    def test_compressed_response_is_rejected(self):
        resolver = FakeResolver([dns_answer("8.8.8.8")])
        factory = FakeConnectionFactory([
            FakeResponse(404),
            FakeResponse(200, {"content-encoding": "gzip"}, [b"compressed"]),
        ])
        transport = PinnedTLSTransport(
            resolver=resolver,
            connection_factory=factory,
        )
        result = fetch_public_source(
            URL, live_test_policy(), transport=transport, now=NOW
        )
        self.assertEqual(result.snapshot["fetch_status"], "BLOCKED_BY_POLICY")
        self.assertEqual(result.error_code, "CONTENT_ENCODING_NOT_ALLOWED")

    def test_429_returns_retry_after_and_does_not_retry(self):
        resolver = FakeResolver([dns_answer("8.8.8.8")])
        factory = FakeConnectionFactory([
            FakeResponse(404),
            FakeResponse(429, {"Retry-After": "120"}),
        ])
        transport = PinnedTLSTransport(
            resolver=resolver,
            connection_factory=factory,
        )
        result = fetch_public_source(
            URL, live_test_policy(), transport=transport, now=NOW
        )
        self.assertEqual(result.snapshot["fetch_status"], "UNAVAILABLE")
        self.assertEqual(result.retry_after_seconds, 120)
        self.assertEqual(len(factory.connections), 2)

    def test_checked_in_policy_keeps_live_network_disabled(self):
        loaded = load_source_policy(ROOT / "config/source_domain_policy.v1.json")
        self.assertFalse(loaded.live_network_enabled)
        self.assertFalse(loaded.dns_pinning)
        self.assertFalse(loaded.egress_controls_audited)

    def test_pinned_transport_is_blocked_when_any_live_gate_is_missing(self):
        policy = SourcePolicy(
            {HOST: RECORD},
            dns_pinning=True,
            egress_controls_audited=False,
            live_network_enabled=False,
        )
        transport = PinnedTLSTransport(
            resolver=FakeResolver([dns_answer("8.8.8.8")])
        )
        with self.assertRaisesRegex(SourcePolicyError, "LIVE_NETWORK_DISABLED"):
            transport(URL, policy, 1000, HOST)


if __name__ == "__main__":
    unittest.main()
