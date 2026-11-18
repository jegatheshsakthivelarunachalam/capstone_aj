import tempfile
import unittest
import os
from pathlib import Path

from src.api_doc_sync.markdown import (
    MAX_MARKDOWN_LINES,
    render_markdown,
    write_markdown,
)
from src.api_doc_sync.model import (
    CanonicalApiModel,
    OperationFact,
    ParameterFact,
    RequestBodyFact,
    ResponseFact,
    SchemaFact,
)


class MarkdownTests(unittest.TestCase):
    def test_approved_markdown_limits_are_declared(self):
        from src.api_doc_sync.markdown import (
            MAX_MARKDOWN_BYTES,
            MAX_MARKDOWN_LINES,
        )

        self.assertEqual(MAX_MARKDOWN_BYTES, 5 * 1024 * 1024)
        self.assertEqual(MAX_MARKDOWN_LINES, 50_000)

    def test_markdown_line_limit_is_enforced(self):
        from unittest import mock
        from src.api_doc_sync import markdown as markdown_module
        from src.api_doc_sync.errors import GenerationError

        model = CanonicalApiModel(openapi_version="3.1.0")
        with mock.patch.object(markdown_module, "MAX_MARKDOWN_LINES", 3):
            with self.assertRaises(GenerationError):
                render_markdown(model)

    def test_markdown_byte_limit_is_enforced(self):
        from unittest import mock
        from src.api_doc_sync import markdown as markdown_module
        from src.api_doc_sync.errors import GenerationError

        model = CanonicalApiModel(openapi_version="3.1.0")
        with mock.patch.object(markdown_module, "MAX_MARKDOWN_BYTES", 20):
            with self.assertRaises(GenerationError):
                render_markdown(model)

    def sample_model(self):
        return CanonicalApiModel(
            openapi_version="3.1.0",
            operations=(
                OperationFact(
                    path="/pets",
                    method="GET",
                    summary="List pets",
                    parameters=(
                        ParameterFact(
                            name="limit",
                            location="query",
                            required=False,
                            schema={"type": "integer"},
                        ),
                    ),
                    request_body=RequestBodyFact(
                        required=True,
                        schemas=(
                            SchemaFact(
                                name="Pet",
                                media_type="application/json",
                                schema={"type": "object"},
                            ),
                        ),
                    ),
                    responses=(
                        ResponseFact(
                            status="200",
                            description="OK",
                        ),
                    ),
                ),
            ),
            schemas=(
                SchemaFact(
                    name="Pet",
                    schema={"type": "object", "properties": {"name": {"type": "string"}}},
                ),
            ),
        )

    def test_renders_approved_fields_and_metadata(self):
        markdown = render_markdown(self.sample_model())

        self.assertIn("# API Reference", markdown)
        self.assertIn("api-doc-sync-metadata:", markdown)
        self.assertIn("`GET /pets`", markdown)
        self.assertIn("List pets", markdown)
        self.assertIn("limit", markdown)
        self.assertIn("application/json", markdown)
        self.assertIn("Status 200", markdown)
        self.assertIn("Pet", markdown)

    def test_missing_fields_render_not_found(self):
        markdown = render_markdown(CanonicalApiModel(openapi_version="3.0.3"))

        self.assertIn("Not Found", markdown)

    def test_secret_like_text_is_redacted(self):
        model = CanonicalApiModel(
            openapi_version="3.1.0",
            operations=(
                OperationFact(
                    path="/private",
                    method="GET",
                    summary="Authorization: Bearer markdown-secret",
                    responses=(
                        ResponseFact(
                            status="200",
                            description="Ordinary text",
                        ),
                    ),
                ),
            ),
        )

        markdown = render_markdown(model)

        self.assertNotIn("markdown-secret", markdown)
        self.assertIn("ordinary text", markdown.lower())

    def test_markdown_write_to_relative_path(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "docs" / "api.md"
            previous = os.getcwd()
            os.chdir(directory)
            try:
                markdown = write_markdown("docs/api.md", self.sample_model())
            finally:
                os.chdir(previous)

            self.assertIn("# API Reference", markdown)
            self.assertTrue(target.exists())

    def test_write_markdown_rejects_absolute_path(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "api.md"
            from src.api_doc_sync.errors import GenerationError

            with self.assertRaises(GenerationError):
                write_markdown(str(target), self.sample_model())


if __name__ == "__main__":
    unittest.main()
