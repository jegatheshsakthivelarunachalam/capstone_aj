import tempfile
import unittest
from pathlib import Path

from src.api_doc_sync.drift import (
    compare_models,
    detect_drift,
    load_baseline,
)
from src.api_doc_sync.markdown import render_markdown
from src.api_doc_sync.model import (
    CanonicalApiModel,
    OperationFact,
)
from src.api_doc_sync.errors import ParseError


class DriftTests(unittest.TestCase):
    def test_unchanged_markdown_has_no_drift(self):
        model = CanonicalApiModel(
            openapi_version="3.1.0",
            operations=(
                OperationFact(path="/pets", method="GET", summary="List pets"),
            ),
        )
        markdown = render_markdown(model)

        result = detect_drift(markdown, model)

        self.assertFalse(result.has_drift)
        self.assertEqual(result.changed_facts, ())

    def test_operation_change_is_drift(self):
        baseline = CanonicalApiModel(
            openapi_version="3.1.0",
            operations=(OperationFact(path="/pets", method="GET"),),
        )
        candidate = CanonicalApiModel(
            openapi_version="3.1.0",
            operations=(OperationFact(path="/pets", method="POST"),),
        )

        result = compare_models(baseline, candidate)

        self.assertTrue(result.has_drift)
        self.assertIn("operations", result.changed_facts)

    def test_missing_baseline_is_explicit_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "docs" / "api.md"
            with self.assertRaises(ParseError):
                load_baseline(str(path))

    def test_invalid_baseline_metadata_is_explicit_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "api.md"
            path.write_text("# API\n", encoding="utf-8")
            with self.assertRaises(ParseError):
                load_baseline(str(path))

    def test_missing_fields_are_reported(self):
        model = CanonicalApiModel(openapi_version="3.1.0")

        result = compare_models(model, model)

        self.assertTrue(result.missing_facts)


if __name__ == "__main__":
    unittest.main()
