# Architecture: Automated Technical Profile

## Overview

Implement a dependency-free Python command-line tool. It reads a public
repository through GitHub's HTTPS REST API and writes a Markdown document. It
does not clone repositories, execute repository code, or publish to Confluence.

## Components

1. **CLI** — validates arguments, invokes profile generation, writes the
   requested output, and maps expected failures to a nonzero exit status.
2. **GitHub client** — validates the repository URL and reads repository
   metadata, language statistics, the recursive default-branch tree, and the
   contents of supported files. Requests use a timeout and do not require a
   token.
3. **Extractors** — functions in the application module parse `package.json`,
   `requirements.txt`, and `pom.xml` without executing repository code. README
   extraction selects a short introductory paragraph and redacts common secret
   formats.
4. **Profile renderer** — converts collected evidence into stable Markdown
   sections; absent facts render as `Not Found`.
5. **Tests** — standard-library `unittest` cases cover each function and mock
   network responses for deterministic behavior.

## Data flow

```text
GitHub HTTPS URL
       |
       v
URL validation -> GitHub metadata + language API + default-branch tree
                                         |
                                         v
                         supported-file contents (read-only)
                                         |
                                         v
                              extraction and redaction
                                         |
                                         v
                         TechnicalProfile -> Markdown file
```

## Technology choices

- Python, standard library (`urllib`, `json`, `xml.etree.ElementTree`,
  `argparse`, `unittest`).
- GitHub REST API, anonymous requests for public repositories.
- Markdown as an intermediate deliverable suitable for review or later
  Confluence import.

## Failure and security boundaries

- Reject URLs outside the canonical `https://github.com/{owner}/{repo}` form.
- Do not log request/response bodies or include them in raised errors.
- Never execute code from the analyzed repository.
- Bound supported-file reads to 1 MB; report a clear error if a file cannot be
  inspected.
- Treat malformed manifests and incomplete/truncated repository-tree responses
  as errors rather than silently presenting partial facts.
- Sanitize README-derived text and repository descriptions before rendering.
- No secrets are required or accepted by the initial CLI.

## Deployment

Run from the repository root with Python 3.10 or later:

```powershell
python -m src.doc_sync_capstone https://github.com/owner/repository
```

The default output is `technical-profile.md`; `--output` selects another path,
and `--force` permits replacing an existing file.
