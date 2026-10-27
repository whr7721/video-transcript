-- Run in a NEW Supabase project. Cloud tables are separate from local Shiwen data.
begin;
create table public.cloud_transcripts (
 id uuid primary key default gen_random_uuid(),
 user_id uuid not null references auth.users(id) on delete cascade,
 source_hash text not null check(source_hash ~ '^[a-f0-9]{64}$'),
 title text not null check(length(title) between 1 and 200),
 duration_sec double precision not null check(duration_sec > 0 and duration_sec <= 300),
 segment_count int not null check(segment_count between 1 and 10),
 status text not null default 'transcribing' check(status in ('transcribing','completed')),
 created_at timestamptz not null default now(),
 unique(user_id,source_hash)
);
create index on public.cloud_transcripts(user_id,created_at desc);
create table public.cloud_segments (
 transcript_id uuid not null references public.cloud_transcripts(id) on delete cascade,
 idx int not null check(idx between 0 and 9),
 start_sec double precision not null,
 end_sec double precision not null check(end_sec > start_sec),
 state text not null check(state in ('processing','done','failed')),
 lease uuid not null,
 attempts int not null default 1 check(attempts between 1 and 2),
 updated_at timestamptz not null default now(),
 audio_hash text not null,
 text text,
 primary key(transcript_id,idx)
);
create table public.cloud_artifacts (
 transcript_id uuid primary key references public.cloud_transcripts(id) on delete cascade,
 state text not null check(state in ('processing','done','failed')),
 lease uuid not null,
 attempts int not null default 1 check(attempts between 1 and 2),
 updated_at timestamptz not null default now(),
 payload jsonb,
 model text
);
create table public.cloud_shares (
 transcript_id uuid primary key references public.cloud_transcripts(id) on delete cascade,
 token_hash text not null unique,
 include_transcript boolean not null default false,
 created_at timestamptz not null default now()
);
create table public.cloud_usage (
 day date primary key,
 jobs int not null default 0,
 audio_seconds double precision not null default 0,
 text_calls int not null default 0
);
create table public.cloud_ip_usage (
 day date not null,
 ip_hash text not null,
 jobs int not null default 0,
 primary key(day,ip_hash)
);
create table public.cloud_maintenance (
 id int primary key check(id=1),
 last_success timestamptz not null
);

-- All browser clients may only read their own source and derived results.
alter table public.cloud_transcripts enable row level security;
alter table public.cloud_segments enable row level security;
alter table public.cloud_artifacts enable row level security;
alter table public.cloud_shares enable row level security;
alter table public.cloud_usage enable row level security;
alter table public.cloud_ip_usage enable row level security;
alter table public.cloud_maintenance enable row level security;
revoke all on public.cloud_transcripts,public.cloud_segments,public.cloud_artifacts,
 public.cloud_shares,public.cloud_usage,public.cloud_ip_usage,public.cloud_maintenance from anon,authenticated;
grant select on public.cloud_transcripts,public.cloud_segments,public.cloud_artifacts to authenticated;
grant all on public.cloud_transcripts,public.cloud_segments,public.cloud_artifacts,
 public.cloud_shares,public.cloud_usage,public.cloud_ip_usage,public.cloud_maintenance to service_role;
create policy owner_read on public.cloud_transcripts for select to authenticated using(auth.uid()=user_id);
create policy owner_read on public.cloud_segments for select to authenticated using(exists(
 select 1 from public.cloud_transcripts t where t.id=transcript_id and t.user_id=auth.uid()));
create policy owner_read on public.cloud_artifacts for select to authenticated using(exists(
 select 1 from public.cloud_transcripts t where t.id=transcript_id and t.user_id=auth.uid()));

-- Called only by the authenticated Worker using its server-side service key.
-- Transaction advisory lock serializes all account/IP trial admission.
create function public.cloud_create_job(p_user uuid,p_hash text,p_title text,p_duration double precision,p_ip text)
returns jsonb language plpgsql security definer set search_path='' as $$
declare j public.cloud_transcripts; ipn int; total_jobs int; d date := (now() at time zone 'UTC')::date;
begin
 perform pg_advisory_xact_lock(57271027);
 select * into j from public.cloud_transcripts where user_id=p_user and source_hash=p_hash;
 if found then return to_jsonb(j); end if;
 if p_duration is null or p_duration <= 0 or p_duration > 300 or p_duration='NaN'::float8 then
  raise exception 'INVALID_DURATION'; end if;
 if (select count(*) from public.cloud_transcripts where user_id=p_user)>=3 then
  raise exception 'TRIAL_LIMIT'; end if;
 insert into public.cloud_usage(day) values(d) on conflict do nothing;
 select jobs into total_jobs from public.cloud_usage where day=d for update;
 if total_jobs>=40 then raise exception 'GLOBAL_LIMIT'; end if;
 insert into public.cloud_ip_usage(day,ip_hash) values(d,p_ip) on conflict do nothing;
 select jobs into ipn from public.cloud_ip_usage where day=d and ip_hash=p_ip for update;
 if ipn>=6 then raise exception 'IP_LIMIT'; end if;
 update public.cloud_ip_usage set jobs=jobs+1 where day=d and ip_hash=p_ip;
 update public.cloud_usage set jobs=jobs+1 where day=d;
 insert into public.cloud_transcripts(user_id,source_hash,title,duration_sec,segment_count)
 values(p_user,p_hash,p_title,p_duration,ceil(p_duration/30)::int) returning * into j;
 return to_jsonb(j);
end $$;

create function public.cloud_claim_segment(p_user uuid,p_job uuid,p_idx int,p_hash text,p_limit int)
returns jsonb language plpgsql security definer set search_path='' as $$
declare j public.cloud_transcripts; s public.cloud_segments; n double precision;
 d date := (now() at time zone 'UTC')::date; used double precision;
