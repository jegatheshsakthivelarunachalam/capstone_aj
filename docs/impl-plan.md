# Implementation Plan: Automated API Documentation Sync

## 1. Scope

This plan implements the approved requirements in
[requirements.md](./requirements.md) according to
[architecture.md](./architecture.md) and [design-review.md](./design-review.md).

It preserves the existing `src/doc_sync_capstone/` Technical Profile
implementation and adds a separate `src/api_doc_sync/` implementation.

No application code is created by this planning document.

## 2. Implementation phases

### Phase 1 — Foundation

Create the package boundary, canonical model, configuration contract,
redaction/error types, and test support. Existing Technical Profile code
remains unchanged.

### Phase 2 — Process and network boundaries

Implement lifecycle/process-tree cleanup, authentication, streamed bounded
HTTP fetching, retry behavior, and retrieval orchestration.

### Phase 3 — OpenAPI processing

Implement OpenAPI 3.0/3.1 validation, approved field extraction, local `$ref`
resolution, and canonical fact metadata.

### Phase 4 — Documentation and drift

Implement `docs/api.md` generation, canonical HTML metadata, baseline/candidate
parsing, semantic drift detection, unified diff, and sanitized reporting
counts.

### Phase 5 — GitHub Actions integration

Add the pull-request workflow with read-only build and conditional reporting
jobs. The workflow invokes the completed CLI; it does not duplicate parsing,
generation, or drift logic.

### Phase 6 — Integration and verification

Run unit, security, mock-application, workflow, drift, and end-to-end checks.
Record exact commands and results.

### Phase 7 — Documentation handoff

Document configuration, authentication, Windows runner behavior, fork fallback,
artifact/comment behavior, limits, and the preserved Technical Profile
implementation.

## 3. Dependency-ordered task list

