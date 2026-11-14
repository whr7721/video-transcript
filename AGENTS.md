# 拾文 · 本机自用版

这个仓库只做一件事：**把音视频变成带时间码的文字**，并告诉你原始文件在哪。

完整产品版（Web 工作台、前端、云端）封存在 git tag `v1.0-portfolio`，需要时 `git worktree add ../shiwen-full v1.0-portfolio` 取出。

**动手前先看 `BOUNDARY.md`**：哪类站点能抓、抓不到时是哪一种错、三个「看起来能其实不能」的坑。失败现象长得很像，判断依据都在那一页。

## 入口

```powershell
.\.venv\Scripts\python.exe -X utf8 grab.py "<链接或本地文件>"
```

产出在 `data/jobs/<job_id>/`：`transcript.txt`（全文）、`transcript.srt`（时间码）、`transcript.json`（分段）、`audio.wav`、`original.mp4`（原始视频）。

两个可选视图，想要才要：

```powershell
.\.venv\Scripts\python.exe -X utf8 facts.py <job_id> --facts   # 事实卡：人/年/数/引语，带时间码
.\.venv\Scripts\python.exe -X utf8 facts.py <job_id> --steps   # 操作流：操作句按时间排开
```

榜单 / 活动页 / 专题页 / 搜索页不属于单条作品，`grab.py` 和 `follow.py` 都不处理，用 `scrape.py` 抓一次；要盯变化就用 `watch.py`。两者都用 `data/browser` 的登录态，签名由页面 JS 算。做法和实测结论见 `skills/shiwen/SKILL.md` 的「页面型内容」和「盯变化」。服务端直出的页面（政府公告 / 新闻 / 博客）加 `--fast` 可以完全跳过浏览器，0.2 秒一页；前端渲染页会自动降级。

## 盯变化

`scrape.py` 抓一次就结束。要比较「和上次比变了什么」，用 `watch.py`：

```powershell
.\.venv\Scripts\python.exe -X utf8 watch.py add 显卡价格 "https://..." --selector "span.price"
.\.venv\Scripts\python.exe -X utf8 watch.py run          # 只报变动
.\.venv\Scripts\python.exe -X utf8 watch.py list / show <名字> / rm <名字>
```

`add` 第一次抓的当基线，不报变化。`--strip` 抹掉行内会动的片段（播放量、时间），`--ignore` 整行剔除，`--only` 只留关心的行——不抗噪的 diff 天天报「全变了」，等于没有。抓到 0 条时不算变化（选择器失效的可能性远大于页面真的空了），只报错、不覆盖基线。

状态在 `data/watch/<名字>/`：`config.json`、`state.json`（当前条目）、`log.jsonl`（变化历史）、`snapshots/`（最近 20 份）。

## 关注源

记住一批在跟的人，每次只处理新作品：

```powershell
.\.venv\Scripts\python.exe -X utf8 follow.py add "https://www.douyin.com/user/MS4w..."  # 加一个
.\.venv\Scripts\python.exe -X utf8 follow.py          # 扫一遍：共几条、最新一条、有没有新的
.\.venv\Scripts\python.exe -X utf8 follow.py new      # 看有哪些新的还没转
.\.venv\Scripts\python.exe -X utf8 follow.py run      # 要转才转（--seq 3 只转某条）
.\.venv\Scripts\python.exe -X utf8 follow.py list     # 看关注了谁，以及各建没建基线
.\.venv\Scripts\python.exe -X utf8 follow.py sync     # 扫 + 转，一次跑完
```

第一次扫描只建基线，不转历史；之后按作品 id 比对，只把没见过的记成新的。**扫描默认不转写**，转写要显式要。

支持抖音博主主页、RSS / 播客、YouTube 频道、B站 UP 主。状态存在 `data/tasks.sqlite3` 的 `channels` / `feed_items` 表，转写完把 `job_id` 写回对应条目。

转完打印里带 `original.mp4` 的绝对路径。口播在描述画面（「点这里」「选这个」）时可读性会明显发虚，那部分信息在画面里，自己抽帧看。

平台：抖音 / 小红书 / B站 / YouTube / TikTok / X / 小宇宙 / Spotify / RSS / 本地文件。抖音和小红书走本机已有登录态，验证码或登录过期请用户本人处理。

转完之后的事——摘要、金句、二创、切片、导图、选题判断——由你直接读产物完成。这条稿子该怎么用，用户可能有完全不同的打算。

## 代码地图

45 个文件、6000 行，两条主链 + 两个页面工具：

```
grab.py   ─┬─ link_ingest ─ pipeline ─ transcribe ─ store ─ facts
follow.py ─┘       │
                   ├─ 抖音：extractor.py（子进程，页面内算签名）
                   ├─ 小红书图文：xhs_ingest ─ image_documents ─ articles ─ ocr_reading
                   └─ 摘要导图：cli_summary ─ manuscript / mindmap（summarize=False 时不触发）

scrape.py ─── Playwright（自己一个文件，不 import 仓库里任何模块）
watch.py  ─── 子进程调 scrape.py ─ 规范化 ─ 比对 ─ data/watch/
```

**主链就是这条竖线上的十几个文件**，平时改的就是这些。图文 OCR 那 10 个、摘要导图那 5 个是支路：只有小红书图文笔记和 `--summarize` 才会走，抖音视频一根线都不碰，但因为被 `link_ingest` 顶层 import 着，看上去像主干。

`scrape.py` 和 `watch.py` 是刻意独立的两块：`scrape.py` 不 import 仓库任何模块，`watch.py` 用子进程调 `scrape.py` 而不是 import 它。这样抓取方式变化（选择器失效、改拦接口）不会传染到比对逻辑，改哪边都不打断另一边。

那两条支路里有 7 处循环 import（`articles ↔ ocr_reading`、`ocr_reading ↔ image_editorial` 等）。Python 能容忍——只要不在模块顶层互相取名字——实测不影响运行。要动那几块先看 `SELFUSE.md`。

名字容易混的几个文件，分工是：`article_fetch` 抓网页 → `article_parser` 切块 → `articles` 存快照；`image_documents` 存图片原件 → `ocr_reading` 取文字 → `image_editorial` 拼成可读文档。`documents.py` 是本地草稿版本管理，和这两串都无关。

## 抓完页面要报三件事

每次抓完页面，在回复里写清，不要省：

1. **用了什么**：浏览器 / 接口 / 要不要签名 / 要不要登录态
2. **能不能复用**：骨架能（`scrape.py` 已参数化），选择器不能——页面一改就失效
3. **要不要入库**：默认不入；要入库由用户点头，只有长期要盯的页面才值得做成入口

## 硬规则

1. 转写原稿、事实卡、编辑稿是用户内容，任何改动不得使其被动变更或丢失。
2. `link_ingest` / `transcribe` / `store` / `asr_hotwords` 是稳定实现，只读使用；新逻辑写进 `grab.py` 或 `facts.py`。
3. MediaCrawler / meme-lab 等外部项目的配置与定时任务由它们自己维护，登录态改动请交回用户。
4. 不提交密钥、登录态、`data/`、模型权重、日志、`.venv`。
5. 说"已完成/已验证"必须附实际输出；命令退出码为 0 不等于产出质量合格。

## 已知误差

转写的**数字和年份基本可信**，**专名成系统错**（`Halifax → halififax`、`Nova Scotia → novava scotia`）。要上屏的人名地名必须核。

补 `data/hotwords.json` 只对**新转写**生效；已有稿子要跑 `facts.py <job_id> --recorrect`。细节与三个踩过的坑见 `SELFUSE.md`。
