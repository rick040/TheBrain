# Second Brain — Engineering Build Specification (Developer Handoff)

**Version**: 1.1 (updated: Postgres replaces SQLite; model IDs corrected;
oslife-reuse notes added — see `00-PLAN.md` for the reasoning) · **Audience**:
the engineer(s) building this · **Status**: ready to start Phase 0
**Companion docs**: `01-build-plan.md` (rationale), `02-data-structure-and-flow.md`
(data spec), `04-self-model-interview.md` (profile seed input, filled in by
the user, not the engineer)

This document is self-contained: an engineer can start from here alone. The
companion docs add rationale; every fact needed to build is repeated below.

## 0. How to use this document

Build **strictly in phase order** (§11). Each phase has a **Definition of
Done (DoD)**; do not start a phase until the prior phase's DoD is met. Each
phase produces something usable on its own — this is the anti-mess
guarantee. Sections §1-§10 are reference; §11 is the work plan; §12-§17 are
guardrails.

## 1. Product vision & goals

A local-first personal knowledge + telemetry system ("second brain") for a
freelancer with ADHD. It:

1. **Captures anything** (text, URL, screenshot, voice note, photo, PDF) through one frictionless inbox.
2. **Normalizes** every input into structured Markdown or a database row (OCR / transcription / extraction).
3. **Stores** it in two tiers — a human-facing Obsidian vault and a machine-facing Postgres store.
4. **Runs a brain** that finds patterns, maintains a model of the user, and proactively coaches — but is fully optional; the store works with the AI switched off.
5. **Works toward one overarching goal**: closing the gap between the user's current self (derived from data) and desired self (seeded by interview, refined over time), generating north-stars → OKRs → habits from that gap.

Four domain modules sit on top: CRM/freelance-ops, Goals/OKR/Habits,
Business-Idea Evaluator, Health/Gym.

## 2. Principles & hard constraints (non-negotiable)

| # | Principle | Implication for the build |
|---|---|---|
| P1 | Local-first | Vault + capture are local/synced; telemetry runs on Postgres (Supabase now, self-hosted NAS later). No required cloud service except transport (Telegram) and the LLM API (swappable/optional). |
| P2 | AI is additive | Store, retrieve, tag (via frontmatter/Dataview) must work with zero AI. All model calls behind one `llm()` abstraction. |
| P3 | Minimal third-party dependencies | Prefer FOSS the user can self-host. Every external dep must be justified and swappable. |
| P4 | Zero-friction capture | One inbox, no filing decisions by the user, ever. (ADHD constraint — friction = abandonment.) |
| P5 | Two stores | Markdown for interactive knowledge; Postgres for high-frequency telemetry. Never store per-minute data in `.md`. |
| P6 | Schema-by-convention | Notes self-describe via a universal frontmatter contract; a linter enforces it so the AI can edit safely. |
| P7 | Nuance is structural | The self-model stores traits with confidence, context, and held contradictions — never binary good/bad. |
| P8 | Self-compassion guardrail | The coach must be tunable and must not become a shame machine; rest/acceptance are first-class states. |
| P9 | Extensible | Adding a source/type/trigger/module follows a documented checklist (§14) with no core changes. |
| P10 | Privacy | Sensitive data encrypted at rest (§12.1) and, during the Supabase interim, never leaves the local vault (§12.1). No sensitive data in URLs/logs. |

## 3. Target environment & tech stack

