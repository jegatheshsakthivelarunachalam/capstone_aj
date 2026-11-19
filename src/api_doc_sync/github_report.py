"""Sanitized GitHub drift report and unified-diff data."""

from __future__ import annotations

import difflib
import json
from dataclasses import dataclass
from pathlib import Path

from .drift import DriftResult
from .errors import ArtifactError
from .security import redact_text


@dataclass(frozen=True)
class UnifiedDiff:
    text: str
    has_changes: bool


@dataclass(frozen=True)
class GitHubDriftReport:
    comment: str
    unified_diff: UnifiedDiff
    patch_text: str


def build_unified_diff(
    baseline_markdown: str,
    candidate_markdown: str,
    *,
    baseline_name: str = "docs/api.md",
    candidate_name: str = "docs/api.md",
) -> UnifiedDiff:
    baseline = redact_text(baseline_markdown).splitlines(keepends=True)
    candidate = redact_text(candidate_markdown).splitlines(keepends=True)
    diff = "".join(
        difflib.unified_diff(
            baseline,
            candidate,
            fromfile=f"a/{baseline_name}",
            tofile=f"b/{candidate_name}",
        )
    )
    return UnifiedDiff(text=diff, has_changes=bool(diff))


def _append_change_lines(
    lines: list[str],
    label: str,
    values: object,
) -> None:
    if isinstance(values, list):
        for value in values:
            lines.append(f"- {label}: {value}")


def _append_schema_field_lines(
    lines: list[str],
    label: str,
    values: object,
) -> None:
    if not isinstance(values, dict):
        return

    for schema_name, fields in sorted(values.items()):
        if isinstance(fields, list):
            for field_name in fields:
                lines.append(
                    f"- {label}: `{schema_name}.{field_name}`"
                )


def build_pr_comment(
    drift: DriftResult,
    *,
    workflow_url: str | None = None,
    artifact_url: str | None = None,
) -> str:
    links: list[str] = []
    if workflow_url:
        links.append(f"[Workflow run]({workflow_url})")
    if artifact_url:
        links.append(f"[Suggested patch]({artifact_url})")

    lines = [
        "<!-- api-doc-sync-drift -->",
        "## API documentation drift detected",
        f"- Changed fact groups: {len(drift.changed_facts)}",
        f"- Paths: {drift.path_count}",
        f"- Schemas: {drift.schema_count}",
        f"- Missing facts: {len(drift.missing_facts)}",
    ]

    changes = getattr(drift, "changes", {}) or {}

    _append_change_lines(lines, "Added path", changes.get("added_paths"))
    _append_change_lines(lines, "Removed path", changes.get("removed_paths"))
    _append_change_lines(lines, "Modified path", changes.get("modified_paths"))

    _append_change_lines(
        lines, "Added operation", changes.get("added_operations")
    )
    _append_change_lines(
        lines, "Removed operation", changes.get("removed_operations")
    )
    _append_change_lines(
        lines, "Modified operation", changes.get("modified_operations")
    )

    _append_change_lines(lines, "Added schema", changes.get("added_schemas"))
    _append_change_lines(lines, "Removed schema", changes.get("removed_schemas"))
    _append_change_lines(
        lines, "Modified schema", changes.get("modified_schemas")
    )

    _append_schema_field_lines(
        lines, "Added schema field", changes.get("added_schema_fields")
    )
    _append_schema_field_lines(
        lines, "Removed schema field", changes.get("removed_schema_fields")
    )
    _append_schema_field_lines(
        lines, "Modified schema field", changes.get("modified_schema_fields")
    )

    if drift.missing_facts:
        lines.append("")
        lines.append("### Validation warnings")
        for fact in drift.missing_facts:
            lines.append(f"- {fact}")

    if links:
        lines.append("")
        lines.append(" | ".join(links))

    return "\n".join(lines)


def build_github_report(
    drift: DriftResult,
    baseline_markdown: str,
    candidate_markdown: str,
    *,
    workflow_url: str | None = None,
    artifact_url: str | None = None,
) -> GitHubDriftReport:
    diff = build_unified_diff(
        baseline_markdown,
        candidate_markdown,
    )
    comment = build_pr_comment(
        drift,
        workflow_url=workflow_url,
        artifact_url=artifact_url,
    )
    safe_comment = redact_text(comment)
    safe_diff = redact_text(diff.text)
    return GitHubDriftReport(
        comment=safe_comment,
        unified_diff=UnifiedDiff(
            text=safe_diff,
            has_changes=bool(safe_diff),
        ),
        patch_text=safe_diff,
    )


def write_patch(path: str, report: GitHubDriftReport) -> str:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        target.write_text(redact_text(report.patch_text), encoding="utf-8")
    except OSError:
        raise ArtifactError("Unified-diff artifact could not be written.") from None
    return str(target)


def write_patch_text(path: str, text: str) -> str:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        target.write_text(redact_text(text), encoding="utf-8")
    except OSError:
        raise ArtifactError("Unified-diff artifact could not be written.") from None
    return str(target)


def write_report_json(path: str, report: dict[str, object]) -> str:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        target.write_text(
            redact_text(json.dumps(report, sort_keys=True)),
            encoding="utf-8",
        )
    except OSError:
        raise ArtifactError("Drift report artifact could not be written.") from None
    return str(target)
