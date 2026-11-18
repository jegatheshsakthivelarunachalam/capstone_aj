import base64
import io
import json
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

from src.doc_sync_capstone import profile


class ParseGithubUrlTests(unittest.TestCase):
    def test_accepts_repository_and_git_urls(self):
        self.assertEqual(
            profile.parse_github_url("https://github.com/example/project"),
            ("example", "project"),
        )
        self.assertEqual(
            profile.parse_github_url("https://github.com/example/project.git"),
            ("example", "project"),
        )

    def test_rejects_unsupported_or_unsafe_urls(self):
        invalid_urls = (
            "http://github.com/example/project",
            "https://github.com/example/project/tree/main",
            "https://user:password@github.com/example/project",
            "https://github.com/example/project?token=secret",
            "https://example.com/example/project",
            "https://github.com/../project",
        )
        for repository_url in invalid_urls:
            with self.subTest(repository_url=repository_url):
                with self.assertRaises(ValueError):
                    profile.parse_github_url(repository_url)


class RequestJsonTests(unittest.TestCase):
    def test_reads_json_with_expected_request_headers(self):
        response = io.BytesIO(b'{"name":"project"}')
        with patch("src.doc_sync_capstone.profile.urllib.request.urlopen", return_value=response) as open_url:
            result = profile.request_json("https://api.github.com/repos/example/project")

        self.assertEqual(result, {"name": "project"})
        request = open_url.call_args.args[0]
        self.assertEqual(request.get_header("User-agent"), "doc-sync-capstone")

    def test_reports_http_error_without_echoing_response_body(self):
        error = urllib.error.HTTPError(
            "https://api.github.com/private",
            404,
            "Not Found",
            {},
            io.BytesIO(b"secret response"),
        )
        with patch("src.doc_sync_capstone.profile.urllib.request.urlopen", side_effect=error):
            with self.assertRaisesRegex(profile.RepositoryError, "HTTP 404") as raised:
                profile.request_json("https://api.github.com/private")

        self.assertNotIn("secret response", str(raised.exception))

    def test_rejects_non_object_json(self):
        with patch(
            "src.doc_sync_capstone.profile.urllib.request.urlopen",
            return_value=io.BytesIO(b"[]"),
        ):
            with self.assertRaises(profile.RepositoryError):
                profile.request_json("https://api.github.com/repos/example/project")

    def test_hides_network_error_details(self):
        with patch(
            "src.doc_sync_capstone.profile.urllib.request.urlopen",
            side_effect=urllib.error.URLError("token=private-value"),
        ):
            with self.assertRaises(profile.RepositoryError) as raised:
                profile.request_json("https://api.github.com/repos/example/project")

        self.assertNotIn("private-value", str(raised.exception))


class ReadGithubFileTests(unittest.TestCase):
    def test_decodes_contents_api_response(self):
        encoded = base64.b64encode(b"hello").decode("ascii")
        with patch(
            "src.doc_sync_capstone.profile.request_json",
            return_value={"encoding": "base64", "content": encoded},
        ) as request:
            content = profile.read_github_file("owner", "repo", "docs/read me.md", "main")

        self.assertEqual(content, "hello")
        self.assertIn("docs/read%20me.md", request.call_args.args[0])

    def test_rejects_oversized_content(self):
        encoded = base64.b64encode(b"x" * (profile.MAX_FILE_BYTES + 1)).decode("ascii")
        with patch(
            "src.doc_sync_capstone.profile.request_json",
            return_value={"encoding": "base64", "content": encoded},
        ):
            with self.assertRaisesRegex(profile.RepositoryError, "1 MB"):
                profile.read_github_file("owner", "repo", "README.md", "main")

    def test_rejects_oversized_file_from_metadata(self):
        with patch(
            "src.doc_sync_capstone.profile.request_json",
            return_value={"size": profile.MAX_FILE_BYTES + 1, "encoding": "none"},
        ):
            with self.assertRaisesRegex(profile.RepositoryError, "1 MB"):
                profile.read_github_file("owner", "repo", "README.md", "main")

    def test_rejects_unsupported_encoding(self):
        with patch("src.doc_sync_capstone.profile.request_json", return_value={"encoding": "none"}):
            with self.assertRaises(profile.RepositoryError):
                profile.read_github_file("owner", "repo", "README.md", "main")


