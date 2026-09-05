"""Page range parsing shared by search preview and PDF export."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PageRange:
    start: int
    end: int | None = None

    def contains(self, page_number: int) -> bool:
        if page_number < self.start:
            return False
        return self.end is None or page_number <= self.end


def parse_page_ranges(expression: str) -> tuple[PageRange, ...]:
    """Parse user-facing ranges like ``1-3,5,10-`` into validated ranges."""
    expression = expression.strip()
    if not expression:
        return ()
    ranges: list[PageRange] = []
    for raw_part in expression.split(","):
        part = raw_part.strip()
        if not part:
            raise ValueError("ช่วงหน้ามีค่าว่าง")
        if "-" in part:
            start_text, end_text = [piece.strip() for piece in part.split("-", 1)]
            start = _parse_positive_page(start_text)
            end = _parse_positive_page(end_text) if end_text else None
            if end is not None and end < start:
                raise ValueError(f"ช่วงหน้าไม่ถูกต้อง: {part}")
            ranges.append(PageRange(start, end))
            continue
        page = _parse_positive_page(part)
        ranges.append(PageRange(page, page))
    return tuple(ranges)


def page_in_ranges(page_number: int, ranges: tuple[PageRange, ...]) -> bool:
    if not ranges:
        return True
    return any(page_range.contains(page_number) for page_range in ranges)


def _parse_positive_page(value: str) -> int:
    if not value.isdigit():
        raise ValueError(f"เลขหน้าไม่ถูกต้อง: {value or 'ว่าง'}")
    page = int(value)
    if page < 1:
        raise ValueError("เลขหน้าต้องเริ่มที่ 1")
    return page
