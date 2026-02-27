#!/usr/bin/env python3
"""
Extract a concise English summary (~1 min read) from the marketing report HTML.
Outputs plain text formatted for Feishu lark_md.

Usage: python extract_summary.py <report.html>
"""

import re
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# HTML utilities
# ---------------------------------------------------------------------------

def _find_all_divs(html: str, start_re) -> list[str]:
    """Return inner HTML of every top-level <div> whose opening tag matches start_re."""
    results = []
    pos = 0
    if isinstance(start_re, str):
        start_re = re.compile(re.escape(start_re), re.IGNORECASE)

    while pos < len(html):
        m = start_re.search(html, pos)
        if not m:
            break
        content_start = m.end()
        depth, scan = 1, content_start

        while scan < len(html) and depth > 0:
            nxt_open  = html.find('<div', scan)
            nxt_close = html.find('</div>', scan)
            if nxt_close == -1:
                break
            if nxt_open != -1 and nxt_open < nxt_close:
                depth += 1
                scan = nxt_open + 4
            else:
                depth -= 1
                if depth == 0:
                    results.append(html[content_start:nxt_close])
                    pos = nxt_close + 6
                    break
                scan = nxt_close + 6
        else:
            pos = content_start

    return results


def _clean(frag: str, max_chars: int = 0) -> str:
    """Strip HTML tags, decode entities, normalise whitespace."""
    frag = re.sub(r'<(?:script|style)[^>]*>.*?</(?:script|style)>',
                  '', frag, flags=re.DOTALL)
    frag = re.sub(r'<(?:br|p|li|h[1-6])[^>]*/?>',  '\n', frag, flags=re.IGNORECASE)
    frag = re.sub(r'<[^>]+>', '', frag)
    for ent, char in [('&amp;', '&'), ('&lt;', '<'), ('&gt;', '>'),
                      ('&nbsp;', ' '), ('&#39;', "'"), ('&quot;', '"')]:
        frag = frag.replace(ent, char)
    frag = re.sub(r'[ \t]+', ' ', frag)
    frag = '\n'.join(l.strip() for l in frag.splitlines())
    frag = re.sub(r'\n{3,}', '\n\n', frag).strip()
    if max_chars and len(frag) > max_chars:
        frag = frag[:max_chars].rsplit(' ', 1)[0] + '…'
    return frag


def _en_text(block: str) -> str:
    """Extract text only from lang="en" divs inside block, skip lang="zh"."""
    EN = re.compile(r'<div\s[^>]*lang=["\']en["\'][^>]*>', re.IGNORECASE)
    ZH = re.compile(r'<div\s[^>]*lang=["\']zh["\'][^>]*>', re.IGNORECASE)
    parts = []
    for en_inner in _find_all_divs(block, EN):
        # Blank out nested zh blocks
        sanitised = en_inner
        for zh_inner in _find_all_divs(en_inner, ZH):
            sanitised = sanitised.replace(zh_inner, '', 1)
        parts.append(_clean(sanitised))
    return '\n'.join(parts)


def _zh_text(block: str) -> str:
    """Extract text only from lang="zh" divs inside block, skip lang="en"."""
    ZH = re.compile(r'<div\s[^>]*lang=["\']zh["\'][^>]*>', re.IGNORECASE)
    EN = re.compile(r'<div\s[^>]*lang=["\']en["\'][^>]*>', re.IGNORECASE)
    parts = []
    for zh_inner in _find_all_divs(block, ZH):
        sanitised = zh_inner
        for en_inner in _find_all_divs(zh_inner, EN):
            sanitised = sanitised.replace(en_inner, '', 1)
        parts.append(_clean(sanitised))
    return '\n'.join(parts)


def _first_sentence(text: str, max_chars: int = 160) -> str:
    """Truncate to max_chars, preferring a sentence boundary."""
    if len(text) <= max_chars:
        return text
    chunk = text[:max_chars]
    for sep in ('. ', '! ', '? '):
        idx = chunk.rfind(sep)
        if idx > max_chars // 2:
            return chunk[:idx + 1] + '…'
    return chunk.rsplit(' ', 1)[0] + '…'


