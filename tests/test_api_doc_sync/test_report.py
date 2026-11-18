import tempfile
import unittest
from unittest import mock
from pathlib import Path

from src.api_doc_sync.drift import DriftResult
from src.api_doc_sync.github_report import (
    build_github_report,
    build_unified_diff,
    write_patch,
    write_patch_text,
    write_report_json,
)
from src.api_doc_sync.errors import ArtifactError


class GitHubReportTests(unittest.TestCase):
    def test_builds_sanitized_unified_diff(self):
        baseline = "# API\n\nOld text\n"
        candidate = "# API\n\nBearer report-secret\n"

        diff = build_unified_diff(
            baseline,
            candidate,
        )

        self.assertTrue(diff.has_changes)
        self.assertIn("--- a/docs/api.md", diff.text)
        self.assertIn("+++ b/docs/api.md", diff.text)
        self.assertNotIn("report-secret", diff.text)

    def test_builds_comment_with_counts_and_links(self):
        drift = DriftResult(
            has_drift=True,
            changed_facts=("operations",),
            missing_facts=("1 missing field(s)",),
            path_count=2,
            schema_count=3,
        )
        report = build_github_report(
            drift,
            "# API\n",
            "# API\n",
            workflow_url="https://example.com/workflow",
            artifact_url="https://example.com/artifact",
        )

        self.assertIn("api-doc-sync-drift", report.comment)
        self.assertIn("Paths: 2", report.comment)
        self.assertIn("Schemas: 3", report.comment)
        self.assertIn("Workflow run", report.comment)
        self.assertIn("Suggested patch", report.comment)

    def test_builds_comment_without_artifact_url(self):
        drift = DriftResult(
            has_drift=True,
            changed_facts=("operations",),
            missing_facts=(),
            path_count=1,
            schema_count=1,
        )
        report = build_github_report(
            drift,
            "# API\n",
            "# API changed\n",
            workflow_url="https://example.com/workflow",
        )
        self.assertIn("Workflow run", report.comment)
        self.assertNotIn("Suggested patch", report.comment)

    def test_builds_comment_with_artifact_url(self):
        drift = DriftResult(
            has_drift=True,
            changed_facts=("operations",),
            missing_facts=(),
            path_count=1,
            schema_count=1,
        )
        report = build_github_report(
            drift,
            "# API\n",
            "# API changed\n",
            workflow_url="https://example.com/workflow",
            artifact_url="https://example.com/artifacts/123",
        )
        self.assertIn("Suggested patch", report.comment)
        self.assertIn("https://example.com/artifacts/123", report.comment)

    def test_patch_write_is_relative(self):
        drift = DriftResult(
            has_drift=True,
            changed_facts=("operations",),
            missing_facts=(),
            path_count=1,
            schema_count=1,
        )
        report = build_github_report(drift, "old", "new")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "artifacts" / "api.patch"
            written = write_patch(str(path), report)
            self.assertTrue(Path(written).exists())
            self.assertNotIn("secret", path.read_text(encoding="utf-8"))

    def test_report_write_failure_is_artifact_error(self):
        with mock.patch(
            "pathlib.Path.write_text",
            side_effect=OSError("disk full"),
        ):
            with self.assertRaises(ArtifactError):
                write_report_json("/tmp/report.json", {"has_drift": True})

    def test_patch_write_failure_is_artifact_error(self):
        with mock.patch(
            "pathlib.Path.write_text",
            side_effect=OSError("disk full"),
        ):
            with self.assertRaises(ArtifactError):
                write_patch_text("/tmp/docs-api.patch", "--- diff")


if __name__ == "__main__":
    unittest.main()
