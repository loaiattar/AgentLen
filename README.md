# AgentLen

AgentLen ingests traces from AI coding agents (Claude Code, Codex, ...), normalizes them into a common relational model, and exposes them through a dashboard.

- Architecture : [`docs/architecture/`](docs/architecture/README.md)
- Datasets : [`docs/datasets.md`](docs/datasets.md)

> This README currently documents the ingestion work in progress on `feat/jsonl-reader-profiler` (issue #3). It will be replaced by the full project README once the core setup lands.

## Quickstart

```bash
python -m venv .venv
.venv\Scripts\Activate.ps1   # PowerShell; use .venv/bin/activate on macOS/Linux
pip install -r requirements.txt
python -m pytest -v
```

## Changes and improvements in this branch

### Added
- Real sample extract from TraceLab (`data/samples/tracelab_example_session.jsonl`), 19 rows, sanitized public example pulled from `uw-syfi/TraceLab` (`example_sessions/sanitized/round_trace.jsonl`).
- JSONL reader (`src/agentlen/infrastructure/files/polars_reader.py`): `read_jsonl(path)` loads a JSONL file into a Polars DataFrame.
- Field profiler (`src/agentlen/infrastructure/files/polars_profiler.py`): `profile_fields(df)` returns, per column, the detected dtype, the null rate, and a few example values.
- Unit tests (`tests/unit/test_polars_reader.py`, `tests/unit/test_polars_profiler.py`) covering the reader and the profiler against the real sample extract.
- Project scaffolding: `pyproject.toml` (pytest config, `pythonpath = ["src"]`), `requirements.txt` (polars, pytest), `.gitignore`.

### Fixed
- `profile_fields` initially cast example values to `Utf8` directly through Polars, which crashed on nested columns (e.g. `timing_events`, a list of structs) with `InvalidOperationError: cannot cast List type ... to String`. Fixed by converting example values to Python objects first (`Series.to_list()`) and stringifying them with `str()`, which works for any column type, nested or not.

## Status

- 3/3 tests passing.
- Standalone utility only — not yet wired into any use case or port (those depend on the domain layer, not implemented yet).
