#!/usr/bin/env python3
"""Generate an XMLTV EPG for the Italian channel "RDS Social TV".

There is no ready-made XMLTV feed for RDS Social TV anywhere public, but the official DTT guide
"Tivù la Guida" exposes its schedule as JSON (channel id 255). This script pulls the next few days,
converts it to XMLTV, and writes rds.xml — a static file a GitHub Action commits and serves, so an
IPTV app (TiViMate, Movie4All, …) can attach it to the channel by URL + tvg-id.

XMLTV consumers match programmes to a channel by the `channel=` attribute, so the tvg-id set in the
app MUST equal CHANNEL_ID below (default "RDSSocialTV.it").

Stdlib only — no pip install, runs on a stock GitHub Actions runner.
"""

import json
import sys
import urllib.request
from datetime import datetime, timedelta
from xml.sax.saxutils import escape
from zoneinfo import ZoneInfo

# --- config -------------------------------------------------------------------------------------
TIVU_CHANNEL_ID = 255                 # "RDS social TV" in the Tivù la Guida payload
CHANNEL_ID = "RDSSocialTV.it"         # XMLTV id → paste this exact string as the app's tvg-id
CHANNEL_NAME = "RDS Social TV"
CHANNEL_LOGO = "https://i.imgur.com/TY6FhqI.png"
DAYS_AHEAD = 7                        # how many days of guide to build
ROME = ZoneInfo("Europe/Rome")
API = ("https://services.tivulaguida.it/api/epg/programming/events/"
       "datestart/{start}%2000:00:00/dateend/{end}%2000:00:00")
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
      "(KHTML, like Gecko) Version/17.0 Safari/605.1.15")
OUT = "rds.xml"


def fetch_day(start: datetime, end: datetime) -> list:
    """Return RDS Social TV's events for one [start, end) day window, or [] on any failure."""
    url = API.format(start=start.strftime("%d-%m-%Y"), end=end.strftime("%d-%m-%Y"))
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=45) as r:
            data = json.load(r)
    except Exception as e:                                   # network/JSON hiccup → skip the day
        print(f"  ! {start:%d-%m-%Y}: {e}", file=sys.stderr)
        return []
    for ch in data.get("channels", []):
        if ch.get("id") == TIVU_CHANNEL_ID:
            return ch.get("events", []) or []
    return []


def parse_rome(s: str) -> datetime:
    """Tivù timestamps are 'DD-MM-YYYY HH:mm' in Europe/Rome (DST-aware)."""
    return datetime.strptime(s, "%d-%m-%Y %H:%M").replace(tzinfo=ROME)


def xmltv_ts(dt: datetime) -> str:
    """XMLTV wants 'YYYYMMDDHHMMSS +HHMM' — +0200 in summer (CEST), +0100 in winter."""
    return dt.strftime("%Y%m%d%H%M%S %z")


def main() -> int:
    today = datetime.now(ROME).replace(hour=0, minute=0, second=0, microsecond=0)

    programmes = []
    seen_ids = set()
    for offset in range(DAYS_AHEAD):
        day = today + timedelta(days=offset)
        for ev in fetch_day(day, day + timedelta(days=1)):
            eid = ev.get("id")
            if eid is not None and eid in seen_ids:          # events repeat across day windows
                continue
            if eid is not None:
                seen_ids.add(eid)
            prog = ev.get("program") or {}
            title = (prog.get("title") or "").strip()
            if not title or not ev.get("date_start") or not ev.get("date_end"):
                continue
            try:
                start = parse_rome(ev["date_start"])
                stop = parse_rome(ev["date_end"])
            except ValueError:
                continue
            desc = (prog.get("description") or "").strip()
            programmes.append((start, stop, title, desc))

    programmes.sort(key=lambda p: p[0])

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<!DOCTYPE tv SYSTEM "xmltv.dtd">',
        '<tv generator-info-name="rds-epg" source-info-name="Tivu la Guida">',
        f'  <channel id="{CHANNEL_ID}">',
        f'    <display-name>{escape(CHANNEL_NAME)}</display-name>',
        f'    <icon src="{escape(CHANNEL_LOGO)}" />',
        '  </channel>',
    ]
    for start, stop, title, desc in programmes:
        lines.append(f'  <programme start="{xmltv_ts(start)}" stop="{xmltv_ts(stop)}" channel="{CHANNEL_ID}">')
        lines.append(f'    <title lang="it">{escape(title)}</title>')
        if desc:
            lines.append(f'    <desc lang="it">{escape(desc)}</desc>')
        lines.append('  </programme>')
    lines.append('</tv>')

    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    print(f"Wrote {OUT}: {len(programmes)} programmes over {DAYS_AHEAD} day(s) for {CHANNEL_NAME}.")
    if not programmes:
        print("WARNING: no programmes — the Tivu API may be unreachable or channel id changed.",
              file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
