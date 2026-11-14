---
name: shiwen
description: 用本机拾文把视频、播客链接或本地音视频转成带时间码的文字，并给出原始视频/音频的位置。适用于"转写这个视频""把这段音频变成文字""这期播客讲了什么"。
---

# 拾文（自用版）

只做一件 agent 做不到的事：**把音频变成带时间码的文字**，并告诉你原始文件在哪。

## 先分清手里是什么

| 你拿到的是 | 用哪个 | 会发生什么 |
| --- | --- | --- |
| 一条视频 / 一期播客 / 一个本地文件 | `grab.py` | 下载 → 转写 → 打印概览和文件路径 |
| 一个博主主页 / YouTube 频道 / B站 UP 主 / RSS | `follow.py` | 先 `add` 记住，再扫出共几条、最新哪条 |
| 一个榜单 / 活动页 / 专题页 / 搜索页 | 自己开浏览器 | 本工具不处理页面，见下面「页面型内容」 |

工具提供的就这两个入口，其余都是内部实现。`grab.py` 收到主页链接会直接告诉你改用 `follow.py`，收到页面链接会告诉你该自己开浏览器，不用自己判断。

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

## 关注源

用户有一批固定要看的人（比如 Michael大麦哥），别每次让他贴链接：

```powershell
... follow.py add "https://www.douyin.com/user/MS4w..."   # 加一个，裸 sec_uid 也认
... follow.py                                           # 扫一遍：共几条、最新哪条、有没有新的
... follow.py new                                       # 看哪些新的还没转
... follow.py run --seq 3                               # 显式要转才转，可指定哪条
... follow.py list                                      # 关注了谁
... follow.py rm --only 5e6eee28                        # 取消关注
```

扫描输出长这样：

```
Michael大麦哥　共 210 条作品　本次看最近 20 条
    最新　2026-11-13 06:59　6 分钟
          推荐3个我真的很喜欢的播客
    没有新的
```

**扫描不等于转写。** 用户想知道的是"他更新了吗、最新的是哪条"，一条 30 分钟的作品转起来要一分多钟，不要顺手把全主页跑一遍。要文字时用 `run`，一次几条由用户定。

第一次扫描只建基线（记下现有作品，一条不转），之后按作品 id 比对，只把没见过的记成新的。所以新加一个人不会把人家几年历史全跑一遍。

支持抖音博主主页、RSS / 播客、YouTube 频道、B站 UP 主。单条视频仍然走 `grab.py`。

要让这件事定期发生，挂个每天一次的定时任务调 `follow.py` 即可，重复跑不会重复记录。

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

## 页面型内容

榜单、活动页、专题页、搜索页、快手的任何页面 —— 这些不是「一条作品」，`grab.py` 和 `follow.py` 都不处理。用 `scrape.py`，它就是这个骨架的参数化版本：

```powershell
# 先看这页调了哪些接口（不取响应体，最快）
... scrape.py "<url>" --xhr-list "aweme/v1/web"

# 拿到感兴趣的接口，取结构化数据
... scrape.py "<url>" --xhr "aweme/v1/web/hot/search/list" --xhr-parse

# 页面上直接取元素
... scrape.py "<url>" --selector "a[href*='/hot/']"
... scrape.py "<url>" --selector "a.video" --attr href

# 整页文字 / 任意表达式 / 滚动后截图
... scrape.py "<url>" --text --scroll 3
... scrape.py "<url>" --js "document.title"
... scrape.py "<url>" --shot shot.png

# 新站点：扫码建登录态
... scrape.py --login "https://www.kuaishou.com"
```

`data/browser` 里存着抖音的登录态，用它开页面跟真人浏览器没区别：`a_bogus`、`msToken`、`uifid` 都由页面里的 JS 现场算，不用实现签名。同一个 profile 可以装多个站点，`--login` 跑一次就多了一个站点的 cookie，不必为每个平台开新目录。

三种取法的差别，实测抖音热榜：

| 方式 | 拿到 | 什么时候用 |
| --- | --- | --- |
| `--selector` | 51 个词，只有文字 | 页面上看得见的就够 |
| `--xhr` | 51 个词 + 热度值 + 榜位 | 要排序、要筛选、要字段 |
| `--text` | 3277 字，但只有导航和页脚 | 内容不是虚拟滚动时 |

两个坑：

**`--text` 常常拿不到正文。** 列表是虚拟滚动的，`innerText` 只有导航和页脚。这时候用 `--selector` 针对条目取，或者 `--xhr` 直接拦接口。

**Git Bash 会把以 `/` 开头的参数改写成 Windows 路径。** `--xhr "/aweme/v1/web/"` 会变成 `C:/Program Files/Git/aweme/v1/web/`，然后安静地返回 0 条——不报错，最难查。脚本里已经做了还原，但更稳的写法是不带开头斜杠：`--xhr "aweme/v1/web"`。

纯请求这条路不通，浏览器是唯一入口：`httpx` 直连抖音接口返回 `403 Blocked by ArgusSecurityPlugin`，快手 graphql 返回 `{"result":2}`（风控码）。

**选择器靠探，不靠猜。** 先数一下有没有：

```powershell
... scrape.py "<url>" --js "document.querySelectorAll('.rank-item').length"
```

返回 0 就换一个，20 就对了。想一次试几个就传数组：

```powershell
... scrape.py "<url>" --js "[document.querySelectorAll('.rank-item').length, document.querySelectorAll('.video-card').length]"
```

实测 B站热门榜：`.rank-item` 是 0，`.video-card` 是 20。改对之后一条命令出 20 条「标题 + 作者 + 播放 + 弹幕」，因为卡片容器的 `innerText` 本来就是连着的。

页面结构随时会变，所以每次现场探，不把选择器写成固定脚本。从页面上拿到具体作品链接之后，再喂给 `grab.py` 转写。

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
