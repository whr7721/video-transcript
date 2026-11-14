---
name: shiwen
description: 用本机拾文把视频、播客链接或本地音视频转成带时间码的文字，并给出原始视频/音频的位置。也能抓网页列表、盯页面变化、列博主更新、批量翻页去重；抓不到的时候说清是反爬、要登录还是前端渲染。适用于"转写这个视频""把这段音频变成文字""这期播客讲了什么""把这个榜单或搜索结果抓下来""盯着这个页面变没变""他更新了吗"。
---

# 拾文（自用版）

只做一件 agent 做不到的事：**把音频变成带时间码的文字**，并告诉你原始文件在哪。

## 不确定能不能用，先跑这个

```powershell
D:\zcode1\video-transcript\.venv\Scripts\python.exe -X utf8 D:\zcode1\video-transcript\status.py
D:\zcode1\video-transcript\.venv\Scripts\python.exe -X utf8 D:\zcode1\video-transcript\status.py --live
```

不带参数 0.1 秒，读本地记录；加 `--live` 约 3 秒，解密 cookie 直接问服务端"还认不认"。

**`--live` 才是真判断。** 本地 cookie 没过期，不代表服务端还认——小红书就是活例子：`web_session` 标称有效期到 2027 年，本地看着好好的，一请求 `302 /login`。只看 cookie 会得出"登录有效"的错结论。

用户说"抓不动""登录态好像掉了"，先跑 `--live`，别猜。

抖音这种签名鉴权的站探不了，用 `--set` 人工记一笔：

```powershell
... status.py --set douyin.com=ok "浏览器开搜索页返回了笔记标题/作者"
```

## 先分清手里是什么

| 你拿到的是 | 用哪个 | 会发生什么 |
| --- | --- | --- |
| 一条视频 / 一期播客 / 一个本地文件 | `grab.py` | 下载 → 转写 → 打印概览和文件路径 |
| 一个博主主页 / YouTube 频道 / B站 UP 主 / RSS | `follow.py` | 先 `add` 记住，再扫出共几条、最新哪条 |
| 一个榜单 / 活动页 / 专题页 / 搜索页 | `scrape.py` | 抓一次，按元素 / 接口 / 文字 / 截图取 |
| 一个会变、要盯着看的页面 | `watch.py` | 抓一次存基线，之后只报变动 |

**抓不动的时候先看 `BOUNDARY.md`**（仓库根目录）。它按站点类型列了实测结果，并把五种失败原因分开——前端渲染、反爬挑战、要登录、页面型内容、代理不通，现象长得很像，处理方式完全不同。别在不清楚原因的情况下反复重试。

四个入口，其余都是内部实现。走错门时 `grab.py` 会直接告诉你该换哪个，不用自己猜。

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

## 平台与登录态

抖音、小红书、B站、YouTube、TikTok、X、小宇宙、Spotify、RSS、本地音视频。

登录态有三套机制并存，别搞混。`status.py` 会直接告诉你每站在哪一套里：

| 站点 | 走什么 | 实测（2026-11-14） | 说明 |
| --- | --- | --- | --- |
| 抖音 | 浏览器 + `data/browser` profile | **可用** | 搜索页返回真实笔记；`a_bogus` / `msToken` 由页面 JS 算 |
| 小红书 | 浏览器 / cookie + 签名 | **已失效，要重登** | 本地 `web_session` 标到 2027，服务端 `302 /login` |
| B站 | cookie + httpx | **游客态，照常能用** | 无 `SESSDATA`，但公开接口、评论、热门榜不登录也能读 |
| 微博 | — | 未登录 | |

**三档状态，别只看"登没登"：**
- **可用** — 带登录态抓，能看到关注流、私密内容
- **游客态** — 没登录，但公开内容照样抓得到。**B站、微博大量场景属于这一档，不等于"不能用"**
- **已失效** — 本地还留着 cookie，服务端已经踢了，必须重登

