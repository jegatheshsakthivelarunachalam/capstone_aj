# Formal Architecture Design Review

## Review disposition

**Verdict: Approved after agreed architectural resolutions.**

The architecture satisfies the approved requirements after the following
resolutions:

- preserve no-auth, Bearer, Basic, API-key, and OAuth2 client credential support;
- keep `docs/api.md` as the only committed documentation artifact and embed
  deterministic HTML-comment metadata;
- redact before Markdown, diff, temp, log, and reporting output;
- separate the read-only build job from conditional reporting;
- bound process-tree cleanup;
- keep startup readiness, HTTP timeout, and retries as separate stages;
- stream and bound OpenAPI responses;
- preserve fork reporting fallback and existing source files.

No finding changes, removes, or expands a requirement.

## Strengths

- Uses `pull_request`, not `pull_request_target`, for untrusted PR code.
- Keeps the build job read-only and recommends explicit reporting isolation.
- Preserves every approved resource and artifact limit.
- Uses `Not Found` and external `$ref` safeguards consistently.
- Separates configuration, lifecycle, extraction, generation, drift, and reporting.
- Never proposes committing or pushing candidate documentation.
- Provides deterministic source-order Markdown and semantic drift expectations.

# Findings

## DR-01

- **Review category:** Requirement coverage / Security
- **Severity:** High
- **Description:** The architecture previously described enterprise
  authentication as gated instead of specifying coverage for FR-10 and FR-11.
- **Potential impact:** An implementation could omit an approved authentication
  mode or expose credentials to PR-controlled code.
- **Recommended solution:** Implement small explicit no-auth, Bearer, Basic,
  API-key, and OAuth2 client credential adapters. Store secret names in
  `.github/doc-sync.yml`; obtain values from GitHub secrets or OIDC only in a
  trusted context.
- **Architecture update:** Required and applied.
- **Decision:** Approved.
- **Resolution:** Architecture now defines an authentication adapter and fork
  behavior.
- **Remaining limitation:** Repository-specific OAuth2/OIDC token endpoint,
  audience, subject/identity, and secret mapping values must be provided.

## DR-02

- **Review category:** Requirement coverage / Drift reliability
- **Severity:** High
- **Description:** Semantic drift comparison previously lacked a stable way to
  distinguish Markdown formatting from API facts.
- **Potential impact:** Drift detection could depend on brittle free-text
  parsing or differ between baseline and candidate documents.
- **Recommended solution:** Keep `docs/api.md` as the sole artifact and embed
  deterministic HTML-comment metadata from the shared canonical model.
- **Architecture update:** Required and applied.
- **Decision:** Approved.
- **Resolution:** Baseline and candidate now use the same canonical parser/model.
- **Remaining limitation:** Metadata parsing and format fixtures must be validated
  during implementation and tests.

## DR-03

- **Review category:** Security
- **Severity:** High
- **Description:** Redaction could be applied only to final reporting while
  candidate Markdown or diff temp files retained secret-like text.
- **Potential impact:** Credential-like text could leak through logs, diffs,
  temp artifacts, or comments.
- **Recommended solution:** Redact canonical text before Markdown, temp data,
  unified diff, logs, and reporting. Test secret-like descriptions and schemas.
- **Architecture update:** Required and applied.
- **Decision:** Approved.
- **Resolution:** The architecture now defines an end-to-end redaction boundary.
- **Remaining limitation:** Pattern-based redaction cannot identify every
  arbitrary secret; allowlisted secret handling remains preferable.

## DR-04

- **Review category:** GitHub Actions / Security
- **Severity:** Medium
- **Description:** Reporting permissions and PR build responsibilities were not
  explicitly separated.
- **Potential impact:** PR-controlled startup code could accidentally receive
  write permissions or secrets.
- **Recommended solution:** Use a read-only build job and a conditional
  reporting job that receives only sanitized summary/diff metadata.
- **Architecture update:** Required and applied.
- **Decision:** Approved.
- **Resolution:** Separate trust boundaries are documented in the architecture
  and workflow data flow.
- **Remaining limitation:** Fork PR comment permissions remain unavailable by
  GitHub event policy.

## DR-05

- **Review category:** Reliability
- **Severity:** Medium
- **Description:** The architecture promised process cleanup but did not specify
  termination of child processes or shell/process trees.
- **Potential impact:** Child processes could remain listening after a failed or
  completed PR check.
- **Recommended solution:** Implement bounded process-tree cleanup and
  exception-safe termination, including Windows process-tree handling.
- **Architecture update:** Required and applied.
- **Decision:** Approved.
- **Resolution:** Process cleanup now covers ordinary, timeout, and exception paths.
- **Remaining limitation:** Windows process-job behavior may require runner or
  platform-specific implementation details.

## DR-06

- **Review category:** Reliability / Performance
- **Severity:** Medium
- **Description:** Startup readiness and HTTP retry timing were not described
  as independent stage deadlines.
- **Potential impact:** Fetch retries could be interpreted as extending the
  5-minute startup readiness deadline or create unclear failure stages.
- **Recommended solution:** Keep startup at 5 minutes, then apply 180-second
  HTTP attempts and four total attempts with fixed 1-second retries. Do not
  add an overall timeout.
- **Architecture update:** Required and applied.
- **Decision:** Approved.
- **Resolution:** Stage timing is explicitly separated.
- **Remaining limitation:** GitHub-hosted runner limits remain external.

