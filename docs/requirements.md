# Requirements: Automated API Documentation Sync

## 1. Purpose and scope

As a software developer, pull-request changes to application endpoints or
schemas must produce accurate API documentation in `docs/api.md`.

The system will:

- run in GitHub Actions;
- start the application from repository configuration;
- fetch a live OpenAPI document from an absolute URL;
- generate Markdown for a PR review;
- detect documentation drift against the committed `docs/api.md`;
- fail the pull-request check when drift is found;
- publish a summary-only pull-request comment;
- provide a unified-diff suggested-patch artifact.

The system does not push generated documentation automatically, publish to
Confluence, or extract API facts directly from framework source annotations.
Repository-only OpenAPI artifacts are not the primary discovery source.

## 2. Approved functional requirements

- **FR-1 — Configuration:** Read `startup_command`, `openapi_url`, and
  `output_path` from `.github/doc-sync.yml`. The output path for the first
  release is `docs/api.md`.
- **FR-2 — Environment overrides:** Environment variables may override
  repository configuration values.
- **FR-3 — Shell support:** A configurable shell may be selected for each
  startup command. The Windows runner default is configurable PowerShell per
  command.
- **FR-4 — Trigger:** Run for pull requests when changed-file globs match:
  `src/**`, `app/**`, `openapi/**`, `docs/api.md`,
  `.github/doc-sync.yml`, `package.json`, `pom.xml`, or `requirements.txt`.
- **FR-5 — Application startup:** Start the configured application on
  `windows-latest`. Wait up to 5 minutes for readiness.
- **FR-6 — Readiness:** Poll `health_check_url` when configured. Otherwise,
  poll the configured absolute OpenAPI URL.
- **FR-7 — OpenAPI retrieval:** Fetch the live OpenAPI document from an
  absolute URL. Relative OpenAPI URLs are not supported.
- **FR-8 — Formats:** Accept JSON and YAML OpenAPI documents using the header
  `Accept: application/json, application/yaml`.
- **FR-9 — OpenAPI versions:** Support OpenAPI 3.0 and 3.1. OpenAPI 2.0 is out
  of scope.
- **FR-10 — Authentication:** Support no authentication, Bearer tokens, Basic
  authentication, API-key headers, and OAuth2 client credentials.
- **FR-11 — Secret mapping:** Authentication secret names are declared in a
  standard mapping in `.github/doc-sync.yml`. Credential values come from
  GitHub Actions secrets or OIDC-generated credentials.
- **FR-12 — Retrieval retry:** Allow 180 seconds per HTTP attempt and make
  four total requests (the initial request plus three retries). Wait one second
  between requests.
- **FR-13 — Endpoint data:** Generate Markdown for:
  - endpoint path and HTTP method;
  - request parameters and headers;
  - request body and schemas;
  - response status codes and schemas.
- **FR-14 — Missing facts:** Write `Not Found` for missing or unresolved facts.
  Never infer a fact that is not supported by the OpenAPI document.
- **FR-15 — Schema references:** Resolve local `$ref` values only, up to a
  depth of 6. Mark external `$ref` values `Not Found`. Circular or excessively
  deep references must not recurse indefinitely.
- **FR-16 — Validation:** Accept valid operations and mark invalid sections
  `Not Found`. JSON/YAML syntax or document structures that prevent safe
  processing are an explicit workflow failure.
- **FR-17 — Markdown output:** Generate `docs/api.md` in the declared
  OpenAPI order, preserving tags, paths, methods, parameters, schemas, and
  response structures in the source's sequence.
- **FR-18 — Secret safety:** Never print or include credentials, tokens,
  authorization headers, raw API response bodies, or startup-command secret
  values in logs, comments, Markdown, or artifacts.
- **FR-19 — Drift baseline:** Compare the newly generated Markdown facts only
  against the committed `docs/api.md`.
- **FR-20 — Drift comparison:** Compare API operation and schema facts while
  ignoring whitespace and formatting-only prose differences.
- **FR-21 — Drift result:** Any detected drift fails the pull-request check.
- **FR-22 — PR comment:** Add or update one existing bot comment on the pull
  request. The comment contains only summary counts and status, including
  counts for paths and schemas and missing-fact findings.
- **FR-23 — Report links:** The PR comment includes links to the GitHub
  Actions workflow run and suggested-patch artifact.
- **FR-24 — Suggested patch:** Create a unified-diff artifact for manual
  application to `docs/api.md`.
- **FR-25 — Artifact retention:** Retain the suggested-patch artifact for 5
  days.
- **FR-26 — Permissions:** The workflow may require read access to contents
  and write access for pull requests, checks, actions, and issues.

## 3. Non-functional requirements

### 3.1 Resource limits

- Maximum raw OpenAPI document size: 10 MB.
- Maximum API paths: 500.
- Maximum schemas: 500.
- Maximum local `$ref` depth: 6.
- Maximum generated Markdown size: 5 MB.
- Maximum generated Markdown length: 50,000 lines.
- Application startup timeout: 5 minutes.
- OpenAPI HTTP timeout: 180 seconds per attempt.
- Retry count: initial attempt plus three retries.
- Retry interval: fixed 1-second delay.
- No hard overall GitHub Actions timeout is required.

### 3.2 Security

- Credentials must not be committed.
- Credential values must come from GitHub Actions secrets or OIDC.
- Authentication errors must be reported without leaking headers or values.
- External `$ref` resolution is prohibited; no external network fetch is made
  for schema references.
- The generated artifact must escape Markdown and HTML-sensitive content.
- Raw OpenAPI response bodies must not appear in workflow logs or comments.
- Secret redaction must be covered by security tests.

