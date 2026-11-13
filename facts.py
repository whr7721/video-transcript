"""转写稿 → 概览 / 事实卡 / 步骤流。只做提取，不判断用途。

音频转文字是唯一不可替代的一步；剩下的都是可选视图，想要哪个显式要，
默认只打印概览和文件路径。

    python facts.py <job_id>                  # 概览：时长、字数、视频/音频在哪
    python facts.py <job_id> --facts          # 带时间码的事实卡 → facts.md
    python facts.py <job_id> --steps          # 操作流 → steps.md
    python facts.py <job_id> --recorrect      # 用当前 hotwords 重跑专名纠正

不给的东西：类型判定、用途建议、该洗稿还是该照着做。这些读一遍文字就有答案，
写死在规则里只会挡住别的用法。

也不替你做抽帧：视频路径直接印出来，怎么抽、抽哪几帧，按你要看的东西定。
"""
import argparse
import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

# ---------------------------------------------------------------- 切句

SPLIT = re.compile(r"(?<=[。！？；\n])")
SPLIT_FINE = re.compile(r"(?<=[。！？；，,\n])")
FINE_MAX = 45


def sentences_of(segments, min_chars=6, fine=False):
    """把 VAD 段切成句，按字符比例估算每句的起始时间。

    min_chars 默认 6 适合事实卡（碎片句没信息）；抽步骤时传 4，因为操作句本来就短。
    fine=True 时超过 FINE_MAX 字的句子再按逗号拆一层——短句拆开会丢主语。
    """
    out = []
    for seg in segments:
        text = (seg.get("text") or "").strip()
        if not text:
            continue
        start, end = seg.get("start") or 0, seg.get("end") or 0
        span = max(end - start, 0)
        total = max(len(text), 1)
        cursor = 0
        for piece in SPLIT.split(text):
            for sub in (SPLIT_FINE.split(piece) if fine and len(piece) > FINE_MAX else [piece]):
                sub = sub.strip()
                if len(sub) < min_chars:
                    cursor += len(sub)
                    continue
                at = start + span * (cursor / total)
                out.append({"t": round(at, 1), "text": sub})
                cursor += len(sub)
    return out


# ---------------------------------------------------------------- 信号

OP = re.compile(r"(?:打开|点击|点开|双击|右键|选中|勾选|取消勾选|输入|填上|填入|粘贴|拖到|拖进|"
                r"上传|导入|导出|保存|复制|删除|新建|添加|设置|改为|改成|调成|调到|切换到|选择|挑一|"
                r"注册|登录|安装|下载|重启|刷新|发布|生成|运行|执行|按下|按住|滑动|滚动|"
                r"准备|建一|建个|存进|放进|丢进|交给|发给|告诉|让他|要求|试听|比对|录制|贴上|"
                r"改一遍|过一遍|跑一遍|算一遍|导出来|存下来|拿出来|换掉|去掉|加上|勾上)")
SEQ = re.compile(r"(?:第一步|第二步|第三步|第四步|首先|其次|然后|接着|接下来|下一步|最后一步|"
                 r"现在我们来|我们先把|我们先|再来|再把|在这里|之后呢|最后)")
UI = re.compile(r"(?:按钮|菜单|选项|面板|窗口|界面|工具栏|下拉|弹窗|设置页|标签页|输入框|"
                r"时间轴|轨道|图层|画布|文件夹|路径|官网|后台|控制台|账号|登录态|快捷键)")
# 只要带数值的规格。「参数」「默认值」这种没有值的裸词不算数——列出来等于没列。
PARAM = re.compile(r"(?:\d+(?:\.\d+)?\s*(?:px|像素|帧|fps|kb|mb|gb|hz|khz|db|%|倍|k\b))|"
                   r"(?:\d{3,4}\s*[*x×]\s*\d{3,4})|(?:\d+\s*:\s*\d+)|"
                   r"(?:\d+(?:\.\d+)?\s*(?:秒|分钟|小时|元|块))|(?:\d+(?:\.\d+)?\s*[bB]参数)",
                   re.I)
WARN = re.compile(r"(?:注意|不然|否则|记得|切记|一定要|千万别|容易出错|会报错|踩坑|避坑|"
                  r"如果出现|解决办法|亲测|实测|建议你|千万不要)")
TOOL = re.compile(r"(?:剪映|即梦|可灵|通义|千问|豆包|ChatGPT|Claude|DeepSeek|Midjourney|ComfyUI|"
                  r"Stable\s?Diffusion|Photoshop|Figma|Premiere|CapCut|DaVinci|达芬奇|Audition|"
                  r"Whisper|Edge[- ]?TTS|ffmpeg|Python|GitHub|Vercel|WorkBuddy|Cursor|Trae|"
                  r"Coze|扣子|n8n|Dify|API|Token|Plugin|MCP|Skill|Prompt|提示词|小程序|智能体|"
                  r"Obsidian|Notion|Excel|WPS|Blender|After\s?Effects)", re.I)

