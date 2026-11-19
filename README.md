# Automated Documentation Sync

This repository contains two Python projects developed as part of the GitHub Copilot Capstone.

1. **API Documentation Sync** â€” the primary capstone. Starts a configured application, retrieves its live OpenAPI 3.0/3.1 specification, generates Markdown API documentation, and detects semantic documentation drift in pull requests.
2. **Technical Profile Generator** â€” reads public GitHub repository information and generates a local Markdown Technical Profile.

The original Technical Profile functionality is preserved independently under `src/doc_sync_capstone/`.

## Requirements

- Python 3.10 or later
- PyYAML
- Network access to the configured OpenAPI endpoint
- GitHub Actions for automated pull-request checks

## Installation

Run from the repository root:

```powershell
python -m pip install -r requirements.txt
python -m pip install -e .
```

## API Documentation Sync

### How it works

1. Starts the configured application.
2. Waits for the health endpoint and OpenAPI endpoint to become available.
3. Retrieves and validates the OpenAPI specification.
4. Generates candidate Markdown documentation.
5. Compares semantic API facts against the committed `docs/api.md` baseline.
6. Produces a JSON report and unified-diff patch.
7. Reports detected drift in the pull request.

### Configuration

Configure `.github/doc-sync.yml`:

```yaml
startup_command: "python app.py"
openapi_url: "http://127.0.0.1:8000/openapi.json"
output_path: "docs/api.md"
health_check_url: "http://127.0.0.1:8000/health"
shell: "pwsh"

auth:
  mode: "none"
  secret_names: {}
```

See [docs/api-sync-usage.md](docs/api-sync-usage.md) for authentication modes, environment overrides, and security details.

### Run locally

```powershell
python -m api_doc_sync --help

python -m api_doc_sync `
    --config .github/doc-sync.yml `
    --report build/report.json `
    --patch build/docs-api.patch
```

The installed console command is also available:

```powershell
api-doc-sync --help
```

### Pull-request workflow

The workflow in `.github/workflows/api-doc-sync.yml`:

- Uses `pull_request` events, not `pull_request_target`.
- Runs the documentation build with read-only permissions.
- Compares generated documentation with the committed baseline.
- Fails the build check when semantic drift is detected.
- Generates a detailed drift report covering paths, operations, schemas, and schema fields.
- Uploads the patch artifact for five days.
- Creates or updates a pull-request comment when permissions allow.
- Does not automatically commit or push generated documentation.

### Demonstration

PR #4 demonstrates intentional API documentation drift:

[Demo: Detect API documentation drift](https://github.com/jegatheshsakthivelarunachalam/capstone_aj/pull/4)

The mock API introduces `GET /patients` and a `Patient` schema. The workflow detects the additions, fails the documentation check as expected, and successfully publishes the detailed report.

**Important:** PR #4 is a demonstration PR and must not be merged as-is because it intentionally introduces documentation drift.

### Security limitation

The workflow is PR-visible. A pull-request author can modify workflow steps or reporting behavior. Checking out trusted base-revision implementation code does not make a PR-modifiable workflow definition trusted.

A fully trusted verification boundary requires a workflow maintained on the protected default branch or an equivalent protected reusable workflow.

Do not treat the current workflow as a fully trusted security boundary.

Supported authentication modes:

- `none`
- `bearer`
- `basic`
- `api_key`
- `oauth2_client_credentials`

Credential values must come from trusted environment variables or approved secret/OIDC mechanisms. Never place secret values in configuration, command-line arguments, or startup commands.

## Technical Profile Generator

The existing package is preserved under `src/doc_sync_capstone/`.

Example:

```powershell
python -m src.doc_sync_capstone `
    https://github.com/owner/repository `
    --output docs/technical-profile.md
```

The generator uses public repository evidence, renders unsupported facts as `Not Found`, and does not publish to Confluence.

## Copilot SDLC assets

The `.github/` directory contains:

- **Agents** for requirements analysis, implementation, review, and Technical Profile generation.
- **Prompts** for requirements, architecture, design review, implementation planning, implementation, PR description, and verification.
- **Skills** for API Documentation Sync and GitHub Technical Profile workflows.
- **Project instructions** describing shared development, security, and testing rules.

## Tests and verification

Run the complete test suite:

```powershell
python -m unittest discover -s tests -v
```

Additional checks:

```powershell
python -m compileall -q src tests
git diff --check
```

The latest recorded local full-suite result is **150 tests passed**.

See the `docs/` directory for requirements, architecture, design decisions, usage instructions, code review, verification evidence, and the capstone completion report.

## Project status

The implementation and intentional drift demonstration have been completed and verified. The final documentation and trainer submission report are being prepared. The PR-visible workflow trust-boundary limitation remains an open security consideration.
