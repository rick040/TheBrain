-- RAG primitive backing the Telegram bot's /ask command
-- (docs/03-engineering-build-spec.md §6.1 DoD: "/ask returns a relevant
-- RAG answer"). Already applied to the live project.
create or replace function public.match_embeddings(
  query_embedding extensions.vector(768),
  match_count int default 5,
  for_user uuid default auth.uid()
)
returns table(ref text, kind text, similarity float)
language sql stable
security invoker
set search_path = public, extensions
as $$
  select ref, kind, 1 - (vec <=> query_embedding) as similarity
  from embeddings
  where user_id = for_user
  order by vec <=> query_embedding
  limit match_count;
$$;

revoke all on function public.match_embeddings(extensions.vector, int, uuid) from public;
grant execute on function public.match_embeddings(extensions.vector, int, uuid) to authenticated, service_role;
