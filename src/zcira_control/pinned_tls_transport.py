from __future__ import annotations

import http.client
import ipaddress
import socket
import ssl
import time
import urllib.parse
from typing import Callable

from .source_fetcher import (
    SourcePolicy,
    SourcePolicyError,
    SourceTransportError,
    TransportResponse,
    _canonical_url,
    _header,
    _validate_url,
)

_REDIRECT_STATUSES = {301, 302, 303, 307, 308}
_ALLOWED_CONTENT_ENCODINGS = {"", "identity"}


class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    """HTTPSConnection that opens a socket to a literal IP but keeps hostname SNI."""

    def __init__(
        self,
        host: str,
        pinned_ip: str,
        timeout: float,
        context: ssl.SSLContext,
        socket_factory: Callable = socket.socket,
    ) -> None:
        super().__init__(host, port=443, timeout=timeout, context=context)
        self._pinned_ip = pinned_ip
        self._socket_factory = socket_factory

    def connect(self) -> None:
        if self._tunnel_host is not None:
            raise OSError("HTTP_CONNECT_TUNNEL_PROHIBITED")
        address = ipaddress.ip_address(self._pinned_ip)
        family = socket.AF_INET if address.version == 4 else socket.AF_INET6
        raw = self._socket_factory(family, socket.SOCK_STREAM)
        try:
            raw.settimeout(self.timeout)
            if address.version == 4:
                sockaddr = (str(address), self.port)
            else:
                sockaddr = (str(address), self.port, 0, 0)
            raw.connect(sockaddr)
            self.sock = self._context.wrap_socket(raw, server_hostname=self.host)
        except BaseException:
            raw.close()
            raise


