import subprocess
import unittest
from unittest.mock import Mock, patch

from src.api_doc_sync.config import AuthConfig, DocSyncConfig
from src.api_doc_sync.errors import ReadinessError, StartupError
from src.api_doc_sync.lifecycle import (
    ApplicationLifecycle,
    build_shell_command,
)


def make_config(
    *,
    startup_command: str = "python app.py",
    openapi_url: str = "http://127.0.0.1:8000/openapi.json",
    health_check_url: str | None = "http://127.0.0.1:8000/health",
) -> DocSyncConfig:
    return DocSyncConfig(
        startup_command=startup_command,
        openapi_url=openapi_url,
        output_path="docs/api.md",
        health_check_url=health_check_url,
        shell="pwsh",
        auth=AuthConfig(),
    )


class ShellCommandTests(unittest.TestCase):
    def test_builds_pwsh_command(self):
        argv, use_shell = build_shell_command("python app.py", "pwsh")

        self.assertFalse(use_shell)
        self.assertEqual(argv[:2], ["pwsh", "-NoProfile"])
        self.assertIn("python app.py", argv)

    def test_builds_bash_command(self):
        argv, use_shell = build_shell_command("python app.py", "bash")

        self.assertFalse(use_shell)
        self.assertEqual(argv[:3], ["bash", "-lc", "python app.py"])


class ApplicationLifecycleTests(unittest.TestCase):
    def test_start_uses_pr_application_working_directory(self):
        process = Mock()
        process.pid = 1234
        popen = Mock(return_value=process)
        lifecycle = ApplicationLifecycle(
            make_config(),
            popen=popen,
            working_directory="pr-app",
        )

        lifecycle.start()

        kwargs = popen.call_args.kwargs
        self.assertEqual(kwargs["cwd"], "pr-app")
        self.assertIn("pr-app", kwargs["env"]["PYTHONPATH"])

    def test_environment_excludes_secret_shaped_values(self):
        lifecycle = ApplicationLifecycle(make_config())
        with patch.dict(
            "os.environ",
            {
                "PATH": "C:\\Windows",
                "OPENAPI_TOKEN": "secret-token",
                "CLIENT_SECRET": "secret-value",
                "SAFE_SETTING": "keep",
            },
            clear=False,
        ):
            environment = lifecycle._build_environment()

        self.assertNotIn("OPENAPI_TOKEN", environment)
        self.assertNotIn("CLIENT_SECRET", environment)
        self.assertEqual(environment.get("SAFE_SETTING"), "keep")

    def test_start_returns_process_information(self):
        process = Mock()
        process.pid = 1234
        popen = Mock(return_value=process)
        lifecycle = ApplicationLifecycle(make_config(), popen=popen)

        info = lifecycle.start()

        self.assertEqual(info.pid, 1234)
        self.assertIsNone(info.exit_code)
        popen.assert_called_once()

    def test_start_failure_is_sanitized(self):
        popen = Mock(side_effect=OSError("raw secret and response body"))
        lifecycle = ApplicationLifecycle(make_config(), popen=popen)

        with self.assertRaises(StartupError) as raised:
            lifecycle.start()

        self.assertEqual(raised.exception.code, "STARTUP_FAILED")
        self.assertNotIn("raw secret", str(raised.exception))

    def test_successful_readiness_uses_health_url(self):
        process = Mock()
        process.pid = 1234
        process.poll.return_value = None
        probe = Mock(return_value=True)
        lifecycle = ApplicationLifecycle(
            make_config(),
            popen=Mock(return_value=process),
            probe=probe,
        )

        lifecycle.start()
        info = lifecycle.wait_until_ready()

        self.assertEqual(info.pid, 1234)
        probe.assert_called_once_with("http://127.0.0.1:8000/health")

    def test_readiness_falls_back_to_openapi_url(self):
        process = Mock()
        process.pid = 1234
        process.poll.return_value = None
        probe = Mock(return_value=True)
        lifecycle = ApplicationLifecycle(
            make_config(health_check_url=None),
            popen=Mock(return_value=process),
            probe=probe,
        )

        lifecycle.start()
        lifecycle.wait_until_ready()

        probe.assert_called_once_with("http://127.0.0.1:8000/openapi.json")

    def test_early_process_exit_is_readiness_failure(self):
        process = Mock()
        process.pid = 1234
        process.poll.return_value = 7
        lifecycle = ApplicationLifecycle(
            make_config(),
            popen=Mock(return_value=process),
            probe=Mock(return_value=False),
        )

        lifecycle.start()
        with self.assertRaises(ReadinessError) as raised:
            lifecycle.wait_until_ready()

        self.assertEqual(raised.exception.code, "READINESS_FAILED")

    def test_readiness_timeout_enforces_deadline(self):
        process = Mock()
        process.pid = 1234
        process.poll.return_value = None
        times = iter((0.0, 1.0, 301.0))
        lifecycle = ApplicationLifecycle(
            make_config(),
            popen=Mock(return_value=process),
            probe=Mock(return_value=False),
            clock=Mock(side_effect=lambda: next(times)),
            sleep=Mock(),
            timeout_seconds=300,
        )

        lifecycle.start()
        with self.assertRaises(ReadinessError) as raised:
            lifecycle.wait_until_ready()

        self.assertEqual(raised.exception.code, "READINESS_FAILED")

    def test_probe_exception_is_readiness_failure(self):
        process = Mock()
        process.pid = 1234
        process.poll.return_value = None
        lifecycle = ApplicationLifecycle(
            make_config(),
            popen=Mock(return_value=process),
            probe=Mock(side_effect=RuntimeError("raw response body")),
        )

        lifecycle.start()
        with self.assertRaises(ReadinessError) as raised:
            lifecycle.wait_until_ready()

        self.assertNotIn("raw response body", str(raised.exception))

    def test_stop_terminates_running_process(self):
        process = Mock()
        process.pid = 1234
        process.poll.return_value = None
        process.wait.return_value = 0
        lifecycle = ApplicationLifecycle(
            make_config(),
            popen=Mock(return_value=process),
        )

        lifecycle.start()
        with patch.object(
            lifecycle,
            "_terminate_process_tree",
        ) as terminate:
            info = lifecycle.stop()

        terminate.assert_called_once_with(process)
        self.assertEqual(info.pid, 1234)
        self.assertEqual(info.exit_code, 0)

    def test_stop_is_safe_when_process_is_already_exited(self):
        process = Mock()
        process.pid = 1234
        process.poll.return_value = 0
        lifecycle = ApplicationLifecycle(
            make_config(),
            popen=Mock(return_value=process),
        )

        lifecycle.start()
        info = lifecycle.stop()

        self.assertEqual(info.exit_code, 0)

    def test_start_and_wait_cleans_up_on_readiness_timeout(self):
        process = Mock()
        process.pid = 1234
        process.poll.return_value = None
        process.wait.return_value = 0
        lifecycle = ApplicationLifecycle(
            make_config(),
            popen=Mock(return_value=process),
            probe=Mock(return_value=False),
            clock=Mock(side_effect=[0.0, 301.0]),
            timeout_seconds=300,
        )

        with patch.object(
            lifecycle,
            "_terminate_process_tree",
        ) as terminate:
            with self.assertRaises(ReadinessError):
                lifecycle.start_and_wait()

        terminate.assert_called_once_with(process)


if __name__ == "__main__":
    unittest.main()
