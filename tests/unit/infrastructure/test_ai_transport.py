"""Retries, timeouts, and the guarantee that no key reaches a log."""

from __future__ import annotations

import logging
from typing import Any

import httpx
import pytest

from agentlen.application.errors import AnalyzerError
from agentlen.infrastructure.ai.base import MAX_ATTEMPTS
from agentlen.infrastructure.ai.openai_adapter import OpenAIAnalyzer
from agentlen.infrastructure.config.settings import AISettings

# Fausse clé, plantée exprès : les tests vérifient qu'elle ne ressort ni
# dans les logs ni dans les erreurs.
SECRET = "sk-proj-SUPERSECRETVALUE123456"  # noqa: S105


def analyzer() -> OpenAIAnalyzer:
    return OpenAIAnalyzer(
        AISettings(provider="openai", model="m", base_url="https://api.example/v1"), SECRET
    )


class Transport(httpx.AsyncBaseTransport):
    """Serves a scripted sequence of responses, counting the attempts."""

    def __init__(self, *statuses: int) -> None:
        self.statuses = list(statuses)
        self.attempts = 0

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        self.attempts += 1
        status = self.statuses.pop(0) if self.statuses else 200
        if status == 200:
            return httpx.Response(200, json={"choices": [{"message": {"content": "{}"}}]})
        return httpx.Response(status, json={"error": "nope"})


@pytest.fixture
def patched(monkeypatch: pytest.MonkeyPatch):  # type: ignore[no-untyped-def]
    """Swap the transport and remove the backoff sleep, so the retry policy is
    tested without the test paying for it."""

    def install(transport: Transport) -> Transport:
        original = httpx.AsyncClient.__init__

        def patched_init(self: Any, *args: Any, **kwargs: Any) -> None:
            kwargs["transport"] = transport
            original(self, *args, **kwargs)

        monkeypatch.setattr(httpx.AsyncClient, "__init__", patched_init)

        async def no_sleep(_: float) -> None:
            return None

        monkeypatch.setattr("agentlen.infrastructure.ai.base.asyncio.sleep", no_sleep)
        return transport

    return install


async def test_a_rate_limit_is_retried(patched) -> None:  # type: ignore[no-untyped-def]
    """429 is the provider asking us to wait, not a permanent failure."""
    transport = patched(Transport(429, 429, 200))

    await analyzer()._post({"x": 1})

    assert transport.attempts == 3


async def test_a_server_error_is_retried(patched) -> None:  # type: ignore[no-untyped-def]
    transport = patched(Transport(503, 200))
    await analyzer()._post({"x": 1})
    assert transport.attempts == 2


async def test_a_bad_request_is_not_retried(patched) -> None:  # type: ignore[no-untyped-def]
    """Retrying a malformed request or a bad key just wastes time and money."""
    transport = patched(Transport(400))

    with pytest.raises(AnalyzerError):
        await analyzer()._post({"x": 1})

    assert transport.attempts == 1


async def test_an_invalid_key_fails_immediately(patched) -> None:  # type: ignore[no-untyped-def]
    transport = patched(Transport(401))
    with pytest.raises(AnalyzerError):
        await analyzer()._post({"x": 1})
    assert transport.attempts == 1


async def test_retries_are_bounded(patched) -> None:  # type: ignore[no-untyped-def]
    transport = patched(Transport(*([503] * 20)))

    with pytest.raises(AnalyzerError) as exc:
        await analyzer()._post({"x": 1})

    assert transport.attempts == MAX_ATTEMPTS
    assert "injoignable" in str(exc.value)


async def test_no_key_reaches_the_logs_or_the_error(
    patched, caplog: pytest.LogCaptureFixture
) -> None:  # type: ignore[no-untyped-def]
    """Connection errors habitually carry the URL, and a self-hosted URL can
    carry the credential."""
    patched(Transport(*([503] * 20)))

    with caplog.at_level(logging.DEBUG), pytest.raises(AnalyzerError) as exc:
        await analyzer()._post({"x": 1})

    assert SECRET not in caplog.text
    assert SECRET not in str(exc.value)
    assert SECRET not in str(exc.value.details)


async def test_a_network_failure_is_reported_by_class_not_message(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    class Failing(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError(f"failed connecting with key {SECRET}")

    original = httpx.AsyncClient.__init__

    def patched_init(self: Any, *args: Any, **kwargs: Any) -> None:
        kwargs["transport"] = Failing()
        original(self, *args, **kwargs)

    monkeypatch.setattr(httpx.AsyncClient, "__init__", patched_init)

    async def no_sleep(_: float) -> None:
        return None

    monkeypatch.setattr("agentlen.infrastructure.ai.base.asyncio.sleep", no_sleep)

    with caplog.at_level(logging.DEBUG), pytest.raises(AnalyzerError) as exc:
        await analyzer()._post({"x": 1})

    assert SECRET not in caplog.text
    assert SECRET not in str(exc.value)
    assert "ConnectError" in str(exc.value.details)
