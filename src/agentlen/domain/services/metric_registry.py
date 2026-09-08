from __future__ import annotations

from agentlen.domain.model.metrics import MetricDefinition

SESSION_COUNT = MetricDefinition(
    key="session_count",
    label="Nombre total de sessions",
    unit="sessions",
    formula="COUNT(*) FROM session",
    scope="Sessions correspondant aux filtres actifs (source, agent, période).",
    missing_policy="Couverture toujours 1.0 — toute session importée est comptée.",
    comparability="cross_source",
)

AVG_TOKENS_PER_SESSION = MetricDefinition(
    key="avg_tokens_per_session",
    label="Tokens moyens par session",
    unit="tokens",
    formula="AVG( SUM(input_tokens + output_tokens) GROUP BY session )",
    scope="Sessions ayant au moins un appel modèle avec données tokens.",
    missing_policy=(
        "Une session sans aucun token renseigné est exclue du calcul — "
        "elle n'est ni au numérateur ni au dénominateur. "
        "La couverture indique le ratio de sessions avec données tokens. "
        "Une absence n'est jamais comptée comme 0."
    ),
    comparability="cross_source",
)

AVG_SESSION_DURATION_MS = MetricDefinition(
    key="avg_session_duration_ms",
    label="Durée moyenne d'une session",
    unit="ms",
    formula="AVG(session.duration_ms)",
    scope="Sessions avec duration_ms non nulle.",
    missing_policy=(
        "Les sessions sans duration_ms sont exclues du calcul. "
        "Une durée absente n'est jamais comptée comme 0 ms. "
        "La couverture indique le ratio de sessions avec durée connue."
    ),
    comparability="cross_source",
)

TOOL_ERROR_RATE = MetricDefinition(
    key="tool_error_rate",
    label="Taux d'erreur des appels d'outils",
    unit="ratio",
    formula=(
        "COUNT(tool_call WHERE status='error') / COUNT(tool_call WHERE status IN ('ok','error'))"
    ),
    scope="Appels d'outils avec statut connu (ok ou error) dans les sessions filtrées.",
    missing_policy=(
        "Les appels avec status='unknown' sont exclus du dénominateur. "
        "Si aucun appel n'a de statut connu, la valeur est null (pas 0). "
        "La couverture = appels avec statut connu / total des appels."
    ),
    comparability="cross_source",
)

# Ordered list exposed by GET /api/v1/metrics/definitions
ALL_METRICS: tuple[MetricDefinition, ...] = (
    SESSION_COUNT,
    AVG_TOKENS_PER_SESSION,
    AVG_SESSION_DURATION_MS,
    TOOL_ERROR_RATE,
)

_REGISTRY: dict[str, MetricDefinition] = {m.key: m for m in ALL_METRICS}


def get(key: str) -> MetricDefinition:
    """Retrieve a MetricDefinition by key. Raises KeyError if not found."""
    return _REGISTRY[key]


def all_definitions() -> tuple[MetricDefinition, ...]:
    """Return all registered metric definitions in display order."""
    return ALL_METRICS
