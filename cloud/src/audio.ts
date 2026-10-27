export function pcmWav(samples:Float32Array){
 const bytes=new ArrayBuffer(44+samples.length*2),v=new DataView(bytes);
 const str=(offset:number,s:string)=>{for(let i=0;i<s.length;i++)v.setUint8(offset+i,s.charCodeAt(i))};
 str(0,'RIFF');v.setUint32(4,36+samples.length*2,true);str(8,'WAVE');str(12,'fmt ');v.setUint32(16,16,true);
 v.setUint16(20,1,true);v.setUint16(22,1,true);v.setUint32(24,16000,true);v.setUint32(28,32000,true);v.setUint16(32,2,true);v.setUint16(34,16,true);str(36,'data');v.setUint32(40,samples.length*2,true);
 samples.forEach((x,i)=>v.setInt16(44+i*2,Math.round(Math.max(-1,Math.min(1,x))*(x<0?32768:32767)),true));
 return bytes;
}
export function splitPcm(samples:Float32Array){
 const parts:{idx:number;offset:number;wav:ArrayBuffer}[]=[];
 for(let start=0;start<samples.length;start+=480_000)parts.push({idx:parts.length,offset:start/16000,wav:pcmWav(samples.subarray(start,start+480_000))});
 return parts;
}
export async function prepareAudio(file:File){
 if(!file.size||file.size>20*1024*1024)throw new Error('请选择非空且不超过20MB的音频。');
 if(!/\.(mp3|m4a|wav|aac|ogg|opus|flac|webm)$/i.test(file.name))throw new Error('请选择 MP3、M4A、WAV 等音频文件。');
 // Read metadata before allocating decoded PCM; a small compressed file can contain hours.
 const metadataUrl=URL.createObjectURL(file),probe=document.createElement('audio');probe.preload='metadata';
 try{
  const duration=await new Promise<number>((resolve,reject)=>{const timer=setTimeout(()=>reject(new Error('无法读取音频时长，请转换为 MP3 或 WAV。')),15_000);probe.onloadedmetadata=()=>{clearTimeout(timer);resolve(probe.duration)};probe.onerror=()=>{clearTimeout(timer);reject(new Error('浏览器无法读取此音频，请转换为 MP3 或 WAV。'))};probe.src=metadataUrl});
  if(!Number.isFinite(duration)||duration<=0||duration>300)throw new Error('体验版支持5分钟以内音频，未截取或上传部分内容。');
 }finally{probe.removeAttribute('src');probe.load();URL.revokeObjectURL(metadataUrl)}
 const bytes=await file.arrayBuffer();
 const hash=[...new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))].map(x=>x.toString(16).padStart(2,'0')).join('');
 const ctx=new AudioContext({sampleRate:16000});
 try{
  let decoded:AudioBuffer;
  try{decoded=await ctx.decodeAudioData(bytes)}catch{throw new Error('浏览器无法解码此音频，请转换为 MP3 或 WAV 后重试。')}
  if(!decoded.length||decoded.duration>300)throw new Error('体验版支持5分钟以内音频，未截取或上传部分内容。');
  const frames=Math.ceil(decoded.duration*16000),offline=new OfflineAudioContext(1,frames,16000);
  const source=offline.createBufferSource();source.buffer=decoded;source.connect(offline.destination);source.start();
  const mono=await offline.startRendering();return{hash,duration:mono.length/16000,parts:splitPcm(mono.getChannelData(0))};
 }finally{await ctx.close()}
}