| ID | Priority | Task | Files/modules | Dependencies | Acceptance criteria | Traceability |
|---|---|---|---|---|---|---|
| T01 | P0 | Create API synchronization package skeleton and error/model types | `src/api_doc_sync/__init__.py`, `src/api_doc_sync/errors.py`, `src/api_doc_sync/model.py`; leave `src/doc_sync_capstone/**` unchanged | — | Both packages import independently; existing Technical Profile behavior is not changed; model/error types compile and have focused tests | DR-12 |
| T02 | P0 | Implement configuration loading and auth secret-name mapping | `src/api_doc_sync/config.py`, `.github/doc-sync.yml`, `tests/test_api_doc_sync/test_config.py` | T01 | Reads `startup_command`, absolute `openapi_url`, `output_path`, optional `health_check_url`, shell, auth mode, and environment overrides; credential values are prohibited in config | FR-1, FR-2, FR-3, FR-10, FR-11; DR-01 |
| T03 | P0 | Implement canonical fact model and HTML metadata contract | `src/api_doc_sync/model.py`, `tests/test_api_doc_sync/test_model.py` | T01 | Canonical model represents paths, methods, parameters, headers, request bodies, responses, schemas, and missing facts; metadata round-trips without another committed artifact | FR-13, FR-14, FR-17, FR-19, FR-20; DR-02, DR-10 |
| T04 | P0 | Implement shared redaction, temp-file, and stage-error boundaries | `src/api_doc_sync/security.py`, `src/api_doc_sync/errors.py`, `tests/test_api_doc_sync/test_security.py` | T01 | Redacts credentials and secret-like text before Markdown/diff/log/report output; temp files use unique bounded paths and stage codes cover startup/readiness/fetch/parse/extract/generate/drift/artifact/report | FR-18, NFR Security, Edge Cases; DR-03, DR-13 |
| T05 | P0 | Implement authentication adapter | `src/api_doc_sync/openapi.py` or a focused auth helper, `tests/test_api_doc_sync/test_auth.py` | T02, T04 | Supports none, Bearer, Basic, API-key, and OAuth2 client credentials; secret names map to trusted secrets/OIDC values; no credential enters command arguments or PR process environment | FR-10, FR-11, FR-18; DR-01 |
| T06 | P0 | Implement streamed, bounded OpenAPI fetch | `src/api_doc_sync/openapi.py`, `tests/test_api_doc_sync/test_openapi_fetch.py` | T02, T04 | Validates absolute HTTP(S), sends approved Accept header, streams with 10 MB-plus-one limit, uses 180-second timeout, four attempts, and fixed 1-second retry; raw body/auth data never logs | FR-7, FR-8, FR-12, FR-18, NFR 10 MB; DR-03, DR-06, DR-07 |
| T07 | P0 | Implement authentication-and-fetch orchestration | `src/api_doc_sync/openapi.py`, `tests/test_api_doc_sync/test_openapi_fetch.py` | T05, T06 | Applies the selected auth mode to fetch; authentication/fetch failures return sanitized stage errors and no raw response content | FR-10, FR-11, FR-12, FR-18; DR-01, DR-03 |
| T08 | P0 | Implement OpenAPI validation and extraction | `src/api_doc_sync/openapi.py`, `tests/test_api_doc_sync/test_openapi_extract.py` | T03, T07 | Supports OpenAPI 3.0/3.1 JSON/YAML; fails closed for unsafe/malformed roots; enforces 10 MB/500 paths/500 schemas; extracts approved fields; invalid facts become `Not Found` | FR-8, FR-9, FR-13, FR-14, FR-16, NFR limits; DR-02, DR-07, DR-10 |
| T09 | P0 | Implement local `$ref` resolver | `src/api_doc_sync/openapi.py`, `tests/test_api_doc_sync/test_refs.py` | T08 | Resolves only local refs to depth 6; stops circular/deep references; external refs become `Not Found`; no external network call occurs | FR-15, NFR `$ref` depth, Edge Cases; DR-03 |
| T10 | P0 | Implement deterministic Markdown and metadata rendering | `src/api_doc_sync/markdown.py`, `tests/test_api_doc_sync/test_markdown.py` | T03, T04, T08, T09 | Generates `docs/api.md` or configured output, preserves declared order, escapes/ redacts text, writes metadata, and enforces 5 MB/50,000-line limits | FR-13, FR-14, FR-17, FR-18, NFR limits; DR-02, DR-03, DR-10 |
| T11 | P0 | Implement baseline/candidate parser and semantic drift | `src/api_doc_sync/drift.py`, `tests/test_api_doc_sync/test_drift.py`, fixtures under `tests/fixtures/baseline/` and `tests/fixtures/candidate/` | T03, T10 | Shared parser reads baseline/candidate metadata and visible facts; ignores formatting/whitespace; reports changed/missing paths/schemas/facts; missing baseline fails explicitly | FR-19, FR-20, FR-21, Edge Cases; DR-02, DR-08, DR-10 |
| T12 | P0 | Implement unified diff and sanitized report model | `src/api_doc_sync/drift.py`, `src/api_doc_sync/github_report.py`, `tests/test_api_doc_sync/test_report.py` | T04, T10, T11 | Creates unified diff and summary counts, missing-fact count, workflow/artifact link fields, and no secret/raw-body content; valid candidate can create full replacement patch for missing baseline | FR-22, FR-23, FR-24, FR-18; DR-03, DR-08 |
| T13 | P0 | Implement CLI lifecycle and pipeline orchestration | `src/api_doc_sync/__main__.py`, `src/api_doc_sync/cli.py`, `tests/test_api_doc_sync/test_cli.py` | T02-T12 | Runs config→lifecycle→fetch→extract→render→drift→report-input generation; returns stage-specific exits; cleans temp/process resources; no committed JSON artifact | FR-1, FR-5, FR-6, FR-21 to FR-24, NFR reliability; DR-05, DR-06, DR-13 |
| T14 | P0 | Implement read-only build GitHub Actions job | `.github/workflows/api-doc-sync.yml`, `tests/workflows/test_api_doc_sync_workflow.py` if kept as a unit-level workflow assertion | T13 | Uses `pull_request`, approved path filters, `windows-latest`, read-only build permissions, invokes completed CLI, and never commits/pushes docs | FR-4, FR-5, FR-21, FR-26, NFR CI; DR-04 |
| T15 | P0 | Implement conditional reporting job/stage | `.github/workflows/api-doc-sync.yml`, reporting helper under `src/api_doc_sync/github_report.py`, workflow tests | T12, T13 | Receives sanitized summary/diff only; uploads patch for 5 days; creates/updates hidden-marker comment only when permitted; fails PR check on drift; fork fallback retains check/artifact | FR-22, FR-23, FR-24, FR-25, FR-26; DR-04, DR-09 |
| T16 | P0 | Create isolated mock application integration fixture | `tests/integration/mock_app.py`, `tests/integration/test_api_doc_sync_e2e.py`, `tests/integration/config/**` | T13; fixture work may begin during T05-T12 | Starts/stops only inside integration tests, exposes health/OpenAPI JSON/YAML loopback endpoints, supports auth-failure/readiness-failure/malformed/oversized fixture modes, and cleans process-tree/temp resources | FR-6, FR-7, FR-8, FR-10, FR-12, FR-16, NFR reliability; DR-05, DR-07 |
| T17 | P0 | Run end-to-end workflow integration | Workflow and integration suite, fixtures under `tests/fixtures/openapi/**` and `tests/fixtures/{baseline,candidate}/` | T14, T15, T16 | Mock app starts, CLI fetches and generates, unchanged case passes, changed case drifts/fails, missing baseline fails, patch is uploaded, comment behavior follows permissions | FR-4, FR-5, FR-6, FR-19 to FR-25, Acceptance Criteria 1-11; DR-04, DR-08, DR-09 |
| T18 | P1 | Update project usage and verification documentation | `README.md`, `docs/verification.md`; add `docs/api-sync-usage.md` only if this is a distinct usage guide | T16, T17 | Documents config, auth secret mapping, fork behavior, Windows runner, startup/fetch limits, artifact/comment fallback, and existing package preservation; no requirement changes | FR-1, FR-10, FR-11, FR-22 to FR-26; DR-12, DR-13 |
| T19 | P0 | Run final unit, security, and workflow verification | Existing test runner, `.github/workflows/api-doc-sync.yml`, `docs/verification.md` | T02-T18; T19 is verification only and does not add duplicate test cases | Mandatory unit/security/workflow tests pass or failures are explicit; exact command/results are recorded; no unrun claim | Acceptance Criterion 11, NFR CI/testing, all tested FR/NDR findings |

