# Automated Documentation Sync

This repository contains two preserved projects:

- **Technical Profile generator:** reads a public GitHub repository and writes a
  local Markdown Technical Profile.
- **API Documentation Sync:** starts a configured application, reads its live
  OpenAPI 3.0/3.1 JSON or YAML document, generates `docs/api.md`, and detects
  semantic documentation drift in pull requests.

## Requirements

- Python 3.10 or later
- PyYAML
- Network access to the absolute OpenAPI endpoint
- GitHub Actions for pull-request checks and reporting

Install dependencies:

```powershell
python -m pip install -r requirements.txt
python -m pip install -e .
```

## API Documentation Sync

Configure the workflow in `.github/doc-sync.yml`:

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

Run the CLI from the repository root:

```powershell
python -m api_doc_sync --config .github/doc-sync.yml --report build/report.json --patch build/docs-api.patch
```

The CLI can also run through the installed console entry point:

```powershell
api-doc-sync --help
```

The pull-request workflow:

- runs only for approved changed-file globs;
- uses `pull_request` and never `pull_request_target`;
- runs build/startup logic with read-only build permissions;
- does not commit or push candidate documentation;
- fails the PR check on semantic drift;
- uploads a unified-diff patch for 5 days;
- conditionally updates a summary-only PR comment.

**Security boundary limitation:** this repository currently uses a PR-visible
`pull_request` workflow. A pull-request author can modify workflow steps or
reporting behavior, so the workflow is not a fully trusted verification
boundary. The implementation checks out the base revision as `src` and PR
application code separately under `pr-app`, but a fully trusted check requires
a workflow maintained on the default branch or an equivalent protected
workflow.

Supported authentication modes are `none`, `bearer`, `basic`, `api_key`, and
`oauth2_client_credentials`. Secret values must come from trusted environment
variables or OIDC; secret names may be stored in configuration.

See [docs/api-sync-usage.md](docs/api-sync-usage.md) for setup and security
details.

## Technical Profile generator

The existing Technical Profile package remains under
`src/doc_sync_capstone/`:

```powershell
python -m src.doc_sync_capstone https://github.com/owner/repository --output docs\technical-profile.md
```

Missing facts are shown as `Not Found`. This tool does not publish to
Confluence.

## Tests

```powershell
python -m unittest discover -s tests -v
```

See [`docs/`](docs/) for requirements, architecture, design review,
implementation plan, verification evidence, and the PR-ready summary.
