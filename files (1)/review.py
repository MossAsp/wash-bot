# ============================================================
# review.py — ระบบรีวิว/ให้คะแนน หลังใช้บริการ
# ============================================================

import json
from datetime import datetime
from pathlib import Path

REVIEW_FILE = Path("logs/reviews.json")
REVIEW_FILE.parent.mkdir(exist_ok=True)

# user ที่รอให้คะแนนอยู่ { user_id: True }
_pending_review: set[str] = set()


def _load() -> list:
    if REVIEW_FILE.exists():
        try:
            return json.loads(REVIEW_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return []
    return []


def _save(records: list):
    REVIEW_FILE.write_text(
        json.dumps(records, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


# ── ส่ง Quick Reply ขอคะแนน ─────────────────────────────────
def get_review_request_message() -> dict:
    """
    Flex Message + Quick Reply ขอให้ user ให้คะแนน
    ส่งหลังจากผ้าซักเสร็จหรือ user ออกจากร้าน
    """
    return {
        "type": "flex",
        "altText": "ให้คะแนนบริการ W&D",
        "contents": {
            "type": "bubble",
            "body": {
                "type": "box",
                "layout": "vertical",
                "spacing": "sm",
                "contents": [
                    {"type": "text", "text": "ขอบคุณที่ใช้บริการ W&D นะครับ/ค่ะ 🙏",
                     "weight": "bold", "size": "md", "wrap": True},
                    {"type": "text",
                     "text": "ช่วยให้คะแนนบริการด้วยได้ไหมครับ? จะได้ปรับปรุงให้ดีขึ้นครับ 😊",
                     "size": "sm", "color": "#888888", "wrap": True, "margin": "sm"},
                    {
                        "type": "box",
                        "layout": "horizontal",
                        "margin": "lg",
                        "spacing": "sm",
                        "contents": [
                            {
                                "type": "button",
                                "style": "secondary",
                                "action": {"type": "message", "label": s, "text": f"รีวิว {s}"},
                            }
                            for s in ["⭐", "⭐⭐", "⭐⭐⭐", "⭐⭐⭐⭐", "⭐⭐⭐⭐⭐"]
                        ],
                    },
                ],
            },
        },
    }


def get_review_quick_reply() -> dict:
    """Quick Reply ปุ่มดาว (lightweight กว่า Flex)"""
    return {
        "items": [
            {"type": "action", "action": {"type": "message", "label": s, "text": f"รีวิว {s}"}}
            for s in ["⭐ 1", "⭐⭐ 2", "⭐⭐⭐ 3", "⭐⭐⭐⭐ 4", "⭐⭐⭐⭐⭐ 5"]
        ]
    }


# ── บันทึกคะแนน ─────────────────────────────────────────────
def submit_review(user_id: str, stars: int, comment: str = "") -> str:
    """บันทึกคะแนนและคืนข้อความขอบคุณ"""
    record = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "user_id":   user_id,
        "stars":     stars,
        "comment":   comment,
    }
    records = _load()
    records.append(record)
    _save(records)

    _pending_review.discard(user_id)

    if stars >= 4:
        return f"ขอบคุณมากเลยครับ/ค่ะ! {stars}⭐ รู้สึกดีใจมากเลยนะครับ 😊\nแล้วมาใช้บริการอีกนะครับ/ค่ะ 🙏"
    elif stars == 3:
        return f"ขอบคุณสำหรับคะแนน {stars}⭐ ครับ/ค่ะ 🙏\nจะพยายามปรับปรุงให้ดีขึ้นนะครับ/ค่ะ 😊"
    else:
        return f"ขอบคุณสำหรับ feedback ครับ/ค่ะ 🙏\nขอโทษที่บริการยังไม่ดีพอนะครับ/ค่ะ จะรีบปรับปรุงครับ 😔"


def parse_star_rating(text: str) -> int | None:
    """แยกจำนวนดาวจากข้อความ เช่น 'รีวิว ⭐⭐⭐' → 3"""
    stars = text.count("⭐")
    if stars > 0:
        return min(stars, 5)
    # รองรับตัวเลข เช่น "รีวิว 4"
    import re
    m = re.search(r"(\d)", text)
    if m:
        n = int(m.group(1))
        if 1 <= n <= 5:
            return n
    return None


def is_pending(user_id: str) -> bool:
    return user_id in _pending_review


def set_pending(user_id: str):
    _pending_review.add(user_id)


# ── สถิติ ────────────────────────────────────────────────────
def get_stats() -> dict:
    records = _load()
    if not records:
        return {"total": 0, "avg_stars": 0}
    total = len(records)
    avg   = sum(r["stars"] for r in records) / total
    dist  = {i: sum(1 for r in records if r["stars"] == i) for i in range(1, 6)}
    return {"total": total, "avg_stars": round(avg, 2), "distribution": dist}
