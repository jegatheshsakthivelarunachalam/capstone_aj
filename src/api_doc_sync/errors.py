"""Exception types for API documentation synchronization."""

from enum import Enum


class ApiDocSyncStage(str, Enum):
    STARTUP = "startup"
    READINESS = "readiness"
    FETCH = "fetch"
    PARSE = "parse"
    EXTRACT = "extract"
    GENERATE = "generate"
    DRIFT = "drift"
    ARTIFACT = "artifact"
    REPORT = "report"


class ApiDocSyncError(Exception):
    """Base exception for a sanitized API documentation sync failure."""

    def __init__(
        self,
        stage: ApiDocSyncStage,
        message: str,
        *,
        details: str | None = None,
    ) -> None:
        super().__init__(message)
        self.stage = stage
        self.message = message
        self.details = None
        self.code = f"{stage.value.upper()}_FAILED"


class SanitizedApiDocSyncError(ApiDocSyncError):
    """Stage error with an optional diagnostic code and no raw details."""

    def __init__(
        self,
        stage: ApiDocSyncStage,
        code: str,
        message: str,
    ) -> None:
        super().__init__(stage, message)
        self.code = code


class StartupError(SanitizedApiDocSyncError):
    def __init__(self, message: str = "Application startup failed.") -> None:
        super().__init__(ApiDocSyncStage.STARTUP, "STARTUP_FAILED", message)


class ReadinessError(SanitizedApiDocSyncError):
    def __init__(self, message: str = "Application readiness check failed.") -> None:
        super().__init__(ApiDocSyncStage.READINESS, "READINESS_FAILED", message)


class FetchError(SanitizedApiDocSyncError):
    def __init__(self, message: str = "OpenAPI fetch failed.") -> None:
        super().__init__(ApiDocSyncStage.FETCH, "FETCH_FAILED", message)


class ParseError(SanitizedApiDocSyncError):
    def __init__(self, message: str = "OpenAPI document could not be parsed.") -> None:
        super().__init__(ApiDocSyncStage.PARSE, "PARSE_FAILED", message)


class ExtractError(SanitizedApiDocSyncError):
    def __init__(self, message: str = "OpenAPI facts could not be extracted.") -> None:
        super().__init__(ApiDocSyncStage.EXTRACT, "EXTRACT_FAILED", message)


class DriftError(SanitizedApiDocSyncError):
    def __init__(self, message: str = "Documentation drift check failed.") -> None:
        super().__init__(ApiDocSyncStage.DRIFT, "DRIFT_FAILED", message)


class ArtifactError(SanitizedApiDocSyncError):
    def __init__(self, message: str = "Artifact generation failed.") -> None:
        super().__init__(ApiDocSyncStage.ARTIFACT, "ARTIFACT_FAILED", message)


class ReportError(SanitizedApiDocSyncError):
    def __init__(self, message: str = "GitHub report failed.") -> None:
        super().__init__(ApiDocSyncStage.REPORT, "REPORT_FAILED", message)


class ConfigurationError(ApiDocSyncError):
    """Raised when synchronization configuration is invalid."""

    def __init__(self, message: str, *, details: str | None = None) -> None:
        super().__init__(
            ApiDocSyncStage.PARSE,
            message,
            details=details,
        )


class OpenApiError(ApiDocSyncError):
    """Raised for fetch, parsing, or validation failures."""

    def __init__(
        self,
        stage: ApiDocSyncStage,
        message: str,
        *,
        details: str | None = None,
    ) -> None:
        super().__init__(stage, message, details=details)


class GenerationError(ApiDocSyncError):
    """Raised when Markdown or report generation fails."""

    def __init__(self, message: str, *, details: str | None = None) -> None:
        super().__init__(
            ApiDocSyncStage.GENERATE,
            message,
            details=details,
        )
