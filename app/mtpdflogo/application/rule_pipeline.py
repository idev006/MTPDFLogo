"""Headless evaluation of ordered if/elif/else overlay rules."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from mtpdflogo.application.page_ranges import page_in_ranges, parse_page_ranges
from mtpdflogo.domain.rules import RuleBranch, RuleGroup, RuleScope

_MAX_REGEX_PATTERN_LENGTH = 500
_NESTED_QUANTIFIER_PATTERN = re.compile(r"\([^)]*[+*][^)]*\)\s*[+*{]")


@dataclass(frozen=True, slots=True)
class RuleMatch:
    """Explain which branch was selected and why."""

    group_id: str
    branch_id: str | None
    occurrence_count: int
    overlays: tuple[Any, ...]


def evaluate_rule_group(
    group: RuleGroup,
    *,
    page_text: str,
    page_number: int,
    document_text: str | None = None,
) -> RuleMatch:
    """Select the first enabled matching branch, then the enabled else branch."""
    if not group.enabled or not page_in_ranges(page_number, _parsed_ranges(group.page_ranges)):
        return RuleMatch(group.id, None, 0, ())
    content = (
        document_text
        if group.scope is RuleScope.DOCUMENT and document_text is not None
        else page_text
    )
    count = count_occurrences(
        content,
        group.keyword,
        use_regex=group.use_regex,
        case_sensitive=group.case_sensitive,
    )
    fallback: RuleBranch | None = None
    for branch in group.branches:
        if not branch.enabled:
            continue
        if branch.is_else:
            fallback = fallback or branch
        elif branch.matches_count(count):
            return RuleMatch(group.id, branch.id, count, branch.overlays)
    if fallback is not None:
        return RuleMatch(group.id, fallback.id, count, fallback.overlays)
    return RuleMatch(group.id, None, count, ())


def resolve_page_overlays(
    groups: list[RuleGroup] | tuple[RuleGroup, ...],
    *,
    page_text: str,
    page_number: int,
    document_text: str | None = None,
) -> tuple[list[Any], list[RuleMatch]]:
    """Resolve layers from every enabled group while preserving group/branch order."""
    overlays: list[Any] = []
    matches: list[RuleMatch] = []
    for group in groups:
        match = evaluate_rule_group(
            group,
            page_text=page_text,
            page_number=page_number,
            document_text=document_text,
        )
        matches.append(match)
        overlays.extend(match.overlays)
    return overlays, matches


def validate_rule_groups(groups: list[RuleGroup] | tuple[RuleGroup, ...]) -> list[str]:
    """Return deterministic validation issues for UI and preflight use."""
    issues: list[str] = []
    seen_group_ids: set[str] = set()
    for group in groups:
        if not group.id or group.id in seen_group_ids:
            issues.append(f"Rule Group ID ซ้ำหรือว่าง: {group.name}")
        seen_group_ids.add(group.id)
        if group.use_regex:
            if len(group.keyword) > _MAX_REGEX_PATTERN_LENGTH:
                issues.append(f"{group.name}: Regex ยาวเกิน {_MAX_REGEX_PATTERN_LENGTH} ตัวอักษร")
            if _NESTED_QUANTIFIER_PATTERN.search(group.keyword):
                issues.append(f"{group.name}: Regex มี nested quantifier ที่เสี่ยงทำงานช้า")
            try:
                re.compile(unicodedata.normalize("NFKD", group.keyword))
            except re.error as error:
                issues.append(f"{group.name}: Regex ไม่ถูกต้อง: {error}")
        try:
            parse_page_ranges(group.page_ranges)
        except ValueError as error:
            issues.append(f"{group.name}: ช่วงหน้าไม่ถูกต้อง: {error}")
        enabled_else = 0
        seen_branch_ids: set[str] = set()
        intervals: list[tuple[int, int, str]] = []
        for branch in group.branches:
            if not branch.id or branch.id in seen_branch_ids:
                issues.append(f"{group.name}: Branch ID ซ้ำหรือว่าง: {branch.name}")
            seen_branch_ids.add(branch.id)
            if branch.is_else:
                enabled_else += int(branch.enabled)
                continue
            maximum = branch.max_occurrences
            if branch.min_occurrences < 0 or (
                maximum is not None and maximum < branch.min_occurrences
            ):
                issues.append(f"{group.name}/{branch.name}: ช่วงจำนวนครั้งไม่ถูกต้อง")
                continue
            if branch.enabled:
                intervals.append(
                    (
                        branch.min_occurrences,
                        maximum if maximum is not None else 2**31 - 1,
                        branch.name,
                    )
                )
        if enabled_else > 1:
            issues.append(f"{group.name}: เปิดใช้งาน Else ได้ไม่เกินหนึ่ง Branch")
        for index, (low, high, name) in enumerate(intervals):
            for other_low, other_high, other_name in intervals[index + 1 :]:
                if max(low, other_low) <= min(high, other_high):
                    issues.append(f"{group.name}: {name} ซ้อนกับ {other_name}")
    return issues


def blocking_rule_issues(groups: list[RuleGroup] | tuple[RuleGroup, ...]) -> list[str]:
    """Return issues that make evaluation unsafe; interval overlap remains a warning."""
    return [issue for issue in validate_rule_groups(groups) if " ซ้อนกับ " not in issue]


def count_occurrences(
    text: str,
    keyword: str,
    *,
    use_regex: bool = False,
    case_sensitive: bool = False,
) -> int:
    """Count with the same Unicode/whitespace semantics as legacy page search."""
    if not keyword.strip():
        return 0
    content = unicodedata.normalize("NFKD", text)
    pattern = unicodedata.normalize("NFKD", keyword)
    if use_regex:
        return sum(1 for _ in _compiled_pattern(pattern, case_sensitive).finditer(content))
    if not case_sensitive:
        content = content.casefold()
        pattern = pattern.casefold()
    return "".join(content.split()).count("".join(pattern.split()))


@lru_cache(maxsize=128)
def _compiled_pattern(pattern: str, case_sensitive: bool) -> re.Pattern[str]:
    return re.compile(pattern, 0 if case_sensitive else re.I)


@lru_cache(maxsize=128)
def _parsed_ranges(value: str) -> tuple[Any, ...]:
    return parse_page_ranges(value)
