from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ReferenceRequest:
    """A name that needs to be resolved (or created) as a referential row.

    Declarative only: the domain never does I/O. `resolve_references`
    (application layer) is what actually upserts these via the repositories.
    """

    kind: str  # 'provider' | 'model' | 'agent' | 'tool' | 'repository'
    name: str

    VALID_KINDS = frozenset({"provider", "model", "agent", "tool", "repository"})

    def __post_init__(self) -> None:
        if self.kind not in self.VALID_KINDS:
            raise ValueError(
                f"Invalid reference kind '{self.kind}'. Must be one of {sorted(self.VALID_KINDS)}."
            )
