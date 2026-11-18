"""Sanitization helpers for logs, artifacts, Markdown, and reports."""

from __future__ import annotations

import os
import re
import tempfile
from collections.abc import Iterable, Mapping
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

REDACTION = "[REDACTED]"

SENSITIVE_FIELD_NAMES = re.compile(
    r"(?i)(authorization|proxy[-_]?authorization|password|passwd|secret|"
    r"client[-_]?secret|access[-_]?token|refresh[-_]?token|id[-_]?token|"
    r"bearer|api[-_]?key|x[-_]?api[-_]?key|token)",
)


def redact_text(text: str, known_secrets: Iterable[str] = ()) -> str:
    """Redact common credential formats and explicitly supplied secrets."""

    result = str(text)
    for secret in known_secrets:
        if secret:
            result = result.replace(str(secret), REDACTION)

    patterns = (
        r"\bBearer\s+[A-Za-z0-9._~+/=-]+\b",
        r"\bBasic\s+[A-Za-z0-9+/=]+\b",
        r"\b(Basic|Bearer)\s*[:=]\s*[^\s,\"']+",
        r"\bgithub_pat_[A-Za-z0-9_]{20,}\b",
        r"\bgh[pousr]_[A-Za-z0-9]{20,}\b",
        r"\bsk-[A-Za-z0-9_-]{20,}\b",
        r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b",
        r"\bAKIA[0-9A-Z]{16}\b",
        r"\bAIza[0-9A-Za-z_-]{30,}\b",
        r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}",
        r"https://[^/\s:@]+:[^/\s@]+@",
    )
    for pattern in patterns:
        result = re.sub(pattern, REDACTION, result, flags=re.IGNORECASE)

    assignment_pattern = re.compile(
        r"(?i)(\b(?:password|passwd|secret|client[_-]?secret|access[_-]?token|"
        r"refresh[_-]?token|id[_-]?token|api[_-]?key|authorization|"
        r"proxy[-_]?authorization|bearer|token)\b)"
        r"(\s*[:=]\s*)(\"[^\"]*\"|'[^']*'|[^\s,;\"'<>]+)",
    )
    result = assignment_pattern.sub(r"\1\2" + REDACTION, result)

    return result


def redact_url(url: str, known_secrets: Iterable[str] = ()) -> str:
    """Redact userinfo and sensitive query parameters in a URL."""

    redacted = str(url)
    for secret in known_secrets:
        if secret:
            redacted = redacted.replace(str(secret), REDACTION)
    try:
        parsed = urlsplit(redacted)
    except ValueError:
        return REDACTION

    netloc = parsed.netloc
    if "@" in netloc:
        host = netloc.rsplit("@", 1)[-1]
        netloc = f"{REDACTION}@{host}"

    query_items = []
    for name, value in parse_qsl(parsed.query, keep_blank_values=True):
        if SENSITIVE_FIELD_NAMES.search(name):
            value = REDACTION
        query_items.append((name, value))
    query = urlencode(query_items)
    return urlunsplit((parsed.scheme, netloc, parsed.path, query, ""))


def redact_headers(
    headers: Mapping[str, object],
    known_secrets: Iterable[str] = (),
) -> dict[str, str]:
    """Redact sensitive header names and values."""

    redacted: dict[str, str] = {}
    for name, value in headers.items():
        header_name = str(name)
        if SENSITIVE_FIELD_NAMES.search(header_name):
            redacted[header_name] = REDACTION
        else:
            redacted[header_name] = redact_text(str(value), known_secrets)
    return redacted


def sanitize_value(value: object, known_secrets: Iterable[str] = ()) -> object:
    """Recursively redact strings, mappings, and sequences."""

    secrets = tuple(known_secrets)
    if isinstance(value, Mapping):
        sanitized: dict[str, object] = {}
        for key, child in value.items():
            key_text = str(key)
            if SENSITIVE_FIELD_NAMES.search(key_text):
                sanitized[key_text] = REDACTION
            else:
                sanitized[key_text] = sanitize_value(child, secrets)
        return sanitized
    if isinstance(value, list):
        return [sanitize_value(child, secrets) for child in value]
    if isinstance(value, tuple):
        return [sanitize_value(child, secrets) for child in value]
    if isinstance(value, (str, bytes)):
        if isinstance(value, bytes):
            try:
                value = value.decode("utf-8")
            except UnicodeDecodeError:
                return REDACTION
        return redact_text(value, secrets)
    return value


def write_sanitized_text(
    path: str | os.PathLike[str],
    content: str,
    known_secrets: Iterable[str] = (),
) -> None:
    """Write redacted text to a temp or report path."""

    target = Path(path)
    target.write_text(
        redact_text(content, known_secrets),
        encoding="utf-8",
    )


def sanitize_for_metadata(
    value: Mapping[str, object],
    known_secrets: Iterable[str] = (),
) -> dict[str, object]:
    """Sanitize data before Base64 metadata, Markdown, or diff generation."""

    sanitized = _sanitize_metadata_object(value, tuple(known_secrets))
    if not isinstance(sanitized, dict):
        return {}
    return sanitized


def _sanitize_metadata_object(
    value: object,
    known_secrets: tuple[str, ...],
) -> object:
    if isinstance(value, Mapping):
        sanitized: dict[str, object] = {}
        for key, child in value.items():
            key_text = str(key)
            if SENSITIVE_FIELD_NAMES.search(key_text):
                sanitized[key_text] = REDACTION
                continue

            if key_text == "headers" and isinstance(child, list):
                sanitized_headers: list[object] = []
                for header in child:
                    if isinstance(header, Mapping):
                        header_name = str(header.get("name", ""))
                        header_copy = dict(header)
                        if _is_sensitive_header_name(header_name):
                            if "schema" in header_copy:
                                header_copy["schema"] = {"value": REDACTION}
                            if "example" in header_copy:
                                header_copy["example"] = REDACTION
                        sanitized_headers.append(
                            _sanitize_metadata_object(header_copy, known_secrets)
                        )
                    else:
                        sanitized_headers.append(
                            _sanitize_metadata_object(header, known_secrets)
                        )
                sanitized[key_text] = sanitized_headers
                continue

            sanitized[key_text] = _sanitize_metadata_object(child, known_secrets)
        return sanitized

    if isinstance(value, list):
        return [_sanitize_metadata_object(child, known_secrets) for child in value]
    if isinstance(value, tuple):
        return [_sanitize_metadata_object(child, known_secrets) for child in value]
    if isinstance(value, str):
        stripped = value.strip()
        if re.match(r"(?i)^https?://", stripped):
            return redact_url(stripped, known_secrets)
        return redact_text(stripped, known_secrets)
    return value


def _is_sensitive_header_name(header_name: str) -> bool:
    normalized = header_name.strip().lower().replace("_", "-")
    return normalized in {
        "authorization",
        "proxy-authorization",
        "x-api-key",
        "api-key",
        "token",
        "password",
        "passwd",
    }


def create_safe_temp_directory(prefix: str = "api-doc-sync-") -> tempfile.TemporaryDirectory[str]:
    """Create a unique temporary directory that caller code cleans up."""

    return tempfile.TemporaryDirectory(prefix=prefix)
