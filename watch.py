"""页面监控：抓一次，和上次比，只报变动。

scrape.py 是「抓一次」，watch.py 是「抓一次 + 比一次」。分开是因为抓取方式会变
（选择器会失效、有人想换接口），而比对逻辑不变。

    python watch.py add 显卡价格 "https://..." --selector "span.price"
    python watch.py add 公告 "https://..." --ignore "更新于.*"
    python watch.py run                      # 全部跑一遍，只报变了的
    python watch.py run 显卡价格
    python watch.py list
    python watch.py show 显卡价格             # 历史变化记录
    python watch.py rm 显卡价格

第一次运行只建基线，不报变化——否则每个新监控项第一次都会「全都变了」。

三种取法，前两种是逐条比对，能看见「哪一条进了、哪一条出了」：

    --selector "..."     元素文本（--attr 取属性）
    --js "表达式"        表达式返回字符串数组，最灵活，能自己挑字段
    都不给               整页文字按行比对（公告、政策、说明页）

两种抗噪手段，这是这类活成不成的关键：

    --strip "正则"       把行内匹配的片段删掉再比（播放量、访问数这类会动的数字）
    --ignore "正则"      整行剔除（时间戳行、广告行）
    --only "正则"        只留匹配的行

选择器失效是主要故障：页面改版后抓回 0 条。这时候绝不能当「全部消失」，
所以抓到 0 条不算变化，只报错。
"""
import argparse
import json
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STORE = ROOT / "data" / "watch"
PY = sys.executable
KEEP = 20          # 每个监控项保留最近 20 份快照


# ---------------------------------------------------------------- 存储

def slug(name):
    """名字直接当目录名。Windows 支持中文，只挡掉路径非法字符。"""
    bad = '\\/:*?"<>|'
    return "".join("_" if c in bad else c for c in name).strip() or "item"


def folder(name):
    return STORE / slug(name)


def load(name, filename, default=None):
    p = folder(name) / filename
    if not p.is_file():
        return default
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return default


def save(name, filename, data):
    p = folder(name) / filename
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def load_all():
    if not STORE.is_dir():
        return []
    out = []
    for d in sorted(STORE.iterdir()):
        p = d / "config.json"
        if p.is_file():
            try:
                out.append(json.loads(p.read_text(encoding="utf-8")))
            except Exception:
                pass
    return out


def find(name):
    for cfg in load_all():
        if cfg["name"] == name or slug(cfg["name"]) == slug(name):
            return cfg
    return None


# ---------------------------------------------------------------- 抓取

