# ============================================================
# line_bot.py — LINE Bot Webhook Server (v3) — fixed
# ============================================================

import os
from flask import Flask, request, abort

from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    Configuration, ApiClient, MessagingApi,
    ReplyMessageRequest, PushMessageRequest,
    TextMessage, FlexMessage, QuickReply, QuickReplyItem,
    MessageAction,
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent

from chatbot        import WDChatbot
from machine_status import get_summary_text, get_flex_message, set_busy
from wash_timer     import start_timer, cancel_timer, parse_timer_request, set_push_callback
from review         import (get_review_quick_reply, submit_review,
                            parse_star_rating, is_pending, set_pending,
                            get_stats as review_stats)
from admin_notify   import (set_line_api, notify_escalation,
                            notify_machine_error, notify_low_rating)
from logger         import get_stats

# ── โหลด .env ถ้ามี ─────────────────────────────────────────
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

app = Flask(__name__)

CHANNEL_SECRET       = os.getenv("LINE_CHANNEL_SECRET",       "YOUR_CHANNEL_SECRET")
CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "YOUR_CHANNEL_ACCESS_TOKEN")

configuration = Configuration(access_token=CHANNEL_ACCESS_TOKEN)
handler       = WebhookHandler(CHANNEL_SECRET)

# ── Sessions ─────────────────────────────────────────────────
_sessions: dict[str, WDChatbot] = {}

def get_bot(user_id: str) -> WDChatbot:
    if user_id not in _sessions:
        _sessions[user_id] = WDChatbot(platform="line", user_id=user_id)
    return _sessions[user_id]

# ── Push callback สำหรับ wash_timer ─────────────────────────
def _push_to_user(user_id: str, message: str):
    with ApiClient(configuration) as api_client:
        line_api = MessagingApi(api_client)
        line_api.push_message(
            PushMessageRequest(
                to=user_id,
                messages=[
                    TextMessage(
                        text=message,
                        quick_reply=QuickReply(items=[
                            QuickReplyItem(action=MessageAction(label="⭐ ให้คะแนน",  text="ให้คะแนนบริการ")),
                            QuickReplyItem(action=MessageAction(label="🏭 เช็คเครื่อง", text="เช็คสถานะเครื่อง")),
                        ])
                    )
                ]
            )
        )
        set_pending(user_id)

set_push_callback(_push_to_user)

# ── Webhook endpoint ─────────────────────────────────────────
@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers.get("X-Line-Signature", "")
    body      = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return "OK"

