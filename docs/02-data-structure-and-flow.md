# Second Brain — Data Structure, Layout & Flow (canonical spec)

The single source of truth for how data is shaped, named, stored, and
moved. Designed to be easy to extend: everything is a plain Markdown file
or a Postgres row, every note self-describes via frontmatter, and every
extension point has a checklist at the end (§13).

Design rule: **conventions over configuration.** If you follow the naming +
frontmatter contract, both you and the AI can read, write, and reorganize
without special cases.

> Storage note: the original design used SQLite + sqlite-vec for telemetry.
> This spec uses **Postgres + pgvector** instead (Supabase-hosted now,
> self-hosted on the NAS later) so the interim deployment and the eventual
> NAS deployment are the same database — see `00-PLAN.md`. Schemas below
> are written in Postgres syntax.

## 1. The two stores (recap)

| Store | Tech | Holds | You see it? |
|---|---|---|---|
| Knowledge | Obsidian vault (`.md` + YAML) | Everything you think about or act on | Yes |
| Telemetry | Postgres (Supabase now / self-hosted later) | High-frequency, low-interaction data | Rarely — via conclusions |
| Index | pgvector columns/table | Embeddings of notes + telemetry summaries | No (brain only) |

Git versions the vault. Telemetry is backed up nightly (`pg_dump`). The
vault is fully usable with **zero AI**.

## 2. Vault tree

```
vault/
├── inbox/                  # THE drop zone. Anything lands here.
│   └── _processed/         # originals archived after normalization (never deleted)
│
├── daily/                  # daily notes + the coach's morning brief
│   └── 2026-07-16.md
│
├── crm/
│   ├── clients/    client--acme.md
│   ├── projects/   project--acme-website.md
│   └── invoices/   invoice--2026-001.md
│
├── goals/
│   ├── vision.md            # north-star direction (3-5 yr)
│   ├── okrs/    okr--Q3-2026.md
│   └── habits/  habit--gym.md
│
├── self/                    # ← the Self-Model (see 01-build-plan.md Part B)
│   ├── profile-seed.md      # output of the onboarding interview
│   ├── current/    values.md working-style.md energy-mood.md decision-style.md skills.md anti-patterns.md
│   ├── desired/    north-star.md identity.md aspirations.md no-gos.md
│   ├── gap/        gap--follow-through.md   # generated tensions + proposals
│   ├── decisions/  decision--2026-07-16-drop-client.md
│   ├── experiments/ exp--morning-deepwork.md
│   └── reviews/    review--2026-W29.md
│
├── ideas/     idea--saas-x.md          # captured ideas + evaluator reports
│
├── health/
│   ├── training/  program--strength-Q3.md
│   └── workouts/                        # session logs → mostly Postgres
│
├── knowledge/
│   ├── notes/    note--<slug>.md        # your thoughts, distilled
│   └── sources/  source--<slug>.md      # captured articles/web/IG/screenshots
│
├── people/  person--<slug>.md           # non-client contacts
│
├── _templates/                          # frontmatter templates per type
├── _system/
│   ├── taxonomy.md      # controlled tags + entities registry
│   ├── config.yaml      # llm() provider, coach schedule, thresholds
│   └── lint-rules.md    # frontmatter validation rules
└── README.md
```

## 3. Naming conventions

- **Files**: `type--slug.md`, lowercase, hyphenated. e.g. `client--acme.md`, `okr--Q3-2026.md`. The `type--` prefix makes files self-sorting and greppable.
- **IDs**: `YYYYMMDD-HHMM` timestamp, stable forever, used in frontmatter `id`.
- **Links**: Obsidian wikilinks `[[client--acme]]`. Always link, never duplicate.
- **Tags**: lowercase, kebab-case, from `_system/taxonomy.md`. Freely add new ones; the metabolism job merges near-duplicates.
- **Entities**: named things the data is *about* (people, orgs, places, projects): `[acme, belastingdienst, home-gym]`. Entities are how the brain correlates across domains.
- **Dates**: ISO 8601 always (`2026-07-16T14:32`).

## 4. The universal frontmatter contract

Every note has these fields. Missing fields fail the linter (§13d).

```yaml
---
id: 20260716-1432
type: <one of the catalog in §5>
created: 2026-07-16T14:32
updated: 2026-07-16T14:32       # metabolism bumps this
source: manual                  # manual|gmail|web|screenshot|voice|owntracks|health|coach|evaluator
visibility: interactive          # interactive | brain-only | sensitive
freshness: dated                 # timeless | dated | pointer (§10)
tags: []
entities: []
links: []
status: active                   # active | done | archived | revised | retired
---
```

Type-specific fields are added on top of this contract (see catalog).

## 5. Note type catalog

