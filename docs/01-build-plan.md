# Second Brain — Build Plan v3 (canonical)

Schemas live in the companion doc `02-data-structure-and-flow.md` — this doc
is the "what it does and why." See `00-PLAN.md` for the reconciliation notes
(storage substrate, oslife reuse, corrections) layered on top of this plan.

**You**: Python-capable · Android · hardware TBD (no NAS yet) · EU (Netherlands)
· freelancer with ADHD
**Interaction**: chat-native · aggressive daily coach · via Telegram bot
**Overarching purpose**: close the gap between the person you are and the
person you want to become — nuanced, evolving, never black-and-white.

## Part A — Foundation (the substrate)

One inbox, two stores (Obsidian vault for what you see, **Postgres +
pgvector** for telemetry — Supabase-hosted now, self-hosted on the NAS
later; see `00-PLAN.md`), a normalization pipeline, a brain that's additive
not required, and a coach that reaches you on Telegram. Local-first
end-state on a lean x86 mini-PC/NAS (32GB RAM, defer the GPU) — but Phases
0-6 run fine on Supabase + your laptop, no hardware purchase required yet.
Full tech stack + folder tree + schemas: see the data-structure doc.

The vault is deliberately interconnected: a logged workout ticks a habit →
advances an OKR → traces up to a gap in your self-model → which the coach
frames as identity ("you're becoming someone who finishes"). That chain is
what makes it a brain rather than four trackers.

## Part B — The Self-Model & Gap Engine ⭐ (the spine of the whole system)

You said the system should point at "the version of me I want to be" — but
you don't yet know what that looks like. So the system doesn't assume it;
it discovers and refines it with you, and generates everything downstream
(north-stars → OKRs → habits → coach nudges) from the distance between two
evolving models of you.

### B1 · Two living models

- **`self/current/`** — descriptive. Who you are now, derived from data +
  observed patterns. Written and continuously revised by the brain (never
  by you directly). Facets: values, working-style, energy-mood,
  decision-style, skills, anti-patterns.
- **`self/desired/`** — aspirational. Who you want to become. Seeded by the
  onboarding interview (B3), refined as you learn what you actually want.
  Facets: north-star, identity ("I am someone who…"), aspirations, no-gos.

Neither is fixed. The current model sharpens as data accrues; the desired
model matures as you discover yourself. **The desired self is a hypothesis,
not a verdict.**

### B2 · Nuance is built into the data, not hoped for

The system is structurally prevented from being black-and-white (schema in
data-doc §5a):

- Every trait carries **confidence** (0-1), grows with evidence — no premature certainty.
- Every trait is **contextual** (`contexts: [...]`) — true *when*, not always.
- Traits are **strength / tension / neutral**, never good / bad.
- **Contradictions are held, not force-resolved.** "You crave freedom and structure" is stored as a lived tension (`hold: true`), not a bug to fix.
- Traits are **revised or retired with history**, never silently deleted — you can see how the model of you changed.

This is what lets it "really understand how you're wired" instead of
flattening you into a scorecard.

### B3 · The seed: an onboarding interview → `self/profile-seed.md`

Because you can't just name your future self, the interview surfaces it
indirectly — through projection, aversion, peak moments, and envy, which
reveal desires you can't state directly. See `04-self-model-interview.md`
— fill it in yourself, at your own pace; its answers seed both models.

### B4 · The gap loop (how it keeps working toward the goal)

```
new data ──▶ update self/current (traits, confidence, contexts)
weekly gap-review:
  diff current ↔ desired ──▶ write/refresh self/gap/*
  for each gap that is NOT held:
    propose or adjust an OKR + keystone habit to close it
  for uncertain gaps:
    spawn an identity experiment (B5)
  measure results ──▶ refine BOTH models (maybe the *desired* self was wrong)
```

Crucially, patterns feed both models: repeatedly saving articles on a topic
isn't just "an interest" in `current` — it's evidence of a latent desire
that may belong in `desired`. The system proposes; you confirm. Goals are
never static — they're regenerated as the gap moves.

### B5 · Identity experiments (nuanced change, not willpower)

Instead of decreeing "I will now be disciplined," the system runs small,
time-boxed tests: *"Hypothesis: you finish more with a hard 90-min morning
block. Protocol: 2 weeks. Measure: deliverables shipped + how it felt."*
Results update the model. This treats becoming-yourself as experiments to
learn from, not a pass/fail moral test — which is the only version that
survives ADHD.

### B6 · The self-compassion guardrail (design principle, not optional)

An aggressive coach + a gap engine can curdle into a shame machine you mute
within a month — the #1 failure mode. So, by design:

