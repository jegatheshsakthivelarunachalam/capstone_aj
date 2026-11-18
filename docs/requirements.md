# Requirements: Automated Technical Profile

## Context

Generate a Confluence-ready Technical Profile from a GitHub repository. The
user supplied `https://github.com/jegatheshsakthivelarunachalam/capstone_aj`,
selected Python, requested Markdown output only, and confirmed the default
profile fields.

## Functional requirements

- **FR-1 — Repository input:** Accept a public GitHub repository HTTPS URL and
  inspect its default branch. Reject malformed or unsupported URLs with a
  clear error.
- **FR-2 — Evidence sources:** Read repository metadata, GitHub language
  statistics, `README.md`, and any tracked `package.json`, `requirements.txt`,
  or `pom.xml` files, including files in subdirectories.
- **FR-3 — Profile content:** Generate Markdown with the repository name,
  description, default branch, languages, README summary, and detected
  manifest/runtime/dependency details.
- **FR-4 — Missing facts:** Render each unavailable profile fact as `Not Found`.
  Do not infer facts from other fields.
- **FR-5 — Output:** Write a local Markdown file (`technical-profile.md` by
  default); allow an explicit output path. Do not publish to Confluence.
- **FR-6 — Errors:** Report invalid input, inaccessible repositories, API
  failures, and malformed supported manifests as errors and return a nonzero
  exit status. Missing manifests alone are not errors.
- **FR-7 — Secret handling:** Never include credentials or tokens in generated
  output or diagnostics. Sanitize free-text excerpts and do not echo API/file
  response bodies.

## Non-functional requirements

- Use Python and the standard library only for the initial implementation.
- Keep the implementation small, typed, and separated into repository access,
  extraction, and Markdown rendering.
- Add unit tests for every function, including missing-file and malformed-input
  cases.
- Keep project planning and review artifacts in `/docs`.

## Acceptance criteria

1. A valid public repository URL produces a readable Markdown profile.
2. The supplied repository URL can be processed without GitHub credentials.
3. Missing README/manifest fields appear as `Not Found`.
4. Credentials and common token/secret formats are redacted from free-text
   profile fields and never echoed in error messages.
5. Invalid URLs, GitHub API errors, oversized supported files, and malformed
   manifests fail clearly rather than producing a misleading success profile.
6. Unit tests pass using Python's built-in `unittest` runner.

## Decisions and boundaries

- Only public repositories are supported; private-repository authentication is
  out of scope.
- The first release creates Markdown for human review; Confluence API publishing
  and credentials are out of scope.
- The profile uses repository name/description, default branch, languages,
  README summary, and details found in the three supported manifest types.
- Current evidence for the supplied repository: it has a `main` branch, a
  description, `.github/copilot-instructions.md`, and `README.md`; it currently
  has no supported dependency manifest. The generated profile must not infer
  additional technology facts.
