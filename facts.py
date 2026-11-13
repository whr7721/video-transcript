"""从已有转写稿抽取「事实卡片」：人 + 年份 + 数字 + 可画场景。

只读 transcript.json，不下载、不调用模型、不计配额。目的：把 30k 字全文压成
20~40 条能直接开工的分镜素材，每条带时间码，方便回听核对。

用法：
    python facts.py <job_id|任务目录> [--top 40] [--json] [--recorrect]
"""
import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

# 权重：越靠前越像「可被画出来的事实」
RULES = [
    ("年份", re.compile(r"(?:1[5-9]\d{2}|20[0-2]\d)\s*年?"), 4),
    ("数字", re.compile(r"\d+(?:\.\d+)?\s*(?:万|亿|千|百|米|公里|千米|吨|美元|加元|英镑|欧元|人|名|天|年|小时|分钟|秒|%|倍|层|岁)"), 3),
    ("引语", re.compile(r"[「“\"][^」”\"]{2,40}[」”\"]"), 3),
    ("专名", re.compile(r"[A-Za-z][A-Za-z'.\- ]{2,30}"), 2),
    ("机构", re.compile(r"(?:大学|学院|银行|公司|集团|博物馆|美术馆|图书馆|研究所|法院|议会|政府|省政府|市政府|军队|海军|陆军|医院|教堂|基金会|协会|电视台|时报|邮报|日报)"), 2),
    ("地名", re.compile(r"(?:州|省|郡|市|镇|村|岛|港|湾|河|山|广场|公园|大道|街)"), 1),
    ("转折", re.compile(r"(?:但是|但|其实|结果|直到|后来|最后|没想到|反而|然而|可是|偏偏|竟然)"), 1),
    ("动作", re.compile(r"(?:发生|爆炸|沉没|失窃|倒塌|去世|出生|抢|炸|烧|逃|救|判决|起诉|签署|发明|发现|遇难|死亡|幸存|离开|返回|转身|拦|停下|通知|牺牲|辞职|拒|签字)"), 2),
]

SPLIT = re.compile(r"(?<=[。！？；])")


def sentences_of(segments):
    """把 VAD 段切成句，按字符比例估算每句的起始时间。"""
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
            piece = piece.strip()
            if len(piece) < 6:
                cursor += len(piece)
                continue
            at = start + span * (cursor / total)
            out.append({"t": round(at, 1), "text": piece})
            cursor += len(piece)
    return out


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
        # 去掉纯寒暄、纯语气
        if len(re.sub(r"[^一-鿿A-Za-z0-9]", "", text)) < 8:
            continue
        if re.search(r"(?:我们下期|感谢收听|订阅|点赞|关注|广告|赞助)", text):
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


def stamp(seconds):
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def render(job, data, rows):
    """事实卡片的 Markdown 表示；grab.py 与命令行共用同一份排版。"""
    strong = [r for r in rows if r["score"] >= 8]
    body = [f"# 事实卡片 · {job}", ""]
    body.append(f"- 来源：{data.get('source_url') or data.get('url') or '本地文件'}")
    body.append(f"- 标题：{data.get('title') or '未命名'}")
    body.append(f"- 时长：{stamp(data.get('duration') or 0)}　段数：{len(data.get('segments') or [])}　字数：{len(data.get('text') or '')}")
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


def main(argv=None):
    parser = argparse.ArgumentParser(description="转写稿 → 事实卡片（不调用模型）")
    parser.add_argument("target", help="任务 ID 或 data/jobs/<id> 目录")
    parser.add_argument("--top", type=int, default=40)
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

    rows = build(data.get("segments") or [], args.top)

    if args.json:
        print(json.dumps({"job": directory.name, "count": len(rows), "facts": rows},
                         ensure_ascii=False, indent=2))
        return

    markdown = render(directory.name, data, rows)
    out = directory / "facts.md"
    out.write_text(markdown, encoding="utf-8")
    print(markdown)
    print(f"\n已写入：{out}", file=sys.stderr)


if __name__ == "__main__":
    main()
