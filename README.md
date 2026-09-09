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

### Added — issue #50 (`/data-sources` router)
- `interfaces/http/routers/data_sources.py`: `GET /api/v1/data-sources` (list) and `POST /api/v1/data-sources` (create, 201) — the first half of #50, before `/files` (the upload half).
- `interfaces/http/schemas/data_sources.py`: `DataSourceOut`/`DataSourceCreateIn` wire shapes.
- `application/ports/repositories.py`: extended `DataSourceRepository` with `get_by_id`, `list`, and additive `create(...)` kwargs (description, url, license, dataset_version, retrieved_at).
- `infrastructure/persistence/repositories/sql.py` and `tests/fakes/repositories.py`: matching implementations, kept in sync via the contract test suite.
- `interfaces/http/dependencies.py`: wired `get_unit_of_work` for real (`SqlAlchemyUnitOfWork`), replacing its `_not_wired` placeholder — repository, session and mapping ports go through it now.
- Fixed a latent `mypy --strict` gap surfaced by wiring the UoW for real: `SqlAlchemyUnitOfWork`'s repository attributes were untyped at the class level, so mypy inferred their concrete adapter types instead of the `UnitOfWork` protocol's port types — invariant under Protocol structural checks, so every repository attribute silently failed the check. Fixed by declaring them at the class level with the port types.
- Fixed `tests/e2e/conftest.py`'s `client` fixture: its `ASGITransport` was missing `raise_app_exceptions=False`, so a genuinely unhandled exception (simulated via an unreachable database) propagated through httpx instead of returning the app's own clean `500 {"error": {"code": "INTERNAL_ERROR"}}` response — the one other e2e fixture that exercises this path (`raising_client` in `test_error_envelope.py`) already had the flag set.
- `tests/e2e/test_data_sources_routes.py`: full route coverage (empty list, create + full record, appears in list, duplicate slug -> 409, missing field -> 422, database down -> 500 envelope).

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
### Added — issue #46 (RecordNormalizer + referentials resolution)
- `domain/model/reference.py`: `ReferenceRequest` (kind + name), declarative only — the domain never does I/O.
- `domain/services/record_normalizer.py`: `RecordNormalizer.normalize(mapping, raw, data_source_id=..., line_number=...)` assembles `TransformationEngine`'s flat field values into linked `Session`/`ModelCall`/`ToolCall` domain entities — session built first, children linked to it via the generated UUID, `sequence_index` deduced from an explicit field or the deterministic iteration order, `MAPPING_MISSING_NATURAL_KEY`/`PARENT_SESSION_MISSING` issues on failure, and `ReferenceRequest`s collected for every agent/provider/model/tool name encountered.
- `application/ports/repositories.py`: added `ReferentialRepository` (upsert-by-name for provider/model/agent/tool/repository — didn't exist yet).
- `application/use_cases/resolve_references.py`: `ResolveReferences` upserts `ReferenceRequest`s through that port, with a per-instance cache so the same name declared by several records only hits the repository once per import run.
- **Fixed a gap in `TransformationEngine` (Lot A, already merged)**: a `required` field that was simply absent from the source (no operator exception) rejected its entity with **zero** `ImportIssue` — silently, which contradicts the project's "an explained rejection" principle. Now emits `MISSING_REQUIRED_FIELD`.
- Tests: entity assembly/linking/sequence_index/natural-key/rejection cascade in `tests/unit/domain/test_record_normalizer.py`; caching/reuse behaviour (with an in-memory fake repository, no DB needed) in `tests/unit/application/use_cases/test_resolve_references.py`.

### Fixed — review findings on PR #67 (loaiattar)
- **`sequence_index` broke reimport idempotence** — it was derived from a row's rank among *survivors*, not its position in the source. Rejecting a middle row shifted every later row's key, so fixing that row and reimporting inserted the shifted rows a second time under a new key (ARCHITECTURE.md §11's idempotence acceptance test). `TransformationEngine.apply()` now returns each result's `source_index` (position before any rejection); `RecordNormalizer` uses that instead of its own loop rank.
- **Three ways a single bad row could crash the whole import** instead of producing a rejection: `data["external_id"]`/`data["tool_name"]` indexed directly even though `natural_key` doesn't guarantee their presence (→ `KeyError`), and an out-of-enum `status`/`outcome` (e.g. a source writing `"success"` instead of `"ok"`) raised straight out of the entity's `__post_init__` (→ `ValueError`). Entity construction is now wrapped in `try/except`, converting both into an `ENTITY_CONSTRUCTION_FAILED` `ImportIssue` — the row is skipped, the rest of the import continues.
- **Multiple session rows from one record were silently dropped to the first** — nothing in `EntityMapping`/`MappingValidator` actually forbids `iterate` on the session entity. Now emits a `MULTIPLE_SESSIONS_IGNORED` warning for the discarded ones instead of losing them with zero trace.
- **`ReferentialRepository.resolve(kind, name)` couldn't satisfy the schema** — `model` is unique on `(provider_id, name)`, not `name` alone (`DATA_MODEL.md` §4). `ReferenceRequest`/`ReferentialRepository.resolve` gained a `context` field/param for composite keys, decided now rather than surfacing as a `NOT NULL` violation deep in #45's adapter. `RecordNormalizer` now emits the provider as context on every model reference; `ResolveReferences`' cache key includes context, so two providers publishing a same-named model no longer collapse into one row. `repository` reference requests are still not emitted — `Session` has no repository/host/owner field yet, a domain-model gap flagged for a follow-up, not papered over here.
- `sequence_index` is now cast to `int` during construction (same try/except catches a bad cast too).
- `PARENT_SESSION_MISSING` is now emitted once per affected entity type (`model_call`, `tool_call`), not once per child — was inflating `ImportReport.issues` 8x on a rejected session with 8 children.
- 12 new tests added directly reproducing each scenario above (reimport-after-fix, missing-optional-field crash, invalid status/outcome, multiple sessions, model/provider context, cache non-collapse, int cast).

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
- Project scaffolding: `pyproject.toml` (pytest config, `pythonpath = ["src"]`), `requirements.txt` (polars, pytest), `.gitignore`.

### Fixed
- `profile_fields` initially cast example values to `Utf8` directly through Polars, which crashed on nested columns (e.g. `timing_events`, a list of structs) with `InvalidOperationError: cannot cast List type ... to String`. Fixed by converting example values to Python objects first (`Series.to_list()`) and stringifying them with `str()`, which works for any column type, nested or not. (Superseded by the recursive flattening added in #48, which handles nested columns field-by-field rather than stringifying the whole value.)

## Status

- 158/158 tests passing (`pytest`), `ruff`/`mypy --strict`/`import-linter` clean on the files this issue touches.
- `infrastructure/files/` now implements the `FileReader`-adjacent scanning helpers and the `FileProfiler` port, and is wired into `application/use_cases/profile_file.py`. Not yet wired into an HTTP route or a persisted `file_upload` (that's Lot E / #47 / #50).
- All findings from loaiattar's review on PR #66 addressed (see changelog above).
- 61/61 tests passing (`pytest`), `ruff`/`mypy --strict`/`import-linter` clean on the files issue #46 touches. Rebased onto latest `develop`.
- **Known gap, not fixed here**: `mapping_validator._SCHEMA` accepts `session.repository_url`, `model_call.reasoning_tokens` and `tool_call.arguments`, none of which `RecordNormalizer` reads — a validated mapping can silently lose those fields. Needs the domain entities extended before it can be fixed; flagged for the team rather than worked around.
- 142/142 tests passing (`pytest`), `ruff`/`mypy --strict`/`import-linter` clean, rebased onto latest `develop`.
- 5 of 6 transformation-engine operators done; `split_rows` pending a team decision (see above) — opening the PR now for the 5 that are done rather than waiting.
