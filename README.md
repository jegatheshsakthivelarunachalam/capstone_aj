# Automated Documentation Sync

Generate a local Markdown Technical Profile from a **public GitHub repository**.
The tool reads repository metadata, GitHub language statistics, `README.md`,
and tracked `package.json`, `requirements.txt`, and `pom.xml` files. It does not
clone or execute repository code and does not publish to Confluence.

## Requirements

- Python 3.10 or later
- Network access to the public GitHub REST API

The application has no third-party Python dependencies.

## Usage

From the project root:

```powershell
python -m src.doc_sync_capstone https://github.com/owner/repository
```

By default, the command writes `technical-profile.md` in the current directory
and refuses to overwrite an existing file. Choose an output path or explicitly
allow replacement:

```powershell
python -m src.doc_sync_capstone https://github.com/owner/repository --output docs\technical-profile.md
python -m src.doc_sync_capstone https://github.com/owner/repository --output docs\technical-profile.md --force
```

Missing facts are shown as `Not Found`. Only public repositories are supported;
private-repository authentication and Confluence publishing are out of scope.
Supported manifest files larger than 1 MB, malformed manifests, API failures,
and incomplete GitHub trees are reported as errors.

## Tests

```powershell
python -m unittest discover -s tests -v
```

See [`docs/`](docs/) for requirements, architecture, design review,
implementation plan, code review, and verification evidence.
