"""Private XHS auth reusing Shiwen Bilibili lifecycle; own restricted HTTP plus MIT xhshow."""
import asyncio,base64,json,os,shutil,subprocess,time,threading
from pathlib import Path
import httpx
from fastapi import APIRouter,HTTPException
import store

router=APIRouter(prefix='/api/xiaohongshu')
LOGIN=None
LOGIN_ERROR=None
CACHE={}
COOKIE_LOCK=threading.RLock()
LOGIN_EPOCH=0

def cookie_path():return store.DATA/'cookies'/'xiaohongshu.json'
def profile_path():return store.DATA/'browser-xiaohongshu'

def protect(path):
    path=Path(path)
    if os.name!='nt':path.chmod(0o700 if path.is_dir() else 0o600);return
    # Replace the DACL, rather than relying on chmod (which does not restrict Windows readers).
    target=str(path).replace("'","''")
    kind='Directory' if path.is_dir() else 'File'
    inheritance="[System.Security.AccessControl.InheritanceFlags]'ContainerInherit,ObjectInherit'" if path.is_dir() else '[System.Security.AccessControl.InheritanceFlags]::None'
    script=f"$sid=[System.Security.Principal.WindowsIdentity]::GetCurrent().User;$acl=New-Object System.Security.AccessControl.{kind}Security;$acl.SetAccessRuleProtection($true,$false);$rule=New-Object System.Security.AccessControl.FileSystemAccessRule($sid,[System.Security.AccessControl.FileSystemRights]::FullControl,{inheritance},[System.Security.AccessControl.PropagationFlags]::None,[System.Security.AccessControl.AccessControlType]::Allow);$acl.AddAccessRule($rule);[System.IO.{kind}]::SetAccessControl('{target}',$acl)"
    result=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-EncodedCommand',base64.b64encode(script.encode('utf-16le')).decode()],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW)
    if result.returncode:raise RuntimeError('无法设置小红书会话的本机访问权限，未保存登录态')

def read_cookies():
    try:
        value=json.loads(cookie_path().read_text(encoding='utf8'))
        if not isinstance(value,list):return []
        return [c for c in value if isinstance(c,dict) and c.get('domain','').lstrip('.')=='xiaohongshu.com' and isinstance(c.get('name'),str) and isinstance(c.get('value'),str)]
    except (OSError,ValueError):return []

def save_cookies(cookies,epoch=None):
    with COOKIE_LOCK:
        if epoch is not None and epoch!=LOGIN_EPOCH:return False
        folder=cookie_path().parent;folder.mkdir(parents=True,exist_ok=True);protect(folder)
        temporary=folder/'xiaohongshu.json.tmp'
        try:
            with temporary.open('w',encoding='utf8') as f:
                protect(temporary);json.dump(cookies,f,ensure_ascii=False)
            temporary.replace(cookie_path());protect(cookie_path());CACHE.clear()
        finally:temporary.unlink(missing_ok=True)
        return True

def xhs_api(path,*,cookies=(),payload=None):
    if path not in {'/api/sns/web/v1/user/selfinfo','/api/sns/web/v1/feed'}:raise ValueError('不支持的小红书接口')
    from xhshow import Xhshow
    cookie='; '.join(c['name']+'='+c['value'] for c in cookies)
    signer=Xhshow();method='POST' if payload is not None else 'GET'
    signed=signer.sign_headers_post(path,cookies=cookie,payload=payload) if payload is not None else signer.sign_headers_get(path,cookies=cookie,params={})
    headers={k:str(v) for k,v in signed.items() if k.lower() in {'x-s','x-t','x-s-common','x-b3-traceid'}}
    headers.update({'Cookie':cookie,'Content-Type':'application/json;charset=UTF-8','Origin':'https://www.xiaohongshu.com','Referer':'https://www.xiaohongshu.com/','User-Agent':'Mozilla/5.0'})
    with httpx.Client(trust_env=False,timeout=20,follow_redirects=False) as client:
        r=client.request(method,'https://edith.xiaohongshu.com'+path,headers=headers,content=json.dumps(payload,separators=(',',':'),ensure_ascii=False).encode() if payload is not None else None)
        if r.status_code!=200:raise ValueError('小红书接口暂不可用，请检查登录或平台验证')
        value=r.json()
    if not isinstance(value,dict) or value.get('success') is not True:raise ValueError('小红书登录失效、内容不可用或需平台验证')
    return value


def validated():
    cookies=read_cookies()
    if not cookies:return {'status':'not_logged_in'},[],{}
    try:
        value=xhs_api('/api/sns/web/v1/user/selfinfo',cookies=cookies)
        valid=(value.get('data') or {}).get('result',{}).get('success') is True
        return {'status':'logged_in' if valid else 'expired'},cookies if valid else [],value
    except (ValueError,httpx.HTTPError):return {'status':'expired'},[],{}


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
                await page.goto('https://www.xiaohongshu.com/explore',wait_until='domcontentloaded',timeout=45000)
                deadline=time.monotonic()+300
                while time.monotonic()<deadline:
                    if page.is_closed():return
                    cookies=await context.cookies('https://www.xiaohongshu.com')
                    if any(c['name']=='web_session' and c['value'] for c in cookies):
                        try:
                            nav=await asyncio.to_thread(xhs_api,'/api/sns/web/v1/user/selfinfo',cookies=cookies)
                            if (nav.get('data') or {}).get('result',{}).get('success') is True:
                                await asyncio.to_thread(save_cookies,cookies,epoch);return
                        except (httpx.HTTPError,ValueError):pass
                    await asyncio.sleep(3)
                LOGIN_ERROR='扫码登录已超时，请重新打开登录窗口'
            finally:await context.close()
    except asyncio.CancelledError:raise
    except Exception:LOGIN_ERROR='小红书登录窗口未完成，请检查浏览器依赖或网络后重试'

async def stop():
    global LOGIN
    if LOGIN and not LOGIN.done():
        LOGIN.cancel()
        try:await LOGIN
        except asyncio.CancelledError:pass
    LOGIN=None

def admit():
    if os.environ.get('SHIWEN_PUBLIC')=='1':raise HTTPException(403,'小红书登录仅支持本机私有版')

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
    except OSError:raise HTTPException(409,'Cookie已删除，但浏览器目录仍被占用，请关闭小红书登录窗口后再次登出')
    LOGIN_ERROR=None;return {'status':'not_logged_in','login_pending':False}
