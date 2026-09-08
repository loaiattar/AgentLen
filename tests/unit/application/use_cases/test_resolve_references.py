"""ResolveReferences must run without a database — a FakeReferentialRepository
stands in for the SQLAlchemy one (not built yet, that's Lot B)."""

from agentlen.application.use_cases.resolve_references import ResolveReferences
from agentlen.domain.model.reference import ReferenceRequest

EXPECTED_UNIQUE_REQUEST_COUNT = 2


class FakeReferentialRepository:
    """In-memory double: counts calls so tests can prove the cache works."""

    def __init__(self) -> None:
        self.call_count = 0
        self._next_id = 1
        self._ids: dict[tuple[str, str], int] = {}

    async def resolve(self, kind: str, name: str) -> int:
        self.call_count += 1
        key = (kind, name)
        if key not in self._ids:
            self._ids[key] = self._next_id
            self._next_id += 1
        return self._ids[key]


async def test_resolves_each_request_to_an_id():
    repository = FakeReferentialRepository()
    use_case = ResolveReferences(repository)

    resolved = await use_case.execute(
        [
            ReferenceRequest(kind="tool", name="Bash"),
            ReferenceRequest(kind="agent", name="claude-code"),
        ]
    )

    assert resolved[("tool", "Bash")] != resolved[("agent", "claude-code")]
    assert repository.call_count == EXPECTED_UNIQUE_REQUEST_COUNT


async def test_two_sources_declaring_the_same_tool_reuse_the_same_row():
    # Simulates two different raw records, both mentioning the tool 'Bash',
    # resolved through the same ResolveReferences instance (one per import run).
    repository = FakeReferentialRepository()
    use_case = ResolveReferences(repository)

    first_record = await use_case.execute([ReferenceRequest(kind="tool", name="Bash")])
    second_record = await use_case.execute([ReferenceRequest(kind="tool", name="Bash")])

    assert first_record[("tool", "Bash")] == second_record[("tool", "Bash")]
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
