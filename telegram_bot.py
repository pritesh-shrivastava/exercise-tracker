#!/usr/bin/env python3
"""Telegram bot that logs workouts from chat messages.

Usage:
  1. Create a Telegram bot with BotFather
  2. Set TELEGRAM_BOT_TOKEN
  3. Optionally set TELEGRAM_ALLOWED_CHAT_ID to restrict logging to your DM/chat
  4. Run this script on the VPS
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from tracker_core import fetch_summary, format_summary, insert_lines

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_DB = BASE_DIR / "data" / "workouts.sqlite"
API_BASE = "https://api.telegram.org/bot{token}/{method}"


def env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def request_json(token: str, method: str, payload: dict | None = None) -> dict:
    url = API_BASE.format(token=token, method=method)
    if payload is None:
        req = urllib.request.Request(url, method="GET")
    else:
        body = urllib.parse.urlencode(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=body,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )
    with urllib.request.urlopen(req, timeout=70) as resp:
        return json.loads(resp.read().decode("utf-8"))


def send_message(token: str, chat_id: int | str, text: str) -> None:
    request_json(token, "sendMessage", {"chat_id": chat_id, "text": text})


def allowed_chat(message: dict, allowed_chat_id: str) -> bool:
    if not allowed_chat_id:
        return True
    return str(message.get("chat", {}).get("id")) == allowed_chat_id


def handle_message(token: str, db_path: Path, message: dict) -> None:
    chat_id = message.get("chat", {}).get("id")
    text = (message.get("text") or "").strip()
    if not text:
        return

    allowed_id = env("TELEGRAM_ALLOWED_CHAT_ID")
    if not allowed_chat(message, allowed_id):
        return

    if text.startswith("/help"):
        send_message(
            token,
            chat_id,
            "Send workout lines like:\n- squats 3x5 @ 100kg\n- 20 min zone 2 cardio\n- 5 km run in 28:30\n\nCommands:\n/summary - show stats\n/help - show this help",
        )
        return

    if text.startswith("/summary"):
        summary = fetch_summary(db_path)
        send_message(token, chat_id, format_summary(summary))
        return

    count = insert_lines(db_path, text, source="telegram")
    if count:
        send_message(token, chat_id, f"Logged {count} workout line(s).")
    else:
        send_message(token, chat_id, "Nothing to log from that message.")


def main() -> int:
    token = env("TELEGRAM_BOT_TOKEN")
    if not token:
        raise SystemExit("TELEGRAM_BOT_TOKEN is required")

    db_path = Path(env("WORKOUT_DB_PATH", str(DEFAULT_DB)))
    offset = 0
    print("Telegram workout logger running...")

    while True:
        try:
            payload = {"timeout": 50}
            if offset:
                payload["offset"] = offset
            data = request_json(token, "getUpdates", payload)
            if not data.get("ok"):
                print("Telegram API returned non-ok response:", data)
                time.sleep(5)
                continue

            for update in data.get("result", []):
                offset = max(offset, update["update_id"] + 1)
                message = update.get("message") or update.get("edited_message")
                if not message:
                    continue
                try:
                    handle_message(token, db_path, message)
                except Exception as exc:
                    chat_id = message.get("chat", {}).get("id")
                    if chat_id is not None:
                        try:
                            send_message(token, chat_id, f"Error logging workout: {exc}")
                        except Exception:
                            pass
                    print(f"Error handling message {message.get('message_id')}: {exc}")
        except urllib.error.HTTPError as exc:
            print(f"Telegram HTTPError: {exc}")
            time.sleep(5)
        except urllib.error.URLError as exc:
            print(f"Telegram URLError: {exc}")
            time.sleep(5)
        except KeyboardInterrupt:
            print("Exiting.")
            return 0


if __name__ == "__main__":
    raise SystemExit(main())
