# Calendar to Clockify timesheet

Turns your Google Calendar and a Slack sweep into Clockify time entries,
aggregated by customer and rounded to the hour. Built around a workflow where
an agent (e.g. Claude Code) does the data-gathering and classification-review
legwork with you, not a fire-and-forget script.

## How it actually works

There's no single push-button command — this is a multi-step, agent-assisted
workflow:

1. **Calendar data.** If you're running this through Claude Code, the
   easiest path is its own Google Calendar MCP connector (set up once in your
   Claude settings) — have it export your events for the date range into a
   JSON file shaped like `{"events": [...]}`. `scripts/fetch_events.py` +
   `src/auth/google_auth.py` are kept as an optional legacy path that talks
   to the Google Calendar API directly via OAuth, for anyone not using
   Claude Code.
2. **Slack sweep.** Search Slack for customer-relevant discussion that never
   made it onto the calendar (off-calendar debugging, incident response,
   async customer threads) and turn real findings into extra time-entry
   JSON, one dict per finding, shaped like `generate_timesheet.py --extra`
   expects (see any `data/slack_extras_*.json` you've already generated for
   the shape). This searches **by customer name/alias**, broadly across
   Slack — not by a fixed channel list (see "Why no Slack channel config?"
   below).
3. **Generate + review.**
   ```
   python scripts/generate_timesheet.py --start 2026-03-09 --end 2026-03-15 \
     --calendar-json data/calendar_mar9_mar15.json \
     --extra data/slack_extras_mar9_mar15.json \
     --output data/timesheet_mar9_mar15.json
   ```
   This prints a full breakdown (by day, by customer/category, grand total)
   and writes the Clockify payload to `--output`. **Always read the
   breakdown before submitting** — this is a dry run by default.
4. **Submit.** Once the breakdown looks right: re-run with `--submit` to
   actually create the entries in Clockify.
5. **Cross-check (optional).** `scripts/check_coverage.py` cross-references
   Claude Code session history (and, optionally, a local YAPA/ChromaDB
   instance) against the date range to surface work that might be missing
   from the calendar/Slack sweep. It's advisory only — it never writes to
   Clockify — and its default settings touch nothing outside this repo (see
   the privacy section below).

## Setup

**Start with [`SETUP.md`](SETUP.md)** — it's a short guided process (meant to
be run with an agent) that gets your Clockify API key, pulls your real
project/task catalog, and builds `config/config.yaml` by matching against
real IDs instead of guessed ones. You *can* hand-edit the YAML directly if
you prefer (it's just `config/config.yaml.example` copied and filled in),
but SETUP.md is the supported path.

Quick version if you're doing it by hand:

```
cp .env.example credentials/.env          # put your Clockify API key in here
cp config/config.yaml.example config/config.yaml   # fill in your real IDs
pip install -r requirements.txt
```

`config/config.yaml` holds everything account-specific: your Clockify
workspace/project/task IDs, your customer list (names, aliases, email
domains), your timezone, and your own classification pattern overrides. It's
gitignored — never commit it. `config/config.yaml.example` ships with
placeholder values only.

## Why no Slack-channel config?

Most customers have both an internal and an external Slack channel, so it's
tempting to store those in config. We don't: channel names get renamed,
customers get added to (and removed from) both Slack and Clockify over time,
and you aren't limited to billing only your "assigned" customers — you can
occasionally clock time against any of them. A static channel registry would
go stale and would also miss relevant discussion that happens outside a
customer's dedicated channel. Instead, the Slack-sweep step searches
dynamically every time it runs, using each customer's `aliases` from
`config.yaml` as search terms, broadly across Slack. Adding, removing, or
renaming a customer only ever means editing the one `customers` list.

## Privacy: `check_coverage.py`

By default, `check_coverage.py` touches **nothing outside this repo** and
makes **no network calls**. Two things are opt-in, both in `config.yaml`:

- `session_scan.mode` — gates whether it reads Claude Code session history
  from `~/.claude/projects`. `none` (default) scans nothing. `this_repo`
  scopes to just this project. `allowlist` scopes to paths you list
  explicitly. `all` scans every Claude Code project on your machine (useful
  if you do customer work across many repos, but it reads prompt text from
  everything, not just this tool) — only enable it if you understand that
  tradeoff.
- `yapa.enabled` — whether it also cross-references a local YAPA/ChromaDB
  instance. Off by default.

Override either per-run with `--session-scan-mode` / `--yapa` without
editing the config.

## What's in this repo

- `scripts/generate_timesheet.py` + `scripts/check_coverage.py` — the two
  scripts you actually run, day to day.
- `scripts/clockify_catalog.py` — prints your live Clockify project/task
  catalog; used by `SETUP.md`.
- `config/timesheet_config.py` — the config schema/loader these two scripts
  use.
- `scripts/fetch_events.py`, `scripts/validate_parsing.py`, `src/` — an
  earlier, more interactive calendar-sync approach (direct Google OAuth,
  cached classification review) that `config/settings.py` also serves. Kept
  as an alternative for anyone not using Claude Code's calendar connector;
  not required for the primary workflow above.
- `tests/` — unit tests for the classification/aggregation/mapping logic and
  the config loader. Run with `pytest`.

## Development

```
pip install -r requirements.txt
pytest
```