## DR-07

- **Review category:** Performance / Security
- **Severity:** Medium
- **Description:** The 10 MB limit was stated without an explicit streaming
  and rejection mechanism.
- **Potential impact:** The full response could be buffered before resource
  enforcement.
- **Recommended solution:** Stream the response and reject above 10 MB before
  JSON/YAML parsing.
- **Architecture update:** Required and applied.
- **Decision:** Approved.
- **Resolution:** Stream-and-bound behavior is now documented.
- **Remaining limitation:** Network/system buffering below the application
  limit remains subject to runner constraints.

## DR-08

- **Review category:** Reliability / Error handling
- **Severity:** Medium
- **Description:** Missing `docs/api.md` behavior was identified but not
  specified across the failure/report sequence.
- **Potential impact:** Reviewers could receive an unclear failure or no
  replacement patch.
- **Recommended solution:** Return an explicit missing-baseline validation
  failure and create a full replacement patch only if candidate generation
  succeeds.
- **Architecture update:** Required and applied.
- **Decision:** Approved.
- **Resolution:** Missing baseline handling is now explicit.
- **Remaining limitation:** PR comment availability still follows fork policy.

## DR-09

- **Review category:** GitHub Actions / Requirement coverage
- **Severity:** Medium
- **Description:** An unconditional PR comment conflicts with GitHub fork
  permission restrictions.
- **Potential impact:** A valid PR could not receive a comment even though drift
  and artifact reporting work.
- **Recommended solution:** Make comment creation conditional; retain the
  failing check and unified-diff artifact as guaranteed fallbacks.
- **Architecture update:** Required and applied.
- **Decision:** Approved.
- **Resolution:** Conditional comments and fallback behavior are documented.
- **Remaining limitation:** FR-22 remains subject to available
  `pull-requests: write` permission.

## DR-10

- **Review category:** Testability / Drift reliability
- **Severity:** Medium
- **Description:** Unit-test coverage did not define a stable baseline format or
  fixtures.
- **Potential impact:** Renderer/parser changes could invalidate drift results.
- **Recommended solution:** Embed canonical HTML-comment metadata and test
  baseline/candidate normalization with fixed fixtures.
- **Architecture update:** Required and applied.
- **Decision:** Approved.
- **Resolution:** Shared canonical parser/model and metadata are documented.
- **Remaining limitation:** Metadata schema details remain an implementation
  contract requiring test coverage.

## DR-11

- **Review category:** Maintainability
- **Severity:** Low
- **Description:** The original component set was moderate and did not require
  enterprise abstractions.
- **Potential impact:** Excessive abstractions could increase implementation
  and test burden.
- **Recommended solution:** Retain the six module boundaries and use a small
  authentication adapter instead of an enterprise framework.
- **Architecture update:** Not required as a structural change.
- **Decision:** Approved.
- **Resolution:** Modular simplicity is preserved.
- **Remaining limitation:** None in this review.

## DR-12

- **Review category:** Maintainability / Scope
- **Severity:** Low
- **Description:** Existing Technical Profile code must not be overwritten or
  deleted while API synchronization is added.
- **Potential impact:** Module and entry-point confusion could occur.
- **Recommended solution:** Preserve `src/doc_sync_capstone/` and add a separate
  `src/api_doc_sync/` package boundary.
- **Architecture update:** Required and applied.
- **Decision:** Approved.
- **Resolution:** Existing and new source boundaries are documented.
- **Remaining limitation:** CLI entry points must be clearly documented by the
  implementation.

## DR-13

- **Review category:** Reliability / Observability
- **Severity:** Low
- **Description:** Failure reporting did not explicitly separate startup,
  fetch, parse, generation, drift, artifact, and comment stages.
- **Potential impact:** Operators could diagnose failures only by broad workflow
  status.
- **Recommended solution:** Emit sanitized stage identifiers and meaningful
  exit codes for each stage.
- **Architecture update:** Required and applied.
- **Decision:** Approved.
- **Resolution:** Stage logging and exit codes are documented.
- **Remaining limitation:** Raw response bodies and secret values remain excluded
  even for detailed diagnostics.

# Critical and high-priority findings

No finding was classified as Critical.

High-priority resolved findings:

- DR-01: Authentication modes and trusted secret boundaries.
- DR-02: Machine-readable baseline metadata and shared parser/model.
- DR-03: Redaction before all generated and reporting outputs.

# Requirement coverage summary

All FR-1 through FR-26 are covered by the revised architecture.

The key approvals are:

- FR-10 and FR-11: all required authentication modes and secret sources.
- FR-12: 180-second timeout, four attempts, and fixed 1-second delay.
- FR-17 and FR-20: deterministic Markdown and semantic drift.
- FR-22/FR-23: conditional comment with workflow/artifact links.
- FR-24/FR-25: unified diff and 5-day artifact retention.
- FR-26: read-only build permissions and conditional reporting permissions.

No approved requirement was changed.

# Remaining open decisions

1. OAuth2/OIDC provider-specific token endpoint and identity configuration.
2. Exact HTML-comment metadata schema and canonical model fields.
3. Existing unit-test workflow versus API synchronization workflow naming.

# References

- [requirements.md](./requirements.md)
- [architecture.md](./architecture.md)