**Hardware**: none required yet. Phases 0-6 run on a laptop + Supabase, no
purchase needed. A NAS/mini-PC (x86, 32GB RAM, SSD, Linux) only becomes
relevant around Phase 7, and only if/when you want full local hosting or a
GPU for local LLM. See `00-PLAN.md` for the Supabase-now → NAS-later
migration path (it's a `pg_dump`/`pg_restore`, not a rewrite).

**Runtime**: Supabase (Postgres + pgvector + Storage + Edge Functions) for
the telemetry/brain layer; Python 3.11+ for workers that can't run in Deno
Edge Functions (OCR, transcription, the normalizer, the gap-engine) — run
these on a small always-on VPS (~€5/mo) or batch them on your own machine;
systemd timers (or Supabase scheduled functions / pg_cron) for scheduled
jobs.

| Concern | Choice | Notes |
|---|---|---|
| Knowledge store | Obsidian vault (Markdown + YAML) | Human-facing. Dataview plugin for in-app queries. |
| Telemetry store | **Postgres + pgvector** (Supabase now, self-hosted later) | See `00-PLAN.md`. RLS on from day one. |
| Version history | git | Auto-commit vault nightly; history = undo/merge trail. |
| Phone ↔ vault sync | Syncthing | Local, no cloud. Primary capture transport from phone. |
| Location | OwnTracks (self-hosted MQTT/HTTP) | → telemetry `kind=location`. |
| Android capture | HTTP Shortcuts / Tasker + share-sheet | Drops into a Syncthing'd inbox folder. |
| OCR | Tesseract (`pytesseract`) | Images/scanned PDFs. |
| Transcription | `faster-whisper` | Voice notes. CPU-ok; GPU faster. |
| URL extraction | `trafilatura` | Clean article text. |
| Embeddings | local model via Ollama (e.g. `nomic-embed-text`) or a hosted embedding API until a worker host exists | CPU-ok. |
| LLM | Anthropic API, behind `llm()` | Default Haiku; strong-routing (§7.5). Local Ollama optional later. |
| Coach transport | Telegram Bot API | Two-way + push. Fully-local alt: ntfy + local chat UI. |
| Encryption | gocryptfs | Sensitive subtrees only (§12.1). |
| Orchestration | Python + systemd timers (or Supabase scheduled Edge Functions in the interim) | Visual n8n optional later; not required. |

## 4. System architecture

```
PHONE (Android)                          Wherever Python workers run
┌────────────────┐   Syncthing      (VPS now / NAS later)
│ share-sheet ───┼──────────────▶  ┌──────────────────────────────────────────┐
│ voice / photo  │                 │ inbox/ ──▶ [WATCHER] ──▶ [NORMALIZER]     │
│ OwnTracks ─────┼──HTTP─────────▶ │           OCR/Whisper/trafilatura         │
└────────────────┘                 │           llm() → {frontmatter,body}     │
                                    │                    │                     │
API SOURCES                        │  route: telemetry? ─▶ Postgres (Supabase)│
┌────────────────┐                 │        knowledge?  ─▶ VAULT (.md)        │
│ Gmail API ├──poll───────────────▶│                    │                     │
│ Health Connect ├──export───────▶ │           [EMBEDDER] ─▶ pgvector          │
└────────────────┘                 │  ┌── SCHEDULED BRAIN JOBS ──┐             │
                                    │  │ metabolism (nightly)      │           │
Anthropic API ◀───llm()───────────┼──┤ gap-review (weekly)       │           │
(Haiku default, Sonnet/Opus strong) │  │ coach: morning brief + nudges│        │
                                    │  │ evaluator (on demand, MCP)│           │
Telegram ◀──push / two-way────────┼──└───────────────────────────┘           │
                                    │  git (nightly commit) · gocryptfs (sensitive) │
                                    └──────────────────────────────────────────┘
```

Components (all Python unless noted):
- **watcher** — filesystem watch on `inbox/` (`watchdog`).
- **normalizer** — type detection, text extraction, `llm()` structuring, routing.
- **embedder** — computes + stores embeddings in pgvector.
- **brain jobs** — metabolism, gap-review, coach, evaluator (§6, §8, §9).
- **telegram bot** — capture commands, coach delivery, two-way chat.
- **linter** — frontmatter/schema validation (git pre-commit).
- **evaluator MCP server** — exposes vault read/write + web search to the `biz-eval` skill.

## 5. Data model (authoritative)

Full detail lives in `02-data-structure-and-flow.md`. Summary:

- **Vault** (`.md` + YAML) — interactive knowledge. Git-versioned.
- **Postgres** (Supabase now / self-hosted later) — high-frequency machine data + `insights` + `embeddings` (pgvector). RLS scoped to the single user from day one.
- Universal frontmatter contract, note-type catalog, `trait`/`gap` schemas, telemetry SQL: see `02-data-structure-and-flow.md` §4-§6.
- Config (`_system/config.yaml`): see `02-data-structure-and-flow.md` §11 — includes the `llm()` tier routing (`default` = Haiku, `strong` = Sonnet, `escalate` = Opus on-demand for the metabolism self-model pass, the gap-review synthesis, and the evaluator's deep report).

## 6. Core component specifications

### 6.1 Watcher + Normalizer
- **In**: any file in `inbox/`. **Out**: a vault `.md` or an `events` row; original moved to `inbox/_processed/`.
- Steps: detect type → extract text (Tesseract | faster-whisper | trafilatura | passthrough) → `llm(default)` returns `{frontmatter, body}` JSON → classify telemetry vs knowledge → write/insert → embed.
- **DoD**: dropping each of `{txt, url, png screenshot, m4a voice note, pdf}` yields a correctly-typed, lint-passing note or event, plus an embedding, within 60s; original archived; failures logged and left in `inbox/_failed/`.

### 6.2 Embedder
- Compute embedding for note body / event summary; upsert into the Postgres `embeddings` table (pgvector). Batch nightly + on-write.

### 6.3 Metabolism job (nightly)
- For notes changed since last run: reconcile against existing notes on shared entities; resolve or mark contradictions (`hold`), refresh freshness, re-tag, bump `updated`, propose taxonomy merges. Updates `self/current` traits from new evidence (adjust confidence). Run this pass on `tier=strong` or `tier=escalate` — a cheap model silently mis-revising the self-model is worse than the cost of a stronger one (see `00-PLAN.md`).
- **DoD**: re-running is idempotent; no data loss; contradictions surfaced not silently overwritten; git diff is reviewable.

### 6.4 Linter (`lint.py`)
- Validate every note vs §4 (data spec) + type rules in `_system/lint-rules.md` (required fields, enum values, link resolution, ISO dates). Runs as git pre-commit hook and in CI.
- **DoD**: an invalid note blocks commit with a precise error; clean vault passes.

### 6.5 Telegram bot
- Commands: capture (free text/media → inbox), `/track <client> <hours> "<desc>"`, `/done <habit>`, `/lift <exercise> <scheme> <load>`, `/ask <question>` (RAG over embeddings), `/idea <text>` (starts evaluator intake).
- Delivers coach messages (§8.6). Two-way: replies logged/actioned. **All writes to `self/` and anything involving money go through a propose → confirm step here** — reuse oslife's `confirm_inference()` + Telegram `infer:` callback-button pattern (see `00-PLAN.md`) rather than designing this from scratch.
- **DoD**: each command creates the correct note/event; unknown input is captured as an inbox note; secrets not logged.

## 7. External integrations

| Integration | Direction | Method | Notes / DoD |
|---|---|---|---|
| Syncthing | phone→vault | folder sync | `inbox/` folder syncs; conflict files handled. |
| OwnTracks | phone→worker | HTTP/MQTT | writes `events kind=location {place}`; self-hosted recorder. |
| Gmail | pull | Gmail API (read-only OAuth) | poll for new mail from client addresses → append to client comms log (`brain-only` detail). Never sends. |
| Health Connect | pull | Android export → parser | steps/sleep/hr → `events`; `brain-only`. No wearable yet; phone-only to start. |
| Anthropic API | call | HTTPS behind `llm()` | see §7.5. Supports tool use, MCP servers, web search, streaming — verify current model IDs/pricing at `docs.claude.com` at build time. |
| Telegram | two-way | Bot API | transport only; content stays local/in your Postgres project. |
| gocryptfs | — | mount | sensitive subtrees (§12.1). |
| Supabase | storage + compute | Postgres/pgvector/Storage/Edge Functions | interim host for telemetry+brain; see `00-PLAN.md` for the NAS migration path. |

### 7.5 The `llm()` abstraction (critical)

Single module `llm.py` exposing `llm(prompt, *, tier="default", tools=None) -> str|json`.

- `tier="default"` → Haiku (`claude-haiku-4-5-20251001`): normalization, tagging, coach messages, routine metabolism.
- `tier="strong"` → Sonnet (`claude-sonnet-5`): evaluator deep report, gap-review synthesis.
- `tier="escalate"` → Opus (`claude-opus-4-8`), on-demand only: the metabolism pass that revises `self/current` traits (see §6.3) — optional, gate it the same way the deep report already is (only runs when explicitly invoked or on a slow cadence, not every night).
- Provider is config-driven; adding a local Ollama provider must require **no caller changes**.
- **DoD**: switching provider/model is a config edit only; a mock provider lets all jobs run offline in tests.

## 8. Self-model & gap engine (the spine — full spec)

See `01-build-plan.md` Part B for rationale; this section is the
implementation contract.

### 8.1 Two models
- `self/current/*` — descriptive `trait` notes, written **only by the brain**, never the user. Grows/sharpens from data.
- `self/desired/*` — aspirational `desired` notes, seeded from the interview, editable by the user.

### 8.2 Seeding (from `04-self-model-interview.md`)
On receipt of a filled interview: `llm(strong)` produces (a)
`self/desired/{north-star,identity,aspirations,no-gos}.md`; (b) first-pass
`self/current/*` traits at low confidence (≤0.3) flagged as hypotheses; (c)
preserves raw answers as `profile-seed.md`; (d) an initial `self/gap/*` set.

### 8.3 Gap-review job (weekly, `tier=strong`)
1. refresh `self/current` from the week's data (confidence, contexts)
2. diff current ↔ desired → upsert `self/gap/*` (size, tension, hold?)
3. for each gap with `hold=false` and no active proposal: propose an OKR + keystone habit (write drafts, flag `needs_user_ok`)
4. for uncertain gaps (low-confidence traits): propose an identity experiment
5. ingest experiment results → refine BOTH current and desired (the desired self may be revised — it is a hypothesis)
6. run life-areas balance check; flag neglected areas

Nuance rules: never delete traits (revise/retire); never auto-resolve a
`hold:true` gap; **all user-facing changes are proposals until confirmed
via Telegram** (reuse oslife's confirm/reject pattern here).

**DoD**: produces reviewable proposals, not silent changes; respects
`hold`; idempotent; a dry-run mode prints proposed diffs.

### 8.4 Identity experiments
`experiment` notes: hypothesis + protocol + end date + measure. On
completion, results update the models. Change is framed as learning, not
pass/fail.

### 8.5 Decision journal
`decision` notes with `expected` + `review_on`. A job re-opens them on
`review_on`, asks (via coach) for the actual outcome, and feeds accuracy
back into `self/current/decision-style`.

### 8.6 Coach (daily, `tier=default`)
- **Morning brief** (07:30, time-shifted per energy-mood): today's deliverables/deadlines, KR progress, streaks-at-risk, the single top gap/priority.
- **Live nudges** (threshold triggers): overdue deliverable, unbilled hours > threshold, stale lead, missed habit, focus-window prompt.
- **Escalation**: firmer on broken streaks/slipping OKRs — tunable, and gated by `energy-mood` + `anti-patterns` so it pushes when tolerable, backs off when not.
- **Self-compassion guardrail (enforce)**: frame as "becoming," not "failing"; rest/play/acceptance are valid states, not gaps; honor `hold:true`; provide a global intensity dial + snooze.
- **DoD**: briefs generate on schedule; nudges fire on real thresholds only (no spam); intensity dial demonstrably changes tone/frequency; quiet windows respected.

## 9. Business-Idea Evaluator (MCP + skill)

Trigger: `/idea <text>` or "evaluate this idea" in chat. Flow (3 stages):

1. **Intake** — `llm` asks 5-8 targeted questions; pre-fills from `self/current` (skills, anti-patterns) + finances so it doesn't re-ask.
2. **Fast verdict** (default, no web) — one card: verdict, `idea_score` /10, `fit_score` /10, biggest risk, "the one thing that must be true", offer deep report.
3. **Deep report** (strong + web search, on demand) — saved to `ideas/idea--<slug>.md`: exec summary; market TAM/SAM/SOM (cited); competition; financial model (startup cost, unit economics, break-even, time-to-first-revenue, 12-mo P&L sketch, funding need); go-to-market; risks + kill-criteria; fit-for-you (maps to self-model, brutally honest); NL quick-setup guide (§10).

Implementation: a self-hosted MCP server exposing (a) vault read/write
(scoped), (b) web search/fetch, to a `biz-eval` skill that encodes the
analyst workflow + report template. Uses `tier=strong` for stage 3. Both
MCP servers and Claude Skills are supported, real building blocks — this
is implementable as scoped, not aspirational.

**Honest limitation** (document in output): structure/rigor are reliable;
market *numbers* are only as good as web sources + model — cite sources,
label figures directional.

**DoD**: end-to-end run from `/idea` to a saved, cited report note;
`fit_score` demonstrably reads from the self-model; web sources cited;
stage 2 works with no web.

## 10. Netherlands specifics

**Invoicing** (legal requirements baked into the template & generator):
- Sequential numbering per year, no gaps: `2026-001`, `2026-002`, …
- Required fields: freelancer name + address, KVK number, BTW-id, client name + address, invoice date, invoice number, line items (description, hours, rate), subtotal, BTW 21%, total, payment term, IBAN.
- EU B2B reverse charge: support a "btw verlegd" line (0% + client VAT id) when applicable.
- Generation: hours (from `events kind=time_entry`) × rate → invoice note → render Markdown → PDF → **always presented to the user for approval; never auto-sent.**

Evaluator setup guide defaults to NL structures: eenmanszaak/ZZP vs BV, KVK
registration, BTW/VAT registration, typical first-90-day steps.

## 11. Phased delivery plan

Build in order. Do not start a phase until the previous DoD is met. Every
phase ships something usable.

**Phase 0 — Foundation** *(no AI, no phone)*. Goal: a working manual second
brain. Deliverables: repo scaffold; vault tree; `_templates/` for every
type; `_system/{taxonomy,config,lint-rules}`; `lint.py` + pre-commit;
Dataview boards (pipeline, open deliverables, habits, gaps); git
auto-commit timer; README + runbook. DoD: user can create notes from
templates; linter passes/blocks correctly; Dataview boards render; nightly
git commit works.

**Phase 1 — Capture + normalize**. Goal: drop anything → structured
note/event. Deliverables: `llm.py` (Anthropic default + mock provider);
watcher; normalizer (Tesseract, faster-whisper, trafilatura); router;
embedder + pgvector on a new Supabase project; Syncthing configured (phone
`inbox/`); Telegram bot skeleton (capture, `/track`, `/done`, `/lift`,
`/ask`). DoD: §6.1 + §6.5 DoDs pass; `/ask` returns a relevant RAG answer;
offline tests pass with mock LLM.

**Phase 2 — Seed the self**. Goal: real `profile-seed.md` + first models.
Deliverables: interview intake (accept filled
`04-self-model-interview.md`); §8.2 seeding pipeline; initial
`self/current` (low-confidence) + `self/desired` + initial `self/gap`.
DoD: filled interview produces lint-passing self-model notes; traits ≤0.3
confidence; raw answers preserved.

**Phase 3 — CRM / freelance ops**. Goal: full client/project/billing.
Deliverables: client/project/invoice notes; `time_entry` → billing
rollups; NL invoice generator + PDF (approval-gated, §10); pipeline board;
Gmail comms-log integration; per-project file auto-filing. DoD: log hours
→ see remaining budget → generate a compliant NL invoice PDF for approval;
Gmail appends comms; pipeline board accurate. Consider porting field
choices from oslife's existing `projects`/`clients`/`project_tasks`/
`project_invoices` tables as a reference for what to track (not the code).

**Phase 4 — Gap engine v1**. Goal: goals generated from the gap.
Deliverables: metabolism job; gap-review job (§8.3, dry-run + apply);
OKR/habit proposal generation; streak tracking; life-areas balance check.
DoD: §6.3 + §8.3 DoDs; weekly review produces reviewable OKR/habit
proposals honoring `hold`.

**Phase 5 — Daily coach**. Goal: the aggressive-but-kind coach.
Deliverables: morning brief; live nudge triggers; escalation logic;
intensity dial + snooze; energy-window timing; self-compassion guardrails
(§8.6). DoD: §8.6 DoD; user can tune intensity; no nudge spam; quiet
windows honored.

**Phase 6 — Business-idea evaluator**. Goal: 3-stage evaluator.
Deliverables: MCP server (scoped vault + web search); `biz-eval` skill;
intake→verdict→deep-report; NL setup guide. DoD: §9 DoD.

**Phase 7 — Health / gym**. Goal: telemetry + training engine.
Deliverables: Health Connect ingestion → events (brain-only); program
notes; `/lift` logging; auto-progression + recovery-based deload;
workout→habit→OKR wiring. DoD: logging a workout progresses the plan and
ticks the linked habit; deload triggers on poor-sleep week with
explanation. **This is the earliest point a NAS purchase becomes relevant
— not before.**

**Phase 8 — Extra functions**. Deliverables: decision journal + review
loop (§8.5); weekly/quarterly review ritual; values-alignment time audit;
contradiction tracker; resurfacing/spaced-repetition; mood-energy
dashboard (brain-only). DoD: each function produces its note/report and
feeds the self-model where specified.

**Phase 9 — Visual layer**. Deliverables: read-only dashboard over vault +
Postgres (start with Obsidian Bases/Dataview; custom web UI only if
justified). DoD: user can see cash/pipeline/goals/gaps/health at a glance
without opening raw files.

## 12. Non-functional requirements

### 12.1 Privacy & encryption
- gocryptfs encrypts sensitive subtrees: `self/`, `crm/invoices/`,
  `health/`, and any `visibility: sensitive` note. Mounted decrypted while
  running; ciphertext at rest and in git backups. One passphrase at boot.
- **During the Supabase interim**: `sensitive` records never get uploaded
  to Supabase at all — they live only in the local encrypted vault. Only
  `interactive`/`brain-only` telemetry (steps, location, time entries)
  goes to Supabase.
- No sensitive values in URLs, query strings, or logs. Secrets (API keys,
  OAuth tokens, bot token) in a `.env`/secret store, never committed.
- LLM calls: document what leaves the machine; allow a per-note `no_ai:
  true` opt-out that excludes a note from any API call.

### 12.2 Backup & DR
Nightly encrypted backup of vault (git bundle) + a `pg_dump` of the
Supabase/Postgres project to a second location. Documented restore
procedure. Test restore before Phase 3 handles money.

### 12.3 Performance
Normalization of a dropped item < 60s (excluding large audio). Vault stays
responsive in Obsidian (telemetry stays out of `.md`, per P5).

### 12.4 Reliability & observability
All jobs idempotent and safe to re-run. Structured logs per job; failures
alert the user via Telegram. Watcher failures quarantine to
`inbox/_failed/`, never lose input.

### 12.5 Testing
Unit tests for normalizer routing, linter, invoice math (VAT,
reverse-charge), gap-review dry-run, `llm()` mock path. CI runs linter +
tests on every commit.

## 13. Repository structure & conventions

```
repo/
├── app/
│   ├── llm.py               # the abstraction (§7.5)
│   ├── watcher.py normalizer.py embedder.py lint.py
│   ├── bot/                 # telegram
│   ├── brain/                # metabolism.py gap_review.py coach.py
│   ├── crm/                  # billing.py invoice_pdf.py gmail.py
│   ├── evaluator/             # mcp_server.py skill/
│   ├── health/                # ingest.py training.py
│   └── common/                # frontmatter.py db.py config.py
├── vault/                     # (or configurable path)
├── tests/
├── supabase/                  # migrations for the Postgres schema (§6, data-doc §6)
├── systemd/                   # timers + services for anything not on Supabase
├── .env.example
└── docs/                      # these handoff docs
```

Conventions: Python 3.11+, type hints, ruff + black, pydantic for
frontmatter models, no secrets in code, every scheduled job has a
`--dry-run`. All user-facing model changes go through a proposal→confirm
step (never silent writes to `self/` or money).

## 14. Extension guides (must remain true)

- **New data source**: classify knowledge/telemetry → write `ingest_<source>.py` → register timer/watcher → add `source` enum value → register entities/tags. No core change.
- **New note type**: add catalog row (data-doc §5) → `_templates/<type>.md` → folder → optional coach trigger.
- **New coach trigger**: add rule to `brain/coach.py` (query + threshold + template + severity).
- **New module**: new top-level folder + types + telemetry kinds + triggers; link into gap engine via `desired_link` if it should feed the self-model. Modules are independent and removable.

## 15. Risks & known-hard parts (flag to stakeholder, don't silently absorb)

1. **Finance/bank ingestion** — PSD2/open-banking is fiddly and aggregators are paywalled. Plan: CSV import → `events kind=txn` first; API later. Do not block the project on it.
2. **Instagram** — no usable personal API. Share-to-inbox only.
3. **Local strong reasoning** — needs a GPU; until then deep-report/gap-review/metabolism-escalation use the API. This is the one place a stronger model clearly pays for itself.
4. **Coach → shame machine** — the top *product* failure mode. §8.6 guardrails are requirements, not polish.
5. **Maintenance trap** — if the system needs tending, it gets abandoned (esp. with ADHD). Every phase must run untended for weeks without breaking or demanding cleanup.
6. **Supabase interim cost/availability** — free tier pauses on inactivity; budget Pro (~$25/mo, verify current pricing) for an always-on coach until the NAS replaces it.

## 16. Open decisions / assumptions

- **Resolved**: NL locale; gocryptfs sensitive-only (and sensitive data never leaves the local vault during the Supabase interim); `llm()` default Haiku with strong/escalate routing; custom NL invoice design; Telegram coach transport; Postgres+pgvector (not SQLite) as the telemetry store.
- **Assumed**: single user; Android phone; NAS purchase deferred until at least Phase 7.
- **Pending from user before Phase 3**: KVK number, BTW-id, IBAN, business name/address for the invoice template.
- **Pending from user before Phase 2**: the filled-in `04-self-model-interview.md`.

## 17. Handoff acceptance checklist

- [ ] Engineer has read this doc + `02-data-structure-and-flow.md`.
- [ ] A new Supabase project exists (separate from oslife's).
- [ ] Anthropic API key + Telegram bot token in secret store.
- [ ] Phase 0 DoD met and demoed before Phase 1 begins.
- [ ] Each subsequent phase: DoD met + brief demo + user sign-off before next phase.

## 18. Glossary

- **Vault** — the Obsidian Markdown knowledge store.
- **Telemetry** — high-frequency machine data in Postgres.
- **Metabolism** — nightly job that rewrites/reconciles notes so knowledge doesn't rot.
- **Gap engine** — compares current vs desired self and generates goals/habits from the difference.
- **Held tension** (`hold:true`) — a contradiction to live with, not resolve.
- **`llm()`** — the single, swappable model-call abstraction.
- **DoD** — Definition of Done; the gate to the next phase.
