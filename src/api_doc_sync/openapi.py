"""OpenAPI retrieval, authentication, validation, and extraction."""

from __future__ import annotations

import base64
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from .config import AuthConfig, DocSyncConfig
from .errors import FetchError, OpenApiError, ParseError, ExtractError
from .model import (
    CanonicalApiModel,
    HeaderFact,
    NOT_FOUND,
    OperationFact,
    ParameterFact,
    PathFact,
    RequestBodyFact,
    ResponseFact,
    SchemaFact,
)
from .security import redact_url

MAX_OPENAPI_BYTES = 10 * 1024 * 1024
MAX_PATHS = 500
MAX_SCHEMAS = 500
MAX_REF_DEPTH = 6
HTTP_TIMEOUT_SECONDS = 180
HTTP_ATTEMPTS = 4
RETRY_DELAY_SECONDS = 1
HTTP_METHODS = {"get", "put", "post", "delete", "options", "head", "patch", "trace"}


@dataclass(frozen=True)
class AuthResult:
    headers: dict[str, str]


class AuthenticationAdapter:
    """Resolve approved authentication modes without exposing secret values."""

    def __init__(self, config: AuthConfig, environ: Mapping[str, str] | None = None):
        self.config = config
        self.environ = dict(environ or {})

    def headers(self) -> AuthResult:
        mode = self.config.mode
        if mode == "none":
            return AuthResult({})

        secret_names = self.config.secret_names
        if mode == "bearer":
            value = self._require_secret(secret_names.get("token"))
            return AuthResult({"Authorization": f"Bearer {value}"})
        if mode == "basic":
            username = self._require_secret(secret_names.get("username"))
            password = self._require_secret(secret_names.get("password"))
            encoded = base64.b64encode(
                f"{username}:{password}".encode("utf-8")
            ).decode("ascii")
            return AuthResult({"Authorization": f"Basic {encoded}"})
        if mode == "api_key":
            header_name = self.config.header_name
            value = self._require_secret(secret_names.get("header_value"))
            if not header_name:
                raise FetchError("API-key header name is missing.")
            return AuthResult({header_name: value})
        raise FetchError("OAuth2 client credentials require token acquisition.")

    def _require_secret(self, secret_name: str | None) -> str:
        if not secret_name:
            raise FetchError("Authentication secret-name mapping is incomplete.")
        value = self.environ.get(secret_name)
        if value is None:
            raise FetchError("Required authentication secret is unavailable.")
        if not value:
            raise FetchError("Required authentication secret is empty.")
        return value

    def oauth2_headers(
        self,
        opener: Callable[..., Any] | None = None,
    ) -> AuthResult:
        if self.config.mode != "oauth2_client_credentials":
            return self.headers()
        if not self.config.token_url:
            raise FetchError("OAuth2 token URL is missing.")

        secret_names = self.config.secret_names
        client_id = self._require_secret(secret_names.get("client_id"))
        client_secret = self._require_secret(secret_names.get("client_secret"))
        form = urllib.parse.urlencode(
            {
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": client_secret,
                "scope": " ".join(self.config.scopes),
            }
        ).encode("ascii")
        request = urllib.request.Request(
            self.config.token_url,
            data=form,
            method="POST",
            headers={
                "Accept": "application/json",
                "Content-Type": "application/x-www-form-urlencoded",
            },
        )
        try:
            open_request = opener or urllib.request.urlopen
            with open_request(request, timeout=HTTP_TIMEOUT_SECONDS) as response:
                payload = response.read(MAX_OPENAPI_BYTES + 1)
            token_payload = json.loads(payload.decode("utf-8"))
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError, json.JSONDecodeError, UnicodeDecodeError):
            raise FetchError("OAuth2 token acquisition failed.") from None

        access_token = token_payload.get("access_token") if isinstance(token_payload, dict) else None
        if not isinstance(access_token, str) or not access_token:
            raise FetchError("OAuth2 response did not provide an access token.")
        return AuthResult({"Authorization": f"Bearer {access_token}"})


