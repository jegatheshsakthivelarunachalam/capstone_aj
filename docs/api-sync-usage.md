# API Documentation Sync Usage

## Configuration

Create or update `.github/doc-sync.yml`:

```yaml
startup_command: "python app.py"
openapi_url: "http://127.0.0.1:8000/openapi.json"
output_path: "docs/api.md"
health_check_url: "http://127.0.0.1:8000/health"
shell: "pwsh"

auth:
  mode: "none"
  secret_names: {}

environment_overrides:
  openapi_url: "DOC_SYNC_OPENAPI_URL"
  health_check_url: "DOC_SYNC_HEALTH_CHECK_URL"
```

`output_path` must be a repository-relative Markdown path. The initial approved
output is `docs/api.md`.

Environment overrides affect only non-secret configuration values. Secret names
may be mapped in configuration, but credential values must come from GitHub
Actions secrets or OIDC-provided environment values.

## Authentication examples

Bearer:

```yaml
auth:
  mode: "bearer"
  secret_names:
    token: "OPENAPI_BEARER_TOKEN"
```

Basic:

```yaml
auth:
  mode: "basic"
  secret_names:
    username: "OPENAPI_BASIC_USERNAME"
    password: "OPENAPI_BASIC_PASSWORD"
```

API key:

```yaml
auth:
  mode: "api_key"
  header_name: "X-API-Key"
  secret_names:
    header_value: "OPENAPI_API_KEY"
```

OAuth2 client credentials:

```yaml
auth:
  mode: "oauth2_client_credentials"
  token_url: "https://auth.example.com/oauth/token"
  scopes: ["read:api"]
  secret_names:
    client_id: "OAUTH_CLIENT_ID"
    client_secret: "OAUTH_CLIENT_SECRET"
```

Fork pull requests do not receive repository secrets. The workflow fails
explicitly if an authenticated mode requires unavailable credentials.

## Local execution

Install dependencies:

```powershell
python -m pip install -r requirements.txt
python -m pip install -e .
```

Run the CLI:

```powershell
python -m api_doc_sync --config .github/doc-sync.yml --report build/report.json --patch build/docs-api.patch
```

Or use the configured console script:

```powershell
api-doc-sync --help
```

## Pull-request behavior

**Trust limitation:** the current workflow is PR-visible. A pull-request author
can modify workflow steps or reporting permissions. The implementation checks
out the base revision for verification and the PR application separately under
`pr-app`, but this is not a fully trusted security boundary. A fully trusted
check requires a workflow maintained on the default branch or equivalent
protected workflow.

The workflow runs on matching pull-request file changes and:

1. starts the configured application;
2. waits up to 5 minutes for health/OpenAPI readiness;
3. fetches the live OpenAPI document with approved limits and retries;
4. renders candidate `docs/api.md`;
5. compares semantic facts with the committed baseline;
6. uploads a unified diff for 5 days on drift;
7. fails the pull-request check;
8. conditionally creates or updates one summary-only PR comment.

The workflow never commits or pushes generated documentation.

## Security

- Never store credential values in `.github/doc-sync.yml`.
- Never pass credentials through `startup_command` or process arguments.
- Raw response bodies and authorization headers are not printed.
- `docs/api.md`, metadata, diffs, temporary artifacts, and reports are redacted.
- External `$ref` values are not fetched.
- Fork build jobs use read-only repository permissions.
