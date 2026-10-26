import {useEffect,useState} from 'react'
import TopicSearch from './TopicSearch'
type Topic={id:string;title:string;notes_count:number;materials_count?:number}
export default function TopicLibrary(){
 const [topics,setTopics]=useState<Topic[]>([]),[topic,setTopic]=useState(new URLSearchParams(location.search).get('topic')||''),[error,setError]=useState(''),[job,setJob]=useState<any>(null)
 useEffect(()=>{fetch('/api/studio/research/topics').then(async r=>{if(!r.ok)throw Error('无法读取专题');setTopics(await r.json())}).catch(e=>setError(e.message))},[])
 function choose(id:string){setTopic(id);setJob(null);history.replaceState(null,'','/studio/?view=topics&topic='+encodeURIComponent(id))}
 async function research(id:string){try{const r=await fetch('/api/studio/research/jobs/'+encodeURIComponent(id));const v=await r.json();if(!r.ok)throw Error(v.detail||'无法读取记录');setJob(v)}catch(e){setError((e as Error).message)}}
 return <main className="topic-library"><nav><a href="/studio/">文稿工作台</a><a href="/studio/?view=library">图文素材库</a></nav><h1>专题资料</h1><p>把阅读留下的原文与自己的理解，再找回来。</p>{error&&<p role="alert">{error}</p>}<TopicSearch topics={topics} topicId={topic} onTopic={choose} onResearch={research} onNotesChanged={async()=>{}}/>{job&&<section><h2>{job.title||'深入记录'}</h2><blockquote>{job.context?.selection}</blockquote>{job.sections?.map((s:any,i:number)=><div key={i}><h3>{s.heading}</h3><p>{s.text}</p></div>)}<p>AI解释不等于已核实事实。<a href={'/studio/?task='+encodeURIComponent(job.task_id)}>打开来源文稿</a></p></section>}</main>
}