同一个 profile 能装多个站点，`--login` 跑一次就多一个站点的 cookie，不必为每个平台开新目录。`data/browser-bilibili` / `data/browser-xiaohongshu` 是 auth 模块留下的独立目录方案，目前不存在——只有 `data/browser` 一套在真用。

**为什么抖音不能只存 cookie。** 它拦的是 JS 算出来的签名（`a_bogus`），不是 TLS 指纹。把 `sessionid` 抠出来塞给 `httpx` 或 `curl_cffi`，拿回的是 `403 Blocked by ArgusSecurityPlugin`——现象很像"登录态失效"，实际是绕过了算签名的那一层。所以抖音必须留 profile，用浏览器开页面。

**反过来，B站 / 小红书 / 微博这类只要 cookie 就能过的站，导成 JSON 更省事**：不用每次起浏览器，`httpx` 带着 cookie 直连就行。这就是 `data/cookies/` 那套的用途，和抖音的 profile 不是二选一，是各走各的。

遇到验证码或登录过期，请用户本人完成；MediaCrawler / meme-lab 的配置与定时任务由它们各自维护，改动交回用户。

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

# 不开浏览器，直接拿正文（政府公告 / 新闻 / 博客 / 文档站）
... scrape.py "<url>" --fast

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

**`--fast` 是快路径，先试它。** 它用 curl_cffi 伪造 Chrome 的 TLS 指纹直接发 HTTP（不是 `httpx`，`httpx` 用的是 OpenSSL 的握手顺序，一眼就被识别），再用 trafilatura 提正文，0.5 秒一页，不消耗浏览器登录态。

适用：服务端直出 HTML 的页面——政府公告、新闻、博客、文档站、论坛。实测天津政采 1844 字 0.57s、MDN 10524 字 0.95s、天津数据开放平台 1483 字 0.56s。

**两种模式：** trafilatura 抽到主文章时是 `fast`（干净无导航）；抽不到但页面有字时自动转 `fast-raw`（去标签全文，带导航噪音），适合首页和列表页——这些页面本来就没有「一篇主文章」。想强制全文用 `--fast-whole`。stderr 会标注是哪种。

不管用：前端渲染页和跳转壳页。这两种会自动降级到浏览器，stderr 打一行 `[fast] 降级到浏览器：HTML 里没有正文（可见文字仅 60 字…）`。所以**放心先加 `--fast`**，最坏情况是多花一次请求。

实测对比：天津政采首页 `--fast` 抓到 42 条、1.17 秒，开浏览器 137 条、8.33 秒。不是漏抓，是两种取法对「什么算一条」的定义不同——要快用 fast，要全量用浏览器。

它和 `--selector` / `--xhr` / `--js` / `--shot` 互斥：要这些就必须起浏览器，`--fast` 会被忽略。境外站点靠环境变量代理（`$https_proxy`），报 `CONNECT tunnel failed` 时先查梯子。

**不要给抖音加 `--ua`。** 抖音的 webid 是按 UA + 屏幕分辨率生成的，换 UA 就破坏了 webid 与 UA 的一致性，a_bogus 签名校验直接失败——现象像「登录态突然失效」，其实是自己把环境改坏了。脚本已在抖音域名下拒绝该参数。

抖音/快手的纯请求这条路不通，浏览器是唯一入口：`httpx` 直连抖音接口返回 `403 Blocked by ArgusSecurityPlugin`，快手 graphql 返回 `{"result":2}`（风控码）。它们拦的不是 TLS，是 JS 算出来的签名（`a_bogus` / `x-s`），curl_cffi 过不了这一层。

## 批量：翻页 + 去重

列表页翻页分三种，按稳定性排：

1. **URL 参数**（最稳）：`--page-param page`。把 URL 里的 page 换成 2、3、4……，其余参数原样不动。
2. **下一页按钮**：`--next "a.next"`。点不到会直接报错，并提示先数一下选择器。
3. **无限滚动**：两个都不给，默认滚到底再抓。最不稳，容易反复抓到同一批。