class PinnedTLSTransport:
    """One-host, one-task pinned-IP HTTPS transport.

    The checked-in source policy keeps live_network_enabled, dns_pinning and
    egress_controls_audited false. The transport is accepted only when all
    three independent policy gates are true.
    """

    is_pinned_tls_transport = True
    is_test_transport = False

    def __init__(
        self,
        *,
        resolver: Callable = socket.getaddrinfo,
        socket_factory: Callable = socket.socket,
        context_factory: Callable = ssl.create_default_context,
        connection_factory: Callable | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._resolver = resolver
        self._socket_factory = socket_factory
        self._context_factory = context_factory
        self._connection_factory = connection_factory or self._make_connection
        self._clock = clock
        self._pins: dict[str, str] = {}
        self._first_host: str | None = None

    def __call__(
        self,
        url: str,
        policy: SourcePolicy,
        max_bytes: int,
        same_host: str | None,
    ) -> TransportResponse:
        if not (
            policy.live_network_enabled
            and policy.dns_pinning
            and policy.egress_controls_audited
        ):
            raise SourcePolicyError(
                "LIVE_NETWORK_DISABLED_PENDING_DNS_PINNING_AND_EGRESS_AUDIT"
            )
        host = _validate_url(url, policy, same_host)
        pinned_ip = self._resolve_and_pin(host)
        return self._fetch_url(url, host, pinned_ip, policy, max_bytes)

    def _resolve_and_pin(self, host: str) -> str:
        if self._first_host is not None and host != self._first_host:
            raise SourcePolicyError("ONE_PINNED_TRANSPORT_INSTANCE_PER_EXACT_HOST")
        if host in self._pins:
            return self._pins[host]
        self._first_host = host
        try:
            answers = self._resolver(
                host,
                443,
                socket.AF_UNSPEC,
                socket.SOCK_STREAM,
                socket.IPPROTO_TCP,
            )
        except (OSError, socket.gaierror, TimeoutError):
            raise SourceTransportError("DNS_RESOLUTION_FAILED") from None
        if not answers:
            raise SourceTransportError("DNS_NO_ADDRESS_RECORDS")

        public_addresses: list[str] = []
        for answer in answers:
            try:
                family, _socktype, _proto, _canonname, sockaddr = answer
                raw_address = sockaddr[0]
            except (TypeError, IndexError, ValueError):
                raise SourceTransportError("DNS_RESPONSE_INVALID") from None
            if family not in (socket.AF_INET, socket.AF_INET6):
                raise SourcePolicyError("DNS_ADDRESS_FAMILY_NOT_ALLOWED")
            if not isinstance(raw_address, str) or "%" in raw_address:
                raise SourcePolicyError("DNS_SCOPED_OR_INVALID_ADDRESS")
            try:
                address = ipaddress.ip_address(raw_address)
            except ValueError:
                raise SourcePolicyError("DNS_ADDRESS_INVALID") from None
            if family == socket.AF_INET and address.version != 4:
                raise SourcePolicyError("DNS_ADDRESS_FAMILY_MISMATCH")
            if family == socket.AF_INET6 and address.version != 6:
                raise SourcePolicyError("DNS_ADDRESS_FAMILY_MISMATCH")
            if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped:
                address = address.ipv4_mapped
            if (
                not address.is_global
                or address.is_private
                or address.is_loopback
                or address.is_link_local
                or address.is_multicast
                or address.is_reserved
                or address.is_unspecified
            ):
                raise SourcePolicyError("DNS_NON_PUBLIC_ADDRESS_PRESENT")
            public_addresses.append(str(address))

        if not public_addresses:
            raise SourceTransportError("DNS_NO_PUBLIC_ADDRESSES")
        self._pins[host] = public_addresses[0]
        return self._pins[host]

    def _build_tls_context(self) -> ssl.SSLContext:
        context = self._context_factory()
        if (
            getattr(context, "check_hostname", False) is not True
            or getattr(context, "verify_mode", None) != ssl.CERT_REQUIRED
        ):
            raise SourcePolicyError("TLS_CERTIFICATE_AND_HOSTNAME_VERIFICATION_REQUIRED")
        if context.minimum_version < ssl.TLSVersion.TLSv1_2:
            context.minimum_version = ssl.TLSVersion.TLSv1_2
        context.options |= ssl.OP_NO_COMPRESSION
        return context

    def _make_connection(
        self,
        host: str,
        pinned_ip: str,
        timeout: float,
        context: ssl.SSLContext,
    ):
        return _PinnedHTTPSConnection(
            host,
            pinned_ip,
            timeout,
            context,
            socket_factory=self._socket_factory,
        )

    def _request_once(
        self,
        url: str,
        host: str,
        pinned_ip: str,
        policy: SourcePolicy,
        max_bytes: int,
    ) -> TransportResponse:
        if not isinstance(max_bytes, int) or isinstance(max_bytes, bool) or not 1 <= max_bytes <= 1_000_000:
            raise SourcePolicyError("TRANSPORT_BYTE_LIMIT_INVALID")
        _validate_url(url, policy, host)
        if any(ch.isspace() for ch in url):
            raise SourcePolicyError("URL_WHITESPACE_PROHIBITED")

        parts = urllib.parse.urlsplit(url)
        request_target = urllib.parse.urlunsplit(("", "", parts.path or "/", parts.query, ""))
        deadline = self._clock() + policy.timeout_seconds
        context = self._build_tls_context()
        connection = self._connection_factory(
            host, pinned_ip, policy.timeout_seconds, context
        )
        response = None
        try:
            connection.request(
                "GET",
                request_target,
                headers={
                    "User-Agent": policy.user_agent,
                    "Accept": "text/html, text/plain, application/json",
                    "Accept-Encoding": "identity",
                    "Connection": "close",
                },
            )
            response = connection.getresponse()
            headers = dict(response.getheaders())
            status = response.status

            if status in _REDIRECT_STATUSES:
                return TransportResponse(status, headers, b"", url, False)

            content_encoding = (_header(headers, "content-encoding") or "").strip().lower()
            if content_encoding not in _ALLOWED_CONTENT_ENCODINGS:
                raise SourcePolicyError("CONTENT_ENCODING_NOT_ALLOWED")

            content_length = _header(headers, "content-length")
            if content_length is not None:
                raw_length = content_length.strip()
                if not raw_length.isdigit():
                    raise SourceTransportError("CONTENT_LENGTH_INVALID")
                if int(raw_length) > max_bytes:
                    return TransportResponse(status, headers, b"", url, True)

            body = bytearray()
            while True:
                remaining_time = deadline - self._clock()
                if remaining_time <= 0:
                    raise SourceTransportError("REQUEST_TIMEOUT")
                sock = getattr(connection, "sock", None)
                if sock is not None:
                    sock.settimeout(remaining_time)
                remaining_bytes = max_bytes + 1 - len(body)
                if remaining_bytes <= 0:
                    return TransportResponse(status, headers, b"", url, True)
                chunk = response.read(min(65_536, remaining_bytes))
                if not chunk:
                    break
                body.extend(chunk)
                if len(body) > max_bytes:
                    return TransportResponse(status, headers, b"", url, True)

            return TransportResponse(status, headers, bytes(body), url, False)
        except SourcePolicyError:
            raise
        except SourceTransportError:
            raise
        except (socket.timeout, TimeoutError):
            raise SourceTransportError("REQUEST_TIMEOUT") from None
        except (OSError, ssl.SSLError, http.client.HTTPException):
            raise SourceTransportError("TLS_OR_HTTP_TRANSPORT_FAILED") from None
        finally:
            if response is not None:
                try:
                    response.close()
                except Exception:
                    pass
            try:
                connection.close()
            except Exception:
                pass

    def _fetch_url(
        self,
        url: str,
        host: str,
        pinned_ip: str,
        policy: SourcePolicy,
        max_bytes: int,
    ) -> TransportResponse:
        current = _canonical_url(url, host)
        for redirects_followed in range(policy.max_redirects + 1):
            response = self._request_once(
                current, host, pinned_ip, policy, max_bytes
            )
            if response.status_code not in _REDIRECT_STATUSES:
                return response
            location = _header(response.headers, "location")
            if not location:
                return response
            if redirects_followed >= policy.max_redirects:
                raise SourcePolicyError("REDIRECT_LIMIT_EXCEEDED")
            target = urllib.parse.urljoin(current, location)
            _validate_url(target, policy, host)
            if any(ch.isspace() for ch in target):
                raise SourcePolicyError("REDIRECT_URL_WHITESPACE_PROHIBITED")
            current = _canonical_url(target, host)
        raise SourcePolicyError("REDIRECT_LIMIT_EXCEEDED")
