#!/usr/bin/env python3
"""Generate an XMLTV EPG for the Italian channel "RDS Social TV".

RDS Social TV is the television simulcast of RDS radio — the same shows, with the studio on
camera — so the station's own schedule at rds.it/palinsesto *is* the channel's schedule, and it
is the only source that comes straight from the broadcaster.

This replaces the Tivù la Guida API (channel id 255), which stopped being supplied with RDS
listings after 1 November 2026: its seven-day window drained a day at a time from 23 October
until nothing was left. The official page is better on every count — one request instead of
seven, thirteen days instead of seven, every day a gapless 24 hours, and the presenters named.

XMLTV consumers match programmes to a channel by the `channel=` attribute, so the tvg-id set in
the app MUST equal CHANNEL_ID below (default "RDSSocialTV.it"). It is unchanged from the Tivù
version on purpose: nothing in any IPTV app needs touching.

Stdlib only — no pip install, runs on a stock GitHub Actions runner.
"""

import html
import re
import sys
import urllib.request
from datetime import datetime, timedelta
from xml.sax.saxutils import escape
from zoneinfo import ZoneInfo

# --- config -------------------------------------------------------------------------------------
SOURCE = "https://www.rds.it/palinsesto"
CHANNEL_ID = "RDSSocialTV.it"         # XMLTV id → paste this exact string as the app's tvg-id
CHANNEL_NAME = "RDS Social TV"
CHANNEL_LOGO = "https://i.imgur.com/TY6FhqI.png"
DAYS_AHEAD = 7                        # how many days of guide to build
ROME = ZoneInfo("Europe/Rome")
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
      "(KHTML, like Gecko) Version/17.0 Safari/605.1.15")
OUT = "rds.xml"

# Each programme is one <div class="palisesto-programma … data-YYYY-MM-DD …"> carrying its start
# time, title, duration and presenters. Scraping rather than an API because the page has no JSON
# endpoint — so these patterns are the brittle part, and each is checked rather than assumed.
BLOCK = re.compile(r'<div class="palisesto-programma ')
DATE = re.compile(r"\bdata-(\d{4}-\d{2}-\d{2})\b")
TIME = re.compile(r"palisesto-orario[^>]*>\s*<span>\s*([0-2]\d:[0-5]\d)\s*</span>")
TITLE = re.compile(r"titolo-programma[^>]*>(.*?)</div>", re.S)
DURATION = re.compile(r"durata-programma[^>]*>\s*Durata\s*([^<]+?)\s*</div>")
PRESENTER = re.compile(r"conduttori/[^']*'>([^<]+)</a>")


def text(fragment: str) -> str:
    """Tag soup to plain text, entities and all."""
    return html.unescape(re.sub(r"<[^>]+>", "", fragment)).strip()


def minutes(duration: str):
    """'2h', '1h 30min', '45min' → minutes. None when it says something unexpected."""
    hours = re.search(r"(\d+)\s*h", duration)
    mins = re.search(r"(\d+)\s*min", duration)
    if not hours and not mins:
        return None
    return int(hours.group(1) if hours else 0) * 60 + int(mins.group(1) if mins else 0)


def fetch() -> str:
    req = urllib.request.Request(SOURCE, headers={
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "it-IT,it;q=0.9",
    })
    with urllib.request.urlopen(req, timeout=45) as r:
        return r.read().decode("utf-8", "replace")


