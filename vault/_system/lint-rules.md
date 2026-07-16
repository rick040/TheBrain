# Lint rules

Human-readable description of what `tools/lint.py` enforces. The code is
the source of truth (`TYPE_SPEC` in that file); this doc exists so you
don't have to read Python to know why a note failed.

## Scope

Every `.md` file under the vault **except**: `_templates/`, `_system/`,
`_dashboards/`, `inbox/` (raw, not-yet-normalized drops), and the vault's
own `README.md`. Everything else is expected to be a real note that
follows the universal frontmatter contract.

## Universal contract (every note)

All of these keys must be present (empty/null is fine for some — see
below — but the key must exist):

| field | rule |
|---|---|
| `id` | must match `YYYYMMDD-HHMM` |
| `type` | must be one of the note-type catalog (see `docs/02-data-structure-and-flow.md` §5) |
| `created` | ISO 8601 (`YYYY-MM-DDTHH:MM`) |
| `updated` | ISO 8601 |
| `source` | one of `manual, gmail, web, screenshot, voice, owntracks, health, coach, evaluator` |
| `visibility` | one of `interactive, brain-only, sensitive` |
| `freshness` | one of `timeless, dated, pointer` |
| `tags` | a list (can be empty) |
| `entities` | a list (can be empty) |
| `links` | a list (can be empty) |
| `status` | one of `active, done, archived, revised, retired` |

## Type-specific required fields

Each type in the catalog has extra fields that must be present (the key
must exist in frontmatter — the *value* can be blank while you're drafting,
except where an enum is checked, see below). Full list is in
`tools/lint.py`'s `TYPE_SPEC`; mirrors `docs/02-data-structure-and-flow.md`
§5.

## Enum fields checked beyond the universal contract

- `trait.polarity` → `strength | tension | neutral` (never good/bad — see build plan Part B2)
- `desired.derivation` → `seed | inferred`
- `gap.size` → `subtle | moderate | large`
- `gap.hold` → boolean

## Links

Any `[[wikilink]]` found anywhere in a note's body or frontmatter (anchors
after `#` and display text after `|` are stripped first) must resolve to
some other note's filename stem somewhere in the vault. This is what lets
you trust that a link isn't a typo/dead end.

## Why lint at all in Phase 0 (no AI yet)?

Two reasons: (1) it catches your own typos early, before there are enough
notes that a broken link is hard to spot; (2) from Phase 1 onward, the
brain edits notes too — the linter is what lets it do that without quietly
corrupting your vault, so it's worth having the habit (and the CI/pre-commit
wiring) in place before that starts.
