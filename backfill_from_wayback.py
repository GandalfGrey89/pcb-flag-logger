#!/usr/bin/env python3
"""
Backfill historical beach flag statuses for Panama City Beach, FL using the
Internet Archive (Wayback Machine).

Outputs pcb_flags_historical.csv with:
date_local,flag_text,normalized_flag,source_url,wayback_ts,wayback_url,fetched_at_utc

Usage examples:
  python backfill_from_wayback.py --from-year 2022 --to-year 2025 --months 5,6,7,8
  python backfill_from_wayback.py --from-year 2023 --to-year 2023 --months 8

Notes:
- We ask Wayback for 1 snapshot per day (collapse to 8-digit date).
- We fetch the iframe first; if no flag text found, we try the safety page.
- We don’t try to guess the *exact* local date if the snapshot time crosses midnight;
  we record both the Wayback UTC timestamp and the derived local date for transparency.
"""

from __future__ import annotations
import argparse
import csv
import datetime as dt
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Iterable, Optional

import requests
from bs4 import BeautifulSoup

IFRAME_URL = "https://www.visitpanamacitybeach.com/beach-alerts-iframe/"
FALLBACK_URL = "https://www.visitpanamacitybeach.com/safety/beach-safety/"
CSV_PATH = Path("pcb_flags_historical.csv")
USER_AGENT = "pcb-flag-backfill/1.0 (+https://github.com/)"

# Same normalization as the daily scraper
FLAG_ALIASES = {
    "green": {"green", "green flag"},
    "yellow": {"yellow", "yellow flag"},
    "purple": {"purple", "purple flag"},
    "single_red": {"single red", "single red flag", "red flag"},
    "double_red": {"double red", "double red flag"},
}

def normalize_flag(raw: str) -> Optional[str]:
    s = raw.strip().lower()
    for norm, variants in FLAG_ALIASES.items():
        if s in variants:
            return norm
    if "double" in s and "red" in s:
        return "double_red"
    if "single" in s and "red" in s:
        return "single_red"
    if "red" in s:
        return "single_red"
    if "yellow" in s:
        return "yellow"
    if "green" in s:
        return "green"
    if "purple" in s:
        return "purple"
    return None

def extract_flag_text(html_text: str) -> Optional[str]:
    soup = BeautifulSoup(html_text, "html.parser")
    text = soup.get_text(" ", strip=True)
    t = text.lower()
    # Try tighter phrases first
    for key in ("double red flag", "single red flag", "red flag", "yellow flag", "green flag", "purple flag"):
        if key in t:
            return key.title()
    # Then looser single-word hits
    for key in ("double red", "single red", "yellow", "green", "purple", "red"):
        if key in t:
            return key.title()
    return None

def cdx_query(url: str, year_from: int, year_to: int) -> list[dict]:
    """
    Query Wayback CDX API for one snapshot per day (collapse=timestamp:8).
    """
    params = {
        "url": url,
        "output": "json",
        "from": str(year_from),
        "to": str(year_to),
        "filter": "statuscode:200",
        "collapse": "timestamp:8",
    }
    r = requests.get("https://web.archive.org/cdx/search/cdx", params=params, headers={"User-Agent": USER_AGENT}, timeout=30)
    r.raise_for_status()
    data = r.json()
    if not data or len(data) <= 1:
        return []
    cols = data[0]
    rows = [dict(zip(cols, row)) for row in data[1:]]
    return rows

def fetch_wayback(url: str, ts: str) -> str:
    # Use "id_/" to preserve original resource URLs
    wb = f"https://web.archive.org/web/{ts}id_/{url}"
    r = requests.get(wb, headers={"User-Agent": USER_AGENT}, timeout=30)
    r.raise_for_status()
    return r.text

def ensure_header(path: Path) -> None:
    if not path.exists():
        with path.open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["date_local","flag_text","normalized_flag","source_url","wayback_ts","wayback_url","fetched_at_utc"])

