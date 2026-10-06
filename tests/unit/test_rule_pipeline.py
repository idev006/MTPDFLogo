from dataclasses import replace

from mtpdflogo.application.rule_pipeline import (
    evaluate_rule_group,
    resolve_page_overlays,
    validate_rule_groups,
)
from mtpdflogo.domain.rules import (
    ConditionLogic,
    RuleBranch,
    RuleCondition,
    RuleGroup,
    RuleScope,
)


def _group(*branches: RuleBranch, **changes) -> RuleGroup:
    values = {
        "id": "amount",
        "name": "จำนวนเงิน",
        "keyword": "จำนวนเงิน",
        "branches": tuple(branches),
    }
    values.update(changes)
    return RuleGroup(**values)


def test_exact_inclusive_ranges_select_first_matching_branch() -> None:
    group = _group(
        RuleBranch("three", "เท่ากับ 3", ("x1", "x2"), 3, 3),
        RuleBranch("five", "เท่ากับ 5", ("x3", "x4"), 5, 5),
        RuleBranch("else", "ค่าอื่น", (), is_else=True),
    )

    match = evaluate_rule_group(
        group,
        page_text="จำนวนเงิน จำนวนเงิน จำนวนเงิน",
        page_number=1,
    )

    assert match.branch_id == "three"
    assert match.occurrence_count == 3
    assert match.overlays == ("x1", "x2")


def test_disabled_branch_falls_through_to_else_without_losing_layers() -> None:
    disabled = RuleBranch("three", "เท่ากับ 3", ("kept",), 3, 3, enabled=False)
    group = _group(disabled, RuleBranch("else", "ค่าอื่น", ("fallback",), is_else=True))

    match = evaluate_rule_group(
        group,
        page_text="จำนวนเงิน จำนวนเงิน จำนวนเงิน",
        page_number=1,
    )

    assert disabled.overlays == ("kept",)
    assert match.branch_id == "else"
    assert match.overlays == ("fallback",)


def test_group_disabled_produces_no_match() -> None:
    group = _group(
        RuleBranch("three", "เท่ากับ 3", ("overlay",), 3, 3),
        enabled=False,
    )

    match = evaluate_rule_group(group, page_text="จำนวนเงิน " * 3, page_number=1)

    assert match.branch_id is None
    assert match.overlays == ()


def test_multiple_groups_combine_layers_but_each_group_selects_one_branch() -> None:
    first = _group(
        RuleBranch("first-match", "3", ("a",), 3, 3),
        RuleBranch("overlap", "2-4", ("must-not-run",), 2, 4),
    )
    second = RuleGroup(
        "approved",
        "อนุมัติ",
        "อนุมัติ",
        (RuleBranch("yes", "พบ", ("b",), 1, None),),
    )

    overlays, matches = resolve_page_overlays(
        [first, second],
        page_text="จำนวนเงิน " * 3 + "อนุมัติ",
        page_number=1,
    )

    assert overlays == ["a", "b"]
    assert [match.branch_id for match in matches] == ["first-match", "yes"]


def test_document_scope_uses_document_text_and_page_ranges_still_apply() -> None:
    group = _group(
        RuleBranch("five", "5", ("doc",), 5, 5),
        scope=RuleScope.DOCUMENT,
        page_ranges="2",
    )

    outside = evaluate_rule_group(
        group, page_text="", document_text="จำนวนเงิน " * 5, page_number=1
    )
    inside = evaluate_rule_group(
        group, page_text="", document_text="จำนวนเงิน " * 5, page_number=2
    )

    assert outside.branch_id is None
    assert inside.branch_id == "five"


def test_validation_reports_overlap_invalid_ranges_and_multiple_else() -> None:
    group = _group(
        RuleBranch("a", "3-7", (), 3, 7),
        RuleBranch("b", "5-9", (), 5, 9),
        RuleBranch("bad", "bad", (), 9, 4),
        RuleBranch("else-1", "else 1", (), is_else=True),
        RuleBranch("else-2", "else 2", (), is_else=True),
    )

    issues = validate_rule_groups([group])

    assert any("3-7 ซ้อนกับ 5-9" in issue for issue in issues)
    assert any("ช่วงจำนวนครั้งไม่ถูกต้อง" in issue for issue in issues)
    assert any("Else" in issue for issue in issues)


