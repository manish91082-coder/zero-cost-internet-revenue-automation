import copy
import hashlib
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from zcira_control.snapshot_envelope import (
    SnapshotEnvelopeError,
    build_metadata_snapshot_envelope,
    verify_snapshot_envelope_bytes,
)

SNAPSHOT_SCHEMA = json.loads((ROOT / "schemas/v1/source_snapshot.schema.json").read_text(encoding="utf-8"))
ENVELOPE_SCHEMA = json.loads((ROOT / "schemas/v1/source_snapshot_envelope.schema.json").read_text(encoding="utf-8"))
RAW = b"public actor documentation body"
URL = "https://docs.apify.com/platform/actors?campaign=public#overview"


def make_snapshot(raw=RAW):
    return {
        "schema_version": "1.0.0",
        "project_id": "ZCIRA-2026-11-13",
        "snapshot_id": "snapshot-apify-actors-test",
        "source_url": URL,
        "source_domain": "docs.apify.com",
        "publisher": "Apify Documentation",
        "page_title": "Actor runtime documentation",
        "captured_at": "2026-11-20T03:00:00Z",
        "last_updated_at": None,
        "content_sha256": hashlib.sha256(raw).hexdigest(),
        "excerpt": "Actor runtime and lifecycle details.",
        "fetch_status": "CAPTURED",
        "trust_boundary": "UNTRUSTED_DATA_ONLY",
        "access_mode": "PUBLIC_READ_ONLY",
        "access_control_bypass": False,
        "content_ref": None,
    }


def build(snapshot=None, raw=RAW, **kwargs):
    return build_metadata_snapshot_envelope(
        make_snapshot() if snapshot is None else snapshot,
        raw,
        allowed_hosts={"docs.apify.com"},
        snapshot_schema=SNAPSHOT_SCHEMA,
        envelope_schema=ENVELOPE_SCHEMA,
        provenance={
            "category_id": 1,
            "destination_id": "apify-docs-actors",
            "source_row_ref": "category-1:destination-1",
            "source_line": 42,
            "archive_sha256": "c" * 64,
        },
        http_status=200,
        **kwargs,
    )


