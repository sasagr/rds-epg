# rds-epg

A tiny cloud-hosted **XMLTV EPG for the Italian channel _RDS Social TV_**.

No public XMLTV guide exists for RDS Social TV, but the channel is the television simulcast of RDS
radio — the same shows, with the studio on camera — so the station's own schedule at
[rds.it/palinsesto](https://www.rds.it/palinsesto) *is* the channel's schedule.
[`generate.py`](generate.py) reads that page, converts the next 7 days to XMLTV, and writes
[`rds.xml`](rds.xml). A GitHub Action re-runs it every 6 hours and commits the file, so any IPTV app
(TiViMate, Movie4All, …) can attach the guide to the channel with a plain URL.

## Deploy (once, ~2 minutes)

1. Create a **public** GitHub repo named `rds-epg` and add these four files:
   `generate.py`, `rds.xml`, `.github/workflows/epg.yml`, `README.md`.
2. Open the repo's **Actions** tab → enable workflows if prompted → select **“Generate RDS EPG”** →
   **Run workflow**. (It also runs automatically every 6 hours.)
3. Your EPG is now live at:
   `https://raw.githubusercontent.com/<your-username>/rds-epg/main/rds.xml`

## Add it to the app (Movie4All)

Settings ▸ IPTV ▸ edit the **RDS Social TV** channel:

| Field | Value |
|-------|-------|
| **EPG URL** | `https://raw.githubusercontent.com/<your-username>/rds-epg/main/rds.xml` |
| **EPG channel id / tvg-id** | `RDSSocialTV.it` — must be **exactly** this |

Then **Save & reload**. The channel will show now/next and a program list.

> The `tvg-id` must match the `channel=` id inside `rds.xml`. If the guide stays empty, that string is
> almost always the culprit — it has to be `RDSSocialTV.it`.

### CDN alternative
`https://cdn.jsdelivr.net/gh/<your-username>/rds-epg@main/rds.xml` — CDN-backed and fast, but caches
longer than the raw URL (which refreshes within ~5 minutes of each commit).

## Notes
- Times are emitted in Europe/Rome with a DST-correct offset (`+0200` summer / `+0100` winter).
- Each programme ends where the next begins, taken from the page's own running order rather than
  from the stated duration, so the guide has no holes in it.
- If the guide goes stale, the page's markup has moved: the run says so explicitly, and the fix is
  the handful of patterns at the top of `generate.py`. Nothing in the app needs to change.
- Data source: `www.rds.it/palinsesto`. This project just reformats a public schedule into XMLTV.

### Why not Tivù la Guida
Until November 2026 this read the DTT guide **Tivù la Guida** (`services.tivulaguida.it`, channel id
`255`). RDS stopped supplying it around 23 October 2026: the API kept answering, but its seven-day
window drained a day at a time — 162 programmes, then 161, 145, 121, 98, 75, 52, 29, 6, 1 — until on
2 November there were none and the run failed. The official page does not depend on a third party
being kept up to date, and carries thirteen days rather than seven.