def append_row(path: Path, row: list[str]) -> None:
    with path.open("a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(row)

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--from-year", type=int, required=True, help="Start year, e.g. 2022")
    ap.add_argument("--to-year", type=int, required=True, help="End year inclusive, e.g. 2025")
    ap.add_argument("--months", type=str, default="", help="Comma list of months 1-12 to include (optional). Example: 5,6,7,8")
    args = ap.parse_args()

    months_filter: set[int] = set()
    if args.months.strip():
        months_filter = {int(m) for m in args.months.split(",")}

    # Query CDX for both sources
    iframe_snapshots = cdx_query(IFRAME_URL, args.from_year, args.to_year)
    fb_snapshots = cdx_query(FALLBACK_URL, args.from_year, args.to_year)
    all_snaps = []
    all_snaps.extend((IFRAME_URL, s["timestamp"]) for s in iframe_snapshots)
    all_snaps.extend((FALLBACK_URL, s["timestamp"]) for s in fb_snapshots)

    # Group by YYYYMMDD; prefer iframe when both exist
    by_day: dict[str, dict[str, str]] = defaultdict(dict)  # day -> {source_url: ts}
    for url, ts in all_snaps:
        day = ts[:8]
        by_day[day][url] = ts

    ensure_header(CSV_PATH)

    # Timezone for PCB (America/New_York)
    try:
        from zoneinfo import ZoneInfo
        tz = ZoneInfo("America/New_York")
    except Exception:
        tz = None

    now_utc = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
    fetched_at = now_utc.isoformat().replace("+00:00", "Z")

    days_processed = 0
    for day, sources in sorted(by_day.items()):
        y, m, d = int(day[:4]), int(day[4:6]), int(day[6:8])
        if months_filter and m not in months_filter:
            continue

        # Resolve a timestamp (prefer iframe, else fallback)
        if IFRAME_URL in sources:
            src_url = IFRAME_URL
            ts = sources[IFRAME_URL]
        else:
            src_url = FALLBACK_URL
            ts = sources.get(FALLBACK_URL)

        if not ts:
            continue

        try:
            html = fetch_wayback(src_url, ts)
            flag = extract_flag_text(html)
            if not flag:
                # Try the other source if we started with iframe
                if src_url == IFRAME_URL and FALLBACK_URL in sources:
                    html2 = fetch_wayback(FALLBACK_URL, sources[FALLBACK_URL])
                    flag = extract_flag_text(html2)
                    if flag:
                        src_url = FALLBACK_URL
                        ts = sources[FALLBACK_URL]
                elif src_url == FALLBACK_URL and IFRAME_URL in sources:
                    html2 = fetch_wayback(IFRAME_URL, sources[IFRAME_URL])
                    f2 = extract_flag_text(html2)
                    if f2:
                        flag = f2
                        src_url = IFRAME_URL
                        ts = sources[IFRAME_URL]

            if not flag:
                continue

            norm = normalize_flag(flag) or ""

            # Compute local date for the snapshot timestamp
            # Wayback ts is UTC: YYYYMMDDhhmmss
            dt_utc = dt.datetime.strptime(ts, "%Y%m%d%H%M%S").replace(tzinfo=dt.timezone.utc)
            dt_local = dt_utc.astimezone(tz) if tz else dt_utc
            date_local = dt_local.date().isoformat()

            wb_url = f"https://web.archive.org/web/{ts}id_/{src_url}"

            append_row(CSV_PATH, [date_local, flag, norm, src_url, ts, wb_url, fetched_at])
            days_processed += 1

        except requests.HTTPError as e:
            print(f"[warn] HTTP {e.response.status_code} for {src_url} at {ts}", file=sys.stderr)
        except Exception as e:
            print(f"[warn] {e}", file=sys.stderr)

    print(f"[ok] wrote {days_processed} day(s) to {CSV_PATH}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
