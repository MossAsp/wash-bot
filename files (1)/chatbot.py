# ============================================================
# chatbot.py — Engine W&D (v3) + Claude API
#
# Flow:
#   1. เช็ค escalation keywords → โอน Admin ทันที
#   2. Pattern match จาก Q&A database → ตอบเลย (เร็ว/แม่นยำ)
#   3. ถ้าไม่เจอ → ส่งให้ Claude API ตอบ (ฉลาด/ยืดหยุ่น)
#   4. Claude ตอบไม่ได้ / error → escalate Admin
# ============================================================

import re
import uuid
import json
import urllib.request
import urllib.error
import os

from database import QA_DATASET, ESCALATE_KEYWORDS, SHOP_INFO, SERVICES
from logger   import log_message, log_session_start, log_escalation

# ── Claude API config ────────────────────────────────────────
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL      = "claude-haiku-4-5-20251001"   # เร็ว + ถูก เหมาะสำหรับ chatbot
CLAUDE_API_URL    = "https://api.anthropic.com/v1/messages"

# ── System prompt สำหรับ Claude ─────────────────────────────
SYSTEM_PROMPT = f"""คุณคือผู้ช่วย AI ของร้านสะดวกซัก "{SHOP_INFO['name']}" ตั้งอยู่ที่ {SHOP_INFO['location']}
{SHOP_INFO['hours']}

ข้อมูลบริการและราคา:
เครื่องซักผ้า:
- 9 kg = {SERVICES['washer'][0]['price']} บาท
- 14 kg = {SERVICES['washer'][1]['price']} บาท
- 27 kg (ผ้านวม) = {SERVICES['washer'][2]['price']} บาท

เครื่องอบผ้า:
- เริ่มต้น {SERVICES['dryer']['base_price']} บาท ({SERVICES['dryer']['base_minutes']} นาที)
- เพิ่มเวลา 5 นาที = +{SERVICES['dryer']['extra_per_5min']} บาท

น้ำยาซักผ้า/ปรับผ้านุ่ม: ตู้อัตโนมัติ เริ่มต้น {SERVICES['detergent']['start_price']} บาท/ซอง
การชำระเงิน: รับธนบัตรและเหรียญเท่านั้น

กฎการตอบ:
1. ตอบเป็นภาษาไทย สุภาพ ใจดี เป็นกันเอง ลงท้ายด้วย ครับ/ค่ะ
2. ตอบสั้นกระชับ ไม่เกิน 3-4 ประโยค
3. ถ้าถามเรื่องที่ไม่เกี่ยวกับร้าน ให้บอกว่าตอบได้เฉพาะเรื่องร้านเท่านั้น
4. ห้ามแต่งข้อมูลที่ไม่รู้ ให้บอกตรงๆ ว่าไม่ทราบ
5. ถ้าเป็นปัญหาเร่งด่วน เช่น เครื่องเสีย ลืมผ้า ให้แนะนำติดต่อ Admin"""


