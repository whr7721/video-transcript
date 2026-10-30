"""Explicit private full variants. Source/runtime assets only, never profiles or data."""
import json,os,re,shutil,subprocess,sys,tempfile,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parent
def requirements():
 entries={}
 for name in ['requirements.lock.txt','requirements-ocr.lock.txt']:
  for line in (ROOT/name).read_text().splitlines():
   if line.strip() and not line.startswith('#'):entries[re.split(r'[=<>~]',line)[0].casefold()]=line
 for line in ['playwright==1.64.0','tenacity==8.2.2','PyExecJS==1.5.1','aiomysql==0.2.0','xhshow==0.2.0']:
  entries[line.split('==')[0].casefold()]=line
 return '\n'.join(entries.values())+'\n'
def collector(stage,mc,discovery):
 dest=stage/'vendor/mediacrawler';dest.mkdir(parents=True)
 # Only importable code/assets; never copy checkout config, browser_data, data, .env or caches.
 for name in ['base','cache','model','tools','proxy','media_platform/douyin']:
  source=mc/name
  for p in source.rglob('*.py'):
   if '__pycache__' in p.parts:continue
   q=dest/p.relative_to(mc);q.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,q)
 for name in ['var.py','LICENSE','libs/douyin.js']:
  q=dest/name;q.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(mc/name,q)
 (dest/'media_platform/__init__.py').write_text('')
 # The imported client must not initialize the full crawler/store/database subsystem.
 (dest/'media_platform/douyin/__init__.py').write_text('# Shiwen private adapter: client only; original license in ../../LICENSE\n')
 (dest/'config').mkdir();(dest/'config/__init__.py').write_text('DISABLE_SSL_VERIFY=False\nCACHE_TYPE_REDIS="memory"\n')
 text=discovery.read_text(encoding='utf8').replace('MC = Path(r"D:\\zcode1\\mediacrawler")','MC = Path(os.environ["SHIWEN_MEDIACRAWLER_DIR"])').replace('PROFILE = ROOT / "browser"','PROFILE = Path(os.environ["SHIWEN_DISCOVERY_PROFILE"])')
 (stage/'vendor/douyin_discovery.py').write_text(text,encoding='utf8')
