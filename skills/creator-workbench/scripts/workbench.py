"""Local media intake and explicit publishing packages. No model client or publishing API."""
import argparse,contextlib,hashlib,json,os,re,shutil,struct,sys,time,zipfile
from pathlib import Path

def write(path,value):
 path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
 tmp=path.with_suffix(path.suffix+'.tmp');tmp.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf8');tmp.replace(path)

def read(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))

def root_path():return Path(os.environ.get('SHIWEN_HOME','D:/zcode1/video-transcript')).resolve()

def modules():
 root=root_path()
 if not (root/'link_ingest.py').is_file():raise ValueError('未找到拾文，请设置SHIWEN_HOME')
 sys.path.insert(0,str(root))
 import store,link_ingest
 link_ingest.configure(True);store.init()
 return store,link_ingest

def ingest(args):
 store,li=modules()
 from types import SimpleNamespace
 opt=SimpleNamespace(url=args.url,language='auto',episode=args.episode,summarize=False,diarize=False,speakers=0)
 plan=li.prepare(opt)
 if 'feed' in plan:raise ValueError('RSS需用--episode明确选择单集，不会自动处理整份Feed')
 folder=store.DATA/'jobs'/plan['ident'];cached=(folder/'transcript.json').is_file();opt.plan=plan
 with contextlib.redirect_stdout(sys.stderr):ident=li.add(opt)
 path=store.DATA/'jobs'/ident/'transcript.json';d=read(path)
 blocks=d.get('subtitlesArray') or d.get('segments') or []
 result={'schema_version':1,'id':ident,'kind':'source','platform':d.get('platform') or plan['kind'],'url':d.get('sourceUrl') or args.url,'title':d.get('title'),'author':d.get('author'),'published_at':d.get('publishedDate'),'captured_at':d.get('created_at'),'retrieved_at':time.time(),'cached':cached,'transcript_path':str(path.resolve()),'text_path':str(path.with_suffix('.txt').resolve()),'segment_count':len(blocks),'source_hash':hashlib.sha256(path.read_bytes()).hexdigest(),'text_ai_called':False}
 if args.output:write(args.output,result)
 return result

def latest(args):
 modules()
 import source_enumeration as enum
 kind,url=enum.identify(args.url)
 if kind=='single' or kind.endswith('topic'):raise ValueError('请输入支持的博主/频道主页，不是单篇链接或话题')
 with contextlib.redirect_stdout(sys.stderr):result=enum.enumerate_source(kind,url,args.limit)
 def stamp(row):
  v=row.get('published')
  try:return float(v)
  except (ValueError,TypeError):return 0
 items=sorted(result['items'],key=stamp,reverse=True)
 if not items:raise ValueError('没有取得作品，请检查登录和可用性')
 if not stamp(items[0]):raise ValueError('当前列表缺少可比较发布时间，无法宣称最新；请检查原列表')
 out={'schema_version':1,'kind':'source_listing','platform':kind,'checked_at':time.time(),'scope':f'本次接口返回最近{args.limit}条中的最新，非全平台绝对最新保证','status':result.get('status'),'warning':result.get('message'),'latest':items[0],'items':items}
 if args.output:write(args.output,out)
 return out

def init_job(args):
 folder=Path(args.directory).resolve();folder.mkdir(parents=True,exist_ok=True)
 if (folder/'manifest.json').exists():raise ValueError('作品已存在，请用status续做，不覆盖已有作品')
 value={'schema_version':1,'id':folder.name,'platform':args.platform,'status':'draft','created_at':time.time(),'expected_images':args.images,'title_file':'title.txt','caption_file':'正文.md','images':[],'sources':[],'music':{'status':'unverified'},'steps':{'intake':'pending','editorial':'pending','images':'pending','music':'pending'},'reviews':[]}
 write(folder/'manifest.json',value);(folder/'brief.md').write_text(args.brief+'\n',encoding='utf8');return value

def local(folder,name):
 if not isinstance(name,str) or not name:raise ValueError('缺少相对文件名')
 p=(folder/name).resolve()
 if not p.is_relative_to(folder):raise ValueError('文件必须位于作品目录内')
 return p

