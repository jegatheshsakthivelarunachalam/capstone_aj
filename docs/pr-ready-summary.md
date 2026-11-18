# Pull Request Ready Summary

## Summary

Adds an API Documentation Sync pipeline that starts a configured application,
reads a live OpenAPI document, generates candidate `docs/api.md`, and detects
semantic drift for pull requests. The implementation preserves the existing
Technical Profile package and uses read-only build and isolated reporting
permissions.

## Changes Made

- Add API synchronization CLI, lifecycle, configuration, authentication,
  OpenAPI extraction, Markdown, drift, reporting, and security modules.
- Add HTML metadata-based semantic baseline handling and unified diffs.
- Add `.github/doc-sync.yml` and the pull-request GitHub Actions workflow.
- Add unit, security, workflow, and mock integration tests.
- Add API usage, verification, and handoff documentation.

## Test Evidence

```powershell
python -m unittest discover -s tests -v
python -m compileall -q src tests
git diff --check
python -c "import yaml, pathlib; yaml.safe_load(pathlib.Path('.github/workflows/api-doc-sync.yml').read_text(encoding='utf-8')); yaml.safe_load(pathlib.Path('.github/doc-sync.yml').read_text(encoding='utf-8')); print('workflow/config YAML: valid')"
```

Actual final evidence:

- Complete suite: 145 tests passed.
- Remediation/security focused suite: 47 tests passed.
- Compilation: passed.
- Diff check: passed.
- Workflow/config safe YAML loading: passed.

## Known Limitations

- OAuth2/OIDC provider-specific values remain repository configuration.
- Fork PR workflows cannot receive repository secrets or guarantee comments.
- The workflow reports drift and uploads patches; it does not commit generated
  documentation.
- Hosted GitHub Actions evidence must be recorded after a hosted run.

## Reviewer Checklist

- [ ] Requirements and architecture traceability reviewed.
- [ ] Credentials excluded from logs, diffs, Markdown, metadata, and reports.
- [ ] Read-only build and conditional reporting permissions verified.
- [ ] All approved authentication modes reviewed.
- [ ] JSON/YAML, `$ref`, limits, missing baseline, and drift behavior verified.
- [ ] Unit and mock integration tests pass.
