"""Every path PolarsFileProfiler reports resolves through TransformationEngine (#121):
the profile is what the agent copies into a mapping."""

import json
from pathlib import Path
from uuid import uuid4

import pytest

from agentlen.domain.model.mapping import EntityMapping, FieldRule, Mapping
from agentlen.domain.services.transformation_engine import TransformationEngine
from agentlen.infrastructure.ai.sanitizer import sanitize_value
from agentlen.infrastructure.files.polars_profiler import PolarsFileProfiler

SAMPLE_FILE = Path(__file__).parents[2] / "data" / "samples" / "tracelab_example_session.jsonl"

pytestmark = pytest.mark.asyncio


async def _assert_every_profiled_path_resolves(file: Path) -> None:
    profile = await PolarsFileProfiler().profile(str(file))
    # One entity per list: `$.tools[].tool_name` is read under `iterate: $.tools[]`,
    # with its source written exactly as profiled.
    groups: dict[str | None, list[str]] = {}
    for field in profile.fields:
        iterate = field.path[: field.path.rindex("[]") + 2] if "[]" in field.path else None
        groups.setdefault(iterate, []).append(field.path)
    entities = [
        EntityMapping(
            target="session",
            natural_key=["unused"],
            iterate=iterate,
            fields=[FieldRule(target=path, source=path) for path in paths],
        )
        for iterate, paths in groups.items()
    ]
    mapping = Mapping(uuid4(), name="profiled", version=1, source_format="jsonl", entities=entities)

    resolved: dict[str, list[str]] = {field.path: [] for field in profile.fields}
    for line in file.read_text(encoding="utf-8").splitlines():
        results, issues = TransformationEngine().apply(mapping, json.loads(line))
        assert issues == []
        for result in results:
            for path, value in result["data"].items():
                resolved[path].append(sanitize_value(str(value)))

    for field in profile.fields:
        assert bool(resolved[field.path]) == (field.types != ("null",)), field.path
        assert set(field.examples) <= set(resolved[field.path]), field.path


async def test_every_path_profiled_on_the_sample_resolves_on_the_sample():
    await _assert_every_profiled_path_resolves(SAMPLE_FILE)


async def test_quoted_names_and_scalar_lists_resolve_as_profiled(tmp_path: Path):
    records = [
        {
            "a.b": 1,
            'say "hi"': "x",
            "back\\slash": "y",
            "meta": {"my-key": {"inner.leaf": 2}},
            "items": [{"x.y": 3}, {"x.y": 4}],
            "tags": ["red", "blue"],
        },
        {"a.b": 5, 'say "hi"': "z", "back\\slash": None, "meta": None, "items": [], "tags": []},
    ]
    file = tmp_path / "odd_names.jsonl"
    file.write_text("\n".join(json.dumps(record) for record in records), encoding="utf-8")

    paths = {field.path for field in (await PolarsFileProfiler().profile(str(file))).fields}
    assert {'$["a.b"]', '$["say \\"hi\\""]', '$.items[]["x.y"]', "$.tags[]"} <= paths

    await _assert_every_profiled_path_resolves(file)