| type | folder | purpose | key extra fields | default visibility |
|---|---|---|---|---|
| `daily` | `daily/` | day log + coach brief | mood, energy, wins, blocks | interactive |
| `client` | `crm/clients/` | a client | stage, rate, contacts, projects | interactive |
| `project` | `crm/projects/` | a client project | client, stage, deliverables[], budget_hours, rate | interactive |
| `invoice` | `crm/invoices/` | billable summary | project, hours, amount, paid | sensitive |
| `vision` | `goals/` | 3-5yr direction | horizons[] | interactive |
| `okr` | `goals/okrs/` | objective + KRs | period, objective, key_results[], linked_habits | interactive |
| `habit` | `goals/habits/` | tracked habit | cadence, streak, linked_kr, log(postgres) | interactive |
| `trait` | `self/current/*` | one facet of current self | domain, statement, polarity, confidence, contexts[], evidence[], desired_link | sensitive |
| `desired` | `self/desired/*` | one facet of goal self | domain, statement, source(seed/inferred), commitment | sensitive |
| `gap` | `self/gap/` | tension between current↔desired | current, desired, size, tension, proposal, hold | sensitive |
| `decision` | `self/decisions/` | a decision + rationale | options[], chosen, expected, review_on, outcome | interactive |
| `experiment` | `self/experiments/` | time-boxed identity test | hypothesis, protocol, ends, result | interactive |
| `review` | `self/reviews/` | weekly/quarterly review | period, wins, misses, adjustments[] | interactive |
| `idea` | `ideas/` | business idea + report | verdict, idea_score, fit_score, report_status | interactive |
| `program` | `health/training/` | workout plan | split, weeks, progression_rule | interactive |
| `note` | `knowledge/notes/` | a distilled thought | — | interactive |
| `source` | `knowledge/sources/` | captured external content | url, author, captured_from | interactive |
| `person` | `people/` | a non-client contact | relationship, last_contact | interactive |

Extending this catalog is expected — see §13b.

### 5a. The nuanced `trait` schema (the core of the self-model)

```yaml
type: trait
domain: working-style
statement: "Starts projects strong, momentum fades past ~2 weeks"
polarity: tension            # strength | tension | neutral (NOT good/bad)
confidence: 0.6               # 0-1, rises with corroborating evidence
contexts: ["multi-week solo projects", "no external deadline"]   # WHEN true, not absolute
evidence: [[project--acme]], [[daily/2026-07-02]]
desired_link: [[self/desired/identity#follow-through]]
status: active                 # revised/retired instead of deleted — history matters
```

Nuance is enforced structurally: no trait is "true," it's true in
*contexts*, with a confidence, backed by evidence, held as
strength/tension/neutral rather than good/bad.

### 5b. The `gap` schema

```yaml
type: gap
current: [[self/current/working-style#follow-through]]
desired: [[self/desired/identity#finisher]]
size: moderate                # subtle | moderate | large
tension: "You value spontaneity; consistency can feel like a cage."
proposal: [[goals/okrs/okr--Q3-2026]]   # what's proposed to close it
hold: false                    # true = a gap to accept/observe, NOT close (nuance!)
```

`hold: true` is important: some gaps are contradictions to live with, not
defeats to fix.

## 6. Telemetry schema (Postgres — Supabase now, self-hosted later)

```sql
create extension if not exists vector;

-- generic time-series event: steps, sleep, location, hr, time_entry, habit_tick, lift, txn
create table events (
  id          bigint generated always as identity primary key,
  ts          timestamptz not null,
  kind        text not null,     -- steps|sleep|location|hr|time_entry|habit_tick|lift|txn
  value       numeric,           -- numeric payload (hours, count, kg, minutes...)
  meta        jsonb,             -- {project, place, merchant, exercise, reps, mood...}
  source      text
);
create index idx_events_kind_ts on events(kind, ts);

-- derived facts the brain wrote (so it can revise them later, with provenance)
create table insights (
  id          bigint generated always as identity primary key,
  ts          timestamptz,
  about       text,              -- entity or trait id
  statement   text,
  confidence  numeric,
  evidence    jsonb,             -- list of event ids / note ids
  wrote_to    text               -- vault note path it materialized into
);

-- semantic index
create table embeddings (
  ref         text primary key,  -- note path or event id
  vec         vector(768),       -- pgvector; dimension matches your embedding model
  kind        text,
  updated     timestamptz
);
create index on embeddings using ivfflat (vec vector_cosine_ops);
```

Rule of thumb: anything logged more than ~once a day, or that you won't
read individually, goes here — not into `.md`.

Row-level security note: since this runs on Supabase in the interim, turn
on RLS scoped to your user id on every table from the start (same pattern
oslife already uses) even though it's single-user — free, and removes a
footgun if the project ever gets a second Supabase-authenticated client.

## 7. Data flows

### 7a. Capture → normalize → route

```
drop in inbox/ → watcher detects type
  → extract text (Tesseract | Whisper | trafilatura | passthrough)
  → llm() structures → {frontmatter, body}
  → classify: telemetry? → INSERT into events
             knowledge?  → write .md to correct folder
  → embed → INSERT into embeddings
  → move original to inbox/_processed/
```

