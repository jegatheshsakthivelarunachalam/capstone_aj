# Pull Request Description

## Summary

Adds a dependency-free Python CLI that reads a public GitHub repository and
generates a local Markdown Technical Profile. The profile uses repository
evidence, marks missing facts as `Not Found`, and does not publish to Confluence.

## Changes Made

- Add the Python CLI, GitHub API reader, README/manifest extraction, secret
  filtering, and Markdown renderer.
- Add 26 unit tests and a GitHub Actions test workflow for Python 3.10 and 3.14.
- Add Copilot SDLC agents, prompts, project instructions, and a technical-profile
  skill.
- Add the requirements, architecture, design review, implementation plan, code
  review, verification evidence, and generated example profile in `/docs`.
- Add usage guidance and an Unreleased changelog entry.

## Test Evidence

- `python -m unittest discover -s tests -v` — **26 tests passed** on Python
  3.14.3.
- Pylance diagnostics for source and tests — **No errors found**.
- Ran the CLI against the supplied public repository; it generated
  `docs/technical-profile.md` with missing language and manifest facts shown as
  `Not Found`.

## Known Limitations

- Supports public GitHub repositories only; private-repository authentication
  and Confluence publishing are out of scope.
- Anonymous GitHub API rate limits apply; supported manifest files are limited
  to 1 MB.
- Only `package.json`, `requirements.txt`, and `pom.xml` are analyzed.
- Secret detection filters common credential/token patterns but cannot identify
  every arbitrary secret string.
- The hosted GitHub Actions workflow has not yet run.

## Reviewer Checklist

- [ ] Confirm behavior matches `/docs/requirements.md`.
- [ ] Verify missing facts appear as `Not Found`.
- [ ] Review URL validation, error handling, secret filtering, and Markdown
  escaping.
- [ ] Run the unit suite and inspect `docs/technical-profile.md`.
- [ ] Confirm the public-only / no-Confluence scope and redaction limitation are
  acceptable.
