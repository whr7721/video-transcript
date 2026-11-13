---
name: shiwen
description: 用本机拾文把视频、播客链接或本地音视频转成带时间码的文字，并按内容类型分别产出：教程给操作步骤单，案例给事实卡片，观点给判定。适用于"转写这个视频""这个教程讲了几步""这期播客有哪些能用的案例""把这个音频变成文字"。
---

# 拾文（自用版）

只做一件 agent 自己做不到的事：**把音频变成带时间码的文字**。

转完之后的事——摘要、金句、二创、切片、导图、选题判断——由你直接读产物完成。
判断这条值不值得做、该洗稿还是该照做，也是你的活。

## 入口

一条命令，从链接直到分类型产出：

```powershell
D:\zcode1\video-transcript\.venv\Scripts\python.exe -X utf8 D:\zcode1\video-transcript\grab.py "<链接或本地文件>"
```

常用参数：

| 参数 | 用途 |
| --- | --- |
| `--top N` | 案例型：输出前 N 条事实卡，默认 40 |
| `--type tutorial\|case\|note` | 强制类型，默认 `auto` 按内容判 |
| `--lang zh\|en\|auto` | 语言，默认 auto |
| `--episode N` | RSS / 播客订阅源，指定第几集 |
| `--json` | 只输出 JSON（`job` / `dir` / `kind` / `classify` / `payload`） |

拾文装在别处时用环境变量 `SHIWEN_HOME` 指定根目录，或直接替换上面的路径。

已转过、只想重出产出（不重新下载转写）：

```powershell
D:\zcode1\video-transcript\.venv\Scripts\python.exe -X utf8 D:\zcode1\video-transcript\facts.py <job_id> --top 25
```

## 产出

跑完后在 `data/jobs/<job_id>/` 下：

- `transcript.txt` —— 全文，带段落
- `transcript.srt` —— 时间码字幕
- `transcript.json` —— 分段数据（`segments` 含每段起止时间）
- 下面三个按类型二选一产出

### 三种类型

| 类型 | 判定依据 | 产出 | 用户拿它干什么 |
| --- | --- | --- | --- |
| **教程** | 有可点的界面、有参数、有具名工具，操作句密集 | `steps.md` | 照着做，或者让 AI 学会这件事 |
| **案例** | 有年份、数字、人名、事件动作 | `facts.md` | 洗稿二创，做知识动画的分镜素材 |
| **观点** | 只有论点和金句，既没物象也没步骤 | `note.md` | 当选题灵感，不当素材源 |

`steps.md` 是**按时间顺序**铺开的操作流（不按分数排序，因为步骤顺序本身就是信息），每条带时间码；带 ⚠ 的是作者当场打的招呼；后面附「坑和前提」和「参数速查」。

**教程型不要当稿子洗。** 它的价值是流程本身，不是里面的句子。用户要的通常是"这条我能不能照着做""这件事该我干还是你干"。所以你读完 `steps.md` 之后：

- 用一两句话说清它到底做了什么、需要什么前置条件（账号、密钥、装了什么软件）
- 指出哪几步是关键分叉、哪几步可以跳
- 再给判断：这套流程是让用户自己上手，还是你能直接替他跑完

`facts.md` 是事实卡片表，按"人 / 年份 / 数字 / 引语 / 专名 / 机构 / 动作"打分排序。案例型才用它。

分类是按句子密度算的（教程分 / 案例分都写在文件头），**会判错**。判得不对时用 `--type` 覆盖；分数贴在文件开头就是为了让你能一眼看出它凭什么这么判。

要文字直接读 `transcript.txt`；按时间定位查对应的 `.md` 或 `transcript.srt`。

**默认动作是：转写 → 看类型 → 读全文 → 自己判断该拿什么。** 用户的真实需求通常是"这里有什么能用的"，而不是"给我一份摘要"。

## 平台

抖音、小红书、B站、YouTube、TikTok、X、小宇宙、Spotify、RSS、本地音视频。

抖音、小红书依赖本机已有的登录态（`link_ingest.configure(True)` 已开启）。遇到验证码或登录过期，请用户本人完成；MediaCrawler / meme-lab 的配置与定时任务由它们自己维护，改动交回用户。

RSS 未指定 `--episode` 时只列出节目，等用户选定再处理。

## 误差边界

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

   它会从 `raw_text` 重新纠正并重写 `transcript.json` / `transcript.txt` / `transcript.srt`，命中的词和次数打到 stderr。没有命中说明词表写法有问题。
5. `data/hotwords.json` 被 gitignore，是唯一会累积增值的资产，换机器要手动带走。
