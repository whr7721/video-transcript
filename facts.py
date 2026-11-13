"""转写稿 → 分类型产出：教程出「步骤单」，案例出「事实卡」，观点出「判定」。

先判类型再决定输出什么，因为这两类稿子的用法完全不同：

- **教程**（怎么点、怎么配、参数多少）→ 我要的是能照着做的流程，不是拿它二创。
  所以按时间顺序铺开操作，标出参数和坑，谁来做由我看完再定。
- **案例**（某年某人干了某事）→ 我要的是可画的事实块，用来洗稿做知识动画。
  所以按"人+年+数+动作"打分，取前 N 条。
- **观点**（金句、鸡汤、方法论）→ 既没物象也没步骤，做动画会退化成会动的海报，先亮明。

只读 transcript.json，不下载、不调用模型、不计配额。

用法：
    python facts.py <job_id|任务目录>                # 自动判类型
    python facts.py <job_id> --type tutorial         # 强制按教程出
    python facts.py <job_id> --all                   # 两种都出
    python facts.py <job_id> --recorrect             # 重跑专名纠正
"""
import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

# ---------------------------------------------------------------- 切句

SPLIT = re.compile(r"(?<=[。！？；\n])")
# 教程口播一个逗号一个动作，粗切会把六件事捏成一句，照着做时没法跟。
# 但不能见逗号就切：切太碎会把「不过要注意，想把字幕导出成文件，要开会员」劈成两条，
# 前半条成了没头没尾的坑、后半条漏进流程。所以只拆超长的。
SPLIT_FINE = re.compile(r"(?<=[。！？；，,\n])")
FINE_MAX = 45


