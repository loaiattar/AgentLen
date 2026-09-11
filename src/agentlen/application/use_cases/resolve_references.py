from __future__ import annotations

from collections.abc import Iterable

from agentlen.application.ports.repositories import ReferentialRepository
from agentlen.domain.model.reference import ReferenceRequest

CacheKey = tuple[str, str, tuple[tuple[str, str], ...]]


class ResolveReferences:
    """Upserts ReferenceRequests via the ReferentialRepository port.

    One instance is meant to live for the duration of a single import run:
    its cache means two records both declaring the tool 'Bash' only hit the
    repository once, and both resolve to the same id. `context` is part of
    the cache key too — a model named 'x' under provider 'a' and one named
    'x' under provider 'b' are different rows and must not share a cache
    entry, even though `name` alone collides.
    """

    def __init__(self, repository: ReferentialRepository) -> None:
        self._repository = repository
        self._cache: dict[CacheKey, int] = {}

    async def execute(self, requests: Iterable[ReferenceRequest]) -> dict[CacheKey, int]:
        resolved: dict[CacheKey, int] = {}
        for request in requests:
            key: CacheKey = (request.kind, request.name, request.context)
            if key not in self._cache:
                context = dict(request.context) if request.context else None
                self._cache[key] = await self._repository.resolve(
                    request.kind, request.name, context=context
                )
            resolved[key] = self._cache[key]
        return resolved
