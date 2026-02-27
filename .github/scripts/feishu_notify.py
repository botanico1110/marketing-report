#!/usr/bin/env python3
"""
Send a structured JSON payload to an enterprise internal-app webhook.
The enterprise automation parses the JSON variables and fills in the message template.

Required env vars:
  FEISHU_WEBHOOK_URL  — enterprise app webhook URL
  REPORT_FILE         — e.g. game-marketing-report-W08-20260223.html
  REPORT_WEEK         — e.g. W08
  REPORT_DATE         — e.g. 2026-02-23
  REPORT_URL          — full GitHub Pages URL with ?lang=en

Optional env vars:
  REPORT_SUMMARY      — English summary text
"""

import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta


def week_range(week_str: str, date_str: str) -> str:
    """Human-readable week span, e.g. 'Feb 17–23, 2026'."""
    try:
        pub = datetime.strptime(date_str, "%Y-%m-%d")
        mon = pub - timedelta(days=pub.weekday())
        sun = mon + timedelta(days=6)
        if mon.month == sun.month:
            return f"{mon.strftime('%b')} {mon.day}–{sun.day}, {mon.year}"
        return f"{mon.strftime('%b')} {mon.day} – {sun.strftime('%b')} {sun.day}, {sun.year}"
    except ValueError:
        return date_str


def build_payload(week: str, date: str, report_url: str, summary: str) -> dict:
    """
    Build a simple JSON payload for the enterprise app webhook.
    The enterprise automation will parse these fields as variables
    and inject them into the message template.
    """
    latest_url = "https://botanico1110.github.io/marketing-report/latest.html"
    span = week_range(week, date)

    return {
        "report_week": week,
        "week_span":   span,
        "report_date": date,
        "report_url":  report_url,
        "latest_url":  latest_url,
        "summary":     summary.strip() if summary.strip() else (
            f"{week} · {span}\n\n"
            "本期游戏营销监测周报已发布。\n"
            "This week's game marketing report is ready for review."
        ),
    }


def send(webhook_url: str, payload: dict) -> None:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        webhook_url,
        data=data,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        body = resp.read().decode("utf-8")
        print(f"✓ Webhook delivered. Response: {body}")
        # Enterprise apps vary in response format; we only fail on HTTP errors.


def main() -> None:
    webhook_url    = os.environ.get("FEISHU_WEBHOOK_URL", "")
    report_file    = os.environ.get("REPORT_FILE", "")
    report_week    = os.environ.get("REPORT_WEEK", "")
    report_date    = os.environ.get("REPORT_DATE", "")
    report_url     = os.environ.get("REPORT_URL", "")
    report_summary = os.environ.get("REPORT_SUMMARY", "")

    if not webhook_url:
        print("FEISHU_WEBHOOK_URL not set — skipping.")
        sys.exit(0)
    if not report_url:
        print("REPORT_URL is empty.", file=sys.stderr)
        sys.exit(1)

    print(f"Sending webhook for {report_file}")
    print(f"  Week    : {report_week}")
    print(f"  Date    : {report_date}")
    print(f"  URL     : {report_url}")
    print(f"  Summary : {len(report_summary)} chars")

    payload = build_payload(report_week, report_date, report_url, report_summary)
    print(f"  Payload : {json.dumps(payload, ensure_ascii=False, indent=2)}")

    try:
        send(webhook_url, payload)
    except urllib.error.HTTPError as exc:
        print(f"HTTP {exc.code}: {exc.read().decode()}", file=sys.stderr)
        sys.exit(1)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
