"""The migration head is read from disk once per process (issue #162)."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from alembic.script import ScriptDirectory

from agentlen.infrastructure.persistence.health import head_revision


@pytest.fixture(autouse=True)
def fresh_cache() -> Iterator[None]:
    head_revision.cache_clear()
    yield
    head_revision.cache_clear()


def test_head_revision_parses_the_scripts_only_once(monkeypatch: pytest.MonkeyPatch) -> None:
    loads: list[object] = []

    class Scripts:
        def get_current_head(self) -> str:
            return "0042"

    def from_config(config: Any) -> Scripts:
        loads.append(config)
        return Scripts()

    monkeypatch.setattr(ScriptDirectory, "from_config", from_config)

    assert [head_revision() for _ in range(3)] == ["0042"] * 3
    assert len(loads) == 1


def test_unreadable_scripts_give_none_rather_than_raising(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def broken(config: Any) -> None:
        raise OSError("alembic/ is missing")

    monkeypatch.setattr(ScriptDirectory, "from_config", broken)

    assert head_revision() is None