def prepare(stage,mc=None,discovery=None):
 stage=Path(stage);stage.mkdir(parents=True,exist_ok=True)
 for p in ROOT.glob('*.py'):
  if p.name.startswith(('build_','check_core')):continue
  shutil.copyfile(p,stage/p.name)
 for name in ['cli_assets','experiments','skills']:
  shutil.copytree(ROOT/name,stage/name,ignore=(lambda folder,names:[n for n in names if n=='__pycache__' or (Path(folder,n).is_file() and Path(n).suffix!='.py')]) if name=='experiments' else shutil.ignore_patterns('__pycache__','*.pyc'),dirs_exist_ok=True)
 shutil.copytree(ROOT/'frontend/dist',stage/'frontend/dist')
 shutil.copytree(ROOT/'web',stage/'web')
 for name in ['THIRD_PARTY_NOTICES.md','THIRD_PARTY_LICENSES.txt']:shutil.copyfile(ROOT/'distribution'/name,stage/name)
 shutil.copytree(ROOT/'tools/md2card/dist',stage/'tools/md2card/dist')
 shutil.copyfile(ROOT/'tools/md2card/LICENSE',stage/'tools/md2card/LICENSE')
 for p in (ROOT/'full_delivery').iterdir():
  if p.is_file():shutil.copyfile(p,stage/p.name)
 for name in ['runtime-lock.json','delivery_models.py'] :shutil.copyfile(ROOT/'private_delivery'/name,stage/name)
 (stage/'requirements.txt').write_text(requirements(),encoding='utf8')
 for name in ['app.py','shiwen.py']:
  p=stage/name;p.write_text('import full_env\nfull_env.configure()\n'+p.read_text(encoding='utf8'),encoding='utf8')
 collector(stage,Path(mc or os.environ.get('SHIWEN_MEDIACRAWLER_DIR',r'D:\zcode1\mediacrawler')),Path(discovery or os.environ.get('SHIWEN_DISCOVERY_ADAPTER',r'D:\zcode1\douyin-discovery\discovery.py')))
 (stage/'full-package.json').write_text(json.dumps({'version':1,'profile':'full','platforms':['local_file','youtube','bilibili','douyin','rss','tiktok','twitter','xiaoyuzhou','spotify','xiaohongshu'],'sessions_included':False}),encoding='utf8')
 guide=(ROOT/'private_delivery/USER_GUIDE.html').read_text(encoding='utf8').replace('客户','自用全功能').replace('data-core','data-full').replace('</html>','')
 guide+='<section><h2>抖音 / B站 / 小红书首次扫码</h2><svg viewBox="0 0 820 100" role="img" aria-label="设置、登录、手机扫码、状态确认流程示意"><g fill="#f7edf3" stroke="#ce3080"><rect x="0" y="10" width="180" height="75" rx="10"/><rect x="210" y="10" width="180" height="75" rx="10"/><rect x="420" y="10" width="180" height="75" rx="10"/><rect x="630" y="10" width="180" height="75" rx="10"/></g><g font-size="20" text-anchor="middle"><text x="90" y="55">① 打开设置</text><text x="300" y="55">② 平台登录</text><text x="510" y="55">③ 手机扫码</text><text x="720" y="55">④ 确认状态</text></g></svg><p>上图是操作示意，不是已经登录的截图。抖音点“打开独立登录窗口”，用抖音App扫码确认后关闭该窗口；B站点“B站登录”，用哔哩哔哩App扫码，成功自动关闭，设置显示已登录。小红书点“登录小红书”，用小红书App扫码，成功自动关闭；三者独立保存于本包data-full；不要求原MediaCrawler已部署。不在聊天发送Cookie/Key，不复用打包者登录态。</p><p>这是个人自用全功能变体，包含MediaCrawler客户端片段及其NON-COMMERCIAL LEARNING LICENSE；保留vendor/mediacrawler/LICENSE，不将该变体作为商业许可承诺。平台风控/登录仍需用户配合。普通full按需下载环境；offline-full内含工具/依赖wheel/浏览器/模型，用install.ps1 -Offline安装，但联网内容提取和云端AI本身仍需网络。</p></section></html>'
 (stage/'USER_GUIDE.html').write_text(guide,encoding='utf8')
 for name,script in [('install','install.ps1'),('start','start.ps1'),('uninstall','uninstall.ps1'),('stop','stop.ps1'),('shiwen','run-cli.ps1')]:
  (stage/(name+'.cmd')).write_text('@echo off\r\npowershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0'+script+'" %*\r\n',encoding='ascii')
 for p in stage.glob('*.ps1'):p.write_text(p.read_text(encoding='utf8'),encoding='utf-8-sig')
def offline_assets(stage,seed):
 seed=Path(seed)
 for name in ['bin','python','browsers']:
  source=seed/'.runtime'/name
  if not source.is_dir():raise ValueError('离线种子缺少 '+name+'，请先完成full安装')
  if name=='python':
   # uv's minor-version directory is a junction, not a second Python installation.
   actual=source/'cpython-3.11.14-windows-x86_64-none'
   if not actual.is_dir():raise ValueError('缺少固定版本Python目录')
   shutil.copytree(actual,stage/'.runtime/python'/actual.name)
  else:shutil.copytree(source,stage/'.runtime'/name)
 wheels=seed/'.runtime/wheels';wheels.mkdir(exist_ok=True)
 subprocess.run([sys.executable,'-m','pip','wheel','--wheel-dir',str(wheels),'-r',str(stage/'requirements.txt')],check=True)
 shutil.copytree(wheels,stage/'.runtime/wheels')
 import setup_models
 if not all(setup_models.verify(seed/'models').values()):raise ValueError('离线种子模型校验失败')
 shutil.copytree(seed/'models',stage/'models')
def build(output=None,offline_full=False,runtime_seed=None,mc=None,discovery=None):
 out=Path(output or ROOT/'runtime/final-sprint-20261029/packages');out.mkdir(parents=True,exist_ok=True)
 if offline_full and not runtime_seed:raise ValueError('--offline-full 需 --runtime-seed 指向已安装的full包')
 with tempfile.TemporaryDirectory(dir=ROOT/'runtime') as tmp:
  stage=Path(tmp)/'shiwen';prepare(stage,mc,discovery)
  if offline_full:offline_assets(stage,Path(runtime_seed))
  archive=out/('shiwen-windows-offline-full.zip' if offline_full else 'shiwen-windows-full.zip')
  with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=3) as z:
   for p in stage.rglob('*'):
    if p.is_file():z.write(p,Path('shiwen')/p.relative_to(stage))
 return archive.resolve()
