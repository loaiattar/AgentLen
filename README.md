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

## Changes and improvements

### Added — issue #48 (CSV/Parquet profiling, wired to the domain port)
- `polars_reader.py`: `read_csv`, `read_parquet` alongside `read_jsonl`. All three are now **lazy** (`pl.scan_*`, return `LazyFrame`) instead of eager reads, so a large file is never loaded whole. Added `scan_file(path, format=...)` dispatcher and `infer_format(path)` (suffix-based).
- `polars_profiler.py`: rewritten as `PolarsFileProfiler`, a concrete implementation of the `FileProfiler` port (`application/ports/file_reader.py`). `profile(path, sample_size=500)` now returns the domain's `FileProfile`/`FieldProfile` dataclasses (not a Polars object — a leaked Polars type across the port boundary was a stated PR-rejection criterion).
  - Nested fields (structs and lists of structs) are recursively flattened into JSONPath-addressed leaves, e.g. `$.tools[].tool_name`.
  - `record_count` is the file's real total row count (cheap `pl.len()` scan); `sampled_records` is bounded by `sample_size` — the two are computed independently so profiling stays bounded on large files.
  - Per field: `types` (including `"null"` when nulls are present), `null_ratio`, `distinct_ratio`, `min`/`max` (numeric fields only), `examples`.
- `application/use_cases/profile_file.py`: new `ProfileFile` use case — calls the port, then stamps the real `file_id` onto the resulting profile (the port itself is source-agnostic).
- `tests/fixtures/profiler/`: small flat dataset generated identically as `.jsonl`/`.csv`/`.parquet` (`generate_flat_sample.py`), used to test that all three formats produce equivalent `FileProfile`s.
- Test coverage: lazy reading per format, format inference, nested-field flattening on the real TraceLab sample, exact `null_ratio` computation, `record_count` vs `sampled_records` distinction, no-Polars-type-leak check, cross-format equivalence.
- `pyproject.toml` dev extras (`pytest-asyncio`, `mypy`, `import-linter`, `ruff`) — verified locally: `mypy --strict` and `import-linter` both pass on `domain/`/`application/`.

### Added — issue #3 (original ingestion utilities)
- Real sample extract from TraceLab (`data/samples/tracelab_example_session.jsonl`), 19 rows, sanitized public example pulled from `uw-syfi/TraceLab` (`example_sessions/sanitized/round_trace.jsonl`).
- Project scaffolding: `pyproject.toml` (pytest config, `pythonpath = ["src"]`), `requirements.txt` (polars, pytest), `.gitignore`.

### Fixed
- `profile_fields` initially cast example values to `Utf8` directly through Polars, which crashed on nested columns (e.g. `timing_events`, a list of structs) with `InvalidOperationError: cannot cast List type ... to String`. Fixed by converting example values to Python objects first (`Series.to_list()`) and stringifying them with `str()`, which works for any column type, nested or not. (Superseded by the recursive flattening added in #48, which handles nested columns field-by-field rather than stringifying the whole value.)

## Status

- 60/60 tests passing (`pytest`), `ruff`/`mypy --strict`/`import-linter` clean on the files this issue touches.
- `infrastructure/files/` now implements the `FileReader`-adjacent scanning helpers and the `FileProfiler` port, and is wired into `application/use_cases/profile_file.py`. Not yet wired into an HTTP route or a persisted `file_upload` (that's Lot E / #47 / #50).
