from __future__ import annotations

import argparse
import base64
import binascii
import html
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

NOT_FOUND = "Not Found"
MAX_FILE_BYTES = 1_000_000
API_ROOT = "https://api.github.com"


class RepositoryError(Exception):
    """Raised when repository evidence cannot be read safely."""


@dataclass
class TechnicalProfile:
    repository_name: str
    repository_url: str
    description: str
    default_branch: str
    languages: str
    readme_summary: str
    manifest_summaries: list[tuple[str, str]]


def parse_github_url(repository_url: str) -> tuple[str, str]:
    parsed = urllib.parse.urlsplit(repository_url.strip())
    parts = parsed.path.strip("/").split("/")
    if (
        parsed.scheme != "https"
        or parsed.hostname != "github.com"
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or len(parts) != 2
    ):
        raise ValueError("Use a public GitHub URL in the form https://github.com/owner/repository.")

    owner, repository = parts
    if repository.endswith(".git"):
        repository = repository[:-4]
    valid_part = re.compile(r"^[A-Za-z0-9_.-]+$")
    if (
        owner in {".", ".."}
        or repository in {".", ".."}
        or not valid_part.fullmatch(owner)
        or not valid_part.fullmatch(repository)
    ):
        raise ValueError("The GitHub owner or repository name is invalid.")
    return owner, repository


def request_json(url: str) -> dict[str, object]:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "doc-sync-capstone",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            payload = response.read()
    except urllib.error.HTTPError as error:
        raise RepositoryError(f"GitHub API request failed with HTTP {error.code}.") from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise RepositoryError("GitHub API request failed; check connectivity and try again.") from None

    try:
        result = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise RepositoryError("GitHub API returned invalid JSON.") from None
    if not isinstance(result, dict):
        raise RepositoryError("GitHub API returned an unexpected response.")
    return result


def read_github_file(owner: str, repository: str, path: str, branch: str) -> str:
    encoded_path = urllib.parse.quote(path, safe="/")
    endpoint = (
        f"{API_ROOT}/repos/{urllib.parse.quote(owner)}/"
        f"{urllib.parse.quote(repository)}/contents/{encoded_path}?"
        f"{urllib.parse.urlencode({'ref': branch})}"
    )
    result = request_json(endpoint)
    size = result.get("size")
    if isinstance(size, int) and not isinstance(size, bool) and size > MAX_FILE_BYTES:
        raise RepositoryError("A supported repository file exceeds the 1 MB inspection limit.")
    if result.get("encoding") != "base64" or not isinstance(result.get("content"), str):
        raise RepositoryError("GitHub returned an unsupported file encoding.")

    try:
        encoded_content = "".join(result["content"].split())
        content = base64.b64decode(encoded_content, validate=True)
    except (ValueError, binascii.Error):
        raise RepositoryError("GitHub returned invalid file content.") from None
    if len(content) > MAX_FILE_BYTES:
        raise RepositoryError("A supported repository file exceeds the 1 MB inspection limit.")
    try:
        return content.decode("utf-8")
    except UnicodeDecodeError:
        raise RepositoryError("A supported repository file is not valid UTF-8.") from None