def sentences_of(segments, min_chars=6, fine=False):
    """把 VAD 段切成句，按字符比例估算每句的起始时间。

    min_chars 默认 6 适合事实卡（碎片句没信息）；判类型和抽步骤时传 4，
    因为教程里的操作句本来就短（"点这里"「选第二个」），门槛高了会漏。

    fine=True 时，超过 FINE_MAX 字的句子再按逗号拆一层。短句保持完整，
    长句才拆——这样「坑」不会和它的前提分家。
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

# 教程：手上有动作、眼前有界面、嘴里有参数
OP = re.compile(r"(?:打开|点击|点开|双击|右键|选中|勾选|取消勾选|输入|填上|填入|粘贴|拖到|拖进|"
                r"上传|导入|导出|保存|复制|删除|新建|添加|设置|改为|改成|调成|调到|切换到|选择|挑一|"
                r"注册|登录|安装|下载|重启|刷新|发布|生成|运行|执行|按下|按住|滑动|滚动|"
                r"准备|建一|建个|存进|放进|丢进|交给|发给|告诉|让他|要求|试听|比对|录制|贴上|"
                r"改一遍|过一遍|跑一遍|算一遍|导出来|存下来|拿出来|换掉|去掉|加上|勾上)")
SEQ = re.compile(r"(?:第一步|第二步|第三步|第四步|首先|其次|然后|接着|接下来|下一步|最后一步|"
                 r"现在我们来|我们先把|我们先|再来|再把|在这里|之后呢|最后)")
UI = re.compile(r"(?:按钮|菜单|选项|面板|窗口|界面|工具栏|下拉|弹窗|设置页|标签页|输入框|"
                r"时间轴|轨道|图层|画布|文件夹|路径|官网|后台|控制台|账号|登录态|快捷键)")
# 只要带数值的规格。「参数」「默认值」这种没有值的裸词别进表——列出来等于没列。
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

# 案例：有年份、有数字、有人死了、有东西炸了
YEAR = re.compile(r"(?:1[5-9]\d{2}|20[0-2]\d)\s*年")
NUM = re.compile(r"\d+(?:\.\d+)?\s*(?:万|亿|千|百|米|公里|吨|美元|加元|英镑|欧元|人|名|天|小时|分钟|岁|层)")
NAR = re.compile(r"(?:爆炸|沉没|失窃|倒塌|去世|出生|抢|炸|烧|逃|救|判决|起诉|签署|发明|发现|"
                 r"遇难|死亡|幸存|辞职|拒|签字|营救|追捕|拍卖|赠|夺|拦|投降|破产|上市|失踪|绑架)")
STO = re.compile(r"(?:故事|传说|据说|当年|那一年|曾经|后来|真实发生|历史上|一辈子|临终|回忆)")
QUOTE = re.compile(r"[「“\"][^」”\"]{2,40}[」”\"]")

TITLE_TUT = re.compile(r"(?:教程|保姆|手把手|教你|教学|实战|零基础|入门|步骤|流程|接入|搭建|"
                       r"配置|实测|指南|攻略|从0|从零|怎么(?:做|弄|用|接|配|搭|装|开|玩|搞)|"
                       r"如何(?:做|用|接|配|搭|装|开))")

# 事实卡打分：越靠前越像「可被画出来的事实」
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

KIND_CN = {"tutorial": "教程", "case": "案例", "note": "观点", "unknown": "判不出"}
MIN_SCORE = 0.42          # 低于这个分，两类都不算，归「观点」


# ---------------------------------------------------------------- 分类

def _share(sents, pred):
    return sum(1 for s in sents if pred(s)) / len(sents)


def classify(segments, title=""):
    """靠句子密度判类型。返回连续分 + 命中句数，判错了也能看出为什么。

    两条经验：① 「首先/然后」不能单独当教程证据——观点稿列举论点时满篇都是，
    必须和操作词共现才算步骤；② 标题里的「保姆级/手把手」只是先验，最多加 0.45，
    真正决定的是操作密度，标题党骗不过去。
    """
    sents = [s["text"] for s in sentences_of(segments, min_chars=4)]
    n = len(sents)
    if n < 5:
        return {"kind": "unknown", "tutorial": 0.0, "case": 0.0, "level": "低",
                "signal": {}, "count": n,
                "reason": "句子太少，判不出来；看全文比看分数靠谱"}

    op = _share(sents, lambda s: bool(OP.search(s)))
    seq = _share(sents, lambda s: bool(SEQ.search(s) and OP.search(s)))
    ui = _share(sents, lambda s: bool(UI.search(s) or TOOL.search(s)))
    par = _share(sents, lambda s: bool(PARAM.search(s)))
    warn = _share(sents, lambda s: bool(WARN.search(s)))
    yr = _share(sents, lambda s: bool(YEAR.search(s)))
    num = _share(sents, lambda s: bool(NUM.search(s)))
    nar = _share(sents, lambda s: bool(NAR.search(s)))
    sto = _share(sents, lambda s: bool(STO.search(s)))
    quote = _share(sents, lambda s: bool(QUOTE.search(s)))

    ui_n, par_n, seq_n = round(ui * n), round(par * n), round(seq * n)
    tool_n = len({m.group(0).lower() for s in sents for m in TOOL.finditer(s)})

    bonus = 0.0
    if TITLE_TUT.search(title or ""):
        bonus += 0.30
    if re.search(r"(?:教程|保姆|手把手|教你|实战|从零|从0)", title or ""):
        bonus += 0.15

    tutorial = 3.0 * op + 1.5 * seq + 1.0 * ui + 0.6 * par + 0.6 * warn + bonus
    case = 2.5 * nar + 2.0 * yr + 1.0 * num + 1.5 * sto + 0.2 * quote

    # 光有动作词不够。观点稿里「先去实验」「换掉」「加上」也能凑十几句，
    # 但没界面、没参数、没具名工具——说明他没在操作任何东西，只是在讲道理。
    # 教程至少得摸到其中一样。
    anchors = sum([ui_n >= 3, par_n >= 3, tool_n >= 2, seq_n >= 3])
    if tutorial >= MIN_SCORE and anchors < 1:
        tutorial *= 0.5
    elif anchors >= 2:
        tutorial += 0.15

    if tutorial >= MIN_SCORE and tutorial >= case:
        kind = "tutorial"
    elif case >= MIN_SCORE and case > tutorial:
        kind = "case"
    else:
        kind = "note"

    top = tutorial if kind == "tutorial" else case
    high, mid = (0.9, 0.55) if kind == "tutorial" else (0.75, 0.45)
    level = "高" if top >= high else ("中" if top >= mid else "低")
    if kind == "tutorial" and anchors < 1:
        level = "低"      # 分数够但一样实操锚点都没有，别让人照着做

    return {
        "kind": kind,
        "tutorial": round(tutorial, 2),
        "case": round(case, 2),
        "level": level,
        "count": n,
        "anchor": anchors,
        "signal": {
            "操作句": round(op * n), "步骤句": seq_n, "界面句": ui_n,
            "参数句": par_n, "告诫句": round(warn * n), "工具数": tool_n,
            "年份句": round(yr * n), "数字句": round(num * n),
            "叙事句": round(nar * n), "故事句": round(sto * n),
        },
        "bonus": round(bonus, 2),
    }


# ---------------------------------------------------------------- 事实卡

def score(text):
    hits, total = [], 0
    for name, pattern, weight in RULES:
        if pattern.search(text):
            hits.append(name)
            total += weight
    return total, hits


def build(segments, top=40, min_score=4):
    rows = []
    seen = set()
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


# ---------------------------------------------------------------- 步骤单

def build_steps(segments):
    """按时间顺序铺开操作，不按分数排序——教程的步骤顺序本身就是信息。

    教程不能去重：同一个动作重复三遍（换三个素材各做一次）是真实流程，
    只在 8 秒内出现逐字相同的句子时才当识别抖动丢掉。

    分类只放真心是告诫的句子。只有参数、既没动作又没告诫的句子直接丢，
    不然「坑」那一节会塞满「1秒60帧」这种描述，把真坑埋了。
    """
    flow, warns = [], []
    tools = Counter()
    params_rows = []
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


def _head(data, kind, cls):
    src = data.get("source_url") or data.get("url") or "本地文件"
    forced = "（强制）" if cls.get("kind") and cls["kind"] != kind else ""
    return [
        f"- 类型：**{KIND_CN.get(kind, kind)}**{forced}　教程分 {cls.get('tutorial', 0):.2f} / "
        f"案例分 {cls.get('case', 0):.2f}　置信{cls.get('level', '低')}",
        f"- 来源：{src}",
        f"- 标题：{_title(data, 60)}",
        f"- 时长：{stamp(data.get('duration') or 0)}　段数：{len(data.get('segments') or [])}　"
        f"字数：{len(data.get('text') or '')}",
    ]


def render(job, data, rows, cls=None):
    """事实卡片的 Markdown 表示；grab.py 与命令行共用同一份排版。"""
    strong = [r for r in rows if r["score"] >= 8]
    body = [f"# 事实卡片 · {job}", ""]
    body += _head(data, "case", cls or {})
    body.append(f"- 强候选（人+年+数，可直接开工）：**{len(strong)}** 条　全部候选：{len(rows)} 条")
    body.append("")
    body.append("| # | 时间 | 事实 | 命中 | 分 |")
    body.append("|---|---|---|---|---|")
    for i, row in enumerate(rows, 1):
        text = row["text"].replace("|", "／")
        body.append(f"| {i} | {stamp(row['t'])} | {text} | {'/'.join(row['hits'])} | {row['score']}")
    body.append("")
    body.append("> 识别稿可能有错字，人名地名尤其容易错；上屏前按时间码回听核对。数字通常比专名可靠。")
    return "\n".join(body)


def render_steps(job, data, cls, pack):
    flow, warns, tools, params = pack["flow"], pack["warns"], pack["tools"], pack["params"]
    body = [f"# 操作步骤 · {_title(data)}", ""]
    body += _head(data, "tutorial", cls)
    body.append(f"- 内容量：操作 {len(flow)} 条　坑 {len(warns)} 条　参数 {len(params)} 处"
                + (f"　工具 {len(tools)} 个" if tools else ""))
    body.append("")
    if tools:
        body.append("## 提到的工具")
        body.append("　".join(f"`{n}` ×{c}" for n, c in tools))
        body.append("")
    body.append(f"## 流程（{len(flow)} 条，按时间顺序，未合并）")
    body.append("")
    for i, row in enumerate(flow, 1):
        mark = " **⚠**" if row["warn"] else ""
        body.append(f"{i}. `{stamp(row['t'])}`{mark} {row['text']}")
    if warns:
        body.append("")
        body.append("## 坑和前提（不带动作的告诫句，原文照录）")
        body.append("")
        for row in warns:
            body.append(f"- `{stamp(row['t'])}` {row['text']}")
    if len(params) >= 3:
        body.append("")
        body.append("## 参数速查（照着做时最容易漏的就是这些）")
        body.append("")
        body.append("| 时间 | 值 |")
        body.append("|---|---|")
        for row in params:
            body.append(f"| {stamp(row['t'])} | {' · '.join(row['params'])} |")
    body.append("")
    body.append("> 顺序和时间码来自转写稿，是真的；**步骤边界是我按操作词和顺序词推的**，"
                "不一定等于原作者的分步。要照着做之前，按时间码回看那一段最稳。")
    return "\n".join(body)


def render_note(job, data, cls):
    sig = cls.get("signal") or {}
    body = [f"# 判定：观点稿 · {_title(data)}", ""]
    body += _head(data, "note", cls)
    body.append("")
    if cls.get("kind") == "unknown":
        body.append(f"> {cls.get('reason')}")
    else:
        body.append("没有可画的事实，也没有可照做的步骤。")
        body.append("")
        body.append("这类稿子是论点不是案例——拿去做知识动画，会退化成会动的海报："
                    "每屏只有一句话，没有物象可演。当选题灵感用可以，当素材源不行。")
    if sig:
        body.append("")
        body.append("信号（命中句数 / 共 "
                    f"{cls.get('count', 0)} 句）：" +
                    "　".join(f"{k} {v}" for k, v in sig.items() if v))
    body.append("")
    body.append("## 开头几句，先看看是什么货色")
    body.append("")
    for item in sentences_of(data.get("segments") or [], min_chars=4)[:8]:
        body.append(f"- `{stamp(item['t'])}` {item['text']}")
    return "\n".join(body)


# ---------------------------------------------------------------- 重跑纠正

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


def analyze(data, force="auto"):
    """判类型 + 抽取。grab.py 和命令行共用这个入口。"""
    segments = data.get("segments") or []
    cls = classify(segments, data.get("title") or "")
    kind = cls["kind"] if force == "auto" else force
    if kind == "tutorial":
        return kind, cls, build_steps(segments)
    if kind == "case":
        return kind, cls, build(segments)
    return kind, cls, None


def main(argv=None):
    parser = argparse.ArgumentParser(description="转写稿 → 分类型产出（不调用模型）")
    parser.add_argument("target", help="任务 ID 或 data/jobs/<id> 目录")
    parser.add_argument("--top", type=int, default=40, help="案例：输出多少条事实卡")
    parser.add_argument("--type", dest="force", default="auto",
                        choices=["auto", "tutorial", "case", "note"], help="强制类型，默认自动判")
    parser.add_argument("--all", action="store_true", help="步骤单和事实卡都出，不做二选一")
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

    kind, cls, payload = analyze(data, args.force)

    if args.json:
        print(json.dumps({"job": directory.name, "kind": kind, "classify": cls,
                          "payload": payload}, ensure_ascii=False, indent=2))
        return

    written = []
    if args.all:
        steps = render_steps(directory.name, data, cls, build_steps(data.get("segments") or []))
        (directory / "steps.md").write_text(steps, encoding="utf-8")
        written.append(directory / "steps.md")
        facts = render(directory.name, data, build(data.get("segments") or [], args.top), cls)
        (directory / "facts.md").write_text(facts, encoding="utf-8")
        written.append(directory / "facts.md")
        print(steps)
        print("\n" + "=" * 60 + "\n")
        print(facts)
    elif kind == "tutorial":
        text = render_steps(directory.name, data, cls, payload)
        (directory / "steps.md").write_text(text, encoding="utf-8")
        written.append(directory / "steps.md")
        print(text)
    elif kind == "case":
        text = render(directory.name, data, payload, cls)
        (directory / "facts.md").write_text(text, encoding="utf-8")
        written.append(directory / "facts.md")
        print(text)
    else:
        text = render_note(directory.name, data, cls)
        (directory / "note.md").write_text(text, encoding="utf-8")
        written.append(directory / "note.md")
        print(text)

    print("\n已写入：" + "、".join(str(p) for p in written), file=sys.stderr)


if __name__ == "__main__":
    main()
