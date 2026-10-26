"""Lossless region selection. Derived text is always copied from immutable OCR."""
import hashlib
import json
import re
from collections import Counter

VERSION = 'ocr-selection-v1'
LOW_SCORE = .85
CATEGORIES = {'body', 'watermark', 'furniture', 'interface', 'unknown'}
STATES = {'keep', 'exclude', 'fold'}


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def originals(item):
    images = {b['id']: b for b in item.get('blocks', []) if b['type'] == 'image'}
    result = []
    for block in item.get('blocks', []):
        if block['type'] != 'ocr':
            continue
        image = images.get(block.get('source_image_id'), {})
        raw = image.get('ocr_original', {}).get(block.get('region_id'))
        # Legacy unedited regions can be read, but a correction is never passed off as OCR.
        text = raw.get('text', '') if raw is not None else (block.get('text', '') if not block.get('corrected') else '')
        row = {**block, 'text': text, 'page': image.get('page', 1),
               'score': raw.get('score') if raw is not None else block.get('score'),
               'bbox': raw.get('bbox') if raw is not None else block.get('bbox'),
               'width': image.get('width'), 'height': image.get('height')}
        row['source_key'] = digest([row['id'], text, row.get('score'), row.get('bbox'), image.get('ocr_version')])
        result.append(row)
    return result


def source_hash(item):
    return digest([VERSION, [(r['id'], r['source_key']) for r in originals(item)]])


def rules(item):
    rows = originals(item)
    repeats = Counter()
    for page in {r['page'] for r in rows}:
        repeats.update({re.sub(r'\s+', '', r['text']) for r in rows if r['page'] == page})
    result = []
    for row in rows:
        text = row['text'].strip()
        box, height = row.get('bbox'), row.get('height')
        edge = bool(box and height and (box[3] <= height*.09 or box[1] >= height*.91))
        category, state, reason, uncertain = 'body', 'keep', '未发现明确杂讯，保留原文', False
        if not text:
            category, state, reason = 'unknown', 'fold', '没有可用机器原文；人工校对仍在对照栏'
        elif edge and re.fullmatch(r'(?:\d{1,2}:\d{2}|\d{1,3}%|[45]G|返回|点赞|收藏|分享|评论|关注)', text):
            category, state, reason = 'interface', 'exclude', '边缘位置且整区匹配界面标记'
        else:
            # Position and repetition alone cannot establish that a heading is noise.
            repeated = repeats[re.sub(r'\s+', '', text)] >= 3
            uncertain = edge or repeated or bool(re.search(r'水印|抖音号|小红书号|未经授权|禁止转载|点击关注', text))
            if uncertain:
                category, reason = 'unknown', '语义待判断，当前保留'
        score = row.get('score')
        if isinstance(score, (int, float)) and score < LOW_SCORE:
            state, reason = 'fold', '识别分低于0.85，仅折叠不认定为杂讯'
            uncertain = False
        result.append({**row, 'category': category, 'state': state, 'reason': reason,
                       'origin': 'rule', 'uncertain': uncertain})
    return result


def selection(item, mode='effective'):
    saved = item.get('reading_selection', {})
    result = []
    for row in rules(item):
        if mode != 'rules':
            for origin, field in [('ai', 'ai'), ('human', 'manual')]:
                if mode == 'ai' and origin == 'human':
                    continue
                decision = saved.get(field, {}).get(row['id'])
                if not decision or decision.get('source_key') != row['source_key']:
                    continue
                category = decision.get('category')
                if category not in CATEGORIES:
                    continue
                state = decision.get('state') if origin == 'human' else ('exclude' if category in {'watermark', 'furniture', 'interface'} else 'keep')
                if state not in STATES:
                    continue
                # AI cannot undo low-confidence folding; explicit human restoration can.
                if origin == 'ai' and row['state'] == 'fold':
                    continue
                row = {**row, 'category': category, 'state': state, 'origin': origin,
                       'reason': '人工筛选' if origin == 'human' else 'AI仅分类，文字取自原始OCR', 'uncertain': category == 'unknown'}
        result.append(row)
    return result


def blocks(item, include_hidden=False):
    return [{k: r[k] for k in ('id', 'text', 'source_image_id', 'bbox', 'source_key', 'state') if k in r}
            for r in selection(item) if r['text'].strip() and (include_hidden or r['state'] == 'keep')]


def view(item):
    if item.get('kind') != 'images':
        return item
    rows = selection(item)
    return {**item, 'reading': {'version': VERSION, 'source_hash': source_hash(item),
            'revision': item.get('reading_selection', {}).get('revision', 0), 'regions': rows,
            'counts': dict(Counter(r['state'] for r in rows))}}


def checked_ai(value, candidates):
    """Reject the whole response on extra fields, unknown IDs or duplicate IDs."""
    if not isinstance(value, dict) or set(value) != {'decisions'} or not isinstance(value['decisions'], list):
        raise ValueError('分类格式无效；维持规则版')
    allowed = {r['id']: r for r in candidates}
    decisions = {}
    for decision in value['decisions']:
        if not isinstance(decision, dict) or set(decision) != {'id', 'category'}:
            raise ValueError('AI只能返回区域ID和类别；维持规则版')
        ident, category = decision['id'], decision['category']
        if not isinstance(ident, str) or ident not in allowed or ident in decisions or not isinstance(category, str) or category not in CATEGORIES:
            raise ValueError('分类引用无效；维持规则版')
        decisions[ident] = {'category': category, 'source_key': allowed[ident]['source_key']}
    if set(decisions) != set(allowed):
        raise ValueError('分类结果遗漏区域；维持规则版')
    return decisions


def override(ident, block_id, source_key, revision, category, state):
    import articles
    import documents
    with articles.LOCK:
        item = articles.get(ident)
        if not item or item.get('kind') != 'images' or item.get('status') != 'ready':
            raise ValueError('请等待图片材料就绪')
        saved = item.setdefault('reading_selection', {})
        row = next((r for r in originals(item) if r['id'] == block_id), None)
        if not row or row['source_key'] != source_key or saved.get('revision', 0) != revision:
            raise documents.Conflict('原文或筛选已有更新，请刷新；未覆盖其他筛选')
        manual = saved.setdefault('manual', {})
        if category is None and state is None:
            manual.pop(block_id, None)
        elif category in CATEGORIES and state in STATES:
            manual[block_id] = {'source_key': source_key, 'category': category, 'state': state}
        else:
            raise ValueError('筛选类别或显示状态无效')
        saved['revision'] = revision+1
        articles.save(item)
        return view(item)
