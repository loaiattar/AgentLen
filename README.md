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

### Added — issue #46 (RecordNormalizer + referentials resolution)
- `domain/model/reference.py`: `ReferenceRequest` (kind + name), declarative only — the domain never does I/O.
- `domain/services/record_normalizer.py`: `RecordNormalizer.normalize(mapping, raw, data_source_id=..., line_number=...)` assembles `TransformationEngine`'s flat field values into linked `Session`/`ModelCall`/`ToolCall` domain entities — session built first, children linked to it via the generated UUID, `sequence_index` deduced from an explicit field or the deterministic iteration order, `MAPPING_MISSING_NATURAL_KEY`/`PARENT_SESSION_MISSING` issues on failure, and `ReferenceRequest`s collected for every agent/provider/model/tool name encountered.
- `application/ports/repositories.py`: added `ReferentialRepository` (upsert-by-name for provider/model/agent/tool/repository — didn't exist yet).
- `application/use_cases/resolve_references.py`: `ResolveReferences` upserts `ReferenceRequest`s through that port, with a per-instance cache so the same name declared by several records only hits the repository once per import run.
- **Fixed a gap in `TransformationEngine` (Lot A, already merged)**: a `required` field that was simply absent from the source (no operator exception) rejected its entity with **zero** `ImportIssue` — silently, which contradicts the project's "an explained rejection" principle. Now emits `MISSING_REQUIRED_FIELD`.
- Tests: entity assembly/linking/sequence_index/natural-key/rejection cascade in `tests/unit/domain/test_record_normalizer.py`; caching/reuse behaviour (with an in-memory fake repository, no DB needed) in `tests/unit/application/use_cases/test_resolve_references.py`.

### Added — issue #43 (transformation engine operators)
See branch `feat/43-transformation-engine-operators` (PR pending — `split_rows` blocked on a design question raised with the team).

### Added — issue #3 (original ingestion utilities)
- Real sample extract from TraceLab (`data/samples/tracelab_example_session.jsonl`), 19 rows, sanitized public example pulled from `uw-syfi/TraceLab` (`example_sessions/sanitized/round_trace.jsonl`).
- JSONL reader (`src/agentlen/infrastructure/files/polars_reader.py`): `read_jsonl(path)` loads a JSONL file into a Polars DataFrame.
- Field profiler (`src/agentlen/infrastructure/files/polars_profiler.py`): `profile_fields(df)` returns, per column, the detected dtype, the null rate, and a few example values.
- Unit tests (`tests/unit/test_polars_reader.py`, `tests/unit/test_polars_profiler.py`) covering the reader and the profiler against the real sample extract.
- Project scaffolding: `pyproject.toml` (pytest config, `pythonpath = ["src"]`), `requirements.txt` (polars, pytest), `.gitignore`.

### Fixed
- `profile_fields` initially cast example values to `Utf8` directly through Polars, which crashed on nested columns (e.g. `timing_events`, a list of structs) with `InvalidOperationError: cannot cast List type ... to String`. Fixed by converting example values to Python objects first (`Series.to_list()`) and stringifying them with `str()`, which works for any column type, nested or not.

## Status

- 49/49 tests passing (`pytest`), `ruff`/`mypy --strict`/`import-linter` clean on the files issue #46 touches.
