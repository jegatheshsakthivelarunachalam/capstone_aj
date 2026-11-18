import unittest
import subprocess
import sys
from pathlib import Path
from urllib.request import urlopen

from tests.integration.mock_app import start_mock_application


class MockApplicationFixtureTests(unittest.TestCase):
    def test_mock_app_module_entry_help(self):
        fixture = Path(__file__).resolve().parent / "mock_app.py"
        completed = subprocess.run(
            [sys.executable, str(fixture), "--help"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(completed.returncode, 0)
        self.assertIn("--port", completed.stdout)
        self.assertIn("--mode", completed.stdout)

    def test_fixture_starts_and_stops(self):
        application, base_url = start_mock_application()
        try:
            with urlopen(base_url + "/health", timeout=2) as response:
                self.assertEqual(response.status, 200)
            with urlopen(base_url + "/openapi.json", timeout=2) as response:
                self.assertEqual(response.status, 200)
        finally:
            application.stop()

        self.assertIsNone(application.server)
        self.assertIsNone(application.thread)

    def test_fixture_supports_malformed_mode(self):
        application, base_url = start_mock_application(mode="malformed")
        try:
            with urlopen(base_url + "/openapi.json", timeout=2) as response:
                body = response.read()
            self.assertEqual(body, b"{malformed")
        finally:
            application.stop()

    def test_fixture_supports_oversized_mode(self):
        application, base_url = start_mock_application(mode="oversized")
        try:
            with urlopen(base_url + "/openapi.json", timeout=2) as response:
                body = response.read()
            self.assertEqual(len(body), 10 * 1024 * 1024 + 1)
        finally:
            application.stop()


if __name__ == "__main__":
    unittest.main()
