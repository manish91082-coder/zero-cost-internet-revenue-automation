from __future__ import annotations

import base64
import json
from pathlib import PurePosixPath
from typing import Any, Mapping, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit, parse_qs
from urllib.request import Request, urlopen

from .checkpoints import StaleCheckpoint
from .policy import CANONICAL_BRANCH, CANONICAL_REPO, PolicyError, validate_git_sha


class GitHubAPIError(RuntimeError):
    def __init__(self, status: int, message: str):
        self.status = status
        super().__init__(f"GitHub API status {status}: {message[:240]}")


class BranchHeadConflict(StaleCheckpoint):
    """The branch moved after the expected-head check; no ref update was accepted."""


class StateTransport(Protocol):
    def request(self, method: str, path: str, payload: Mapping[str, Any] | None = None) -> dict[str, Any]:
        ...


class UrllibGitHubTransport:
    """Small standard-library GitHub REST transport. The token is never logged or returned."""

    def __init__(self, token: str, repo: str = CANONICAL_REPO, timeout_seconds: int = 20):
        if not isinstance(token, str) or not token.strip():
            raise PolicyError("GitHub token is required at runtime")
        if repo != CANONICAL_REPO:
            raise PolicyError("non-canonical repository is forbidden")
        self._token = token.strip()
        self._repo = repo
        self._timeout = timeout_seconds

    def request(self, method: str, path: str, payload: Mapping[str, Any] | None = None) -> dict[str, Any]:
        if not path.startswith("/") or path.startswith("//"):
            raise PolicyError("GitHub API path must be repository-relative")
        url = f"https://api.github.com/repos/{self._repo}{path}"
        data = None if payload is None else json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        request = Request(
            url,
            data=data,
            method=method.upper(),
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {self._token}",
                "X-GitHub-Api-Version": "2022-11-28",
                "Content-Type": "application/json",
                "User-Agent": "zcira-state-store/1.0",
            },
        )
        try:
            with urlopen(request, timeout=self._timeout) as response:
                raw = response.read()
        except HTTPError as exc:
            try:
                body = json.loads(exc.read().decode("utf-8"))
                message = body.get("message", "request rejected")
            except Exception:
                message = "request rejected"
            raise GitHubAPIError(exc.code, str(message)) from None
        except URLError:
            raise GitHubAPIError(0, "network unavailable") from None
        if not raw:
            return {}
        try:
            result = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise GitHubAPIError(502, "GitHub returned a non-JSON response") from None
        if not isinstance(result, dict):
            raise GitHubAPIError(502, "GitHub returned an unexpected response")
        return result


def validate_state_path(path: str) -> None:
    if not isinstance(path, str) or not path.startswith("state/") or not path.endswith(".json"):
        raise PolicyError("durable state adapter may write only state/*.json paths")
    parsed = PurePosixPath(path)
    if parsed.is_absolute() or ".." in parsed.parts or "." in parsed.parts or str(parsed) != path:
        raise PolicyError("state path traversal or non-canonical path")


class GitHubGitDataStore:
    """Atomic multi-file state commits using Git Data API and a non-force ref update.

    All writes are based on an expected branch-head SHA. Concurrent sibling commits
    cannot both advance the same branch head with force=false.
    """

    def __init__(self, transport: StateTransport, branch: str = CANONICAL_BRANCH):
        if branch != CANONICAL_BRANCH:
            raise PolicyError("state store branch is locked to main")
        self.transport = transport
        self.branch = branch

    def read_head(self) -> str:
        result = self.transport.request("GET", f"/git/ref/heads/{quote(self.branch, safe='')}")
        sha = result.get("object", {}).get("sha")
        validate_git_sha(sha)
        return sha

    def read_file(self, path: str, ref: str | None = None) -> str | None:
        validate_state_path(path)
        target_ref = ref or self.branch
        if target_ref != self.branch:
            validate_git_sha(target_ref)
        encoded_path = quote(path, safe="/")
        encoded_ref = quote(target_ref, safe="")
        try:
            result = self.transport.request("GET", f"/contents/{encoded_path}?ref={encoded_ref}")
        except GitHubAPIError as exc:
            if exc.status == 404:
                return None
            raise
        if result.get("type") != "file" or result.get("encoding") != "base64":
            raise GitHubAPIError(502, "state file response is not a base64 file")
        try:
            return base64.b64decode(result["content"], validate=False).decode("utf-8")
        except (KeyError, ValueError, UnicodeDecodeError):
            raise GitHubAPIError(502, "state file content is invalid") from None

    def commit_files(
        self,
        expected_head_sha: str,
        files: Mapping[str, str],
        message: str,
    ) -> dict[str, Any]:
        validate_git_sha(expected_head_sha)
        if not isinstance(message, str) or not message.strip() or len(message) > 200:
            raise PolicyError("state commit message must be non-empty and bounded")
        if not isinstance(files, Mapping) or not files:
            raise PolicyError("state commit requires at least one file")
        for path, content in files.items():
            validate_state_path(path)
            if not isinstance(content, str):
                raise PolicyError("state file contents must be UTF-8 text")

        current_head = self.read_head()
        if current_head != expected_head_sha:
            raise StaleCheckpoint("branch head changed before state commit; re-fetch and rebuild")

        parent = self.transport.request("GET", f"/git/commits/{expected_head_sha}")
        base_tree_sha = parent.get("tree", {}).get("sha")
        validate_git_sha(base_tree_sha)

        tree_entries = []
        blob_shas: dict[str, str] = {}
        for path, content in sorted(files.items()):
            blob = self.transport.request(
                "POST",
                "/git/blobs",
                {"content": content, "encoding": "utf-8"},
            )
            blob_sha = blob.get("sha")
            validate_git_sha(blob_sha)
            blob_shas[path] = blob_sha
            tree_entries.append({"path": path, "mode": "100644", "type": "blob", "sha": blob_sha})

        tree = self.transport.request(
            "POST",
            "/git/trees",
            {"base_tree": base_tree_sha, "tree": tree_entries},
        )
        tree_sha = tree.get("sha")
        validate_git_sha(tree_sha)

        commit = self.transport.request(
            "POST",
            "/git/commits",
            {"message": message, "tree": tree_sha, "parents": [expected_head_sha]},
        )
        commit_sha = commit.get("sha")
        validate_git_sha(commit_sha)

        try:
            self.transport.request(
                "PATCH",
                f"/git/refs/heads/{quote(self.branch, safe='')}",
                {"sha": commit_sha, "force": False},
            )
        except GitHubAPIError as exc:
            if exc.status in {409, 422}:
                raise BranchHeadConflict("branch changed during atomic state commit; orphan commit was not published") from None
            raise

        verified_head = self.read_head()
        if verified_head != commit_sha:
            raise BranchHeadConflict("branch head did not resolve to the proposed state commit")

        return {
            "base_commit_sha": expected_head_sha,
            "commit_sha": commit_sha,
            "tree_sha": tree_sha,
            "blob_shas": blob_shas,
            "branch": self.branch,
            "force_push": False,
        }