### 3.3 Reliability and error handling

- Startup failure, invalid readiness, authentication failure, HTTP timeout,
  malformed JSON/YAML, unsafe resource limits, and write failure must produce
  a clear nonzero workflow result.
- Missing OpenAPI facts are represented by `Not Found`, not omitted silently.
- Circular, external, or excessive-depth `$ref` values must not cause hangs or
  recursive expansion.
- A workflow run must fail closed for a document that cannot be safely parsed.
- Valid operations in a partially invalid document may be rendered and marked
  with `Not Found` for invalid sections.

### 3.4 Determinism

- Preserve declared source order for tags and operations.
- Generate byte-stable Markdown for an identical OpenAPI document and
  configuration.
- Drift comparison may ignore whitespace and formatting-only differences.

### 3.5 CI and testing

- The default GitHub Actions runner is `windows-latest`.
- Startup commands may use a shell configured per command.
- GitHub Actions workflow smoke tests are mandatory.
- Unit tests for OpenAPI extraction and Markdown generation are mandatory.
- Security tests for secret redaction and local/external `$ref` handling are
  mandatory.
- Integration tests with a live mock API and semantic-drift tests are
  optional unless approved separately.

## 4. Configuration contract

The initial `.github/doc-sync.yml` contract requires:

```yaml
startup_command: "application-specific command"
openapi_url: "absolute-http-or-https-url"
output_path: "docs/api.md"
```

Optional supported settings include:

- `health_check_url`;
- environment variable overrides;
- authentication secret mapping;
- shell selection for startup commands.

No configuration key may contain a credential value.

## 5. Pull-request workflow behavior

1. Activate for a matching pull-request changed-file glob.
2. Read `.github/doc-sync.yml` and environment overrides.
3. Start the application using the configured command and shell.
4. Poll the configured health URL or absolute OpenAPI URL for up to 5 minutes.
5. Fetch and validate the OpenAPI document.
6. Resolve safe local references and extract approved API fields.
7. Generate candidate `docs/api.md` Markdown.
8. Compare supported API facts with the committed `docs/api.md`.
9. On drift:
   - fail the pull-request check;
   - update or add one summary-only bot comment;
   - upload a unified-diff suggested patch;
   - include workflow and artifact links.
10. On no drift:
   - pass the pull-request check;
   - update or remove the existing drift comment according to workflow
     convention.

The workflow never commits candidate Markdown to the pull-request branch.

## 6. Acceptance criteria

1. A matching pull request starts the configured application and fetches the
   absolute OpenAPI URL.
2. OpenAPI 3.0 and 3.1 JSON/YAML documents produce `docs/api.md`.
3. Endpoint methods, paths, parameters, headers, request bodies, and response
   statuses/schemas appear in Markdown.
4. Missing facts appear as `Not Found`.
5. External `$ref` values are not fetched and appear as `Not Found`.
6. A local `$ref` resolves through no more than six levels.
7. Oversized specs, excessive paths/schemas, oversized Markdown, and malformed
   documents return clear failures.
8. No secret or raw API response body appears in logs, comments, Markdown, or
   the suggested patch.
9. Semantically unchanged but whitespace/formatted Markdown is not reported as
   drift.
10. Changed operation or schema facts produce drift, a failing check, one
    summary-only PR comment, and a unified-diff artifact retained for 5 days.
11. The workflow smoke test and all mandatory unit/security tests pass.

## 7. Assumptions

- The existing repository is a Python-based capstone project that may be
  extended to support this use case.
- The application is startable through `startup_command` and is reachable from
  a GitHub-hosted Windows runner.
- The absolute OpenAPI URL is public or internally reachable with approved
  authentication.
- The target branch stores `docs/api.md` as the drift baseline.
- GitHub Actions secrets or OIDC are available when authentication is required.
- Pull-request permissions allow comments and check reporting.
- External `$ref` resolution is intentionally unsupported.

## 8. Constraints and dependencies

- GitHub Actions.
- GitHub-hosted `windows-latest` runner.
- `.github/doc-sync.yml`.
- A configurable application startup command.
- Absolute OpenAPI endpoint.
- OpenAPI 3.0 or 3.1.
- JSON or YAML parser.
- GitHub Actions secrets or OIDC.
- GitHub pull-request comment, action, and checks permissions.
- Markdown generation and unified-diff support.

## 9. Edge cases

- Empty or unavailable OpenAPI document.
- Application startup or health-check timeout.
- Invalid Bearer, Basic, API-key, or OAuth2 credentials.
- HTTP 4xx/5xx responses and exhausted retries.
- Malformed JSON or YAML.
- OpenAPI 3.0/3.1 validation errors.
- Missing paths, operations, parameters, request bodies, responses, or schemas.
- Local and external `$ref` values.
- Circular references.
- `$ref` depth above 6.
- 501st path or 501st schema.
- Spec above 10 MB.
- Markdown above 5 MB or 50,000 lines.
- Duplicate operation IDs or tags.
- Secret-like text in operation descriptions or schema metadata.
- Unavailable workflow permissions.
- Artifact upload failure.
- PR comment API failure.
- Candidate Markdown write failure.

## 10. Explicit out of scope

- Private-repository authentication not delivered through GitHub Actions secrets
  or OIDC.
- Confluence publishing.
- Automatic documentation commit or automatic PR merge.
- OpenAPI extraction directly from framework source or annotations.
- OpenAPI 2.0.
- Scheduled synchronization pushes.
- Confluence API integration.
- External `$ref` fetching.
- Inline PR diff rendering.
- Automatic infrastructure deployment for preview environments.
- A hard overall CI job timeout.
