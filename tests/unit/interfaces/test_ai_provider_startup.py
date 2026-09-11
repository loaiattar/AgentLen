"""The API says at startup when no AI provider can answer (#195)."""

from __future__ import annotations

import logging

import pytest

from agentlen.infrastructure.config.settings import Settings
from agentlen.interfaces.http.app import create_app


async def _start_and_stop() -> None:
    app = create_app(settings=Settings(api_key="k"))
    async with app.router.lifespan_context(app):
        pass


async def test_startup_names_the_variable_to_set_when_no_provider_is_chosen(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setenv("AI_PROVIDER", "")
    caplog.set_level(logging.WARNING, logger="agentlen.api")

    await _start_and_stop()

    assert "Aucun fournisseur IA utilisable" in caplog.text
    assert "renseigner AI_PROVIDER" in caplog.text


async def test_startup_is_silent_when_the_provider_can_answer(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setenv("AI_PROVIDER", "openai_compatible")
    monkeypatch.setenv("AI_MODEL", "m")
    monkeypatch.setenv("AI_BASE_URL", "http://localhost:11434/v1")
    caplog.set_level(logging.WARNING, logger="agentlen.api")

    await _start_and_stop()

    assert "fournisseur IA" not in caplog.text


async def test_an_invalid_ai_setting_does_not_stop_the_api(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Everything but the assistant works without AI, as before this check."""
    monkeypatch.setenv("AI_TIMEOUT_SECONDS", "not-a-number-7f3a")
    caplog.set_level(logging.WARNING, logger="agentlen.api")

    await _start_and_stop()

    assert "Configuration IA invalide (ValidationError)" in caplog.text
    assert "not-a-number-7f3a" not in caplog.text
