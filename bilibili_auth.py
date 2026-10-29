"""Private Bilibili login. Cookies never cross the localhost API boundary."""
import asyncio,base64,json,os,shutil,subprocess,time,threading
from pathlib import Path
import httpx
from fastapi import APIRouter,HTTPException
import store

router=APIRouter(prefix='/api/bilibili')
LOGIN=None
LOGIN_ERROR=None
CACHE={}
COOKIE_LOCK=threading.RLock()
LOGIN_EPOCH=0

def cookie_path():return store.DATA/'cookies'/'bilibili.json'
def profile_path():return store.DATA/'browser-bilibili'

def protect(path):
    path=Path(path)
    if os.name!='nt':path.chmod(0o700 if path.is_dir() else 0o600);return
    # Replace the DACL, rather than relying on chmod (which does not restrict Windows readers).
    target=str(path).replace("'","''")
    kind='Directory' if path.is_dir() else 'File'
    inheritance="[System.Security.AccessControl.InheritanceFlags]'ContainerInherit,ObjectInherit'" if path.is_dir() else '[System.Security.AccessControl.InheritanceFlags]::None'
    script=f"$sid=[System.Security.Principal.WindowsIdentity]::GetCurrent().User;$acl=New-Object System.Security.AccessControl.{kind}Security;$acl.SetAccessRuleProtection($true,$false);$rule=New-Object System.Security.AccessControl.FileSystemAccessRule($sid,[System.Security.AccessControl.FileSystemRights]::FullControl,{inheritance},[System.Security.AccessControl.PropagationFlags]::None,[System.Security.AccessControl.AccessControlType]::Allow);$acl.AddAccessRule($rule);[System.IO.{kind}]::SetAccessControl('{target}',$acl)"
    result=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-EncodedCommand',base64.b64encode(script.encode('utf-16le')).decode()],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW)
    if result.returncode:raise RuntimeError('无法设置B站会话的本机访问权限，未保存登录态')

def read_cookies():
    try:
        value=json.loads(cookie_path().read_text(encoding='utf8'))
        if not isinstance(value,list):return []
        return [c for c in value if isinstance(c,dict) and c.get('domain','').lstrip('.')=='bilibili.com' and isinstance(c.get('name'),str) and isinstance(c.get('value'),str)]
    except (OSError,ValueError):return []

def save_cookies(cookies,epoch=None):
    with COOKIE_LOCK:
        if epoch is not None and epoch!=LOGIN_EPOCH:return False
        folder=cookie_path().parent;folder.mkdir(parents=True,exist_ok=True);protect(folder)
        temporary=folder/'bilibili.json.tmp'
        try:
            with temporary.open('w',encoding='utf8') as f:
                protect(temporary);json.dump(cookies,f,ensure_ascii=False)
            temporary.replace(cookie_path());protect(cookie_path());CACHE.clear()
        finally:temporary.unlink(missing_ok=True)
        return True

def api_client(cookies=()):
    jar=httpx.Cookies()
    for c in cookies:jar.set(c['name'],c['value'],domain=c['domain'],path=c.get('path','/'))
    return httpx.Client(cookies=jar,trust_env=False,timeout=6,headers={'Referer':'https://www.bilibili.com/','User-Agent':'Mozilla/5.0'})

def bilibili_api_get(path,*,cookies=(),params=None):
    if path not in {'/x/web-interface/nav','/x/web-interface/view','/x/player/v2','/x/player/wbi/v2','/x/space/wbi/arc/search'}:raise ValueError('不支持的B站接口')
    with api_client(cookies) as c:
        response=c.get('https://api.bilibili.com'+path,params=params);response.raise_for_status();value=response.json()
    if not isinstance(value,dict):raise ValueError('B站接口响应异常')
    return value

def wbi_signed(params,nav):
 from urllib.parse import urlencode
 import hashlib
 image=nav['wbi_img'];lookup=''.join(image[k].rsplit('/',1)[-1].split('.')[0] for k in ('img_url','sub_url'))
 key=''.join(lookup[i] for i in [46,47,18,2,53,8,23,32,15,50,10,31,58,3,45,35,27,43,5,49,33,9,42,19,29,28,14,39,12,38,41,13])
 values={k:str(v) for k,v in sorted({**params,'wts':int(time.time())}.items())};values['w_rid']=hashlib.md5((urlencode(values)+key).encode()).hexdigest();return values


