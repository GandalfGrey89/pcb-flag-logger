#!/usr/bin/env python3
"""
Logs the NWS Surf Zone Forecast for Coastal Bay (FLZ112) once per run.
Saves a tab-delimited CSV with a few parsed fields + the raw text for reference.

Output: data/noaa_pcb_srf_log.tsv
"""

import csv
import datetime as dt
import hashlib
import os
import re
import sys
from pathlib import Path

import requests

URL = "https://tgftp.nws.noaa.gov/data/forecasts/marine/surf_zone/fl/flz112.txt"
OUT = Path("data/noaa_pcb_srf_log.tsv")
OUT.parent.mkdir(parents=True, exist_ok=True)

HEADERS = [
    "fetched_utc",
    "issued_line",
    "rip_current_risk",
    "surf",
    "wind",
    "uv_index",
    "water_temp",
    "tides",
    "source_url",
    "raw_sha1",
    "raw_text",
]

# ---------- parsing helpers ----------

def fetch_text(url: str) -> str:
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    return r.text

def first_line_matching(pattern, text, flags=re.IGNORECASE):
    m = re.search(pattern, text, flags)
    return m.group(0).strip() if m else ""

def capture_value(pattern, text, group=1, flags=re.IGNORECASE):
    m = re.search(pattern, text, flags)
    return (m.group(group).strip() if m and m.group(group) else "").replace("..", ".")  # tiny cleanup

def parse_fields(txt: str) -> dict:
    # “ISSUED” or a top timestamp line (varies by office issuance style)
    issued = first_line_matching(r"(?i)^\s*(?:\w{3}\s+\w{3}\s+\d{1,2}.*|.*ISSUED.*)$", txt, flags=re.IGNORECASE | re.MULTILINE)

    # Common field formats used in Surf Zone text:
    risk = capture_value(r"(?i)rip\s*current\s*risk\W+\s*([A-Z][A-Z/\-\s]+)", txt)
    # Normalize to LOW/MODERATE/HIGH if present
    norm = ""
    for lvl in ("HIGH", "MODERATE", "LOW"):
        if lvl in risk.upper():
            norm = lvl
            break
    risk = norm or risk.upper()

    surf = capture_value(r"(?i)\bSURF\W+\s*([0-9]+(?:\s*(?:to|-)\s*[0-9]+)?\s*(?:ft|feet|foot)?)", txt)

    wind = capture_value(r"(?i)\bWIND\W+\s*(.+?)(?:\n|$)", txt)
    uv   = capture_value(r"(?i)\bUV\s*INDEX\W+\s*([A-Za-z0-9\s/+-]+)", txt)
    wtmp = capture_value(r"(?i)\bWATER\s*TEMPERATURE\W+\s*([0-9]+(?:\s*-\s*[0-9]+)?\s*(?:F|°F|C|°C)?)", txt)
    tide = capture_value(r"(?i)\bTIDE[S]?\W+\s*(.+?)(?:\n[A-Z ]{3,}:|\Z)", txt, flags=re.IGNORECASE | re.DOTALL)

    return {
        "issued_line": issued,
        "rip_current_risk": risk,
        "surf": surf,
        "wind": wind,
        "uv_index": uv,
        "water_temp": wtmp,
        "tides": " ".join(tide.split()) if tide else "",
    }

def sha1(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8")).hexdigest()

def load_existing_keys(path: Path):
    """Return a set of keys to help de-dupe. Key = sha1 of raw_text."""
    keys = set()
    if not path.exists():
        return keys
    with path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            if "raw_sha1" in row and row["raw_sha1"]:
                keys.add(row["raw_sha1"])
    return keys

def main():
    fetched_utc = dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    raw = fetch_text(URL)
    raw_hash = sha1(raw)
    fields = parse_fields(raw)

    # De-dupe: if the exact product text is already logged, skip
    seen = load_existing_keys(OUT)
    if raw_hash in seen:
        print("No change in SRF text; already logged. Exiting.")
        return

    write_header = not OUT.exists()
    with OUT.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=HEADERS, delimiter="\t")
        if write_header:
            w.writeheader()
        w.writerow({
            "fetched_utc": fetched_utc,
            "issued_line": fields["issued_line"],
            "rip_current_risk": fields["rip_current_risk"],
            "surf": fields["surf"],
            "wind": fields["wind"],
            "uv_index": fields["uv_index"],
            "water_temp": fields["water_temp"],
            "tides": fields["tides"],
            "source_url": URL,
            "raw_sha1": raw_hash,
            "raw_text": raw.replace("\r\n", "\n").strip(),
        })
    print(f"Logged SRF. Risk={fields['rip_current_risk']!r} Surf={fields['surf']!r}")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
