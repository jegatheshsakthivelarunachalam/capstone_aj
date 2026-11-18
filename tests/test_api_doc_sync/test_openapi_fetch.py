import json
import unittest
from unittest.mock import Mock

from src.api_doc_sync.config import AuthConfig
from src.api_doc_sync.errors import FetchError, ParseError
from src.api_doc_sync.openapi import (
    AuthenticationAdapter,
    OpenAPIFetcher,
    parse_openapi_document,
)


class MockResponse:
    def __init__(self, content: bytes, status: int = 200):
        self.content = content
        self.status = status
        self.offset = 0

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self, size: int = -1):
        if self.offset >= len(self.content):
            return b""
        if size < 0:
            size = len(self.content)
        chunk = self.content[self.offset:self.offset + size]
        self.offset += len(chunk)
        return chunk


class AuthenticationAdapterTests(unittest.TestCase):
    def test_none_auth_returns_no_headers(self):
        result = AuthenticationAdapter(AuthConfig(mode="none")).headers()
        self.assertEqual(result.headers, {})

    def test_bearer_auth_reads_environment_secret_name(self):
        auth = AuthConfig(
            mode="bearer",
            secret_names={"token": "OPENAPI_BEARER"},
        )
        result = AuthenticationAdapter(
            auth,
            {"OPENAPI_BEARER": "bearer-value"},
        ).headers()
        self.assertEqual(
            result.headers,
            {"Authorization": "Bearer bearer-value"},
        )

    def test_basic_auth_reads_both_secrets(self):
        auth = AuthConfig(
            mode="basic",
            secret_names={
                "username": "OPENAPI_USERNAME",
                "password": "OPENAPI_PASSWORD",
            },
        )
        result = AuthenticationAdapter(
            auth,
            {
                "OPENAPI_USERNAME": "user",
                "OPENAPI_PASSWORD": "password",
            },
        ).headers()
        self.assertTrue(result.headers["Authorization"].startswith("Basic "))

    def test_api_key_auth_uses_configured_header(self):
        auth = AuthConfig(
            mode="api_key",
            header_name="X-API-Key",
            secret_names={"header_value": "OPENAPI_API_KEY"},
        )
        result = AuthenticationAdapter(
            auth,
            {"OPENAPI_API_KEY": "api-value"},
        ).headers()
        self.assertEqual(result.headers, {"X-API-Key": "api-value"})

    def test_missing_secret_fails_safely(self):
        auth = AuthConfig(
            mode="bearer",
            secret_names={"token": "OPENAPI_BEARER"},
        )
        with self.assertRaises(FetchError) as raised:
            AuthenticationAdapter(auth, {}).headers()
        self.assertNotIn("OPENAPI_BEARER", str(raised.exception))

    def test_oauth2_acquires_bearer_header(self):
        auth = AuthConfig(
            mode="oauth2_client_credentials",
            token_url="https://auth.example.com/token",
            secret_names={
                "client_id": "OAUTH_CLIENT_ID",
                "client_secret": "OAUTH_CLIENT_SECRET",
            },
            scopes=("read:api",),
        )
        token_response = MockResponse(
            json.dumps({"access_token": "oauth-access-token"}).encode("utf-8")
        )
        opener = Mock(return_value=token_response)

        result = AuthenticationAdapter(
            auth,
            {
                "OAUTH_CLIENT_ID": "client-id",
                "OAUTH_CLIENT_SECRET": "client-secret",
            },
        ).oauth2_headers(opener)

        self.assertEqual(
            result.headers,
            {"Authorization": "Bearer oauth-access-token"},
        )

    def test_oauth2_token_failure_is_sanitized(self):
        auth = AuthConfig(
            mode="oauth2_client_credentials",
            token_url="https://auth.example.com/token",
            secret_names={
                "client_id": "OAUTH_CLIENT_ID",
                "client_secret": "OAUTH_CLIENT_SECRET",
            },
        )
        opener = Mock(
            return_value=MockResponse(
                b'{"error":"raw oauth response"}',
                status=400,
            )
        )

        with self.assertRaises(FetchError) as raised:
            AuthenticationAdapter(
                auth,
                {
                    "OAUTH_CLIENT_ID": "client-id",
                    "OAUTH_CLIENT_SECRET": "client-secret",
                },
            ).oauth2_headers(opener)

        self.assertNotIn("raw oauth response", str(raised.exception))


