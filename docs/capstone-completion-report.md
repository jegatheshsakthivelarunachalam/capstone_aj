# Capstone Project Completion Report

## Project Title

**Automated Documentation Sync Using GitHub Copilot**

## 1. Executive Summary

This capstone demonstrates how GitHub Copilot can support structured software development and the automation of API documentation maintenance.

The primary project, API Documentation Sync, retrieves a running application's OpenAPI specification, generates Markdown API documentation, and detects semantic differences between the generated documentation and the committed baseline.

The repository also preserves an earlier Technical Profile Generator that creates a factual Markdown profile from public GitHub repository information.

The project combines Python development, automated testing, GitHub Actions, security controls, and GitHub Copilot SDLC guidance.

## 2. Problem Statement

API documentation can become outdated when application endpoints, operations, request or response schemas, and fields change without corresponding updates to the documentation.

Manual comparison is time-consuming and may allow inconsistencies to reach the main branch.

The project addresses this problem by automatically comparing live API information with committed documentation during pull requests and reporting detected differences.

## 3. Project Objectives

- Retrieve live OpenAPI 3.0 and 3.1 specifications.
- Generate Markdown API documentation.
- Maintain a committed documentation baseline.
- Detect added, removed, and modified API paths, operations, schemas, and schema fields.
- Generate machine-readable JSON drift reports.
- Generate unified-diff patches for review.
- Integrate documentation checks into GitHub pull requests.
- Protect credentials and sensitive information.
- Preserve the existing Technical Profile Generator.
- Apply structured GitHub Copilot-assisted SDLC practices.

## 4. Repository Projects

### 4.1 Primary project: API Documentation Sync

The API Documentation Sync implementation is located in:

`src/api_doc_sync/`

Its responsibilities include:

- Configuration loading and validation.
- Application startup and readiness checks.
- OpenAPI retrieval and validation.
- Markdown generation.
- Semantic baseline comparison.
- Detailed drift reporting.
- Unified-diff generation.
- Credential redaction and security handling.
- CLI execution.

### 4.2 Preserved project: Technical Profile Generator

The existing implementation remains under:

`src/doc_sync_capstone/`

It reads public GitHub repository information and produces a local Markdown Technical Profile.

It does not execute repository code or publish to Confluence. Unsupported facts are represented as `Not Found`.

## 5. System Architecture and Workflow

The primary API Documentation Sync workflow follows these stages:

1. Read the approved configuration.
2. Start the configured application.
3. Wait for the health and OpenAPI endpoints.
4. Retrieve and validate the OpenAPI specification.
5. Generate candidate Markdown documentation.
6. Load the committed documentation baseline.
7. Compare semantic API facts.
8. Generate a detailed JSON report and unified-diff patch.
9. Publish available findings through GitHub Actions.
10. Fail the documentation check when drift is detected.

The workflow separates the read-only build job from the reporting job and does not automatically commit or push generated documentation.

## 6. Technology Stack

- **Language:** Python
- **API specification:** OpenAPI 3.0 and 3.1
- **Documentation format:** Markdown
- **Configuration:** YAML
- **Testing:** Python unittest
- **Version control:** Git and GitHub
- **Automation:** GitHub Actions
- **Development assistance:** GitHub Copilot instructions, agents, prompts, and skills

## 7. GitHub Copilot SDLC Features

The repository contains structured Copilot guidance for the development lifecycle.

### Project instructions

`.github/copilot-instructions.md`

Defines shared project purpose, source-of-truth documents, development conventions, security rules, testing expectations, and human approval requirements.

### Agents

Located in `.github/agents/`:

- Requirements Analyst
- API Documentation Sync Engineer
- SDLC Reviewer
- Technical Profile Builder

These agents define focused responsibilities for requirements, implementation, review, and the preserved Technical Profile project.

### Prompts

Located in `.github/prompts/`:

- Requirements
- Architecture
- Design Review
- Implementation Plan
- Implementation
- PR Description
- Review and Verification