class OpenAPIFetcher:
    """Fetch and validate a bounded OpenAPI HTTP document."""

    def __init__(
        self,
        *,
        opener: Callable[..., Any] | None = None,
        sleep: Callable[[float], None] = time.sleep,
        environ: Mapping[str, str] | None = None,
    ) -> None:
        self.opener = opener or urllib.request.urlopen
        self.sleep = sleep
        self.environ = environ

    def fetch(
        self,
        url: str,
        auth: AuthConfig,
    ) -> bytes:
        parsed = urllib.parse.urlsplit(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise FetchError("OpenAPI URL must be absolute.")
        if parsed.username or parsed.password or parsed.fragment:
            raise FetchError("OpenAPI URL must not contain credentials or fragments.")

        adapter = AuthenticationAdapter(auth, self.environ)
        auth_result = (
            adapter.oauth2_headers(self.opener)
            if auth.mode == "oauth2_client_credentials"
            else adapter.headers()
        )

        last_error: Exception | None = None
        for attempt in range(HTTP_ATTEMPTS):
            request = urllib.request.Request(
                url,
                method="GET",
                headers={
                    "Accept": "application/json, application/yaml",
                    **auth_result.headers,
                },
            )
            try:
                with self.opener(request, timeout=HTTP_TIMEOUT_SECONDS) as response:
                    status = getattr(response, "status", 200)
                    if status < 200 or status >= 300:
                        last_error = FetchError("OpenAPI endpoint returned an HTTP error.")
                    else:
                        chunks: list[bytes] = []
                        total = 0
                        while True:
                            chunk = response.read(64 * 1024)
                            if not chunk:
                                break
                            total += len(chunk)
                            if total > MAX_OPENAPI_BYTES:
                                raise FetchError("OpenAPI document exceeds the 10 MB limit.")
                            chunks.append(chunk)
                        return b"".join(chunks)
            except FetchError:
                raise
            except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError) as error:
                last_error = error
            if attempt < HTTP_ATTEMPTS - 1:
                self.sleep(RETRY_DELAY_SECONDS)

        raise FetchError("OpenAPI fetch failed after retries.") from last_error


def retrieve_openapi(
    config: DocSyncConfig,
    *,
    opener: Callable[..., Any] | None = None,
    sleep: Callable[[float], None] = time.sleep,
    environ: Mapping[str, str] | None = None,
) -> CanonicalApiModel:
    """Orchestrate bounded retrieval, parsing, validation, and extraction."""

    fetcher = OpenAPIFetcher(
        opener=opener,
        sleep=sleep,
        environ=environ,
    )
    content = fetcher.fetch(config.openapi_url, config.auth)
    document = parse_openapi_document(content)
    return extract_openapi_model(document)


def parse_openapi_document(content: bytes) -> dict[str, Any]:
    if not content:
        raise ParseError("OpenAPI document is empty.")
    if len(content) > MAX_OPENAPI_BYTES:
        raise ParseError("OpenAPI document exceeds the 10 MB limit.")

    text = content.decode("utf-8", errors="strict")
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        try:
            import yaml
        except ImportError:
            raise ParseError("YAML support is unavailable because PyYAML is not installed.") from None
        try:
            _validate_yaml_resource_graph(text)
            value = yaml.safe_load(text)
        except yaml.YAMLError:
            raise ParseError("OpenAPI document is not valid YAML.") from None
        except ParseError:
            raise
        except (RecursionError, MemoryError):
            raise ParseError("OpenAPI YAML document is excessively complex.") from None

    if not isinstance(value, dict):
        raise ParseError("OpenAPI root must be a JSON or YAML object.")
    return value


