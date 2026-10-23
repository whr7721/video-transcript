"""RSS metadata only. Bytes are fetched by the caller, never by the parser."""
import hashlib
import xml.etree.ElementTree as ET
from urllib.parse import urljoin
import feedparser
from article_fetch import public_url

MAX_FEED_BYTES = 8_000_000
MAX_EPISODES = 500


def duration(value):
    try:
        parts = str(value).strip().split(':')
        if not 1 <= len(parts) <= 3:
            return None
        numbers = [int(p) for p in parts]
        if any(n < 0 for n in numbers) or any(n >= 60 for n in numbers[1:]):
            return None
        result = 0
        for number in numbers:
            result = result * 60 + number
        return result if result > 0 else None
    except (TypeError, ValueError):
        return None


def parse(data, feed_url):
    if not isinstance(data, bytes) or not data or len(data) > MAX_FEED_BYTES:
        raise ValueError('RSS为空或超过8MB')
    feed_url = public_url(feed_url)
    # Inspect normalized XML bytes too, including UTF-16/32 declarations.
    normalized = data.replace(b'\x00', b'').upper()
    if b'<!DOCTYPE' in normalized or b'<!ENTITY' in normalized:
        raise ValueError('不支持含DTD或实体声明的RSS')
    # The released parser does not implement the podcast namespace. Read only this
    # standard's metadata from bounded, well-formed XML, retaining feedparser for RSS/Atom.
    pull=ET.XMLPullParser(events=('start','end'));depth=0;nodes=0;tree=None
    try:
        for offset in range(0,len(data),65536):
            pull.feed(data[offset:offset+65536])
            for event,node in pull.read_events():
                if event=='start':
                    if tree is None:tree=node
                    depth+=1;nodes+=1
                    if depth>40 or nodes>100000:raise ValueError('RSS结构过于复杂')
                else:depth-=1
        pull.close()
    except ET.ParseError:raise ValueError('RSS XML格式无效，请核对RSS地址') from None
    parsed=feedparser.parse(data)
    if not parsed.version or not parsed.entries:raise ValueError('没有找到单集，请提供公开RSS地址')
    if parsed.get('bozo'):raise ValueError('RSS格式异常，未将部分解析结果作为完整列表')
    xml_items=tree.findall('./channel/item') or tree.findall('{http://www.w3.org/2005/Atom}entry')

    def safe_url(value):
        try:
            return public_url(urljoin(feed_url, value)) if value else None
        except ValueError:
            return None

    episodes = []
    for position, item in enumerate(parsed.entries[:MAX_EPISODES]):
        media = next((safe_url(e.get('href')) for e in item.get('enclosures', [])
                      if safe_url(e.get('href'))), None)
        transcripts = []
        rows=[]
        if position<len(xml_items):
            rows=[node.attrib for node in xml_items[position] if node.tag in {
                '{https://podcastindex.org/namespace/1.0}transcript','{http://podcastindex.org/namespace/1.0}transcript'}]
        for row in rows:
            link = safe_url(row.get('url'))
            kind = row.get('type', '').split(';')[0].strip().lower()
            if link and kind in {'text/plain', 'text/vtt'}:
                transcripts.append({'url': link, 'type': kind})
        chapter_url = None
        if position < len(xml_items):
            for node in xml_items[position]:
                if node.tag in {'{https://podcastindex.org/namespace/1.0}chapters','{http://podcastindex.org/namespace/1.0}chapters'} and node.attrib.get('type') == 'application/json+chapters':
                    chapter_url = safe_url(node.attrib.get('url'))
                    break
        guid = str(item.get('id', ''))[:2000]
        identity = '\n'.join((feed_url, guid, media or '', str(item.get('title','')), str(item.get('published',''))))
        episodes.append({'id': hashlib.sha256(identity.encode()).hexdigest()[:24],
                         'guid': guid or None, 'title': str(item.get('title', '未命名单集'))[:500],
                         'published': str(item.get('published', ''))[:200],
                         'duration_seconds': duration(item.get('itunes_duration')),
                         'audio_url': media, 'transcripts': transcripts, 'chapters_url': chapter_url,
                         'importable': bool(media or transcripts)})
    return {'schema_version': 1, 'feed_url': feed_url,
            'title': str(parsed.feed.get('title', '未命名节目'))[:500],
            'episodes': episodes, 'truncated': len(parsed.entries) > MAX_EPISODES,
            'feed_hash': hashlib.sha256(data).hexdigest()}