class RedactSecretsTests(unittest.TestCase):
    def test_redacts_common_tokens_and_credentials(self):
        text = (
            "token=abc123 password: hidden "
            "api_token=api-secret-value client_secret=client-secret-value "
            '"password": "two word secret" token=comma,separated-secret '
            "ghp_abcdefghijklmnopqrstuvwxyz123456 "
            "Bearer abc.def.ghi https://user:pass@example.com "
            "-----BEGIN PRIVATE KEY-----private-key-data-----END PRIVATE KEY-----"
        )
        result = profile.redact_secrets(text)

        for secret in (
            "abc123",
            "hidden",
            "api-secret-value",
            "client-secret-value",
            "two word secret",
            "comma,separated-secret",
            "ghp_abcdefghijklmnopqrstuvwxyz123456",
            "abc.def.ghi",
            "user:pass",
            "private-key-data",
        ):
            self.assertNotIn(secret, result)
        self.assertIn("[REDACTED]", result)


class ReadmeSummaryTests(unittest.TestCase):
    def test_summarizes_first_paragraph_and_redacts_secrets(self):
        readme = "# Project\n\nA useful project. token=very-secret-value\n\nMore details.\n"
        summary = profile.readme_summary(readme)

        self.assertIn("A useful project.", summary)
        self.assertNotIn("More details.", summary)
        self.assertNotIn("very-secret-value", summary)

    def test_returns_not_found_for_empty_content_and_caps_length(self):
        self.assertEqual(profile.readme_summary("# Heading\n\n```text\nignored\n```"), "Not Found")
        self.assertLessEqual(len(profile.readme_summary("x" * 800)), 500)


class ManifestSummaryTests(unittest.TestCase):
    def test_summarizes_package_json(self):
        result = profile.summarize_package_json(
            json.dumps(
                {
                    "name": "sample",
                    "version": "1.2.3",
                    "engines": {"node": ">=20"},
                    "dependencies": {"zlib": "^2", "alpha": "~1"},
                }
            )
        )

        self.assertIn("name: sample", result)
        self.assertIn("Node runtime: >=20", result)
        self.assertIn("alpha@~1, zlib@^2", result)

    def test_reports_missing_package_fields_and_invalid_json(self):
        self.assertIn("version: Not Found", profile.summarize_package_json("{}"))
        with self.assertRaisesRegex(ValueError, "Invalid package.json"):
            profile.summarize_package_json("{")
        with self.assertRaisesRegex(ValueError, "structure"):
            profile.summarize_package_json("[]")

    def test_summarizes_requirements_without_echoing_direct_urls(self):
        result = profile.summarize_requirements(
            "requests>=2.0,<3\n# comment\nmy-lib[extra]==1.4\nprivate @ https://user:secret@example.com/pkg\n"
        )

        self.assertIn("my-lib==1.4", result)
        self.assertIn("requests>=2.0,<3", result)
        self.assertNotIn("example.com", result)
        self.assertEqual(profile.summarize_requirements("# empty\n-e ."), "Not Found")

    def test_summarizes_pom_and_rejects_unsafe_or_invalid_xml(self):
        pom = """<project xmlns="http://maven.apache.org/POM/4.0.0">
          <artifactId>demo</artifactId><version>1.0</version>
          <properties><maven.compiler.release>21</maven.compiler.release></properties>
          <dependencies><dependency><groupId>org.example</groupId>
          <artifactId>lib</artifactId><version>2</version></dependency></dependencies>
        </project>"""
        result = profile.summarize_pom(pom)

        self.assertIn("artifact: demo", result)
        self.assertIn("Java runtime: 21", result)
        self.assertIn("org.example:lib:2", result)
        with self.assertRaisesRegex(ValueError, "DTD or entity"):
            profile.summarize_pom("<!DOCTYPE project><project/>")
        with self.assertRaisesRegex(ValueError, "Invalid pom.xml"):
            profile.summarize_pom("<project>")
        with self.assertRaisesRegex(ValueError, "structure"):
            profile.summarize_pom("<not-project/>")