YEAR = re.compile(r"(?:1[5-9]\d{2}|20[0-2]\d)\s*年")
NUM = re.compile(r"\d+(?:\.\d+)?\s*(?:万|亿|千|百|米|公里|吨|美元|加元|英镑|欧元|人|名|天|小时|分钟|岁|层)")
NAR = re.compile(r"(?:爆炸|沉没|失窃|倒塌|去世|出生|抢|炸|烧|逃|救|判决|起诉|签署|发明|发现|"
                 r"遇难|死亡|幸存|辞职|拒|签字|营救|追捕|拍卖|赠|夺|拦|投降|破产|上市|失踪|绑架)")
QUOTE = re.compile(r"[「“\"][^」”\"]{2,40}[」”\"]")
INFO = re.compile(r"(?:1[5-9]\d{2}|20[0-2]\d)\s*年|"
                  r"\d+(?:\.\d+)?\s*(?:万|亿|千|百|米|公里|吨|美元|加元|英镑|欧元|元|人|名|天|"
                  r"小时|分钟|秒|%|倍|岁|帧|px)")

# 事实卡打分：越靠前越像「能被复述出来的具体东西」
RULES = [
    ("年份", re.compile(r"(?:1[5-9]\d{2}|20[0-2]\d)\s*年?"), 4),
    ("数字", re.compile(r"\d+(?:\.\d+)?\s*(?:万|亿|千|百|米|公里|千米|吨|美元|加元|英镑|欧元|人|名|天|年|小时|分钟|秒|%|倍|层|岁)"), 3),
    ("引语", QUOTE, 3),
    ("专名", re.compile(r"[A-Za-z][A-Za-z'.\- ]{2,30}"), 2),
    ("机构", re.compile(r"(?:大学|学院|银行|公司|集团|博物馆|美术馆|图书馆|研究所|法院|议会|政府|省政府|市政府|军队|海军|陆军|医院|教堂|基金会|协会|电视台|时报|邮报|日报)"), 2),
    ("地名", re.compile(r"(?:州|省|郡|市|镇|村|岛|港|湾|河|山|广场|公园|大道|街)"), 1),
    ("转折", re.compile(r"(?:但是|但|其实|结果|直到|后来|最后|没想到|反而|然而|可是|偏偏|竟然)"), 1),
    ("动作", re.compile(r"(?:发生|爆炸|沉没|失窃|倒塌|去世|出生|抢|炸|烧|逃|救|判决|起诉|签署|发明|发现|遇难|死亡|幸存|离开|返回|转身|拦|停下|通知|牺牲|辞职|拒|签字)"), 2),
]

NOISE = re.compile(r"(?:我们下期|感谢收听|感谢观看|订阅|点赞|关注|广告|赞助|三连|转发|评论区|一键三连)")


# ---------------------------------------------------------------- 概览

def _share(sents, pattern):
    return sum(1 for s in sents if pattern.search(s)) / max(len(sents), 1)


def profile(segments):
    """客观描述这条稿子的文字长什么样。不下结论，不指方向。

    只报三个比例和一个计数。读完这几行大概知道文字本身够不够用，
    够不够用取决于要拿它干什么——那件事不归这里管。
    """
    sents = [s["text"] for s in sentences_of(segments, min_chars=4)]
    n = len(sents) or 1
    chars = sum(len(s) for s in sents) or 1
    info = sum(len(INFO.findall(s)) for s in sents)
    tools = Counter()
    for s in sents:
        for m in TOOL.finditer(s):
            tools[m.group(0)] += 1
    return {
        "sentences": n,
        "chars": chars,
        "op": round(_share(sents, OP), 3),
        "seq": round(_share(sents, SEQ), 3),
        "nar": round(_share(sents, NAR), 3),
        "info": info,
        "info_per_100": round(info * 100 / chars, 1),
        "tools": tools.most_common(8),
    }


def form_line(p):
    """只报数字，不贴标签——同一个数在不同用法下含义完全不同。"""
    return (f"操作句 {p['op'] * 100:.0f}% ｜ 顺序词 {p['seq'] * 100:.0f}% ｜ "
            f"叙事句 {p['nar'] * 100:.0f}% ｜ 具体信息 {p['info']} 处"
            f"（每百字 {p['info_per_100']}）")


# ---------------------------------------------------------------- 媒体

MEDIA_SKIP = {".part", ".json", ".ytdl", ".wav", ".txt", ".srt", ".md"}


def find_media(directory):
    """任务目录里的原始媒体。original.* 是下载的源，podcast.audio 是播客。"""
    for path in sorted(directory.glob("original.*")):
        if path.suffix.lower() not in MEDIA_SKIP:
            return path
    podcast = directory / "podcast.audio"
    if podcast.is_file():
        return podcast
    return None


