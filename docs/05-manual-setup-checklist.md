# Manual setup checklist

Everything below is code-complete and tested (see the root `README.md`
status table) but needs a human step — a secret only you should hold, a
browser-based consent flow, a piece of hardware, or a judgment call.
Nothing in this list was skipped by accident; each item says why it
couldn't be done for you. Roughly in the order to actually do them —
earlier items unblock later ones.

## 0. Security — do this first, regardless of anything else

An Anthropic API key, a Supabase project URL, and a Telegram bot token
were pasted into this chat during the build and used to verify things
live. Treat anything that passed through a chat transcript as
potentially exposed:

- [ ] **Rotate the Telegram bot token**: message [@BotFather](https://t.me/BotFather) → `/revoke` on the `R_os_bot` token → update `TELEGRAM_BOT_TOKEN` in your local `.env`.
- [ ] **Regenerate the Anthropic API key**: console.anthropic.com → API keys → revoke the old one, create a new one → update `ANTHROPIC_API_KEY`.

## 1. Local machine setup

Pick any machine with Python 3.11+ — doesn't need to be the eventual NAS
(see `docs/00-PLAN.md`).

- [ ] `git clone` this repo, `python3 -m venv .venv && source .venv/bin/activate`
- [ ] `pip install -r requirements-dev.txt`
- [ ] `cp .env.example .env` — this file is gitignored; everything below fills it in
- [ ] `git config core.hooksPath hooks` — enables the pre-commit lint gate
- [ ] Confirm the basics work: `python3 tools/lint.py --path vault` and `python3 -m pytest -q` (both should pass with zero configuration — they don't touch real credentials)

## 2. Supabase credentials (unblocks Phase 1 capture)

The Supabase project ("TheBrain", `oavyzzvvlhgyxkagzmza`, separate from
oslife's) and its Postgres schema already exist — this is just wiring
your local `.env` to it.

- [ ] Supabase Dashboard → your "TheBrain" project → Project Settings → API → copy the **service_role** secret → `SUPABASE_SERVICE_ROLE_KEY` in `.env`
- [ ] Copy the Project URL → `SUPABASE_URL` in `.env` (should be `https://oavyzzvvlhgyxkagzmza.supabase.co`)
- [ ] Generate a stable user id, once, forever: `python3 -c "import uuid; print(uuid.uuid4())"` → `THEBRAIN_USER_ID` in `.env`

*(Not done for you on purpose: the service_role key bypasses row-level
security entirely — it's the one secret in this whole system I
specifically avoided fetching or generating on your behalf, even though
an MCP connector could technically reach it.)*

## 3. Telegram bot chat id (unblocks Phase 5's proactive coach)

- [ ] Start `python3 -m app.bot.telegram_bot` locally, message it `/start`
- [ ] It replies with your chat id — copy that into `TELEGRAM_CHAT_ID` in `.env`
- [ ] Without this, capture/`/track`/`/invoice`/etc. all still work (they reply to you directly) — only the morning brief and live nudges need it, since those messages aren't replies to anything

## 4. Business details (unblocks real `/invoice` output)

- [ ] `BUSINESS_NAME`, `BUSINESS_ADDRESS` in `.env`
- [ ] `BUSINESS_KVK_NUMBER` (KVK registration number)
- [ ] `BUSINESS_BTW_ID` (BTW/VAT id)
- [ ] `BUSINESS_IBAN`
- Until these are set, `/invoice` still generates a structurally-correct
  PDF, just with placeholder text where these values would go.

## 5. Obsidian

- [ ] Open the `vault/` folder (not the repo root) as a vault in Obsidian
- [ ] Settings → Community plugins → turn on community plugins → install + enable **Dataview** (already listed in `vault/.obsidian/community-plugins.json`, just needs your approval)
- [ ] Look at `_dashboards/*.md` — pipeline, deliverables, habits, gaps, goals, decisions all render live; `billing-snapshot.md`/`health-snapshot.md` render once the snapshot job has run at least once (see §7)
- [ ] Delete the notes tagged `example` once you've looked around, or replace them with real client/project/habit data (ask me to do this for you if you'd rather hand me the details than edit Obsidian directly)

## 6. Keep the bot running somewhere

This coding session doesn't persist — you need a machine that stays on
(a VPS, or your laptop while it's on; doesn't need to be the eventual
NAS). See `systemd/README.md` for the full reference; summary:

- [ ] The Telegram bot itself: a persistent systemd **service** (not timer) — `systemd/README.md` has the exact unit file — or run it in `screen`/`tmux` if you're cron-only
- [ ] `vault-autocommit` timer (23:45 daily)
- [ ] `thebrain-morning-brief` timer (07:30 daily) — needs §3 done first
- [ ] `thebrain-nudges` timer (every 2h, 08:00-20:00) — needs §3
- [ ] `thebrain-metabolism` timer (03:30 daily)
- [ ] `thebrain-gap-review` timer (Sunday 18:00) — harmless no-op until §9 (the interview) is done
- [ ] `thebrain-weekly-review` timer (Sunday 19:00)
- [ ] `thebrain-snapshot` timer (every 4h) — feeds the two Dataview snapshot boards

## 7. Optional: OCR / voice-note / PDF capture

Only needed if you want to drop screenshots, voice notes, or scanned
PDFs into the inbox (plain text and URLs already work without this):

- [ ] `pip install -r requirements-media.txt`
- [ ] Install the `tesseract-ocr` system package (`apt install tesseract-ocr` / `brew install tesseract`) for OCR
- [ ] `faster-whisper` downloads its model (~150MB for "base") on first use — no action needed, just expect a pause the first time

## 8. Optional: Syncthing (phone ↔ vault)

For dropping things into `inbox/` from your phone, and for browsing the
vault in Obsidian mobile:

- [ ] Install Syncthing on your phone and on whatever machine runs the watcher
- [ ] Share the `vault/` folder (or at least `vault/inbox/`) between them
- [ ] Android: a share-sheet target or an HTTP Shortcuts/Tasker action that saves shared text/images/audio into the synced `inbox/` folder gets you capture-from-anywhere without the Telegram bot

## 9. Phase 2 — the self-model interview (whenever, no rush)

- [ ] Fill in `docs/04-self-model-interview.md` at your own pace — partial answers are fine, this can be revisited
- [ ] Once filled in, tell me (or run the seeding step yourself) to generate the first `self/current`/`self/desired` notes
- This is what makes Phase 4 (gap engine) and Phase 6's fit-scoring
  produce real output instead of "no self-model data yet" — everything
  else in this system works without it, it's just less personalized.

## 10. Optional: Gmail comms log (Phase 3, deferred)

Not built — needs a browser-based OAuth consent flow this session
can't do:

- [ ] Google Cloud Console → create a project → enable the Gmail API → create an OAuth 2.0 client (Desktop app type)
- [ ] `GMAIL_OAUTH_CLIENT_ID` / `GMAIL_OAUTH_CLIENT_SECRET` in `.env`
- [ ] Ask me to write the actual polling/comms-log code once you have these — it wasn't built without credentials to test against

## 11. Optional: real web search for the business-idea evaluator (Phase 6)

`/idea` (fast verdict) works today with no setup. The **deep report**
(`.claude/skills/biz-eval/SKILL.md`, via `app/evaluator/mcp_server.py`)
needs actual web search for market research — `fetch_url` in the MCP
server only fetches a page you already have the URL for, it doesn't
discover sources:

- [ ] Connect `app/evaluator/mcp_server.py` as an MCP server in Claude Code/Desktop (`python3 -m app.evaluator.mcp_server`)
- [ ] For source *discovery*, use whatever web-search tool is available in that Claude Code/Desktop session — if none is connected there, get an API key from a search provider (Brave Search API, Serper, etc.) and ask me to wire it into a `web_search` tool on the MCP server
- [ ] Nothing here blocks the fast verdict — only the deep, cited report

## 12. Optional: Health Connect ingestion (Phase 7, deferred)

The Edge Function is deployed and confirmed rejecting unauthenticated
requests (401) — it needs two things before it does anything useful:

- [ ] Supabase Dashboard → your project → Edge Functions → `health-ingest` → Manage secrets → set `INGEST_SECRET` (any long random string you choose) and `THEBRAIN_USER_ID` (the **same** UUID from §2 — not settable via MCP, has to be you)
- [ ] On Android: an automation (Tasker, or an app that reads Health Connect and can make an HTTP POST) that sends `{"kind": "steps"|"sleep"|"hr", "value": ..., "ts": "..."}` to `https://oavyzzvvlhgyxkagzmza.supabase.co/functions/v1/health-ingest` with header `X-Ingest-Secret: <your INGEST_SECRET>`
- Until this exists, `/next <exercise>` still gives progressive-overload
  suggestions (+2.5kg per session) — it just never suggests a deload,
  since there's no sleep data to trigger one on.

## 13. Later: the NAS

Not needed for anything above — Supabase covers "always reachable"
today. Buy/set up hardware whenever it makes sense (cost, wanting full
local hosting, wanting a local LLM), then follow the `pg_dump`/
`pg_restore` migration path in `docs/00-PLAN.md`. Nothing else changes.

## Quick reference: what needs what

| To use... | You need (beyond §1) |
|---|---|
| Text/URL capture, `/ask` | §2 |
| `/track`, `/review`, `/done`, `/lift`, `/next` | §2 |
| Morning brief, live nudges | §2, §3 |
| `/invoice` (real, not placeholder) | §2, §4 |
| Screenshot/voice/PDF capture | §2, §7 |
| Phone-drop capture | §8 |
| Gap engine producing real proposals | §2, §9 |
| `/idea` fast verdict | §2 |
| `/idea` deep report | §2, §11 |
| Gmail comms log | §10 (not built yet either) |
| Health-based deload suggestions | §2, §12 |
