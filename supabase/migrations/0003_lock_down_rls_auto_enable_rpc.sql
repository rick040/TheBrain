-- Pre-existing platform safety-net function on this Supabase project
-- (fires as an event trigger to auto-enable RLS on new public tables,
-- not something TheBrain's schema created) — the security advisor
-- flagged it as callable via RPC by anon/authenticated, which it was
-- never meant to be. Revoking removes that RPC surface without
-- affecting its actual job (firing on DDL). Already applied.
revoke execute on function public.rls_auto_enable() from anon, authenticated;
