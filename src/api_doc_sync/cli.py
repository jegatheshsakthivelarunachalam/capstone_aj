"""CLI orchestration for pull-request API documentation synchronization."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

from .config import DocSyncConfig, load_config
from .drift import detect_drift, load_baseline
from .errors import ApiDocSyncError, ArtifactError, DriftError, GenerationError
from .github_report import (
    build_github_report,
    build_unified_diff,
    write_patch_text,
    write_report_json,
)
from .lifecycle import ApplicationLifecycle
from .markdown import render_markdown
from .openapi import retrieve_openapi


class CliResult:
    def __init__(
        self,
        exit_code: int,
        candidate_markdown: str,
        baseline_markdown: str | None,
        report: dict[str, object],
    ) -> None:
        self.exit_code = exit_code
        self.candidate_markdown = candidate_markdown
        self.baseline_markdown = baseline_markdown
        self.report = report


def run(
    config_path: str = ".github/doc-sync.yml",
    app_root: str | os.PathLike[str] | None = None,
    baseline_root: str | os.PathLike[str] | None = None,
) -> CliResult:
    config = load_config(config_path)
    lifecycle = ApplicationLifecycle(
        config,
        working_directory=app_root,
    )

    with tempfile.TemporaryDirectory(prefix="api-doc-sync-") as temp_dir:
        temp = Path(temp_dir)
        try:
            lifecycle.start_and_wait()
            model = retrieve_openapi(
                config,
                environ=os.environ,
            )
            candidate = render_markdown(model)
        finally:
            lifecycle.stop()

        resolved_baseline_root = (
            Path(baseline_root) if baseline_root is not None
            else (Path(app_root) if app_root is not None else Path("."))
        )
        baseline_path = resolved_baseline_root / config.output_path
        baseline_markdown: str | None = None
        if baseline_path.exists():
            try:
                baseline_markdown = baseline_path.read_text(encoding="utf-8")
            except OSError:
                raise ArtifactError("Committed docs/api.md baseline could not be read.")
            drift = detect_drift(baseline_markdown, model)
        else:
            drift = None

        patch_path = temp / "docs-api.patch"
        if baseline_markdown is None:
            write_patch_text(str(patch_path), candidate)
        else:
            github_report = build_github_report(
                drift,
                baseline_markdown,
                candidate,
            )
            write_patch_text(str(patch_path), github_report.patch_text)

        report = {
            "has_drift": bool(drift and drift.has_drift),
            "missing_baseline": baseline_markdown is None,
            "changed_facts": list(drift.changed_facts) if drift else [],
            "missing_facts": list(drift.missing_facts) if drift else [],
            "path_count": drift.path_count if drift else len(model.to_dict()["paths"]),
            "schema_count": drift.schema_count if drift else len(model.to_dict()["schemas"]),
            "patch_path": str(patch_path),
        }

        if baseline_markdown is None:
            exit_code = 1
        elif drift.has_drift:
            exit_code = 1
        else:
            exit_code = 0

        return CliResult(
            exit_code=exit_code,
            candidate_markdown=candidate,
            baseline_markdown=baseline_markdown,
            report=report,
        )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate live OpenAPI documentation and detect drift.",
    )
    parser.add_argument(
        "--config",
        default=".github/doc-sync.yml",
        help="Repository-relative API sync configuration.",
    )
    parser.add_argument(
        "--report",
        default=None,
        help="Optional sanitized JSON report output path.",
    )
    parser.add_argument(
        "--patch",
        default=None,
        help="Optional sanitized unified-diff or replacement patch output path.",
    )
    parser.add_argument(
        "--app-root",
        default=None,
        help="Repository-relative application source root used for startup and baseline files.",
    )
    parser.add_argument(
        "--baseline-root",
        default=None,
        help="Repository-relative trusted base checkout root used for docs/api.md.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    try:
        result = run(args.config, args.app_root, args.baseline_root)
    except ApiDocSyncError as error:
        print(
            f"{error.code}: {error.message}",
            file=sys.stderr,
        )
        return 1
    except Exception:
        print("Unexpected API documentation synchronization failure.", file=sys.stderr)
        return 1

    if args.report:
        try:
            report_path = Path(args.report)
            write_report_json(str(report_path), result.report)
        except ArtifactError as error:
            print(f"{error.code}: {error.message}", file=sys.stderr)
            return 1

    if args.patch:
        try:
            patch_path = Path(args.patch)
            if result.baseline_markdown is None:
                write_patch_text(str(patch_path), result.candidate_markdown)
            else:
                diff = build_unified_diff(
                    result.baseline_markdown,
                    result.candidate_markdown,
                )
                write_patch_text(str(patch_path), diff.text)
        except ArtifactError as error:
            print(f"{error.code}: {error.message}", file=sys.stderr)
            return 1

    print(json.dumps(result.report, sort_keys=True))
    return result.exit_code
