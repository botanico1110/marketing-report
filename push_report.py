#!/usr/bin/env python3
"""
Marketing Report Publisher
==========================
Copies new HTML report(s) from your local working directory to the repo,
updates latest.html, commits, and pushes to GitHub.
GitHub Actions will automatically send the Feishu notification after the push.

Usage
-----
  # Auto-detect new reports in default source directory:
  python push_report.py

  # Specify a file explicitly:
  python push_report.py "D:\\coding\\marketing-monitor-demo\\game-marketing-report-W09-20260302.html"

  # Specify a custom source directory:
  python push_report.py --source "D:\\other\\folder"

  # Force-push all HTML reports (including already-published ones):
  python push_report.py --all
"""

import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration — edit SOURCE_DIR to match your local export folder
# ---------------------------------------------------------------------------
SOURCE_DIR = r"D:\coding\marketing-monitor-demo"

# Repo root = folder containing this script
REPO_DIR = Path(__file__).parent.resolve()

# GitHub Pages base URL
PAGES_BASE = "https://botanico1110.github.io/marketing-report"

# Branch to push reports to
TARGET_BRANCH = "main"

# Pattern that identifies a valid weekly report filename
REPORT_PATTERN = re.compile(r".+-W\d{2}-\d{8}\.html$")
# ---------------------------------------------------------------------------


def find_reports_in(directory: str) -> list[Path]:
    """Return all HTML report files in *directory* matching the naming pattern."""
    try:
        all_html = Path(directory).glob("*.html")
    except FileNotFoundError:
        return []
    return sorted(p for p in all_html if REPORT_PATTERN.match(p.name))


def existing_report_names() -> set[str]:
    """Return names of HTML reports already committed to the repo root."""
    return {p.name for p in REPO_DIR.glob("*.html") if REPORT_PATTERN.match(p.name)}


def update_latest_html(report_filename: str) -> None:
    """Rewrite latest.html so it always redirects to the newest report (EN)."""
    target = f"./{report_filename}?lang=en"
    content = f"""\
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <meta http-equiv="refresh" content="0; url={target}">
  <script>window.location.replace('{target}');</script>
</head>
<body>Redirecting to latest report...</body>
</html>
"""
    (REPO_DIR / "latest.html").write_text(content, encoding="utf-8")
    print(f"  ✓ latest.html  →  {report_filename}?lang=en")


def git(args: list[str], check: bool = True) -> str:
    """Run a git command in the repo directory and return stdout."""
    result = subprocess.run(
        ["git"] + args,
        cwd=REPO_DIR,
        capture_output=True,
        text=True,
    )
    if check and result.returncode != 0:
        print(f"\n[git error] {' '.join(args)}")
        print(result.stderr.strip())
        sys.exit(1)
    return result.stdout.strip()


def ensure_on_target_branch() -> None:
    """Switch to TARGET_BRANCH if needed, then pull latest changes."""
    current = git(["rev-parse", "--abbrev-ref", "HEAD"])
    if current != TARGET_BRANCH:
        print(
            f"\n⚠  Current branch is '{current}', not '{TARGET_BRANCH}'.\n"
            f"   Reports are pushed to '{TARGET_BRANCH}' to keep GitHub Pages live.\n"
            f"   Switching to '{TARGET_BRANCH}' now..."
        )
        git(["checkout", TARGET_BRANCH])
    print(f"  ⬇  Pulling latest from origin/{TARGET_BRANCH} ...")
    git(["pull", "origin", TARGET_BRANCH])


def publish(src: Path) -> None:
    """Copy *src* into the repo, update latest.html, commit, and push."""
    filename = src.name
    dest = REPO_DIR / filename

    print(f"\n📤  Publishing: {filename}")

    # Copy file
    shutil.copy2(src, dest)
    print(f"  ✓ Copied from {src}")

    # Update stable redirect
    update_latest_html(filename)

    # Build a readable commit message
    m = REPORT_PATTERN.search(filename)
    week = re.search(r"W\d{2}", filename)
    date_raw = re.search(r"\d{8}", filename)
    week_tag  = week.group()      if week      else "report"
    date_part = date_raw.group()  if date_raw  else ""
    date_fmt  = (
        f"{date_part[:4]}-{date_part[4:6]}-{date_part[6:8]}"
        if len(date_part) == 8
        else ""
    )
    commit_msg = f"Add report: {week_tag}"
    if date_fmt:
        commit_msg += f" | {date_fmt}"
    commit_msg += " | Game Marketing Weekly"

    git(["add", filename, "latest.html"])
    git(["commit", "-m", commit_msg])
    print(f"  ✓ Committed: {commit_msg}")

    print(f"  ⬆  Pushing to origin/{TARGET_BRANCH} ...")
    git(["push", "-u", "origin", TARGET_BRANCH])

    pages_url = f"{PAGES_BASE}/{filename}?lang=en"
    print(f"\n  🌐 GitHub Pages URL (will be live in ~1 min):")
    print(f"     {pages_url}")
    print(f"\n  GitHub Actions will send the Feishu notification automatically.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Publish a marketing-report HTML to GitHub."
    )
    parser.add_argument(
        "files",
        nargs="*",
        help="Path(s) to HTML file(s) to publish. If omitted, scans SOURCE_DIR.",
    )
    parser.add_argument(
        "--source",
        default=SOURCE_DIR,
        metavar="DIR",
        help=f"Source directory to scan (default: {SOURCE_DIR})",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Publish all HTML reports found in source dir, including already-published ones.",
    )
    args = parser.parse_args()

    ensure_on_target_branch()

    if args.files:
        # Explicit file paths provided
        to_publish = [Path(f) for f in args.files]
        missing = [p for p in to_publish if not p.exists()]
        if missing:
            for p in missing:
                print(f"File not found: {p}")
            sys.exit(1)
    else:
        # Auto-discover from source directory
        print(f"🔍  Scanning: {args.source}")
        found = find_reports_in(args.source)
        if not found:
            print(f"No HTML report files found in {args.source}")
            sys.exit(0)

        if args.all:
            to_publish = found
        else:
            existing = existing_report_names()
            to_publish = [p for p in found if p.name not in existing]

        if not to_publish:
            print("No new reports to publish (all already in repo).")
            print("Use --all to force-republish.")
            sys.exit(0)

        print(f"Found {len(to_publish)} new report(s):")
        for p in to_publish:
            print(f"  • {p.name}")

    for src in to_publish:
        publish(src)

    print("\n✅  Done!")


if __name__ == "__main__":
    main()
