# Implementation Plan

Tasks are ordered by dependency. A task is blocked until its listed
prerequisites are complete.

| ID | Task | Depends on | Completion evidence |
|---|---|---|---|
| T1 | Define the profile schema, supported inputs, and Markdown sections. | — | Requirements and architecture approved. |
| T2 | Implement safe URL validation and read-only GitHub API access. | T1 | Unit tests cover URL validation, API success, and API failures. |
| T3 | Implement README sanitization and supported manifest extractors. | T1 | Unit tests cover valid, missing, secret-containing, and malformed input. |
| T4 | Assemble repository evidence into the profile and render Markdown. | T2, T3 | Deterministic tests verify output fields and `Not Found` values. |
| T5 | Add CLI output-path and overwrite behavior. | T4 | CLI tests verify success, errors, and no accidental overwrite. |
| T6 | Add workflow-specific Copilot agent, prompts, and skill guidance. | T1 | Files are discoverable under `.github/`; instructions agree with requirements. |
| T7 | Run unit tests and process the supplied public repository URL. | T2, T3, T4, T5 | Test output and generated-profile content check recorded in `/docs`. |
| T8 | Complete the structured code review and prepare PR description/changelog. | T6, T7 | Review checklist and PR description prepared; limitations called out. |
| T9 | Create/submit the PR. | T8 | Requires GitHub authentication and human approval; currently blocked if unavailable. |

## Implementation notes

- Keep all generated planning/review evidence in `/docs`.
- Do not add Confluence publishing, private-repository credentials, or
  unsupported manifest formats without a new requirement.
- Treat API rate limiting and unavailable repository contents as explicit
  failures, not missing facts.
