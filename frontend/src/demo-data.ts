import type {JSONContent} from '@tiptap/react'
export const demoLibraryItems = [
 {uid:'audio:demo:1',id:'demo:1',title:'把注意力留给真正重要的事',platform:'youtube',status:'completed',created_at:1793300000,starred:true,snippet:'信息从未如此丰富，但我们并不需要读完所有内容。重要的是，知道什么值得留下。',author:'深度阅读',duration:1280},
 {uid:'audio:demo:2',id:'demo:2',title:'散步、留白，与创造力的关系',platform:'xiaoyuzhou',status:'completed',created_at:1793213600,starred:false,snippet:'一段没有目的地的散步，也可能是思考开始的地方。聊聊日常生活里的创作节奏。',author:'日常之间',duration:2560},
 {uid:'audio:demo:3',id:'demo:3',title:'设计的最后一步，是做减法',platform:'bilibili',status:'completed',created_at:1793127200,starred:false,snippet:'从一张书桌、一盏台灯开始，重新理解设计里的秩序、分寸和人与物的关系。',author:'好好设计',duration:1840},
 {uid:'audio:demo:4',id:'demo:4',title:'如何建立自己的知识连接',platform:'rss',status:'completed',created_at:1793040800,starred:true,snippet:'收藏只是开始。在不同的材料之间发现关联，才是个人资料库真正有价值的时刻。',author:'知识漫游',duration:3200},
 {uid:'audio:demo:5',id:'demo:5',title:'在城市的缝隙里，发现生活',platform:'xiaohongshu',status:'completed',created_at:1792954400,starred:false,snippet:'街边的招牌、落日下的楼梯、一本翻旧的杂志。值得记录的细节，一直都在身边。',author:'城市观察',duration:480},
 {uid:'audio:demo:6',id:'demo:6',title:'一个普通人的长期主义',platform:'douyin',status:'completed',created_at:1792868000,starred:false,snippet:'不急着抵达，也不停止前进。让微小但确定的行动，慢慢积累出自己的答案。',author:'慢慢来',duration:960}
].map(r=>({...r,url:'/studio/?task='+r.id+'&preview=1'}))
export const demoLibraryStats={total:6,duration:10320,recent:6,platforms:{youtube:1,xiaoyuzhou:1,bilibili:1,rss:1,xiaohongshu:1,douyin:1}}
const paragraphs=[
 '我们每天打开很多页面，看过许多视频，也收藏了许多“以后再读”的链接。但信息的积累，并不总能带来理解的积累。真正需要问的，或许不是还能获取什么，而是哪些内容值得我们停下来。',
 '注意力是一种有限的资源。为输入设定边界，并不是拒绝好奇心，而是给思考留出空间。把一段值得重读的访谈保存下来，提炼出一个问题，再用自己的话写下回答，这个过程比匆忙刷过更多内容更有意义。',
 '一个好的资料库，不应该只是一座越来越满的仓库。它应当帮助我们在不同材料之间建立连接：这段对话让我想起了哪本书？这个观点在哪种场景下成立？哪些地方还需要继续求证？',
 '从今天开始，试着只留下一条你真正想读懂的内容。保留它的原话，记录自己的疑问，再让新的理解慢慢发生。把看过的，变成自己的。'
]
export function demoDocument(id:string){
 const task=demoLibraryItems.find(r=>r.id===id)||demoLibraryItems[0]
 const content:JSONContent={type:'doc',content:[{type:'heading',attrs:{level:2},content:[{type:'text',text:'少一些输入，多一点理解'}]},...paragraphs.map((text,i)=>({type:'paragraph',attrs:{id:'block-seg-'+i,sourceIds:['seg-'+i]},content:[{type:'text',text}]}))]}
 const sources=paragraphs.map((text,i)=>({id:'seg-'+i,text,start:i*38,end:(i+1)*38-2}))
 return {task_id:task.id,revision:1,content,updated_at:1793300000,sources,versions:[{revision:1,created:1793300000}],audio_available:false,generations:[{id:'demo-manuscript',task_id:task.id,action:'manuscript',status:'completed',base_revision:1,content},{id:'demo-summary',task_id:task.id,action:'summary',status:'completed',base_revision:1,items:[{text:'信息不必全部读完。选择值得重读的内容，为输入设定边界，给思考留出空间。',source_ids:['seg-0','seg-1']},{text:'让资料库成为观点之间的连接，而不只是一座收藏仓库。',source_ids:['seg-2']}]},{id:'demo-mindmap',task_id:task.id,action:'mindmap',status:'completed',base_revision:1,mindmap:{text:'有意识地阅读',children:[{text:'选择输入',children:[{text:'保留值得重读的内容'}]},{text:'建立连接',children:[{text:'联系已知，提出问题'}]},{text:'形成理解',children:[{text:'用自己的话写下答案'}]}]}}]}
}
export const demoTasks=demoLibraryItems.map(r=>({...r,source:{kind:'link',platform:r.platform},result:{text:paragraphs.join('\n\n'),segments:demoDocument(r.id).sources}}))
