"""Application configuration, 12-factor.

**No model identifier appears anywhere in this file** — not even as an example
in a comment, which the CI guard checks for and rightly rejected on the first
attempt. `AI_MODEL` has no default: hardcoding one would mean the
"interchangeable by configuration" requirement holds only until someone forgets
to set the variable. Not choosing for the operator is the point.
"""

from __future__ import annotations

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AISettings(BaseSettings):
    """Everything needed to reach a model provider."""

    model_config = SettingsConfigDict(env_prefix="AI_", extra="ignore")

    provider: str = Field(
        default="fake",
        description=(
            "anthropic | openai | openai_compatible | fake. "
            "Defaults to the test double so nothing can accidentally spend "
            "credits or require a key."
        ),
    )
    model: str = Field(
        default="",
        description="Provider's model identifier. Deliberately without a default.",
    )
    base_url: str = Field(
        default="",
        description=(
            "Override the provider's endpoint. Required by openai_compatible, "
            "which is how Groq, Mistral, OpenRouter, Ollama and the rest are reached."
        ),
    )
    timeout_seconds: float = Field(default=60.0, gt=0)
    max_output_tokens: int = Field(default=8000, ge=1)
    max_iterations: int = Field(
        default=10,
        ge=1,
        description="Tool-loop bound for the initial analysis (AI_MAX_ITERATIONS).",
    )
    max_conversation_turns: int = Field(
        default=10,
        ge=1,
        description=(
            "How many stored turns are replayed into a refinement prompt "
            "(AI_MAX_CONVERSATION_TURNS). This used to bound the refinement "
            "tool loop as well; that bound is now max_refinement_iterations, so "
            "an operator who lowered this one to cap spend must set that one too."
        ),
    )
    max_refinement_iterations: int = Field(
        default=10,
        ge=1,
        description="Tool-loop bound for one refinement (AI_MAX_REFINEMENT_ITERATIONS).",
    )


class ProviderKeys(BaseSettings):
    """API keys, read separately so they are never mixed into a descriptor.

    Nothing in this class is ever logged, echoed in an API response, or put in
    a `MappingProposal`.
    """

    model_config = SettingsConfigDict(extra="ignore")

    anthropic_api_key: str = ""
    openai_api_key: str = ""
    # Anything OpenAI-shaped that is neither: Groq, Mistral, OpenRouter…
    ai_api_key: str = ""


class Settings(BaseSettings):
    """HTTP process configuration: API key auth and CORS.

    `api_key` is `repr=False` so it cannot leak through logs that stringify
    the settings object. Compare it in constant time; never interpolate it
    into a log line.
    """

    model_config = SettingsConfigDict(extra="ignore", populate_by_name=True)

    api_key: str = Field(default="", repr=False)
    origins: str = Field(
        default="http://localhost:5173",
        validation_alias=AliasChoices("ALLOWED_ORIGINS", "allowed_origins", "origins"),
    )

    @property
    def allowed_origins(self) -> list[str]:
        """Comma-separated `ALLOWED_ORIGINS` as a list of origins."""
        return [part.strip() for part in self.origins.split(",") if part.strip()]


def load_ai_settings() -> AISettings:
    return AISettings()


def load_provider_keys() -> ProviderKeys:
    return ProviderKeys()


def load_settings() -> Settings:
    return Settings()
