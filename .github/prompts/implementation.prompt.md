
---
description: Implement approved tasks for either repository project with focused tests and evidence.
mode: agent
---

Read `.github/copilot-instructions.md` and the applicable project skill.

Implement only approved tasks in `/docs/impl-plan.md`, following the
requirements, architecture, and design-review decisions.

For API Documentation Sync:
- Preserve the semantic OpenAPI comparison and baseline behavior.
- Preserve secret redaction, input limits, timeouts, and process cleanup.
- Never fetch external OpenAPI `$ref` references.
- Preserve least-privilege GitHub Actions permissions and job separation.
- Never automatically commit or push generated documentation.

For Technical Profile Generator:
- Use public GitHub evidence only.
- Never execute repository code.
- Render unsupported facts as `Not Found`.
- Preserve existing functionality.

For both projects:
- Keep changes surgical and consistent with existing patterns.
- Add focused tests for new behavior and relevant failure cases.
- Run focused tests, then the full suite when practical.
- Record exact commands and actual results in `/docs/verification.md`.
- Never output secrets or claim unrun checks passed.
- Do not modify protected planning decisions without human approval.