These prompts provide repeatable instructions for the relevant SDLC activities.

### Skills

Located in `.github/skills/`:

- `api-documentation-sync`
- `github-technical-profile`

These describe domain-specific workflows, security requirements, and verification expectations.

The repository includes these reusable assets. Their presence alone should not be interpreted as evidence that every asset was invoked during implementation.

## 8. Testing and Verification

The complete test suite was recorded as passing:

```powershell
python -m unittest discover -s tests -v
```

**Recorded result: 150 tests passed.**

Additional recorded verification:

| Verification | Result |
|---|---|
| Python compilation | Passed |
| Workflow and configuration YAML validation | Passed |
| Git diff whitespace validation | Passed |
| Local drift detection scenario | Passed |
| Local clean-baseline scenario | Passed |
| Hosted drift reporting job | Passed |

The drift scenario returned exit code `1`, as expected when semantic drift was detected.

The clean-baseline scenario returned exit code `0`.

Python 3.10 was not available for local verification; refer to the hosted CI workflow for version-specific evidence.

## 9. Practical Demonstration

The project includes an intentional API documentation drift demonstration.

Pull request:

[PR #4 â€” Demo: Detect API documentation drift](https://github.com/jegatheshsakthivelarunachalam/capstone_aj/pull/4)

The mock application introduces:

- A new `GET /patients` endpoint.
- A new `Patient` schema.
- Four fields: `patient_id`, `first_name`, `email`, and `phone`.

The workflow detects these additions and reports the affected paths, operations, schemas, and fields.

Recorded hosted behavior:

- Generate and check API documentation job: failed as expected because drift was introduced.
- Report API documentation drift job: succeeded.
- Detailed pull-request comment: successfully displayed the detected changes.

**Important:** PR #4 is an intentional demonstration and must not be merged as-is because it contains deliberate documentation drift.

## 10. Security Considerations

The implementation includes the following security measures:

- Credential values are sourced from trusted environment variables or approved secret/OIDC mechanisms.
- Secrets are not passed through command-line arguments or startup commands.
- Sensitive content is redacted from generated documentation, metadata, reports, and patches.
- External OpenAPI `$ref` references are not fetched.
- Input sizes, processing limits, and timeouts are constrained.
- Build permissions are read-only.
- Generated documentation is not automatically committed or pushed.

### Unresolved workflow trust limitation

The current GitHub Actions workflow is PR-visible. A pull-request author can modify workflow steps or reporting behavior.

Checking out trusted base-revision implementation code does not make a PR-modifiable workflow definition trusted.

A protected default-branch workflow or equivalent protected reusable workflow is required before treating the check as a fully trusted security enforcement boundary.

This limitation remains an open consideration.

## 11. Project Deliverables

The repository contains:

- Python implementation for both projects.
- OpenAPI documentation generation and drift detection.
- GitHub Actions automation.
- Mock integration application and automated tests.
- Copilot project instructions, agents, prompts, and skills.
- Requirements, architecture, design review, and implementation plan.
- API usage guide.
- Code review and verification documents.
- Pull-request demonstration.
- This capstone completion report.

## 12. Conclusion

The capstone demonstrates an automated approach to detecting API documentation drift during software development.

It combines OpenAPI processing, semantic comparison, Markdown generation, test automation, GitHub Actions reporting, and security-aware implementation practices.

The practical pull-request demonstration confirms that the system can identify intentional API changes and present detailed findings to reviewers.

The project also demonstrates structured use of GitHub Copilot SDLC assets while preserving the existing Technical Profile Generator.

The remaining workflow trust-boundary limitation is documented and should be addressed before relying on the workflow as a fully trusted production enforcement mechanism.

## 13. Repository Reference

**GitHub repository:**

https://github.com/jegatheshsakthivelarunachalam/capstone_aj

**Demonstration pull request:**

https://github.com/jegatheshsakthivelarunachalam/capstone_aj/pull/4