def _validate_yaml_resource_graph(text: str) -> None:
    try:
        import yaml
    except ImportError:
        raise ParseError("YAML support is unavailable because PyYAML is not installed.")

    try:
        root = yaml.compose(text, Loader=yaml.SafeLoader)
    except yaml.YAMLError as error:
        raise ParseError("OpenAPI document is not valid YAML.") from error
    if root is None:
        raise ParseError("OpenAPI document is empty.")

    active: set[int] = set()
    expanded: dict[int, int] = {}
    alias_expansions = 0

    def walk(node: Any, depth: int) -> None:
        nonlocal alias_expansions
        if depth > 32:
            raise ParseError("OpenAPI YAML nesting exceeds the safe limit.")
        node_id = id(node)
        if node_id in active:
            raise ParseError("OpenAPI YAML contains recursive aliases.")
        active.add(node_id)

        expanded_count = expanded.get(node_id, 0) + 1
        expanded[node_id] = expanded_count
        if expanded_count > 1:
            alias_expansions += 1
            if alias_expansions > 20:
                raise ParseError("OpenAPI YAML contains excessive alias expansion.")

        if isinstance(node, yaml.MappingNode):
            for key_node, value_node in node.value:
                walk(key_node, depth + 1)
                walk(value_node, depth + 1)
        elif isinstance(node, yaml.SequenceNode):
            for value_node in node.value:
                walk(value_node, depth + 1)
        active.remove(node_id)

    try:
        walk(root, 0)
    except RecursionError:
        raise ParseError("OpenAPI YAML nesting exceeds the safe limit.") from None




def validate_openapi_document(spec: Mapping[str, Any]) -> dict[str, Any]:
    openapi_version = spec.get("openapi") or spec.get("swagger")
    if not isinstance(openapi_version, str):
        raise ParseError("OpenAPI version is missing.")
    if not openapi_version.startswith("3.0") and not openapi_version.startswith("3.1"):
        raise ParseError("Only OpenAPI 3.0 and 3.1 are supported.")

    paths = spec.get("paths")
    if not isinstance(paths, dict):
        raise ParseError("OpenAPI paths must be a mapping.")
    if len(paths) > MAX_PATHS:
        raise ParseError("OpenAPI document exceeds 500 paths.")

    components = spec.get("components")
    schemas: dict[str, Any] = {}
    if components is not None:
        if not isinstance(components, dict):
            raise ParseError("OpenAPI components must be a mapping.")
        raw_schemas = components.get("schemas", {})
        if raw_schemas is not None:
            if not isinstance(raw_schemas, dict):
                raise ParseError("OpenAPI component schemas must be a mapping.")
            schemas = raw_schemas
    if len(schemas) > MAX_SCHEMAS:
        raise ParseError("OpenAPI document exceeds 500 schemas.")

    return dict(spec)


