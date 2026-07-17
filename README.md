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
cp .env.example .env               # fill in the secrets — see docs/05-manual-setup-checklist.md
python3 tools/lint.py --path vault  # "lint passed — 10 note(s) OK."
python3 -m pytest -q                # 108 passed, all offline (mock llm/embeddings, fake DB)
git config core.hooksPath hooks     # enable the pre-commit lint gate
```

Open `vault/` directly in Obsidian (see `vault/README.md` for the one-time
Dataview setup) and start replacing the notes tagged `example` with your own.

To run it for real:

```bash
python3 -m app.watcher --path vault --once   # process anything already in vault/inbox/
python3 -m app.watcher --path vault          # or stay running (Syncthing's target on your phone/NAS)
python3 -m app.bot.telegram_bot              # the Telegram bot — every command below lives here
```

**All commands**: capture (drop text/photo/voice), `/track <project-slug>
<hours> <desc>`, `/invoice <project-slug> <YYYY-MM>`, `/review` (confirm/
reject gap-engine proposals), `/idea <description>`, `/done <habit>`,
`/lift <exercise> <scheme> <load>`, `/next <exercise>`, `/ask <question>`.

**Read this next**: [`docs/05-manual-setup-checklist.md`](docs/05-manual-setup-checklist.md)
— every remaining manual step (secrets, scheduling, Syncthing, credential
rotation, the interview) as one walkthrough, in the order to actually do them.

## Start here

1. [`docs/00-PLAN.md`](docs/00-PLAN.md) — reconciliation notes: how the
   original design chat and the oslife audit fit together, and the one
   architecture decision (Postgres over SQLite) made on top of it.
2. [`docs/01-build-plan.md`](docs/01-build-plan.md) — the "what and why":
   the self-model/gap-engine, the four domain modules, the coach, the roadmap.
3. [`docs/02-data-structure-and-flow.md`](docs/02-data-structure-and-flow.md) —
   the canonical technical spec: vault tree, frontmatter contract, note type
   catalog, database schema, data flows, extension guides.
4. [`docs/03-engineering-build-spec.md`](docs/03-engineering-build-spec.md) —
   the original phase-by-phase Definition-of-Done spec this was built against.
5. [`docs/04-self-model-interview.md`](docs/04-self-model-interview.md) — fill
   this in yourself, whenever. Seeds `self/current`/`self/desired` — the one
   piece that needs you, not code.
6. [`docs/05-manual-setup-checklist.md`](docs/05-manual-setup-checklist.md) —
   the full walkthrough of what's left for you to do, across every phase.

## Status: every phase has code

| Phase | State | Notes |
|---|---|---|
| 0 — Foundation | Done | Vault, 18 templates, linter (+hook +CI), Dataview, auto-commit |
| 1 — Capture + normalize | Done | `llm.py`, watcher/normalizer/embedder, Telegram bot, live Supabase schema |
| 2 — Seed the self | **Parked, on purpose** | Needs you to fill in the interview; nothing else was blocked on it |
| 3 — CRM / freelance ops | Done (Gmail + file auto-filing deferred) | Billing rollup, NL invoicing + PDF, `/track` + `/invoice` |
| 4 — Gap engine v1 | Done, but inert until Phase 2 | metabolism + gap-review + `/review` propose→confirm |
| 5 — Daily coach | Done | Morning brief, live nudges, scheduling, self-compassion framing enforced |
| 6 — Business-idea evaluator | Done (intake+verdict); deep report needs Claude Code/Desktop | MCP server (live-tested) + `biz-eval` Skill + `/idea` |
| 7 — Health/Gym | Done, needs secrets + phone automation to carry real data | Edge Function ingestion (deployed) + training engine + `/next` |
| 8 — Extra functions | Done | Decision journal, weekly review, resurfacing, life-areas balance |
| 9 — Visual layer | Done | More Dataview boards + a Postgres→vault snapshot job; no custom UI (none was justified) |

**108 tests pass** (`python3 -m pytest -q`), all offline against a mock
LLM/embedding provider and a fake Postgres client — no secrets needed to
run the suite. Real-credential paths (Anthropic, Telegram, Supabase) were
verified live during the build, not just unit-tested; the Supabase Edge
Function and the evaluator's MCP server were each confirmed working over
their real protocols, not just imported.

**What "done" means here, precisely**: the code exists, is tested, and
(where it touches live infrastructure) was verified against your real
Supabase project once. It is **not** running anywhere continuously — this
repo doesn't host a server. Nothing was set up on your behalf that
required a browser, an OAuth consent screen, or a secret only you should
hold. See `docs/05-manual-setup-checklist.md` for the complete list of
what that leaves for you.

## Security note

An Anthropic API key, Supabase project URL, and Telegram bot token were
shared in chat during this build and used to verify things end-to-end —
none of them are in this repo (`.env` is gitignored; only `.env.example`
with blank placeholders is committed). Since they passed through a chat
transcript, treat them as potentially exposed: rotate the Telegram bot
token via @BotFather (`/revoke`) and regenerate the Anthropic key at
console.anthropic.com if you haven't already, then update your local `.env`.
