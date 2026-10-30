"""Local CLI over shared transcription, summary and chapter pipelines."""
import argparse,contextlib,json,os,sys,time
from pathlib import Path
from link_ingest import platform,stamp,export,ytdlp,add,configure

def main(argv=None):
    parser=argparse.ArgumentParser(prog='shiwen');sub=parser.add_subparsers(dest='command',required=True)
    p=sub.add_parser('add');p.add_argument('url');p.add_argument('--episode',type=int);p.add_argument('--language',choices=['auto','zh','en','ja','ko','yue'],default='auto');p.add_argument('--summarize',action='store_true',help='原稿保存后用模型生成完整稿、精华、金句与离线导图；共享每日请求配额')
    p=sub.add_parser('summarize',help='链接或本地音视频 → 原稿、三层摘要与离线导图')
    p.add_argument('url');p.add_argument('--episode',type=int);p.add_argument('--language',choices=['auto','zh','en','ja','ko','yue'],default='auto')
    p.add_argument('--chapter',action='store_true',help='另用已有章节链生成语义章节导读，额外请求计入共享配额')
    p.add_argument('--json',action='store_true',help='stdout仅输出JSON；costDuration为本次耗时秒数，日志到stderr')
    for command in ('add','summarize'):
        sub.choices[command].add_argument('--diarize',action='store_true',help='本地识别说话人，自动估计人数')
        sub.choices[command].add_argument('--speakers',type=int,choices=range(1,21),default=0,help='指定说话人数并开启识别')
    p=sub.add_parser('rewrite',help='已有文稿多平台二创');p.add_argument('task_id');p.add_argument('--style',choices=['xiaohongshu','gongzhonghao','zhihu','moments'],default='xiaohongshu');p.add_argument('--json',action='store_true')
    p=sub.add_parser('clips',help='从已有文稿挑选双语金句并渲染竖屏成片');p.add_argument('task_id');p.add_argument('--count',type=int,default=5);p.add_argument('--json',action='store_true')
    sub.add_parser('commands',help='列出本机命令和边界，不联网、不调用模型')
    args=parser.parse_args(argv)
    if args.command=='commands':
        print(json.dumps({'commands':[{'name':'rewrite','usage':'shiwen rewrite <task_id> [--style xiaohongshu|gongzhonghao|zhihu|moments] [--json]','effect':'每平台一次请求，缓存命中免费，独立版本不改原稿'},{'name':'clips','usage':'shiwen clips <task_id> [--count N] [--json]','effect':'一次模型挑选与翻译；本地渲染竖屏成片，缓存免重复请求'},{'name':'add','usage':'shiwen add <url|file> [--summarize] [--diarize|--speakers N] [--episode N] [--language auto|zh|en|ja|ko|yue]','effect':'本地转写免费；可选AI整理计入共享配额'},{'name':'summarize','usage':'shiwen summarize <url|file> [--chapter] [--json] [--diarize|--speakers N] [--episode N]','effect':'AI三层整理与导图；chapter额外语义章节请求，缓存不重复调用'},{'name':'commands','usage':'shiwen commands','effect':'只读命令清单'}],'requires':'需本机已部署拾文、本地工具','costDuration':'wall-clock seconds; not currency'},ensure_ascii=False,indent=2));return
    started=time.monotonic()
    try:
        configure(os.environ.get('SHIWEN_PROFILE')!='core' and not (Path(__file__).parent/'customer-package.json').exists())
        if args.command=='rewrite':
            import rewrite
            value=rewrite.submit(args.task_id,args.style)
            if args.json:print(json.dumps(value,ensure_ascii=False))
            elif value['status']=='completed':print(value['text'])
            if value['status']=='failed':parser.exit(1,value.get('error','二创失败')+'\n')
            return
        if args.command=='clips':
            import clips
            pending=[]
            value=clips.submit(args.task_id,args.count,pending.append)
            if pending:value=clips.run(pending[0][6:])
            print(json.dumps(value,ensure_ascii=False,indent=2))
            if value['status']=='failed':parser.exit(1,'切片未完成，可用相同命令重试；已完成阶段保留。\n')
            return
        if args.command=='add':add(args);return
        args.summarize=True
        with contextlib.redirect_stdout(sys.stderr if args.json else sys.stdout):
            ident=add(args)
            if ident is None:raise ValueError('RSS请使用 --episode 序号明确选择单集')
            import store
            directory=store.DATA/'jobs'/ident
            summary=(directory/'summary.md').read_text(encoding='utf8')
            if args.chapter:
                import cli_chapters
                chapter=cli_chapters.summarize(ident)
            else:chapter=None
        result={'id':ident,'summary':summary,'costDuration':round(time.monotonic()-started,3)}
        result['xmind']=str((directory/'mindmap.xmind').resolve())
        if chapter is not None:result['chapters']=chapter
        if args.json:print(json.dumps(result,ensure_ascii=False))
        else:
            print(summary)
            if chapter is not None:print(chapter)
    except Exception as e:
        if getattr(args,'json',False):parser.exit(1,json.dumps({'error':str(e),'costDuration':round(time.monotonic()-started,3)},ensure_ascii=False)+'\n')
        parser.exit(1,f'处理失败：{e}\n')

if __name__=='__main__':main()
