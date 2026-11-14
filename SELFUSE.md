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
33:43 ｜ 115 段 ｜ 10445 字
操作句 5% ｜ 顺序词 10% ｜ 叙事句 14% ｜ 具体信息 36 处（每百字 0.3）

全文：D://zcode1//video-transcript//data//jobs//3f2bc4eb027b02fc//transcript.txt
媒体：D://zcode1//video-transcript//data//jobs//3f2bc4eb027b02fc//podcast.audio（62 MB）
```

支持平台：抖音 / 小红书 / B站 / YouTube / TikTok / X / 小宇宙 / Spotify / RSS / 本地文件。
转写本机完成（SenseVoice INT8，约 30 倍实时，零费用）。

常用参数：`--facts`（顺带出事实卡）、`--steps`（顺带出操作流）、`--lang en`（英文内容）、`--episode 3`（RSS 选集）、`--json`（给脚本吃）。

只想对已有任务重出附加产出，不用重新下载：

```powershell
.\.venv\Scripts\python.exe -X utf8 facts.py <任务ID> --facts
```

---

## 转完给什么

一条命令转到文字，打印概览和两个路径，结束：

```
AI 配音怎么做，我是怎么做视频的
12:08 ｜ 73 段 ｜ 4075 字
操作句 24% ｜ 顺序词 24% ｜ 叙事句 2% ｜ 具体信息 11 处（每百字 0.3）

