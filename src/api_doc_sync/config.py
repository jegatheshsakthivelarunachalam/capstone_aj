"""Configuration loading and validation for API documentation sync."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping
from urllib.parse import urlsplit

from .errors import ConfigurationError


AUTH_MODES = {"none", "bearer", "basic", "api_key", "oauth2_client_credentials"}
SECRET_REFERENCE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
HEADER_NAME = re.compile(r"^[!#$%&'*+\-.^_`|~0-9A-Za-z]+$")
OVERRIDE_FIELDS = {
    "startup_command",
    "openapi_url",
    "output_path",
    "health_check_url",
    "shell",
    "auth_mode",
}


@dataclass(frozen=True)
class AuthConfig:
    mode: str = "none"
    secret_names: dict[str, str] = field(default_factory=dict)
    token_url: str | None = None
    header_name: str | None = None
    scopes: tuple[str, ...] = ()


@dataclass(frozen=True)
class DocSyncConfig:
    startup_command: str
    openapi_url: str
    output_path: str
    health_check_url: str | None
    shell: str | None
    auth: AuthConfig
    environment_overrides: dict[str, str] = field(default_factory=dict)


def _strip_comment(value: str) -> str:
    quote: str | None = None
    escaped = False
    for index, character in enumerate(value):
        if escaped:
            escaped = False
            continue
        if character == "\\" and quote == '"':
            escaped = True
            continue
        if character in {"'", '"'}:
            if quote is None:
                quote = character
            elif quote == character:
                quote = None
        elif character == "#" and quote is None:
            return value[:index].rstrip()
    return value.strip()


def _parse_scalar(value: str) -> object:
    value = _strip_comment(value)
    if not value:
        return ""
    if value.lower() in {"null", "~"}:
        return None
    if value.lower() in {"true", "false"}:
        return value.lower() == "true"
    if value.startswith("[") or value.startswith("{"):
        try:
            import json

            parsed = json.loads(value)
            if isinstance(parsed, (list, dict)):
                return parsed
        except json.JSONDecodeError:
            pass
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        if value[0] == '"':
            try:
                import json

                parsed = json.loads(value)
                if isinstance(parsed, str):
                    return parsed
            except json.JSONDecodeError:
                pass
        return value[1:-1]
    return value


def parse_yaml_subset(text: str) -> dict[str, object]:
    """Parse the mapping-only YAML subset used by .github/doc-sync.yml."""

    root: dict[str, object] = {}
    stack: list[tuple[int, dict[str, object]]] = [(-1, root)]

    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        if "\t" in raw_line[: len(raw_line) - len(raw_line.lstrip())]:
            raise ConfigurationError(
                f"Invalid YAML indentation on line {line_number}.",
            )

        indent = len(raw_line) - len(raw_line.lstrip(" "))
        stripped = raw_line.strip()
        if ":" not in stripped:
            raise ConfigurationError(
                f"Invalid configuration line {line_number}.",
            )

        key, raw_value = stripped.split(":", 1)
        key = key.strip()
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", key):
            raise ConfigurationError(
                f"Invalid configuration key on line {line_number}.",
            )

        while stack[-1][0] >= indent:
            stack.pop()
        parent = stack[-1][1]
        value_text = raw_value.strip()
        if not value_text:
            child: dict[str, object] = {}
            parent[key] = child
            stack.append((indent, child))
        else:
            parent[key] = _parse_scalar(value_text)

    return root


def _load_yaml(path: Path) -> dict[str, object]:
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise ConfigurationError("Configuration file was not found.") from None
    except OSError:
        raise ConfigurationError("Configuration file could not be read.") from None

    if not text.strip():
        raise ConfigurationError("Configuration file is empty.")
    return parse_yaml_subset(text)


def _require_nonempty_mapping(
    mapping: Mapping[str, object],
    key: str,
) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ConfigurationError(f"Required configuration field '{key}' is missing.")
    return value.strip()


def _validate_absolute_url(value: str, field_name: str) -> str:
    try:
        parsed = urlsplit(value)
    except ValueError:
        raise ConfigurationError(f"Invalid {field_name} URL.") from None
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ConfigurationError(f"{field_name} must be an absolute HTTP(S) URL.")
    if parsed.username or parsed.password:
        raise ConfigurationError(f"{field_name} must not contain URL credentials.")
    if parsed.fragment:
        raise ConfigurationError(f"{field_name} must not contain a URL fragment.")
    return value


def _validate_output_path(value: str) -> str:
    candidate = Path(value)
    if candidate.is_absolute():
        raise ConfigurationError("output_path must be a repository-relative path.")
    normalized = candidate.as_posix()
    if normalized in {"", "."} or ".." in candidate.parts:
        raise ConfigurationError("output_path must stay within the repository.")
    if candidate.suffix.lower() != ".md":
        raise ConfigurationError("output_path must be a Markdown file.")
    return normalized


def _validate_shell(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip().lower()
    allowed = {"pwsh", "powershell", "powershell.exe", "cmd", "cmd.exe", "bash", "sh"}
    if normalized not in allowed:
        raise ConfigurationError(
            "shell must be a supported shell name.",
        )
    return normalized


def _validate_secret_reference(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not SECRET_REFERENCE.fullmatch(value):
        raise ConfigurationError(
            f"{field_name} must contain a secret-name reference, not a credential.",
        )
    return value


def _parse_auth(config: Mapping[str, object]) -> AuthConfig:
    raw_auth = config.get("auth")
    if raw_auth is None:
        return AuthConfig()
    if not isinstance(raw_auth, dict):
        raise ConfigurationError("auth must be a mapping.")

    mode = raw_auth.get("mode", "none")
    if not isinstance(mode, str) or mode not in AUTH_MODES:
        raise ConfigurationError(
            "auth.mode must be none, bearer, basic, api_key, or oauth2_client_credentials.",
        )

    raw_secret_names = raw_auth.get("secret_names", {})
    if not isinstance(raw_secret_names, dict):
        raise ConfigurationError("auth.secret_names must be a mapping.")
    secret_names = {
        str(key): _validate_secret_reference(value, f"auth.secret_names.{key}")
        for key, value in raw_secret_names.items()
    }

    token_url = raw_auth.get("token_url")
    if token_url is not None:
        if not isinstance(token_url, str):
            raise ConfigurationError("auth.token_url must be a string.")
        token_url = _validate_absolute_url(token_url, "auth.token_url")

    header_name = raw_auth.get("header_name")
    if header_name is not None:
        if not isinstance(header_name, str) or not HEADER_NAME.fullmatch(header_name):
            raise ConfigurationError("auth.header_name is invalid.")
        header_name = header_name.strip()

    raw_scopes = raw_auth.get("scopes", [])
    if not isinstance(raw_scopes, list) or not all(
        isinstance(scope, str) and scope.strip()
        for scope in raw_scopes
    ):
        raise ConfigurationError("auth.scopes must be a list of strings.")
    scopes = tuple(scope.strip() for scope in raw_scopes)

    if mode == "none":
        if secret_names or token_url or header_name or scopes:
            raise ConfigurationError(
                "none authentication must not configure secrets or OAuth fields.",
            )
    elif mode == "bearer":
        if set(secret_names) != {"token"}:
            raise ConfigurationError(
                "bearer authentication requires auth.secret_names.token.",
            )
    elif mode == "basic":
        if set(secret_names) != {"username", "password"}:
            raise ConfigurationError(
                "basic authentication requires username and password secret-name references.",
            )
    elif mode == "api_key":
        if not header_name:
            raise ConfigurationError(
                "api_key authentication requires auth.header_name.",
            )
        if set(secret_names) != {"header_value"}:
            raise ConfigurationError(
                "api_key authentication requires auth.secret_names.header_value.",
            )
    else:
        if not token_url:
            raise ConfigurationError(
                "oauth2_client_credentials requires auth.token_url.",
            )
        if set(secret_names) != {"client_id", "client_secret"}:
            raise ConfigurationError(
                "OAuth2 authentication requires client_id and client_secret secret-name references.",
            )

    return AuthConfig(
        mode=mode,
        secret_names=secret_names,
        token_url=token_url,
        header_name=header_name,
        scopes=scopes,
    )


def _parse_environment_overrides(
    config: Mapping[str, object],
) -> dict[str, str]:
    raw_overrides = config.get("environment_overrides", {})
    if raw_overrides is None:
        return {}
    if not isinstance(raw_overrides, dict):
        raise ConfigurationError("environment_overrides must be a mapping.")

    overrides: dict[str, str] = {}
    for field_name, environment_name in raw_overrides.items():
        if field_name not in OVERRIDE_FIELDS:
            raise ConfigurationError(
                f"Unsupported environment override field '{field_name}'.",
            )
        if not isinstance(environment_name, str) or not SECRET_REFERENCE.fullmatch(
            environment_name
        ):
            raise ConfigurationError(
                f"Environment override '{field_name}' must be an environment-variable name.",
            )
        overrides[field_name] = environment_name
    return overrides


def _apply_overrides(
    config: Mapping[str, object],
    overrides: Mapping[str, str],
    environ: Mapping[str, str],
) -> dict[str, object]:
    result = dict(config)
    for field_name, environment_name in overrides.items():
        if field_name == "auth_mode":
            auth = result.get("auth")
            if not isinstance(auth, dict):
                auth = {}
                result["auth"] = auth
            if environment_name in environ:
                auth["mode"] = environ[environment_name]
            continue
        if environment_name in environ:
            result[field_name] = environ[environment_name]
    return result


def load_config(
    path: str | os.PathLike[str] = ".github/doc-sync.yml",
    *,
    environ: Mapping[str, str] | None = None,
) -> DocSyncConfig:
    """Load and validate an API synchronization configuration."""

    mapping = _load_yaml(Path(path))
    overrides = _parse_environment_overrides(mapping)
    effective = _apply_overrides(mapping, overrides, environ or os.environ)

    startup_command = _require_nonempty_mapping(effective, "startup_command")
    openapi_url = _validate_absolute_url(
        _require_nonempty_mapping(effective, "openapi_url"),
        "openapi_url",
    )
    output_path = _validate_output_path(
        effective.get("output_path", "docs/api.md")
        if isinstance(effective.get("output_path", "docs/api.md"), str)
        else ""
    )

    raw_health_url = effective.get("health_check_url")
    health_check_url = None
    if raw_health_url not in (None, ""):
        if not isinstance(raw_health_url, str):
            raise ConfigurationError("health_check_url must be a string.")
        health_check_url = _validate_absolute_url(
            raw_health_url,
            "health_check_url",
        )

    raw_shell = effective.get("shell")
    if raw_shell is not None and not isinstance(raw_shell, str):
        raise ConfigurationError("shell must be a string.")
    shell = _validate_shell(raw_shell)

    auth = _parse_auth(effective)
    return DocSyncConfig(
        startup_command=startup_command,
        openapi_url=openapi_url,
        output_path=output_path,
        health_check_url=health_check_url,
        shell=shell,
        auth=auth,
        environment_overrides=overrides,
    )
