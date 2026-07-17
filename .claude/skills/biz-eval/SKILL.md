---
name: biz-eval
description: Deep, web-researched evaluation of a business idea already captured via /idea in the Telegram bot — market sizing, competition, financial model, go-to-market, risks, and a fit-for-you section read from the vault's self-model. Use when the user asks to "evaluate this idea", "do the deep report on <idea>", or names an existing ideas/idea--*.md note.
---

# Business-Idea Evaluator — deep report (Stage 3)

This is Stage 3 of the three-stage evaluator described in
`docs/03-engineering-build-spec.md` §9. Stages 1-2 (intake questions +
fast verdict) already ran in the Telegram bot (`/idea <description>`,
see `app/evaluator/idea_intake.py`) and wrote a note to
`vault/ideas/idea--<slug>.md` with a preliminary verdict. This skill
picks up from there and does the parts that genuinely need research and
more reasoning than a single fast pass: market sizing, competition, a
financial model, and an honest fit-for-you read.

**Prerequisite**: the `app.evaluator.mcp_server` MCP server must be
connected to this session (`python3 -m app.evaluator.mcp_server`,
configured as an MCP server in Claude Code/Desktop). It exposes:
- `list_past_ideas()` / `read_vault_note(path)` — scoped to
  `self/current/`, `self/desired/`, and `ideas/` only. Never ask it to
  read `crm/`, `health/`, or anything else — it will refuse, and you
  shouldn't need to; this evaluator has no business reading finances or
  client data.
- `list_self_model()` — available self-model note paths (may be empty;
  Phase 2 might not be seeded yet — treat that as "no data", not an error).
- `fetch_url(url)` — fetches and extracts one page's text. **Not a search
  engine.** Use this session's own web-search tool for discovery
  (finding candidate sources for a query); use `fetch_url` to pull the
  full text of a specific page once you have its URL, so you can quote
  and cite it accurately.
- `write_idea_report(slug, report_body)` — writes the finished report
  body back into the existing `ideas/idea--<slug>.md` note. It refuses
  if that note doesn't already exist (it must have come from `/idea`
  first) — never invent the frontmatter yourself.

## Procedure

1. **Locate the idea.** Ask for the slug/topic if not given, or use
   `list_past_ideas()` and `read_vault_note()` to find the matching
   `ideas/idea--<slug>.md` note and read its preliminary verdict + intake
   questions.
2. **Read the self-model, if any exists.** Call `list_self_model()`, then
   `read_vault_note()` on anything relevant (skills, anti-patterns,
   values, energy-mood) for the fit-for-you section. An empty result is
   normal, not a problem — say so plainly in the report rather than
   guessing.
3. **Check for near-duplicates.** `list_past_ideas()` — if something
   similar was captured before, say so and note how this one differs (or
   doesn't).
4. **Research.** Use this session's web-search tool to find sources for
   market size, competitors, and pricing; use `fetch_url` to pull full
   text from the specific pages you cite. Cite every source. Treat
   figures as **directional**, not gospel — the structure/rigor below is
   reliable, the exact numbers are only as good as what you found.
5. **Write the report**, in this order, and call `write_idea_report`
   with the full Markdown body:

   1. Executive summary + recommendation
   2. Market: TAM / SAM / SOM, growth, trends — cited
   3. Competition: key players, positioning gaps, moats
   4. Financial model: startup cost, unit economics, break-even,
      time-to-first-revenue, a 12-month P&L sketch, funding needed
   5. Go-to-market: first 3 channels, first 10 customers
   6. Risks & kill-criteria
   7. Fit-for-you: maps the idea to the self-model read in step 2 —
      brutally honest, not encouraging. If there's no self-model data
      yet, say that plainly instead of fabricating a fit assessment.
   8. Quick setup guide: NL legal structure (eenmanszaak/ZZP vs BV), KVK/
      BTW registration, a week-by-week first-90-days plan

6. **Reply to the user** with a short summary (a few sentences) and the
   vault path the full report was written to — don't paste the whole
   report back into chat, it's already in the vault.

## Non-negotiables

- Never fabricate a source. If you can't find real numbers, say the
  market-sizing section is an estimate and explain the reasoning instead.
- Never touch anything outside the MCP server's exposed scope — no
  finances, no client data, no health data. If you think you need it,
  you're out of scope; say so instead of trying another path.
- This never sends the report anywhere (email, Slack, etc.) — it writes
  to the vault only. Sending it anywhere is the user's decision, not this
  skill's.
