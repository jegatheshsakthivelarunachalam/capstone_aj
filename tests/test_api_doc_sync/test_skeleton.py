import unittest

from src.api_doc_sync import (
    ApiDocSyncError,
    ConfigurationError,
    GenerationError,
    OpenApiError,
)
from src.api_doc_sync.errors import ApiDocSyncStage
from src.api_doc_sync.model import CanonicalApiModel, NOT_FOUND


class ApiDocSyncSkeletonTests(unittest.TestCase):
    def test_packages_can_import_independently(self):
        from src.doc_sync_capstone import profile

        self.assertTrue(callable(profile.main))

    def test_error_hierarchy_and_stage_are_available(self):
        error = ConfigurationError("Invalid configuration")

        self.assertIsInstance(error, ApiDocSyncError)
        self.assertEqual(error.stage, ApiDocSyncStage.PARSE)
        self.assertEqual(str(error), "Invalid configuration")

    def test_specialized_errors_use_expected_stages(self):
        openapi_error = OpenApiError(
            ApiDocSyncStage.FETCH,
            "OpenAPI unavailable",
        )
        generation_error = GenerationError("Could not generate Markdown")

        self.assertEqual(openapi_error.stage, ApiDocSyncStage.FETCH)
        self.assertEqual(
            generation_error.stage,
            ApiDocSyncStage.GENERATE,
        )

    def test_canonical_model_starts_empty_and_not_found_is_constant(self):
        model = CanonicalApiModel()

        self.assertEqual(model.facts, {})
        self.assertEqual(NOT_FOUND, "Not Found")

    def test_public_api_sync_exports_are_available(self):
        import src.api_doc_sync as api

        self.assertTrue(callable(api.load_config))
        self.assertTrue(callable(api.retrieve_openapi))
        self.assertTrue(callable(api.render_markdown))
        self.assertTrue(callable(api.ApplicationLifecycle))
        self.assertTrue(callable(api.CanonicalApiModel))
        self.assertTrue(callable(api.run))
        self.assertTrue(callable(api.cli_main))


if __name__ == "__main__":
    unittest.main()
