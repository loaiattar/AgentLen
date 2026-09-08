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

### Fixed — review findings on PR #66 (loaiattar)
- **`examples` reached the mapping agent's prompt unsanitized** — a raw API key or home path in a source file leaked straight through `file_profile.fields[].examples` (MAPPING_CONTRACT.md §5), even though `sample_records` was already redacted. Now goes through `sanitize_value` (the `SampleSanitizer` from #44), same as everything else that reaches a provider.
- **A field appearing after row 100 silently vanished from the profile** — `scan_ndjson`/`scan_csv` only infer the schema from their first `infer_schema_length` rows (Polars default: 100), independently of `sample_size` (default: 500). `infer_schema_length` now follows `sample_size` (floored at 100).
- **`distinct_ratio` could never reach `1.0` on a nullable column** — it divided unique non-null values by the *total* row count instead of the non-null count, capping a fully-unique-but-nullable key below the 1.0 threshold `MAPPING_CONTRACT.md` §5 uses as the natural-key signal.
- **JSONPath collisions on dotted field names** — a raw field literally named `"a.b"` rendered identically to a nested field `a.b` from a struct (`$.a.b` either way). Segments are now escaped to `$["a.b"]` when the raw name isn't a plain identifier.
- **`profile()` blocked the event loop** — both `collect()` calls were synchronous inside an `async def`; on `POST /files/{id}/profile` that would stall every other concurrent FastAPI request for the duration of the profile. Now runs via `asyncio.to_thread`.
- `_type_name`'s fallback (`str(dtype).lower()`) leaked raw Polars reprs (e.g. `"decimal(precision=38, scale=2)"`) across the port boundary — the exact leak the port exists to prevent. `Decimal`/`Duration` are now named explicitly; anything else reports `"unknown"`. `Decimal` also now gets `min`/`max` like other numeric types.
- `sample_size <= 0` now raises a clear `ValueError` instead of silently profiling nothing (`0`) or leaking a raw Polars `ValueError` (`-1`).
- An empty (0-byte) file now returns a `record_count=0` profile instead of crashing with a raw Polars `ComputeError` during schema inference.
- The cross-format test checked each of jsonl/csv/parquet against fixed values independently — a real divergence between two formats would have passed silently. Added a direct three-way comparison of the `FileProfile`s.

### Added — issue #3 (original ingestion utilities)
- Real sample extract from TraceLab (`data/samples/tracelab_example_session.jsonl`), 19 rows, sanitized public example pulled from `uw-syfi/TraceLab` (`example_sessions/sanitized/round_trace.jsonl`).
- Project scaffolding: `pyproject.toml` (pytest config, `pythonpath = ["src"]`), `requirements.txt` (polars, pytest), `.gitignore`.

### Fixed
- `profile_fields` initially cast example values to `Utf8` directly through Polars, which crashed on nested columns (e.g. `timing_events`, a list of structs) with `InvalidOperationError: cannot cast List type ... to String`. Fixed by converting example values to Python objects first (`Series.to_list()`) and stringifying them with `str()`, which works for any column type, nested or not. (Superseded by the recursive flattening added in #48, which handles nested columns field-by-field rather than stringifying the whole value.)

## Status

- 158/158 tests passing (`pytest`), `ruff`/`mypy --strict`/`import-linter` clean on the files this issue touches.
- `infrastructure/files/` now implements the `FileReader`-adjacent scanning helpers and the `FileProfiler` port, and is wired into `application/use_cases/profile_file.py`. Not yet wired into an HTTP route or a persisted `file_upload` (that's Lot E / #47 / #50).
- All findings from loaiattar's review on PR #66 addressed (see changelog above).