# ── Message handler ──────────────────────────────────────────
@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event: MessageEvent):
    user_id = event.source.user_id
    text    = event.message.text.strip()

    with ApiClient(configuration) as api_client:
        line_api = MessagingApi(api_client)
        set_line_api(line_api)

        # ── 1) รับรีวิว ────────────────────────────────────
        if is_pending(user_id) and ("รีวิว" in text or "⭐" in text):
            stars = parse_star_rating(text)
            if stars:
                reply = submit_review(user_id, stars)
                if stars <= 2:
                    notify_low_rating(user_id, stars)
                _reply_text(line_api, event.reply_token, reply)
                return

        # ── 2) เช็คสถานะเครื่อง ────────────────────────────
        if any(k in text for k in ["เช็คเครื่อง", "เครื่องว่าง", "สถานะเครื่อง",
                                   "เครื่องไหนว่าง", "ว่างไหม"]):
            flex = get_flex_message()
            line_api.reply_message(ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[FlexMessage(
                    alt_text=flex["altText"],
                    contents=flex["contents"],
                )]
            ))
            return

        # ── 3) ตั้ง timer ───────────────────────────────────
        if any(k in text for k in ["ตั้งเวลา", "จับเวลา", "แจ้งเตือนฉัน",
                                   "บอกเมื่อซักเสร็จ", "บอกเมื่ออบเสร็จ"]):
            minutes = parse_timer_request(text) or 30
            label   = "เครื่องอบ" if "อบ" in text else "เครื่องซัก"
            reply   = start_timer(user_id, minutes, label)
            _reply_text(line_api, event.reply_token, reply)
            return

        # ── 4) ยกเลิก timer ─────────────────────────────────
        if "ยกเลิกเวลา" in text or "ยกเลิกแจ้งเตือน" in text:
            ok    = cancel_timer(user_id)
            reply = "ยกเลิกการแจ้งเตือนแล้วครับ/ค่ะ ✅" if ok else "ไม่มีการแจ้งเตือนที่ค้างอยู่ครับ/ค่ะ"
            _reply_text(line_api, event.reply_token, reply)
            return

        # ── 5) ให้คะแนน ────────────────────────────────────
        if any(k in text for k in ["ให้คะแนน", "รีวิว", "ให้คะแนนบริการ"]):
            set_pending(user_id)
            qr_msg = TextMessage(
                text="ขอบคุณมากเลยครับ/ค่ะ 🙏 ช่วยให้คะแนนบริการด้วยได้ไหมครับ?",
                quick_reply=QuickReply(items=[
                    QuickReplyItem(action=MessageAction(label=s, text=f"รีวิว {s}"))
                    for s in ["⭐ 1", "⭐⭐ 2", "⭐⭐⭐ 3", "⭐⭐⭐⭐ 4", "⭐⭐⭐⭐⭐ 5"]
                ])
            )
            line_api.reply_message(ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[qr_msg]
            ))
            return

        # ── 6) Chatbot engine ───────────────────────────────
        bot = get_bot(user_id)
        response, speaker = bot.chat(text)

        if bot.mode == "admin" and speaker == "bot":
            reason = "keyword" if any(k in text for k in ["เสีย", "ลืมผ้า"]) else "unknown_question"
            notify_escalation(user_id, text, reason)
            if "เสีย" in text:
                notify_machine_error("ไม่ระบุ", user_id)

        qr  = _build_quick_reply(bot.mode)
        msg = TextMessage(text=response, quick_reply=qr) if qr else TextMessage(text=response)
        line_api.reply_message(ReplyMessageRequest(
            reply_token=event.reply_token,
            messages=[msg]
        ))

# ── Quick Reply builder ──────────────────────────────────────
def _build_quick_reply(mode: str) -> QuickReply | None:
    if mode == "admin":
        return None
    items = [
        QuickReplyItem(action=MessageAction(label="💰 ราคาซัก",    text="ซักผ้าราคาเท่าไร")),
        QuickReplyItem(action=MessageAction(label="☀️ ราคาอบ",     text="อบผ้าราคาเท่าไร")),
        QuickReplyItem(action=MessageAction(label="🏭 เช็คเครื่อง", text="เช็คสถานะเครื่อง")),
        QuickReplyItem(action=MessageAction(label="⏱️ ตั้งเวลา",    text="ตั้งเวลาซัก 30 นาที")),
        QuickReplyItem(action=MessageAction(label="📍 ที่ตั้งร้าน", text="ร้านอยู่ที่ไหน")),
        QuickReplyItem(action=MessageAction(label="⭐ ให้คะแนน",   text="ให้คะแนนบริการ")),
    ]
    return QuickReply(items=items)

def _reply_text(api, reply_token: str, text: str, quick_reply=None):
    msg = TextMessage(text=text, quick_reply=quick_reply) if quick_reply else TextMessage(text=text)
    api.reply_message(ReplyMessageRequest(reply_token=reply_token, messages=[msg]))

# ── Endpoints ────────────────────────────────────────────────
@app.route("/", methods=["GET"])
def index():
    return "W&D LINE Bot v3 is running! 🧺"

@app.route("/stats", methods=["GET"])
def stats():
    return {
        "chat_log": get_stats(),
        "reviews":  review_stats(),
        "sessions": len(_sessions),
    }

if __name__ == "__main__":
    print("=" * 52)
    print("  🧺  W&D LINE Bot v3")
    print("  📡  http://localhost:5000/callback  (webhook)")
    print("  📊  http://localhost:5000/stats     (dashboard)")
    print("=" * 52)
    print()
    if CHANNEL_SECRET == "YOUR_CHANNEL_SECRET":
        print("  ⚠️  ยังไม่ได้ตั้งค่า LINE credentials ใน .env")
        print("  คัดลอก .env.example → .env แล้วใส่ค่าครับ")
    print()
    app.run(port=5000, debug=True)
