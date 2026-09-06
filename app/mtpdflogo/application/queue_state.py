"""Headless queue status helpers for the batch workspace."""

READINESS_MESSAGES = {
    "ready": "พร้อมเริ่ม",
    "running": "กำลังประมวลผล",
    "missing_jobs": "ยังไม่มีไฟล์ใน queue",
    "invalid_page_filter": "แก้เงื่อนไข Search/Regex ก่อนเริ่ม",
    "missing_overlay": "เพิ่ม Text หรือ Logo ก่อนเริ่ม",
    "missing_output": "เลือก Output Folder ก่อนเริ่ม",
}

STATUS_MESSAGES = {
    "Pending": "รอทำ",
    "Processing": "กำลังทำ",
    "Completed": "สำเร็จ",
    "Failed": "ล้มเหลว",
    "Cancelled": "ยกเลิก",
    "Stopping": "กำลังหยุด",
}


def queue_summary_text(
    *,
    total: int,
    statuses: dict[str, int],
    output_ready: bool,
    workers: int,
    readiness_reason: str,
) -> str:
    """Return a concise user-facing queue summary."""
    if total == 0:
        return "ยังไม่มีไฟล์ใน queue"
    status_text = ", ".join(
        f"{status_message(name)}: {count}" for name, count in sorted(statuses.items())
    )
    ready_text = readiness_message(readiness_reason, output_ready=output_ready)
    return f"{total} ไฟล์ใน queue | {status_text} | Workers: {workers} | {ready_text}"


def readiness_message(reason: str, *, output_ready: bool) -> str:
    if output_ready:
        return READINESS_MESSAGES["ready"]
    return READINESS_MESSAGES.get(reason, "รอข้อมูลให้ครบก่อนเริ่ม")


def blocked_start_message(reason: str) -> str:
    message = READINESS_MESSAGES.get(reason, "ตรวจข้อมูลใน Batch Workspace ให้ครบ")
    if reason == "ready":
        return "พร้อมเริ่ม Batch"
    return f"เริ่มไม่ได้: {message}"


def status_message(status: str) -> str:
    return STATUS_MESSAGES.get(status, status)
