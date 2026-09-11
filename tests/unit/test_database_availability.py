"""The rule that decides whether database tests run or skip.

It used to probe Docker alone, so a job handing the suite a database through
TEST_DATABASE_URL, but without Docker, skipped every database test in silence.
"""

from __future__ import annotations

import pytest

from tests.integration.conftest import database_available

URL = "postgresql+asyncpg://agentlen:agentlen@db:5432/agentlen"


def _docker_must_not_be_probed() -> bool:
    raise AssertionError("Docker was probed although TEST_DATABASE_URL names a database")


def test_a_preset_database_url_is_enough_without_docker() -> None:
    assert database_available({"TEST_DATABASE_URL": URL}, _docker_must_not_be_probed) is True


def test_docker_alone_is_enough() -> None:
    assert database_available({}, lambda: True) is True


@pytest.mark.parametrize("env", [{}, {"TEST_DATABASE_URL": ""}])
def test_neither_a_database_url_nor_docker_means_unavailable(env: dict[str, str]) -> None:
    assert database_available(env, lambda: False) is False
