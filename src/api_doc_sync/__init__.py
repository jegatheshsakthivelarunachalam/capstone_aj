"""Automated API documentation synchronization."""

from .errors import (
    ApiDocSyncError,
    ArtifactError,
    ConfigurationError,
    DriftError,
    ExtractError,
    FetchError,
    GenerationError,
    OpenApiError,
    ParseError,
    ReadinessError,
    ReportError,
    StartupError,
)
from .openapi import OpenAPIFetcher, retrieve_openapi
from .markdown import render_markdown, write_markdown
from .drift import compare_models, detect_drift, load_baseline
from .github_report import build_github_report, build_unified_diff, write_patch
from .lifecycle import ApplicationLifecycle, ProcessInfo
from .model import (
    CanonicalApiModel,
    HeaderFact,
    OperationFact,
    ParameterFact,
    PathFact,
    RequestBodyFact,
    ResponseFact,
    SchemaFact,
)
from .security import redact_text, redact_url, sanitize_for_metadata
from .config import AuthConfig, DocSyncConfig, load_config
from .cli import CliResult, build_arg_parser, main as cli_main, run

__all__ = [
    "ApiDocSyncError",
    "ArtifactError",
    "ConfigurationError",
    "DriftError",
    "ExtractError",
    "FetchError",
    "GenerationError",
    "OpenApiError",
    "ParseError",
    "ReadinessError",
    "ReportError",
    "StartupError",
    "OpenAPIFetcher",
    "retrieve_openapi",
    "render_markdown",
    "write_markdown",
    "compare_models",
    "detect_drift",
    "load_baseline",
    "build_github_report",
    "build_unified_diff",
    "write_patch",
    "ApplicationLifecycle",
    "ProcessInfo",
    "CanonicalApiModel",
    "HeaderFact",
    "OperationFact",
    "ParameterFact",
    "PathFact",
    "RequestBodyFact",
    "ResponseFact",
    "SchemaFact",
    "redact_text",
    "redact_url",
    "sanitize_for_metadata",
    "AuthConfig",
    "DocSyncConfig",
    "load_config",
    "CliResult",
    "build_arg_parser",
    "cli_main",
    "run",
]