class WDChatbot:
    """AI ด่านหน้าสำหรับร้านสะดวกซัก W&D พร้อม Claude API"""

    def __init__(self, platform: str = "terminal", user_id: str = "anonymous"):
        self.mode       = "ai"
        self.history: list[dict] = []
        self.platform   = platform
        self.user_id    = user_id
        self.session_id = str(uuid.uuid4())[:8]

        self._qa_compiled       = self._compile_qa()
        self._escalate_compiled = [
            re.compile(re.escape(k), re.IGNORECASE)
            for k in ESCALATE_KEYWORDS
        ]

        log_session_start(self.session_id, self.platform, self.user_id)

    # ─── Setup ─────────────────────────────────────────────
    def _compile_qa(self) -> list[dict]:
        compiled = []
        for qa in QA_DATASET:
            patterns = [
                re.compile(re.escape(p), re.IGNORECASE)
                for p in qa["patterns"]
            ]
            compiled.append({
                "id":       qa["id"],
                "patterns": patterns,
                "answer":   qa["answer"],
            })
        return compiled
    
    # ─── Core ──────────────────────────────────────────────
    def _needs_escalation(self, text: str) -> bool:
        return any(pat.search(text) for pat in self._escalate_compiled)

    def _find_answer(self, text: str) -> str | None:
        for qa in self._qa_compiled:
            if any(pat.search(text) for pat in qa["patterns"]):
                return qa["answer"]()
        return None

    def chat(self, user_input: str) -> tuple[str, str]:
        """
        ประมวลผลข้อความจาก user
        Returns: (response_text, speaker)
        """
        text = user_input.strip()
        self.history.append({"role": "user", "content": text})
        log_message(
            session_id=self.session_id, platform=self.platform,
            user_id=self.user_id, role="user", content=text, mode=self.mode,
        )

        # ── Admin mode ──────────────────────────────────────
        if self.mode == "admin":
            resp = self._admin_reply(text)
            self._log_and_store("admin", resp)
            return resp, "admin"

        # ── 1) Escalation keywords ──────────────────────────
        if self._needs_escalation(text):
            return self._escalate(text)

        # ── 2) Pattern match (เร็ว แม่นยำ) ──────────────────
        answer = self._find_answer(text)
        if answer:
            self._log_and_store("bot", answer)
            return answer, "bot"

        # ── 3) Claude API (ฉลาด ยืดหยุ่น) ───────────────────
        if ANTHROPIC_API_KEY:
            claude_resp = self._ask_claude(text)
            if claude_resp:
                self._log_and_store("bot", claude_resp)
                return claude_resp, "bot"

        # ── 4) Fallback → escalate ───────────────────────────
        return self._escalate(text, unknown=True)

    # ─── Claude API ────────────────────────────────────────
    def _ask_claude(self, text: str) -> str | None:
        """ส่งคำถามไปให้ Claude API ตอบ"""
        try:
            # สร้าง conversation history สำหรับส่งให้ Claude
            # เอาแค่ 10 ข้อความล่าสุดเพื่อประหยัด token
            recent = [
                {"role": m["role"], "content": m["content"]}
                for m in self.history[-10:]
                if m["role"] in ("user", "assistant")
            ]
            # ถ้าไม่มี history ให้ใช้แค่ข้อความปัจจุบัน
            if not recent:
                recent = [{"role": "user", "content": text}]

            payload = json.dumps({
                "model":      CLAUDE_MODEL,
                "max_tokens": 300,
                "system":     SYSTEM_PROMPT,
                "messages":   recent,
            }).encode("utf-8")

            req = urllib.request.Request(
                CLAUDE_API_URL,
                data=payload,
                headers={
                    "Content-Type":      "application/json",
                    "x-api-key":         ANTHROPIC_API_KEY,
                    "anthropic-version": "2023-06-01",
                },
                method="POST",
            )

            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data["content"][0]["text"]

        except urllib.error.HTTPError as e:
            print(f"[Claude API] HTTP {e.code}: {e.read().decode()}")
            return None
        except Exception as e:
            print(f"[Claude API] error: {e}")
            return None

    # ─── Escalation ────────────────────────────────────────
    def _escalate(self, text: str, unknown: bool = False) -> tuple[str, str]:
        self.mode = "admin"
        log_escalation(self.session_id, self.platform, self.user_id, text)

        if unknown:
            msg = (
                "ขอโทษนะครับ/ค่ะ คำถามนี้หนูยังไม่สามารถตอบได้ 🙏\n"
                "กำลังแจ้ง Admin ให้เข้ามาช่วยโดยตรงเลยนะครับ/ค่ะ\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "🔔  [ระบบแจ้ง Admin แล้ว] รอสักครู่นะครับ/ค่ะ ⏳"
            )
        else:
            msg = (
                "รับทราบครับ/ค่ะ 🙏\n"
                "กำลังแจ้ง Admin ให้เข้ามาดูแลทันทีเลยนะครับ/ค่ะ\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "🔔  [ระบบแจ้ง Admin แล้ว] รอสักครู่นะครับ/ค่ะ ⏳"
            )

        self._log_and_store("bot", msg)
        return msg, "bot"

    def _admin_reply(self, text: str) -> str:
        return (
            "สวัสดีครับ/ค่ะ Admin เข้ามาแล้วนะครับ 👋\n"
            "รับทราบเรื่องแล้วครับ กำลังดำเนินการช่วยเหลือให้เลยนะครับ 😊"
        )

    def _log_and_store(self, role: str, content: str):
        self.history.append({"role": role, "content": content})
        log_message(
            session_id=self.session_id, platform=self.platform,
            user_id=self.user_id, role=role, content=content, mode=self.mode,
        )

    # ─── Helpers ───────────────────────────────────────────
    def reset(self):
        self.mode = "ai"
        self.history.clear()
        self.session_id = str(uuid.uuid4())[:8]
        log_session_start(self.session_id, self.platform, self.user_id)

    def get_history(self) -> list[dict]:
        return self.history.copy()