class CollectProfileTests(unittest.TestCase):
    def test_collects_repository_facts_and_missing_files(self):
        with (
            patch(
                "src.doc_sync_capstone.profile.request_json",
                side_effect=[
                    {
                        "full_name": "example/project",
                        "description": "A project",
                        "default_branch": "main",
                    },
                    {"Python": 200},
                    {
                        "truncated": False,
                        "tree": [{"path": "README.md", "type": "blob"}],
                    },
                ],
            ),
            patch(
                "src.doc_sync_capstone.profile.read_github_file",
                return_value="# Project\n\nA repository.",
            ),
        ):
            result = profile.collect_profile("https://github.com/example/project")

        self.assertEqual(result.repository_name, "example/project")
        self.assertEqual(result.languages, "Python")
        self.assertEqual(result.readme_summary, "A repository.")
        self.assertEqual(result.manifest_summaries, [])
        self.assertEqual(result.description, "A project")

    def test_fails_on_truncated_repository_tree(self):
        with patch(
            "src.doc_sync_capstone.profile.request_json",
            side_effect=[
                {"full_name": "example/project", "default_branch": "main"},
                {},
                {"truncated": True, "tree": []},
            ],
        ):
            with self.assertRaisesRegex(profile.RepositoryError, "incomplete"):
                profile.collect_profile("https://github.com/example/project")

    def test_handles_empty_repository_without_default_branch(self):
        with patch(
            "src.doc_sync_capstone.profile.request_json",
            side_effect=[{"full_name": "example/empty", "default_branch": None}, {}],
        ):
            result = profile.collect_profile("https://github.com/example/empty")

        self.assertEqual(result.default_branch, "Not Found")
        self.assertEqual(result.readme_summary, "Not Found")
        self.assertEqual(result.languages, "Not Found")


class RenderMarkdownTests(unittest.TestCase):
    def test_escapes_untrusted_markdown_and_html(self):
        result = profile.markdown_text("<script>alert(1)</script> **bold**")

        self.assertNotIn("<script>", result)
        self.assertIn("&lt;script&gt;", result)
        self.assertIn(r"\*\*bold\*\*", result)

    def test_renders_missing_values_and_redacts_secrets(self):
        result = profile.render_markdown(
            profile.TechnicalProfile(
                repository_name="example/repo",
                repository_url="https://github.com/example/repo",
                description="token=secret-value",
                default_branch="Not Found",
                languages="Python",
                readme_summary="Not Found",
                manifest_summaries=[],
            )
        )

        self.assertIn("# Technical Profile: example/repo", result)
        self.assertIn(r"**Description:** token=\[REDACTED\]", result)
        self.assertIn("## Dependency and runtime manifests\n\n- Not Found", result)
        self.assertNotIn("secret-value", result)


class MainTests(unittest.TestCase):
    def test_generates_output_file(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "profile.md"
            sample = profile.TechnicalProfile(
                "example/repo",
                "https://github.com/example/repo",
                "Not Found",
                "main",
                "Not Found",
                "Not Found",
                [],
            )
            with patch("src.doc_sync_capstone.profile.collect_profile", return_value=sample):
                result = profile.main(
                    ["https://github.com/example/repo", "--output", str(output)]
                )

            self.assertEqual(result, 0)
            self.assertIn("# Technical Profile", output.read_text(encoding="utf-8"))

    def test_refuses_to_overwrite_existing_file_without_force(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "profile.md"
            output.write_text("existing", encoding="utf-8")
            with patch("src.doc_sync_capstone.profile.collect_profile") as collect:
                result = profile.main(
                    ["https://github.com/example/repo", "--output", str(output)]
                )

            self.assertEqual(result, 2)
            self.assertEqual(output.read_text(encoding="utf-8"), "existing")
            collect.assert_not_called()

    def test_force_replaces_existing_file(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "profile.md"
            output.write_text("existing", encoding="utf-8")
            sample = profile.TechnicalProfile(
                "example/repo",
                "https://github.com/example/repo",
                "Not Found",
                "main",
                "Not Found",
                "Not Found",
                [],
            )
            with patch("src.doc_sync_capstone.profile.collect_profile", return_value=sample):
                result = profile.main(
                    [
                        "https://github.com/example/repo",
                        "--output",
                        str(output),
                        "--force",
                    ]
                )

            self.assertEqual(result, 0)
            self.assertIn("# Technical Profile", output.read_text(encoding="utf-8"))

    def test_reports_invalid_url_as_cli_error(self):
        with patch("sys.stderr", new_callable=io.StringIO) as stderr:
            result = profile.main(["https://example.com/repo"])

        self.assertEqual(result, 1)
        self.assertIn("GitHub URL", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
