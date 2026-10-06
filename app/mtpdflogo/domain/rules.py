"""Domain records for ordered conditional overlay rules."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class RuleScope(StrEnum):
    """Text scope used when counting occurrences."""

    PAGE = "page"
    DOCUMENT = "document"


@dataclass(frozen=True, slots=True)
class RuleBranch:
    """One ordered if/elif/else branch and its independent layers."""

    id: str
    name: str
    overlays: tuple[Any, ...] = ()
    min_occurrences: int = 0
    max_occurrences: int | None = 0
    enabled: bool = True
    is_else: bool = False

    def matches_count(self, count: int) -> bool:
        if self.is_else or not self.enabled:
            return False
        if count < self.min_occurrences:
            return False
        return self.max_occurrences is None or count <= self.max_occurrences


@dataclass(frozen=True, slots=True)
class RuleGroup:
    """An ordered conditional chain sharing one text-search expression."""

    id: str
    name: str
    keyword: str
    branches: tuple[RuleBranch, ...]
    enabled: bool = True
    use_regex: bool = False
    case_sensitive: bool = False
    page_ranges: str = ""
    scope: RuleScope = RuleScope.PAGE

