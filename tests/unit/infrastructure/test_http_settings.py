"""HTTP settings: API_KEY and comma-separated ALLOWED_ORIGINS."""

from __future__ import annotations

from agentlen.infrastructure.config.settings import Settings, load_settings


def test_allowed_origins_defaults_to_the_vite_dev_server() -> None:
    settings = Settings(api_key="k")
    assert settings.allowed_origins == ["http://localhost:5173"]


def test_allowed_origins_splits_on_commas(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("ALLOWED_ORIGINS", "http://localhost:5173, https://agentscope.example")
    monkeypatch.setenv("API_KEY", "from-env")
    settings = load_settings()
    assert settings.allowed_origins == [
        "http://localhost:5173",
        "https://agentscope.example",
    ]
    assert settings.api_key == "from-env"


def test_api_key_is_omitted_from_repr() -> None:
    settings = Settings(api_key="must-not-appear", origins="http://localhost:5173")
    assert "must-not-appear" not in repr(settings)
