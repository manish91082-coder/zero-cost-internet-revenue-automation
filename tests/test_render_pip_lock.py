import json
import tempfile
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from render_pip_lock import LockReportError, render_lock

LANGGRAPH_SHA = "0f8ebec55a58667e40474a0e55bdb4f06a8c7a1d98cde2b7c8d996a2ee78fe3f"
OTHER_SHA = "a" * 64


def wheel(name, version, digest, url=None):
    return {
        "metadata": {"name": name, "version": version},
        "download_info": {
            "url": url or f"https://files.pythonhosted.org/packages/example/{name}-{version}-py3-none-any.whl",
            "archive_info": {"hashes": {"sha256": digest}},
        },
    }


class RenderPipLockTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.report = self.root / "report.json"
        self.expected = self.root / "requirements-langgraph.txt"
        self.expected.write_text(
            f"langgraph==1.2.22 --hash=sha256:{LANGGRAPH_SHA}\n", encoding="utf-8"
        )

    def tearDown(self):
        self.temp.cleanup()

    def write_report(self, entries):
        self.report.write_text(json.dumps({"install": entries}), encoding="utf-8")

    def test_renders_sorted_exact_hash_locked_packages(self):
        self.write_report([
            wheel("LangGraph", "1.2.22", LANGGRAPH_SHA),
            wheel("JSONSchema", "4.25.1", OTHER_SHA),
        ])
        rendered = render_lock(self.report, self.expected, "linux-x86_64-cp312")
        self.assertLess(rendered.index("jsonschema=="), rendered.index("langgraph=="))
        self.assertIn(f"langgraph==1.2.22 --hash=sha256:{LANGGRAPH_SHA}", rendered)
        self.assertIn("# Target: linux-x86_64-cp312", rendered)

    def test_rejects_missing_sha256(self):
        entry = wheel("langgraph", "1.2.22", LANGGRAPH_SHA)
        entry["download_info"]["archive_info"]["hashes"] = {}
        self.write_report([entry])
        with self.assertRaises(LockReportError):
            render_lock(self.report, self.expected, "linux-x86_64-cp312")

    def test_rejects_unapproved_host(self):
        self.write_report([wheel("langgraph", "1.2.22", LANGGRAPH_SHA, "https://example.com/langgraph.whl")])
        with self.assertRaises(LockReportError):
            render_lock(self.report, self.expected, "linux-x86_64-cp312")

    def test_rejects_source_distribution(self):
        self.write_report([wheel("langgraph", "1.2.22", LANGGRAPH_SHA, "https://files.pythonhosted.org/packages/langgraph.tar.gz")])
        with self.assertRaises(LockReportError):
            render_lock(self.report, self.expected, "linux-x86_64-cp312")

    def test_rejects_mismatched_expected_wheel(self):
        self.write_report([wheel("langgraph", "1.2.22", OTHER_SHA)])
        with self.assertRaises(LockReportError):
            render_lock(self.report, self.expected, "linux-x86_64-cp312")

    def test_rejects_conflicting_duplicate_package(self):
        self.write_report([
            wheel("langgraph", "1.2.22", LANGGRAPH_SHA),
            wheel("langgraph", "1.2.23", OTHER_SHA),
        ])
        with self.assertRaises(LockReportError):
            render_lock(self.report, self.expected, "linux-x86_64-cp312")

    def test_rejects_empty_install_report(self):
        self.write_report([])
        with self.assertRaises(LockReportError):
            render_lock(self.report, self.expected, "linux-x86_64-cp312")

    def test_rejects_unpinned_expected_requirement(self):
        self.expected.write_text("langgraph>=1.2\n", encoding="utf-8")
        self.write_report([wheel("langgraph", "1.2.22", LANGGRAPH_SHA)])
        with self.assertRaises(LockReportError):
            render_lock(self.report, self.expected, "linux-x86_64-cp312")


if __name__ == "__main__":
    unittest.main()
