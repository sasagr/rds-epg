# rds-epg

A tiny cloud-hosted **XMLTV EPG for the Italian channel _RDS Social TV_**.

No public XMLTV guide exists for RDS Social TV, but the official DTT guide **Tivù la Guida** exposes its
schedule as JSON (channel id `255`). [`generate.py`](generate.py) pulls the next 7 days, converts it to
XMLTV, and writes [`rds.xml`](rds.xml). A GitHub Action re-runs it every 6 hours and commits the file,
so any IPTV app (TiViMate, Movie4All, …) can attach the guide to the channel with a plain URL.

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
- If the guide ever goes stale, Tivù la Guida likely changed its API or the channel id — fix
  `TIVU_CHANNEL_ID` / `CHANNEL_ID` in `generate.py`. Nothing in the app needs to change.
- Data source: `services.tivulaguida.it`. This project just reformats a public schedule into XMLTV.
