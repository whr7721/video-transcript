# 自用层（self-use）

这个仓库有两副面孔，别混用。

| | 用途 | 在哪 |
|---|---|---|
| **完整产品** | 简历项目、接单演示、功能展示 | tag `v1.0-portfolio` 或分支 `archive/full-product`。工作区里已删除，`git worktree add ../shiwen-full v1.0-portfolio` 取出整份 |
| **自用层** | 我做视频时真的会敲的两条命令 | `grab.py` + `facts.py`，就在根目录 |

自用层**不启动服务、不碰前端、不调用模型、不计配额**，也不依赖 `data/` 以外的任何状态。

---

## 一条命令

```powershell
.\.venv\Scripts\python.exe -X utf8 grab.py "https://www.xiaoyuzhoufm.com/episode/xxxx"
```

跑完得到：

```
Ep. 1 一场爆炸带来的价值24万的圣诞树：波士顿官方圣诞树的故事
33:43 ｜ 10485 字 ｜ 强候选 12 条 / 共 40 条 ｜ data/jobs/3f2bc4eb027b02fc

★ 1 06:21  第一棵树是在 1918 年 12 月，由 Halifax 赠送给波士顿……
★ 5 23:26  爆炸一共造成了 1600 人死亡，9000 多人受伤

全文：data/jobs/<id>/transcript.txt
事实表：data/jobs/<id>/facts.md
```

支持平台：抖音 / 小红书 / B站 / YouTube / TikTok / X / 小宇宙 / Spotify / RSS / 本地文件。
转写本机完成（SenseVoice INT8，约 30 倍实时，零费用）；事实抽取是纯正则，不计配额。

常用参数：`--top 60`（多给点候选）、`--lang en`（英文内容）、`--episode 3`（RSS 选集）、`--json`（给脚本吃）。

只想对已有任务重跑事实表，不用重新下载：

```powershell
.\.venv\Scripts\python.exe -X utf8 facts.py <任务ID> --top 40
```

---

## 刻意不做的事

摘要、精华、金句、二创改写、导图、章节导读、切片 —— **这些以前固化在 `rewrite.py` / `clips.py` / `summary` 里（现已从工作区移除），现在全部交给 agent。**

理由：固化是为了服务"没用过 AI 的人"，自用没必要。每多一个固定环节，就多一处要维护、多一处跟不上模型能力。**工具只负责把不可替代的那步做掉，剩下的让 agent 现场判断。**

不可替代的是哪一步：**音频 → 带时间码的文本。** agent 没有耳朵，它做不了这一步；剩下的它比你我都做得好。

---

## 为什么不开第二个仓库

考虑过，结论是不开。三个理由：

1. **第二个仓库要重建一套环境**：venv、414 MB 模型、ffmpeg/Deno、MediaCrawler 路径与登录态。这些是成本，不是资产。
2. **会拆成两个半成品**：简历版缺"真实使用痕迹"，自用版缺"完整工程"。合在一起才是一个完整故事——**我做了一个产品，然后为自用把它砍到只剩脊梁骨**。这个叙事本身就是简历里最值钱的一段。
3. **一个仓库两个入口就够**：tag 封存 + 根目录两个文件，不需要第二份 git 历史。

真需要单独发一个"作品集版"时，从 tag 开一个新的空仓库，一条命令就够，不用提前分家：

```bash
git worktree add ../shiwen-portfolio v1.0-portfolio
```

---

## 事实卡的误差边界

这不是可信文本，是**有骨架的草稿**：

- **数字、年份、金额通常是对的** —— 也是 agent 补不出来的
- **专有名词成系统错** —— `Nova Scotia` → `novava scotia` / `nobo Sc`；`加元` → `家元`
- 所以：**上屏前按时间码回听核对**，尤其人名、地名、机构名

修一次专名，永久受益：把该片里的变异补进 `data/hotwords.json`（键是规范写法，值是识别变体），下一条转写就生效。`asr_hotwords.py` 已经实现了这层后处理，只是表里词太少。

**已经转过的稿子不会自己变。** 两个原因叠在一起：缓存命中时 `link_ingest.add` 直接 return，不走 `export`；而 `asr_hotwords.apply` 开头有 `if 'corrections' in result: return result`，补的新词进不去。所以补完词表要显式跑一次：

```powershell
.\.venv\Scripts\python.exe -X utf8 facts.py <job_id> --recorrect
```

它丢弃 `corrections`、从 `raw_text` 重新纠正，再整份重写 `transcript.json` / `.txt` / `.srt`，并把命中的词和次数打到 stderr。**没有命中就说明词表写法有问题**，别当成已经修好。

**三个踩过的坑，写在这里省得再踩：**

1. **变体规范化后不足 4 字符会被静默跳过。** `保森`（2 字）、`波尔顿`（3 字）写进去也不会生效。要么写成更长的片段（`保森 commonmon`），要么承认它只能人工改。
2. **别把变体映射到比它宽的概念。** 我一开始写 `Boston: ["commonmon"]`，结果 `boston commonmon` 被替换成 `boston Boston`。正确做法是把整段写成变体：`Boston Common: ["boston commonmon"]`。
3. **每加一条都要在真实稿上验一次。** 替换是全文级的，写错一次会污染所有后续转写，而且不会报错。

实测效果（这集 33 分钟）：补表前专名错 30 多处，补表后 `Halifax ×15`、`Nova Scotia ×12`、`Boston Common ×4`、`Coleman ×1` 全部归位，正文可读性从"要猜"变成"能直接引用"。

同音词不要进表：`加元 → 家元 / 家园` 这类替换会误伤正常词，交给 agent 按上下文判断。

---

## 代码

| 文件 | 行数 | 做什么 |
|---|---|---|
| `grab.py` | ~80 | 链接 → 转写 → 事实卡，一条命令 |
| `facts.py` | ~180 | 转写稿 → 带时间码的事实卡；`--recorrect` 重跑专名纠正 |

两者只读调用现有模块（`link_ingest` / `transcribe` / `store`），**不修改任何原有代码**。删掉这两个文件，产品版不受任何影响。

---

## 给 agent 的 Skill

`skills/shiwen/SKILL.md` 已同步改成自用版（`dsh-plugin/skills/shiwen/` 是同一份的分发副本）：

- 只讲一条命令 `grab.py` 和产出文件在哪
- 明确列出**不该调用**的：`summarize` / `clips` / `rewrite` / `app.py` / 前端 / 云端 ASR
- 写清误差边界：数字可信、专名必核，以及 `--recorrect` 这一步
- 默认动作从「转写 → 调摘要接口」改成「转写 → 读全文 → agent 自己判断」

原来的 skill 是给"不接 AI 的用户"写的，教 agent 去调工具里固化的加工链；自用场景下那条链正是要被绕过的部分。