# ---------------------------------------------------------------- 事实卡

def score(text):
    hits, total = [], 0
    for name, pattern, weight in RULES:
        if pattern.search(text):
            hits.append(name)
            total += weight
    return total, hits


def build(segments, top=40, min_score=4):
    rows, seen = [], set()
    for item in sentences_of(segments):
        text = item["text"]
        if len(re.sub(r"[^一-鿿A-Za-z0-9]", "", text)) < 8:
            continue
        if NOISE.search(text):
            continue
        key = re.sub(r"\W", "", text)[:24]
        if key in seen:
            continue
        value, hits = score(text)
        if value < min_score:
            continue
        seen.add(key)
        rows.append({"t": item["t"], "text": text, "score": value, "hits": hits})
    rows.sort(key=lambda r: (-r["score"], r["t"]))
    return rows[:top]


def render(job, data, rows):
    strong = [r for r in rows if r["score"] >= 8]
    body = [f"# 事实卡 · {_title(data)}", ""]
    body += _head(data)
    body.append(f"- 强候选（人+年+数，能直接复述）：**{len(strong)}** 条　全部候选：{len(rows)} 条")
    body.append("")
    body.append("| # | 时间 | 内容 | 命中 | 分 |")
    body.append("|---|---|---|---|---|")
    for i, row in enumerate(rows, 1):
        text = row["text"].replace("|", "／")
        body.append(f"| {i} | {stamp(row['t'])} | {text} | {'/'.join(row['hits'])} | {row['score']}")
    body.append("")
    body.append("> 识别稿有错字，人名地名尤其容易错；数字通常比专名可靠。")
    return "\n".join(body)


# ---------------------------------------------------------------- 步骤流

def build_steps(segments):
    """按时间顺序铺开操作。不排序、不去重——顺序本身就是内容。

    只在 8 秒内出现逐字相同的句子时才当识别抖动丢掉。
    只有参数、既没动作又没告诫的句子丢掉，不然「告诫」那节会被描述句填满。
    """
    flow, warns, params_rows = [], [], []
    tools = Counter()
    prev = None
    for item in sentences_of(segments, min_chars=4, fine=True):
        text = item["text"]
        if NOISE.search(text):
            continue
        for m in TOOL.finditer(text):
            tools[m.group(0)] += 1
        found = ["".join(m.group(0).split()) for m in PARAM.finditer(text)]
        is_op, is_warn = bool(OP.search(text)), bool(WARN.search(text))
        is_ui = bool(UI.search(text))
        if not (is_op or is_warn or is_ui or found):
            continue
        if prev and text == prev["text"] and item["t"] - prev["t"] < 8:
            continue
        row = {"t": item["t"], "text": text, "params": found, "warn": is_warn}
        if found:
            params_rows.append(row)
        if is_op or is_ui:
            flow.append(row)
        elif is_warn:
            warns.append(row)
        prev = row
    return {"flow": flow, "warns": warns,
            "tools": tools.most_common(10), "params": params_rows}


def render_steps(job, data, pack):
    flow, warns, tools, params = pack["flow"], pack["warns"], pack["tools"], pack["params"]
    body = [f"# 操作流 · {_title(data)}", ""]
    body += _head(data)
    body.append(f"- 操作 {len(flow)} 条　告诫 {len(warns)} 条　参数 {len(params)} 处"
                + (f"　提到 {len(tools)} 个工具" if tools else ""))
    body.append("")
    if tools:
        body.append("## 提到的工具")
        body.append("　".join(f"`{n}` ×{c}" for n, c in tools))
        body.append("")
    body.append(f"## 按时间顺序（{len(flow)} 条，未合并）")
    body.append("")
    for i, row in enumerate(flow, 1):
        mark = " **⚠**" if row["warn"] else ""
        body.append(f"{i}. `{stamp(row['t'])}`{mark} {row['text']}")
    if warns:
        body.append("")
        body.append("## 不带动作的告诫句")
        body.append("")
        for row in warns:
            body.append(f"- `{stamp(row['t'])}` {row['text']}")
    if len(params) >= 3:
        body.append("")
        body.append("## 带数值的地方")
        body.append("")
        body.append("| 时间 | 值 |")
        body.append("|---|---|")
        for row in params:
            body.append(f"| {stamp(row['t'])} | {' · '.join(row['params'])} |")
    body.append("")
    body.append("> 这是转写稿里的操作句按时间排开，不是原作者的分步。"
                "口播在描述画面时（「点这里」「选这个」），这里只剩半句——"
                "那部分信息在画面里，用 `--frames` 抽出来看。")
    return "\n".join(body)


