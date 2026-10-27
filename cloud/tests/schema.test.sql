\set ON_ERROR_STOP on
do $$
declare j jsonb; claim jsonb; cached jsonb; jid uuid; lease uuid;
begin
 j:=public.cloud_create_job('11111111-1111-4111-8111-111111111111',repeat('a',64),'fixture',60,'ip-one');
 jid:=(j->>'id')::uuid;
 if public.cloud_create_job('11111111-1111-4111-8111-111111111111',repeat('a',64),'fixture',60,'ip-one')->>'id'<>jid::text then raise exception 'cache miss';end if;
 begin perform public.cloud_claim_segment('22222222-2222-4222-8222-222222222222',jid,0,'hash',1200);raise exception 'wrong owner accepted';exception when raise_exception then if sqlerrm<>'NOT_FOUND' then raise;end if;end;
 claim:=public.cloud_claim_segment('11111111-1111-4111-8111-111111111111',jid,0,'hash',1200);
 begin perform public.cloud_claim_segment('11111111-1111-4111-8111-111111111111',jid,0,'hash',1200);raise exception 'duplicate claimed';exception when raise_exception then if sqlerrm<>'BUSY' then raise;end if;end;
 if public.cloud_finish_segment('11111111-1111-4111-8111-111111111111',jid,0,gen_random_uuid(),'bad',true) then raise exception 'stale lease accepted';end if;
 perform public.cloud_finish_segment('11111111-1111-4111-8111-111111111111',jid,0,(claim->>'lease')::uuid,'first',true);
 cached:=public.cloud_claim_segment('11111111-1111-4111-8111-111111111111',jid,0,'hash',1200);
 if (cached->>'cached')::boolean is not true or cached->>'text'<>'first' then raise exception 'uncached segment';end if;
 begin perform public.cloud_claim_artifact('11111111-1111-4111-8111-111111111111',jid);raise exception 'partial summarized';exception when raise_exception then if sqlerrm<>'INCOMPLETE' then raise;end if;end;
 claim:=public.cloud_claim_segment('11111111-1111-4111-8111-111111111111',jid,1,'hash2',1200);
 perform public.cloud_finish_segment('11111111-1111-4111-8111-111111111111',jid,1,(claim->>'lease')::uuid,'second',true);
 claim:=public.cloud_claim_artifact('11111111-1111-4111-8111-111111111111',jid);
 begin perform public.cloud_claim_artifact('11111111-1111-4111-8111-111111111111',jid);raise exception 'duplicate summary';exception when raise_exception then if sqlerrm<>'BUSY' then raise;end if;end;
 perform public.cloud_finish_artifact('11111111-1111-4111-8111-111111111111',jid,(claim->>'lease')::uuid,'{"summary":"fixture"}','mock',true);
 cached:=public.cloud_claim_artifact('11111111-1111-4111-8111-111111111111',jid);
 if (cached->>'cached')::boolean is not true then raise exception 'uncached artifact';end if;
 if (select audio_seconds from public.cloud_usage)<>60 or (select text_calls from public.cloud_usage)<>1 then raise exception 'cache consumed budget';end if;
 perform public.cloud_create_job('11111111-1111-4111-8111-111111111111',repeat('b',64),'fixture',30,'ip-one');
 perform public.cloud_create_job('11111111-1111-4111-8111-111111111111',repeat('c',64),'fixture',30,'ip-one');
 begin perform public.cloud_create_job('11111111-1111-4111-8111-111111111111',repeat('d',64),'fixture',30,'ip-one');raise exception 'trial bypassed';exception when raise_exception then if sqlerrm<>'TRIAL_LIMIT' then raise;end if;end;
 j:=public.cloud_create_job('22222222-2222-4222-8222-222222222222',repeat('d',64),'fixture',30,'ip-two');
 begin perform public.cloud_claim_segment('22222222-2222-4222-8222-222222222222',(j->>'id')::uuid,0,'hash',60);raise exception 'global bypassed';exception when raise_exception then if sqlerrm<>'GLOBAL_LIMIT' then raise;end if;end;
 if (select audio_seconds from public.cloud_usage)<>60 then raise exception 'rejected request consumed budget';end if;
 -- Failure is explicit, results from an old lease cannot win, and retry is bounded.
 claim:=public.cloud_claim_segment('22222222-2222-4222-8222-222222222222',(j->>'id')::uuid,0,'hash',1200);
 perform public.cloud_finish_segment('22222222-2222-4222-8222-222222222222',(j->>'id')::uuid,0,(claim->>'lease')::uuid,null,false);
 lease:=(claim->>'lease')::uuid;
 claim:=public.cloud_claim_segment('22222222-2222-4222-8222-222222222222',(j->>'id')::uuid,0,'hash',1200);
 if public.cloud_finish_segment('22222222-2222-4222-8222-222222222222',(j->>'id')::uuid,0,lease,'late',true) then raise exception 'old retry overwrote new lease';end if;
 perform public.cloud_finish_segment('22222222-2222-4222-8222-222222222222',(j->>'id')::uuid,0,(claim->>'lease')::uuid,null,false);
 begin perform public.cloud_claim_segment('22222222-2222-4222-8222-222222222222',(j->>'id')::uuid,0,'hash',1200);raise exception 'unbounded retry';exception when raise_exception then if sqlerrm<>'RETRY_LIMIT' then raise;end if;end;
 if (select audio_seconds from public.cloud_usage)<>120 then raise exception 'failed retry accounting';end if;
end $$;
set role authenticated;
select set_config('request.jwt.claim.sub','22222222-2222-4222-8222-222222222222',false);
do $$begin
 if (select count(*) from public.cloud_transcripts)<>1 then raise exception 'RLS transcript leak';end if;
 if (select count(*) from public.cloud_segments)<>1 or (select count(*) from public.cloud_artifacts)<>0 then raise exception 'RLS derived data leak';end if;
 begin update public.cloud_transcripts set title='changed';raise exception 'source editable';exception when insufficient_privilege then null;end;
 begin perform public.cloud_create_job('11111111-1111-4111-8111-111111111111',repeat('e',64),'forged',30,'evil');raise exception 'RPC exposed';exception when insufficient_privilege then null;end;
 begin perform * from public.cloud_shares;raise exception 'share token storage exposed';exception when insufficient_privilege then null;end;
end $$;
reset role;
set role anon;
do $$begin
 begin perform * from public.cloud_transcripts;raise exception 'anonymous read';exception when insufficient_privilege then null;end;
 begin perform public.cloud_claim_artifact('11111111-1111-4111-8111-111111111111',gen_random_uuid());raise exception 'anonymous RPC';exception when insufficient_privilege then null;end;
end $$;
reset role;
select 'RLS, ownership, immutable source, atomic quotas, deduplication, leases, partial failure: PASS' as result;