```powershell
# 抓 5 页，自动去重
... scrape.py "<url>" --selector ".item" --pages 5 --page-param page

# 元素是复合对象时，按某个字段去重（不然整条 JSON 里带时间戳就永远不重复）
... scrape.py "<url>" --js "<返回数组的表达式>" --pages 5 --page-param page --dedupe url
```

去重是逐条做的：本页内重复、跨页重复、跟基准文件重复，都算。stderr 每页打一行：

```
[page 3/5] 本页 20 条，新增 18，重复 2
```

**某页返回 0 条就停**，不再往下点——继续只会拿到同一批东西或错误页。

**增量**：`--seen 基准.json` 让第二次跑只报新增，跑完基准自动更新成全量。加 `--only-new` 则只输出新增。

```powershell
... scrape.py "<url>" --pages 5 --page-param page --selector ".item" --seen data/jobs.json --only-new
```

**不能和 `--xhr` 一起用。** 翻页会连续触发请求，多页的接口数据混在一起分不清先后。先用 `--xhr-list` 找到接口地址，再用 `--page-param` 直接改 URL 翻页。

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

## 盯变化

`scrape.py` 抓一次就结束，看不出「和昨天比变了什么」。要盯的东西（价格、公告、榜单、政策、库存）用 `watch.py`：

```powershell
# 建监控项，第一次抓的当基线，不报变化
... watch.py add 显卡价格 "https://..." --selector "span.price"
... watch.py add 公告 "https://..." --ignore "更新于.*"
... watch.py add 政采首页 "https://..." --fast      # 静态站不开浏览器

# 之后每次只报变动
... watch.py run                # 全部跑一遍
... watch.py run 显卡价格
... watch.py list
... watch.py show 显卡价格       # 历史变化记录
... watch.py rm 显卡价格
```

`--fast` 只能配整页文字（不给 `--selector` / `--js`），静态站用它能快七倍：实测天津政采 **1.17 秒 vs 8.33 秒**。前端渲染页会自动降级回浏览器，同一份配置不用改。注意两者抓到的条目数不同（42 vs 137），是粗粒度差异不是丢数据。

两种粒度，看你要什么：

| 取法 | 看到什么 |
| --- | --- |
| `--selector "..."` / `--js "..."` | **哪一条**进了、哪一条出了、哪几条换了位次 |
| 都不给（整页文字按行） | **哪一行**变了，带前后文 |

### 抗噪是这类活成不成的关键

直接比原始文本会天天报变化——播放量、访问数、时间戳一直在动。两个参数：

```powershell
--strip "\s+\d+(?:\.\d+)?万?(?:\s+\d+)*$"   # 抹掉行内会动的片段（数字、时间）
--ignore "更新于.*"                          # 整行剔除
--only "价格|¥|￥"                           # 只留关心的行
```

实测 B站热门榜：不抹播放量时每次都报「20 条全变」；抹掉之后同样的页面报「无变化」。**先用 `--strip` 把会动的东西去掉，再看结果，别急着相信第一次的 diff。**

用 `--strip` 的前提是选择器选得够细。`.video-card` 拿到的是「标题 + 作者 + 播放 + 弹幕」一整串，抹数字就得小心别把标题里的数字也抹了；能选到只含一个字段的元素（`.price`、`.title`）就不用抗噪。

### 抓到 0 条不算变化

页面改版后选择器失效，抓回 0 条。如果当成「原来的全部消失」，报出来的假变化会让人再也不信这个工具。所以 `watch.py` 抓到 0 条时**不比对、不覆盖基线、只报错**，并给出诊断命令。

`add` 时抓到 0 条会直接拒绝建基线，并打印页面标题（确认页面本身加载成功了）和两条探路命令。

扫描和转写要分开，这里的道理和 `follow.py` 一样：`run` 才抓，不加参数不会自己去跑。

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
