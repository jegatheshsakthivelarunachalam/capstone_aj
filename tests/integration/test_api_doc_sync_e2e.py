import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.api_doc_sync.cli import run
from src.api_doc_sync.config import AuthConfig, DocSyncConfig
from src.api_doc_sync.markdown import render_markdown
from src.api_doc_sync.openapi import extract_openapi_model
from tests.integration.mock_app import start_mock_application


class EndToEndWorkflowTests(unittest.TestCase):
    def test_mock_application_json_flow_no_drift(self):
        application, base_url = start_mock_application()
        try:
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                output = root / "docs" / "api.md"
                output.parent.mkdir(parents=True)

                config = DocSyncConfig(
                    startup_command="python -m tests.integration.mock_app",
                    openapi_url=base_url + "/openapi.json",
                    output_path=str(output),
                    health_check_url=base_url + "/health",
                    shell="pwsh",
                    auth=AuthConfig(mode="none"),
                )
                with (
                    patch("src.api_doc_sync.cli.load_config", return_value=config),
                    patch(
                        "src.api_doc_sync.lifecycle.ApplicationLifecycle.start_and_wait",
                        autospec=True,
                    ),
                    patch(
                        "src.api_doc_sync.lifecycle.ApplicationLifecycle.stop",
                        autospec=True,
                    ),
                ):
                    model = extract_openapi_model(application.openapi_document)
                    output.write_text(render_markdown(model), encoding="utf-8")
                    result = run(str(root / ".github" / "doc-sync.yml"))

                self.assertEqual(result.exit_code, 0)
                self.assertFalse(result.report["has_drift"])
                self.assertFalse(result.report["missing_baseline"])
        finally:
            application.stop()

    def test_missing_baseline_returns_replacement_candidate(self):
        application, base_url = start_mock_application()
        try:
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                output = root / "docs" / "api.md"
                config = DocSyncConfig(
                    startup_command="python -m tests.integration.mock_app",
                    openapi_url=base_url + "/openapi.json",
                    output_path=str(output),
                    health_check_url=base_url + "/health",
                    shell="pwsh",
                    auth=AuthConfig(mode="none"),
                )
                with (
                    patch("src.api_doc_sync.cli.load_config", return_value=config),
                    patch(
                        "src.api_doc_sync.lifecycle.ApplicationLifecycle.start_and_wait",
                        autospec=True,
                    ),
                    patch(
                        "src.api_doc_sync.lifecycle.ApplicationLifecycle.stop",
                        autospec=True,
                    ),
                ):
                    result = run(str(root / ".github" / "doc-sync.yml"))

                self.assertEqual(result.exit_code, 1)
                self.assertTrue(result.report["missing_baseline"])
                self.assertIn("# API Reference", result.candidate_markdown)
        finally:
            application.stop()

    def test_endpoint_change_detected_as_drift(self):
        application, base_url = start_mock_application()
        try:
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                output = root / "docs" / "api.md"
                output.parent.mkdir(parents=True)
                changed_document = {
                    "openapi": "3.1.0",
                    "paths": {
                        "/health": {
                            "get": {
                                "summary": "Changed health check",
                                "responses": {
                                    "200": {"description": "Changed response"}
                                },
                            }
                        }
                    },
                }
                baseline_model = extract_openapi_model(application.openapi_document)
                from src.api_doc_sync.markdown import render_markdown

                output.write_text(
                    render_markdown(baseline_model),
                    encoding="utf-8",
                )
                config = DocSyncConfig(
                    startup_command="python -m tests.integration.mock_app",
                    openapi_url=base_url + "/openapi.json",
                    output_path=str(output),
                    health_check_url=base_url + "/health",
                    shell="pwsh",
                    auth=AuthConfig(mode="none"),
                )
                with (
                    patch("src.api_doc_sync.cli.load_config", return_value=config),
                    patch(
                        "src.api_doc_sync.lifecycle.ApplicationLifecycle.start_and_wait",
                        autospec=True,
                    ),
                    patch(
                        "src.api_doc_sync.lifecycle.ApplicationLifecycle.stop",
                        autospec=True,
                    ),
                    patch(
                        "src.api_doc_sync.openapi.OpenAPIFetcher.fetch",
                        return_value=json.dumps(changed_document).encode("utf-8"),
                    ),
                ):
                    result = run(str(root / ".github" / "doc-sync.yml"))

                self.assertEqual(result.exit_code, 1)
                self.assertTrue(result.report["has_drift"])
        finally:
            application.stop()


if __name__ == "__main__":
    unittest.main()