class SnapshotEnvelopeTests(unittest.TestCase):
    def test_builds_metadata_only_envelope_and_never_persists_raw_body(self):
        result = build()
        self.assertEqual(result.payload["raw_body_sha256"], hashlib.sha256(RAW).hexdigest())
        self.assertEqual(result.payload["raw_body_size_bytes"], len(RAW))
        self.assertFalse(result.payload["retention"]["raw_body_persisted"])
        self.assertNotIn(RAW, result.canonical_bytes)
        self.assertNotIn("raw_content", result.payload)
        self.assertEqual(result.content_ref, "sha256:" + result.envelope_sha256)
        self.assertEqual(result.storage_path, "evidence/snapshots/sha256/" + result.envelope_sha256 + ".json")
        self.assertEqual(hashlib.sha256(result.canonical_bytes).hexdigest(), result.envelope_sha256)

    def test_query_and_fragment_are_removed_but_original_url_is_hashed(self):
        result = build()
        self.assertEqual(result.payload["source_url"], "https://docs.apify.com/platform/actors")
        self.assertEqual(result.payload["source_url_sha256"], hashlib.sha256(URL.encode()).hexdigest())
        self.assertNotIn("campaign", result.canonical_bytes.decode())
        self.assertNotIn("overview", result.canonical_bytes.decode())

    def test_canonical_bytes_are_stable(self):
        first = build()
        second = build()
        self.assertEqual(first.canonical_bytes, second.canonical_bytes)
        self.assertEqual(first.envelope_sha256, second.envelope_sha256)

    def test_redacts_email_phone_and_known_token_patterns(self):
        snapshot = make_snapshot()
        snapshot["page_title"] = "Contact alice@example.com"
        snapshot["excerpt"] = "Email alice@example.com call +91 9876543210 Bearer abcdefghijklmnop ghp_123456789012345678901234"
        result = build(snapshot)
        text = result.payload["page_title"] + " " + result.payload["excerpt"]
        self.assertNotIn("alice@example.com", text)
        self.assertNotIn("9876543210", text)
        self.assertNotIn("ghp_123456789012345678901234", text)
        self.assertIn("[REDACTED_EMAIL]", text)
        self.assertIn("[REDACTED_PHONE]", text)
        self.assertIn("[REDACTED_TOKEN]", text)

    def test_excerpt_is_hard_bounded(self):
        snapshot = make_snapshot()
        snapshot["excerpt"] = "x" * 2500
        result = build(snapshot, max_excerpt_chars=1800)
        self.assertEqual(len(result.payload["excerpt"]), 1800)

    def test_rejects_raw_body_hash_mismatch(self):
        with self.assertRaises(SnapshotEnvelopeError):
            build(raw=b"different bytes")

    def test_captured_snapshot_requires_raw_bytes(self):
        with self.assertRaises(SnapshotEnvelopeError):
            build(raw=None)

    def test_rejects_oversized_raw_body(self):
        with self.assertRaises(SnapshotEnvelopeError):
            build(raw=b"x" * 1_000_001)

    def test_rejects_non_bytes_raw_content(self):
        with self.assertRaises(SnapshotEnvelopeError):
            build(raw="not bytes")

    def test_rejects_unlisted_host(self):
        snapshot = make_snapshot()
        snapshot["source_url"] = "https://example.org/page"
        snapshot["source_domain"] = "example.org"
        with self.assertRaises(SnapshotEnvelopeError):
            build(snapshot)

    def test_rejects_non_https_url(self):
        snapshot = make_snapshot()
        snapshot["source_url"] = "http://docs.apify.com/page"
        with self.assertRaises(SnapshotEnvelopeError):
            build(snapshot)

    def test_rejects_credentials_and_nonstandard_port(self):
        snapshot = make_snapshot()
        snapshot["source_url"] = "https://user:pass@docs.apify.com/page"
        with self.assertRaises(SnapshotEnvelopeError):
            build(snapshot)
        snapshot = make_snapshot()
        snapshot["source_url"] = "https://docs.apify.com:8443/page"
        with self.assertRaises(SnapshotEnvelopeError):
            build(snapshot)

    def test_rejects_invalid_provenance_and_boolean_category(self):
        with self.assertRaises(SnapshotEnvelopeError):
            build(provenance={"archive_sha256": "bad"})
        with self.assertRaises(SnapshotEnvelopeError):
            build(provenance={"category_id": True})

    def test_rejects_invalid_http_status(self):
        with self.assertRaises(SnapshotEnvelopeError):
            build(http_status=700)

    def test_allows_blocked_metadata_without_body(self):
        snapshot = make_snapshot(raw=b"")
        snapshot["fetch_status"] = "BLOCKED_BY_POLICY"
        result = build(snapshot, raw=None, http_status=403)
        self.assertEqual(result.payload["fetch_status"], "BLOCKED_BY_POLICY")
        self.assertEqual(result.payload["raw_body_size_bytes"], 0)
        self.assertFalse(result.payload["retention"]["raw_body_persisted"])

    def test_fetch_back_verifier_checks_digest_canonical_form_and_schema(self):
        result = build()
        parsed = verify_snapshot_envelope_bytes(
            result.canonical_bytes,
            result.envelope_sha256,
            envelope_schema=ENVELOPE_SCHEMA,
        )
        self.assertEqual(parsed, result.payload)
        with self.assertRaises(SnapshotEnvelopeError):
            verify_snapshot_envelope_bytes(
                result.canonical_bytes + b" ",
                result.envelope_sha256,
                envelope_schema=ENVELOPE_SCHEMA,
            )

    def test_fetch_back_verifier_rejects_wrong_digest_and_noncanonical_json(self):
        result = build()
        with self.assertRaises(SnapshotEnvelopeError):
            verify_snapshot_envelope_bytes(
                result.canonical_bytes,
                "0" * 64,
                envelope_schema=ENVELOPE_SCHEMA,
            )
        pretty = json.dumps(result.payload, indent=2, ensure_ascii=False).encode()
        with self.assertRaises(SnapshotEnvelopeError):
            verify_snapshot_envelope_bytes(
                pretty,
                hashlib.sha256(pretty).hexdigest(),
                envelope_schema=ENVELOPE_SCHEMA,
            )


if __name__ == "__main__":
    unittest.main()