def fetch(cfg):
    """调 scrape.py 抓一次，返回 (数据, 是否列表, 标题)。

    走子进程而不是 import：scrape.py 是给人用的入口，把结果写到 --out，
    这里只是多一个消费者。两边互不依赖，改哪边都不打断另一边。
    """
    tmp = folder(cfg["name"]) / "_fetch.json"
    cmd = [PY, "-X", "utf8", str(ROOT / "scrape.py"), cfg["url"],
           "--wait", str(cfg.get("wait") or 6),
           "--scroll", str(cfg.get("scroll") or 0),
           "--json", "--out", str(tmp)]
    if cfg.get("mode") == "selector":
        cmd += ["--selector", cfg["selector"]]
        if cfg.get("attr"):
            cmd += ["--attr", cfg["attr"]]
    elif cfg.get("mode") == "js":
        cmd += ["--js", cfg["js"]]
    elif cfg.get("fast"):                 # 整页文字 + 静态站，可以不开浏览器
        cmd += ["--fast"]
    if cfg.get("profile"):
        cmd += ["--profile", cfg["profile"]]

    proc = subprocess.run(cmd, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    if not tmp.is_file():
        raise RuntimeError((proc.stderr or proc.stdout or "抓取无输出").strip()[-400:])
    envelope = json.loads(tmp.read_text(encoding="utf-8"))
    tmp.unlink(missing_ok=True)
    return envelope.get("data"), isinstance(envelope.get("data"), list), envelope.get("title") or ""


# ---------------------------------------------------------------- 规范化
# 抗噪全在这一层：抓回来的东西先洗一遍再比。洗得干净，diff 才有信噪比。

def norm(text):
    return re.sub(r"\s+", " ", (text or "").strip())


def wash(raw_items, cfg):
    out, seen = [], set()
    strips = cfg.get("strip") or []
    ignores = cfg.get("ignore") or []
    only = cfg.get("only")

    for item in raw_items:
        s = item if isinstance(item, str) else json.dumps(item, ensure_ascii=False, sort_keys=True)
        s = norm(s)
        if not s:
            continue
        for pat in strips:                 # 先把会动的片段抹掉（播放量、时间、计数
            s = re.sub(pat, "", s)
        s = norm(s)
        if not s:
            continue
        if any(re.search(p, s) for p in ignores):
            continue
        if only and not re.search(only, s):
            continue
        if s in seen:                      # 推荐位重复同一句，只留一次
            continue
        seen.add(s)
        out.append(s)
    return out


def lines_of(text):
    return [ln for ln in (text or "").splitlines() if ln.strip()]


# ---------------------------------------------------------------- 比对

def diff_list(old, new):
    """集合比较 + 位次比较。

    有新增或消失时不报位次：插入一条后面全部位移 1，报了全是噪音。
    只有两边集合完全一致、顺序变了，才是真的「重排」。
    """
    os_, ns_ = set(old), set(new)
    added = [s for s in new if s not in os_]
    removed = [s for s in old if s not in ns_]
    moved = []
    if not added and not removed:
        pos = {s: i for i, s in enumerate(old)}
        moved = [(s, pos[s], i) for i, s in enumerate(new) if pos[s] != i]
    return {"added": added, "removed": removed, "moved": moved}


def diff_text(old, new, context=1):
    """整页文字按行比。只报变化块和它前一行——看的人只想知道「哪里变了」。"""
    import difflib

    old, new = lines_of(old), lines_of(new)
    blocks = []
    matcher = difflib.SequenceMatcher(None, old, new, autojunk=False)
    for group in matcher.get_grouped_opcodes(context):
        head = old[group[0][1]:group[0][2]]
        rows = []
        for tag, i1, i2, j1, j2 in group:
            if tag == "equal":
                continue
            rows += [("-", ln) for ln in old[i1:i2]]
            rows += [("+", ln) for ln in new[j1:j2]]
        if rows:
            blocks.append({"at": head[-1] if head else "", "rows": rows[:40]})
    return blocks


# ---------------------------------------------------------------- 命令

def cmd_add(args):
    if find(args.name):
        raise SystemExit(f"「{args.name}」已经存在。换个名字，或先 watch.py rm {args.name}")

    mode = "selector" if args.selector else ("js" if args.js else "text")
    fast = bool(getattr(args, "fast", False)) and mode == "text"
    if getattr(args, "fast", False) and mode != "text":
        print("提示：--fast 只对整页文字生效，给 --selector / --js 时忽略", file=sys.stderr)
    cfg = {
        "name": args.name, "url": args.url, "mode": mode,
        "selector": args.selector, "attr": args.attr, "js": args.js, "fast": fast,
        "strip": args.strip or [], "ignore": args.ignore or [], "only": args.only,
        "scroll": args.scroll, "wait": args.wait, "profile": args.profile,
        "created": time.time(), "last_run": None, "runs": 0,
    }
    folder(args.name).mkdir(parents=True, exist_ok=True)

    print(f"抓第一次，建基线：{args.name}", file=sys.stderr)
    try:
        data, is_list, title = fetch(cfg)
    except Exception:
        _discard(args.name)          # 抓取就失败，别留个空目录让 list 看着有东西
        raise
    items = wash(data if is_list else lines_of(data), cfg)

    if not items:
        # 抓到 0 条有两种可能：页面确实空，或选择器失效。后者远更常见。
        # 存成基线的话，下一次就会报「全部新增」，从此这个项就废了。
        _discard(args.name)
        raise SystemExit(
            f"抓到 0 条，没建基线。\n"
            f"  页面标题：{title or '（空）'}\n"
            f"  看这页到底有什么：scrape.py \"{cfg['url']}\" --js \"document.body.innerText.slice(0,300)\"\n"
            f"  或者换选择器：scrape.py \"{cfg['url']}\" --selector \"a\" | head\n"
            f"  选择器失效是这类活最常见的故障，别急着存基线。")

    cfg.update(last_run=time.time(), runs=1)
    save(args.name, "config.json", cfg)
    save(args.name, "state.json", {"at": time.time(), "title": title, "items": items})

    kind = {"selector": f"逐条（{args.selector}）", "js": "逐条（js 表达式）",
            "text": "整页文字按行"}[mode]
    if fast:
        kind += "，不开浏览器"
    print(f"已建基线：{args.name}")
    print(f"  标题：{title or '（无）'}")
    print(f"  粒度：{kind}")
    print(f"  抓到：{len(items)} 条")
    for s in items[:5]:
        print(f"    {s[:78]}")
    if len(items) > 5:
        print(f"    …还有 {len(items) - 5} 条")
    print("\n下次 watch.py run 只报变化。")


def cmd_run(args):
    if args.name:
        cfg = find(args.name)
        if not cfg:
            raise SystemExit(f"没有「{args.name}」。watch.py list 看有哪些。")
        targets = [cfg]
    else:
        targets = load_all()
        if not targets:
            raise SystemExit("还没有监控项。watch.py add <名字> <url> --selector \"...\"")

    changed = failed = 0
    for cfg in targets:
        name = cfg["name"]
        try:
            data, is_list, title = fetch(cfg)
        except Exception as exc:
            print(f"{name}　抓取失败：{exc}")
            failed += 1
            continue

        items = wash(data if is_list else lines_of(data), cfg)
        if not items:
            print(f"{name}　抓到 0 条，跳过比对（选择器可能失效）")
            failed += 1
            continue

        old = (load(name, "state.json", {}) or {}).get("items") or []
        is_text = cfg["mode"] == "text"
        d = diff_text("\n".join(old), "\n".join(items)) if is_text else diff_list(old, items)
        has = bool(d) if is_text else bool(d["added"] or d["removed"] or d["moved"])

        stamp = datetime.now().strftime("%m-%d %H:%M")
        if not has:
            print(f"{name}　{stamp}　无变化（{len(items)} 条）")
        else:
            changed += 1
            print(f"{name}　{stamp}")
            if is_text:
                for blk in d[:6]:
                    print(f"  @@ 附近：{blk['at'][:60]}")
                    for sign, ln in blk["rows"]:
                        print(f"     {sign} {ln[:74]}")
                if len(d) > 6:
                    print(f"  …还有 {len(d) - 6} 处")
            else:
                for label, key in (("+ 新增", "added"), ("- 消失", "removed")):
                    for s in d[key][:10]:
                        print(f"  {label}  {s[:76]}")
                    if len(d[key]) > 10:
                        print(f"  {label}  …还有 {len(d[key]) - 10} 条")
                for s, a, b in d["moved"][:8]:
                    print(f"  ~ 位次  {s[:58]}  {a + 1} → {b + 1}")
                if d["moved"]:
                    print(f"  （{len(d['moved'])} 条重排，集合没变）")

            save(name, f"snapshots/{datetime.now().strftime('%Y%m%d-%H%M%S')}.json",
                 {"at": time.time(), "items": items})
            _trim(name)
            _log(name, d, len(items))

        cfg.update(last_run=time.time(), runs=(cfg.get("runs") or 0) + 1)
        save(name, "config.json", cfg)
        save(name, "state.json", {"at": time.time(), "title": title, "items": items})

    if len(targets) > 1:
        tail = f"{len(targets)} 个监控项，{changed} 个有动静"
        print(f"\n{tail}，{failed} 个没跑成。" if failed else f"\n{tail}。")


def _log(name, d, total):
    if isinstance(d, list):
        summary = f"{len(d)} 处"
    else:
        parts = [f"+{len(d['added'])}" if d["added"] else "",
                 f"-{len(d['removed'])}" if d["removed"] else "",
                 f"~{len(d['moved'])}" if d["moved"] else ""]
        summary = " ".join(p for p in parts if p)
    entry = {"at": time.time(), "summary": summary or "变化", "total": total}
    p = folder(name) / "log.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _trim(name):
    snaps = sorted((folder(name) / "snapshots").glob("*.json"))
    for p in snaps[:-KEEP]:
        p.unlink(missing_ok=True)


def _discard(name):
    """建基线失败时把半成品目录清掉，免得 list 里留个空壳。"""
    import shutil
    shutil.rmtree(folder(name), ignore_errors=True)


def cmd_list(args):
    rows = load_all()
    if not rows:
        print("还没有监控项。watch.py add <名字> <url> --selector \"...\"")
        return
    for cfg in rows:
        state = load(cfg["name"], "state.json", {}) or {}
        last = datetime.fromtimestamp(cfg["last_run"]).strftime("%m-%d %H:%M") if cfg.get("last_run") else "未跑"
        print(f"{cfg['name']}　{cfg['mode']}　{len(state.get('items') or [])} 条　跑了 {cfg.get('runs') or 0} 次　{last}")
        print(f"    {cfg['url']}")
        if cfg.get("strip"):
            print(f"    抹掉：{' | '.join(cfg['strip'])}")
        if cfg.get("ignore"):
            print(f"    忽略：{' | '.join(cfg['ignore'])}")
        if cfg.get("only"):
            print(f"    只看：{cfg['only']}")


def cmd_show(args):
    cfg = find(args.name)
    if not cfg:
        raise SystemExit(f"没有「{args.name}」")
    state = load(cfg["name"], "state.json", {}) or {}
    print(f"{cfg['name']}　{cfg['url']}")
    print(f"  当前 {len(state.get('items') or [])} 条，共跑了 {cfg.get('runs') or 0} 次\n")
    log = folder(cfg["name"]) / "log.jsonl"
    if not log.is_file():
        print("还没有变化记录。")
        return
    rows = [json.loads(l) for l in log.read_text(encoding="utf-8").splitlines() if l.strip()]
    for r in rows[-15:]:
        t = datetime.fromtimestamp(r["at"]).strftime("%m-%d %H:%M")
        print(f"  {t}　{r['summary']}　共 {r['total']} 条")
    print(f"\n快照：{folder(cfg['name']) / 'snapshots'}")


def cmd_rm(args):
    cfg = find(args.name)
    if not cfg:
        raise SystemExit(f"没有「{args.name}」")
    import shutil
    shutil.rmtree(folder(cfg["name"]), ignore_errors=True)
    print(f"已删除 {cfg['name']}")


def main(argv=None):
    ap = argparse.ArgumentParser(description="页面监控：抓一次，和上次比，只报变动")
    sub = ap.add_subparsers(dest="cmd")

    p = sub.add_parser("add", help="新建监控项，并立即抓一次建基线")
    p.add_argument("name", help="名字，中文也行")
    p.add_argument("url")
    p.add_argument("--selector", help="CSS 选择器，逐条比对")
    p.add_argument("--attr", help="配合 --selector，取属性")
    p.add_argument("--js", help="表达式返回字符串数组，逐条比对")
    p.add_argument("--fast", action="store_true",
                   help="不开浏览器直接拿正文，只对静态站有效（政府公告/新闻/博客），跑得快十倍")
    p.add_argument("--strip", action="append", metavar="正则", help="抹掉行内会动的片段，可多次")
    p.add_argument("--ignore", action="append", metavar="正则", help="整行剔除，可多次")
    p.add_argument("--only", metavar="正则", help="只保留匹配的行")
    p.add_argument("--scroll", type=int, default=0)
    p.add_argument("--wait", type=float, default=6)
    p.add_argument("--profile")
    p.set_defaults(func=cmd_add)

    p = sub.add_parser("run", help="跑一遍，只报变化")
    p.add_argument("name", nargs="?")
    p.set_defaults(func=cmd_run)

    p = sub.add_parser("list", help="看监控了什么")
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("show", help="看某个项的历史变化")
    p.add_argument("name")
    p.set_defaults(func=cmd_show)

    p = sub.add_parser("rm", help="删掉")
    p.add_argument("name")
    p.set_defaults(func=cmd_rm)

    args = ap.parse_args(argv)
    if not getattr(args, "func", None):
        args = ap.parse_args(["run", *(argv or [])])
    args.func(args)


if __name__ == "__main__":
    main()
