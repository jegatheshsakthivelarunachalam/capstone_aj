
# Project Instructions

## Project Purpose

This repository contains two independent Python projects:

1. **API Documentation Sync** (`src/api_doc_sync/`): Starts a configured
   application, retrieves its live OpenAPI specification, generates Markdown
   API documentation, and detects semantic drift against the committed
   documentation baseline.
2. **Technical Profile Generator** (`src/doc_sync_capstone/`): Reads public
   GitHub repository information and generates a local Markdown Technical
   Profile.

API Documentation Sync is the primary capstone project.

Preserve the existing Technical Profile functionality when modifying
API Documentation Sync.

## Source of Truth

Before implementation, review the applicable documents:

- `docs/requirements.md`
- `docs/architecture.md`
- `docs/design-review.md`
- `docs/impl-plan.md`
- `docs/code-review.md`
- `docs/verification.md`

Do not silently change approved requirements or protected planning decisions.
Ask for human approval when a change affects approved scope or architecture.

## API Documentation Sync Rules

- Treat the configured application and OpenAPI response as untrusted input.
- Support the approved OpenAPI 3.0 and 3.1 JSON/YAML behavior.
- Do not fetch external OpenAPI `$ref` references.
- Preserve semantic comparison against the committed documentation baseline.
- Report added, removed, and modified paths, operations, schemas, and schema
  fields where supported.
- Generate candidate documentation, JSON reports, and unified-diff patches.
- Never automatically commit or push generated documentation.
- Handle missing baselines and API failures explicitly.
- Respect configured input, output, timeout, and processing limits.

## Security Rules

- Never expose credentials, tokens, authorization headers, or raw sensitive
  response bodies in logs, reports, Markdown, metadata, or patches.
- Obtain credential values only from trusted environment variables or
  approved secret/OIDC mechanisms.
- Never pass secrets through command-line arguments or startup commands.
- Treat pull-request code and configuration as untrusted.
- Do not claim the PR-visible workflow is a fully trusted security boundary.
- Preserve least-privilege permissions and the existing separation between
  build and reporting jobs.

## Technical Profile Rules

- Use public repository evidence only.
- Never execute repository code.
- Do not infer unsupported technology or dependency facts.
- Render missing facts as `Not Found`.
- Do not add Confluence publishing without approved requirements.

## Development and Testing

- Follow existing package and code conventions.
- Add focused tests for new behavior and relevant failure/security cases.
- Preserve compatibility with both project packages.
- Run focused tests first and the complete suite when practical.

Standard full-suite command:

`python -m unittest discover -s tests -v`

Also run compilation, YAML validation, and `git diff --check` when relevant.

Record only checks that were actually executed. Never invent test results,
CI results, review approvals, or PR status.

## Human Approval

The human reviewer approves requirements, design decisions, implementation
scope, and changes to protected files.

Do not commit, push, or merge without explicit human approval.
