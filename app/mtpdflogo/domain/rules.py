"""Domain records for ordered conditional overlay rules."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class RuleScope(StrEnum):
    """Text scope used when counting occurrences."""

    PAGE = "page"
    DOCUMENT = "document"


class ConditionLogic(StrEnum):
    """How enabled conditions inside one branch are combined."""

    ALL = "all"
    ANY = "any"


@dataclass(frozen=True, slots=True)
class RuleCondition:
    """One independently configurable text occurrence predicate."""

    id: str
    name: str
    keyword: str
    min_occurrences: int = 1
    max_occurrences: int | None = None
    enabled: bool = True
    use_regex: bool = False
    case_sensitive: bool = False
    negate: bool = False
    scope: RuleScope = RuleScope.PAGE

    def matches_count(self, count: int) -> bool:
        matched = count >= self.min_occurrences and (
            self.max_occurrences is None or count <= self.max_occurrences
        )
        return not matched if self.negate else matched


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
    conditions: tuple[RuleCondition, ...] = ()
    condition_logic: ConditionLogic = ConditionLogic.ALL

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
