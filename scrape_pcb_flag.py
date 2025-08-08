#!/usr/bin/env python3
"""
Scrape Panama City Beach, FL daily beach flag status and append to a CSV.

- Primary source: PCB's official beach alerts iframe.
- Fallback: PCB Beach Safety page.

Creates/updates pcb_flags.csv with columns:
date_local,flag_text,normalized_flag,source_url,fetched_at_utc
"""

from __future__ import annotations
import csv
import datetime as dt
import re
import sys
from pathlib import Path
from typing import Optional

import requests
from bs4 import BeautifulSoup

IFRAME_URL = "https://www.visitpanamacitybeach.com/beach-alerts-iframe/"
FALLBACK_URL = "https://www.visitpanamacitybeach.com/safety/beach-safety/"
CSV_PATH = Path("pcb_flags.csv")
USER_AGENT = "pcb-flag-logger/1.0 (+https://github.com/yourname/pcb-flag-logger)"

# Known flag variants we’ll normalize
FLAG_ALIASES = {
    "green": {"green", "green flag"},
    "yellow": {"yellow", "yellow flag"},
    "purple": {"purple", "purple flag"},
    "single_red": {"single red", "single red flag", "red flag"},
    "double_red": {"double red", "double red flag"},
}

FLAG_PATTERN = re.compile(
    r"\b("
    r"double\s+red\s+flag|single\s+red\s+flag|red\s+flag|double\s+red|single\s+red|"
    r"yellow\s+flag|green\s+flag|purple\s+flag|yellow|green|purple|red"
    r")\b",
    re.IGNORECASE,
)

def _normalize_flag(raw: str) -> Optional[str]:
    s = raw.strip().lower()
    # prefer exact alias match
    for norm, variants in FLAG_ALIASES.items():
        if s in variants:
            return norm
    # fallback mappings
    if "double" in s and "red" in s:
        return "double_red"
    if "single" in s and "red" in s:
        return "single_red"
    if "red" in s:
        # If they just say "Red", assume single red (most common phrasing outside closures)
        return "single_red"
    if "yellow" in s:
        return "yellow"
    if "green" in s:
        return "green"
    if "purple" in s:
        return "purple"
    return None

def _fetch_text(url: str) -> str:
    r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=20)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    return soup.get_text(" ", strip=True)

def _extract_flag(text: str) -> Optional[str]:
    # Try to grab text after a "Current Beach Conditions" lead-in if present
    lead_idx = text.lower().find("current beach conditions")
    snippet = text[lead_idx: lead_idx + 240] if lead_idx != -1 else text

    m = FLAG_PATTERN.search(snippet)
    if not m:
        m = FLAG_PATTERN.search(text)

    if m:
        flag_text = m.group(0).strip()
        norm = _normalize_flag(flag_text)
        return flag_text if norm is not None else flag_text  # return raw; will normalize separately
    return None

def get_flag() -> tuple[str, str, str]:
    """Return (flag_text, normalized_flag, source_url). Raises on total failure."""
    # Primary source: iframe
    try:
        iframe_text = _fetch_text(IFRAME_URL)
        raw = _extract_flag(iframe_text)
        if raw:
            norm = _normalize_flag(raw) or ""
            return raw, norm, IFRAME_URL
    except Exception as e:
        print(f"[warn] iframe fetch failed: {e}", file=sys.stderr)

    # Fallback: safety page
    try:
        fall_text = _fetch_text(FALLBACK_URL)
        raw = _extract_flag(fall_text)
        if raw:
            norm = _normalize_flag(raw) or ""
            return raw, norm, FALLBACK_URL
    except Exception as e:
        print(f"[warn] fallback fetch failed: {e}", file=sys.stderr)

    raise RuntimeError("Could not determine flag status from known sources.")

def _read_rows(path: Path) -> list[list[str]]:
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8") as f:
        return list(csv.reader(f))

def _write_rows(path: Path, rows: list[list[str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerows(rows)

def main() -> int:
    # Use America/New_York date for "date_local"
    try:
        from zoneinfo import ZoneInfo
        tz = ZoneInfo("America/New_York")
    except Exception:
        # If ZoneInfo is missing for any reason, fall back to UTC (rare on Actions)
        tz = None

    now_utc = dt.datetime.now(dt.timezone.utc)
    now_local = now_utc.astimezone(tz) if tz else now_utc
    date_local = now_local.date().isoformat()

    flag_text, normalized, source_url = get_flag()

    # Ensure CSV exists with header
    rows = _read_rows(CSV_PATH)
    if not rows:
        rows = [["date_local", "flag_text", "normalized_flag", "source_url", "fetched_at_utc"]]

    # Update or append today’s row (idempotent daily run)
    header = rows[0]
    idx_date = header.index("date_local")
    idx_flag = header.index("flag_text")
    idx_norm = header.index("normalized_flag")
    idx_src = header.index("source_url")
    idx_fetched = header.index("fetched_at_utc")

    today_idx = None
    for i in range(1, len(rows)):
        if rows[i][idx_date] == date_local:
            today_idx = i
            break

    new_row = [
        date_local,
        flag_text,
        normalized,
        source_url,
        now_utc.isoformat(timespec="seconds").replace("+00:00", "Z"),
    ]

    if today_idx is None:
        rows.append(new_row)
        action = "append"
    else:
        rows[today_idx] = new_row
        action = "update"

    _write_rows(CSV_PATH, rows)

    print(f"[ok] {action}: {date_local} → {flag_text} (normalized={normalized or 'n/a'}) from {source_url}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
