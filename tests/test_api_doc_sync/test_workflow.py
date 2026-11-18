import unittest
from pathlib import Path
import yaml


class WorkflowTests(unittest.TestCase):
    def test_api_sync_workflow_uses_approved_security_model(self):
        workflow = Path(".github/workflows/api-doc-sync.yml").read_text(
            encoding="utf-8"
        )

        self.assertIn("pull_request:", workflow)
        self.assertIn("windows-latest", workflow)
        self.assertIn("contents: read", workflow)
        self.assertIn("pull-requests: write", workflow)
        self.assertIn("retention-days: 5", workflow)
        self.assertIn("python -m pip install -e .", workflow)
        self.assertIn("python -m api_doc_sync", workflow)
        self.assertNotIn("pull_request_target:", workflow)
        self.assertNotIn("git push", workflow)
        self.assertNotIn("git commit", workflow)
        self.assertIn("continue-on-error: true", workflow)
        self.assertIn("github.event.pull_request.base.sha", workflow)
        self.assertIn("github.event.pull_request.head.sha", workflow)
        self.assertIn("pr-app", workflow)
        self.assertIn("listWorkflowRunArtifacts", workflow)
        self.assertIn("Suggested patch", workflow)
        self.assertIn("github.event.pull_request.base.sha", workflow)
        self.assertIn("github.event.pull_request.head.sha", workflow)
        self.assertIn("--baseline-root .", workflow)
        self.assertIn("continue-on-error: true", workflow)
        self.assertIn("const { owner, repo } = context.repo;", workflow)

    def test_workflow_and_doc_sync_yaml_are_safe_valid_yaml(self):
        workflow = yaml.safe_load(
            Path(".github/workflows/api-doc-sync.yml").read_text(
                encoding="utf-8"
            )
        )
        config = yaml.safe_load(
            Path(".github/doc-sync.yml").read_text(
                encoding="utf-8"
            )
        )

        self.assertIsInstance(workflow, dict)
        self.assertIn("jobs", workflow)
        self.assertIn("build", workflow["jobs"])
        self.assertIn("reporting", workflow["jobs"])
        self.assertIsInstance(config, dict)
        self.assertIn("startup_command", config)
        self.assertIn("openapi_url", config)
        self.assertIn("output_path", config)


if __name__ == "__main__":
    unittest.main()