- The desired self is a **direction, not a debt**. Progress is framed as "becoming," not "still failing."
- Rest, play, and acceptance are **first-class states**, not gaps to close.
- Held tensions (`hold: true`) are honored, not nagged.
- The coach's firmness is **tunable**, and it reads your `energy-mood` model so it pushes when you can take it and backs off when you can't.

Compassion here isn't softness — it's what keeps the system used long
enough to work.

## Part C — The four domain modules (each feeds the self-model)

Recap; full schemas in data-doc §5. **Build order: CRM → Goals/OKR/Habits →
Evaluator → Health/Gym.**

- **CRM / Freelance Ops** (build #1, greenfield) — clients, projects,
  pipeline, time→auto-billing, invoices, comms log, files. Feeds `current`
  (work patterns, follow-through evidence). oslife's client/project/CRM
  tables are a useful reference for what fields matter in practice, but the
  UI here is Obsidian notes + Dataview boards, not a bespoke screen.
- **Goals → OKR → Habits** (build #2) — generated by the gap engine, not
  authored in a vacuum. The cascade is the *output* of Part B, and habits
  are the atomic units of identity change.
- **Business-Idea Evaluator** (build #3) — 3-stage (intake questions → fast
  verdict → deep web report), scoring idea + fit (fit is read straight from
  `self/current` skills & anti-patterns). An MCP server over the vault + web
  search + a `biz-eval` Skill.
- **Health & Gym** (build #4) — Android Health Connect hub (no wearable
  yet), training engine that programs + auto-progresses; feeds `current`
  energy/recovery patterns.

## Part D — Brain & Coach

- **Cheap/local/always-on** (`llm(tier="default")`, Haiku): OCR,
  transcription, tagging, embeddings, nightly metabolism (reconcile &
  rewrite notes, freshness).
- **Strong/scheduled/swappable** (`llm(tier="strong")`, Sonnet — Opus for
  the hardest passes, see `00-PLAN.md`): gap-review, OKR decomposition,
  coach messages needing real judgment, evaluator reports. API now; local
  Ollama once you add a GPU.
- **Daily coach (Telegram)**: morning brief (deliverables, KR progress,
  streaks-at-risk, top gap, timed to energy profile) + live nudges +
  two-way chat + tunable escalation.

## Part E — Extra functions

- **Decision journal** — log real decisions with options/rationale/expected
  outcome + a `review_on` date. Later, the brain scores predicted vs actual
  → this is how `decision-style` in your self-model gets accurate instead
  of self-flattering.
- **Weekly & quarterly reviews** — coach-guided ritual: wins, misses, what
  the data says, proposed adjustments to gaps/OKRs.
- **Values-alignment time audit** — cross time-entries + location + activity
  against your stated values. Uncomfortable, useful, feeds a gap.
- **Contradiction tracker** — surfaces where stated values, desired self,
  and actual behavior diverge — the richest signal for real change.
- **Resurfacing / spaced repetition** — old ideas and shelved business ideas
  resurface at useful intervals.
- **Life-areas balance (wheel)** — keeps the gap engine from optimizing one
  axis (work) while another (health, relationships) quietly collapses.
- **Mood-energy correlation dashboard** — brain-only; drives coach timing
  and training auto-deloads.

## Part F — Roadmap

Each phase is usable alone. Full DoDs are in `03-engineering-build-spec.md` §11.

- **Phase 0 · Foundation** — vault, schema, inbox, git, Dataview, templates. Runs on any machine today.
- **Phase 1 · Capture + normalize** — watcher (OCR/Whisper/URL/`llm()`), Syncthing, Telegram bot skeleton (capture, `/track`, `/done`), Postgres+pgvector wired up on Supabase.
- **Phase 2 · Seed the self** — run the onboarding interview → `profile-seed.md` + first `self/current` + `self/desired`.
- **Phase 3 · CRM** — full freelance ops; wire work data into `self/current`.
- **Phase 4 · Gap engine v1** — weekly gap-review, OKR/habit generation from gaps, streaks, metabolism.
- **Phase 5 · Daily coach** — briefs + nudges + escalation, energy-timed, self-compassion guardrails.
- **Phase 6 · Evaluator** — MCP + `biz-eval` skill, fit-scored from the self-model.
- **Phase 7 · Health/Gym** — Health Connect → telemetry, training auto-progression. (NAS decision becomes relevant around here, not before.)
- **Phase 8 · Extra functions** — decision journal, reviews, time-audit, resurfacing, wheel.
- **Phase 9 · Visual** — dashboard over vault + database. Last.
