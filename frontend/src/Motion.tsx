import {useEffect,useLayoutEffect,useRef,useState,type RefObject} from 'react'
import {X} from 'lucide-react'
export function useReducedMotion(){
 const [reduce,setReduce]=useState(()=>typeof matchMedia==='function'&&matchMedia('(prefers-reduced-motion: reduce)').matches)
 useEffect(()=>{if(typeof matchMedia!=='function')return;const query=matchMedia('(prefers-reduced-motion: reduce)'),change=()=>setReduce(query.matches);change();query.addEventListener('change',change);return()=>query.removeEventListener('change',change)},[])
 return reduce
}
export function Skeleton({label='正在读取内容',lines=3,cards=false}:{label?:string;lines?:number;cards?:boolean}){return <div className={'motion-skeleton '+(cards?'skeleton-cards':'')} role="status" aria-label={label} aria-busy="true"><span className="sr-only">{label}</span>{Array.from({length:lines},(_,i)=><i key={i}/>)}</div>}
export function EmptyState({children}:{children:string}){return <div className="motion-empty"><svg viewBox="0 0 80 64" width="80" height="64" aria-hidden="true"><path d="M17 15h32l13 12v25H17zM49 15v13h13M26 34h22M26 41h15"/><path d="M27 8h30l12 12v23"/></svg><p>{children}</p></div>}
export function useFirstReveal(ready:boolean){const once=useRef(false),[enter,setEnter]=useState(false);useLayoutEffect(()=>{if(!ready||once.current)return;once.current=true;setEnter(true);const timer=setTimeout(()=>setEnter(false),1000);return()=>clearTimeout(timer)},[ready]);return {enter,cancel:()=>{once.current=true;setEnter(false)}}}
export function CountUp({value}:{value:number}){
 const reduce=useReducedMotion(),played=useRef(false),[display,setDisplay]=useState(reduce?value:0)
 useEffect(()=>{if(played.current||reduce||typeof requestAnimationFrame!=='function'){played.current=true;setDisplay(value);return}played.current=true;let frame=0;const started=performance.now();const tick=(now:number)=>{const p=Math.min(1,(now-started)/300);setDisplay(Math.round(value*(1-Math.pow(1-p,3))));if(p<1)frame=requestAnimationFrame(tick)};frame=requestAnimationFrame(tick);return()=>cancelAnimationFrame(frame)},[value,reduce])
 return <span className="motion-count"><span className="count-reserve" aria-hidden="true">{value}</span><span className="count-value" aria-hidden="true">{display}</span><span className="sr-only">{value}</span></span>
}
export function TaskMeter({value,label="链接处理进度"}:{value?:number;label?:string}){const known=typeof value==='number'&&Number.isFinite(value),v=known?Math.max(0,Math.min(1,value!)):0;return <div className={'task-meter '+(!known?'is-indeterminate':'')} role="progressbar" aria-label={label} aria-valuemin={0} aria-valuemax={100} aria-valuenow={known?Math.round(v*100):undefined}><i style={{transform:`scaleX(${known?v:.3})`}}/></div>}
export function WaitingDust({active}:{active:boolean}){
 const canvas=useRef<HTMLCanvasElement>(null),reduce=useReducedMotion(),[visible,setVisible]=useState(false)
 useEffect(()=>{if(!active||reduce||typeof CanvasRenderingContext2D==='undefined'){setVisible(false);return}const c=canvas.current,ctx=c?.getContext('2d');if(!c||!ctx)return;let frame=0;const began=performance.now(),dots=Array.from({length:16},(_,i)=>({x:(i*67)%640,y:(i*29)%130}));setVisible(true);const draw=(now:number)=>{const p=Math.min(1,(now-began)/900);ctx.clearRect(0,0,640,130);ctx.fillStyle='#6f8960';for(const d of dots){ctx.globalAlpha=(1-p)*.22;ctx.beginPath();ctx.arc(d.x,d.y-p*10,1.2,0,Math.PI*2);ctx.fill()}if(p<1)frame=requestAnimationFrame(draw);else setVisible(false)};frame=requestAnimationFrame(draw);return()=>cancelAnimationFrame(frame)},[active,reduce])
 return <canvas ref={canvas} className={'waiting-dust '+(visible?'is-visible':'')} width={640} height={130} aria-hidden="true"/>
}
export function ReadingProgress({target,identity}:{target:RefObject<HTMLDivElement|null>;identity:string}){
 const [progress,setProgress]=useState(0)
 useEffect(()=>{const el=target.current;if(!el)return;let frame=0;const update=()=>{cancelAnimationFrame(frame);frame=requestAnimationFrame(()=>{const range=el.scrollHeight-el.clientHeight;setProgress(range>0?Math.min(1,el.scrollTop/range):0)})};el.addEventListener('scroll',update,{passive:true});const observer=typeof ResizeObserver!=='undefined'?new ResizeObserver(update):null;observer?.observe(el);if(el.firstElementChild)observer?.observe(el.firstElementChild);update();return()=>{el.removeEventListener('scroll',update);observer?.disconnect();cancelAnimationFrame(frame)}},[target,identity])
 return <div className="reading-progress" role="progressbar" aria-label="阅读进度" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(progress*100)}><i style={{transform:`scaleX(${progress})`}}/></div>
}
export function MotionToast({message,onClose}:{message:string;onClose:()=>void}){
 const [leaving,setLeaving]=useState(false),timer=useRef<ReturnType<typeof setTimeout>|null>(null),remaining=useRef(3000),began=useRef(0),close=useRef(onClose),paused=useRef(false);close.current=onClose
 const clear=()=>{if(timer.current)clearTimeout(timer.current)}
 const leave=()=>{clear();setLeaving(true);timer.current=setTimeout(()=>close.current(),180)}
 const start=()=>{clear();began.current=Date.now();timer.current=setTimeout(leave,remaining.current)}
 const pause=()=>{if(paused.current||leaving)return;paused.current=true;remaining.current=Math.max(0,remaining.current-(Date.now()-began.current));clear()}
 const resume=()=>{if(!paused.current||leaving)return;paused.current=false;start()}
 useEffect(()=>{remaining.current=3000;paused.current=false;setLeaving(false);start();return clear},[message])
 return <div className={'toast-message motion-toast '+(leaving?'is-leaving':'')} role="status" aria-atomic="true" onMouseEnter={pause} onMouseLeave={resume} onFocusCapture={pause} onBlurCapture={event=>{if(!event.currentTarget.contains(event.relatedTarget))resume()}}>{message}<button aria-label="关闭提示" onClick={leave}><X size={15}/></button></div>
}
