# TheBrain

A local-first second brain: one inbox for everything (thoughts, transactions,
health data, messages, articles, photos of letters), a self-model that tracks
the gap between who you are and who you want to become, and four domain
modules (freelance CRM, goals/OKRs/habits, a business-idea evaluator,
health/gym) — coached over Telegram, browsed in Obsidian.

Replaces `oslife` (which stays running in parallel until this covers what it
needs to and gets cut over deliberately, not on a deadline).

## Quick start

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env               # fill in the Phase 1 secrets — see below
python3 tools/lint.py --path vault  # "lint passed — 10 note(s) OK."
python3 -m pytest -q                # 24 passed, all offline (mock llm/embeddings)
git config core.hooksPath hooks     # enable the pre-commit lint gate
```

Open `vault/` directly in Obsidian (see `vault/README.md` for the one-time
Dataview setup) and start replacing the notes tagged `example` with your
own.

To run the capture pipeline for real:

```bash
python3 -m app.watcher --path vault --once   # process anything already in vault/inbox/
python3 -m app.watcher --path vault          # or stay running (Syncthing's target on your phone/NAS)
python3 -m app.bot.telegram_bot              # the Telegram bot (capture, /track, /done, /lift, /ask)
```

Needs `ANTHROPIC_API_KEY`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`,
`THEBRAIN_USER_ID`, and `TELEGRAM_BOT_TOKEN` in `.env` — see
`.env.example`. Never commit `.env`; it's gitignored.

## Start here

1. [`docs/00-PLAN.md`](docs/00-PLAN.md) — how this repo's docs relate to each
   other, the reconciliation notes between the original design chat and the
   oslife audit, and the one architecture decision (Postgres over SQLite)
   made after the original spec was written.
2. [`docs/01-build-plan.md`](docs/01-build-plan.md) — the "what and why":
   the self-model/gap-engine, the four domain modules, the coach, the
   roadmap.
3. [`docs/02-data-structure-and-flow.md`](docs/02-data-structure-and-flow.md) —
   the canonical technical spec: vault tree, frontmatter contract, note type
   catalog, database schema, data flows, extension guides.
4. [`docs/03-engineering-build-spec.md`](docs/03-engineering-build-spec.md) —
   the self-contained developer handoff: phases 0-9, each with a Definition
   of Done. Build strictly in phase order.
5. [`docs/04-self-model-interview.md`](docs/04-self-model-interview.md) — fill
   this in yourself, at your own pace. It seeds `self/current` and
   `self/desired`, the two models the whole system works to close the gap
   between. This is the one piece that needs you, not code — it gates
   Phase 2.

## Status

- **Phase 0 (foundation) — done.** Vault tree, 18 note-type templates,
  taxonomy/config/lint-rules, `tools/lint.py` (+ pre-commit hook + CI),
  four Dataview dashboards, nightly auto-commit script.
- **Phase 1 (capture + normalize) — done.** `app/llm.py` (Anthropic +
  mock provider, tier routing), `app/common/{config,db,frontmatter}.py`,
  `app/watcher.py` + `app/normalizer.py` (text/URL live; OCR/voice/PDF
  wired but need `requirements-media.txt` + system deps), `app/embedder.py`
  (pgvector, mock embedding provider until a worker host runs Ollama —
  see `docs/00-PLAN.md`), `app/bot/telegram_bot.py` (capture, `/track`,
  `/done`, `/lift`, `/ask` RAG). Postgres schema is live on a fresh
  Supabase project ("TheBrain", separate from oslife's) — see
  `supabase/migrations/`. 24 tests pass offline against the mock
  provider; the real Anthropic key and Telegram bot token were verified
  live. **Not yet done**: nothing is running continuously anywhere (this
  repo doesn't host a server) — you still need to run
  `python3 -m app.watcher` and `python3 -m app.bot.telegram_bot` on
  whatever machine will keep them alive (a VPS, or your laptop while
  it's on) per `docs/00-PLAN.md`. `SUPABASE_SERVICE_ROLE_KEY` and
  `THEBRAIN_USER_ID` in `.env.example` are still yours to fill in (grab
  the key from the Supabase dashboard; generate the UUID once and keep
  it forever).
- **Phase 2 (seed the self)** — blocked on you filling in
  `docs/04-self-model-interview.md`, at your own pace, whenever.
- Phases 3-9: see `docs/03-engineering-build-spec.md` §11.

## Security note

An Anthropic API key, Supabase project URL, and Telegram bot token were
shared in chat during this build and used to verify Phase 1 end-to-end —
none of them are in this repo (`.env` is gitignored; only `.env.example`
with blank placeholders is committed). Since they passed through a chat
transcript, treat them as potentially exposed: rotate the Telegram bot
token via @BotFather (`/revoke`) and regenerate the Anthropic key at
console.anthropic.com if you haven't already, then update your local
`.env`.
