import tempfile
import unittest
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import Mock, patch

from src.api_doc_sync.cli import build_arg_parser, main, run
from src.api_doc_sync.model import CanonicalApiModel, OperationFact
from src.api_doc_sync.config import AuthConfig, DocSyncConfig
from src.api_doc_sync.errors import ArtifactError


class CliTests(unittest.TestCase):
    def test_module_invocation_help_succeeds(self):
        repository = Path(__file__).resolve().parents[2]
        environment = os.environ.copy()
        source = repository / "src"
        environment["PYTHONPATH"] = (
            str(source)
            + (os.pathsep + environment["PYTHONPATH"])
            if environment.get("PYTHONPATH")
            else str(source)
        )

        completed = subprocess.run(
            [sys.executable, "-m", "api_doc_sync", "--help"],
            cwd=repository,
            env=environment,
            capture_output=True,
            text=True,
            timeout=30,
        )

        self.assertEqual(completed.returncode, 0)
        self.assertIn("API documentation", completed.stdout)
        self.assertEqual(completed.stderr, "")

    def test_argument_parser_defaults(self):
        args = build_arg_parser().parse_args([])
        self.assertEqual(args.config, ".github/doc-sync.yml")
        self.assertIsNone(args.report)
        self.assertIsNone(args.patch)
        self.assertIsNone(args.app_root)

    def test_main_reports_unexpected_failure_safely(self):
        with patch("src.api_doc_sync.cli.run", side_effect=RuntimeError("secret response")):
            with patch("sys.stderr") as stderr:
                exit_code = main([])

        self.assertEqual(exit_code, 1)
        output = " ".join(str(call) for call in stderr.method_calls)
        self.assertNotIn("secret response", output)

    def test_report_write_failure_uses_artifact_stage_error(self):
        result = Mock(exit_code=0)
        result.report = {"has_drift": False}
        result.baseline_markdown = None
        result.candidate_markdown = "# API"
        with (
            patch("src.api_doc_sync.cli.run", return_value=result),
            patch(
                "src.api_doc_sync.cli.write_report_json",
                side_effect=ArtifactError("Drift report artifact could not be written."),
            ),
            patch("sys.stderr") as stderr,
        ):
            exit_code = main(["--report", "/tmp/report.json"])
        self.assertEqual(exit_code, 1)
        self.assertNotIn("traceback", " ".join(str(call) for call in stderr.method_calls).lower())

    def test_missing_baseline_returns_failure_and_candidate(self):
        model = CanonicalApiModel(
            openapi_version="3.1.0",
            operations=(OperationFact(path="/health", method="GET"),),
        )
        config = Mock(
            startup_command="python app.py",
            openapi_url="http://127.0.0.1/openapi.json",
            health_check_url=None,
            output_path="docs/api.md",
            shell="pwsh",
        )
        lifecycle = Mock()
        with (
            patch("src.api_doc_sync.cli.load_config", return_value=config),
            patch("src.api_doc_sync.cli.ApplicationLifecycle", return_value=lifecycle),
            patch("src.api_doc_sync.cli.retrieve_openapi", return_value=model),
            patch("src.api_doc_sync.cli.render_markdown", return_value="# API Reference"),
            patch("pathlib.Path.exists", return_value=False),
        ):
            result = run()

        lifecycle.start_and_wait.assert_called_once()
        lifecycle.stop.assert_called_once()
        self.assertEqual(result.exit_code, 1)
        self.assertTrue(result.report["missing_baseline"])

    def test_no_drift_returns_success(self):
        model = CanonicalApiModel(
            openapi_version="3.1.0",
            operations=(OperationFact(path="/health", method="GET"),),
        )
        candidate = "# API Reference\n"
        config = Mock(
            startup_command="python app.py",
            openapi_url="http://127.0.0.1/openapi.json",
            health_check_url=None,
            output_path="docs/api.md",
            shell="pwsh",
        )
        lifecycle = Mock()
        with tempfile.TemporaryDirectory() as directory:
            baseline = Path(directory) / "docs/api.md"
            baseline.parent.mkdir(parents=True)
            baseline.write_text(candidate, encoding="utf-8")
            config.output_path = str(baseline)
            with (
                patch("src.api_doc_sync.cli.load_config", return_value=config),
                patch("src.api_doc_sync.cli.ApplicationLifecycle", return_value=lifecycle),
                patch("src.api_doc_sync.cli.retrieve_openapi", return_value=model),
                patch("src.api_doc_sync.cli.render_markdown", return_value=candidate),
                patch("src.api_doc_sync.cli.detect_drift") as detect,
            ):
                detect.return_value = Mock(
                    has_drift=False,
                    changed_facts=(),
                    missing_facts=(),
                    path_count=1,
                    schema_count=0,
                )
                result = run()

        self.assertEqual(result.exit_code, 0)

    def test_baseline_root_is_separate_from_app_root(self):
        model = CanonicalApiModel(
            openapi_version="3.1.0",
            operations=(OperationFact(path="/health", method="GET"),),
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            app_root = root / "pr-app"
            baseline_root = root / "base"
            app_root.mkdir()
            (baseline_root / "docs").mkdir(parents=True)
            baseline = baseline_root / "docs" / "api.md"
            baseline.write_text("# API Reference\n", encoding="utf-8")
            config = DocSyncConfig(
                startup_command="python app.py",
                openapi_url="http://127.0.0.1/openapi.json",
                output_path="docs/api.md",
                health_check_url=None,
                shell="pwsh",
                auth=AuthConfig(),
            )
            lifecycle = Mock()
            with (
                patch("src.api_doc_sync.cli.load_config", return_value=config),
                patch("src.api_doc_sync.cli.ApplicationLifecycle", return_value=lifecycle),
                patch("src.api_doc_sync.cli.retrieve_openapi", return_value=model),
                patch("src.api_doc_sync.cli.render_markdown", return_value="# API Reference\n"),
                patch("src.api_doc_sync.cli.detect_drift") as detect,
            ):
                detect.return_value = Mock(
                    has_drift=False,
                    changed_facts=(),
                    missing_facts=(),
                    path_count=1,
                    schema_count=0,
                )
                result = run(
                    "pr-app/.github/doc-sync.yml",
                    str(app_root),
                    str(baseline_root),
                )
            self.assertEqual(result.baseline_markdown, "# API Reference\n")
        lifecycle.stop.assert_called_once()

    def test_app_root_is_used_for_startup_and_baseline(self):
        model = CanonicalApiModel(
            openapi_version="3.1.0",
            operations=(OperationFact(path="/health", method="GET"),),
        )
        with tempfile.TemporaryDirectory() as directory:
            app_root = Path(directory)
            baseline = app_root / "docs" / "api.md"
            baseline.parent.mkdir(parents=True)
            candidate = "# API Reference\n"
            baseline.write_text(candidate, encoding="utf-8")
            config = DocSyncConfig(
                startup_command="python app.py",
                openapi_url="http://127.0.0.1/openapi.json",
                output_path="docs/api.md",
                health_check_url=None,
                shell="pwsh",
                auth=AuthConfig(),
            )
            lifecycle = Mock()
            with (
                patch("src.api_doc_sync.cli.load_config", return_value=config),
                patch(
                    "src.api_doc_sync.cli.ApplicationLifecycle",
                    return_value=lifecycle,
                ) as lifecycle_type,
                patch("src.api_doc_sync.cli.retrieve_openapi", return_value=model),
                patch("src.api_doc_sync.cli.render_markdown", return_value=candidate),
                patch("src.api_doc_sync.cli.detect_drift") as detect,
            ):
                detect.return_value = Mock(
                    has_drift=False,
                    changed_facts=(),
                    missing_facts=(),
                    path_count=1,
                    schema_count=0,
                )
                result = run("pr-app/.github/doc-sync.yml", str(app_root))

            lifecycle_type.assert_called_once()
            lifecycle_kwargs = lifecycle_type.call_args.kwargs
            self.assertEqual(lifecycle_kwargs["working_directory"], str(app_root))
            self.assertEqual(result.exit_code, 0)


if __name__ == "__main__":
    unittest.main()
