#!/usr/bin/env python3
"""ちいかわベーカリー（Japanticket）の空き枠を監視して、新しい枠が出たらMac（とスマホ）に通知する。"""
import json
import os
import subprocess
import sys
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path

# ---- 設定 ----
PRODUCT_ID = 13995  # ちいかわベーカリーOSAKA ノベルティ付き優先入場券
PAGE_URL = "https://e.japanticket.com/shops/chiikawabakery_OSAKA/products/13995/"
OPEN_BROWSER = True  # 新しい枠が出たら予約ページを自動で開く（Macのみ）
NTFY_TOPIC = os.environ.get("NTFY_TOPIC")  # 設定されていればスマホ(ntfy)にも通知
# --------------

API = "https://api.japanticket.com/owned/vacancy/{pid}/{kind}?{q}"
STATE = Path(__file__).with_name("state.json")
LOG = Path(__file__).with_name("watch.log")
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/130 Safari/537.36",
    "Origin": "https://e.japanticket.com",
    "Referer": "https://e.japanticket.com/",
}


def get(kind, q):
    req = urllib.request.Request(API.format(pid=PRODUCT_ID, kind=kind, q=q), headers=HEADERS)
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)


def fetch_slots():
    """{'2026-12-01 17:35': 残数, ...} を返す（空きのある枠のみ）"""
    today = date.today()
    dates = get("date", f"stockDateFrom={today}&stockDateTo={today + timedelta(days=365)}")
    slots = {}
    for d in dates:
        if d.get("isOutOfInventory"):
            continue
        for s in get("timeperson", f"stockDate={d['date']}"):
            if s.get("isOffDate") or not s.get("availableCount"):
                continue
            slots[f"{s['stockDate']} {s['stockTime'][:5]}"] = s["availableCount"]
    return slots


def notify(title, msg, urgent=False):
    if sys.platform == "darwin":
        q = lambda s: json.dumps(s, ensure_ascii=False)
        script = f'display notification {q(msg)} with title {q(title)} sound name "Glass"'
        subprocess.run(["osascript", "-e", script])
    if NTFY_TOPIC:
        body = {"topic": NTFY_TOPIC, "title": title, "message": msg,
                "click": PAGE_URL, "priority": 5 if urgent else 3}
        req = urllib.request.Request("https://ntfy.sh/", data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=20)


def log(msg):
    line = f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {msg}"
    print(line)
    with LOG.open("a") as f:
        f.write(line + "\n")


def main():
    try:
        slots = fetch_slots()
    except Exception as e:
        log(f"取得エラー: {e}")
        return 1

    prev = json.loads(STATE.read_text()) if STATE.exists() else None
    STATE.write_text(json.dumps(slots, ensure_ascii=False, indent=1))

    if prev is None:
        log(f"初回チェック: 空き枠 {len(slots)} 件")
        notify("ちいかわベーカリー監視スタート", f"現在の空き枠: {len(slots)}件")
        return 0

    new = sorted(k for k in slots if k not in prev)
    log(f"空き枠 {len(slots)} 件 / 新規 {len(new)} 件")
    if new:
        days = sorted({k.split()[0] for k in new})
        summary = "、".join(d[5:].replace("-", "/") for d in days[:6]) + (" ほか" if len(days) > 6 else "")
        notify("🥐 ちいかわベーカリー 予約枠が出ました！", f"{len(new)}枠: {summary}", urgent=True)
        log("新規: " + ", ".join(new))
        if OPEN_BROWSER and sys.platform == "darwin":
            subprocess.run(["open", PAGE_URL])
    return 0


if __name__ == "__main__":
    sys.exit(main())
