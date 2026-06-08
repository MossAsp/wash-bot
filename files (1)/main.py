#!/usr/bin/env python3
# ============================================================
# main.py — W&D Chatbot Terminal UI (v2)
# รัน: python main.py
# ============================================================

import sys
import textwrap
from chatbot import WDChatbot
from database import SHOP_INFO, SERVICES
from logger import get_stats

# ── ANSI Colors ────────────────────────────────────────────
class C:
    RESET  = "\033[0m"
    BOLD   = "\033[1m"
    DIM    = "\033[2m"
    GREEN  = "\033[32m"
    TEAL   = "\033[36m"
    YELLOW = "\033[33m"
    WHITE  = "\033[97m"
    BG_TEAL   = "\033[46m"
    BG_YELLOW = "\033[43m"
    BG_GRAY   = "\033[100m"


WRAP_WIDTH = 60


def wrap_text(text: str, width: int = WRAP_WIDTH) -> str:
    lines = text.split("\n")
    wrapped = []
    for line in lines:
        if len(line) <= width:
            wrapped.append(line)
        else:
            wrapped.extend(textwrap.wrap(line, width=width))
    return "\n".join(wrapped)


def print_bubble(text: str, speaker: str, mode: str = "ai"):
    lines = wrap_text(text).split("\n")

    if speaker == "user":
        prefix = f"{C.BG_GRAY}{C.WHITE} คุณ {C.RESET} "
        print()
        print(f"{prefix}{C.BOLD}{lines[0]}{C.RESET}")
        for line in lines[1:]:
            print(f"       {line}")

    elif speaker == "bot" and mode == "ai":
        prefix = f"{C.BG_TEAL}{C.WHITE} W&D {C.RESET} "
        print()
        print(f"{prefix}{C.TEAL}{C.BOLD}{lines[0]}{C.RESET}")
        for line in lines[1:]:
            print(f"       {C.TEAL}{line}{C.RESET}")

    elif speaker == "bot" and mode == "admin":
        prefix = f"{C.BG_TEAL}{C.WHITE} W&D {C.RESET} "
        print()
        print(f"{prefix}{C.YELLOW}{C.BOLD}{lines[0]}{C.RESET}")
        for line in lines[1:]:
            print(f"       {C.YELLOW}{line}{C.RESET}")

    elif speaker == "admin":
        prefix = f"{C.BG_YELLOW} 👤 Admin {C.RESET} "
        print()
        print(f"{prefix}{C.BOLD}{lines[0]}{C.RESET}")
        for line in lines[1:]:
            print(f"            {line}")


def print_header():
    print()
    print(f"{C.TEAL}{'━' * 52}{C.RESET}")
    print(f"{C.TEAL}{C.BOLD}  🧺  {SHOP_INFO['name']}  —  AI ผู้ช่วยออนไลน์{C.RESET}")
    print(f"{C.DIM}  📍 {SHOP_INFO['location']}  |  🕐 {SHOP_INFO['hours']}{C.RESET}")
    print(f"{C.TEAL}{'━' * 52}{C.RESET}")


def print_divider(label: str = ""):
    if label:
        print(f"\n{C.DIM}{'─' * 20} {label} {'─' * 20}{C.RESET}")
    else:
        print(f"{C.DIM}{'─' * 52}{C.RESET}")


def print_help():
    print(f"\n{C.DIM}คำสั่งพิเศษ:{C.RESET}")
    print(f"{C.DIM}  /help    — แสดงคำสั่ง{C.RESET}")
    print(f"{C.DIM}  /reset   — เริ่มสนทนาใหม่{C.RESET}")
    print(f"{C.DIM}  /price   — ดูตารางราคา{C.RESET}")
    print(f"{C.DIM}  /history — ดูประวัติ session นี้{C.RESET}")
    print(f"{C.DIM}  /stats   — ดูสถิติ log ทั้งหมด{C.RESET}")
    print(f"{C.DIM}  /quit    — ออกจากโปรแกรม{C.RESET}")


