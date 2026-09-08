from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ReferenceRequest:
    """A name that needs to be resolved (or created) as a referential row.

    Declarative only: the domain never does I/O. `resolve_references`
    (application layer) is what actually upserts these via the repositories.

    Not every referential is keyed by name alone (DATA_MODEL.md §4):
    `model` is unique on `(provider_id, name)`, `repository` on
    `(host, owner, name)`. `context` carries whatever extra key components
    a kind needs beyond `name` — e.g. `context=(("provider_name", "anthropic"),)`
    for a model — so `ReferentialRepository.resolve` can build the real key
    instead of the request silently losing the link, or two homonymous
    entries from different parents merging into one row.
    """

    kind: str  # 'provider' | 'model' | 'agent' | 'tool' | 'repository'
    name: str
    context: tuple[tuple[str, str], ...] = field(default_factory=tuple)

    VALID_KINDS = frozenset({"provider", "model", "agent", "tool", "repository"})

    def __post_init__(self) -> None:
        if self.kind not in self.VALID_KINDS:
            raise ValueError(
                f"Invalid reference kind '{self.kind}'. Must be one of {sorted(self.VALID_KINDS)}."
            )
        object.__setattr__(self, "context", tuple(self.context))