## 4. Corrected dependency graph

```text
T01 Foundation
  |
  +--> T02 Configuration
  +--> T03 Canonical model / metadata
  +--> T04 Redaction / errors / temp
              |
              +--> T05 Authentication
              |
T02 ----------+--> T06 HTTP fetch
  |               |
  +---------------> T07 Retrieval orchestration
                      |
T03 ------------------> T08 OpenAPI extract
                          |
                          v
                         T09 $ref resolver
                          |
                          v
                         T10 Markdown / metadata
                          |
                          v
                         T11 Drift
                          |
                          v
                         T12 Diff / report model
                          |
                          v
                         T13 CLI
                          |
          +---------------+---------------+
          v                               v
         T14 Build workflow          T15 Reporting workflow
          |                               |
          +---------------+---------------+
                          v
                         T16 Mock fixture
                          |
                          v
                         T17 End-to-end workflow
                          |
                          v
                         T18 Docs
                          |
                          v
                         T19 Verification
```

Authentication is implemented before retrieval orchestration and HTTP composition.
HTTP fetching is complete before OpenAPI extraction. The CLI is created only
after lifecycle, auth, fetch, extraction, Markdown, drift, and reporting inputs
exist. GitHub Actions invokes the CLI; it does not duplicate pipeline logic.

## 5. Testing plan

### 5.1 Unit testing alongside implementation

Every implementation task owns focused tests at or before that task is complete:

- T02: configuration, environment override, credential values.
- T03: canonical model, `Not Found`, metadata round-trip.
- T04: secret-like values, stage errors, temp cleanup.
- T05: all five authentication modes and fork-secret behavior.
- T06: streaming, 10 MB limit, timeout, four attempts, 1-second retry.
- T08: JSON/YAML, OpenAPI 3.0/3.1, limits, extraction, invalid fields.
- T09: depth/cycle/external `$ref`.
- T10: Markdown, HTML-comment metadata, escaping, size/line limits.
- T11: unchanged/changed/missing baseline drift semantics.
- T12: unified diff, summary counts, missing-baseline replacement patch.
- T13: stage exits and lifecycle cleanup.

There is no separate T16 unit-test suite; T16/T17 are integration and
workflow verification only.

### 5.2 Security testing

Security tests are distributed across T04, T05, T09, T10, T12, T14, T15, and
T16 rather than owned by a duplicate end-of-plan security task.

Mandatory cases:

- no secret or authorization header in Markdown/diff/log/comment/report;
- secret-like OpenAPI descriptions and schema values are redacted;
- raw API response bodies do not enter output;
- external `$ref` performs no network request;
- cycle/deep `$ref` terminates safely;
- fork build jobs receive no write permission or repository secret;
- reporting jobs receive only sanitized summary/diff metadata;
- temp files are cleaned after success and exceptions.

### 5.3 Mock application integration fixture

The mock application is isolated under `tests/integration/mock_app.py`.

- It is not added to `src/` or executed as production application code.
- T16 starts it as a test-owned loopback process.
- It exposes health and absolute OpenAPI URLs.
- It supports JSON and YAML OpenAPI fixtures.
- It supports no-auth and fixture authentication failure modes.
- It supports slow startup, malformed spec, oversized response, and ordinary
  success modes.
- T16 owns process/fixture startup and end-to-end assertions.
- T16/T17 stop the process tree and remove temporary output in success and
  failure cases.

## 6. Test fixture layout

Use only test fixtures for baseline/candidate and OpenAPI documents:

```text
tests/
  fixtures/
    baseline/
      unchanged.md
      changed.md
      missing-fields.md
    candidate/
      unchanged.md
      changed.md
      missing-fields.md
    openapi/
      openapi-3.0.json
      openapi-3.1.yaml
      malformed.json
      oversized.json
      external-ref.yaml
      circular-ref.json
  integration/
    mock_app.py
    test_api_doc_sync_e2e.py
  test_api_doc_sync/
    test_config.py
    test_model.py
    test_security.py
    test_auth.py
    test_openapi_fetch.py
    test_openapi_extract.py
    test_refs.py
    test_markdown.py
    test_drift.py
    test_report.py
    test_cli.py
```

The real `docs/api.md` is never used as a test fixture.

## 7. Traceability matrix

### 7.1 Functional requirements

| Requirements | Implementation tasks | Verification |
|---|---|---|
| FR-1, FR-2, FR-3 | T02 | T02 unit tests |
| FR-4 | T14 | T14/T17 workflow tests |
| FR-5, FR-6 | T13, T14, T16 | T13 unit and T16/T17 integration tests |
| FR-7, FR-8, FR-9 | T06, T08 | T06/T08 unit tests and T16 fixture tests |
| FR-10, FR-11 | T02, T05, T07 | T05/T07 unit/security tests and T16 trusted/fork behavior |
| FR-12 | T06, T07 | T06/T07 unit tests |
| FR-13 | T08, T10 | T08/T10 unit tests |
| FR-14 | T03, T08, T10 | T03/T08/T10 unit tests |
| FR-15 | T09 | T09 unit/security tests |
| FR-16 | T08 | T08 unit tests and T16 malformed-spec case |
| FR-17 | T10 | T10 unit and fixture tests |
| FR-18 | T04, T05, T10, T12, T15 | T04/T05/T10/T12/T15 security tests |
| FR-19 | T11 | T11 baseline/candidate fixture tests |
| FR-20 | T11 | T11 formatting-insensitive drift tests |
| FR-21 | T11, T13, T14 | T11/T14/T17 drift/failing-check tests |
| FR-22 | T15 | T15/T17 conditional comment tests |
| FR-23 | T12, T15 | T12/T15 report-link tests |
| FR-24 | T12, T15 | T12/T15/T17 unified-diff tests |
| FR-25 | T15 | T15 workflow artifact-retention test |
| FR-26 | T14, T15 | T14/T15 permission tests |

