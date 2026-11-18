import tempfile
import unittest
from pathlib import Path

from src.api_doc_sync.config import load_config, parse_yaml_subset
from src.api_doc_sync.errors import ConfigurationError


class ConfigParserTests(unittest.TestCase):
    def write_config(self, content: str) -> Path:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / "doc-sync.yml"
        path.write_text(content, encoding="utf-8")
        return path

    def valid_config(self, extra: str = "") -> str:
        return (
            'startup_command: "python mock_app.py"\n'
            'openapi_url: "http://127.0.0.1:8000/openapi.json"\n'
            'output_path: "docs/api.md"\n'
            'health_check_url: "http://127.0.0.1:8000/health"\n'
            'shell: "pwsh"\n'
            "auth:\n"
            '  mode: "none"\n'
            "  secret_names: {}\n"
            + extra
        )

    def test_loads_none_configuration(self):
        path = self.write_config(self.valid_config())

        config = load_config(path)

        self.assertEqual(config.startup_command, "python mock_app.py")
        self.assertEqual(config.openapi_url, "http://127.0.0.1:8000/openapi.json")
        self.assertEqual(config.output_path, "docs/api.md")
        self.assertEqual(config.health_check_url, "http://127.0.0.1:8000/health")
        self.assertEqual(config.shell, "pwsh")
        self.assertEqual(config.auth.mode, "none")
        self.assertEqual(config.auth.secret_names, {})

    def test_environment_overrides_supported_fields(self):
        path = self.write_config(
            self.valid_config(
                "environment_overrides:\n"
                '  openapi_url: "DOC_SYNC_OPENAPI_URL"\n'
                '  auth_mode: "DOC_SYNC_AUTH_MODE"\n'
            )
        )

        config = load_config(
            path,
            environ={
                "DOC_SYNC_OPENAPI_URL": "https://localhost/openapi.yaml",
                "DOC_SYNC_AUTH_MODE": "none",
            },
        )

        self.assertEqual(
            config.openapi_url,
            "https://localhost/openapi.yaml",
        )
        self.assertEqual(config.auth.mode, "none")

    def test_missing_required_field_fails(self):
        path = self.write_config(
            'openapi_url: "http://127.0.0.1/openapi.json"\n'
            'output_path: "docs/api.md"\n'
        )

        with self.assertRaisesRegex(
            ConfigurationError,
            "startup_command",
        ):
            load_config(path)

    def test_relative_and_credential_urls_are_rejected(self):
        relative = self.write_config(
            'startup_command: "python mock_app.py"\n'
            'openapi_url: "/openapi.json"\n'
            'output_path: "docs/api.md"\n'
        )
        credentials = self.write_config(
            'startup_command: "python mock_app.py"\n'
            'openapi_url: "https://user:pass@example.com/openapi.json"\n'
            'output_path: "docs/api.md"\n'
        )

        with self.assertRaises(ConfigurationError):
            load_config(relative)
        with self.assertRaisesRegex(ConfigurationError, "credentials"):
            load_config(credentials)

    def test_output_path_must_be_relative_markdown(self):
        absolute = self.write_config(
            self.valid_config().replace(
                'output_path: "docs/api.md"',
                'output_path: "C:/temp/api.md"',
            )
        )
        traversal = self.write_config(
            self.valid_config().replace(
                'output_path: "docs/api.md"',
                'output_path: "../api.md"',
            )
        )

        with self.assertRaisesRegex(ConfigurationError, "repository-relative"):
            load_config(absolute)
        with self.assertRaisesRegex(ConfigurationError, "repository"):
            load_config(traversal)

    def test_supports_bearer_secret_name_mapping(self):
        path = self.write_config(
            self.valid_config(
                "auth:\n"
                '  mode: "bearer"\n'
                "  secret_names:\n"
                '    token: "OPENAPI_BEARER_TOKEN"\n'
            )
        )

        config = load_config(path)

        self.assertEqual(config.auth.mode, "bearer")
        self.assertEqual(
            config.auth.secret_names["token"],
            "OPENAPI_BEARER_TOKEN",
        )

    def test_supports_basic_secret_name_mapping(self):
        path = self.write_config(
            'startup_command: "python mock_app.py"\n'
            'openapi_url: "http://127.0.0.1/openapi.json"\n'
            'output_path: "docs/api.md"\n'
            "auth:\n"
            '  mode: "basic"\n'
            "  secret_names:\n"
            '    username: "OPENAPI_BASIC_USERNAME"\n'
            '    password: "OPENAPI_BASIC_PASSWORD"\n'
        )

        config = load_config(path)

        self.assertEqual(config.auth.mode, "basic")
        self.assertEqual(
            set(config.auth.secret_names),
            {"username", "password"},
        )

    def test_supports_api_key_secret_name_mapping(self):
        path = self.write_config(
            'startup_command: "python mock_app.py"\n'
            'openapi_url: "http://127.0.0.1/openapi.json"\n'
            'output_path: "docs/api.md"\n'
            "auth:\n"
            '  mode: "api_key"\n'
            '  header_name: "X-API-Key"\n'
            "  secret_names:\n"
            '    header_value: "OPENAPI_API_KEY"\n'
        )

        config = load_config(path)

        self.assertEqual(config.auth.mode, "api_key")
        self.assertEqual(config.auth.header_name, "X-API-Key")

    def test_supports_oauth2_secret_name_mapping(self):
        path = self.write_config(
            'startup_command: "python mock_app.py"\n'
            'openapi_url: "http://127.0.0.1/openapi.json"\n'
            'output_path: "docs/api.md"\n'
            "auth:\n"
            '  mode: "oauth2_client_credentials"\n'
            '  token_url: "https://auth.example.com/oauth/token"\n'
            '  scopes: ["read:api", "write:api"]\n'
            "  secret_names:\n"
            '    client_id: "OAUTH_CLIENT_ID"\n'
            '    client_secret: "OAUTH_CLIENT_SECRET"\n'
        )

        config = load_config(path)

        self.assertEqual(
            config.auth.mode,
            "oauth2_client_credentials",
        )
        self.assertEqual(
            config.auth.scopes,
            ("read:api", "write:api"),
        )

    def test_rejects_actual_credentials_in_secret_name_mapping(self):
        path = self.write_config(
            'startup_command: "python mock_app.py"\n'
            'openapi_url: "http://127.0.0.1/openapi.json"\n'
            'output_path: "docs/api.md"\n'
            "auth:\n"
            '  mode: "bearer"\n'
            "  secret_names:\n"
            '    token: "actual-token-value"\n'
        )

        with self.assertRaisesRegex(ConfigurationError, "secret-name"):
            load_config(path)

    def test_rejects_invalid_auth_combinations(self):
        invalid_configs = (
            (
                'startup_command: "python mock_app.py"\n'
                'openapi_url: "http://127.0.0.1/openapi.json"\n'
                'output_path: "docs/api.md"\n'
                "auth:\n"
                '  mode: "bearer"\n'
                "  secret_names: {}\n"
            ),
            (
                'startup_command: "python mock_app.py"\n'
                'openapi_url: "http://127.0.0.1/openapi.json"\n'
                'output_path: "docs/api.md"\n'
                "auth:\n"
                '  mode: "basic"\n'
                "  secret_names:\n"
                '    username: "BASIC_USERNAME"\n'
            ),
            (
                'startup_command: "python mock_app.py"\n'
                'openapi_url: "http://127.0.0.1/openapi.json"\n'
                'output_path: "docs/api.md"\n'
                "auth:\n"
                '  mode: "api_key"\n'
                "  secret_names:\n"
                '    header_value: "API_KEY"\n'
            ),
            (
                'startup_command: "python mock_app.py"\n'
                'openapi_url: "http://127.0.0.1/openapi.json"\n'
                'output_path: "docs/api.md"\n'
                "auth:\n"
                '  mode: "oauth2_client_credentials"\n'
                "  secret_names:\n"
                '    client_id: "OAUTH_CLIENT_ID"\n'
                '    client_secret: "OAUTH_CLIENT_SECRET"\n'
            ),
        )

        for content in invalid_configs:
            with self.subTest(content=content):
                path = self.write_config(content)
                with self.assertRaises(ConfigurationError):
                    load_config(path)

    def test_unknown_auth_mode_is_rejected(self):
        path = self.write_config(
            'startup_command: "python mock_app.py"\n'
            'openapi_url: "http://127.0.0.1/openapi.json"\n'
            'output_path: "docs/api.md"\n'
            "auth:\n"
            '  mode: "digest"\n'
        )

        with self.assertRaisesRegex(ConfigurationError, "auth.mode"):
            load_config(path)

    def test_unknown_environment_override_field_is_rejected(self):
        path = self.write_config(
            self.valid_config(
                "environment_overrides:\n"
                '  client_secret: "ACTUAL_SECRET_ENV"\n'
            )
        )

        with self.assertRaisesRegex(ConfigurationError, "Unsupported"):
            load_config(path)

    def test_shell_must_be_supported(self):
        path = self.write_config(
            self.valid_config().replace(
                'shell: "pwsh"',
                'shell: "malicious-shell"',
            )
        )

        with self.assertRaisesRegex(ConfigurationError, "shell"):
            load_config(path)

    def test_yaml_subset_parser_handles_nested_and_list_values(self):
        parsed = parse_yaml_subset(
            'auth:\n'
            '  mode: "oauth2_client_credentials"\n'
            '  scopes: ["read:api", "write:api"]\n'
        )

        self.assertEqual(
            parsed["auth"]["mode"],
            "oauth2_client_credentials",
        )


if __name__ == "__main__":
    unittest.main()
