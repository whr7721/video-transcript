"""ASR 英文专名纠正（后处理层）。

sherpa-onnx 1.13.8 里 SenseVoice 属 non-transducer：`OfflineRecognizer.from_sense_voice()`
没有 hotwords_file/hotwords_score，官方文档也写明只有 transducer 模型（且必须
modified_beam_search）支持热词，所以热词走不了原生。这里在转写结果上做一次归一化替换：
只改展示稿与下游，未纠正原文另存 raw_text，纠正明细写 corrections。
"""
import json
import unicodedata
from pathlib import Path

FILE_NAME = 'hotwords.json'

# 键是规范写法，值是本地识别实测到的变体；大小写、空格、标点不敏感。
DEFAULT = {
    'DeepSeek': ['deep sickick', 'deep sick', 'deeps', 'deepseak', 'dedes'],
    'harness': ['harnes', 'honess', 'harnessness', '哈nes'],
    'SnoLuma': ['snluma', 'snoluma', 'snow luer', 'snowluer', 'snow鲁码', 'snow鲁马', 'snow路码', 'snow撸码'],
}


def _clean(term):
    return ''.join(ch.casefold() for ch in str(term) if ch.isalnum() or '\u3400' <= ch <= '\u9fff')


def _path():
    from store import DATA
    return Path(DATA) / FILE_NAME


def ensure_file():
    """首次使用时落一份可编辑词表；失败不阻断转写。"""
    path = _path()
    if path.is_file():
        return path
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({'_说明': '键是规范写法，值是识别变体（大小写/空格/标点不敏感）；改完下一条转写生效。',
                                    **DEFAULT}, ensure_ascii=False, indent=1), encoding='utf-8')
    except OSError:
        pass
    return path


def table():
    """默认表 + data/hotwords.json（用户表按规范写法追改变体，不丢默认项）。"""
    merged = {key: list(values) for key, values in DEFAULT.items()}
    path = ensure_file()
    if path.is_file():
        try:
            user = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            user = {}
        if isinstance(user, dict):
            existing = {key.casefold(): key for key in merged}
            for key, values in user.items():
                if not isinstance(key, str) or key.startswith('_') or not isinstance(values, list):
                    continue
                name = existing.get(key.casefold(), key)
                existing.setdefault(key.casefold(), name)
                merged.setdefault(name, [])
                for value in values:
                    if isinstance(value, str) and value.strip() and value not in merged[name]:
                        merged[name].append(value)
    return merged


def _variants(mapping):
    pairs = []
    seen = set()
    for canonical, values in mapping.items():
        for value in values:
            normalized = _clean(value)
            if len(normalized) < 4 or normalized in seen or normalized == _clean(canonical):
                continue
            seen.add(normalized)
            pairs.append((normalized, canonical, value))
    pairs.sort(key=lambda item: len(item[0]), reverse=True)
    return pairs


def _boundary(text, start, end, normalized):
    """拉丁字母/数字紧邻时不算命中（避免 harnes 吃掉 harness 的尾巴）。"""
    if normalized[0].isascii() and start > 0 and (text[start - 1].isalnum() and text[start - 1].isascii()):
        return False
    if normalized[-1].isascii() and end < len(text) and (text[end].isalnum() and text[end].isascii()):
        return False
    return True


def correct(text, mapping=None):
    """返回 (纠正后文本, 明细列表)。替换按规范化长度从长到短、跳过重叠。"""
    if not isinstance(text, str) or not text.strip():
        return text, []
    normalized, index = [], []
    for position, char in enumerate(text):
        for part in unicodedata.normalize('NFKC', char).casefold():
            if part.isalnum() or '\u3400' <= part <= '\u9fff':
                normalized.append(part)
                index.append(position)
    if not normalized:
        return text, []
    haystack = ''.join(normalized)
    taken = []
    hits = {}
    for needle, canonical, label in _variants(mapping or table()):
        start = haystack.find(needle)
        while start != -1:
            end = start + len(needle)
            span = (index[start], index[end - 1] + 1)
            if all(span[1] <= left or span[0] >= right for left, right, _ in taken) and _boundary(text, *span, needle):
                taken.append((span[0], span[1], canonical))
                hits.setdefault(canonical, {}).setdefault(label, 0)
                hits[canonical][label] += 1
            start = haystack.find(needle, start + 1)
    if not taken:
        return text, []
    taken.sort()
    pieces, cursor = [], 0
    for left, right, canonical in taken:
        pieces.append(text[cursor:left])
        pieces.append(canonical)
        cursor = right
    pieces.append(text[cursor:])
    details = [{'term': canonical, 'variants': variants, 'count': sum(variants.values())}
               for canonical, variants in hits.items()]
    details.sort(key=lambda item: (-item['count'], item['term']))
    return ''.join(pieces), details


def apply(result, mapping=None):
    """把纠正结果写回转写记录：text/segments 纠正，raw_text 保留原文，corrections 记明细。"""
    if not isinstance(result, dict) or 'corrections' in result:
        return result
    mapping = mapping or table()
    text, details = correct(result.get('text', ''), mapping)
    segments = result.get('segments') or []
    corrected_segments = []
    for segment in segments:
        if isinstance(segment, dict) and isinstance(segment.get('text'), str):
            fixed, _ = correct(segment['text'], mapping)
            corrected_segments.append({**segment, 'text': fixed})
        else:
            corrected_segments.append(segment)
    total = sum(item['count'] for item in details)
    result = {**result, 'corrections': details}
    if total:
        result['raw_text'] = result.get('text', '')
        result['text'] = text
        if corrected_segments:
            result['segments'] = corrected_segments
        note = result.get('review_note') or ''
        result['review_note'] = (note.rstrip('。') + '；' if note else '') + f'已按专名表纠正 {total} 处英文专名（原始识别保留在 raw_text）'
    return result
