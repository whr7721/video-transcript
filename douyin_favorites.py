"""Authenticated favorites enumeration; runs inside Shiwen's owned browser context.

Endpoint semantics checked against F2 (Apache-2.0), no F2 code/dependency copied.
"""
import asyncio
import re
import hashlib

async def collect(page, context, limit=20):
    if not 1 <= limit <= 100:
        raise ValueError('收藏条数须在1到100之间')
    await page.goto('https://www.douyin.com/user/self?showTab=collection', wait_until='domcontentloaded', timeout=45000)
    await asyncio.sleep(3)
    tab=page.get_by_text('收藏',exact=True)
    if await tab.count():
        await tab.first.click()
        await asyncio.sleep(2)
    cookies = await context.cookies(['https://www.douyin.com'])
    if not any(c['name'] in {'sessionid', 'sessionid_ss'} and c['value'] for c in cookies):
        raise RuntimeError('抖音收藏需要登录，请在设置重新登录抖音')
    uid=next((c['value'] for c in cookies if c['name']=='uid_tt'),None)
    if not uid:raise RuntimeError('未能确认收藏所属账号，请重新登录后重试')
    identity=hashlib.sha256(uid.encode()).hexdigest()[:24]
    # The page's own fetch is same-origin and uses its authenticated browser session.
    posts = []; seen = set(); cursor = 0; cursors = set()
    for _ in range(10):
        raw = await page.evaluate('''async ({cursor,count}) => {
          const r = await fetch('/aweme/v1/web/aweme/listcollection/?device_platform=webapp&aid=6383&channel=channel_pc_web', {
            method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/x-www-form-urlencoded; charset=UTF-8'},
            body:new URLSearchParams({cursor:String(cursor),count:String(count)}).toString()});
          if (!r.ok) return {http_error:r.status};
          try { return await r.json(); } catch { return {invalid_json:true}; }
        }''', {'cursor':cursor,'count':min(20,limit-len(posts))})
        rows, more, next_cursor = parse_page(raw)
        for post in rows:
            ident = str(post.get('aweme_id',''))
            if re.fullmatch(r'\d{15,22}',ident) and ident not in seen:
                seen.add(ident);posts.append(post)
        if len(posts)>=limit or not more:
            return {'status':'ok','account':identity,'posts':posts[:limit],'has_more':more,'cursor':next_cursor}
        if str(next_cursor) in cursors or str(next_cursor)==str(cursor):
            raise RuntimeError('收藏分页未前进，请稍后重试，未将结果当作完整收藏')
        cursors.add(str(cursor));cursor=next_cursor
        await asyncio.sleep(2)
    raise RuntimeError('收藏分页达到本次检查上限，请减少条数后重试')

def parse_page(raw):
    if not isinstance(raw,dict) or raw.get('status_code',0)!=0 or 'has_more' not in raw:
        raise RuntimeError('抖音收藏未返回有效列表，请检查登录状态或验证提示后重试')
    rows=raw.get('aweme_list')
    if not isinstance(rows,list):
        raise RuntimeError('抖音收藏列表格式异常，未将其当作空收藏')
    return rows,bool(raw['has_more']),raw.get('cursor',raw.get('max_cursor',0))

def metadata(result):
    items=[]
    for e in result.get('posts',[]):
        ident=str(e.get('aweme_id',''))
        if not re.fullmatch(r'\d{15,22}',ident):continue
        kind='note' if e.get('images') else 'video'
        items.append({'id':ident,'title':e.get('desc') or '未命名收藏',
            'url':f'https://www.douyin.com/{kind}/{ident}',
            'published':e.get('create_time'),'duration':((e.get('video') or {}).get('duration') or 0)/1000,
            'media_kind':kind,'author':(e.get('author') or {}).get('nickname')})
    return {'identity':'douyin-self-collection:'+result['account'],'title':'我的抖音收藏','items':items,'status':'ok','window_has_more':bool(result.get('has_more'))}
