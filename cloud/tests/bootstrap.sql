-- ONLY for an empty, disposable local PostgreSQL database; never run in Supabase.
do $$begin create role anon nologin;exception when duplicate_object then null;end$$;
do $$begin create role authenticated nologin;exception when duplicate_object then null;end$$;
do $$begin create role service_role nologin bypassrls;exception when duplicate_object then null;end$$;
create schema auth;
create table auth.users(id uuid primary key);
create function auth.uid() returns uuid language sql stable as $$select nullif(current_setting('request.jwt.claim.sub',true),'')::uuid$$;
grant usage on schema auth to anon,authenticated,service_role;
grant execute on function auth.uid() to anon,authenticated,service_role;
insert into auth.users values('11111111-1111-4111-8111-111111111111'),('22222222-2222-4222-8222-222222222222'),('33333333-3333-4333-8333-333333333333');