class LocalRefResolver:
    """Resolve only local OpenAPI references to a bounded depth."""

    def resolve(self, spec: Mapping[str, Any], reference: str, depth: int = 0) -> Any:
        if depth >= MAX_REF_DEPTH:
            return {"type": NOT_FOUND}
        if not reference.startswith("#/"):
            return {"type": NOT_FOUND}

        current: Any = spec
        for segment in reference[2:].split("/"):
            segment = segment.replace("~1", "/").replace("~0", "~")
            if not isinstance(current, dict) or segment not in current:
                return {"type": NOT_FOUND}
            current = current[segment]
        if isinstance(current, dict):
            nested = current.get("$ref")
            if isinstance(nested, str):
                return self.resolve(spec, nested, depth + 1)
            return current
        return {"type": NOT_FOUND}

    def resolve_schema(
        self,
        schema: Any,
        spec: Mapping[str, Any],
        depth: int = 0,
        visited: tuple[str, ...] = (),
    ) -> dict[str, Any]:
        if not isinstance(schema, dict):
            return {"type": NOT_FOUND}
        reference = schema.get("$ref")
        if isinstance(reference, str):
            if not reference.startswith("#/"):
                return {"type": NOT_FOUND}
            if reference in visited:
                return {"type": NOT_FOUND}
            if depth >= MAX_REF_DEPTH:
                return {"type": NOT_FOUND}
            resolved = self.resolve(spec, reference, depth)
            if isinstance(resolved, dict):
                return self.resolve_schema(
                    resolved,
                    spec,
                    depth + 1,
                    visited + (reference,),
                )
            return {"type": NOT_FOUND}

        resolved: dict[str, Any] = {}
        for key, value in sorted(schema.items(), key=lambda item: str(item[0])):
            if key in {"properties", "items", "allOf", "oneOf", "anyOf"}:
                if isinstance(value, dict):
                    nested_items: dict[str, Any] = {}
                    for nested_key, nested_value in sorted(value.items(), key=lambda item: str(item[0])):
                        nested_items[str(nested_key)] = self.resolve_schema(
                            nested_value,
                            spec,
                            depth,
                            visited,
                        )
                    resolved[str(key)] = nested_items
                elif isinstance(value, list):
                    resolved[str(key)] = [
                        self.resolve_schema(item, spec, depth, visited)
                        if isinstance(item, dict)
                        else item
                        for item in value
                    ]
                else:
                    resolved[str(key)] = value
            else:
                resolved[str(key)] = value
        if not resolved:
            resolved["type"] = NOT_FOUND
        return resolved


def _schema_fact(
    name: str,
    media_type: str,
    schema: Any,
    spec: Mapping[str, Any],
    resolver: LocalRefResolver,
) -> SchemaFact:
    resolved = resolver.resolve_schema(schema, spec)
    from .security import sanitize_for_metadata

    sanitized = sanitize_for_metadata(resolved)
    return SchemaFact(
        name=name,
        media_type=media_type,
        schema=sanitized,
    )