def inspect(folder):
 folder=Path(folder).resolve();m=read(folder/'manifest.json');errors=[];warnings=[];files=[]
 for key in ['title_file','caption_file']:
  try:
   f=local(folder,m.get(key));files.append(f)
   if not f.is_file() or not f.read_text(encoding='utf8').strip():errors.append(key+'为空或缺失')
  except (ValueError,OSError):errors.append(key+'路径无效')
 images=m.get('images',[])
 if not isinstance(images,list):images=[];errors.append('images必须是列表')
 if len(images)!=m.get('expected_images'):errors.append('图片数量不符合本篇要求')
 if len(set(images))!=len(images):errors.append('图片列表重复')
 for name in images:
  try:
   f=local(folder,name);files.append(f);data=f.read_bytes()[:24]
   if data[:8]!=b'\x89PNG\r\n\x1a\n':raise ValueError('当前检查器支持PNG，请先导出PNG')
   w,h=struct.unpack('>II',data[16:24])
   if not h or abs(w/h-3/4)>.02:errors.append(name+'不是3:4')
  except (OSError,ValueError,struct.error) as e:errors.append(str(name)+': '+str(e))
 for src in m.get('sources',[]):
  if src.get('kind')=='source' and src.get('transcript_path'):
   f=Path(src['transcript_path'])
   if not f.is_file() or hashlib.sha256(f.read_bytes()).hexdigest()!=src.get('source_hash'):errors.append('来源原稿已变化或不可用，请重新核对')
 if not m.get('sources'):warnings.append('尚无来源记录，请由agent确认这是否为纯原创选题')
 music=m.get('music',{})
 if music.get('status') not in {'track_confirmed','platform_confirmed','not_requested'}:warnings.append('配乐仍未核实')
 if music.get('status')=='track_confirmed':warnings.append('仅确认曲名，尚未核实平台纯伴奏可选入口')
 if not m.get('reviews'):warnings.append('尚无宿主内容/文字/图片人工式检查记录，文件检查不代替质量检查')
 return m,files,errors,warnings

def status(args):
 m,_,errors,warnings=inspect(args.directory)
 return {'manifest':m,'file_check_pass':not errors,'errors':errors,'warnings':warnings}

def pack(args):
 folder=Path(args.directory).resolve();m,files,errors,warnings=inspect(folder)
 if errors:raise ValueError('不能打包：'+'；'.join(errors))
 if not m.get('reviews'):raise ValueError('请先查看正文和每张图，并将检查结论写入reviews')
 m.update(status='packaged',packaged_at=time.time(),warnings=warnings);write(folder/'manifest.json',m)
 target=folder/'发布包.zip';temp=folder/'发布包.tmp'
 with zipfile.ZipFile(temp,'w',zipfile.ZIP_DEFLATED) as z:
  # Exact allowlist: never recursively include cookies, source media or unrelated files.
  for f in files+[folder/'manifest.json']:
   z.write(f,str(f.relative_to(folder)))
  for name in ['brief.md','music.md','来源说明.md']:
   f=folder/name
   if f.is_file():z.write(f,name)
 temp.replace(target)
 return {'id':m['id'],'zip':str(target),'warnings':warnings,'published':False}

def main():
 p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='command',required=True)
 a=sub.add_parser('ingest');a.add_argument('url');a.add_argument('--episode',type=int);a.add_argument('--output')
 a=sub.add_parser('latest');a.add_argument('url');a.add_argument('--limit',type=int,choices=[10,20,50],default=20);a.add_argument('--output')
 a=sub.add_parser('init');a.add_argument('directory');a.add_argument('--platform',choices=['douyin','kuaishou','xiaohongshu','bilibili'],required=True);a.add_argument('--images',type=int,choices=range(1,11),default=4);a.add_argument('--brief',default='')
 for command in ['status','pack']:a=sub.add_parser(command);a.add_argument('directory')
 args=p.parse_args()
 try:print(json.dumps(globals()[{'init':'init_job'}.get(args.command,args.command)](args),ensure_ascii=False,indent=2))
 except Exception as e:
  # Avoid leaking HTTP headers, session values or arbitrary upstream response bodies.
  message=str(e) if isinstance(e,(ValueError,FileNotFoundError)) else '本机工具调用失败（'+type(e).__name__+'），请检查登录与环境；不自动换付费服务'
  print(json.dumps({'error':message},ensure_ascii=False),file=sys.stderr);return 1
 return 0

if __name__=='__main__':raise SystemExit(main())
