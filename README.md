# TheBrain

A local-first second brain: one inbox for everything (thoughts, transactions,
health data, messages, articles, photos of letters), a self-model that tracks
the gap between who you are and who you want to become, and four domain
modules (freelance CRM, goals/OKRs/habits, a business-idea evaluator,
health/gym) — coached over Telegram, browsed in Obsidian.

Replaces `oslife` (which stays running in parallel until this covers what it
needs to and gets cut over deliberately, not on a deadline).

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

Planning complete. Phase 0 (foundation: vault, templates, linter, no AI, no
phone) has not been started yet. No NAS purchased yet — see `00-PLAN.md` for
why that's fine and what runs where in the interim.