### 7.2 Non-functional requirements

| Requirement area | Implementation tasks | Verification |
|---|---|---|
| 10 MB OpenAPI limit | T06, T08 | T06/T08 streaming and size tests |
| 500 paths / 500 schemas | T08 | T08 boundary tests |
| $ref depth 6 | T09 | T09 depth/cycle tests |
| 5 MB / 50,000-line Markdown | T10 | T10 size/line boundary tests |
| 5-minute startup | T13, T16 | T13/T16 readiness timeout tests |
| 180-second timeout / four attempts / 1-second delay | T06, T07 | T06/T07 retry tests |
| Determinism | T03, T10, T11 | T03/T10/T11 repeated-output tests |
| GitHub Actions smoke/CI | T14, T15, T17 | T14/T15/T17 workflow smoke |
| Secret and external-$ref security | T04, T05, T09, T12 | T04/T05/T09/T12 security tests |

### 7.3 Design-review findings

| Finding | Implementation tasks | Verification |
|---|---|---|
| DR-01 Authentication coverage | T02, T05, T07 | T02/T05 unit and security tests |
| DR-02 HTML baseline metadata | T03, T10, T11 | T03/T10/T11 fixture round-trip tests |
| DR-03 Redaction | T04, T10, T12 | T04/T10/T12 redaction tests |
| DR-04 Read-only build/report separation | T14, T15 | T14/T15 workflow permission tests |
| DR-05 Process cleanup | T13, T16 | T13/T16 ordinary/timeout/child cleanup tests |
| DR-06 Separate startup/retry timing | T06, T13 | T06/T13 timing tests |
| DR-07 Streamed 10 MB fetch | T06 | T06 streaming boundary tests |
| DR-08 Missing baseline | T11, T12, T15 | T11/T12/T17 missing-baseline tests |
| DR-09 Fork fallback | T15, T17 | T15/T17 no-permission and artifact fallback tests |
| DR-10 Shared parser/fixtures | T03, T10, T11 | T03/T10/T11 fixture tests |
| DR-11 Maintainable module boundaries | T01-T15 | Focused unit tests per module |
| DR-12 Preserve existing package | T01, T18 | T19 import-regression and docs check |
| DR-13 Stage logging | T04, T13 | T04/T13 stage-code and sanitization tests |

## 8. Open dependencies and implementation boundaries

- OAuth2/OIDC provider-specific token endpoint, audience/identity, scopes, and
  secret mapping values must be supplied through approved repository
  configuration and trusted secret/OIDC sources.
- Fork pull-request jobs cannot receive repository credentials or guaranteed
  PR-comment write access; authenticated-fork and commenting behavior remains
  a controlled fallback.
- `windows-latest` remains the implementation runner. Changing runner requires
  requirements approval.
- HTML-comment metadata schema details must be tested as part of T03/T10/T11,
  not introduced as a second committed artifact.

## 9. Final implementation acceptance gate

Implementation is complete when:

- every T01-T19 task has passing acceptance evidence;
- unit tests cover every implemented module;
- security tests cover secrets, raw bodies, external refs, temp cleanup, and
  fork permissions;
- mock integration tests cover startup, OpenAPI JSON/YAML, no drift, drift,
  malformed spec, oversized spec, and missing baseline;
- workflow smoke tests verify build/report separation and artifact/check/comment
  behavior;
- `docs/api.md` remains the only committed documentation artifact;
- existing `src/doc_sync_capstone/` behavior remains intact;
- no implementation task silently changes an approved requirement.
