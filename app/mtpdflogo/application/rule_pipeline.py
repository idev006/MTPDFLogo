"""Headless evaluation of ordered if/elif/else overlay rules."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from mtpdflogo.application.page_ranges import page_in_ranges, parse_page_ranges
from mtpdflogo.domain.rules import (
    ConditionLogic,
    RuleBranch,
    RuleCondition,
    RuleGroup,
    RuleScope,
)

_MAX_REGEX_PATTERN_LENGTH = 500
_NESTED_QUANTIFIER_PATTERN = re.compile(r"\([^)]*[+*][^)]*\)\s*[+*{]")


@dataclass(frozen=True, slots=True)
class RuleMatch:
    """Explain which branch was selected and why."""

    group_id: str
    branch_id: str | None
    occurrence_count: int
    overlays: tuple[Any, ...]
    condition_results: tuple[ConditionResult, ...] = ()


@dataclass(frozen=True, slots=True)
class ConditionResult:
    condition_id: str
    occurrence_count: int
    matched: bool


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
    count_cache: dict[tuple[str, bool, bool, RuleScope], int] = {}
    legacy_count: int | None = None
    last_results: tuple[ConditionResult, ...] = ()
    fallback: RuleBranch | None = None
    for branch in group.branches:
        if not branch.enabled:
            continue
        if branch.is_else:
            fallback = fallback or branch
            continue
        if branch.conditions:
            enabled_conditions = [item for item in branch.conditions if item.enabled]
            if not enabled_conditions:
                continue
            results = tuple(
                _evaluate_condition(
                    condition,
                    page_text=page_text,
                    document_text=document_text,
                    count_cache=count_cache,
                )
                for condition in enabled_conditions
            )
            last_results = results
            matched = (
                all(result.matched for result in results)
                if branch.condition_logic is ConditionLogic.ALL
                else any(result.matched for result in results)
            )
            if matched:
                return RuleMatch(
                    group.id,
                    branch.id,
                    results[0].occurrence_count,
                    branch.overlays,
                    results,
                )
            continue
        if legacy_count is None:
            legacy_count = count_occurrences(
                content,
                group.keyword,
                use_regex=group.use_regex,
                case_sensitive=group.case_sensitive,
            )
        if branch.matches_count(legacy_count):
            return RuleMatch(group.id, branch.id, legacy_count, branch.overlays)
    if fallback is not None:
        count = last_results[0].occurrence_count if last_results else (legacy_count or 0)
        return RuleMatch(
            group.id,
            fallback.id,
            count,
            fallback.overlays,
            last_results,
        )
    count = last_results[0].occurrence_count if last_results else (legacy_count or 0)
    return RuleMatch(group.id, None, count, (), last_results)


def _evaluate_condition(
    condition: RuleCondition,
    *,
    page_text: str,
    document_text: str | None,
    count_cache: dict[tuple[str, bool, bool, RuleScope], int],
) -> ConditionResult:
    key = (
        condition.keyword,
        condition.use_regex,
        condition.case_sensitive,
        condition.scope,
    )
    if key not in count_cache:
        content = (
            document_text
            if condition.scope is RuleScope.DOCUMENT and document_text is not None
            else page_text
        )
        count_cache[key] = count_occurrences(
            content,
            condition.keyword,
            use_regex=condition.use_regex,
            case_sensitive=condition.case_sensitive,
        )
    count = count_cache[key]
    return ConditionResult(condition.id, count, condition.matches_count(count))


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
        uses_legacy_condition = any(
            branch.enabled and not branch.is_else and not branch.conditions
            for branch in group.branches
        )
        if uses_legacy_condition and group.use_regex:
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
        seen_condition_ids: set[str] = set()
        intervals: list[tuple[int, int, str]] = []
        for branch in group.branches:
            if not branch.id or branch.id in seen_branch_ids:
                issues.append(f"{group.name}: Branch ID ซ้ำหรือว่าง: {branch.name}")
            seen_branch_ids.add(branch.id)
            if branch.is_else:
                enabled_else += int(branch.enabled)
                continue
            if branch.conditions:
                enabled_conditions = [item for item in branch.conditions if item.enabled]
                if branch.enabled and not enabled_conditions:
                    issues.append(f"{group.name}/{branch.name}: ต้องมี Condition ที่เปิดใช้งาน")
                for condition in branch.conditions:
                    if not condition.id or condition.id in seen_condition_ids:
                        issues.append(
                            f"{group.name}/{branch.name}: Condition ID ซ้ำหรือว่าง: "
                            f"{condition.name}"
                        )
                    seen_condition_ids.add(condition.id)
                    issues.extend(_condition_issues(group.name, branch.name, condition))
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


def _condition_issues(
    group_name: str,
    branch_name: str,
    condition: RuleCondition,
) -> list[str]:
    prefix = f"{group_name}/{branch_name}/{condition.name}"
    issues: list[str] = []
    if not condition.keyword.strip():
        issues.append(f"{prefix}: กรุณาระบุคำหรือ Regex")
    maximum = condition.max_occurrences
    if condition.min_occurrences < 0 or (
        maximum is not None and maximum < condition.min_occurrences
    ):
        issues.append(f"{prefix}: ช่วงจำนวนครั้งไม่ถูกต้อง")
    if condition.use_regex:
        if len(condition.keyword) > _MAX_REGEX_PATTERN_LENGTH:
            issues.append(f"{prefix}: Regex ยาวเกิน {_MAX_REGEX_PATTERN_LENGTH} ตัวอักษร")
        if _NESTED_QUANTIFIER_PATTERN.search(condition.keyword):
            issues.append(f"{prefix}: Regex มี nested quantifier ที่เสี่ยงทำงานช้า")
        try:
            _compiled_pattern(
                unicodedata.normalize("NFKD", condition.keyword),
                condition.case_sensitive,
            )
        except re.error as error:
            issues.append(f"{prefix}: Regex ไม่ถูกต้อง: {error}")
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