def test_layer_state_is_independent_per_branch() -> None:
    original = RuleBranch("three", "3", ({"id": "logo", "enabled": True},), 3, 3)
    changed = replace(original, overlays=({"id": "logo", "enabled": False},))

    assert original.overlays[0]["enabled"] is True
    assert changed.overlays[0]["enabled"] is False


def test_compound_all_requires_every_enabled_condition() -> None:
    branch = RuleBranch(
        "approved-three",
        "Amount 3 and approved",
        ("layer",),
        conditions=(
            RuleCondition("amount", "Amount", "amount", 3, 3),
            RuleCondition("approved", "Approved", "approved", 1, None),
        ),
        condition_logic=ConditionLogic.ALL,
    )
    group = _group(branch, RuleBranch("else", "Else", (), is_else=True))

    matched = evaluate_rule_group(
        group,
        page_text="amount amount amount approved",
        page_number=1,
    )
    fallback = evaluate_rule_group(
        group,
        page_text="amount amount amount",
        page_number=1,
    )

    assert matched.branch_id == branch.id
    assert [result.occurrence_count for result in matched.condition_results] == [3, 1]
    assert fallback.branch_id == "else"


def test_compound_any_and_not_support_business_exclusions() -> None:
    branch = RuleBranch(
        "urgent",
        "Urgent but not cancelled",
        ("urgent-layer",),
        conditions=(
            RuleCondition("urgent", "Urgent", "urgent", 1, None),
            RuleCondition("not-cancelled", "Not cancelled", "cancelled", 1, None, negate=True),
        ),
        condition_logic=ConditionLogic.ALL,
    )
    alternative = replace(
        branch,
        id="any",
        condition_logic=ConditionLogic.ANY,
    )

    assert evaluate_rule_group(
        _group(branch), page_text="urgent", page_number=1
    ).branch_id == "urgent"
    assert evaluate_rule_group(
        _group(branch), page_text="urgent cancelled", page_number=1
    ).branch_id is None
    assert evaluate_rule_group(
        _group(alternative), page_text="ordinary", page_number=1
    ).branch_id == "any"


def test_disabled_conditions_are_ignored_but_empty_active_stack_never_matches() -> None:
    branch = RuleBranch(
        "branch",
        "Branch",
        ("layer",),
        conditions=(
            RuleCondition("disabled", "Disabled", "missing", 1, 1, enabled=False),
            RuleCondition("active", "Active", "present", 1, 1),
        ),
    )
    empty = replace(
        branch,
        id="empty",
        conditions=(replace(branch.conditions[0], id="only-disabled"),),
    )

    assert evaluate_rule_group(
        _group(branch), page_text="present", page_number=1
    ).branch_id == "branch"
    assert evaluate_rule_group(
        _group(empty), page_text="missing", page_number=1
    ).branch_id is None
    assert any("ต้องมี Condition" in issue for issue in validate_rule_groups([_group(empty)]))


def test_repeated_condition_expression_is_counted_once_per_group(monkeypatch) -> None:
    from mtpdflogo.application import rule_pipeline

    calls: list[str] = []
    original = rule_pipeline.count_occurrences

    def counted(text, keyword, **options):
        calls.append(keyword)
        return original(text, keyword, **options)

    monkeypatch.setattr(rule_pipeline, "count_occurrences", counted)
    condition = RuleCondition("same", "Same", "amount", 5, 5)
    first = RuleBranch("first", "First", (), conditions=(condition,))
    second = RuleBranch(
        "second",
        "Second",
        ("layer",),
        conditions=(replace(condition, id="same-again", min_occurrences=3, max_occurrences=3),),
    )

    match = evaluate_rule_group(
        _group(first, second), page_text="amount amount amount", page_number=1
    )

    assert match.branch_id == "second"
    assert calls == ["amount"]
