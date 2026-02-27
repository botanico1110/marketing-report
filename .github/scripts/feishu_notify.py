#!/usr/bin/env python3
"""
Send a Feishu (Lark) interactive card notification for a new marketing report.

Required environment variables:
  FEISHU_WEBHOOK_URL  - Feishu bot webhook URL
  REPORT_FILE         - e.g. game-marketing-report-W08-20260223.html
  REPORT_WEEK         - e.g. W08
  REPORT_DATE         - e.g. 2026-02-23
  REPORT_URL          - Full GitHub Pages URL with ?lang=en
"""

import os
import sys
import json
import re
import urllib.request
import urllib.error
from datetime import datetime, timedelta


def get_week_range(week_str: str, date_str: str) -> str:
    """Return a human-readable date range for the week, e.g. 'Feb 17 – 23, 2026'."""
    try:
        pub_date = datetime.strptime(date_str, "%Y-%m-%d")
        # ISO week: find Monday of that week
        monday = pub_date - timedelta(days=pub_date.weekday())
        sunday = monday + timedelta(days=6)
        if monday.month == sunday.month:
            return f"{monday.strftime('%b')} {monday.day}–{sunday.day}, {monday.year}"
        else:
            return f"{monday.strftime('%b')} {monday.day} – {sunday.strftime('%b')} {sunday.day}, {sunday.year}"
    except ValueError:
        return date_str


def build_card(week: str, date: str, url: str, latest_url: str) -> dict:
    week_range = get_week_range(week, date)
    return {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": f"🎮 Game Marketing Weekly {week} is out"
                },
                "template": "indigo"
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": (
                            f"**{week} · {week_range}**\n\n"
                            "本期游戏营销监测周报已发布 🚀\n"
                            "This week's report is ready for review."
                        )
                    }
                },
                {
                    "tag": "hr"
                },
                {
                    "tag": "action",
                    "actions": [
                        {
                            "tag": "button",
                            "text": {
                                "tag": "plain_text",
                                "content": "📖 Read Full Report (EN)"
                            },
                            "url": url,
                            "type": "primary"
                        },
                        {
                            "tag": "button",
                            "text": {
                                "tag": "plain_text",
                                "content": "🔗 Latest Report"
                            },
                            "url": latest_url,
                            "type": "default"
                        }
                    ]
                }
            ]
        }
    }


def send_webhook(webhook_url: str, payload: dict) -> None:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        webhook_url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        body = resp.read().decode("utf-8")
        result = json.loads(body)
        if result.get("code", 0) != 0:
            raise RuntimeError(f"Feishu API error: {result}")
        print(f"Feishu notification sent successfully. Response: {body}")


def main():
    webhook_url = os.environ.get("FEISHU_WEBHOOK_URL")
    report_file = os.environ.get("REPORT_FILE", "")
    report_week = os.environ.get("REPORT_WEEK", "")
    report_date = os.environ.get("REPORT_DATE", "")
    report_url  = os.environ.get("REPORT_URL", "")

    if not webhook_url:
        print("FEISHU_WEBHOOK_URL is not set — skipping notification.")
        sys.exit(0)

    if not report_url:
        print("REPORT_URL is empty — cannot send notification.")
        sys.exit(1)

    latest_url = "https://botanico1110.github.io/marketing-report/latest.html"

    payload = build_card(report_week, report_date, report_url, latest_url)

    print(f"Sending Feishu card for {report_file} ...")
    print(f"  Week : {report_week}")
    print(f"  Date : {report_date}")
    print(f"  URL  : {report_url}")

    try:
        send_webhook(webhook_url, payload)
    except urllib.error.HTTPError as e:
        print(f"HTTP error {e.code}: {e.read().decode()}")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
