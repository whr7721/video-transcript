"""Ordered, non-executable source blocks; no model rewriting during ingestion."""
import hashlib
import re
from urllib.parse import urljoin,urlsplit
from bs4 import BeautifulSoup,Tag
import trafilatura

VERSION='article-blocks-v1.2'


def safe_link(value,base=''):
    try:
        url=urljoin(base,value)
        p=urlsplit(url)
        return url if p.scheme in {'http','https'} and p.hostname and not p.username and not p.password else ''
    except (ValueError,TypeError):return ''


def parse(content,kind='html',source_url='',title=''):
    warnings=[];blocks=[]
    def add(type,text='',**attrs):
        if text.strip() or type=='image':blocks.append({'id':f'b{len(blocks)+1}','type':type,'text':text,**attrs})
    if kind=='text':
        title=title.strip() or next((x.strip()[:100] for x in content.splitlines() if x.strip()),'粘贴的文章')
        for p in re.split(r'\n\s*\n',content.strip()):
            pieces=re.split(r'(?m)^图片[ \t]*$',p)
            for n,piece in enumerate(pieces):
                if n:
                    warnings.append('粘贴内容含图片占位，但未包含原图。');add('paragraph','[原图未导入]')
                if piece.strip():add('paragraph',piece.strip())
        warnings.append('来自手动粘贴；无法确认原网页是否还有图片、链接或其他段落。')
        return finish(title,'',source_url,blocks,warnings,'pasted_text')
    soup=BeautifulSoup(content,'html.parser')
    page_text=soup.get_text(' ',strip=True)
    if any(x in page_text[:1800] for x in ['环境异常','访问过于频繁','请完成安全验证','安全验证后继续','验证你是真人']):
        raise ValueError('来源返回验证页面，没有读取到正文。请在浏览器正常打开后导入网页 HTML，或粘贴正文。')
    def meta(name):
        node=soup.find('meta',attrs={'property':name}) or soup.find('meta',attrs={'name':name})
        return node.get('content','') if node else ''
    title=title.strip() or meta('og:title') or (soup.title.get_text(strip=True) if soup.title else '')
    author=meta('author')
    root=soup.select_one('#js_content')
    platform='wechat' if urlsplit(source_url).hostname=='mp.weixin.qq.com' else 'web'
    if root:
        name=soup.select_one('#js_name');heading=soup.select_one('#activity-name')
        author=name.get_text(strip=True) if name else author
        title=title or (heading.get_text(strip=True) if heading else '')
        platform='wechat'
    elif platform=='wechat':raise ValueError('没有找到公众号正文；没有把提示页当作文章。可导入已打开页面的 HTML 或粘贴正文。')
    else:
        # The outer article on SSPAI also contains author/footer/recommendation widgets.
        root=soup.select_one('.article-body') if urlsplit(source_url).hostname=='sspai.com' else None
        root=root or soup.find('article') or soup.find('main')
    if root:
        parser='site-container'
        for n in root.select('script,style,noscript,iframe,form,button,input,nav,aside,footer,svg,canvas'):
            n.decompose()
        def walk(node):
            if not isinstance(node,Tag):
                if str(node).strip():add('paragraph',str(node).strip())
                return
            name=node.name
            if name=='img':
                src=safe_link(node.get('data-src') or node.get('data-original') or node.get('src',''),source_url)
                if src:add('image',node.get('alt','')[:500],url=src)
                else:warnings.append('一张图片没有可读取的公开地址。')
            elif name=='a':
                # Standalone links are retained in the destination appendix below.
                if not safe_link(node.get('href',''),source_url):add('paragraph',node.get_text(' ',strip=True))
                # Linked galleries still carry source content, even without link text.
                for image in node.find_all('img'):walk(image)
            elif name=='pre':add('code',node.get_text('',strip=False).strip('\n'))
            elif name=='table':
                rows=[[c.get_text(' ',strip=True) for c in r.find_all(['td','th'],recursive=False)] for r in node.find_all('tr')]
                rows=[r for r in rows if r]
                if rows:add('table','\n'.join('\t'.join(r) for r in rows),rows=rows)
            elif name in {'h1','h2','h3','h4','h5','h6'}:add('heading',node.get_text(' ',strip=True),level=int(name[1]))
            elif name in {'p','li','blockquote'} and not node.find(['p','li','pre','table','blockquote']):
                # Keep inline image positions instead of discarding them within paragraphs.
                pieces=[]
                def inline(child):
                    if not isinstance(child,Tag):pieces.append(str(child));return
                    if child.name=='img':
                        if ''.join(pieces).strip():add('paragraph',''.join(pieces).strip());pieces.clear()
                        walk(child)
                    elif child.name=='br':pieces.append('\n')
                    else:
                        for part in child.children:inline(part)
                for child in node.children:inline(child)
                if ''.join(pieces).strip():add('quote' if name=='blockquote' else 'paragraph',''.join(pieces).strip())
            else:
                for child in node.children:walk(child)
        walk(root)
        # Inline link destinations are a separate source appendix, never executable HTML.
        links=list(dict.fromkeys((a.get_text(' ',strip=True),safe_link(a.get('href',''),source_url)) for a in root.find_all('a',href=True)))
        for label,url in links[:80]:
            if url:add('link',label or url,url=url)
    else:
        parser='trafilatura-xml'
        xml=trafilatura.extract(content,url=source_url or None,output_format='xml',include_images=True,
                                 include_links=True,include_formatting=True,include_comments=False)
        if not xml:raise ValueError('未识别到文章正文，请改用粘贴正文或网页 HTML。')
        tree=BeautifulSoup(xml,'xml');main=tree.find('main')
        if main:
            for node in main.children:
                if not isinstance(node,Tag):continue
                text=node.get_text('',strip=False)
                if node.name=='graphic':
                    url=safe_link(node.get('src',''),source_url)
                    if url:add('image',node.get('alt',''),url=url)
                elif node.name=='code':add('code',text)
                elif node.name=='table':
                    rows=[[c.get_text(' ',strip=True) for c in r.find_all('cell')] for r in node.find_all('row')]
                    add('table',text,rows=rows)
                else:add('heading' if node.name=='head' else 'paragraph',text)
                for ref in node.find_all('ref'):
                    url=safe_link(ref.get('target',''),source_url)
                    if url:add('link',ref.get_text(),url=url)
                for img in node.find_all('graphic'):
                    url=safe_link(img.get('src',''),source_url)
                    if url:add('image',img.get('alt',''),url=url)
        warnings.append('通用规则提取；请核对正文是否有漏段或图表缺失。')
    if not any(b['text'].strip() for b in blocks):raise ValueError('正文为空，没有保存空文章。')
    if len(blocks)>3000 or sum(len(b['text']) for b in blocks)>200000:raise ValueError('文章超过本版处理上限。')
    warnings.append('已保存当前可提取内容，尚未逐段对照原网页确认完整性。')
    if platform not in {'wechat'} and any(x in page_text[:1500] for x in ['登录后查看全文','登录后阅读全文','付费阅读']):warnings.append('页面可能包含登录或付费截断，仅保存可见部分。')
    result=finish(title or '未命名文章',author,source_url,blocks,warnings,parser)
    time_node=soup.find('time',datetime=True)
    result['published_at']=meta('article:published_time') or meta('date') or (time_node['datetime'] if time_node else '')
    return result


def finish(title,author,url,blocks,warnings,parser):
    import json
    if not blocks or len(blocks)>3000 or sum(len(b['text']) for b in blocks)>200000:
        raise ValueError('正文为空或超过本版20万字/3000块上限。')
    return {'title':title[:300],'author':author[:200],'source_url':url,'blocks':blocks,
            'warnings':list(dict.fromkeys(warnings)),'parser':parser,'parser_version':VERSION,
            'completeness':'partial' if any('原图' in w or '截断' in w for w in warnings) else 'unverified',
            'content_hash':hashlib.sha256(json.dumps(blocks,ensure_ascii=False,sort_keys=True).encode()).hexdigest()}
