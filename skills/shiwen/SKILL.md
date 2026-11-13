---
name: shiwen
description: 用本机拾文把视频、播客链接或本地音视频转成带时间码的文字，并给出原始视频/音频的位置。适用于"转写这个视频""把这段音频变成文字""这期播客讲了什么"。
---

# 拾文（自用版）

只做一件 agent 做不到的事：**把音频变成带时间码的文字**，并告诉你原始文件在哪。

## 入口

```powershell
D:\zcode1\video-transcript\.venv\Scripts\python.exe -X utf8 D:\zcode1\video-transcript\grab.py "<链接或本地文件>"
```

转完打印：

```
AI 配音怎么做，我是怎么做视频的
12:08 ｜ 73 段 ｜ 4075 字
操作句 24% ｜ 顺序词 24% ｜ 叙事句 2% ｜ 具体信息 11 处（每百字 0.3）

全文：...\data\jobs\<id>\transcript.txt
媒体：...\data\jobs\<id>\original.mp4（88 MB）
```

参数：

| 参数 | 用途 |
| --- | --- |
| `--facts` | 顺带出事实卡 `facts.md`：人 / 年份 / 数字 / 引语，按"能被复述"的程度排序，带时间码 |
| `--steps` | 顺带出操作流 `steps.md`：操作句按时间顺序排开，标告诫和带数值的地方 |
| `--top N` | 事实卡条数，默认 40 |
| `--lang zh\|en\|auto` | 语言，默认 auto |
| `--episode N` | RSS / 播客订阅源，指定第几集 |
| `--json` | 只输出 JSON |

已转过、只想要附加产出：

```powershell
... facts.py <job_id> --facts
... facts.py <job_id> --steps
```

## 产出

`data/jobs/<job_id>/` 下：

- `transcript.txt` —— 全文，带段落
- `transcript.srt` —— 时间码字幕
- `transcript.json` —— 分段数据（`segments` 含每段起止时间）
- `audio.wav` —— 抽好的 16k 单声道音频
- `original.mp4` —— 原始视频（有的平台只给音频，那就是 `podcast.audio`）

## 转完之后

读 `transcript.txt`，要什么拿什么。摘要、二创、切片、导图、判断值不值得做，都在这之后。

两种值得留意的情形：

**文字是画外音，实指都在画面上。** 典型是操作类视频——口播说「点这里」「选这个」「拖到这」，主语宾语全在画面里，文字只剩半句。这种稿子读起来会明显发虚：句子多、具体信息少、看完不知道东西长什么样。这时候去看 `original.mp4`，按需要自己抽帧，别拿文字硬凑。

**专名成系统错。** 见下节。数字通常可信，人名地名机构名要核。

## 平台

抖音、小红书、B站、YouTube、TikTok、X、小宇宙、Spotify、RSS、本地音视频。

抖音、小红书依赖本机已有的登录态（`link_ingest.configure(True)` 已开启）。遇到验证码或登录过期，请用户本人完成；MediaCrawler / meme-lab 的配置与定时任务由它们各自维护，改动交回用户。

RSS 未指定 `--episode` 时只列出节目，等用户选定再处理。

## 误差边界

实测（33 分钟播客，56 秒转完，36 倍实时，零费用）：

| 类型 | 表现 |
| --- | --- |
| 数字、年份、金额 | **几乎全对**，可直接引用 |
| 人名、地名、机构名 | **成系统错**：`Halifax → halifalifax`、`Nova Scotia → novava scotia / nobo Sc`、`加元 → 家元` |

所以：

1. **数字可以信，专名必须核**。任何要上屏或进正文的人名地名，先按时间码回听或另查一次。
2. 事实卡里的专名当成"读音线索"，不当成写法。
3. 修过的变异补进 `data/hotwords.json`（键是正确写法，值是识别变体），下一条新转写自动生效。前提：变体规范化后 ≥4 字符；不要把变体映射到更宽的概念（`Boston: ["commonmon"]` 会把 `boston commonmon` 改成 `boston Boston`）。
4. **已经转过的稿子不会自动修正**：缓存命中时管线跳过重写，且 `asr_hotwords.apply` 见到 `corrections` 字段就直接返回。补完词表要显式跑一次：

   ```powershell
   ... facts.py <job_id> --recorrect
   ```

   它会从 `raw_text` 重新纠正并重写 `transcript.json` / `transcript.txt` / `transcript.srt`，命中的词和次数打到 stderr。没有命中说明词表写法有问题。
5. `data/hotwords.json` 被 gitignore，是唯一会累积增值的资产，换机器要手动带走。
