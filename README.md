# TheBrain

A local-first second brain: one inbox for everything (thoughts, transactions,
health data, messages, articles, photos of letters), a self-model that tracks
the gap between who you are and who you want to become, and four domain
modules (freelance CRM, goals/OKRs/habits, a business-idea evaluator,
health/gym) — coached over Telegram, browsed in Obsidian.

Replaces `oslife` (which stays running in parallel until this covers what it
needs to and gets cut over deliberately, not on a deadline).

## Quick start (Phase 0 — built)

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python3 tools/lint.py --path vault      # should print "lint passed — 10 note(s) OK."
git config core.hooksPath hooks         # enable the pre-commit lint gate
```

Then open `vault/` directly in Obsidian (see `vault/README.md` for the
one-time Dataview setup) and start replacing the notes tagged `example`
with your own.

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
  four Dataview dashboards, nightly auto-commit script. No AI, no phone,
  no NAS needed — and none purchased yet (see `docs/00-PLAN.md` for why
  that's fine and what runs where in the interim).
- **Phase 1 (capture + normalize)** — not started. Needs: a fresh
  Supabase project (see `docs/00-PLAN.md`), a Telegram bot token, an
  Anthropic API key.
- **Phase 2 (seed the self)** — blocked on you filling in
  `docs/04-self-model-interview.md`, at your own pace, whenever.
- Phases 3-9: see `docs/03-engineering-build-spec.md` §11.