def parse(page: str) -> list:
    """Every programme on the page as (start, stop, title, presenters), in order.

    The page lists each day as a broadcast day running 05:00 to 05:00, so its last entry or two
    fall after midnight and belong to the *next* calendar day. The wrap is detected rather than
    assumed from any particular hour: within one day's list the times only ever move forward, so
    a time lower than the one before it is the following morning.
    """
    found = []
    for block in BLOCK.split(page)[1:]:
        day, time_, title = DATE.search(block), TIME.search(block), TITLE.search(block)
        if not (day and time_ and title):
            continue
        name = text(title.group(1))
        if not name:
            continue
        duration = DURATION.search(block)
        found.append({
            "day": datetime.strptime(day.group(1), "%Y-%m-%d").date(),
            "time": datetime.strptime(time_.group(1), "%H:%M").time(),
            "title": name,
            "minutes": minutes(duration.group(1)) if duration else None,
            "presenters": [text(p) for p in PRESENTER.findall(block)],
        })

    programmes = []
    previous_day, rolled = None, 0
    for item in found:
        if item["day"] != previous_day:
            previous_day, rolled, last = item["day"], 0, None
        elif item["time"] < last:
            rolled += 1
        last = item["time"]
        start = datetime.combine(item["day"], item["time"], tzinfo=ROME) + timedelta(days=rolled)
        programmes.append((start, item["minutes"], item["title"], item["presenters"]))

    # One wheel per day means consecutive days interlock exactly, and a page refreshed mid-scrape
    # could otherwise list the same slot twice.
    programmes.sort(key=lambda p: p[0])
    unique = []
    for programme in programmes:
        if not unique or programme[0] != unique[-1][0]:
            unique.append(programme)
    return unique


def xmltv_ts(dt: datetime) -> str:
    """XMLTV wants 'YYYYMMDDHHMMSS +HHMM' — +0200 in summer (CEST), +0100 in winter."""
    return dt.strftime("%Y%m%d%H%M%S %z")


def main() -> int:
    try:
        page = fetch()
    except Exception as e:
        print(f"could not read {SOURCE}: {e}", file=sys.stderr)
        return 1

    schedule = parse(page)
    if not schedule:
        # The page answered but nothing came out of it, which means its markup moved. Said plainly,
        # because the fix is to re-read the page and mend the patterns above — nothing else.
        print(f"no programmes parsed from {SOURCE} — its markup has changed.", file=sys.stderr)
        return 1

    today = datetime.now(ROME).replace(hour=0, minute=0, second=0, microsecond=0)
    horizon = today + timedelta(days=DAYS_AHEAD)

    # The stop time comes from the next programme's start rather than the stated duration: the two
    # agree throughout the page, and taking the gap is what guarantees a guide with no holes in it
    # even on a day where a duration is written in some form this does not read.
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<!DOCTYPE tv SYSTEM "xmltv.dtd">',
        '<tv generator-info-name="rds-epg" source-info-name="RDS (rds.it/palinsesto)">',
        f'  <channel id="{CHANNEL_ID}">',
        f'    <display-name>{escape(CHANNEL_NAME)}</display-name>',
        f'    <icon src="{escape(CHANNEL_LOGO)}" />',
        '  </channel>',
    ]
    written = 0
    for index, (start, length, title, presenters) in enumerate(schedule):
        if start >= horizon:
            break
        if index + 1 < len(schedule):
            stop = schedule[index + 1][0]
        elif length:
            stop = start + timedelta(minutes=length)
        else:
            continue                                   # last one, and no duration to end it with
        if stop <= today:                              # already over
            continue
        lines.append(f'  <programme start="{xmltv_ts(start)}" stop="{xmltv_ts(stop)}" '
                     f'channel="{CHANNEL_ID}">')
        lines.append(f'    <title lang="it">{escape(title)}</title>')
        if presenters:
            lines.append(f'    <desc lang="it">{escape("Con " + ", ".join(presenters))}.</desc>')
            lines.append('    <credits>')
            for presenter in presenters:
                lines.append(f'      <presenter>{escape(presenter)}</presenter>')
            lines.append('    </credits>')
        lines.append('  </programme>')
        written += 1
    lines.append('</tv>')

    if not written:
        # Parsed fine, but nothing lands in the window — the page is stale rather than broken.
        # The existing rds.xml is left exactly as it is: an EPG a few days old still works, and
        # an empty one replaces a working guide in every app with nothing at all.
        print(f"nothing within the next {DAYS_AHEAD} days — {OUT} left unchanged.", file=sys.stderr)
        return 1

    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    last = min(horizon, schedule[-1][0])
    print(f"Wrote {OUT}: {written} programmes for {CHANNEL_NAME}, "
          f"through {last:%a %d %b %H:%M}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
