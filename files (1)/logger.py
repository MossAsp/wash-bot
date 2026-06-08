# ============================================================
# logger.py — บันทึก Log การสนทนาทั้งหมด
# บันทึกเป็น JSON (ละเอียด) และ CSV (สรุป)
# ============================================================

import json
import csv
import os
from datetime import datetime
from pathlib import Path

LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

JSON_LOG = LOG_DIR / "conversations.json"
CSV_LOG  = LOG_DIR / "conversations.csv"


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _load_json() -> list:
    if JSON_LOG.exists():
        try:
            return json.loads(JSON_LOG.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return []
    return []


def log_message(
    session_id: str,
    platform: str,       # "terminal" | "line"
    user_id: str,        # user identifier
    role: str,           # "user" | "bot" | "admin" | "system"
    content: str,
    mode: str = "ai",    # "ai" | "admin"
    escalated: bool = False,
):
    """บันทึก 1 ข้อความลง log"""
    entry = {
        "timestamp": _now(),
        "session_id": session_id,
        "platform": platform,
        "user_id": user_id,
        "role": role,
        "content": content,
        "mode": mode,
        "escalated": escalated,
    }

    # ── JSON log (เก็บทุก field) ──────────────────────────
    records = _load_json()
    records.append(entry)
    JSON_LOG.write_text(
        json.dumps(records, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # ── CSV log (สรุปสั้น) ────────────────────────────────
    write_header = not CSV_LOG.exists()
    with open(CSV_LOG, "a", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=entry.keys())
        if write_header:
            writer.writeheader()
        writer.writerow(entry)


def log_session_start(session_id: str, platform: str, user_id: str):
    """บันทึกจุดเริ่มต้น session"""
    log_message(
        session_id=session_id,
        platform=platform,
        user_id=user_id,
        role="system",
        content="SESSION_START",
    )


def log_escalation(session_id: str, platform: str, user_id: str, trigger: str):
    """บันทึกเหตุการณ์ escalation"""
    log_message(
        session_id=session_id,
        platform=platform,
        user_id=user_id,
        role="system",
        content=f"ESCALATED — trigger: {trigger}",
        mode="admin",
        escalated=True,
    )


def get_stats() -> dict:
    """สรุปสถิติจาก log"""
    records = _load_json()
    if not records:
        return {"total": 0}

    total       = len([r for r in records if r["role"] == "user"])
    escalations = len([r for r in records if r.get("escalated")])
    platforms   = {}
    for r in records:
        p = r.get("platform", "unknown")
        platforms[p] = platforms.get(p, 0) + 1

    return {
        "total_messages": total,
        "escalations": escalations,
        "by_platform": platforms,
        "log_file_json": str(JSON_LOG),
        "log_file_csv": str(CSV_LOG),
    }
