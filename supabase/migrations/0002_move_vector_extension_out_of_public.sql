-- Supabase's security linter flags extensions installed in `public`.
-- Moves pgvector into a dedicated schema — already applied to the live
-- project. `extensions` is on the default search_path for new Supabase
-- projects, so embeddings.vec's type resolves without qualification.
create schema if not exists extensions;
alter extension vector set schema extensions;
