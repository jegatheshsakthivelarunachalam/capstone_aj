"""Canonical API facts and HTML metadata for documentation synchronization."""

from __future__ import annotations

import base64
import json
import re
from dataclasses import dataclass, field
from typing import Iterable, Mapping

NOT_FOUND = "Not Found"
METADATA_VERSION = 1
METADATA_MARKER = "api-doc-sync-metadata"
METADATA_PATTERN = re.compile(
    r"<!--\s*api-doc-sync-metadata:([A-Za-z0-9_-]+={0,2})\s*-->",
)


def missing(value: object | None) -> str:
    """Convert missing values consistently to the project-wide marker."""

    if value is None:
        return NOT_FOUND
    if isinstance(value, str):
        stripped = value.strip()
        return stripped if stripped else NOT_FOUND
    return str(value)


def _schema_value(value: object | None) -> dict[str, object]:
    if value is None:
        return {"type": NOT_FOUND}
    if not isinstance(value, Mapping):
        return {"type": NOT_FOUND}
    if not value:
        return {"type": NOT_FOUND}
    return _canonical_json(value)


def _canonical_json(value: object) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise TypeError("Expected a mapping for canonical JSON data.")
    return json.loads(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    )


@dataclass(frozen=True)
class ParameterFact:
    name: str = NOT_FOUND
    location: str = NOT_FOUND
    required: bool = False
    schema: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", missing(self.name))
        object.__setattr__(self, "location", missing(self.location))
        object.__setattr__(self, "schema", _schema_value(self.schema))

    def to_dict(self) -> dict[str, object]:
        return {
            "location": self.location,
            "name": self.name,
            "required": self.required,
            "schema": self.schema,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> "ParameterFact":
        return cls(
            name=missing(value.get("name")),
            location=missing(value.get("location")),
            required=bool(value.get("required", False)),
            schema=_schema_value(value.get("schema")),
        )


@dataclass(frozen=True)
class HeaderFact:
    name: str = NOT_FOUND
    required: bool = False
    schema: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", missing(self.name))
        object.__setattr__(self, "schema", _schema_value(self.schema))

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "required": self.required,
            "schema": self.schema,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> "HeaderFact":
        return cls(
            name=missing(value.get("name")),
            required=bool(value.get("required", False)),
            schema=_schema_value(value.get("schema")),
        )


@dataclass(frozen=True)
class SchemaFact:
    name: str = NOT_FOUND
    media_type: str = NOT_FOUND
    schema: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", missing(self.name))
        object.__setattr__(self, "media_type", missing(self.media_type))
        object.__setattr__(self, "schema", _schema_value(self.schema))

    def to_dict(self) -> dict[str, object]:
        return {
            "media_type": self.media_type,
            "name": self.name,
            "schema": self.schema,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> "SchemaFact":
        return cls(
            name=missing(value.get("name")),
            media_type=missing(value.get("media_type")),
            schema=_schema_value(value.get("schema")),
        )


@dataclass(frozen=True)
class RequestBodyFact:
    required: bool = False
    schemas: tuple[SchemaFact, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "required": self.required,
            "schemas": [schema.to_dict() for schema in self.schemas],
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> "RequestBodyFact":
        raw_schemas = value.get("schemas", [])
        if not isinstance(raw_schemas, list):
            raw_schemas = []
        return cls(
            required=bool(value.get("required", False)),
            schemas=tuple(
                SchemaFact.from_dict(item)
                for item in raw_schemas
                if isinstance(item, Mapping)
            ),
        )


@dataclass(frozen=True)
class ResponseFact:
    status: str = NOT_FOUND
    description: str = NOT_FOUND
    headers: tuple[HeaderFact, ...] = ()
    schemas: tuple[SchemaFact, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "status", missing(self.status))
        object.__setattr__(self, "description", missing(self.description))

    def to_dict(self) -> dict[str, object]:
        return {
            "description": self.description,
            "headers": [header.to_dict() for header in self.headers],
            "schemas": [schema.to_dict() for schema in self.schemas],
            "status": self.status,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> "ResponseFact":
        raw_headers = value.get("headers", [])
        raw_schemas = value.get("schemas", [])
        if not isinstance(raw_headers, list):
            raw_headers = []
        if not isinstance(raw_schemas, list):
            raw_schemas = []
        return cls(
            status=missing(value.get("status")),
            description=missing(value.get("description")),
            headers=tuple(
                HeaderFact.from_dict(item)
                for item in raw_headers
                if isinstance(item, Mapping)
            ),
            schemas=tuple(
                SchemaFact.from_dict(item)
                for item in raw_schemas
                if isinstance(item, Mapping)
            ),
        )


@dataclass(frozen=True)
class OperationFact:
    path: str = NOT_FOUND
    method: str = NOT_FOUND
    summary: str = NOT_FOUND
    parameters: tuple[ParameterFact, ...] = ()
    request_body: RequestBodyFact | None = None
    responses: tuple[ResponseFact, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "path", missing(self.path))
        normalized_method = missing(self.method)
        object.__setattr__(
            self,
            "method",
            normalized_method.upper()
            if normalized_method != NOT_FOUND
            else NOT_FOUND,
        )
        object.__setattr__(self, "summary", missing(self.summary))

    def to_dict(self) -> dict[str, object]:
        return {
            "method": self.method,
            "parameters": [parameter.to_dict() for parameter in self.parameters],
            "path": self.path,
            "request_body": (
                self.request_body.to_dict()
                if self.request_body is not None
                else None
            ),
            "responses": [response.to_dict() for response in self.responses],
            "summary": self.summary,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> "OperationFact":
        raw_parameters = value.get("parameters", [])
        raw_responses = value.get("responses", [])
        raw_request_body = value.get("request_body")
        if not isinstance(raw_parameters, list):
            raw_parameters = []
        if not isinstance(raw_responses, list):
            raw_responses = []
        normalized_method = missing(value.get("method"))
        return cls(
            path=missing(value.get("path")),
            method=(
                normalized_method.upper()
                if normalized_method != NOT_FOUND
                else NOT_FOUND
            ),
            summary=missing(value.get("summary")),
            parameters=tuple(
                ParameterFact.from_dict(item)
                for item in raw_parameters
                if isinstance(item, Mapping)
            ),
            request_body=(
                RequestBodyFact.from_dict(raw_request_body)
                if isinstance(raw_request_body, Mapping)
                else None
            ),
            responses=tuple(
                ResponseFact.from_dict(item)
                for item in raw_responses
                if isinstance(item, Mapping)
            ),
        )


@dataclass(frozen=True)
class PathFact:
    path: str = NOT_FOUND
    summary: str = NOT_FOUND

    def __post_init__(self) -> None:
        object.__setattr__(self, "path", missing(self.path))
        object.__setattr__(self, "summary", missing(self.summary))

    def to_dict(self) -> dict[str, object]:
        return {
            "path": self.path,
            "summary": self.summary,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> "PathFact":
        return cls(
            path=missing(value.get("path")),
            summary=missing(value.get("summary")),
        )


@dataclass(frozen=True)
class CanonicalApiModel:
    """Canonical API facts independent of HTTP, GitHub, and Markdown."""

    openapi_version: str = NOT_FOUND
    paths: tuple[PathFact, ...] = ()
    operations: tuple[OperationFact, ...] = ()
    schemas: tuple[SchemaFact, ...] = ()
    facts: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "openapi_version", missing(self.openapi_version))

    def normalized(self) -> "CanonicalApiModel":
        """Return a stable copy while preserving path and operation source order."""

        paths = tuple(self.paths)
        operations = tuple(
            OperationFact(
                path=operation.path,
                method=operation.method,
                summary=operation.summary,
                parameters=tuple(operation.parameters),
                request_body=(
                    RequestBodyFact(
                        required=operation.request_body.required,
                        schemas=tuple(operation.request_body.schemas),
                    )
                    if operation.request_body is not None
                    else None
                ),
                responses=tuple(
                    ResponseFact(
                        status=response.status,
                        description=response.description,
                        headers=tuple(response.headers),
                        schemas=tuple(response.schemas),
                    )
                    for response in operation.responses
                ),
            )
            for operation in self.operations
        )
        schemas = tuple(self.schemas)
        return CanonicalApiModel(
            openapi_version=self.openapi_version,
            paths=paths,
            operations=operations,
            schemas=schemas,
            facts=dict(self.facts),
        )

    def to_dict(self) -> dict[str, object]:
        model = self.normalized()
        return {
            "model_version": METADATA_VERSION,
            "openapi_version": model.openapi_version,
            "operations": [
                operation.to_dict()
                for operation in model.operations
            ],
            "paths": [path.to_dict() for path in model.paths],
            "schema_count": len(model.schemas),
            "schemas": [schema.to_dict() for schema in model.schemas],
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> "CanonicalApiModel":
        raw_paths = value.get("paths", [])
        raw_operations = value.get("operations", [])
        raw_schemas = value.get("schemas", [])
        if not isinstance(raw_paths, list):
            raw_paths = []
        if not isinstance(raw_operations, list):
            raw_operations = []
        if not isinstance(raw_schemas, list):
            raw_schemas = []
        return cls(
            openapi_version=missing(value.get("openapi_version")),
            paths=tuple(
                PathFact.from_dict(item)
                for item in raw_paths
                if isinstance(item, Mapping)
            ),
            operations=tuple(
                OperationFact.from_dict(item)
                for item in raw_operations
                if isinstance(item, Mapping)
            ),
            schemas=tuple(
                SchemaFact.from_dict(item)
                for item in raw_schemas
                if isinstance(item, Mapping)
            ),
            facts={},
        )


def serialize_metadata(model: CanonicalApiModel) -> str:
    """Serialize canonical facts into an HTML-comment metadata payload."""

    from .security import sanitize_for_metadata

    unsanitized_payload = model.to_dict()
    sanitized_payload = sanitize_for_metadata(unsanitized_payload)
    payload = json.dumps(
        sanitized_payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    encoded = base64.urlsafe_b64encode(payload.encode("utf-8")).decode("ascii")
    return f"<!-- {METADATA_MARKER}:{encoded} -->"


def deserialize_metadata(markdown: str) -> CanonicalApiModel:
    """Deserialize the first canonical metadata comment from Markdown."""

    from .security import sanitize_for_metadata

    matches = METADATA_PATTERN.findall(markdown)
    if not matches:
        raise ValueError("API synchronization metadata was not found.")
    try:
        padded = matches[0] + "=" * (-len(matches[0]) % 4)
        payload = base64.urlsafe_b64decode(padded.encode("ascii"))
        value = json.loads(payload.decode("utf-8"))
    except (ValueError, json.JSONDecodeError, UnicodeDecodeError):
        raise ValueError("API synchronization metadata is invalid.") from None
    if not isinstance(value, Mapping):
        raise ValueError("API synchronization metadata is invalid.")
    if value.get("model_version") != METADATA_VERSION:
        raise ValueError("Unsupported API synchronization metadata version.")
    if not isinstance(value.get("operations"), list):
        raise ValueError("API synchronization metadata is invalid.")
    if not isinstance(value.get("paths"), list):
        raise ValueError("API synchronization metadata is invalid.")
    if not isinstance(value.get("schemas"), list):
        raise ValueError("API synchronization metadata is invalid.")

    sanitized_value = sanitize_for_metadata(value)
    return CanonicalApiModel.from_dict(sanitized_value)


def deserialize_metadata_comments(markdown: str) -> tuple[CanonicalApiModel, ...]:
    """Deserialize all metadata comments and preserve document occurrence order."""

    from .security import sanitize_for_metadata

    matches = METADATA_PATTERN.findall(markdown)
    if not matches:
        return ()
    models: list[CanonicalApiModel] = []
    for encoded in matches:
        try:
            padded = encoded + "=" * (-len(encoded) % 4)
            payload = base64.urlsafe_b64decode(padded.encode("ascii"))
            value = json.loads(payload.decode("utf-8"))
        except (ValueError, json.JSONDecodeError, UnicodeDecodeError):
            raise ValueError("API synchronization metadata is invalid.") from None
        if not isinstance(value, Mapping):
            raise ValueError("API synchronization metadata is invalid.")
        if value.get("model_version") != METADATA_VERSION:
            raise ValueError("Unsupported API synchronization metadata version.")
        if not isinstance(value.get("operations"), list):
            raise ValueError("API synchronization metadata is invalid.")
        if not isinstance(value.get("paths"), list):
            raise ValueError("API synchronization metadata is invalid.")
        if not isinstance(value.get("schemas"), list):
            raise ValueError("API synchronization metadata is invalid.")
        sanitized_value = sanitize_for_metadata(value)
        models.append(CanonicalApiModel.from_dict(sanitized_value))
    return tuple(models)
