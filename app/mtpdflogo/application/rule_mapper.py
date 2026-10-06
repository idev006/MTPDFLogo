"""Map editable rule dictionaries to immutable headless rule models."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from mtpdflogo.application.overlay_mapper import overlays_to_specs
from mtpdflogo.domain.rules import RuleBranch, RuleGroup, RuleScope


def rule_groups_to_models(
    groups: list[dict[str, Any]],
    font_path_resolver: Callable[[str], Path | None],
) -> list[RuleGroup]:
    models: list[RuleGroup] = []
    for group in groups:
        branches: list[RuleBranch] = []
        for branch in group.get("branches", []):
            branches.append(
                RuleBranch(
                    id=str(branch.get("id", "")),
                    name=str(branch.get("name", "")),
                    overlays=tuple(
                        overlays_to_specs(branch.get("overlays", []), font_path_resolver)
                    ),
                    min_occurrences=max(0, int(branch.get("min_occurrences", 0))),
                    max_occurrences=(
                        None
                        if branch.get("max_occurrences") is None
                        else max(0, int(branch.get("max_occurrences", 0)))
                    ),
                    enabled=bool(branch.get("enabled", True)),
                    is_else=bool(branch.get("is_else", False)),
                )
            )
        models.append(
            RuleGroup(
                id=str(group.get("id", "")),
                name=str(group.get("name", "")),
                keyword=str(group.get("keyword", "")),
                branches=tuple(branches),
                enabled=bool(group.get("enabled", True)),
                use_regex=bool(group.get("use_regex", False)),
                case_sensitive=bool(group.get("case_sensitive", False)),
                page_ranges=str(group.get("page_ranges", "")),
                scope=RuleScope(str(group.get("scope", RuleScope.PAGE.value))),
            )
        )
    return models


def all_rule_overlays(groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        overlay
        for group in groups
        for branch in group.get("branches", [])
        for overlay in branch.get("overlays", [])
    ]
