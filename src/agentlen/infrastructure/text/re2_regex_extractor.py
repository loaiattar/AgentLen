"""Concrete `RegexExtractor` (domain/services/transformation_engine.py) using
re2 — linear-time matching, so a pattern like `(a+)+$` can't cause
catastrophic backtracking. Same rationale as infrastructure/ai/sanitizer.py,
which is why re2 usage lives here in infrastructure/ and nowhere in domain/
(import-linter enforces it).
"""

from __future__ import annotations

import re2

from agentlen.domain.errors import InvalidOperatorParamError


class Re2RegexExtractor:
    def extract(self, value: str, pattern: str, group: int) -> str | None:
        try:
            compiled = re2.compile(pattern)
        except re2.error as exc:
            raise InvalidOperatorParamError(
                field_path="", message=f"Invalid regex pattern: {exc}"
            ) from exc
        match = compiled.search(value)
        return match.group(group) if match else None
