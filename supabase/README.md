# Supabase migrations

These `.sql` files are already applied to the live "TheBrain" Supabase
project (via the Supabase MCP connector) — they're kept here so the schema
is reproducible as code rather than only living in the dashboard, and so
the eventual NAS migration (`pg_dump` → `pg_restore`, see `../docs/00-PLAN.md`)
has a paper trail of exactly what's been layered on top of a stock
Postgres instance.

Apply order matters (numbered). To replay them against a fresh Postgres
(e.g. testing the NAS migration path later):

```bash
for f in supabase/migrations/*.sql; do
  psql "$DATABASE_URL" -f "$f"
done
```