def validated():
    cookies=read_cookies()
    if not any(c['name']=='SESSDATA' and c['value'] for c in cookies):return {'status':'not_logged_in'},[],{}
    try:stamp=cookie_path().stat().st_mtime_ns
    except FileNotFoundError:return {'status':'not_logged_in'},[],{}
    if CACHE.get('stamp')==stamp and time.monotonic()<CACHE.get('until',0):return CACHE['result']
    try:
        nav=bilibili_api_get('/x/web-interface/nav',cookies=cookies);data=nav.get('data') or {}
        valid=nav.get('code')==0 and data.get('isLogin') is True
        state='logged_in' if valid else 'expired' if nav.get('code')==-101 or data.get('isLogin') is False else 'unknown'
        result=({'status':state},cookies if valid else [],data)
    except (httpx.HTTPError,ValueError):result=({'status':'unknown','message':'暂时无法验证B站登录，请检查网络；字幕不可用时仍可本地转写'},[],{})
    CACHE.update(stamp=stamp,until=time.monotonic()+30,result=result)
    return result

async def login_browser(epoch):
    global LOGIN_ERROR
    context=None
    try:
        from playwright.async_api import async_playwright
        profile=profile_path();profile.mkdir(parents=True,exist_ok=True);await asyncio.to_thread(protect,profile)
        async with async_playwright() as p:
            context=await p.chromium.launch_persistent_context(str(profile),headless=False,locale='zh-CN',args=['--no-proxy-server'])
            try:
                page=context.pages[0] if context.pages else await context.new_page()
                await page.goto('https://passport.bilibili.com/login',wait_until='domcontentloaded',timeout=45000)
                deadline=time.monotonic()+300
                while time.monotonic()<deadline:
                    if page.is_closed():return
                    cookies=await context.cookies('https://www.bilibili.com')
                    if any(c['name']=='SESSDATA' and c['value'] for c in cookies):
                        try:
                            nav=await asyncio.to_thread(bilibili_api_get,'/x/web-interface/nav',cookies=cookies)
                            if nav.get('code')==0 and (nav.get('data') or {}).get('isLogin') is True:
                                await asyncio.to_thread(save_cookies,cookies,epoch);return
                        except (httpx.HTTPError,ValueError):pass
                    await asyncio.sleep(1)
                LOGIN_ERROR='扫码登录已超时，请重新打开登录窗口'
            finally:await context.close()
    except asyncio.CancelledError:raise
    except Exception:LOGIN_ERROR='B站登录窗口未完成，请检查浏览器依赖或网络后重试'

async def stop():
    global LOGIN
    if LOGIN and not LOGIN.done():
        LOGIN.cancel()
        try:await LOGIN
        except asyncio.CancelledError:pass
    LOGIN=None

def admit():
    if os.environ.get('SHIWEN_PUBLIC')=='1':raise HTTPException(403,'B站登录仅支持本机私有版')

@router.get('/status')
async def status():
    admit()
    state,_,_=await asyncio.to_thread(validated)
    return {**state,'login_pending':bool(LOGIN and not LOGIN.done()),'login_error':LOGIN_ERROR}

@router.post('/login')
async def login():
    global LOGIN,LOGIN_ERROR
    admit()
    if LOGIN and not LOGIN.done():return {'login_pending':True}
    LOGIN_ERROR=None;LOGIN=asyncio.create_task(login_browser(LOGIN_EPOCH));return {'login_pending':True}

@router.delete('/login')
async def logout():
    global LOGIN_ERROR,LOGIN_EPOCH
    admit()
    with COOKIE_LOCK:LOGIN_EPOCH+=1
    await stop()
    with COOKIE_LOCK:CACHE.clear();cookie_path().unlink(missing_ok=True)
    try:
        target=profile_path().resolve()
        if target.parent!=store.DATA.resolve():raise OSError('会话目录不在拾文数据目录内')
        if target.exists():await asyncio.to_thread(shutil.rmtree,target)
    except OSError:raise HTTPException(409,'Cookie已删除，但浏览器目录仍被占用，请关闭B站登录窗口后再次登出')
    LOGIN_ERROR=None;return {'status':'not_logged_in','login_pending':False}
