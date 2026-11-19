
---
description: Review both projects and verify implementation, generated artifacts, security, and test evidence.
mode: agent
---

Read `.github/copilot-instructions.md`, the applicable project skill,
`/docs/requirements.md`, and `/docs/code-review.md`.

Review the implementation for:
- Correctness and requirements compliance.
- Security, secret handling, and input validation.
- Error handling and resource limits.
- Test coverage, clarity, duplication, and dependency safety.
- Preservation of existing Technical Profile functionality.

For API Documentation Sync, additionally verify:
- OpenAPI parsing and semantic drift detection.
- Generated Markdown, JSON report, and unified-diff patch.
- Added, removed, and modified paths, operations, schemas, and fields.
- Authentication and credential redaction.
- Workflow permissions, reporting job, artifact handling, and trust-boundary limitations.

For Technical Profile Generator, additionally verify:
- Public repository evidence supports generated facts.
- Missing facts are rendered as `Not Found`.
- Repository code is not executed.

Run the complete test suite:

`python -m unittest discover -s tests -v`

Also run compilation, YAML validation, generated-document checks,
and `git diff --check` where applicable.

Update `/docs/code-review.md` and `/docs/verification.md` with findings
and actual evidence. Do not hide unresolved issues or claim unrun checks passed.
