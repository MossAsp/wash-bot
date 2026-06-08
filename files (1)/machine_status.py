# ============================================================
# machine_status.py — สถานะเครื่องซัก/อบ
# เก็บ state ใน memory (dict)
# ถ้าอยากเก็บถาวร → เปลี่ยนไปใช้ JSON file หรือ SQLite
# ============================================================

from datetime import datetime, timedelta

# ── สถานะเครื่องทั้งหมด ────────────────────────────────────
# structure: { machine_id: { "type", "size_kg", "status", "free_at", "user_id" } }
MACHINES: dict[str, dict] = {
    "W01": {"type": "washer", "size_kg": 9,  "label": "ซัก 9 kg",           "status": "free",  "free_at": None, "user_id": None},
    "W02": {"type": "washer", "size_kg": 9,  "label": "ซัก 9 kg",           "status": "free",  "free_at": None, "user_id": None},
    "W03": {"type": "washer", "size_kg": 14, "label": "ซัก 14 kg",          "status": "free",  "free_at": None, "user_id": None},
    "W04": {"type": "washer", "size_kg": 27, "label": "ซัก 27 kg (นวม)",    "status": "free",  "free_at": None, "user_id": None},
    "D01": {"type": "dryer",  "size_kg": 14, "label": "อบ 14 kg",           "status": "free",  "free_at": None, "user_id": None},
    "D02": {"type": "dryer",  "size_kg": 14, "label": "อบ 14 kg",           "status": "free",  "free_at": None, "user_id": None},
    "D03": {"type": "dryer",  "size_kg": 14, "label": "อบ 14 kg",           "status": "free",  "free_at": None, "user_id": None},
}

STATUS_LABEL = {
    "free":  "ว่าง ✅",
    "busy":  "ไม่ว่าง 🔴",
    "error": "เสีย 🔧",
}


def get_all_status() -> dict:
    """คืนสถานะเครื่องทั้งหมด พร้อม auto-free เครื่องที่หมดเวลาแล้ว"""
    _auto_free()
    return MACHINES.copy()


def get_summary_text() -> str:
    """สรุปสถานะแบบ text สำหรับตอบใน chat"""
    _auto_free()
    lines = ["🏭 สถานะเครื่องทั้งหมดครับ/ค่ะ\n"]

    washers = {k: v for k, v in MACHINES.items() if v["type"] == "washer"}
    dryers  = {k: v for k, v in MACHINES.items() if v["type"] == "dryer"}

    lines.append("🫧 เครื่องซักผ้า")
    for mid, m in washers.items():
        eta = _eta_text(m)
        lines.append(f"  {mid} ({m['label']}) — {STATUS_LABEL[m['status']]}{eta}")

    lines.append("\n☀️ เครื่องอบผ้า")
    for mid, m in dryers.items():
        eta = _eta_text(m)
        lines.append(f"  {mid} ({m['label']}) — {STATUS_LABEL[m['status']]}{eta}")

    free_w = sum(1 for m in washers.values() if m["status"] == "free")
    free_d = sum(1 for m in dryers.values()  if m["status"] == "free")
    lines.append(f"\nว่างอยู่: ซัก {free_w} เครื่อง / อบ {free_d} เครื่องครับ/ค่ะ 😊")
    return "\n".join(lines)


def get_flex_message() -> dict:
    """สร้าง LINE Flex Message แสดงสถานะเครื่อง"""
    _auto_free()

    def _row(mid: str, m: dict) -> dict:
        color = {"free": "#1D9E75", "busy": "#E24B4A", "error": "#EF9F27"}.get(m["status"], "#888")
        eta   = _eta_text(m).strip()
        sub   = eta if eta else STATUS_LABEL[m["status"]]
        return {
            "type": "box",
            "layout": "horizontal",
            "contents": [
                {"type": "text", "text": mid,         "size": "sm", "color": "#555555", "flex": 1},
                {"type": "text", "text": m["label"],  "size": "sm", "flex": 3},
                {"type": "text", "text": sub,         "size": "sm", "color": color, "flex": 3, "align": "end"},
            ],
            "paddingTop": "6px",
        }

    washers = [_row(k, v) for k, v in MACHINES.items() if v["type"] == "washer"]
    dryers  = [_row(k, v) for k, v in MACHINES.items() if v["type"] == "dryer"]

    return {
        "type": "flex",
        "altText": "สถานะเครื่องซัก/อบ W&D",
        "contents": {
            "type": "bubble",
            "header": {
                "type": "box", "layout": "vertical",
                "backgroundColor": "#0F6E56",
                "contents": [{"type": "text", "text": "🏭  สถานะเครื่อง W&D",
                               "color": "#FFFFFF", "weight": "bold", "size": "md"}],
            },
            "body": {
                "type": "box", "layout": "vertical", "spacing": "sm",
                "contents": [
                    {"type": "text", "text": "🫧 เครื่องซักผ้า", "weight": "bold", "size": "sm"},
                    *washers,
                    {"type": "separator", "margin": "md"},
                    {"type": "text", "text": "☀️ เครื่องอบผ้า", "weight": "bold", "size": "sm", "margin": "md"},
                    *dryers,
                ],
            },
            "footer": {
                "type": "box", "layout": "vertical",
                "contents": [{"type": "button", "style": "primary",
                               "color": "#0F6E56",
                               "action": {"type": "message", "label": "🔄 รีเฟรชสถานะ",
                                          "text": "เช็คสถานะเครื่อง"}}],
            },
        },
    }


def set_busy(machine_id: str, minutes: int, user_id: str = "") -> bool:
    """ตั้งสถานะเครื่องเป็น busy พร้อมเวลาคาดว่าจะว่าง"""
    if machine_id not in MACHINES:
        return False
    MACHINES[machine_id]["status"]  = "busy"
    MACHINES[machine_id]["free_at"] = datetime.now() + timedelta(minutes=minutes)
    MACHINES[machine_id]["user_id"] = user_id
    return True


def set_free(machine_id: str) -> bool:
    if machine_id not in MACHINES:
        return False
    MACHINES[machine_id]["status"]  = "free"
    MACHINES[machine_id]["free_at"] = None
    MACHINES[machine_id]["user_id"] = None
    return True


def set_error(machine_id: str) -> bool:
    if machine_id not in MACHINES:
        return False
    MACHINES[machine_id]["status"] = "error"
    return True


# ── Internal helpers ────────────────────────────────────────
def _auto_free():
    """คืนสถานะเครื่องที่หมดเวลาแล้วเป็น free อัตโนมัติ"""
    now = datetime.now()
    for m in MACHINES.values():
        if m["status"] == "busy" and m["free_at"] and now >= m["free_at"]:
            m["status"]  = "free"
            m["free_at"] = None
            m["user_id"] = None


def _eta_text(m: dict) -> str:
    if m["status"] == "busy" and m["free_at"]:
        remaining = int((m["free_at"] - datetime.now()).total_seconds() / 60)
        remaining = max(0, remaining)
        return f" (อีก ~{remaining} นาที)"
    return ""
