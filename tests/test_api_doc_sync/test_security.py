import base64
import json
import re
import tempfile
import unittest
from pathlib import Path

from src.api_doc_sync.errors import (
    ArtifactError,
    DriftError,
    FetchError,
    ParseError,
    ReadinessError,
    ReportError,
    StartupError,
)
from src.api_doc_sync.model import (
    CanonicalApiModel,
    HeaderFact,
    OperationFact,
    ResponseFact,
    SchemaFact,
    deserialize_metadata,
    serialize_metadata,
)
from src.api_doc_sync.security import (
    REDACTION,
    create_safe_temp_directory,
    redact_headers,
    redact_text,
    redact_url,
    sanitize_for_metadata,
    sanitize_value,
    write_sanitized_text,
)


class SecuritySanitizationTests(unittest.TestCase):
    def test_metadata_base64_payload_has_no_original_secrets(self):
        bearer = "Bearer verification-bearer-token"
        api_key = "nested-api-key-12345"
        header_secret = "header-credential-987"
        password = "url-password-54321"

        model = CanonicalApiModel(
            openapi_version="3.1.0",
            operations=(
                OperationFact(
                    path="/secure",
                    method="GET",
                    summary="Ordinary operation summary",
                    responses=(
                        ResponseFact(
                            status="200",
                            description=f"{bearer}; ordinary response text",
                            headers=(
                                HeaderFact(
                                    name="Authorization",
                                    schema={"example": header_secret},
                                ),
                            ),
                            schemas=(
                                SchemaFact(
                                    name="SecureSchema",
                                    media_type="application/json",
                                    schema={
                                        "api_key": api_key,
                                        "password": password,
                                        "ordinary": "kept-value",
                                    },
                                ),
                            ),
                        ),
                    ),
                ),
            ),
            schemas=(
                SchemaFact(
                    name="SecureSchema",
                    schema={
                        "api_key": api_key,
                        "password": password,
                        "ordinary": "kept-value",
                    },
                ),
            ),
        )

        comment = serialize_metadata(model)
        match = re.search(
            r"api-doc-sync-metadata:([A-Za-z0-9_-]+={0,2})",
            comment,
        )
        self.assertIsNotNone(match)
        encoded = match.group(1)
        padded = encoded + "=" * (-len(encoded) % 4)
        decoded = json.loads(
            base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8")
        )
        decoded_text = json.dumps(decoded, sort_keys=True)

        for secret in (bearer, api_key, header_secret, password):
            self.assertNotIn(secret, decoded_text)
        self.assertIn("Ordinary operation summary", decoded_text)
        self.assertIn("ordinary response text", decoded_text)
        self.assertIn("kept-value", decoded_text)

        restored = deserialize_metadata(comment)
        description = restored.operations[0].responses[0].description
        self.assertIn("ordinary response text", description)
        self.assertNotIn("verification-bearer-token", description)

    def test_deserialization_sanitizes_manually_unsafe_metadata(self):
        payload = {
            "model_version": 1,
            "openapi_version": "3.1.0",
            "paths": [],
            "schema_count": 1,
            "operations": [
                {
                    "path": "/private",
                    "method": "GET",
                    "summary": "Ordinary summary",
                    "parameters": [],
                    "request_body": None,
                    "responses": [
                        {
                            "status": "200",
                            "description": "Bearer deserialize-bearer-secret",
                            "headers": [
                                {
                                    "name": "X-API-Key",
                                    "required": False,
                                    "schema": {"example": "deserialize-header-secret"},
                                }
                            ],
                            "schemas": [
                                {
                                    "name": "Private",
                                    "media_type": "application/json",
                                    "schema": {
                                        "client_secret": "deserialize-client-secret",
                                        "url": "https://user:deserialize-password@example.com/openapi?api_key=deserialize-api-key",
                                        "ordinary": "kept-value",
                                    },
                                }
                            ],
                        }
                    ],
                }
            ],
            "schemas": [],
        }
        encoded = base64.urlsafe_b64encode(
            json.dumps(payload, separators=(",", ":")).encode("utf-8")
        ).decode("ascii")
        markdown = f"<!-- api-doc-sync-metadata:{encoded} -->"

        restored = deserialize_metadata(markdown)
        restored_text = json.dumps(
            restored.to_dict(),
            sort_keys=True,
        )

        for secret in (
            "deserialize-bearer-secret",
            "deserialize-header-secret",
            "deserialize-client-secret",
            "deserialize-password",
            "deserialize-api-key",
        ):
            self.assertNotIn(secret, restored_text)
        self.assertIn("Ordinary summary", restored_text)
        self.assertIn("kept-value", restored_text)

    def test_redacts_bearer_basic_api_key_and_oauth_tokens(self):
        text = (
            "Authorization: Bearer bearer-secret "
            "Basic dXNlcjpwYXNz "
            "api_key=api-key-value "
            "access_token=oauth-access-token "
            "client_secret=oauth-client-secret"
        )

        result = redact_text(text)

        for secret in (
            "bearer-secret",
            "dXNlcjpwYXNz",
            "api-key-value",
            "oauth-access-token",
            "oauth-client-secret",
        ):
            self.assertNotIn(secret, result)
        self.assertIn(REDACTION, result)

    def test_redacts_known_secrets_everywhere(self):
        known = ("literal-password", "X7-GitHub-secret")
        result = redact_text(
            "literal-password was copied to X7-GitHub-secret",
            known,
        )

        self.assertNotIn("literal-password", result)
        self.assertNotIn("X7-GitHub-secret", result)

    def test_redacts_sensitive_headers(self):
        headers = redact_headers(
            {
                "Authorization": "Bearer secret",
                "X-API-Key": "api-secret",
                "Accept": "application/json",
            }
        )

        self.assertEqual(headers["Authorization"], REDACTION)
        self.assertEqual(headers["X-API-Key"], REDACTION)
        self.assertEqual(headers["Accept"], "application/json")

    def test_redacts_url_credentials_and_sensitive_query_values(self):
        url = (
            "https://user:password@auth.example.com/openapi"
            "?api_key=api-secret&format=json"
        )

        result = redact_url(url)

        self.assertNotIn("password", result)
        self.assertNotIn("api-secret", result)
        self.assertIn("api_key=", result)
        self.assertIn("format=json", result)

    def test_recursively_sanitizes_descriptions_and_nested_schemas(self):
        value = {
            "description": "Use Bearer nested-access-token",
            "schema": {
                "properties": {
                    "api_key": {"type": "string", "example": "schema-secret"},
                    "nested": {
                        "client_secret": "nested-client-secret",
                        "safe": "ordinary-value",
                    },
                },
            },
        }

        result = sanitize_value(value)

        serialized = str(result)
        self.assertNotIn("nested-access-token", serialized)
        self.assertNotIn("schema-secret", serialized)
        self.assertNotIn("nested-client-secret", serialized)
        self.assertIn("ordinary-value", serialized)

    def test_sanitizes_canonical_model_for_metadata(self):
        model = CanonicalApiModel(
            openapi_version="3.1.0",
            operations=(
                OperationFact(
                    path="/private",
                    method="get",
                    summary="access_token=secret-in-summary",
                    responses=(
                        ResponseFact(
                            status="200",
                            description="Authorization: Bearer secret-in-description",
                            headers=(),
                            schemas=(),
                        ),
                    ),
                ),
            ),
        )

        result = sanitize_for_metadata(model.to_dict())
        serialized = str(result)

        self.assertNotIn("secret-in-summary", serialized)
        self.assertNotIn("secret-in-description", serialized)
        self.assertIn(REDACTION, serialized)

    def test_sanitized_temp_file_contains_no_known_secret(self):
        with create_safe_temp_directory(prefix="security-test-") as directory:
            path = Path(directory) / "artifact.txt"
            write_sanitized_text(
                path,
                "response body with token=temporary-secret",
                known_secrets=("temporary-secret",),
            )

            content = path.read_text(encoding="utf-8")

        self.assertNotIn("temporary-secret", content)
        self.assertIn(REDACTION, content)

    def test_stage_errors_have_codes_without_raw_details(self):
        errors = (
            (StartupError(), "STARTUP_FAILED", "startup"),
            (ReadinessError(), "READINESS_FAILED", "readiness"),
            (FetchError(), "FETCH_FAILED", "fetch"),
            (ParseError(), "PARSE_FAILED", "parse"),
            (DriftError(), "DRIFT_FAILED", "drift"),
            (ArtifactError(), "ARTIFACT_FAILED", "artifact"),
            (ReportError(), "REPORT_FAILED", "report"),
        )

        for error, code, stage in errors:
            with self.subTest(code=code):
                self.assertEqual(error.code, code)
                self.assertEqual(error.stage.value, stage)
                self.assertIsNone(error.details)
                self.assertNotIn("secret", str(error).lower())


if __name__ == "__main__":
    unittest.main()