# ---------------------------------------------------------------- 排版

def stamp(seconds):
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def _title(data, limit=42):
    """标题截断。抖音的 title 字段常常是整段口播稿，不截会把 H1 撑成一屏。"""
    text = re.sub(r"\s+", " ", (data.get("title") or "")).strip()
    if not text:
        return "未命名"
    for sep in ("。", "？", "！", "?", "!"):
        head = text.split(sep)[0]
        if 6 <= len(head) <= limit:
            return head
    return text if len(text) <= limit else text[:limit] + "…"


def _head(data):
    src = data.get("source_url") or data.get("url") or "本地文件"
    return [
        f"- 来源：{src}",
        f"- 标题：{_title(data, 60)}",
        f"- 时长：{stamp(data.get('duration') or 0)}　段数：{len(data.get('segments') or [])}　"
        f"字数：{len(data.get('text') or '')}",
    ]


# ---------------------------------------------------------------- 维护

def recorrect(directory, data):
    """用当前 hotwords.json 重新纠正已有稿子。

    两个坑必须绕开：① 缓存命中时 link_ingest 不会重新 export，老稿子永远带旧错字；
    ② asr_hotwords.apply 见到 corrections 字段就直接返回，补的新词进不去。
    所以这里先丢掉 corrections、从 raw_text 重来，再整份重写。
    """
    import asr_hotwords
    import link_ingest

    base = {k: v for k, v in data.items() if k != "corrections"}
    if base.get("raw_text"):
        base["text"] = base.pop("raw_text")
    fixed = asr_hotwords.apply(base)
    link_ingest.export(directory, fixed, {})
    applied = {item["term"]: item["count"] for item in fixed.get("corrections") or []}
    return json.loads((directory / "transcript.json").read_text(encoding="utf-8")), applied


def locate(target):
    path = Path(target)
    if path.is_dir():
        return path
    candidate = ROOT / "data" / "jobs" / str(target)
    if candidate.is_dir():
        return candidate
    raise SystemExit(f"找不到任务目录：{target}")


def overview(directory, data, prof):
    """转完之后打印这几行。只有事实，没有建议。"""
    media = find_media(directory)
    lines = [f"\n{_title(data)}",
             f"{stamp(data.get('duration') or 0)} ｜ "
             f"{len(data.get('segments') or [])} 段 ｜ {len(data.get('text') or '')} 字"]
    if prof:
        lines.append(form_line(prof))
    lines.append("")
    lines.append(f"全文：{directory / 'transcript.txt'}")
    if media:
        size = media.stat().st_size / 1024 / 1024
        lines.append(f"媒体：{media.resolve()}（{size:.0f} MB）")
    else:
        lines.append("本机没留媒体文件，只有转写稿。")
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description="转写稿 → 文本 / 事实卡 / 步骤流 / 抽帧")
    parser.add_argument("target", help="任务 ID 或 data/jobs/<id> 目录")
    parser.add_argument("--facts", action="store_true", help="生成带时间码的事实卡 facts.md")
    parser.add_argument("--top", type=int, default=40, help="事实卡条数，默认 40")
    parser.add_argument("--steps", action="store_true", help="生成操作流 steps.md")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--recorrect", action="store_true",
                        help="用当前 hotwords.json 重新纠正已有稿子的专名，再重写 transcript")
    args = parser.parse_args(argv)

    directory = locate(args.target)
    source = directory / "transcript.json"
    if not source.is_file():
        raise SystemExit(f"缺少 transcript.json：{source}")
    data = json.loads(source.read_text(encoding="utf-8"))

    if args.recorrect:
        data, applied = recorrect(directory, data)
        if applied:
            print("已重新纠正：" + "、".join(f"{term}×{n}" for term, n in applied.items()),
                  file=sys.stderr)
        else:
            print("本轮没有命中任何变体；检查 data/hotwords.json 里的写法", file=sys.stderr)

    prof = profile(data.get("segments") or [])
    written = []

    rows = build(data.get("segments") or [], args.top) if args.facts else None
    if args.facts:
        (directory / "facts.md").write_text(render(directory.name, data, rows), encoding="utf-8")
        written.append(directory / "facts.md")

    pack = build_steps(data.get("segments") or []) if args.steps else None
    if args.steps:
        (directory / "steps.md").write_text(
            render_steps(directory.name, data, pack), encoding="utf-8")
        written.append(directory / "steps.md")

    if args.json:
        print(json.dumps({"job": directory.name, "dir": str(directory), "profile": prof,
                          "media": str(find_media(directory) or ""),
                          "facts": rows, "steps": pack}, ensure_ascii=False, indent=2))
        return

    print(overview(directory, data, prof))
    if written:
        print("\n已写入：" + "、".join(str(p) for p in written), file=sys.stderr)


if __name__ == "__main__":
    main()
