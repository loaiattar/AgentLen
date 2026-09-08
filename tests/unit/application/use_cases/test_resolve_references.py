"""ResolveReferences must run without a database — a FakeReferentialRepository
stands in for the SQLAlchemy one (not built yet, that's Lot B)."""

from agentlen.application.use_cases.resolve_references import ResolveReferences
from agentlen.domain.model.reference import ReferenceRequest

EXPECTED_UNIQUE_REQUEST_COUNT = 2


class FakeReferentialRepository:
    """In-memory double: counts calls and records the context it received, so
    tests can prove both the cache and the composite-key link work."""

    def __init__(self) -> None:
        self.call_count = 0
        self.contexts_seen: list[dict[str, str] | None] = []
        self._next_id = 1
        self._ids: dict[tuple[str, str, tuple[tuple[str, str], ...]], int] = {}

    async def resolve(self, kind: str, name: str, *, context: dict[str, str] | None = None) -> int:
        self.call_count += 1
        self.contexts_seen.append(context)
        key = (kind, name, tuple(sorted((context or {}).items())))
        if key not in self._ids:
            self._ids[key] = self._next_id
            self._next_id += 1
        return self._ids[key]


def _key(kind: str, name: str) -> tuple[str, str, tuple]:
    return (kind, name, ())


async def test_resolves_each_request_to_an_id():
    repository = FakeReferentialRepository()
    use_case = ResolveReferences(repository)

    resolved = await use_case.execute(
        [
            ReferenceRequest(kind="tool", name="Bash"),
            ReferenceRequest(kind="agent", name="claude-code"),
        ]
    )

    assert resolved[_key("tool", "Bash")] != resolved[_key("agent", "claude-code")]
    assert repository.call_count == EXPECTED_UNIQUE_REQUEST_COUNT


async def test_two_sources_declaring_the_same_tool_reuse_the_same_row():
    # Simulates two different raw records, both mentioning the tool 'Bash',
    # resolved through the same ResolveReferences instance (one per import run).
    repository = FakeReferentialRepository()
    use_case = ResolveReferences(repository)

    first_record = await use_case.execute([ReferenceRequest(kind="tool", name="Bash")])
    second_record = await use_case.execute([ReferenceRequest(kind="tool", name="Bash")])

    assert first_record[_key("tool", "Bash")] == second_record[_key("tool", "Bash")]
    # The repository itself is only ever hit once per unique (kind, name) —
    # that's the "no round trip per line" requirement from the ticket.
    assert repository.call_count == 1


async def test_duplicate_requests_within_the_same_call_still_hit_the_repository_once():
    repository = FakeReferentialRepository()
    use_case = ResolveReferences(repository)

    await use_case.execute(
        [
            ReferenceRequest(kind="tool", name="Bash"),
            ReferenceRequest(kind="tool", name="Bash"),
            ReferenceRequest(kind="tool", name="Read"),
        ]
    )

    assert repository.call_count == EXPECTED_UNIQUE_REQUEST_COUNT  # Bash once, Read once


async def test_model_context_reaches_the_repository():
    # 'model' is unique on (provider_id, name) — the provider_name context
    # must actually be handed to resolve(), not silently dropped.
    repository = FakeReferentialRepository()
    use_case = ResolveReferences(repository)

    await use_case.execute(
        [
            ReferenceRequest(
                kind="model", name="claude-opus", context=(("provider_name", "anthropic"),)
            )
        ]
    )

    assert repository.contexts_seen == [{"provider_name": "anthropic"}]


async def test_same_model_name_under_different_providers_does_not_collapse():
    # Two providers publishing a model with the same name must resolve to
    # two distinct rows — the cache key must include context, not just name.
    repository = FakeReferentialRepository()
    use_case = ResolveReferences(repository)

    resolved = await use_case.execute(
        [
            ReferenceRequest(kind="model", name="v1", context=(("provider_name", "anthropic"),)),
            ReferenceRequest(kind="model", name="v1", context=(("provider_name", "openai"),)),
        ]
    )

    ids = set(resolved.values())
    assert len(ids) == EXPECTED_UNIQUE_REQUEST_COUNT
    assert repository.call_count == EXPECTED_UNIQUE_REQUEST_COUNT