全文：...\data\jobs\<id>\transcript.txt
媒体：...\data\jobs\<id>\original.mp4（88 MB）
```

那行百分比不是分类，是描述：多少句在讲操作、多少句在讲人和事、有多少处具体数字。读完大概知道文字本身够不够用——**而"够不够用"取决于要拿它干什么，那件事不归工具管**。

事实卡和操作流是可选视图，`--facts` / `--steps` 才生成，不默认出。

### 试过类型判定，删了

先加过教程 / 案例 / 观点三分类，各自出专属文件，还写了「教程不该拿去洗稿」「观点不能当素材」。规则本身调得还行——26 份样本，7 份教程最低 0.46，18 份观点最高 0.39，中间是空的。

删掉有三个理由，最后一个最要紧：

1. **判不准。** 案例样本只有 1 份，阈值等于没验过。
2. **同一个稿子的用法不唯一。** 我判成"只能当论点"的那篇，用户完全可以拿去改成图文。
3. **判对了也没用。** 判完还是要读一遍才知道里面有什么。既然要读，判定就是多余的一步——它只会在读之前先把思路框住。

**工具只报事实，方向由读的人定。** 这句话和下面「刻意不做的事」是同一条原则，之前没守住。

### 口播在描述画面时，文字会发虚

那条 AI 配音教程是最好的例子。文字里说「我先跟他说明两件事」「按中文女生筛出 60 个」——听着挺具体，实际什么也没说清。

抽一帧出来看，画面上写着：`key.txt` 原本 0 字节、现在 51 字节；模型 ID 是 `eleven_v4`，在 `/v1/models` 里核对过；三条挑选依据是平台标签 / 客观测量 / 语音识别闭环；底层参数 PCM、中位基频、半音标准差；10 个候选的字符准确率全部 100%。

**这些音频里一个字都没有。**

这类内容的信息载体是画面，音频只是解说。所以工具能做的只有一件事：把 `original.mp4` 的绝对路径印在概览里。抽哪一帧、看什么、看完怎么用，交给 agent——它按需抽比我预设均匀抽 12 帧准得多。

判据长什么样：句子多、具体信息少（这条每百字 0.3 处）、读完不知道东西长什么样。这三样凑齐基本就是画外音稿。

---

## 关注源

产品版里这块叫 `subscriptions.py`：FastAPI 路由 + 前端 `Subscriptions.tsx` + 一个后台线程按 interval 检查。精简时连同前端一起删了，但功能本身是我在用的——固定要看的人（Michael大麦哥），不想每次贴链接。

恢复成一条命令，逻辑不动，只换了外壳：

```powershell
follow.py add "<主页链接>"     # 记住一个人
follow.py                      # 扫一遍：共几条、最新哪条、有没有新的
follow.py new                  # 看还有哪些没转
follow.py run --seq 3          # 显式要转，才转
follow.py list / rm
```

**扫描和转写是两件事。** 我要的多数时候只是"他更新了吗、最新的是哪条"，一条 30 分钟的作品转起来一分多钟，顺手把主页全跑一遍是最糟的设计。所以不带子命令只扫，`run` 才动转写。

数据仍然落在 `tasks.sqlite3` 的 `channels` / `feed_items` 两张表，字段沿用原版（`id / url / platform / payload`，`UNIQUE(channel_id,content_id)`）。表一直在，只是空着——精简时删的是代码不是数据。

### 作品总数得从页面读

`/aweme/v1/web/user/profile/other/` 这个接口现在对抓取账号返回 `DataFetchError: account blocked`，但 `/aweme/v1/web/aweme/post/`（作品列表）正常。所以昵称和作品总数改成从主页页面上读：

```js
const m = document.body.innerText.match(/作品\s*(\d+)/)
const el = document.querySelector('[data-e2e="user-title"]')
```

读不到就退回兜底（缓存里的昵称、不显示总数），不因为一个数字让整个扫描失败。接口那条路留着——没被风控时它更准（`aweme_count`）。

### 第一次扫描不转写

这个决定不能省。新加一个人，主页上 21 条作品，其中 30 分钟的长视频转一条要一分半——全转完一个多小时，而且他三年的历史我不是每条都要。

所以 `initialized` 之前只入库、标记已见，一条不转；之后按作品 id 比对，`feed_items` 里没见过的才算新的。代价是：**加人的那一刻，他现有的作品我不会告诉你**，想要就 `follow.py new` 里挑着转，`run --seq` 支持指定。

### 和原版的三处差别

1. **没有后台线程。** 原来服务活着就自己按 `interval_minutes` 轮询。现在靠外部定时任务调 `follow.py`——重复跑不会重复转，是幂等的。
2. **没有收藏源。** `douyin_favorites` 那条分支还在 `source_enumeration.py` 里能跑，但 `follow add` 只收主页；收藏是"我点了喜欢"而不是"我固定要看的人"，混在一起反而乱。
3. **去掉了话题源。** 原版支持把关键词当持续追踪的抖音搜索，依赖的 `douyin_search_bridge.py` 在精简时删了，那块也没再用过。

`source_enumeration.py` 从封存版恢复时改了两处：`link_jobs.normalize`（4 行，抽链接）内联进来，避免为它拖回 `link_jobs.py` 那 175 行和 `documents` / `job_retry` / FastAPI 一整套；`douyin_topic` 分支删除。其余原样，包括抖音那条 `--metadata-only` 的参数——它让列表只取元数据，不下载视频。

---

## 盯变化

`follow.py` 盯的是「这个人有没有发新的」，`watch.py` 盯的是「这个页面变了没有」。两者差一层：前者按 id 比，后者按内容比。

### 为什么不塞进 scrape.py

`scrape.py` 的职责是「打开一个 URL，按指定方式取出东西」。加一层状态存储和 diff，它就从「工具」变成了「有记忆的系统」，下一次想改抓取方式还得顾虑已有数据。

所以拆开，而且是用**子进程**调，不是 import：

```
watch.py ──subprocess──> scrape.py --out tmp.json
```

代价是每次多起一个 Python 进程（几十毫秒，比起浏览器启动可以忽略）。收益是 `scrape.py` 完全不知道 `watch.py` 存在，改抓取逻辑不会牵动比对逻辑，反过来也一样。两边只有 `--out` 的 JSON 这一个契约。

### 抗噪是这类活的全部难点

第一版没做抗噪，拿 B站热门榜试：抓两次，每次都报「20 条全变」。因为卡片文本里带着播放量（`87.3万`），几分钟就变一次。

加上 `--strip '\s+\d+(?:\.\d+)?万?(?:\s+\d+)*$'` 抹掉行尾数字后，同样的页面连抓两次报「无变化」。

**这说明一个反直觉的事：diff 能不能用，取决于洗得干不干净，不取决于算法。** 用 `difflib` 还是集合比对是次要的，噪音没处理掉的话，再聪明的算法也只是把假变化排得更整齐。

三个参数分工：

| 参数 | 作用 | 典型用法 |
|---|---|---|
| `--strip` | 抹掉行内片段，保留行 | 播放量、访问数、时间戳 |
| `--ignore` | 整行剔除 | 「更新于 2026-11-14」这种整行没用的 |
| `--only` | 只留匹配行 | 「我只看价格那几行」 |

`--strip` 的前提是选择器够细。`.video-card` 拿到「标题 + 作者 + 播放 + 弹幕」一整串，抹数字就得小心别把标题里的数字一起抹了。能选到只含一个字段的元素就不用抗噪。

### 抓到 0 条时不算变化

这是最要紧的一条。页面改版、选择器失效，抓回 0 条。如果按「原来的全部消失」处理，报出来的假变化会让人再也不信这个工具——而且基线被覆盖成空，从此这个监控项就废了。

所以 `add` 时抓到 0 条直接拒绝建基线（并且先打印页面标题，说明是页面加载成功但选择器不对，不是网络问题）；`run` 时抓到 0 条不比对、不覆盖，只报错。

### 有新增时不报位次

集合比对和位次比对必须分开。插入一条，后面全部位移 1，如果照报，一次新增会带出几十条「位次变了」。

所以：有新增或消失时只报集合变化；两边集合完全一致、顺序变了，才报「N 条重排」。后者才是真信号（榜单第 1 名换人了）。

---

## 刻意不做的事

摘要、精华、金句、二创改写、导图、章节导读、切片 —— **这些以前固化在 `rewrite.py` / `clips.py` / `summary` 里（现已从工作区移除），现在全部交给 agent。**

理由：固化是为了服务"没用过 AI 的人"，自用没必要。每多一个固定环节，就多一处要维护、多一处跟不上模型能力。**工具只负责把不可替代的那步做掉，剩下的让 agent 现场判断。**

不可替代的是哪一步：**音频 → 带时间码的文本。** agent 没有耳朵，它做不了这一步；剩下的它比你我都做得好。

同样的道理适用于"这条稿子该怎么用"。判断值不值得做、洗稿还是照做、做成动画还是图文——这些读一遍就有答案，而且答案随我当天想做什么而变。写进规则就是在替未来的我决定。

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

## 产出的误差边界

这不是可信文本，是**有骨架的草稿**：

- **数字、年份、金额通常是对的** —— 也是 agent 补不出来的
- **专有名词成系统错** —— `Nova Scotia` → `novava scotia` / `nobo Sc`；`加元` → `家元`
- 所以：**上屏前按时间码回听核对**，尤其人名、地名、机构名

步骤单多一条边界：**时间码是真的，步骤边界是推的**。操作句的切分来自转写稿，但"这是一步、那是下一步"是我按操作词和顺序词估的，原作者未必这么分。照着做之前按时间码回看那一段，别把相邻两句当成一条命令。

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
| `grab.py` | ~105 | 链接 → 转写 → 概览，一条命令 |
| `facts.py` | ~380 | 概览统计、事实卡、操作流；`--recorrect` 重跑专名纠正 |
| `follow.py` | ~250 | 关注源 → 新作品 → 转写；第一次只建基线 |
| `source_enumeration.py` | ~99 | 列出某个源最近 N 条（抖音主页 / RSS / YouTube / B站），从封存版恢复 |
| `scrape.py` | ~185 | 页面抓取：元素 / 接口 / 文字 / 表达式 / 截图，用登录态浏览器 |
| `watch.py` | ~430 | 页面监控：抓一次存基线，之后比对只报变动 |

前四个是**转写链**，只读调用现有模块（`link_ingest` / `transcribe` / `store` / `session`），不修改任何原有代码，删掉它们封存版不受影响。

后两个是**抓取链**，完全独立：`scrape.py` 不 import 仓库任何模块，`watch.py` 用子进程调 `scrape.py`。这两块和转写链没有任何代码交集，可以单独拷走使用。

---

## 精简时漏掉的一类依赖

删掉 51 个产品层模块时用的是静态 import 闭包，它能算出 `import x` 形式的依赖，**算不出下面两种**：

1. **字符串路径调用**：`subprocess.run([MC_PY, str(ROOT / "extractor.py"), ...])`。`extractor.py` 不是被 import 的，是被当文件名执行的，所以没进闭包——而抖音的下载全靠它。
2. **间接依赖**：`extractor.py` 里有 `from batch_rules import classify_post`，但 `extractor.py` 当时已被删，所以 `batch_rules` 也从没进过闭包。

后果：抖音链接会直接报「采集组件未能启动」，其他平台不受影响——**只有抖音这一条路是断的，而且报错信息看起来像环境问题，不像缺文件。**

已从 `v1.0-portfolio` 恢复 3 个文件：`extractor.py`、`batch_rules.py`、`douyin_favorites.py`。抖音依赖闭包共 4 个（另加 `douyin_session_guard.py`），当前 41 个模块、按 import 语句逐个核过、断链为 0。

**可复用的排查法**（比字符串搜索可靠）：

```python
# 对每个被删模块名，检查是否仍被保留代码 import
tag = {p[:-3] for p in git_ls_tree('v1.0-portfolio') if '/' not in p and p.endswith('.py')}
for f in Path('.').glob('*.py'):
    for m in re.finditer(r'^(?:\s*from|\s*import)\s+([A-Za-z_]\w*)', f.read_text(), re.M):
        if m.group(1) in tag and m.group(1) not in disk_modules: report(f, m.group(1))
