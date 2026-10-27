import type {Markmap} from 'markmap-view'
import type {INode} from 'markmap-common'
export type MindmapNode={text:string;children:MindmapNode[]}
export const mapOptions={duration:0,maxWidth:216,initialExpandLevel:-1,spacingVertical:14,spacingHorizontal:64,autoFit:true}
export function mapData(root:MindmapNode):{content:string;children:ReturnType<typeof mapData>[]}{
 const escape=(text:string)=>text.replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]!))
 return {content:`<span class="mindmap-label">${escape(root.text)}</span>`,children:root.children.map(mapData)}
}
export async function createMap(svg:SVGSVGElement,root:MindmapNode,initialExpandLevel=-1){
 const {Markmap}=await import('markmap-view')
 const map=Markmap.create(svg,{...mapOptions,initialExpandLevel})
 try{await map.setData(mapData(root));await map.fit();return map}catch(error){map.destroy();throw error}
}
export function downloadBlob(blob:Blob,name:string){
 const url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=name;a.click()
 setTimeout(()=>URL.revokeObjectURL(url),1000)
}
// Use plain SVG text for raster export: foreignObject would taint canvas in browsers.
export function exportSvg(map:Markmap,measure:(text:string)=>number){
 const ns='http://www.w3.org/2000/svg',svg=document.createElementNS(ns,'svg')
 const r=map.state.rect,w=Math.ceil(r.x2-r.x1+64),h=Math.ceil(r.y2-r.y1+64)
 svg.setAttribute('width',String(w));svg.setAttribute('height',String(h));svg.setAttribute('viewBox',`${r.x1-32} ${r.y1-32} ${w} ${h}`)
 const make=(tag:string,attrs:Record<string,string>)=>{const el=document.createElementNS(ns,tag);Object.entries(attrs).forEach(([k,v])=>el.setAttribute(k,v));svg.append(el);return el}
 make('rect',{x:String(r.x1-32),y:String(r.y1-32),width:String(w),height:String(h),fill:'#fff'})
 function visit(node:INode,parent?:INode){
  const {x,y,width,height}=node.state.rect,color=map.options.color(node)
  if(parent){const p=parent.state.rect,x1=p.x+p.width,y1=p.y+p.height,x2=x,y2=y+height,m=(x1+x2)/2
   make('path',{d:`M${x1},${y1} C${m},${y1} ${m},${y2} ${x2},${y2}`,fill:'none',stroke:color,'stroke-width':'2'})}
  make('line',{x1:String(x),y1:String(y+height),x2:String(x+width),y2:String(y+height),stroke:color,'stroke-width':'2'})
  const holder=document.createElement('div');holder.innerHTML=node.content
  const text=holder.textContent||'',lines:string[]=[];let line=''
  for(const char of Array.from(text)){if(line&&measure(line+char)>200){lines.push(line);line=''}line+=char}if(line)lines.push(line)
  const label=make('text',{x:String(x+8),y:String(y+17),fill:'#172b45','font-family':'system-ui, sans-serif','font-size':'14'})
  lines.forEach((value,i)=>{const span=document.createElementNS(ns,'tspan');span.setAttribute('x',String(x+8));span.setAttribute('dy',i?'22':'0');span.textContent=value;label.append(span)})
  node.children.forEach(child=>visit(child,node))
 }
 if(map.state.data)visit(map.state.data)
 return {text:new XMLSerializer().serializeToString(svg),width:w,height:h}
}
export async function mindmapPng(root:MindmapNode){
 const host=document.createElement('div');host.className='mindmap-export-host';host.setAttribute('aria-hidden','true')
 const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');host.append(svg);document.body.append(host)
 let map:Markmap|undefined
 try{
  await document.fonts.ready
  map=await createMap(svg,root)
  const canvas=document.createElement('canvas'),ctx=canvas.getContext('2d');if(!ctx)throw Error('浏览器无法生成图片')
  ctx.font='14px system-ui, sans-serif'
  const image=exportSvg(map,text=>ctx.measureText(text).width),scale=Math.min(2,16000/image.width,16000/image.height,Math.sqrt(32e6/(image.width*image.height)))
  canvas.width=Math.ceil(image.width*scale);canvas.height=Math.ceil(image.height*scale)
  const img=new Image();await new Promise<void>((resolve,reject)=>{img.onload=()=>resolve();img.onerror=()=>reject(Error('图片渲染失败'));img.src='data:image/svg+xml;charset=utf-8,'+encodeURIComponent(image.text)})
  ctx.drawImage(img,0,0,canvas.width,canvas.height)
  return await new Promise<Blob>((resolve,reject)=>canvas.toBlob(blob=>blob?resolve(blob):reject(Error('图片导出未完成')),'image/png'))
 }finally{map?.destroy();host.remove()}
}