def _strip_emoji(text: str) -> str:
    return re.sub(
        r'[\U0001F300-\U0001FFFF\U00002600-\U000027BF\U0000FE00-\U0000FEFF]',
        '', text
    ).strip()


# ---------------------------------------------------------------------------
# Section extractors
# ---------------------------------------------------------------------------

def extract_header(html: str) -> list[str]:
    # The Feishu template already renders the title and date.
    # Only surface the Core Watch game list as a single orientation line.
    blocks = _find_all_divs(html, re.compile(r'<div\s[^>]*class=["\']header["\'][^>]*>'))
    if not blocks:
        return []
    text = _en_text(blocks[0])
    core_m = re.search(r'Core Watch:\s*(.+)', text)
    if core_m:
        return [f"🎮 {core_m.group(1).strip()}"]
    return []


def _card_title(card_html: str) -> str:
    """Extract clean game name from a card, stripping badge spans and emoji."""
    m = re.search(r'class=["\']card-title["\'][^>]*>(.*?)</div>', card_html, re.DOTALL)
    if not m:
        return '?'
    inner = m.group(1)
    # Remove <span class="tag ...">…</span> badge elements before cleaning
    inner = re.sub(r'<span\s[^>]*class=["\'][^"\']*tag[^"\']*["\'][^>]*>.*?</span>', '', inner, flags=re.DOTALL)
    return _strip_emoji(_clean(inner)).strip()


def extract_burst(html: str) -> list[str]:
    BURST = re.compile(r'<div\s[^>]*class=["\']card burst-card["\'][^>]*>', re.IGNORECASE)
    cards = _find_all_divs(html, BURST)
    if not cards:
        return []

    lines = ['**🚨 Burst Alert**']
    for card in cards:
        title = _card_title(card)

        en = _en_text(card)
        # "Trigger" subsection → first substantive paragraph
        trig_m = re.search(r'Trigger\s*\n(.+?)(?=\n[A-Z📌📈⚠🎯]|\Z)', en, re.DOTALL)
        desc = _first_sentence(
            trig_m.group(1).replace('\n', ' ').strip(), 130
        ) if trig_m else ''

        # Strip signal-classification prefixes like "Hard Signal — Global Launch:"
        # that are structural metadata, not readable narrative.
        desc = re.sub(
            r'^(Hard|Medium|Low)\s+Signal\s*[—–]\s*[\w\s]+:\s*', '', desc
        )
        lines.append(f"• **{title}** — {desc}")
    return lines


def extract_watch(html: str) -> list[str]:
    # Match only <div class="card"> — NOT "card burst-card"
    WATCH = re.compile(r'<div\s+class=["\']card["\']>', re.IGNORECASE)
    cards = _find_all_divs(html, WATCH)
    if not cards:
        return []

    lines = ['**🔍 Core Watch**']
    for card in cards[:3]:  # cap at 3 to keep the digest tight
        title = _card_title(card)

        en = _en_text(card)
        # First paragraph with >60 chars = community/social lead
        paras = [p.strip() for p in en.splitlines() if len(p.strip()) > 60]
        desc = _first_sentence(paras[0], 90) if paras else ''  # 140 → 90

        if title and desc:
            lines.append(f"• **{title}** — {desc}")
    return lines


def extract_radar(html: str) -> list[str]:
    # Radar items live directly inside lang="en" divs (no nested lang attr)
    EN = re.compile(r'<div\s[^>]*lang=["\']en["\'][^>]*>', re.IGNORECASE)
    RADAR = re.compile(r'<div\s[^>]*class=["\']radar-item["\'][^>]*>', re.IGNORECASE)

    en_items = []
    for en_block in _find_all_divs(html, EN):
        for radar_inner in _find_all_divs(en_block, RADAR):
            text = _clean(radar_inner).replace('\n', ' ').strip()
            if len(text) > 15:
                en_items.append(text[:110])

    if not en_items:
        return []
    lines = ['**🎯 On the Radar**']
    for item in en_items[:4]:
        lines.append(f"• {item}")
    return lines


