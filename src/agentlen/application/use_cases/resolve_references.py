from __future__ import annotations

from collections.abc import Iterable

from agentlen.application.ports.repositories import ReferentialRepository
from agentlen.domain.model.reference import ReferenceRequest


class ResolveReferences:
    """Upserts ReferenceRequests via the ReferentialRepository port.

    One instance is meant to live for the duration of a single import run:
    its cache means two records both declaring the tool 'Bash' only hit the
    repository once, and both resolve to the same id.
    """

    def __init__(self, repository: ReferentialRepository) -> None:
        self._repository = repository
        self._cache: dict[tuple[str, str], int] = {}

    async def execute(self, requests: Iterable[ReferenceRequest]) -> dict[tuple[str, str], int]:
        resolved: dict[tuple[str, str], int] = {}
        for request in requests:
            key = (request.kind, request.name)
            if key not in self._cache:
                self._cache[key] = await self._repository.resolve(request.kind, request.name)
            resolved[key] = self._cache[key]
        return resolved
