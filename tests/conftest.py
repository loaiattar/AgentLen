"""Shared HTTP test credentials.

The API key is a fixture value, not a production secret. It is injected into
the environment so `create_app()` without an explicit `settings=` still
protects routes the same way the process does in CI.
"""

from __future__ import annotations

import pytest

TEST_API_KEY = "test-api-key"
AUTH_HEADERS = {"X-API-Key": TEST_API_KEY}


@pytest.fixture(autouse=True)
def configure_http_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("API_KEY", TEST_API_KEY)
    monkeypatch.setenv("ALLOWED_ORIGINS", "http://localhost:5173")