# ---------------------------------------------------------------------------
# Chinese section extractors
# ---------------------------------------------------------------------------

def extract_burst_zh(html: str) -> list[str]:
    BURST = re.compile(r'<div\s[^>]*class=["\']card burst-card["\'][^>]*>', re.IGNORECASE)
    cards = _find_all_divs(html, BURST)
    if not cards:
        return []
    lines = ['**🚨 本周爆发**']
    for card in cards:
        title = _card_title(card)
        zh = _zh_text(card)
        paras = [p.strip() for p in zh.splitlines() if len(p.strip()) > 20]
        desc = _first_sentence(paras[0], 80) if paras else ''
        if title and desc:
            lines.append(f"• **{title}** — {desc}")
    return lines


def extract_watch_zh(html: str) -> list[str]:
    WATCH = re.compile(r'<div\s+class=["\']card["\']>', re.IGNORECASE)
    cards = _find_all_divs(html, WATCH)
    if not cards:
        return []
    lines = ['**🔍 重点关注**']
    for card in cards[:3]:
        title = _card_title(card)
        zh = _zh_text(card)
        paras = [p.strip() for p in zh.splitlines() if len(p.strip()) > 20]
        desc = _first_sentence(paras[0], 80) if paras else ''
        if title and desc:
            lines.append(f"• **{title}** — {desc}")
    return lines


def extract_radar_zh(html: str) -> list[str]:
    ZH   = re.compile(r'<div\s[^>]*lang=["\']zh["\'][^>]*>', re.IGNORECASE)
    RADAR = re.compile(r'<div\s[^>]*class=["\']radar-item["\'][^>]*>', re.IGNORECASE)
    zh_items = []
    for zh_block in _find_all_divs(html, ZH):
        for radar_inner in _find_all_divs(zh_block, RADAR):
            text = _clean(radar_inner).replace('\n', ' ').strip()
            if len(text) > 10:
                zh_items.append(text[:110])
    if not zh_items:
        return []
    lines = ['**🎯 雷达监测**']
    for item in zh_items[:4]:
        lines.append(f"• {item}")
    return lines


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def extract_summary(html_path: str) -> str:
    html = Path(html_path).read_text(encoding='utf-8', errors='ignore')

    # Prefer the pre-written summary block generated by the AI Agent
    m = re.search(
        r'<div[^>]*id=["\']wave-summary["\'][^>]*>(.*?)</div>',
        html, re.DOTALL | re.IGNORECASE
    )
    if m:
        return _clean(m.group(1))

    # Fallback: rule-based extraction for older reports without the summary block
    sections: list[list[str]] = [
        extract_header(html),
        extract_burst(html),
        extract_watch(html),
        extract_radar(html),
    ]

    parts = []
    for section in sections:
        if section:
            parts.append('\n'.join(section))

    return '\n\n'.join(parts)


def extract_summary_zh(html_path: str) -> str:
    html = Path(html_path).read_text(encoding='utf-8', errors='ignore')

    m = re.search(
        r'<div[^>]*id=["\']wave-summary-zh["\'][^>]*>(.*?)</div>',
        html, re.DOTALL | re.IGNORECASE
    )
    if m:
        return _clean(m.group(1))

    sections: list[list[str]] = [
        extract_burst_zh(html),
        extract_watch_zh(html),
        extract_radar_zh(html),
    ]
    parts = ['\n'.join(s) for s in sections if s]
    return '\n\n'.join(parts)


if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('report', help='HTML report file path')
    ap.add_argument('--lang', choices=['en', 'zh'], default='en')
    args = ap.parse_args()
    fn = extract_summary_zh if args.lang == 'zh' else extract_summary
    print(fn(args.report))
