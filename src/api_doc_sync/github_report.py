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
    if links:
        lines.append("- " + " | ".join(links))
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
