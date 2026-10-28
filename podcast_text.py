"""Publisher text is data, not ASR. Untimed text never receives invented times."""
import html
import re


def parse(data, kind):
    if not data or len(data)>2_000_000:raise ValueError('节目文字为空或超过2MB')
    try:text=data.decode('utf-8-sig')
    except UnicodeError:raise ValueError('节目文字须为UTF-8编码；可改选本地转写') from None
    if '\x00' in text or re.search(r'<\s*(?:!doctype|html|script|body)\b',text,re.I):
        raise ValueError('来源不是支持的纯文本/字幕，请改选本地转写')
    if kind=='text/plain':
        paragraphs=re.split(r'\n\s*\n',text.strip())
        # Bound paragraph size so one giant block does not disable all passage processing.
        segments=[{'text':p[i:i+3000]} for p in paragraphs if p.strip() for i in range(0,len(p),3000)]
    elif kind=='text/vtt':
        if not text.lstrip().startswith('WEBVTT'):raise ValueError('节目字幕不是有效WebVTT')
        def timestamp(value):
            parts=value.replace(',','.').split(':')
            if len(parts) not in (2,3):raise ValueError('字幕时间格式无效')
            numbers=[float(p) for p in parts]
            if any(n<0 for n in numbers) or any(n>=60 for n in numbers[1:]):raise ValueError('字幕时间范围无效')
            return sum(n*60**(len(numbers)-i-1) for i,n in enumerate(numbers))
        segments=[]
        for cue in re.split(r'\n\s*\n',text.replace('\r\n','\n')):
            lines=cue.splitlines();indices=[i for i,line in enumerate(lines) if '-->' in line]
            if not indices:continue
            index=indices[0];match=re.fullmatch(r'\s*([\d:.]+)\s+-->\s+([\d:.]+)(?:\s+.*)?',lines[index])
            if not match:raise ValueError('字幕时间格式无效')
            start,end=map(timestamp,match.groups())
            if not start<end<=10800.5 or (segments and start<segments[-1]['start']):raise ValueError('字幕超时或顺序无效')
            body=html.unescape(re.sub('<[^>]*>','','\n'.join(lines[index+1:]))).strip()
            if body:segments.append({'text':body,'start':start,'end':end})
    else:raise ValueError('首版仅支持节目纯文本和WebVTT')
    raw='\n\n'.join(s['text'] for s in segments)
    if not raw.strip() or len(raw)>200000 or len(segments)>2000:raise ValueError('节目文字为空或超出20万字/2000块限制')
    return {'text':raw,'segments':segments,'engine':'节目提供文字 · 非语音识别',
            'timing_precision':'publisher_cues' if kind=='text/vtt' else 'none',
            'review_note':'节目提供的文字，完整性和准确性未人工核验；未调用ASR或文本模型。',
            'cost_yuan':0}
