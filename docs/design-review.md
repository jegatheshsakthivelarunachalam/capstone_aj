# Design Review

## Review outcome

**Approved with the decisions and mitigations below.** The architecture is
intentionally a read-only, standard-library CLI that produces a local draft
rather than publishing changes to Confluence.

## Findings and decisions

| Area | Finding / risk | Decision |
|---|---|---|
| Correctness | Missing files must not be mistaken for empty facts. | Represent every absent profile field as `Not Found`; missing supported manifests are not fatal. |
| Security | README text and repository metadata are untrusted and may contain credentials. | Render only a short README introduction, redact common credential/token forms, and never echo raw API or file content in errors. |
| Security | Repository content could contain executable code or malicious XML. | Never execute repository code; parse only JSON, requirements text, and XML with the standard library; reject DTD/entity declarations. |
| Reliability | Anonymous GitHub API requests are rate limited and can fail. | Use request timeouts; surface concise endpoint-independent errors; do not generate a success-shaped profile when required API calls fail. |
| Completeness | GitHub may return a truncated recursive tree. | Fail clearly instead of claiming unsupported files are absent. |
| Resource use | Manifest content may be very large. | Cap each supported file at 1 MB and report an explicit failure if it exceeds the cap. |
| Scope | Publishing would require credentials and a page-update policy. | Out of scope. Generate a Markdown draft only; do not add a credential path. |
| Data handling | Existing output could be overwritten accidentally. | Refuse to overwrite by default; require `--force`. |
| Maintainability | A framework or dependency adds setup burden for a small utility. | Use Python standard library and built-in `unittest`; no runtime dependencies. |

## Agreed design

Proceed with the component boundaries and data flow in
[architecture.md](./architecture.md). The implementation must preserve the
acceptance criteria in [requirements.md](./requirements.md).
