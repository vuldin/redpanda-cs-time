# Setup

This tool needs to know your real Clockify project/task IDs and your real
customer names before it can do anything useful — there's no way to guess
those correctly, so setup is a short guided conversation (ideally with an
agent like Claude Code) rather than a one-shot script.

If you're an agent running this with a human: follow the steps below in
order, don't skip ahead, and don't guess at an ID a human hasn't confirmed
against the live catalog in step 2.

## 1. Get a Clockify API key

Everything downstream depends on this, so nothing else proceeds without it.

1. Ask the person for their Clockify API key (from
   https://clockify.me/user/settings).
2. `cp .env.example credentials/.env`
3. Put the key in `credentials/.env` as `CLOCKIFY_API_KEY=...`.

## 2. Pull the live Clockify catalog

```
set -a && source credentials/.env && set +a
python scripts/clockify_catalog.py
```

This prints every project and task in the person's workspace, with real
IDs. Keep this output around — every ID you write into `config/config.yaml`
in the next steps should be copy-pasted from here, never typed from memory
or guessed.

If the person belongs to more than one workspace, the script lists them and
you'll need `--workspace-id <id>` on the next run.

## 3. Fill in the REQUIRED fields

`cp config/config.yaml.example config/config.yaml`

Walk through each of these with the person, matching against the catalog
from step 2. The tool won't run correctly until all of these are set:

- `clockify.workspace_id`
- `clockify.projects.customer` / `.admin` / `.technical_assets` / `.pto`
- `clockify.tasks.pto_vacation` / `.internal_meetings` / `.slack_catchup`
- at least one entry under `clockify.tasks.technical`, and
  `clockify.tasks.generic_technical_category_task` pointing at one of them
- `timezone` (an IANA name, e.g. `America/Chicago`, `America/New_York`,
  `Europe/London` — ask the person, don't guess from their calendar data)

## 4. Add customers

Loop: ask "add a customer?" For each yes, collect:

- a short canonical key (lowercase, e.g. `acme`)
- which Clockify project it bills to (a key from `clockify.projects`, or a
  literal project id from the catalog)
- its Clockify task id (from the catalog)
- any other names it shows up as in calendar titles or Slack (`aliases`)
- its email domain(s), if attendees' emails are a reliable signal (`domains`)

Repeat until the person says they're done. Zero customers is technically
allowed — the tool still runs, every event just lands in internal/unknown —
but say so plainly if someone tries to stop there; customers are where this
tool actually earns its keep.

Slack attribution is **not** configured here and needs no channel list: the
Slack-sweep step (part of the normal recurring workflow, not setup) searches
dynamically by each customer's `aliases`, broadly across Slack, every time it
runs — see the note in README.md. Channels get renamed and your customer
roster changes over time; a static channel registry would just go stale.

## 5. Walk the optional fields (skippable)

One line each, defaults are fine to keep:

- `title_overrides` / `title_regex_overrides` — exact or pattern-based title
  overrides for events that don't follow a clean naming convention.
- Extra `classification.*` patterns — beyond the generic ignore/internal
  defaults shipped in the example, for your own personal events
  (appointments, pet names, etc.) or coworker-name-specific internal 1:1s.
- `ooo.*` — explicit PTO dates; naturally empty until something comes up.
- `session_scan.*` — see the privacy note in README.md before changing this
  from the safe `none` default.
- `yapa.*` — only relevant if you run YAPA.

## 6. Validate

```
python3 -c "
from config.timesheet_config import load_timesheet_config, validate_timesheet_config
cfg = load_timesheet_config('config/config.yaml')
errors = validate_timesheet_config(cfg)
print(errors or 'OK - all required fields are set')
"
```

If anything required is still missing, go back to step 3 or 4 for just that
field — don't declare setup done with errors outstanding.

## 7. Dry run

Get a small real calendar export for the person (see README.md for how) and
run:

```
python scripts/generate_timesheet.py --start <date> --end <date> \
  --calendar-json <calendar.json> --output /tmp/dry-run.json
```

(No `--submit`.) Show the person the printed breakdown. This is the same
"always show the breakdown before submitting" step the tool uses for every
real period going forward — setup never submits anything on its own.
