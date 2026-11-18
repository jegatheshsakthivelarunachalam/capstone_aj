"""Application process lifecycle and readiness management."""

from __future__ import annotations

import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .config import DocSyncConfig
from .errors import ReadinessError, StartupError

STARTUP_TIMEOUT_SECONDS = 300
READINESS_POLL_INTERVAL_SECONDS = 1
CLEANUP_TERMINATE_SECONDS = 5


@dataclass(frozen=True)
class ProcessInfo:
    pid: int
    exit_code: int | None


ReadinessProbe = Callable[[str], bool]
Clock = Callable[[], float]
Sleep = Callable[[float], None]


def default_readiness_probe(url: str) -> bool:
    request = urllib.request.Request(
        url,
        method="GET",
        headers={"Accept": "application/json, text/plain"},
    )
    try:
        with urllib.request.urlopen(request, timeout=2) as response:
            return 200 <= response.status < 400
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError):
        return False


def build_shell_command(command: str, shell: str | None) -> tuple[list[str], bool]:
    normalized = (shell or "").strip().lower()
    if normalized in {"pwsh", "powershell", "powershell.exe"}:
        executable = "pwsh" if normalized == "pwsh" else "powershell.exe"
        return [executable, "-NoProfile", "-NonInteractive", "-Command", command], False
    if normalized in {"cmd", "cmd.exe"}:
        return ["cmd.exe", "/d", "/s", "/c", command], False
    if normalized in {"bash", "sh"}:
        return [normalized, "-lc", command], False
    if os.name == "nt":
        return ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command], False
    return ["/bin/sh", "-lc", command], False


class ApplicationLifecycle:
    """Own a locally started application process through readiness and cleanup."""

    def __init__(
        self,
        config: DocSyncConfig,
        *,
        popen: Callable[..., subprocess.Popen[str]] = subprocess.Popen,
        probe: ReadinessProbe = default_readiness_probe,
        clock: Clock = time.monotonic,
        sleep: Sleep = time.sleep,
        timeout_seconds: int = STARTUP_TIMEOUT_SECONDS,
        poll_interval_seconds: float = READINESS_POLL_INTERVAL_SECONDS,
        working_directory: str | os.PathLike[str] | None = None,
    ) -> None:
        self.config = config
        self._popen = popen
        self._probe = probe
        self._clock = clock
        self._sleep = sleep
        self._timeout_seconds = timeout_seconds
        self._poll_interval_seconds = poll_interval_seconds
        self.working_directory = (
            str(working_directory)
            if working_directory is not None
            else None
        )
        self.process: subprocess.Popen[str] | None = None

    def _build_environment(self) -> dict[str, str]:
        environment = os.environ.copy()
        if self.working_directory:
            existing_pythonpath = environment.get("PYTHONPATH")
            working = str(Path(self.working_directory))
            environment["PYTHONPATH"] = (
                working
                if not existing_pythonpath
                else working + os.pathsep + existing_pythonpath
            )
        for key in list(environment):
            normalized = key.lower().replace("-", "_")
            if (
                "token" in normalized
                or "secret" in normalized
                or "password" in normalized
                or "api_key" in normalized
                or "authorization" in normalized
            ):
                environment.pop(key, None)
        for secret_name in self.config.auth.secret_names.values():
            environment.pop(secret_name, None)
            environment.pop(secret_name.upper(), None)
        return environment

    def start(self) -> ProcessInfo:
        argv, use_shell = build_shell_command(
            self.config.startup_command,
            self.config.shell,
        )
        try:
            process = self._popen(
                argv,
                shell=use_shell,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                env=self._build_environment(),
                cwd=self.working_directory,
                start_new_session=os.name != "nt",
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
            )
        except (OSError, subprocess.SubprocessError) as error:
            raise StartupError("Application startup failed.") from error

        self.process = process
        pid = getattr(process, "pid", 0)
        if not isinstance(pid, int) or pid <= 0:
            self.stop()
            raise StartupError("Application process did not provide a valid process identifier.")
        return ProcessInfo(pid=pid, exit_code=None)

    def wait_until_ready(self) -> ProcessInfo:
        if self.process is None:
            raise StartupError("Application has not been started.")

        readiness_url = self.config.health_check_url or self.config.openapi_url
        deadline = self._clock() + max(0, self._timeout_seconds)

        while True:
            exit_code = self.process.poll()
            if exit_code is not None:
                raise ReadinessError(
                    "Application exited before reaching readiness.",
                )

            try:
                ready = self._probe(readiness_url)
            except Exception as error:
                raise ReadinessError(
                    "Readiness check could not be completed.",
                ) from error

            if ready:
                return ProcessInfo(
                    pid=self.process.pid,
                    exit_code=None,
                )

            if self._clock() >= deadline:
                raise ReadinessError(
                    "Application readiness timed out.",
                )

            self._sleep(self._poll_interval_seconds)

    def start_and_wait(self) -> ProcessInfo:
        process_info = self.start()
        try:
            return self.wait_until_ready()
        except (StartupError, ReadinessError):
            self.stop()
            raise

    def stop(self) -> ProcessInfo:
        process = self.process
        if process is None:
            return ProcessInfo(pid=0, exit_code=None)

        pid = getattr(process, "pid", 0)
        if not isinstance(pid, int):
            pid = 0

        try:
            if process.poll() is None:
                self._terminate_process_tree(process)
        except Exception:
            pass

        exit_code = process.poll()
        if exit_code is None:
            try:
                exit_code = process.wait(timeout=CLEANUP_TERMINATE_SECONDS)
            except (subprocess.TimeoutExpired, OSError):
                try:
                    process.kill()
                except Exception:
                    pass
                try:
                    exit_code = process.wait(timeout=1)
                except (subprocess.TimeoutExpired, OSError):
                    exit_code = -1

        self.process = None
        return ProcessInfo(pid=pid, exit_code=exit_code)

    def _terminate_process_tree(self, process: subprocess.Popen[str]) -> None:
        if os.name == "nt":
            try:
                subprocess.run(
                    ["taskkill", "/pid", str(process.pid), "/t", "/f"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=CLEANUP_TERMINATE_SECONDS,
                    check=False,
                )
                return
            except (OSError, subprocess.SubprocessError):
                pass

        try:
            if os.name != "nt":
                os.killpg(process.pid, 15)
            else:
                process.terminate()
        except (AttributeError, OSError, ProcessLookupError):
            try:
                process.terminate()
            except Exception:
                pass
