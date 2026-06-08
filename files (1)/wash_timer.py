# ============================================================
# wash_timer.py — แจ้งเตือนเมื่อผ้าซัก/อบเสร็จ
# ใช้ threading.Timer (ไม่ต้องติดตั้ง Celery/Redis)
# ============================================================

import threading
from datetime import datetime, timedelta

# เก็บ timer ที่กำลังนับอยู่ { user_id: Timer }
_active_timers: dict[str, threading.Timer] = {}

# Callback ที่ line_bot.py จะ inject เข้ามา (push message ไปหา user)
_push_callback = None


def set_push_callback(fn):
    """
    ลงทะเบียน callback สำหรับ push LINE message
    fn(user_id: str, message: str)
    """
    global _push_callback
    _push_callback = fn


def start_timer(user_id: str, minutes: int, machine_label: str = "เครื่อง") -> str:
    """
    เริ่มจับเวลา — คืน confirmation text สำหรับตอบกลับ user
    ถ้า user มี timer อยู่แล้วจะ cancel และเริ่มใหม่
    """
    cancel_timer(user_id)

    def _done():
        _active_timers.pop(user_id, None)
        msg = (
            f"🔔 แจ้งเตือนครับ/ค่ะ!\n"
            f"{machine_label} เสร็จแล้ว ⏰\n"
            "รีบมารับผ้าได้เลยนะครับ/ค่ะ ก่อนที่จะมีคิวถัดไปครับ 😊"
        )
        if _push_callback:
            _push_callback(user_id, msg)

    t = threading.Timer(minutes * 60, _done)
    t.daemon = True
    t.start()

    _active_timers[user_id] = t
    finish_at = datetime.now() + timedelta(minutes=minutes)
    finish_str = finish_at.strftime("%H:%M น.")

    return (
        f"⏱️ ตั้งเวลาให้แล้วครับ/ค่ะ!\n"
        f"จะแจ้งเตือนอีก {minutes} นาที (ประมาณ {finish_str})\n"
        "จะได้ไม่ลืมมารับผ้านะครับ/ค่ะ 😊"
    )


def cancel_timer(user_id: str) -> bool:
    """ยกเลิก timer ของ user"""
    t = _active_timers.pop(user_id, None)
    if t:
        t.cancel()
        return True
    return False


def get_active_timers() -> dict[str, str]:
    """คืนรายการ timer ที่กำลังนับอยู่ (สำหรับ debug/admin)"""
    return {uid: "กำลังนับ" for uid in _active_timers}


def parse_timer_request(text: str) -> int | None:
    """
    แยกจำนวนนาทีจากข้อความ เช่น "ซัก 30 นาที", "อบ 20 นาที"
    คืน None ถ้าหาไม่เจอ
    """
    import re
    m = re.search(r"(\d+)\s*นาที", text)
    if m:
        return int(m.group(1))
    # default ตามบริการ
    if "ซัก" in text:
        return 30
    if "อบ" in text:
        return 20
    return None
