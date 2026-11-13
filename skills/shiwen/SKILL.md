---
name: shiwen
description: 用本机拾文把视频、播客链接或本地音视频转成带时间码的文字和事实卡片，供后续选题、核对与创作。适用于"转写这个视频""这期播客有哪些能用的案例""把这个音频变成文字"。不做摘要、二创、切片、导图——这些由 agent 直接读原文完成。
---

# 拾文（自用版）

只做一件 agent 自己做不到的事：**把音频变成带时间码的文字**。

其余所有加工——摘要、金句、二创、切片、导图、选题判断——都交给 agent 读 `transcript.txt` 后直接完成。工具里固化的那些环节是给"不接 AI 的用户"准备的，自用场景不再调用。

## 入口

一条命令，从链接直到事实卡：

```powershell
D:\zcode1\video-transcript\.venv\Scripts\python.exe -X utf8 D:\zcode1\video-transcript\grab.py "<链接或本地文件>"
```

常用参数：

| 参数 | 用途 |
| --- | --- |
| `--top N` | 输出前 N 条事实卡，默认 40 |
| `--lang zh\|en\|auto` | 语言，默认 auto |
| `--episode N` | RSS / 播客订阅源，指定第几集 |
| `--json` | 只输出 JSON（`job` / `dir` / `title` / `count` / `facts`） |

拾文装在别处时用环境变量 `SHIWEN_HOME` 指定根目录，或直接替换上面的路径。入口不存在就说清缺什么，不要自行下载工具或代替用户登录。

已转过、只想重出事实卡（不重新下载转写）：

```powershell
D:\zcode1\video-transcript\.venv\Scripts\python.exe -X utf8 D:\zcode1\video-transcript\facts.py <job_id> --top 25
```

## 产出

跑完后在 `data/jobs/<job_id>/` 下：

- `transcript.txt` —— 全文，带段落
- `transcript.srt` —— 时间码字幕
- `transcript.json` —— 分段数据（`segments` 含每段起止时间）
- `facts.md` —— 事实卡片表，按"人 / 年份 / 数字 / 引语 / 专名 / 机构 / 动作"打分排序

只要文字时直接读 `transcript.txt`；需要按时间定位就查 `facts.md` 或 `transcript.srt`。

## 平台

抖音、小红书、B站、YouTube、TikTok、X、小宇宙、Spotify、RSS、本地音视频。

抖音、小红书依赖本机已有的登录态（`link_ingest.configure(True)` 已开启）。遇到验证码或登录过期，请用户本人完成，不绕过验证，不修改外部 MediaCrawler / meme-lab 的配置。

RSS 未指定 `--episode` 时只列出节目，不要默认处理整个订阅源。

## 误差边界——这条必须遵守

实测结论（33 分钟播客，56 秒转完，36 倍实时，零费用）：

| 类型 | 表现 |
| --- | --- |
| 数字、年份、金额 | **几乎全对**，可直接引用 |
| 人名、地名、机构名 | **成系统错**：`Halifax → halifalifax`、`Nova Scotia → novava scotia / nobo Sc / nvakoa`、`加元 → 家元` |

所以：

1. **数字可以信，专名必须核**。任何要上屏或进正文的人名地名，先按时间码回听或另查一次。
2. 事实卡里的专名当成"读音线索"，不当成写法。
3. 修过的变异补进 `data/hotwords.json`（键是正确写法，值是识别变体），下一条新转写自动生效。生效前提：变体规范化后 ≥4 字符；不要把变体映射到更宽的概念（`Boston: ["commonmon"]` 会把 `boston commonmon` 改成 `boston Boston`）。
4. **已经转过的稿子不会自动修正**：缓存命中时管线跳过重写，且 `asr_hotwords.apply` 见到 `corrections` 字段就直接返回。补完词表要显式跑一次：

   ```powershell
   D:\zcode1\video-transcript\.venv\Scripts\python.exe -X utf8 D:\zcode1\video-transcript\facts.py <job_id> --recorrect
   ```

   它会从 `raw_text` 重新纠正并重写 `transcript.json` / `transcript.txt` / `transcript.srt`，然后把命中的词和次数打到 stderr。没有命中就说明词表写法有问题，不要当成已经修好。
5. `data/hotwords.json` 被 gitignore，是唯一会累积增值的资产，换机器要手动带走。

## 明确不做

| 别调 | 原因 |
| --- | --- |
| `shiwen summarize` / `clips` / `rewrite` | 产品层功能，会调模型、计配额，且产出不如 agent 直接读原文 |
| `app.py` / `studio_api.py` / 前端 | 工作台形态，自用不需要，已封存在 tag `v1.0-portfolio` |
| 云端 ASR | 本地 SenseVoice 已够快够准且免费、离线、内容不出本机 |
| 批量重试或换付费服务 | 失败先如实说明原因，按用户授权再动 |

用户的真实需求通常不是"给我一份摘要"，而是"这里有什么能用的"。所以默认动作是：**转写 → 读全文 → 自己判断**，而不是转写 → 调摘要接口。
