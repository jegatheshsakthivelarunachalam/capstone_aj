"""Semantic drift detection using canonical model metadata."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .errors import DriftError, ParseError
from .model import (
    CanonicalApiModel,
    deserialize_metadata,
)


@dataclass(frozen=True)
class DriftResult:
    has_drift: bool
    changed_facts: tuple[str, ...]
    missing_facts: tuple[str, ...]
    path_count: int
    schema_count: int


def compare_models(
    baseline: CanonicalApiModel,
    candidate: CanonicalApiModel,
) -> DriftResult:
    baseline = baseline.normalized()
    candidate = candidate.normalized()
    baseline_payload = baseline.to_dict()
    candidate_payload = candidate.to_dict()

    changed: list[str] = []
    missing: list[str] = []

    if baseline_payload["openapi_version"] != candidate_payload["openapi_version"]:
        changed.append("openapi_version")
    if baseline_payload["paths"] != candidate_payload["paths"]:
        changed.append("paths")
    if baseline_payload["operations"] != candidate_payload["operations"]:
        changed.append("operations")
    if baseline_payload["schemas"] != candidate_payload["schemas"]:
        changed.append("schemas")

    candidate_text = str(candidate_payload)
    missing_marker_count = candidate_text.count("Not Found")
    if missing_marker_count:
        missing.append(f"{missing_marker_count} missing field(s)")
    if not candidate_payload["paths"]:
        missing.append("No API paths")
    if not candidate_payload["schemas"]:
        missing.append("No API schemas")

    return DriftResult(
        has_drift=bool(changed),
        changed_facts=tuple(changed),
        missing_facts=tuple(missing),
        path_count=len(candidate_payload["paths"]),
        schema_count=len(candidate_payload["schemas"]),
    )


def parse_baseline_markdown(markdown: str) -> CanonicalApiModel:
    try:
        return deserialize_metadata(markdown)
    except ValueError as error:
        raise ParseError("Committed docs/api.md baseline metadata is invalid.") from error


def load_baseline(path: str) -> CanonicalApiModel:
    baseline = Path(path)
    if not baseline.exists():
        raise ParseError("Committed docs/api.md baseline is missing.")
    try:
        markdown = baseline.read_text(encoding="utf-8")
    except OSError:
        raise ParseError("Committed docs/api.md baseline could not be read.") from None
    return parse_baseline_markdown(markdown)


def detect_drift(
    baseline_markdown: str,
    candidate_model: CanonicalApiModel,
) -> DriftResult:
    baseline = parse_baseline_markdown(baseline_markdown)
    return compare_models(baseline, candidate_model)
