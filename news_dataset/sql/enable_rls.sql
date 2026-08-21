-- Enable Row Level Security on all Forsyt public tables.
--
-- Why: Supabase exposes public schema via PostgREST (anon/authenticated keys).
-- Without RLS, the security linter flags "RLS Disabled in Public".
--
-- Forsyt only accesses Postgres through DATABASE_URL (server-side pooler).
-- The postgres role bypasses RLS, so pipelines and API keep working.
-- With RLS on and no permissive policies, anon/authenticated get zero rows.
--
-- Run once in Supabase: SQL Editor → New query → paste → Run.

ALTER TABLE public.articles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.geo_feed_health ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.geo_cycle_stats ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.geo_seen_links ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.gpr_daily ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.corridor_daily ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.dual_signal_daily ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.pipeline_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.scrape_runs ENABLE ROW LEVEL SECURITY;

-- Optional: confirm RLS is on
SELECT c.relname AS table_name, c.relrowsecurity AS rls_enabled
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'public'
  AND c.relkind = 'r'
  AND c.relname IN (
    'articles', 'geo_feed_health', 'geo_cycle_stats', 'geo_seen_links',
    'gpr_daily', 'corridor_daily', 'dual_signal_daily', 'pipeline_runs',
    'scrape_runs'
  )
ORDER BY c.relname;
