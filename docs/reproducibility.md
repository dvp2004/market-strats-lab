# Reproducibility

## Portable validation

Use Python 3.11 and install the declared development dependencies:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python -m pip install -e ".[dev]"
.\.venv\Scripts\python -m ruff check src tests
.\.venv\Scripts\python -m pytest -q -m "not artifact"
```

Portable tests use synthetic fixtures and temporary directories. Tests requiring local generated
evidence must carry the `artifact` marker and are run separately by an operator with the required
manifested inputs.

## Local evidence

Raw provider responses, SEC filings, macro vintage payloads, Parquet panels, reports, release
archives, and environments are not versioned. A reproducible local run should record:

- source and dataset identifiers;
- retrieval and availability timestamps;
- request parameters with credentials removed;
- content SHA-256 values;
- parser and contract versions;
- exact code commit and configuration hashes;
- output paths relative to an explicitly supplied local root.

Do not print or commit API keys. MI-3 reads its required provider credential from the active
process environment and never loads `.env` automatically. Provider terms remain controlling.

## Prospective boundary

Historical replay may use an explicit as-of timestamp. Prospective mode must use current-time
guards, a clean frozen operating release, and immutable append-only records. Consolidation does
not itself authorize or start prospective observation.
