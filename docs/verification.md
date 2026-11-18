# Verification Evidence

## Automated test suite

Run from the project root:

```powershell
python -m unittest discover -s tests -v
python -m compileall -q src tests
git diff --check
```

The suite covers T01–T17 unit, security, workflow, mock-application, and
end-to-end behavior.

Actual final fresh-terminal result: **145 tests passed**.
The final remediation-focused suite passed: **47 tests**.

## Compilation

```powershell
python -m compileall -q src tests
```

Result: **passed**.

## YAML validation

```powershell
python -c "import yaml, pathlib; yaml.safe_load(pathlib.Path('.github/workflows/api-doc-sync.yml').read_text(encoding='utf-8')); yaml.safe_load(pathlib.Path('.github/doc-sync.yml').read_text(encoding='utf-8')); print('workflow/config YAML: valid')"
```

Result: **workflow/config YAML: valid**.

## Diff and protected-file checks

```powershell
git diff --check
```

Result: **passed**. `src/doc_sync_capstone/` and the approved requirements,
architecture, design-review, and implementation-plan documents were unchanged.

## Not run

- Python 3.10 was not available for local verification; its hosted CI job passed.
- The PR was not created: GitHub CLI authentication is unavailable in this
  session.
