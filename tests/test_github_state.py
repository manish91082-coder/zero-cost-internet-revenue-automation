import base64
import hashlib
import json
import sys
import unittest
from pathlib import Path
from urllib.parse import urlsplit, parse_qs, unquote

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from zcira_control.github_state import (
    BranchHeadConflict, GitHubAPIError, GitHubGitDataStore, validate_state_path,
)
from zcira_control.checkpoints import StaleCheckpoint
from zcira_control.policy import PolicyError


def git_blob_sha(content):
    raw = content.encode("utf-8")
    return hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()


class FakeTransport:
    def __init__(self):
        self.head = "a" * 40
        self.trees = {"b" * 40: {}}
        self.commits = {self.head: {"tree": {"sha": "b" * 40}, "parents": []}}
        self.blobs = {}
        self.race_before_patch = False
        self.blob_posts = 0

    def _concurrent_commit(self):
        parent = self.head
        tree = self.commits[parent]["tree"]["sha"]
        sha = hashlib.sha1((parent + "concurrent").encode()).hexdigest()
        self.commits[sha] = {"tree": {"sha": tree}, "parents": [parent]}
        self.head = sha

    def request(self, method, path, payload=None):
        method = method.upper()
        if method == "GET" and path == "/git/ref/heads/main":
            return {"object": {"sha": self.head}}
        if method == "GET" and path.startswith("/git/commits/"):
            sha = path.rsplit("/", 1)[-1]
            return self.commits[sha]
        if method == "GET" and path.startswith("/contents/"):
            parsed = urlsplit(path)
            file_path = unquote(parsed.path[len("/contents/"):])
            ref = parse_qs(parsed.query)["ref"][0]
            commit_sha = self.head if ref == "main" else ref
            tree_sha = self.commits[commit_sha]["tree"]["sha"]
            blob_sha = self.trees[tree_sha].get(file_path)
            if blob_sha is None:
                raise GitHubAPIError(404, "not found")
            return {
                "type": "file",
                "encoding": "base64",
                "content": base64.b64encode(self.blobs[blob_sha].encode()).decode(),
            }
        if method == "POST" and path == "/git/blobs":
            self.blob_posts += 1
            content = payload["content"]
            sha = git_blob_sha(content)
            self.blobs[sha] = content
            return {"sha": sha}
        if method == "POST" and path == "/git/trees":
            tree = dict(self.trees[payload["base_tree"]])
            for entry in payload["tree"]:
                tree[entry["path"]] = entry["sha"]
            serialized = json.dumps(tree, sort_keys=True)
            sha = hashlib.sha1(serialized.encode()).hexdigest()
            self.trees[sha] = tree
            return {"sha": sha}
        if method == "POST" and path == "/git/commits":
            sha = hashlib.sha1(json.dumps(payload, sort_keys=True).encode()).hexdigest()
            self.commits[sha] = {
                "tree": {"sha": payload["tree"]},
                "parents": [{"sha": parent} for parent in payload["parents"]],
            }
            return {"sha": sha}
        if method == "PATCH" and path == "/git/refs/heads/main":
            if self.race_before_patch:
                self.race_before_patch = False
                self._concurrent_commit()
            proposed = self.commits[payload["sha"]]
            parents = proposed["parents"]
            parent_sha = parents[0]["sha"] if parents and isinstance(parents[0], dict) else parents[0]
            if payload["force"] is not False or parent_sha != self.head:
                raise GitHubAPIError(422, "non-fast-forward")
            self.head = payload["sha"]
            return {"object": {"sha": self.head}}
        raise AssertionError(f"unexpected fake request: {method} {path}")


class GitHubStateStoreTests(unittest.TestCase):
    def setUp(self):
        self.transport = FakeTransport()
        self.store = GitHubGitDataStore(self.transport)

    def test_two_files_are_committed_atomically_and_read_back(self):
        base = self.store.read_head()
        object_content = '{"id":"x"}'
        object_path = "state/objects/" + hashlib.sha256(object_content.encode()).hexdigest() + ".json"
        result = self.store.commit_files(
            base,
            {
                "state/manifest.v1.json": '{"generation":0}',
                object_path: object_content,
            },
            "test atomic state commit",
        )
        self.assertEqual(self.store.read_head(), result["commit_sha"])
        self.assertEqual(self.store.read_file("state/manifest.v1.json", result["commit_sha"]), '{"generation":0}')
        self.assertEqual(self.store.read_file(object_path, result["commit_sha"]), object_content)
        self.assertFalse(result["force_push"])

    def test_stale_head_is_rejected_before_any_blob_is_created(self):
        old = self.store.read_head()
        self.transport._concurrent_commit()
        before = self.transport.blob_posts
        with self.assertRaises(StaleCheckpoint):
            self.store.commit_files(old, {"state/objects/" + hashlib.sha256(b"{}").hexdigest() + ".json": "{}"}, "stale")
        self.assertEqual(self.transport.blob_posts, before)

    def test_non_fast_forward_race_is_rejected(self):
        base = self.store.read_head()
        self.transport.race_before_patch = True
        with self.assertRaises(BranchHeadConflict):
            self.store.commit_files(base, {"state/objects/" + hashlib.sha256(b"{}").hexdigest() + ".json": "{}"}, "race")
        self.assertNotEqual(self.store.read_head(), base)

    def test_only_state_json_paths_are_writable(self):
        with self.assertRaises(PolicyError):
            validate_state_path("config/mission_registry.v1.json")
        with self.assertRaises(PolicyError):
            validate_state_path("state/../secrets/token.json")
        with self.assertRaises(PolicyError):
            validate_state_path("state/notes.txt")

    def test_exact_evidence_paths_are_allowed_but_arbitrary_evidence_paths_are_denied(self):
        validate_state_path("evidence/snapshots/sha256/" + "a" * 64 + ".json")
        validate_state_path("evidence/proposals/sha256/" + "b" * 64 + ".json")
        with self.assertRaises(PolicyError):
            validate_state_path("evidence/snapshots/raw-page.html")
        with self.assertRaises(PolicyError):
            validate_state_path("evidence/proposals/sha256/not-a-digest.json")

    def test_evidence_content_address_must_match_exact_sha256_and_fetches_back(self):
        base = self.store.read_head()
        content = '{"kind":"metadata-only-snapshot"}'
        digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
        path = f"evidence/snapshots/sha256/{digest}.json"
        result = self.store.commit_files(base, {path: content}, "test evidence snapshot commit")
        self.assertEqual(self.store.read_file(path, result["commit_sha"]), content)
        bad_path = "evidence/proposals/sha256/" + ("f" * 64) + ".json"
        with self.assertRaises(PolicyError):
            self.store.commit_files(self.store.read_head(), {bad_path: content}, "reject mismatched evidence digest")

    def test_object_path_must_match_content_sha256(self):
        base = self.store.read_head()
        with self.assertRaises(PolicyError):
            self.store.commit_files(base, {"state/objects/" + ("f" * 64) + ".json": "{}"}, "bad object hash")

    def test_state_files_must_be_canonical_json_objects(self):
        base = self.store.read_head()
        with self.assertRaises(PolicyError):
            self.store.commit_files(base, {"state/manifest.v1.json": "{ \"x\": 1 }"}, "non-canonical")
        with self.assertRaises(PolicyError):
            self.store.commit_files(base, {"state/manifest.v1.json": "[]"}, "not object")

    def test_branch_is_locked_to_main(self):
        from zcira_control.github_state import GitHubGitDataStore
        with self.assertRaises(PolicyError):
            GitHubGitDataStore(self.transport, branch="other")


if __name__ == "__main__":
    unittest.main()
