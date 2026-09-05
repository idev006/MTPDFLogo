from __future__ import annotations

from mtpdflogo.application.queue_state import (
    blocked_start_message,
    queue_summary_text,
    readiness_message,
    status_message,
)


def test_readiness_message_is_actionable() -> None:
    assert readiness_message("missing_overlay", output_ready=False) == "เพิ่ม Text หรือ Logo ก่อนเริ่ม"
    assert readiness_message("invalid_page_filter", output_ready=False) == (
        "แก้เงื่อนไข Search/Regex ก่อนเริ่ม"
    )
    assert readiness_message("ready", output_ready=True) == "พร้อมเริ่ม"
    assert blocked_start_message("missing_overlay") == "เริ่มไม่ได้: เพิ่ม Text หรือ Logo ก่อนเริ่ม"
    assert blocked_start_message("ready") == "พร้อมเริ่ม Batch"


def test_queue_summary_text_includes_status_workers_and_blocker() -> None:
    summary = queue_summary_text(
        total=3,
        statuses={"Pending": 2, "Failed": 1},
        output_ready=False,
        workers=4,
        readiness_reason="missing_overlay",
    )

    assert "3 ไฟล์ใน queue" in summary
    assert "ล้มเหลว: 1" in summary
    assert "รอทำ: 2" in summary
    assert "Workers: 4" in summary
    assert "เพิ่ม Text หรือ Logo ก่อนเริ่ม" in summary


def test_queue_summary_text_handles_empty_queue() -> None:
    assert (
        queue_summary_text(
            total=0,
            statuses={},
            output_ready=False,
            workers=1,
            readiness_reason="missing_jobs",
        )
        == "ยังไม่มีไฟล์ใน queue"
    )


def test_status_message_translates_known_queue_states() -> None:
    assert status_message("Processing") == "กำลังทำ"
    assert status_message("Completed") == "สำเร็จ"
    assert status_message("custom") == "custom"
