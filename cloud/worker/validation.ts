export class HttpError extends Error {constructor(public status:number,message:string){super(message)}}
export function checkWav(bytes:ArrayBuffer){
 const b=new DataView(bytes),tag=(i:number,n:number)=>String.fromCharCode(...new Uint8Array(bytes,i,n));
 if(bytes.byteLength<44||bytes.byteLength>1_920_044||tag(0,4)!=='RIFF'||tag(8,4)!=='WAVE'||b.getUint32(4,true)!==bytes.byteLength-8)
  throw new HttpError(415,'请上传浏览器生成的独立音频分段。');
 // The browser encoder emits one canonical PCM WAV header; do not trust client duration/offset.
 if(tag(12,4)!=='fmt '||b.getUint32(16,true)!==16||b.getUint16(20,true)!==1||b.getUint16(22,true)!==1||
 b.getUint32(24,true)!==16000||b.getUint32(28,true)!==32000||b.getUint16(32,true)!==2||b.getUint16(34,true)!==16||
 tag(36,4)!=='data'||b.getUint32(40,true)!==bytes.byteLength-44||(bytes.byteLength-44)%2!==0)
  throw new HttpError(415,'音频分段必须为 16kHz 单声道 PCM WAV。');
 const duration=(bytes.byteLength-44)/32000;
 if(duration<=0||duration>60)throw new HttpError(413,'单段音频须在60秒以内。');
 return duration;
}
export type Tree={text:string;children:Tree[]};
export type Artifact={summary:string;highlights:string[];mindmap:Tree};
export function validateArtifact(value:unknown):Artifact{
 const v=value as Artifact; let count=0;
 const text=(x:unknown,n:number)=>typeof x==='string'&&x.trim().length>0&&x.length<=n&&!/[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]|<\s*\/?\s*[a-zA-Z][^>]*>/.test(x);
 function walk(x:Tree,depth:number){
  if(!x||depth>4||++count>80||!text(x.text,40)||!Array.isArray(x.children)||x.children.length>8||new Set(x.children.map(c=>c?.text?.trim())).size!==x.children.length)throw new HttpError(502,'导图结构不符合要求，请显式重试。');
  x.children.forEach(c=>walk(c,depth+1));
 }
 if(!v||!text(v.summary,2000)||!Array.isArray(v.highlights)||v.highlights.length>8||!v.highlights.every(x=>text(x,240)))throw new HttpError(502,'摘要结构不符合要求，请显式重试。');
 walk(v.mindmap,1);
 function clean(t:Tree):Tree{return{text:t.text.trim(),children:t.children.map(clean)}}
 return {summary:v.summary.trim(),highlights:v.highlights.map(x=>x.trim()),mindmap:clean(v.mindmap)};
}
function treeSchema(depth=1):object{return{type:'object',additionalProperties:false,properties:{text:{type:'string',minLength:1,maxLength:40},children:{type:'array',maxItems:depth===4?0:depth===3?1:6,...(depth===4?{}:{items:treeSchema(depth+1)})}},required:['text','children']}}
export const ARTIFACT_SCHEMA={type:'object',additionalProperties:false,properties:{summary:{type:'string',minLength:1,maxLength:2000},highlights:{type:'array',maxItems:8,items:{type:'string',minLength:1,maxLength:240}},mindmap:treeSchema()},required:['summary','highlights','mindmap']};
export const uuid=(s:string)=>/^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/.test(s);
export async function digest(bytes:ArrayBuffer|string){const b=typeof bytes==='string'?new TextEncoder().encode(bytes):bytes;return [...new Uint8Array(await crypto.subtle.digest('SHA-256',b))].map(x=>x.toString(16).padStart(2,'0')).join('')}
export async function readBounded(request:Request,max:number){
 if(Number(request.headers.get('content-length'))>max)throw new HttpError(413,'文件过大。');
 if(!request.body)throw new HttpError(400,'请求内容为空。');
 const r=request.body.getReader(),chunks:Uint8Array[]=[];let size=0;
 while(true){const {done,value}=await r.read();if(done)break;size+=value.byteLength;if(size>max){await r.cancel();throw new HttpError(413,'文件过大。')}chunks.push(value)}
 const all=new Uint8Array(size);let offset=0;for(const c of chunks){all.set(c,offset);offset+=c.length}return all.buffer;
}