### 7b. Metabolism (nightly)

```
for changed notes:
  reconcile with existing notes on same entity
  resolve/flag contradictions (or mark hold:true)
  update `updated`, re-tag, refresh freshness
  merge near-duplicate tags/entities in taxonomy.md
```

### 7c. Gap loop (see 01-build-plan.md Part B4)

```
new data → update self/current/* (traits, confidence)
weekly gap-review:
  diff current ↔ desired → write/update self/gap/*
  propose or adjust okrs/habits to close non-held gaps
  spawn identity experiments for uncertain gaps
  measure experiment results → refine BOTH current and desired
```

### 7d. Coach (daily)

```
morning: read daily deliverables, KR progress, streaks-at-risk, top gap
  → compose brief, time it to energy-mood profile
  → push via Telegram
live: threshold triggers (overdue, stale, missed) → nudge
two-way: your replies log data / answer / adjust
```

## 8. Tags & entities (`_system/taxonomy.md`)

- Not rigid. You add tags freely; the nightly job clusters synonyms and proposes merges you approve.
- `taxonomy.md` holds the current canonical tag list + entity registry (with aliases: `belastingdienst | tax-office | government`).
- Entities are the join keys across domains — a single `acme` entity ties a client note, its project, emails, and time entries together.

## 9. Visibility model

| value | meaning | where |
|---|---|---|
| `interactive` | you see & act on it | vault, shown in Obsidian |
| `brain-only` | for the AI; hidden from your normal views | vault (filtered) or Postgres |
| `sensitive` | brain-only **and** encrypted at rest, and (during the Supabase interim) never uploaded — stays in the local gocryptfs-encrypted vault only | `self/`, finances, health |

Obsidian saved-searches hide `brain-only`/`sensitive` from daily view.

## 10. Freshness model (so knowledge never rots)

Every fact is one of:

- **timeless** — always true ("I value autonomy").
- **dated** — true as of a date, may expire ("rate = €85/hr, 2026-07").
- **pointer** — a reference to a source of truth, re-fetched, never cached stale ("current bank balance → query telemetry").

The metabolism job re-checks `dated` facts and replaces stale ones instead
of accumulating contradictions.

## 11. Config (`_system/config.yaml`)

```yaml
llm:
  default: {provider: anthropic, model: claude-haiku-4-5-20251001}   # verify at docs.claude.com at build time
  strong:  {provider: anthropic, model: claude-sonnet-5}
  escalate: {provider: anthropic, model: claude-opus-4-8}            # optional, on-demand only (see 00-PLAN.md)
  route_strong_for: [evaluator_deep_report, gap_review_synthesis, metabolism_self_model_pass]
coach:
  channel: telegram
  morning_brief: "07:30"
  escalation: on
  quiet_windows: []          # populated from self/current/energy-mood
thresholds:
  stale_lead_days: 7
  unbilled_hours_alert: 10
locale: {country: NL, currency: EUR, vat_rate: 21}
```

## 12. File template convention

Every type has a stub in `_templates/` so you and the AI write identically.
Example `_templates/trait.md`:

```yaml
---
id:
type: trait
created:
updated:
source:
visibility: brain-only
freshness: timeless
domain:
statement:
polarity:
confidence: 0.3
contexts: []
evidence: []
desired_link:
status: active
tags: []
entities: []
links: []
---
```

## 13. Extension guides — "how to add to it"

### 13a. Add a new data source
1. Decide: knowledge (→ note) or telemetry (→ event `kind`)?
2. Write a small Python `ingest_<source>.py` that outputs the normalized shape.
3. Register a systemd timer (or add to the watcher for push sources).
4. Add its `source` value to the frontmatter enum + config if it needs keys.
5. Add any new entities/tags to `taxonomy.md`. Done — the brain picks it up automatically because it self-describes.

### 13b. Add a new note type
1. Add a row to the catalog (§5).
2. Create `_templates/<type>.md`.
3. Add its folder.
4. If the coach/gap-engine should react to it, add a trigger (§13c). No code change to the core — the vault is schema-by-convention.

### 13c. Add a new coach trigger
1. Add a rule to `coach/triggers.py`: a query + threshold + message template.
2. Reference the entity/field it watches.
3. Set severity (`info` | `nudge` | `escalate`).

### 13d. Keep it valid — the linter
`lint.py` checks every note against §4 + type rules in
`_system/lint-rules.md`: required fields present, enums valid, links
resolve, dates ISO. Run on git pre-commit. This is what lets the AI edit
safely without "eating" your notes.

### 13e. Add a new domain module (like CRM/health)
1. New top-level folder + its note types (§13b).
2. Its telemetry `kind`s (§6).
3. Its coach triggers (§13c).
4. Link it into the gap engine if it should feed the self-model (add
   `desired_link`s). Each module is independent and optional — remove a
   folder, nothing else breaks.