def extract_openapi_model(raw_spec: Mapping[str, Any]) -> CanonicalApiModel:
    spec = validate_openapi_document(raw_spec)
    openapi_version = spec.get("openapi")
    if not isinstance(openapi_version, str):
        openapi_version = NOT_FOUND

    resolver = LocalRefResolver()
    paths: list[PathFact] = []
    operations: list[OperationFact] = []
    schemas: list[SchemaFact] = []

    components = spec.get("components")
    if isinstance(components, dict):
        component_schemas = components.get("schemas")
        if isinstance(component_schemas, dict):
            for name in sorted(component_schemas, key=str):
                schemas.append(
                    _schema_fact(
                        str(name),
                        "schema",
                        component_schemas[name],
                        spec,
                        resolver,
                    )
                )

    for path in spec["paths"]:
        if not isinstance(path, str):
            continue
        path_item = spec["paths"][path]
        if not isinstance(path_item, dict):
            continue
        path_summary = path_item.get("summary")
        paths.append(
            PathFact(
                path=path,
                summary=(
                    path_summary
                    if isinstance(path_summary, str) and path_summary
                    else NOT_FOUND
                ),
            )
        )
        path_parameters = path_item.get("parameters")
        if not isinstance(path_parameters, list):
            path_parameters = []

        for method in spec["paths"][path]:
            if not isinstance(method, str) or method.lower() not in HTTP_METHODS:
                continue
            operation = spec["paths"][path][method]
            if not isinstance(operation, dict):
                operation = {}

            parameters: list[ParameterFact] = []
            for raw_parameter in list(path_parameters) + (
                operation.get("parameters", [])
                if isinstance(operation.get("parameters"), list)
                else []
            ):
                if not isinstance(raw_parameter, dict):
                    continue
                if isinstance(raw_parameter.get("$ref"), str):
                    resolved = resolver.resolve(spec, raw_parameter["$ref"])
                    if not isinstance(resolved, dict):
                        resolved = {}
                else:
                    resolved = raw_parameter
                name = resolved.get("name")
                location = resolved.get("in")
                required = resolved.get("required")
                raw_schema = resolved.get("schema")
                resolved_schema = (
                    resolver.resolve_schema(raw_schema, spec)
                    if isinstance(raw_schema, dict)
                    else {"type": NOT_FOUND}
                )
                from .security import sanitize_for_metadata

                parameters.append(
                    ParameterFact(
                        name=str(name) if isinstance(name, str) and name else NOT_FOUND,
                        location=str(location) if isinstance(location, str) and location else NOT_FOUND,
                        required=required is True,
                        schema=sanitize_for_metadata(resolved_schema),
                    )
                )

            request_body_fact: RequestBodyFact | None = None
            raw_request_body = operation.get("request_body")
            if not isinstance(raw_request_body, dict):
                raw_request_body = None
            if raw_request_body is not None:
                request_schemas: list[SchemaFact] = []
                content = raw_request_body.get("content")
                if isinstance(content, dict):
                    for media_type in sorted(content, key=str):
                        media = content[media_type]
                        if not isinstance(media, dict):
                            continue
                        schema = media.get("schema")
                        if isinstance(schema, dict):
                            request_schemas.append(
                                _schema_fact(
                                    NOT_FOUND,
                                    str(media_type),
                                    schema,
                                    spec,
                                    resolver,
                                )
                            )
                request_body_fact = RequestBodyFact(
                    required=raw_request_body.get("required") is True,
                    schemas=tuple(request_schemas),
                )

            response_facts: list[ResponseFact] = []
            raw_responses = operation.get("responses")
            if not isinstance(raw_responses, dict):
                raw_responses = {}
            for status in sorted(raw_responses, key=str):
                response = raw_responses[status]
                if not isinstance(response, dict):
                    response = {}
                description = response.get("description")
                headers: list[HeaderFact] = []
                raw_headers = response.get("headers")
                if isinstance(raw_headers, dict):
                    for header_name in sorted(raw_headers, key=str):
                        raw_header = raw_headers[header_name]
                        if not isinstance(raw_header, dict):
                            raw_header = {}
                        raw_schema = raw_header.get("schema")
                        resolved_header_schema = (
                            resolver.resolve_schema(raw_schema, spec)
                            if isinstance(raw_schema, dict)
                            else {"type": NOT_FOUND}
                        )
                        from .security import sanitize_for_metadata

                        headers.append(
                            HeaderFact(
                                name=str(header_name),
                                required=raw_header.get("required") is True,
                                schema=sanitize_for_metadata(resolved_header_schema),
                            )
                        )

                response_schemas: list[SchemaFact] = []
                content = response.get("content")
                if isinstance(content, dict):
                    for media_type in sorted(content, key=str):
                        media = content[media_type]
                        if not isinstance(media, dict):
                            continue
                        schema = media.get("schema")
                        if isinstance(schema, dict):
                            response_schemas.append(
                                _schema_fact(
                                    NOT_FOUND,
                                    str(media_type),
                                    schema,
                                    spec,
                                    resolver,
                                )
                            )
                from .security import redact_text

                response_facts.append(
                    ResponseFact(
                        status=str(status),
                        description=(
                            redact_text(str(description))
                            if isinstance(description, str) and description
                            else NOT_FOUND
                        ),
                        headers=tuple(headers),
                        schemas=tuple(response_schemas),
                    )
                )

            summary = operation.get("summary")
            from .security import redact_text

            operations.append(
                OperationFact(
                    path=path,
                    method=method.upper(),
                    summary=(
                        redact_text(str(summary))
                        if isinstance(summary, str) and summary
                        else NOT_FOUND
                    ),
                    parameters=tuple(parameters),
                    request_body=request_body_fact,
                    responses=tuple(response_facts),
                )
            )

    return CanonicalApiModel(
        openapi_version=openapi_version,
        paths=tuple(paths),
        operations=tuple(operations),
        schemas=tuple(schemas),
    )