class OpenAPIFetcherTests(unittest.TestCase):
    def test_fetches_json_with_accept_and_auth_header(self):
        opener = Mock(
            return_value=MockResponse(
                json.dumps({"openapi": "3.1.0", "paths": {}}).encode("utf-8")
            )
        )
        fetcher = OpenAPIFetcher(opener=opener)

        content = fetcher.fetch(
            "http://127.0.0.1:8000/openapi.json",
            AuthConfig(),
        )

        self.assertIn(b'"openapi"', content)
        request = opener.call_args.args[0]
        self.assertIn("application/json", request.get_header("Accept"))

    def test_rejects_relative_and_credential_urls(self):
        fetcher = OpenAPIFetcher(opener=Mock())
        with self.assertRaises(FetchError):
            fetcher.fetch("/openapi.json", AuthConfig())
        with self.assertRaises(FetchError):
            fetcher.fetch(
                "https://user:password@example.com/openapi.json",
                AuthConfig(),
            )

    def test_retries_four_total_attempts(self):
        opener = Mock(side_effect=OSError("unavailable"))
        fetcher = OpenAPIFetcher(opener=opener, sleep=Mock())

        with self.assertRaises(FetchError):
            fetcher.fetch(
                "http://127.0.0.1:8000/openapi.json",
                AuthConfig(),
            )

        self.assertEqual(opener.call_count, 4)

    def test_http_4xx_and_5xx_fail_safely_after_retries(self):
        for status in (404, 503):
            with self.subTest(status=status):
                opener = Mock(
                    return_value=MockResponse(
                        b'{"error":"raw response body"}',
                        status=status,
                    )
                )
                fetcher = OpenAPIFetcher(opener=opener, sleep=Mock())

                with self.assertRaises(FetchError) as raised:
                    fetcher.fetch(
                        "http://127.0.0.1:8000/openapi.json",
                        AuthConfig(),
                    )

                self.assertNotIn("raw response body", str(raised.exception))
                self.assertEqual(opener.call_count, 4)

    def test_rejects_content_over_ten_mb(self):
        opener = Mock(return_value=MockResponse(b"x" * (10 * 1024 * 1024 + 1)))
        fetcher = OpenAPIFetcher(opener=opener)

        with self.assertRaisesRegex(FetchError, "10 MB"):
            fetcher.fetch(
                "http://127.0.0.1:8000/openapi.json",
                AuthConfig(),
            )


class OpenAPIDocumentParserTests(unittest.TestCase):
    def test_parses_json(self):
        spec = parse_openapi_document(
            json.dumps({"openapi": "3.1.0", "paths": {}}).encode("utf-8")
        )
        self.assertEqual(spec["openapi"], "3.1.0")

    def test_rejects_empty_document(self):
        with self.assertRaises(ParseError):
            parse_openapi_document(b"")

    def test_rejects_invalid_yaml(self):
        with self.assertRaises(ParseError):
            parse_openapi_document(b"openapi: [")

    def test_parses_simple_yaml(self):
        yaml = b"openapi: 3.0.3\npaths:\n  /health:\n    get:\n      responses:\n        '200':\n          description: OK\n"
        spec = parse_openapi_document(yaml)
        self.assertEqual(spec["openapi"], "3.0.3")
        self.assertIn("/health", spec["paths"])

    def test_json_and_yaml_documents_extract_equivalently(self):
        json_spec = parse_openapi_document(
            json.dumps(
                {
                    "openapi": "3.1.0",
                    "paths": {
                        "/health": {
                            "get": {
                                "summary": "Health",
                                "responses": {
                                    "200": {"description": "OK"}
                                },
                            }
                        }
                    },
                }
            ).encode("utf-8")
        )
        yaml_spec = parse_openapi_document(
            b'openapi: 3.1.0\npaths:\n  /health:\n    get:\n      summary: Health\n      responses:\n        "200":\n          description: OK\n'
        )
        self.assertEqual(json_spec, yaml_spec)

    def test_rejects_unsafe_yaml_tags(self):
        unsafe = b"openapi: 3.1.0\npaths: !!python/object/apply:os.system [\"echo unsafe\"]\n"
        with self.assertRaises(ParseError):
            parse_openapi_document(unsafe)

    def test_rejects_recursive_yaml_alias(self):
        recursive = b"&a [*a]\n"
        with self.assertRaisesRegex(ParseError, "recursive aliases"):
            parse_openapi_document(recursive)

    def test_rejects_excessive_yaml_nesting(self):
        excessive = b"openapi: 3.1.0\npaths:\n"
        excessive += b"  deep:\n"
        for level in range(40):
            excessive += b"  " * (level + 2) + b"level:\n"
        excessive += b"  " * 43 + b"value: final\n"
        with self.assertRaises(ParseError):
            parse_openapi_document(excessive)


if __name__ == "__main__":
    unittest.main()
