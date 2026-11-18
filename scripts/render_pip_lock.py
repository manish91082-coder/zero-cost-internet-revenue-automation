#!/usr/bin/env python3
"""Render a deterministic, hash-locked requirements file from a pip install report.

This script performs no network access and installs no packages. The caller is
responsible for producing the report with pip --dry-run --report --only-binary.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
VERSION_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9.!+_-]*$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
EXPECTED_LINE_RE = re.compile(
    r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)\s*==\s*([A-Za-z0-9][A-Za-z0-9.!+_-]*)\s+--hash=sha256:([0-9a-fA-F]{64})\s*$"
)
ALLOWED_WHEEL_HOSTS = {"files.pythonhosted.org"}


class LockReportError(ValueError):
    """Raised when a pip report cannot be safely converted to a lock."""


def normalize_name(name: str) -> str:
    if not isinstance(name, str) or not NAME_RE.fullmatch(name):
        raise LockReportError(f"invalid package name: {name!r}")
    return re.sub(r"[-_.]+", "-", name).lower()


def parse_expected_requirements(path: Path | None) -> dict[str, tuple[str, str]]:
    expected: dict[str, tuple[str, str]] = {}
    if path is None:
        return expected
    for line_number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        match = EXPECTED_LINE_RE.fullmatch(line)
        if not match:
            raise LockReportError(
                f"expected-requirements line {line_number} must be an exact == pin with one SHA-256 hash"
            )
        raw_name, version, digest = match.groups()
        name = normalize_name(raw_name)
        digest = digest.lower()
        if not SHA256_RE.fullmatch(digest):
            raise LockReportError(f"invalid expected SHA-256 at line {line_number}")
        if name in expected:
            raise LockReportError(f"duplicate expected package: {name}")
        expected[name] = (version, digest)
    return expected


def sha256_for_item(item: dict) -> str:
    download = item.get("download_info")
    if not isinstance(download, dict):
        raise LockReportError("install entry is missing download_info")
    url = download.get("url")
    if not isinstance(url, str):
        raise LockReportError("install entry is missing a download URL")
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in ALLOWED_WHEEL_HOSTS:
        raise LockReportError(f"unapproved package download host: {url!r}")
    if not parsed.path.lower().endswith(".whl"):
        raise LockReportError(f"non-wheel package artifact rejected: {url!r}")
    archive = download.get("archive_info")
    if not isinstance(archive, dict):
        raise LockReportError("install entry is missing archive_info")
    hashes = archive.get("hashes")
    digest = hashes.get("sha256") if isinstance(hashes, dict) else None
    if not digest:
        legacy_hash = archive.get("hash")
        if isinstance(legacy_hash, str) and legacy_hash.startswith("sha256="):
            digest = legacy_hash.split("=", 1)[1]
    if not isinstance(digest, str) or not SHA256_RE.fullmatch(digest.lower()):
        raise LockReportError("every selected wheel must have a valid SHA-256")
    return digest.lower()


def render_lock(report_path: Path, expected_requirements: Path | None, target: str) -> str:
    raw = report_path.read_bytes()
    try:
        report = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise LockReportError(f"invalid pip report JSON: {exc}") from None
    install = report.get("install") if isinstance(report, dict) else None
    if not isinstance(install, list) or not install:
        raise LockReportError("pip report must contain a non-empty install array")
    packages: dict[str, tuple[str, str]] = {}
    for index, item in enumerate(install):
        if not isinstance(item, dict):
            raise LockReportError(f"install entry {index} is not an object")
        metadata = item.get("metadata")
        if not isinstance(metadata, dict):
            raise LockReportError(f"install entry {index} is missing metadata")
        name = normalize_name(metadata.get("name"))
        version = metadata.get("version")
        if not isinstance(version, str) or not VERSION_RE.fullmatch(version):
            raise LockReportError(f"invalid version for package {name}")
        digest = sha256_for_item(item)
        current = packages.get(name)
        candidate = (version, digest)
        if current is not None and current != candidate:
            raise LockReportError(f"conflicting versions or hashes for package {name}")
        packages[name] = candidate
    expected = parse_expected_requirements(expected_requirements)
    for name, (version, digest) in expected.items():
        if packages.get(name) != (version, digest):
            raise LockReportError(
                f"resolved wheel for {name} does not match the exact version and SHA-256 pin"
            )
    report_hash = hashlib.sha256(raw).hexdigest()
    lines = [
        "# ZCIRA S7-A candidate lock; review and commit through the canonical writer.",
        f"# Target: {target}",
        f"# pip report SHA-256: {report_hash}",
        "# Generated from pip --dry-run --report --ignore-installed --only-binary=:all:.",
        "# Every resolved dependency is exact-pinned and SHA-256 locked.",
    ]
    for name in sorted(packages):
        version, digest = packages[name]
        lines.append(f"{name}=={version} --hash=sha256:{digest}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--expected-requirements", type=Path)
    parser.add_argument("--target", default="linux-x86_64-cp312")
    args = parser.parse_args(argv)
    try:
        rendered = render_lock(args.report, args.expected_requirements, args.target)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8", newline="\n")
    except (OSError, LockReportError) as exc:
        print(f"lock generation failed: {exc}", file=sys.stderr)
        return 2
    print(f"rendered {sum(1 for line in rendered.splitlines() if line and not line.startswith('#'))} packages")
    print(f"output: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
