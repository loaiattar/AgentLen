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

### Added — issue #43 (transformation engine operators)
- `domain/services/transformation_engine.py`: implemented 5 of the 6 operators that were placeholders — `parse_datetime` (iso8601/unix_seconds/unix_millis/strptime, always UTC-aware, never falls back to a default date on failure), `coalesce` and `concat` (both resolve their own `sources` list of paths against the raw record, per `MAPPING_CONTRACT.md` §3), `hash` (sha256 over canonicalized `sources` values, same approach as `Deduplicator.content_hash` — stable regardless of key order), `regex_extract` (uses `google-re2`, not the stdlib `re`, so a pathological pattern like `(a+)+$` can't cause catastrophic backtracking — the timeout guarantee is structural).
- `domain/errors.py`: added `OperatorFailedError` (carries a stable `ImportIssue` code, e.g. `DATETIME_PARSE_FAILED`) and `InvalidOperatorParamError` (e.g. an uncompilable regex).
- `_apply_operator` now also receives the raw row, needed by `coalesce`/`concat`/`hash` since they read several source fields, not just the field's own pre-extracted value.
- Added `google-re2` as a project dependency + a mypy override (it ships no type stubs).
- Tests: one nominal + one failure case per operator, in `tests/unit/domain/test_transformation_engine_operators.py`.
- **Rebased onto `develop`**, which had tightened `import-linter`'s contract in the meantime to forbid `re2` in `domain/` (previously not listed) — `regex_extract`'s original direct `import re2` now failed CI. Fixed by extracting a `RegexExtractor` Protocol in `transformation_engine.py` and moving the concrete re2 implementation to `infrastructure/text/re2_regex_extractor.py`, injected into the engine's constructor. Using `regex_extract` without one configured now fails clearly (`REGEX_EXTRACTOR_NOT_CONFIGURED`) instead of an import error.

**Not done — `split_rows` is blocked on a design question, raised with the team rather than guessed:** every other operator is `value -> value`, but `split_rows` is described as "one source record produces N target rows" at the *field* level, which doesn't fit that contract (the engine already has an equivalent mechanism at the *entity* level via `entity_mapping.iterate`). Needs clarification on how a field-level operator is meant to fan out into multiple rows before implementing it.

### Added — issue #3 (original ingestion utilities)
- Real sample extract from TraceLab (`data/samples/tracelab_example_session.jsonl`), 19 rows, sanitized public example pulled from `uw-syfi/TraceLab` (`example_sessions/sanitized/round_trace.jsonl`).
- JSONL reader (`src/agentlen/infrastructure/files/polars_reader.py`): `read_jsonl(path)` loads a JSONL file into a Polars DataFrame.
- Field profiler (`src/agentlen/infrastructure/files/polars_profiler.py`): `profile_fields(df)` returns, per column, the detected dtype, the null rate, and a few example values.
- Unit tests (`tests/unit/test_polars_reader.py`, `tests/unit/test_polars_profiler.py`) covering the reader and the profiler against the real sample extract.
- Project scaffolding: `pyproject.toml` (pytest config, `pythonpath = ["src"]`), `requirements.txt` (polars, pytest), `.gitignore`.

### Fixed
- `profile_fields` initially cast example values to `Utf8` directly through Polars, which crashed on nested columns (e.g. `timing_events`, a list of structs) with `InvalidOperationError: cannot cast List type ... to String`. Fixed by converting example values to Python objects first (`Series.to_list()`) and stringifying them with `str()`, which works for any column type, nested or not.

## Status

- 142/142 tests passing (`pytest`), `ruff`/`mypy --strict`/`import-linter` clean, rebased onto latest `develop`.
- 5 of 6 transformation-engine operators done; `split_rows` pending a team decision (see above) — opening the PR now for the 5 that are done rather than waiting.
