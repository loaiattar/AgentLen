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


# ---------------------------------------------------------------------------
# Ce que le fournisseur a dit du refus remonte jusqu'à l'opérateur
# ---------------------------------------------------------------------------


class Refusing(httpx.AsyncBaseTransport):
    """Un fournisseur qui refuse en expliquant pourquoi, comme le fait l'API."""

    def __init__(self, status: int, payload: Any, *, request_id: str | None = None) -> None:
        self.status = status
        self.payload = payload
        self.request_id = request_id

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        headers = {"request-id": self.request_id} if self.request_id else {}
        if isinstance(self.payload, str):
            return httpx.Response(self.status, text=self.payload, headers=headers)
        return httpx.Response(self.status, json=self.payload, headers=headers)


async def test_a_refusal_carries_the_providers_own_explanation(patched) -> None:  # type: ignore[no-untyped-def]
    """Constat de la vérification du 2026-09-10 : un solde épuisé, une clé
    invalide et un modèle inexistant donnaient tous les trois « a répondu
    400 », et le request_id que le support réclame était jeté."""
    patched(
        Refusing(
            400,
            {
                "type": "error",
                "error": {
                    "type": "invalid_request_error",
                    "message": "Your credit balance is too low to access the Anthropic API.",
                },
            },
            request_id="req_011CeuqhRg7cecEQkLZ7uaVk",
        )
    )

    with pytest.raises(AnalyzerError) as exc:
        await analyzer()._post({"x": 1})

    assert "credit balance" in str(exc.value)
    details = exc.value.details or {}
    assert details["status"] == 400
    assert details["request_id"] == "req_011CeuqhRg7cecEQkLZ7uaVk"
    assert details["provider_error_type"] == "invalid_request_error"


async def test_the_providers_message_is_redacted_before_it_travels(patched) -> None:  # type: ignore[no-untyped-def]
    """Un proxy mal réglé renvoie l'en-tête Authorization dans son message
    d'erreur. Ce message part maintenant jusqu'au client HTTP : il passe donc
    par le caviardeur, comme n'importe quelle donnée de trace."""
    patched(Refusing(400, {"error": {"message": f"invalid credentials: {SECRET} rejected"}}))

    with pytest.raises(AnalyzerError) as exc:
        await analyzer()._post({"x": 1})

    assert SECRET not in str(exc.value)
    assert SECRET not in str(exc.value.details)
    assert "rejected" in str(exc.value)


async def test_a_refusal_without_a_json_body_still_names_the_status(patched) -> None:  # type: ignore[no-untyped-def]
    """Une base_url qui pointe sur un proxy renvoie du HTML, pas du JSON."""
    patched(Refusing(400, "<html><body>Bad Gateway</body></html>"))

    with pytest.raises(AnalyzerError) as exc:
        await analyzer()._post({"x": 1})

    assert "400" in str(exc.value)
    assert (exc.value.details or {})["status"] == 400


async def test_a_verbose_provider_message_is_bounded(patched) -> None:  # type: ignore[no-untyped-def]
    """Un hôte openai_compatible arbitraire n'est pas tenu d'être sobre."""
    from agentlen.infrastructure.ai.base import MAX_PROVIDER_MESSAGE

    patched(Refusing(400, {"error": {"message": "z" * 5000}}))

    with pytest.raises(AnalyzerError) as exc:
        await analyzer()._post({"x": 1})

    assert len((exc.value.details or {})["provider_message"]) <= MAX_PROVIDER_MESSAGE


async def test_a_200_without_json_is_an_analyzer_error(patched) -> None:  # type: ignore[no-untyped-def]
    """Constat #99 : une base_url qui vise un proxy renvoie du HTML en 200.
    `response.json()` levait alors json.JSONDecodeError, qui n'est pas une
    AnalyzerError : 500 générique au lieu du 502 voulu."""
    patched(Refusing(200, "<html><body>Welcome to nginx</body></html>"))

    with pytest.raises(AnalyzerError) as exc:
        await analyzer()._post({"x": 1})

    assert "AI_BASE_URL" in str(exc.value)
