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

# ---------------------------------------------------------------------------
# Chart indicators — documented, but not part of the headline four
# ---------------------------------------------------------------------------

CACHE_READ_TOKENS = MetricDefinition(
    key="cache_read_tokens",
    label="Tokens lus depuis le cache",
    unit="tokens",
    formula="SUM(model_call.cache_read_tokens)",
    scope="Appels modèles des sources qui fournissent des métriques de cache.",
    missing_policy=(
        "Une source qui ne fournit pas de données de cache remonte null avec "
        "une couverture de 0.0, jamais 0. Les deux ne veulent pas dire la même "
        "chose : 0 signifie « rien n'a été lu depuis le cache », null signifie "
        "« cette source ne le dit pas »."
    ),
    # Certaines sources ne publient aucune donnée de cache. Un total toutes
    # sources confondues mesurerait donc « les sources qui la fournissent »,
    # pas « toutes les sources » — d'où l'avertissement obligatoire.
    comparability="per_source_only",
)

IMPORT_REJECTION_RATIO = MetricDefinition(
    key="import_rejection_ratio",
    label="Taux de rejet à l'import",
    unit="ratio",
    formula="import_run.records_rejected / NULLIF(import_run.records_read, 0)",
    scope="Un import donné, tel qu'enregistré à la fin de son exécution.",
    missing_policy=(
        "Un import n'ayant lu aucun enregistrement renvoie null, pas 0 : un "
        "taux de rejet n'a pas de sens sur un dénominateur vide."
    ),
    comparability="cross_source",
)


# The four headline indicators of GET /api/v1/metrics/overview.
OVERVIEW_METRICS: tuple[MetricDefinition, ...] = (
    SESSION_COUNT,
    AVG_TOKENS_PER_SESSION,
    AVG_SESSION_DURATION_MS,
    TOOL_ERROR_RATE,
)

# Everything GET /api/v1/metrics/definitions publishes: the headline four plus
# the figures the charts expose. Every number the API returns must be findable
# here — that is the "definition accessible" requirement.
ALL_METRICS: tuple[MetricDefinition, ...] = (
    *OVERVIEW_METRICS,
    CACHE_READ_TOKENS,
    IMPORT_REJECTION_RATIO,
)

_REGISTRY: dict[str, MetricDefinition] = {m.key: m for m in ALL_METRICS}


def get(key: str) -> MetricDefinition:
    """Retrieve a MetricDefinition by key. Raises KeyError if not found."""
    return _REGISTRY[key]


def all_definitions() -> tuple[MetricDefinition, ...]:
    """Every published definition, in display order."""
    return ALL_METRICS


def overview_definitions() -> tuple[MetricDefinition, ...]:
    """Only the four indicators of the overview endpoint.

    Kept separate from `all_definitions()` so documenting a chart figure never
    silently adds a fifth tile to the dashboard header.
    """
    return OVERVIEW_METRICS
