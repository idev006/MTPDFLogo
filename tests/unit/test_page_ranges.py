from __future__ import annotations

import pytest
from mtpdflogo.application.page_ranges import page_in_ranges, parse_page_ranges


def test_parse_page_ranges_supports_single_closed_and_open_ranges() -> None:
    ranges = parse_page_ranges("1-3, 5, 10-")

    assert page_in_ranges(1, ranges)
    assert page_in_ranges(3, ranges)
    assert not page_in_ranges(4, ranges)
    assert page_in_ranges(5, ranges)
    assert not page_in_ranges(9, ranges)
    assert page_in_ranges(99, ranges)


def test_parse_page_ranges_empty_means_all_pages() -> None:
    assert parse_page_ranges("") == ()
    assert page_in_ranges(500, ())


@pytest.mark.parametrize("expression", ["0", "3-1", "1,,2", "x", "-3"])
def test_parse_page_ranges_rejects_invalid_user_input(expression: str) -> None:
    with pytest.raises(ValueError):
        parse_page_ranges(expression)
