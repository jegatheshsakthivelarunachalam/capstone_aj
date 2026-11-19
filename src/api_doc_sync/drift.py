"""Semantic drift detection using canonical model metadata."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping

from .errors import ParseError
from .model import CanonicalApiModel, deserialize_metadata


@dataclass(frozen=True)
class DriftResult:
    has_drift: bool
    changed_facts: tuple[str, ...]
    missing_facts: tuple[str, ...]
    path_count: int
    schema_count: int
    changes: dict[str, object] = field(default_factory=dict)


def _index_by(items: list[dict[str, object]], key: str) -> dict[str, dict[str, object]]:
    """Index canonical facts by a stable identifying field."""
    return {
        str(item[key]): item
        for item in items
        if key in item
    }


def _operation_key(operation: dict[str, object]) -> str:
    return f"{operation.get('method', 'Not Found')} {operation.get('path', 'Not Found')}"


def _schema_properties(schema: dict[str, object]) -> dict[str, object]:
    properties = schema.get("schema", {})
    if not isinstance(properties, Mapping):
        return {}

    fields = properties.get("properties", {})
    if not isinstance(fields, Mapping):
        return {}

    return {str(name): value for name, value in fields.items()}


def _compare_details(
    baseline_payload: dict[str, object],
    candidate_payload: dict[str, object],
) -> dict[str, object]:
    baseline_paths = _index_by(baseline_payload["paths"], "path")
    candidate_paths = _index_by(candidate_payload["paths"], "path")

    baseline_operations = {
        _operation_key(item): item
        for item in baseline_payload["operations"]
    }
    candidate_operations = {
        _operation_key(item): item
        for item in candidate_payload["operations"]
    }

    baseline_schemas = _index_by(baseline_payload["schemas"], "name")
    candidate_schemas = _index_by(candidate_payload["schemas"], "name")

    added_paths = sorted(set(candidate_paths) - set(baseline_paths))
    removed_paths = sorted(set(baseline_paths) - set(candidate_paths))
    modified_paths = sorted(
        name
        for name in set(baseline_paths) & set(candidate_paths)
        if baseline_paths[name] != candidate_paths[name]
    )

    added_operations = sorted(
        set(candidate_operations) - set(baseline_operations)
    )
    removed_operations = sorted(
        set(baseline_operations) - set(candidate_operations)
    )
    modified_operations = sorted(
        name
        for name in set(baseline_operations) & set(candidate_operations)
        if baseline_operations[name] != candidate_operations[name]
    )

    added_schemas = sorted(set(candidate_schemas) - set(baseline_schemas))
    removed_schemas = sorted(set(baseline_schemas) - set(candidate_schemas))

    modified_schemas = sorted(
        name
        for name in set(baseline_schemas) & set(candidate_schemas)
        if baseline_schemas[name] != candidate_schemas[name]
    )

    added_schema_fields: dict[str, list[str]] = {}
    removed_schema_fields: dict[str, list[str]] = {}
    modified_schema_fields: dict[str, list[str]] = {}

    for name in added_schemas:
        fields = _schema_properties(candidate_schemas[name])
        if fields:
            added_schema_fields[name] = sorted(fields)

    for name in removed_schemas:
        fields = _schema_properties(baseline_schemas[name])
        if fields:
            removed_schema_fields[name] = sorted(fields)

    for name in set(baseline_schemas) & set(candidate_schemas):
        old_fields = _schema_properties(baseline_schemas[name])
        new_fields = _schema_properties(candidate_schemas[name])

        added = sorted(set(new_fields) - set(old_fields))
        removed = sorted(set(old_fields) - set(new_fields))
        modified = sorted(
            field_name
            for field_name in set(old_fields) & set(new_fields)
            if old_fields[field_name] != new_fields[field_name]
        )

        if added:
            added_schema_fields[name] = added
        if removed:
            removed_schema_fields[name] = removed
        if modified:
            modified_schema_fields[name] = modified

    return {
        "added_paths": added_paths,
        "removed_paths": removed_paths,
        "modified_paths": modified_paths,
        "added_operations": added_operations,
        "removed_operations": removed_operations,
        "modified_operations": modified_operations,
        "added_schemas": added_schemas,
        "removed_schemas": removed_schemas,
        "modified_schemas": modified_schemas,
        "added_schema_fields": added_schema_fields,
        "removed_schema_fields": removed_schema_fields,
        "modified_schema_fields": modified_schema_fields,
    }


def compare_models(
    baseline: CanonicalApiModel,
    candidate: CanonicalApiModel,
) -> DriftResult:
    baseline_payload = baseline.normalized().to_dict()
    candidate_payload = candidate.normalized().to_dict()

    changed: list[str] = []

    if baseline_payload["openapi_version"] != candidate_payload["openapi_version"]:
        changed.append("openapi_version")
    if baseline_payload["paths"] != candidate_payload["paths"]:
        changed.append("paths")
    if baseline_payload["operations"] != candidate_payload["operations"]:
        changed.append("operations")
    if baseline_payload["schemas"] != candidate_payload["schemas"]:
        changed.append("schemas")

    # Only report genuinely absent API collections. "Not Found" is also
    # used for optional descriptive fields, so counting every occurrence
    # would incorrectly report normal optional values as missing.
    missing: list[str] = []
    if not candidate_payload["paths"]:
        missing.append("No API paths")
    if not candidate_payload["schemas"]:
        missing.append("No API schemas")

    changes = _compare_details(baseline_payload, candidate_payload)

    return DriftResult(
        has_drift=bool(changed),
        changed_facts=tuple(changed),
        missing_facts=tuple(missing),
        path_count=len(candidate_payload["paths"]),
        schema_count=len(candidate_payload["schemas"]),
        changes=changes,
    )


def parse_baseline_markdown(markdown: str) -> CanonicalApiModel:
    try:
        return deserialize_metadata(markdown)
    except ValueError as error:
        raise ParseError(
            "Committed docs/api.md baseline metadata is invalid."
        ) from error


def load_baseline(path: str) -> CanonicalApiModel:
    baseline = Path(path)
    if not baseline.exists():
        raise ParseError("Committed docs/api.md baseline is missing.")
    try:
        markdown = baseline.read_text(encoding="utf-8")
    except OSError:
        raise ParseError(
            "Committed docs/api.md baseline could not be read."
        ) from None
    return parse_baseline_markdown(markdown)


def detect_drift(
    baseline_markdown: str,
    candidate_model: CanonicalApiModel,
) -> DriftResult:
    baseline = parse_baseline_markdown(baseline_markdown)
    return compare_models(baseline, candidate_model)
