"""Deterministic Markdown rendering for canonical API facts."""

from __future__ import annotations

import html
import re
from pathlib import Path
from typing import Iterable

from .errors import GenerationError
from .model import CanonicalApiModel, NOT_FOUND, serialize_metadata
from .security import redact_text

MAX_MARKDOWN_BYTES = 5 * 1024 * 1024
MAX_MARKDOWN_LINES = 50_000


def escape_markdown_text(value: str) -> str:
    text = redact_text(str(value))
    escaped_html = html.escape(text)
    return re.sub(r"([\\`*_{}\[\]()#+.!|>~-])", r"\\\1", escaped_html)


def render_markdown(model: CanonicalApiModel) -> str:
    """Render canonical API facts in deterministic declared-source order."""

    model = model.normalized()
    lines = [
        "# API Reference",
        "",
        serialize_metadata(model),
        "",
        "## Operations",
        "",
    ]

    if not model.operations:
        lines.extend(["- **Operations:** " + NOT_FOUND, ""])
    else:
        for operation in model.operations:
            lines.extend(
                [
                    f"### `{escape_markdown_text(operation.method)} "
                    f"{escape_markdown_text(operation.path)}`",
                    "",
                    f"- **Summary:** {escape_markdown_text(operation.summary)}",
                    "",
                    "#### Parameters",
                    "",
                ]
            )
            if not operation.parameters:
                lines.extend(["- " + NOT_FOUND, ""])
            else:
                lines.extend(
                    [
                        "| Location | Name | Required | Schema |",
                        "|---|---|---|---|",
                    ]
                )
                for parameter in operation.parameters:
                    schema = _schema_summary(parameter.schema)
                    lines.append(
                        "| "
                        + " | ".join(
                            (
                                escape_markdown_text(parameter.location),
                                escape_markdown_text(parameter.name),
                                "yes" if parameter.required else "no",
                                escape_markdown_text(schema),
                            )
                        )
                        + " |"
                    )
                lines.append("")

            lines.extend(["#### Request Body", ""])
            if operation.request_body is None:
                lines.extend(["- " + NOT_FOUND, ""])
            else:
                lines.append(
                    "- **Required:** "
                    + ("yes" if operation.request_body.required else "no")
                )
                if not operation.request_body.schemas:
                    lines.extend(["- **Schema:** " + NOT_FOUND, ""])
                else:
                    for schema in operation.request_body.schemas:
                        lines.append(
                            "- **"
                            + escape_markdown_text(schema.media_type)
                            + "** — "
                            + escape_markdown_text(_schema_summary(schema.schema))
                        )
                lines.append("")

            lines.extend(["#### Responses", ""])
            if not operation.responses:
                lines.extend(["- " + NOT_FOUND, ""])
            else:
                for response in operation.responses:
                    lines.extend(
                        [
                            f"##### Status {escape_markdown_text(response.status)}",
                            "",
                            "- **Description:** "
                            + escape_markdown_text(response.description),
                        ]
                    )
                    if response.headers:
                        lines.append("- **Headers:**")
                        for header in response.headers:
                            lines.append(
                                "  - "
                                + escape_markdown_text(header.name)
                                + ": "
                                + escape_markdown_text(_schema_summary(header.schema))
                            )
                    else:
                        lines.append("- **Headers:** " + NOT_FOUND)

                    if response.schemas:
                        for schema in response.schemas:
                            lines.append(
                                "- **Schema:** "
                                + escape_markdown_text(schema.media_type)
                                + " — "
                                + escape_markdown_text(_schema_summary(schema.schema))
                            )
                    else:
                        lines.append("- **Schema:** " + NOT_FOUND)
                    lines.append("")

    lines.extend(["## Schemas", ""])
    if not model.schemas:
        lines.extend(["- " + NOT_FOUND, ""])
    else:
        for schema in model.schemas:
            lines.extend(
                [
                    f"### {escape_markdown_text(schema.name)}",
                    "",
                    "```json",
                    _json_schema_text(schema.schema),
                    "```",
                    "",
                ]
            )

    markdown = "\n".join(lines)
    encoded = markdown.encode("utf-8")
    if len(encoded) > MAX_MARKDOWN_BYTES:
        raise GenerationError("Generated Markdown exceeds the 5 MB limit.")
    if len(markdown.splitlines()) > MAX_MARKDOWN_LINES:
        raise GenerationError("Generated Markdown exceeds the 50,000-line limit.")
    return markdown


def _json_schema_text(schema: dict[str, object]) -> str:
    import json

    return redact_text(
        json.dumps(
            schema,
            sort_keys=True,
            indent=2,
            ensure_ascii=False,
        )
    )


def _schema_summary(schema: dict[str, object]) -> str:
    if not schema:
        return NOT_FOUND
    schema_type = schema.get("type")
    if isinstance(schema_type, str):
        return schema_type
    if "$ref" in schema:
        return str(schema["$ref"])
    if "properties" in schema:
        return "object"
    if "items" in schema:
        return "array"
    return "Not Found"


def write_markdown(path: str, model: CanonicalApiModel) -> str:
    markdown = render_markdown(model)
    target = Path(path)
    if target.is_absolute():
        raise GenerationError("Markdown output path must be repository-relative.")
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        target.write_text(markdown, encoding="utf-8")
    except OSError as error:
        raise GenerationError("Markdown output could not be written.") from error
    return markdown