```

只搜 `xxx.py` 字面量会漏掉 `from xxx import` 这种写法——`batch_rules` 就是这样漏掉的。

## 抖音链路的三个外部依赖

代码补齐之后还报「采集启动失败（Error）」，原因是**运行环境**，不是代码。抖音这条路要三样东西同时在场，缺任何一样都失败：

| 依赖 | 位置 | 检查方式 |
|---|---|---|
| MediaCrawler | `D:\zcode1\mediacrawler`（1.2 GB） | 目录存在即可 |
| 独立 Python 环境 | `mediacrawler\.venv\Scripts\python.exe` | `SHIWEN_MC_PYTHON` 可覆盖 |
| **Playwright Chromium** | `%LOCALAPPDATA%\ms-playwright\chromium-1248\` | 见下 |

第三条最容易漏——它是二进制下载，不在任何仓库里，清理工具或重装系统后会消失，而报错信息只说「采集启动失败（Error）」，看起来像登录问题。

**判据**：

```powershell
D:\zcode1\mediacrawler\.venv\Scripts\python.exe -c "from playwright.sync_api import sync_playwright; from pathlib import Path; p=sync_playwright().start(); e=Path(p.chromium.executable_path); print(e, e.exists())"
```

返回 `False` 就装：

```powershell
cd D:\zcode1\mediacrawler
.\.venv\Scripts\python.exe -m playwright install chromium
```

约 118 MB，国内直连 `cdn.playwright.dev` 可下，不需要镜像。

**登录态**：`data\browser`（不是 MediaCrawler 那个 profile）。`session.py` 从 `D:\zcode1\mediacrawler\browser_data\dy_user_data_dir` 复制一次 Identity / Network / Local Storage，之后所有写入只落在 `data\browser`，不动原采集浏览器。Cookie 实际在 `Default\Network\Cookies`（新版 Chromium 位置），不要在 `Default\Cookies` 找。

登录失效时 `extractor.py login` 会开有头窗口等人工扫码，过期只能手动重登——这条没法自动化。

---

## 给 agent 的 Skill

`skills/shiwen/SKILL.md` 已同步改成自用版（`dsh-plugin/skills/shiwen/` 是同一份的分发副本）：

- 只讲一条命令 `grab.py` 和产出文件在哪
- 写清误差边界：数字可信、专名必核，以及 `--recorrect` 这一步
- 默认动作从「转写 → 调摘要接口」改成「转写 → 读全文 → agent 自己判断」

原来的 skill 是给"不接 AI 的用户"写的，教 agent 去调工具里固化的加工链；自用场景下那条链正是要被绕过的部分。

**不写禁令表**：产品层文件已经移除，agent 扫目录本来也找不到 `summarize` / `app.py`；把它们列进文档反而把不存在的名字塞进上下文，遇到内容像"摘要"的任务时更容易被联想起来。只写「转完之后的事由你直接读 `transcript.txt` 完成」这一句正向分工就够。