def print_price_table():
    print_divider("ตารางราคา")
    print(f"\n  {C.BOLD}{C.TEAL}🫧 เครื่องซักผ้า{C.RESET}")
    for w in SERVICES["washer"]:
        print(f"     {w['size']:25s} {C.GREEN}{w['price']} บาท{C.RESET}")

    d = SERVICES["dryer"]
    print(f"\n  {C.BOLD}{C.TEAL}☀️  เครื่องอบผ้า{C.RESET}")
    print(f"     เริ่มต้น ({d['base_minutes']} นาที)         {C.GREEN}{d['base_price']} บาท{C.RESET}")
    print(f"     เพิ่มเวลาทีละ 5 นาที         {C.GREEN}+{d['extra_per_5min']} บาท{C.RESET}")

    det = SERVICES["detergent"]
    print(f"\n  {C.BOLD}{C.TEAL}🧴 น้ำยาซักผ้า / ปรับผ้านุ่ม{C.RESET}")
    print(f"     ตู้อัตโนมัติ เริ่มต้น          {C.GREEN}{det['start_price']} บาท/ซอง{C.RESET}")
    print_divider()


def print_history(history: list[dict]):
    print_divider("ประวัติการสนทนา (session นี้)")
    if not history:
        print(f"  {C.DIM}(ยังไม่มีประวัติ){C.RESET}")
    for i, entry in enumerate(history, 1):
        role_map = {"user": "คุณ", "bot": "W&D", "admin": "Admin", "system": "System"}
        label   = role_map.get(entry["role"], entry["role"])
        content = entry["content"][:80] + ("…" if len(entry["content"]) > 80 else "")
        print(f"  {C.DIM}{i:2d}. [{label}] {content}{C.RESET}")
    print_divider()


def print_stats():
    s = get_stats()
    print_divider("สถิติ Log ทั้งหมด")
    if s.get("total") == 0:
        print(f"  {C.DIM}(ยังไม่มีข้อมูล){C.RESET}")
    else:
        print(f"  ข้อความทั้งหมด   : {C.GREEN}{s.get('total_messages', 0)}{C.RESET}")
        print(f"  Escalations      : {C.YELLOW}{s.get('escalations', 0)}{C.RESET}")
        print(f"  แยกตาม Platform  :")
        for p, c in s.get("by_platform", {}).items():
            print(f"    • {p:12s}: {c}")
        print(f"\n  📄 JSON : {C.DIM}{s.get('log_file_json')}{C.RESET}")
        print(f"  📄 CSV  : {C.DIM}{s.get('log_file_csv')}{C.RESET}")
    print_divider()


def print_mode_banner(mode: str):
    if mode == "admin":
        print(f"\n  {C.YELLOW}{C.BOLD}⚠️  Admin รับช่วงแล้ว — AI หยุดตอบชั่วคราว{C.RESET}")


def get_input(mode: str) -> str:
    if mode == "ai":
        prompt = f"\n{C.TEAL}คุณ › {C.RESET}"
    else:
        prompt = f"\n{C.YELLOW}คุณ (Admin online) › {C.RESET}"
    try:
        return input(prompt).strip()
    except (EOFError, KeyboardInterrupt):
        return "/quit"


def main():
    bot = WDChatbot(platform="terminal", user_id="local_user")

    print_header()
    print_help()

    welcome = (
        f"สวัสดีครับ/ค่ะ ยินดีต้อนรับสู่ร้าน {SHOP_INFO['name']} นะครับ 😊\n"
        "มีอะไรให้ช่วยไหมครับ? ถามได้เลยนะครับ"
    )
    print_bubble(welcome, "bot", "ai")

    prev_mode = "ai"

    while True:
        user_text = get_input(bot.mode)
        if not user_text:
            continue

        cmd = user_text.lower()

        if cmd in ("/quit", "/exit", "/q"):
            print(f"\n{C.TEAL}ขอบคุณที่ใช้บริการ W&D นะครับ 😊 แล้วพบกันใหม่ครับ!{C.RESET}\n")
            sys.exit(0)

        if cmd == "/help":
            print_help(); continue
        if cmd == "/price":
            print_price_table(); continue
        if cmd == "/reset":
            bot.reset(); prev_mode = "ai"
            print(f"\n{C.TEAL}🔄 เริ่มสนทนาใหม่แล้วครับ{C.RESET}")
            print_bubble(welcome, "bot", "ai"); continue
        if cmd == "/history":
            print_history(bot.get_history()); continue
        if cmd == "/stats":
            print_stats(); continue

        print_bubble(user_text, "user")
        response, speaker = bot.chat(user_text)

        if bot.mode == "admin" and prev_mode == "ai":
            print_mode_banner("admin")

        print_bubble(response, speaker, bot.mode)
        prev_mode = bot.mode


if __name__ == "__main__":
    main()