begin
 select * into j from public.cloud_transcripts where id=p_job and user_id=p_user for update;
 if not found then raise exception 'NOT_FOUND'; end if;
 if p_idx<0 or p_idx>=j.segment_count then raise exception 'INVALID_SEGMENT'; end if;
 select * into s from public.cloud_segments where transcript_id=p_job and idx=p_idx;
 if found then
  if s.audio_hash<>p_hash then raise exception 'SEGMENT_CHANGED'; end if;
  if s.state='done' then return jsonb_build_object('cached',true,'text',s.text); end if;
  if s.state='processing' and s.updated_at>now()-interval '5 minutes' then raise exception 'BUSY'; end if;
  if s.attempts>=2 then raise exception 'RETRY_LIMIT'; end if;
 end if;
 n:=least(30,j.duration_sec-p_idx*30);
 insert into public.cloud_usage(day) values(d) on conflict do nothing;
 select audio_seconds into used from public.cloud_usage where day=d for update;
 if used+n>least(greatest(p_limit,0),1200) then raise exception 'GLOBAL_LIMIT'; end if;
 update public.cloud_usage set audio_seconds=audio_seconds+n where day=d;
 insert into public.cloud_segments(transcript_id,idx,start_sec,end_sec,state,lease,audio_hash)
 values(p_job,p_idx,p_idx*30,p_idx*30+n,'processing',gen_random_uuid(),p_hash)
 on conflict(transcript_id,idx) do update set state='processing',lease=gen_random_uuid(),
 attempts=public.cloud_segments.attempts+1,updated_at=now() returning * into s;
 return jsonb_build_object('cached',false,'lease',s.lease);
end $$;

create function public.cloud_finish_segment(p_user uuid,p_job uuid,p_idx int,p_lease uuid,p_text text,p_ok boolean)
returns boolean language plpgsql security definer set search_path='' as $$
begin
 update public.cloud_segments s set state=case when p_ok then 'done' else 'failed' end,
 text=case when p_ok then p_text else null end,updated_at=now()
 where s.transcript_id=p_job and s.idx=p_idx and s.lease=p_lease and s.state='processing'
 and exists(select 1 from public.cloud_transcripts t where t.id=p_job and t.user_id=p_user);
 return found;
end $$;

create function public.cloud_claim_artifact(p_user uuid,p_job uuid)
returns jsonb language plpgsql security definer set search_path='' as $$
declare j public.cloud_transcripts; a public.cloud_artifacts; calls int;
 d date := (now() at time zone 'UTC')::date;
begin
 select * into j from public.cloud_transcripts where id=p_job and user_id=p_user for update;
 if not found then raise exception 'NOT_FOUND'; end if;
 if (select count(*) from public.cloud_segments where transcript_id=p_job and state='done')<>j.segment_count
 then raise exception 'INCOMPLETE'; end if;
 select * into a from public.cloud_artifacts where transcript_id=p_job;
 if found then
  if a.state='done' then return jsonb_build_object('cached',true,'payload',a.payload); end if;
  if a.state='processing' and a.updated_at>now()-interval '5 minutes' then raise exception 'BUSY'; end if;
  if a.attempts>=2 then raise exception 'RETRY_LIMIT'; end if;
 end if;
 insert into public.cloud_usage(day) values(d) on conflict do nothing;
 select text_calls into calls from public.cloud_usage where day=d for update;
 if calls>=12 then raise exception 'GLOBAL_LIMIT'; end if;
 update public.cloud_usage set text_calls=text_calls+1 where day=d;
 insert into public.cloud_artifacts(transcript_id,state,lease) values(p_job,'processing',gen_random_uuid())
 on conflict(transcript_id) do update set state='processing',lease=gen_random_uuid(),
 attempts=public.cloud_artifacts.attempts+1,updated_at=now() returning * into a;
 return jsonb_build_object('cached',false,'lease',a.lease);
end $$;

create function public.cloud_finish_artifact(p_user uuid,p_job uuid,p_lease uuid,p_payload jsonb,p_model text,p_ok boolean)
returns boolean language plpgsql security definer set search_path='' as $$
begin
 perform 1 from public.cloud_transcripts where id=p_job and user_id=p_user for update;
 if not found then raise exception 'NOT_FOUND'; end if;
 update public.cloud_artifacts set state=case when p_ok then 'done' else 'failed' end,
 payload=case when p_ok then p_payload else null end,model=p_model,updated_at=now()
 where transcript_id=p_job and lease=p_lease and state='processing';
 if not found then return false; end if;
 if p_ok then update public.cloud_transcripts set status='completed' where id=p_job; end if;
 return true;
end $$;

-- Prevent authenticated clients from invoking privileged functions with a forged user ID.
revoke all on function public.cloud_create_job(uuid,text,text,double precision,text),
 public.cloud_claim_segment(uuid,uuid,int,text,int),
 public.cloud_finish_segment(uuid,uuid,int,uuid,text,boolean),
 public.cloud_claim_artifact(uuid,uuid),
 public.cloud_finish_artifact(uuid,uuid,uuid,jsonb,text,boolean) from public,anon,authenticated;
grant execute on function public.cloud_create_job(uuid,text,text,double precision,text),
 public.cloud_claim_segment(uuid,uuid,int,text,int),
 public.cloud_finish_segment(uuid,uuid,int,uuid,text,boolean),
 public.cloud_claim_artifact(uuid,uuid),
 public.cloud_finish_artifact(uuid,uuid,uuid,jsonb,text,boolean) to service_role;
commit;