def redact_secrets(text: str) -> str:
    patterns = (
        (
            r"(?is)-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----",
            "[REDACTED]",
        ),
        (r"\bgithub_pat_[A-Za-z0-9_]{20,}\b", "[REDACTED]"),
        (r"\bgh[pousr]_[A-Za-z0-9]{20,}\b", "[REDACTED]"),
        (r"\bAKIA[0-9A-Z]{16}\b", "[REDACTED]"),
        (r"\bAIza[0-9A-Za-z_-]{30,}\b", "[REDACTED]"),
        (r"\bsk-[A-Za-z0-9_-]{20,}\b", "[REDACTED]"),
        (r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b", "[REDACTED]"),
        (
            r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b",
            "[REDACTED]",
        ),
        (r"(?i)\bBearer\s+[A-Za-z0-9._~+/-]+=*", "Bearer [REDACTED]"),
        (
            r"(?i)(?<!\w)([\"']?)(password|passwd|secret|secret[_-]?key|token|credential|"
            r"authorization|auth|api[_-]?(?:key|token|secret)|"
            r"access[_-]?(?:key|token)|refresh[_-]?token|client[_-]?secret|"
            r"private[_-]?key|aws[_-]?secret[_-]?access[_-]?key|"
            r"aws[_-]?access[_-]?key[_-]?id)\1(?!\w)"
            r"(\s*[:=]\s*)(?:\"[^\"]*\"|'[^']*'|[^\s<>]+)",
            r"\1\2\1\3[REDACTED]",
        ),
        (r"https?://[^/\s:@]+:[^/\s@]+@", "https://[REDACTED]@"),
    )
    for pattern, replacement in patterns:
        text = re.sub(pattern, replacement, text)
    return text


def readme_summary(content: str) -> str:
    paragraph: list[str] = []
    in_code_block = False
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_code_block = not in_code_block
            continue
        if in_code_block or not stripped or stripped.startswith("#"):
            if paragraph and not in_code_block:
                break
            continue
        paragraph.append(stripped)
    summary = redact_secrets(" ".join(paragraph))
    summary = " ".join(summary.split())
    if not summary:
        return NOT_FOUND
    return summary[:500].rstrip()


def summarize_package_json(content: str) -> str:
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        raise ValueError("Invalid package.json JSON.") from None
    if not isinstance(data, dict):
        raise ValueError("Invalid package.json structure.")

    name = data.get("name") if isinstance(data.get("name"), str) else NOT_FOUND
    version = data.get("version") if isinstance(data.get("version"), str) else NOT_FOUND
    engines = data.get("engines")
    runtime = engines.get("node") if isinstance(engines, dict) else NOT_FOUND
    if not isinstance(runtime, str) or not runtime:
        runtime = NOT_FOUND
    dependencies: list[str] = []
    for section in ("dependencies", "devDependencies", "peerDependencies"):
        values = data.get(section)
        if isinstance(values, dict):
            for package, package_version in sorted(values.items()):
                if isinstance(package, str) and isinstance(package_version, str):
                    dependencies.append(f"{package}@{package_version}")
    dependency_text = ", ".join(dependencies) if dependencies else NOT_FOUND
    summary = (
        f"name: {name}; version: {version}; Node runtime: {runtime}; "
        f"dependencies: {dependency_text}"
    )
    return redact_secrets(summary)


def summarize_requirements(content: str) -> str:
    requirements: list[str] = []
    requirement_pattern = re.compile(
        r"^([A-Za-z0-9][A-Za-z0-9._-]*)(?:\[[A-Za-z0-9_,.-]+\])?"
        r"\s*((?:(?:===|==|~=|!=|<=|>=|<|>)[A-Za-z0-9.*+-]+"
        r"(?:\s*,\s*(?:===|==|~=|!=|<=|>=|<|>)[A-Za-z0-9.*+-]+)*)?)$"
    )
    for line in content.splitlines():
        candidate = line.split("#", 1)[0].strip()
        if not candidate or candidate.startswith("-"):
            continue
        match = requirement_pattern.fullmatch(candidate)
        if match:
            name, version = match.groups()
            requirements.append(f"{name}{version}")
    if not requirements:
        return NOT_FOUND
    return redact_secrets(", ".join(sorted(set(requirements), key=str.casefold)))


def summarize_pom(content: str) -> str:
    if re.search(r"(?is)<!DOCTYPE|<!ENTITY", content):
        raise ValueError("pom.xml must not contain DTD or entity declarations.")
    try:
        root = ET.fromstring(content)
    except ET.ParseError:
        raise ValueError("Invalid pom.xml XML.") from None
    if root.tag.rsplit("}", 1)[-1] != "project":
        raise ValueError("Invalid pom.xml structure.")
    local_name = lambda element: element.tag.rsplit("}", 1)[-1]

    def child(parent: ET.Element | None, name: str) -> ET.Element | None:
        if parent is None:
            return None
        return next((element for element in list(parent) if local_name(element) == name), None)

    def value(parent: ET.Element | None, name: str) -> str:
        element = child(parent, name)
        text = element.text.strip() if element is not None and element.text else ""
        return text or NOT_FOUND

    properties = child(root, "properties")
    runtime = next(
        (
            value(properties, key)
            for key in ("maven.compiler.release", "maven.compiler.source", "java.version")
            if value(properties, key) != NOT_FOUND
        ),
        NOT_FOUND,
    )
    dependencies: list[str] = []
    dependency_section = child(root, "dependencies")
    if dependency_section is not None:
        for dependency in list(dependency_section):
            if local_name(dependency) != "dependency":
                continue
            group = value(dependency, "groupId")
            artifact = value(dependency, "artifactId")
            version = value(dependency, "version")
            if artifact != NOT_FOUND:
                dependencies.append(f"{group}:{artifact}:{version}")
    dependency_text = ", ".join(sorted(dependencies)) if dependencies else NOT_FOUND
    summary = (
        f"artifact: {value(root, 'artifactId')}; version: {value(root, 'version')}; "
        f"Java runtime: {runtime}; dependencies: {dependency_text}"
    )
    return redact_secrets(summary)


def collect_profile(repository_url: str) -> TechnicalProfile:
    owner, repository = parse_github_url(repository_url)
    api_repo = f"{API_ROOT}/repos/{urllib.parse.quote(owner)}/{urllib.parse.quote(repository)}"
    metadata = request_json(api_repo)
    branch = metadata.get("default_branch")
    default_branch = branch if isinstance(branch, str) and branch else NOT_FOUND

    full_name = metadata.get("full_name")
    repository_name = full_name if isinstance(full_name, str) and full_name else repository
    description = metadata.get("description")
    description_text = description if isinstance(description, str) and description else NOT_FOUND
    description_text = redact_secrets(description_text)

    language_data = request_json(f"{api_repo}/languages")
    if any(not isinstance(language, str) for language in language_data):
        raise RepositoryError("GitHub returned invalid language data.")
    languages = ", ".join(sorted(language_data, key=str.casefold)) if language_data else NOT_FOUND

    readme = NOT_FOUND
    manifest_summaries: list[tuple[str, str]] = []
    if default_branch != NOT_FOUND:
        tree_url = (
            f"{api_repo}/git/trees/{urllib.parse.quote(default_branch, safe='')}"
            "?recursive=1"
        )
        tree_data = request_json(tree_url)
        if tree_data.get("truncated") is True:
            raise RepositoryError("GitHub returned an incomplete repository tree.")
        entries = tree_data.get("tree")
        if not isinstance(entries, list):
            raise RepositoryError("GitHub returned an invalid repository tree.")

        supported = {"package.json", "requirements.txt", "pom.xml"}
        paths = sorted(
            entry["path"]
            for entry in entries
            if isinstance(entry, dict)
            and isinstance(entry.get("path"), str)
            and entry.get("type") == "blob"
            and (
                entry["path"].rsplit("/", 1)[-1].casefold() in supported
                or entry["path"].rsplit("/", 1)[-1].casefold() == "readme.md"
            )
        )
        for path in paths:
            content = read_github_file(owner, repository, path, default_branch)
            filename = path.rsplit("/", 1)[-1].casefold()
            if filename == "readme.md":
                if readme == NOT_FOUND:
                    readme = readme_summary(content)
            elif filename == "package.json":
                manifest_summaries.append((path, summarize_package_json(content)))
            elif filename == "requirements.txt":
                manifest_summaries.append((path, summarize_requirements(content)))
            elif filename == "pom.xml":
                manifest_summaries.append((path, summarize_pom(content)))

    languages = redact_secrets(languages)
    return TechnicalProfile(
        repository_name=redact_secrets(repository_name),
        repository_url=f"https://github.com/{owner}/{repository}",
        description=description_text,
        default_branch=redact_secrets(default_branch),
        languages=languages,
        readme_summary=readme,
        manifest_summaries=manifest_summaries,
    )


def markdown_text(text: str) -> str:
    safe_text = " ".join(redact_secrets(text).split())
    escaped_html = html.escape(safe_text)
    return re.sub(r"([\\`*_{}\[\]()#+.!|>~-])", r"\\\1", escaped_html)


def render_markdown(profile: TechnicalProfile) -> str:
    lines = [
        f"# Technical Profile: {markdown_text(profile.repository_name)}",
        "",
        "## Repository",
        "",
        f"- **URL:** {profile.repository_url}",
        f"- **Description:** {markdown_text(profile.description)}",
        f"- **Default branch:** {markdown_text(profile.default_branch)}",
        f"- **Languages:** {markdown_text(profile.languages)}",
        "",
        "## README summary",
        "",
        markdown_text(profile.readme_summary),
        "",
        "## Dependency and runtime manifests",
        "",
    ]
    if profile.manifest_summaries:
        lines.extend(
            f"- **{markdown_text(path)}** — {markdown_text(summary)}"
            for path, summary in profile.manifest_summaries
        )
    else:
        lines.append(f"- {NOT_FOUND}")
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate a public GitHub repository Technical Profile.")
    parser.add_argument("repository_url", help="Public GitHub repository URL")
    parser.add_argument("--output", default="technical-profile.md", help="Markdown output path")
    parser.add_argument("--force", action="store_true", help="Replace an existing output file")
    args = parser.parse_args(argv)
    output = Path(args.output)
    if output.exists() and not args.force:
        print("Output already exists; choose another path or pass --force.", file=sys.stderr)
        return 2
    try:
        profile = collect_profile(args.repository_url)
        markdown = render_markdown(profile)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(markdown, encoding="utf-8")
    except (RepositoryError, ValueError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    except OSError:
        print("Could not write the output file.", file=sys.stderr)
        return 1
    print("Technical Profile generated.")
    return 0
