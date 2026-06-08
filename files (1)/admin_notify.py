# ============================================================
# admin_notify.py — แจ้งเตือน Admin ทาง LINE เมื่อ escalation
# ============================================================

import os
from datetime import datetime

# LINE User ID ของ Admin (ดูได้จาก LINE Developers Console → webhook log)
# หรือใช้ Group/Room ID ถ้าอยากแจ้งทั้ง group
ADMIN_LINE_USER_ID = os.getenv("ADMIN_LINE_USER_ID", "")

# inject จาก line_bot.py
_line_api = None


def set_line_api(api):
    """ลงทะเบียน LINE Messaging API client"""
    global _line_api
    _line_api = api


def notify_escalation(
    customer_user_id: str,
    trigger_text: str,
    reason: str = "unknown",
):
    """
    Push แจ้ง Admin เมื่อเกิด escalation
    - customer_user_id : LINE user ID ของลูกค้า
    - trigger_text     : ข้อความที่ลูกค้าพิมพ์
    - reason           : "keyword" | "unknown_question"
    """
    if not ADMIN_LINE_USER_ID:
        print("[admin_notify] ⚠️  ADMIN_LINE_USER_ID ยังไม่ได้ตั้งค่า")
        return False

    reason_label = {
        "keyword":          "คำสำคัญ (เครื่องเสีย/ลืมผ้า)",
        "unknown_question": "คำถามนอกเหนือจาก FAQ",
    }.get(reason, reason)

    now = datetime.now().strftime("%H:%M น.")

    msg = (
        f"🚨 แจ้งเตือน! มีลูกค้าต้องการความช่วยเหลือครับ\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🕐 เวลา       : {now}\n"
        f"👤 User ID   : {customer_user_id[:12]}...\n"
        f"💬 ข้อความ   : {trigger_text[:60]}\n"
        f"📌 สาเหตุ    : {reason_label}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"กรุณาเข้าไปตอบลูกค้าด้วยนะครับ 🙏"
    )

    return _push_to_admin(msg)


def notify_machine_error(machine_id: str, reported_by: str):
    """แจ้ง Admin เมื่อมีการรายงานเครื่องเสีย"""
    if not ADMIN_LINE_USER_ID:
        return False

    now = datetime.now().strftime("%H:%M น.")
    msg = (
        f"🔧 แจ้งเตือน! มีรายงานเครื่องเสียครับ\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🕐 เวลา        : {now}\n"
        f"🏷️  เครื่อง     : {machine_id}\n"
        f"👤 รายงานโดย : {reported_by[:12]}...\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"กรุณาตรวจสอบด้วยนะครับ 🙏"
    )
    return _push_to_admin(msg)


def notify_low_rating(user_id: str, stars: int):
    """แจ้ง Admin เมื่อได้รับคะแนนต่ำ (≤ 2 ดาว)"""
    if not ADMIN_LINE_USER_ID or stars > 2:
        return False

    now = datetime.now().strftime("%H:%M น.")
    msg = (
        f"⭐ แจ้งเตือน! ได้รับคะแนนต่ำครับ\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🕐 เวลา   : {now}\n"
        f"⭐ คะแนน  : {'⭐' * stars} ({stars}/5)\n"
        f"👤 User  : {user_id[:12]}...\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"ลองติดตามเพื่อปรับปรุงบริการด้วยนะครับ 🙏"
    )
    return _push_to_admin(msg)


# ── Internal ────────────────────────────────────────────────
def _push_to_admin(message: str) -> bool:
    if not _line_api:
        print(f"[admin_notify] (no API) → {message[:80]}")
        return False
    try:
        from linebot.v3.messaging import PushMessageRequest, TextMessage
        _line_api.push_message(
            PushMessageRequest(
                to=ADMIN_LINE_USER_ID,
                messages=[TextMessage(text=message)],
            )
        )
        return True
    except Exception as e:
        print(f"[admin_notify] push failed: {e}")
        return False
