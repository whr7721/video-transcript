# 拾文开发路线与接手地图

归档日期：2026-10-30；清零单起点 `cf17db7`（最新实现提交见Git历史）。拾文是 **Windows 本地优先的个人多媒体阅读工作台**：链接/文件→字幕优先或本地转写→整理、导图、检索、追问、笔记与导出。当前主线是私有 `app.py`；旧 `app_core.py` 白名单客户版冻结，云端 `cloud/` 是独立 TypeScript 实现，不能当作本地 Python 的部署开关。最新审查报告记载 A–H 已关单；随后平台扩展与归档经用户转达审查通过；清零四项实现待独立审查；关单不等于下文人工/外部条件全部验收。证据：[AGENTS.md](AGENTS.md)、[最终说明](FINAL_SPRINT_GUIDE.md)、[Git 历史](#时间线)。

## 目录

1. [时间线](#时间线)：P0 → Web/登录/批量/首页/订阅 → A–H → 平台扩展
2. [架构地图](#架构地图)：入口、身份、任务、引用和会话
3. [红线与边界](#红线与边界)
4. [测试与验收](#测试与验收)
5. [未验项与挂账](#未验项与挂账)
6. [接手步骤](#接手步骤)

## 时间线

下列路径相对仓库根目录。`runtime/` 被 Git 忽略：审查报告与真实验收素材必须随本机交接备份；仅克隆仓库不保证拿到这些文件。旧 GUIDE 保留当时状态，状态冲突以最新审查报告及用户裁决为准。证据：[AGENTS.md](AGENTS.md)、[RESEARCH_DECISIONS.md](RESEARCH_DECISIONS.md)。

**前置基础（P0 之前）**：已有不可变转写原稿、版本化编辑稿、manuscript 完整稿/精华/金句、章节、专题检索、文章/OCR、个人资料助手和图文排版。用户从商业化探索调整为“自用完全体优先”，并保留未来白名单收费交付路径；没有要求本地所有能力都搬云端。思维导图已由 `dead319/23931ac` 合入，后续备份只参考离线 HTML，不能再当作未合入代码覆盖。证据：[CLI_SUMMARY_GUIDE.md](CLI_SUMMARY_GUIDE.md)、[PERSONAL_AI_GUIDE_20261028.md](PERSONAL_AI_GUIDE_20261028.md)、[MINDMAP_MILESTONE_20261027.md](MINDMAP_MILESTONE_20261027.md)、[cloud/LAUNCH_20261028.md](cloud/LAUNCH_20261028.md)。

**P0 链接 CLI（`cd506e5`，P1 修复 `81a4965`）**：用户要求 `shiwen add` 统一 YouTube/B站/RSS/抖音；字幕优先，无字幕下载音频后用现有多语言 SenseVoice，解锁语言配置而非加第二模型。JSON 对齐 `subtitlesArray[{startTime,end,text,index}]`，补 cover/duration/publishedDate；抖音只读复用原登录态。审查发现路径硬编码与缺 Deno，随后参数化 `SHIWEN_DOUYIN_PROFILE`、补 Deno/EJS；用户确认 P0 关单。说话人分离不做，原 P2/P3 见挂账。证据：[P0_LINK_GUIDE.md](P0_LINK_GUIDE.md)、[P0 审查](runtime/review-20261028/REVIEW-288c3c2..cd506e5.md)、`runtime/p0-link-20261028/`。

**CLI 整理闭环（`6ee9274`）**：用户要求转写后串联三层整理与导图，`--summarize` 一次整理两次共享请求，五段式精华并入精华层；固定 D3/Markmap 版本内嵌，输出 summary.md/mindmap.html。阶段缓存支持只补失败阶段，transcript.* 字节保持不变；离线导出不再调用模型。审查通过，遗留折叠等人工点验不冒充已完成。证据：[CLI_SUMMARY_GUIDE.md](CLI_SUMMARY_GUIDE.md)、[审查](runtime/review-20261028/REVIEW-81a4965..6ee9274.md)。

**Windows 客户安装包（`e2d7620`）**：用户要求新机器一键安装、申请 AI Key 图文步骤、离线导图与卸载；选择 app_core 白名单避免私有采集混入。复用 uv 管理包内 Python、ffmpeg/Deno、固定模型校验，模型按需下载。审查关单；后续用户冻结旧客户 ZIP，仅 G 明确恢复私有 full 变体。真另一台 Windows 仍不同于同机隔离冷装。证据：[PRIVATE_DELIVERY_20261029.md](PRIVATE_DELIVERY_20261029.md)、[审查](runtime/review-20261029/REVIEW-6ee9274..e2d7620.md)、`private_delivery/`。

**Web 链接输入（`e3c5b86`）**：用户要求私有网页四平台，CLI/Web 共用链路，客户入口仅 YouTube/RSS；抽 link_ingest，采用显式适配器注册，替代打包时 AST 删分支。异步 link_jobs 记录阶段，缓存复用既有成果；隔离旧 organizer/队列，避免接管链接任务。审查关单，包含真实 GUI/手机双态及四平台文档验收。证据：[WEB_LINK_MILESTONE_20261029.md](WEB_LINK_MILESTONE_20261029.md)、[审查](runtime/review-20261029/REVIEW-e2d7620..e3c5b86.md)。

**B站登录快路（`d0396d2`）**：匿名字幕常为空，用户要求扫码→本地 Cookie→nav.isLogin 验证→带认证探针，失败继续匿名/ASR回落。Playwright 专属 profile、Windows DACL、CDN 零 Cookie、登出 epoch 防重写；不动外部采集器登录态。真实字幕快路对照提速12.1倍，审查关单。B站 POSIX 权限仍未实测，不能用 H 的会话锁测试代替。证据：[BILIBILI_LOGIN_GUIDE.md](BILIBILI_LOGIN_GUIDE.md)、[审查](runtime/review-20261029/REVIEW-e3c5b86..d0396d2.md)。

**批量队列（`47e7ac9`）**：用户要求混合多链接、限并发、导出，预览必须显示约2×N请求与日额度不足提示。采用引用式批次，复用单项任务；全局并发1、轮转派发、暂停/继续与重启恢复，ZIP带缺失清单。审查关单；手机页截图由 H 补，真实 RSS 选集等交互仍按证据边界判断。证据：[BATCH_QUEUE_GUIDE.md](BATCH_QUEUE_GUIDE.md)、[审查](runtime/review-20261029/REVIEW-d0396d2..47e7ac9.md)。

**首页产品化与视觉（`bfac712` → `d16bba4`）**：用户要求输入优先、最近文稿、轻导航；用路由隔离 localStorage 自动恢复，保持文档工作台内部功能。随后按实测72px标题、一体输入栏及 Lab 色值复刻形态，文案/素材自写；用户纠正“金黄”为数值实际玫红。两单审查关单，透明 body 的 P3 视觉无影响。证据：[HOME_ENTRY_GUIDE.md](HOME_ENTRY_GUIDE.md)、[入口审查](runtime/review-20261029/REVIEW-47e7ac9..bfac712.md)、[视觉审查](runtime/review-20261029/REVIEW-bfac712..d16bba4.md)。

**订阅/Feed与即时展开（`b6db2cc`）**：用户修正“方式与源分离”：频道/主页/话题可以临时展开，RSS/YouTube/B站/抖音博主用于持续订阅；一个枚举适配器供两个入口。发现只存元数据，提取才进 link_jobs/link_batches；稳定 ID 去重、发现序号已读游标、RSS GUID+单集快照避免退出 Feed 后串集；抖音与提取互斥并限速。两条抖音选5链实测，静音条目真实失败后换条，不伪造成功。审查关单，话题持续追踪与 POSIX 锁后由 H 补。证据：[SUBSCRIPTIONS_GUIDE.md](SUBSCRIPTIONS_GUIDE.md)、[审查](runtime/review-20261029/REVIEW-d16bba4..b6db2cc.md)、`runtime/feed-20261029/`。

**A 资料库（`461c04f`）**：用户要求跨库全文搜索、收藏、合集排序/ZIP、统计。复用中文双字切词与 SQLite FTS5；独立派生索引不改已审专题索引统计，收藏/合集只保存引用，抽出公共 ZIP writer。301后端/82前端与构建通过；后由 H 补常用中英词查询扩展。证据：[LIBRARY_CHAT_SKILL_GUIDE.md](LIBRARY_CHAT_SKILL_GUIDE.md)、[A–C 合并审查](runtime/review-20261029/REVIEW-b6db2cc..3b19115.md)。

**B 文档追问（`d593a62`）**：用户要求按篇持久化、多轮、强引用、长文检索而非全塞。复用 A 检索，先限 UID/原文再排名；摘要/历史只导航，逐字引文校验、原稿变化拒绝、请求 ID 去重，复用 request_json/日额度及费用账本。306/84与构建通过，真实模型0调用；引用存在不证明语义质量，真实回答质量仍待用。证据：[LIBRARY_CHAT_SKILL_GUIDE.md](LIBRARY_CHAT_SKILL_GUIDE.md)、[A–C 合并审查](runtime/review-20261029/REVIEW-b6db2cc..3b19115.md)。

**C CLI 技能（`0054212`，文档 `3b19115`）**：用户要求 summarize/commands、--chapter/--json、Codex/DSH本地安装。继续复用原转写/整理/章节缓存，costDuration明确是耗时秒数；技能全自写、单一 canonical 源打包，无 MCP/OAuth。309/84与构建通过，解包加载/销毁及隔离安装验证；A–C报告合并关单，DSH真实宿主仍未验。证据：[skills/shiwen/SKILL.md](skills/shiwen/SKILL.md)、[说明](LIBRARY_CHAT_SKILL_GUIDE.md)、[审查](runtime/review-20261029/REVIEW-b6db2cc..3b19115.md)。

**D 笔记/导出（`4850684`）**：用户要求多笔记、段落/时间锚点、Obsidian直写、可选Notion。独立版本表不改原稿；vault模板白名单并保护外部手改文件；Notion token沿用本机加密，明确点击才上传。312/85与构建通过，Notion仅契约测试。证据：[FINAL_SPRINT_GUIDE.md](FINAL_SPRINT_GUIDE.md)、[D–G审查](runtime/review-20261029/REVIEW-DEFG-4850684-79f05b7.md)、`runtime/final-sprint-20261029/D-*.txt`。

**E 分享快照（`b564bfa`）**：用户要求不部署、可直接发人的自包含只读 HTML。复用内嵌 Markmap，文稿/时间轴/摘要/笔记转义，导图条件显示，不自动付费补生成。314/85与构建通过；独立审查离线零请求，HTTP502由 H 复现为环境代理触发，直连生成/下载200。证据：[说明](FINAL_SPRINT_GUIDE.md)、[D–G审查](runtime/review-20261029/REVIEW-DEFG-4850684-79f05b7.md)、`runtime/final-sprint-20261029/H-http.json`、`H-browser.json`。

**F 视觉分析（`30775b2`）**：用户要求默认30秒抽帧、最多30帧、中文描述和时间轴对照。免费抽帧与付费描述分离；复用既有视觉请求/预算，每帧缓存，失败显式续跑。317/87与构建通过，真实视觉2次、重复额外0次；局部采样不是整段视频理解，不做全文OCR/画面搜索。证据：[说明](FINAL_SPRINT_GUIDE.md)、[D–G审查](runtime/review-20261029/REVIEW-DEFG-4850684-79f05b7.md)、`runtime/final-sprint-20261029/F-live-acceptance.json`。

**G 全量包（`79f05b7`）**：用户明确恢复 --full/--offline-full 私有变体，不升级旧core。full_env注入包内路径，仅带客户端代码/许可、不带外部config或登录态；复用工具锁与模型校验，离线带Python/wheel/Chromium/工具/模型。修复漏web、ROOT/data和uv次版本链接便携问题。320/87与构建、两种真实隔离安装通过；约848MiB离线包适合网盘/U盘，另一台Windows未验。证据：[说明](FINAL_SPRINT_GUIDE.md)、[D–G审查](runtime/review-20261029/REVIEW-DEFG-4850684-79f05b7.md)、`runtime/final-sprint-20261029/G-*.txt`。

**H 清偿（`fdce3d6`）**：用户要求第五源话题订阅、本地中英扩展、390截图、POSIX锁及挂账处置。纯文字须确认；复用ID集合去重、仅手动检查；常用术语表查询扩展不改原文、不用翻译API。324/87与构建通过；WSL Ubuntu24.04 Python3.12实跑3项锁测试；三页390无横向溢出，真实话题重复检查无重复ID。仓库最终报告记载 H通过、D–H收官；不能扩张为所有旧人工质量项已清。证据：[H最终审查](runtime/review-20261029/REVIEW-H-final.md)、[说明](FINAL_SPRINT_GUIDE.md)、`runtime/final-sprint-20261029/H-*.json`、`H-posix.txt`、`mobile-*-390.png`。

**平台扩展（`2f25559`）**：用户要求先A原生TikTok/X，再B小宇宙/Spotify单集，再C小红书，最后归档。A复用yt-dlp字幕优先，别名规范化、文本推文明确拒绝；B自写公开页面解析复用RSS音频链，不拿Spotify预览冒充完整；C实施前确定自写会话/API/媒体编排，仅复用MIT xhshow签名，避免引入完整爬虫依赖。小红书沿用DACL/epoch、API白名单与CDN零Cookie，图文复用本地OCR；笔记ID+语言缓存、分享令牌可刷新重试。334后端/87前端与构建通过；小宇宙179秒、小红书视频/图文真实出稿，混合批量3/3缓存完成，0付费调用。TikTok/X无代理且直连失败、Spotify实测RSS降级；粤语样本错字明显，未声明模型质量通过。五个新平台只扩单条/批量，不扩订阅枚举；core冻结、历史ZIP不重建。证据：[说明](PLATFORM_EXTENSION_GUIDE.md)、[实现审查请求](runtime/platform-extension-20261030/REVIEW-REQUEST.md)、`runtime/platform-extension-20261030/`。用户随后转达两段通过关单，证据：[平台最终审查](runtime/review-20261030/REVIEW-bbc4d08..cf17db7.md)。

**清零四项（本单）**：用户补充并确认说话人分离/XMind/合集聚合摘要/频道字段范围。复用sherpa离线API，默认中英CAM++一个embedding+INT8分段；普通/分离缓存隔离，新增speaker标签不改文字；XMind由同树零调用转换，分享内嵌、CLI JSON返回路径；合集按指纹缓存与长文map/reduce，失败保留旧摘要，ZIP含成果；频道只记录已有平台值。双人样本自动/指定人数一致、XMind在线查看器实际打开、三篇合集真实2次调用及缓存、频道筛选已测，340/87与构建通过。复杂声音质量/新控件人工点验/更新离线种子真安装保留。证据：[说明](ZERO_GAP_GUIDE.md)、[审查请求](runtime/zero-gap-20261030/REVIEW-REQUEST.md)、`runtime/zero-gap-20261030/`。

## 架构地图

```text
shiwen.py / app.py → link_ingest → 显式平台适配器 → transcript_stage / transcribe
                         ↑              ├─ link_private → pipeline → extractor
                         │              ├─ platform_urls / yt-dlp：TikTok、X
                         │              ├─ podcast_pages：小宇宙、Spotify完整音频或RSS提示
                         │              └─ xhs_ingest → xhs_auth / 本地ASR / image_documents(OCR)
Web单条 → link_jobs ─────┘                              ↕ douyin_session_guard
批量 → link_batches → 引用既有 link_jobs              session → 隔离profile
         ↑
source_expand ← source_enumeration → subscriptions → channels / feed_items

store(SQLite + jobs文件) → documents(版本稿/来源) → organizer / manuscript / mindmap
                         → library(派生FTS/收藏/合集) → document_chat(单篇证据)
                         → document_notes → Obsidian / Notion
                         → share_snapshot → 单文件HTML
                         → video_frames → ffmpeg → 既有视觉client/费用账本
build_customer_package --full → build_full_package → full_delivery / full_env
```

| 模块 | 职责与不可丢失的设计 |
|---|---|
| `link_ingest.py` / `link_private.py` | CLI/Web公共接入；注册制决定能力，不复制两套提取代码、不用AST删分支。 |
| `diarization.py` / `setup_speakers.py` | 可选本地说话人聚类与固定指纹模型；按重叠时长标段，不识别人名、不篡改识别文字。 |
| `xmind_export.py` / `collection_summary.py` | 同树XMind转换；合集分层归纳、来源引用、阶段缓存和过期检测，复用原配额。 |
| `platform_urls.py` / `podcast_pages.py` | 别名规范化、公开单集完整音频解析；无直链/DRM/预览降级RSS，不造字幕。 |
| `xhs_auth.py` / `xhs_ingest.py` | 自有扫码会话、固定API认证、笔记ID缓存；签名用MIT xhshow，媒体无Cookie，图文复用本地OCR。 |
| `link_jobs.py` / `link_batches.py` | 单项执行与引用式批次；串行/轮转、阶段记录、重启恢复；批次不复制内容。 |
| `source_enumeration.py` / `source_expand.py` | 一套元数据枚举服务即时展开和订阅；发现不等于下载/整理。 |
| `subscriptions.py` | 源及Feed持久化；稳定内容ID、发现游标、RSS快照，避免按旧序号串集。 |
| `store.py` / `documents.py` | 所有运行数据按SHIWEN_DATA_DIR隔离；原稿保留，编辑稿版本化。 |
| `organizer.py` / `cli_summary.py` | 共享请求额度；成功阶段缓存、失败不损原稿；缓存身份包含来源/语言/模型或提示版本等实际相关字段，改字段前读各模块指纹。 |
| `session.py` / `douyin_session_guard.py` / `bilibili_auth.py` | 只读来源会话→owned profile；抖音跨进程互斥/冷却，B站nav验证、受限Cookie流向。 |
| `library.py` / `topic_search.py` / `query_expansion.py` | 派生词法索引与本地查询扩展；不得破坏篇/专题范围，词法召回不是通用语义翻译。 |
| `document_chat.py` | 只依据本篇实际检索片段；历史/摘要非原文证据，逐字引用校验不等于语义证明。 |
| `document_notes.py` / `share_snapshot.py` | 笔记版本/锚点与显式导出；保护vault外部编辑，分享只用已有成果且离线自包含。 |
| `video_frames.py` / `experiments/vision/client.py` | 抽帧与视觉调用分开，逐帧缓存、上限与预算；不把采样当完整理解。 |
| `build_full_package.py` / `full_delivery/` | 代码/运行时允许列表式交付，路径注入及便携自检；不打包数据/凭据。 |

证据：上述源码、[RESEARCH_DECISIONS.md](RESEARCH_DECISIONS.md)、[SUBSCRIPTIONS_GUIDE.md](SUBSCRIPTIONS_GUIDE.md)、[FINAL_SPRINT_GUIDE.md](FINAL_SPRINT_GUIDE.md)。

## 红线与边界

- **用途**：full带MediaCrawler片段，受其NON-COMMERCIAL LEARNING LICENSE约束；仅自用/非商业学习分享，不能把付费安装/1对1服务包装成已获商业授权。收费交付需无该代码的白名单路径或另取权利人授权；旧白名单包当前冻结。证据：[D–G审查](runtime/review-20261029/REVIEW-DEFG-4850684-79f05b7.md)、`vendor/mediacrawler/LICENSE`（解包后）、[FINAL_SPRINT_GUIDE.md](FINAL_SPRINT_GUIDE.md)。
- **数据**：登录态、Key、用户材料、数据库、模型和运行日志不入Git；登录态永不入任何安装包。外部MediaCrawler/meme-lab配置、登录态、锁及定时任务不改；允许的是经授权只读复用与自有隔离副本。证据：[AGENTS.md](AGENTS.md)、`session.py`、`build_full_package.py`。
- **审查**：实现方不自行宣布通过。每个里程碑验证后提交，交ZCode独立审查，用户裁决；P0/P1修后才继续，P2/P3登记。用户已授权连续实施时不额外索要重复确认。证据：[AGENTS.md](AGENTS.md)、`runtime/review-*/`。

## 测试与验收

在仓库根目录 PowerShell 运行（前端依赖已安装；pytest使用既有隔离工具目录）：

```powershell
$env:SHIWEN_DATA_DIR = "$PWD/runtime/<本次任务>/test-data"
$env:PYTHONPATH = "$PWD/runtime/public-quota-tools"
.venv/Scripts/python.exe -m pytest tests --ignore=tests/test_customer_package.py --ignore=tests/test_distribution.py -q
npm.cmd --prefix frontend test -- --reporter=dot
npm.cmd --prefix frontend run build
# POSIX真实锁测试（已安装WSL Ubuntu-24.04时）
wsl.exe -d Ubuntu-24.04 --exec env SHIWEN_DATA_DIR=/mnt/d/zcode1/video-transcript/runtime/<本次任务>/posix PYTHONPATH=/mnt/d/zcode1/video-transcript python3 -m unittest tests.test_douyin_session_guard -v
```

上例WSL路径需改成本机仓库位置；全量排除的是冻结旧客户包测试，**包含**新test_full_package。若隔离pytest目录缺失，先在runtime工具环境准备pytest，勿把开发依赖塞进生产环境；旧unittest discover不覆盖所有pytest函数。当前清零单基线340后端/87前端与构建通过；H阶段另有POSIX3项实跑证据。文档归档不需要重新跑模型或重复构建。证据：`runtime/zero-gap-20261030/backend.txt`、`frontend-final.txt`、`build-final.txt`；`runtime/final-sprint-20261029/H-backend.txt`、`H-frontend.txt`、`H-build.txt`、`H-posix.txt`。

每次真实验收先设置隔离目录，再启动进程；本地HTTP用 `httpx.Client(trust_env=False)` 或正确NO_PROXY，防止代理假502。证据放 `runtime/<任务日期>/`：命令日志、API结果、截图、费用次数、原稿前后字节对比；审查放 `runtime/review-<日期>/REVIEW-<区间>.md`。测试/HTTP/浏览器/人工语义分别报告，不能互相冒充。真实付费须遵守当单预算；本周期D–H仅F视觉2次，失败预留不抹账。证据：[AGENTS.md](AGENTS.md)、`runtime/final-sprint-20261029/F-live-calls.json`、`H-http.json`。

## 未验项与挂账

以下合并AGENTS处置段及最终审查，不把历史条目的旧“待验”机械重开：

| 状态 | 项目及继续条件 | 证据 |
|---|---|---|
| 已清 | B站认证字幕快路；跨进程POSIX锁；三页390布局；离线分享零请求；代理502原因；离线体积说明 | B站审查、H最终审查、H-http/H-browser/H-posix、FINAL_SPRINT_GUIDE |
| 外部条件 | Notion真实integration/父页面权限；另一台Windows、无代理网络、离线包真设备；DSH真实宿主加载 | FINAL_SPRINT_GUIDE、LIBRARY_CHAT_SKILL_GUIDE、AGENTS |
| 云端留存 | 原生上传/登录、自然录音、手机/iOS/离线导出、30天Cron与账单；用户已确认Auth配置，不等于上述已验 | cloud/LAUNCH_20261028.md、AGENTS |
| 人工质量 | 自然长音频头中尾听校、术语/数字；OCR净化/图解/原图阅读与标签（用户暂停）；AI研究引用/推论、行动计划可行性；追问真实回答质量 | AGENTS、IMAGE_EDITORIAL_MILESTONE_20261026、PERSONAL_AI_GUIDE_20261028、KNOWLEDGE_PROJECTS_20261028 |
| 专项GUI | 上传中文文件名、RSS/R2章节、专题搜索/图文选择高亮/键盘IME、深入与导出、导图完整中文PNG/大图/触控等尚无最终人工证据者保留；Web链接与首页已有独立GUI审查，不再泛称全未验 | AGENTS、Web/首页审查、MINDMAP_MILESTONE_20261027 |
| 新平台外部条件 | TikTok/X可用代理真链；Spotify完整公开音频正向；xhslink真实短链及新设置GUI；粤语配乐识别稿需人工听校 | PLATFORM_EXTENSION_GUIDE、runtime/platform-extension-20261030/ |
| 平台观察 | 话题图文排除依赖平台标记；真实RSS批量选集交互；B站POSIX Cookie权限分支（H只测会话锁） | Feed/批量/B站审查 |
| 既有P2/P3 | 自动字幕语言排序、429提示/退避、HTTP升级、产物language溯源、混语言recognizer性能；公开core其他action/chapter-jobs保护范围不扩大 | P0审查、AGENTS；B站可选Cookie已由后单解决 |
| 接受风险 | K1共享FTS BM25统计漂移，按用户已接受决定保留，范围过滤仍必守 | AGENTS K1条目 |
| 另立需求 | 定时轮询/推送；在线分享/访问控制、跨篇对话、MCP/OAuth、macOS/Linux安装包等不在本周期承诺内 | 各阶段GUIDE、AGENTS |

这些是继续条件，不是要求下一位开发者未经用户指令把所有方向一起实现。证据：[AGENTS.md](AGENTS.md)、[H最终审查](runtime/review-20261029/REVIEW-H-final.md)。

## 接手步骤

1. **先读**本文件→AGENTS→对应GUIDE→最新审查→RESEARCH_DECISIONS；核对 `git status --short` 和 `git log --oneline`。`HANDOVER_20261026.md`、`.playwright-cli/` 等外部未跟踪内容不要随手清理。缺runtime证据时请求本机备份，不能补造结论。
2. **再定位**用户任务属于入口/发现/执行/内容/导出/分发哪层，沿上图复用现有模块；新功能按用户长期偏好先外部调研、做适量方案，再遵守当次确认或直接实施授权。不要从产品相似就复制素材/第三方受限代码。
3. **隔离后验证**：创建本次runtime目录，显式设SHIWEN_DATA_DIR；只重启自己确认拥有且空闲的服务，不盲用旧端口。先跑与改动相称的检查，按用户要求跑全量；默认模拟付费调用，不自动重复真实模型验收。
4. **交付**：保存证据→更新GUIDE/决策/挂账→明确文件暂存→提交并核对私有远程后推送→出含区间、意图、测试、未验项的审查请求。不要把此档案当运行时保证，也不要把已关单阶段重新宣布“待审”。

证据入口：[AGENTS.md](AGENTS.md)、[RESEARCH_DECISIONS.md](RESEARCH_DECISIONS.md)、[最终使用说明](FINAL_SPRINT_GUIDE.md)、[新平台说明](PLATFORM_EXTENSION_GUIDE.md)、[源码入口](app.py)、[CLI入口](shiwen.py)。


# 附录：历史验收状态记录（2026-10-19 → 10-30，自旧 AGENTS.md 迁入）

以下为按日期累积的验收流水，仅作历史查询，不再更新；当前未验项以上方清单为准。

---

# 交付范围（2026-10-29用户更新）

- 原客户core白名单包继续冻结；用户最新G单明确授权构建/验收 --full 与 --offline-full 私有全功能变体，自用app.py为主线。仅G单恢复全功能打包，不将旧白名单商业包顺带升级。

# 版本管理约定

- 每完成一个里程碑，验证后创建一次 Git 提交。
- 提交信息明确说明该里程碑完成的功能、修复或文档变更，避免含糊描述。
- 不提交 API 密钥、登录态、用户素材、运行数据库、模型权重、日志或依赖目录。
- 推送前检查暂存区和目标远程仓库；GitHub 仓库默认保持私有，除非用户明确要求公开。
- 外部依赖变更（新增包、模型、外部接口）在提交信息中显式列出。

# 审查制衡（2026-10-20 起）

角色分工：Codex 负责实现与方案；ZCode（review-agent 技能）负责缺陷审查；用户负责转达与裁决。**写码方不自行宣布审查通过。**

- 里程碑提交后，向用户输出一段**审查请求**：改动范围（commit 区间）、意图、已知风险与未验证项。
- 等待审查结果期间可继续无关工作，但不得修改被审查范围内的代码。
- 审查结果以 P0-P3 分级返回：P0/P1 必须修复并提交后才进入下一里程碑；P2/P3 记录排期。对某条意见有异议时写明理由交用户裁决，不静默忽略。

# 完成声明纪律

- 任何"已完成 / 已通过 / 已验证"的表述必须附证据：测试输出、实测数据或命令结果。
- 接口返回成功不等于质量通过；未做真实联调的功能不得报告为已验证；模型自评不能替代人工或工具核验。
- **长期挂账项引用制（2026-10-22 起）**：已知的、等待外部条件的验收债在下方清单登记一次即可；里程碑文档用一行引用（如"人工验收挂账见 AGENTS.md，本轮无变化"），不逐轮整段复述。登记项有进展或恶化时更新清单。底线不变：挂账未清前，相关能力仍不得声称已验证。

## 当前登记的长期挂账

- Windows客户交付（2026-10-29）：runtime干净解压安装、包内Python/工具/模型、本地音频与两请求整理、Web设置Key和卸载已实测；真实新Windows、客户无代理网络、完整缓存断网安装与图文说明/离线导图视觉点验待用户解包验收。macOS/Linux不在本轮范围，见PRIVATE_DELIVERY_20261029.md。

- 云端 MVP（2026-10-28 更新）：已部署 Pages + 私有 Worker Service Binding + Supabase，两个临时真实 Auth 会话、5分钟合成中文转写、真实摘要/导图及分享撤销通过；原生浏览器上传/登录、自然录音质量、手机/iOS/离线导出、首30天每日 Cron 与账单仍待验收。用户需完成 Auth URL 与自己的体验账号配置。证据见 cloud/LAUNCH_20261028.md，不把 API 夹具当页面验收。

- K1收官的接受风险（2026-10-25）：用户转达K1-P统一审查通过、无发现；共享FTS的BM25统计漂移记录在案、不处理。不把它自动升级为后续开发任务，跨专题内容过滤仍须维持。

- K1-P 专题搜索人工点验（2026-10-25）：Chrome 已通过 computer-use 启动，但 get_window_state 因无法可靠确定当前浏览器 URL 被工具停止，未继续输入。46项前端组件测试不替代真实视觉/键盘/中文输入法验收。隔离无Key预览在8775，验收专题明确标为夹具；原8765/8772/8774服务未重启。本轮待用户点验，不扩大宣称已验证。

- 人工验收（2026-10-22 更新）：拾文本体界面、key 设置、深入/研究面板、M1 发现界面**均已经用户点验**（2026-10-20/21）；触屏不适用（本机桌面工具）。V1-C 新增的文件上传界面（含中文文件名上传）及R1新增RSS界面、R2章节导航/生成/范围调整/按章整理待点验。浏览器工具本轮仍无可操作窗口，DOM/HTTP测试不替代点验。
- V1-D 独立部署与无代理机器模型下载实测：用户确认暂时没有另一台电脑（2026-10-22），先完成可交付部分。新下载器已在开发机真实直连下载并通过固定指纹校验，但不替代独立无代理机器验收。状态：待外部环境，验收表随包提供。
- V1-D 长素材质量：真实两小时冷缓存处理、编辑/笔记/导出/重启已实测；头中尾回听片段与对应识别稿已自动准备，尚无人逐段听校和记录术语差错。状态：待人工听校，不声明准确率通过。

# 数据红线

- CLI整理（2026-10-28）：两次真实请求及缓存零调用、失败保留原稿/只补失败阶段已验证；用户明确浏览器真实验收交给ZCode，不再排查插件。样例与证据见CLI_SUMMARY_GUIDE.md，不把资源内嵌/脚本语法检查当GUI通过。

- P0 链接审查后续（2026-10-28）：审查报告 runtime/review-20261028/REVIEW-288c3c2..cd506e5.md 的 P2/P3 暂缓：自动字幕语言排序、429退避/提示、B站可选用户cookie、HTTP升级、产物language溯源、混语言recognizer重建性能。本次只修两项P1并补测YouTube，不将其余意见静默视作结清。

- P0 说话人分离（2026-10-28）：用户明确本轮不做，后续另立需求；当前只提供字幕/语音段时间轴，不宣称识别发言人。

- 转写原稿、编辑稿、专题笔记属于用户内容，代码改动不得使其被动变更或丢失。
- 开发夹具、mock 及交互实验必须在启动进程前显式设置 SHIWEN_DATA_DIR 到 runtime 下的隔离目录；不得写入默认真实 data 库。

# 调研落地与经验沉淀（2026-10-21 用户要求）

- 每轮调研都要结合本站现状：指出解决的问题、可复用部分、对应模块/数据/交互、集成成本与验证方式，不能只有工具链接或功能列表。
- 在 RESEARCH_DECISIONS.md 追加或更新采用/候选/暂缓/已否定的决策及证据。假设、仓库声明、本机实测和用户验收分别标明。
- 记录无效尝试、未通过的对照和边界条件，供后续复用；不把用户原文、密钥或运行数据库提交进经验文档。

- 图文入口人工点验（2026-10-26）：本轮Computer Use因无法可靠判断Windows浏览器URL停止，未继续GUI输入；51项组件测试及真实HTTP不替代原图区域、高亮、键盘和中文输入法点验。自用原资料入口8765，操作见IMAGE_IMPORT_GUIDE.md。

- OCR净化阅读（2026-10-26）：工程验证205后端/53前端测试及真实导出/搜索HTTP通过；本轮无可用浏览器操作工具，净化正文/按页侧栏/标注入口仍待用户视觉和键盘点验。用户已同意先确认10—20个人工标签；未确认前不宣称净化质量指标通过。证据与边界见OCR_READING_PROGRESS.md。

- 图文阅读优先级更新（2026-10-26）：用户要求便利优先且按实测决策，人工标注暂停。默认整份AI整理稿/精华已接入；209后端/55前端测试与真实生成不替代用户的阅读质量、视觉/键盘验收。旧原图/OCR和标注资料保留，原挂账不宣称结清。见IMAGE_EDITORIAL_MILESTONE_20261026.md。

- 思维导图人工验收（2026-10-27）：用户明确“验收我来”。拖拽/缩放/折叠、大图、移动布局与完整中文 PNG 待用户页面点验；组件、结构化模型生成与 HTTP 验证不替代该验收。隔离无 Key 预览 8776，证据见 MINDMAP_MILESTONE_20261027.md。

- 个人AI资料助手（2026-10-28）：6次隔离真实研究已验证工具链，模型引用/推论仍须人工核验；GUI、中文输入与导出由自用点验确认，不把65项前端测试当视觉通过。20元独立预算账本未重置旧记录，实测与边界见PERSONAL_AI_GUIDE_20261028.md。

- 资料任务工作区（2026-10-28）：真实隔离研究/采用/进度保存已联通；完成状态由人记录，计划可行性和页面点验仍待自用，不宣称Agent自动执行。详情KNOWLEDGE_PROJECTS_20261028.md。

- Web链接入口（2026-10-29）：四平台真实隔离转写/字幕到文档API及缓存已测；B站登录字幕快路已于后续单经用户扫码实测（BV1GJ411x7h7，1.819秒、47段、无下载/ASR），旧快路挂账解除，见BILIBILI_LOGIN_GUIDE.md。浏览器交互及手机输入态/结果态截图交ZCode。证据见WEB_LINK_MILESTONE_20261029.md；不把单测/HTTP当GUI验收。

- 引用式批量队列（2026-10-29）：真实混合四平台完成、全局执行不重叠、部分成果ZIP及跨批缓存已测；runtime额度用尽夹具验证等待整理、原稿不变及真实服务重启暂停。浏览器交互与手机点验交ZCode，见BATCH_QUEUE_GUIDE.md。客户包继续冻结；未做新的真实付费摘要调用。

- 输入优先首页（2026-10-29）：前端入口隔离旧文稿自动恢复，79项前端测试及构建通过；首页缓存链接→文档的真实浏览器交互与手机首屏截图交ZCode，见HOME_ENTRY_GUIDE.md。后端与正式服务未修改/重启，客户包仍冻结。

- 订阅与来源展开（2026-10-29）：四源真实检查、主页/话题各选5转写、RSS历史快照、缓存引用/已读重启保存已测；104后端/81前端与构建通过，GUI/手机交ZCode，POSIX锁未实测。见SUBSCRIPTIONS_GUIDE.md；客户包冻结，无新增付费调用，独立审查待提交。

- 资料库/单篇追问/CLI技能（2026-10-29）：A301后端82前端、B306/84、C309/84与各次构建通过；8782自用隔离预览已空闲重启，HTTP搜索/收藏/合集排序ZIP/拒答持久化与原稿不变通过。真实LLM0次，模型回答质量/GUI手机/DSH真实宿主加载待验收；技能runtime安装、打包解包加载与格式校验通过。见LIBRARY_CHAT_SKILL_GUIDE.md；本轮合并独立审查待转交，不自行关单。

## H挂账处置（2026-10-30）

- D/E/F/G：用户转达runtime/review-20261029/REVIEW-DEFG-4850684-79f05b7.md通过关单。
- 已清：POSIX锁WSL真实3测试；批量/订阅/资料库390截图与无横向溢出；分享HTTP502确认环境代理触发，直连200、离线外部请求0；离线包约848MiB交付说明补齐。
- 已实现待终审：话题第五源、双向本地术语检索。
- 保留外部条件：Notion真实凭据、真实新Windows/无代理客户网络、云端原生上传/登录/iOS/长期账单。不能用同机安装替代真设备验收。
- 保留人工质量：长音频逐段听校、人名术语、OCR/原图阅读语义、研究引用含义、模型追问质量、触屏/中文输入法、导图PNG完整中文与大图交互；本轮只做三页截图及离线文件，不自动结清其他GUI。
- 保留范围决定：core公开防刷其他action、自动字幕排序/429/HTTP升级/混语言性能等原P2/P3不顺带修改；B站cookie快路已由前单解除，旧清单该项不再当未实现。说话人分离、自动订阅轮询/推送仍属另立需求。pytest函数测试用现有隔离pytest全量运行，unittest discover不代表全套，未为此改变生产依赖。
- 旧阶段条目保留历史证据，当前状态以本节为准，未把人工/外部条件伪装清零。


## 平台扩展验收状态（2026-10-30）

- 小宇宙179秒单集、小红书视频/图文均在runtime隔离真实出稿，混合批量3/3缓存完成；0付费调用。小红书扫码由用户确认，未迁移到真实data。
- TikTok/X无HTTPS_PROXY且直连失败，等待可用代理；Spotify真实单集已验证RSS降级，完整公开音频正向样本未验；xhslink真实短链正向与新设置GUI待验。粤语配乐样本错字明显，不宣布ASR质量通过。见PLATFORM_EXTENSION_GUIDE.md及runtime/platform-extension-20261030/。
- 新XHS认证/API自写，签名用MIT xhshow；Cookie/API受限、CDN无Cookie、Windows DACL与epoch；原core冻结、历史full ZIP未重建，本次同步构建源码/依赖。独立审查待用户转交，不自行关单。


## 最新收尾状态（2026-10-30）

- 平台扩展/归档：用户转达runtime/review-20261030/REVIEW-bbc4d08..cf17db7.md两段通过关单；保留G包下次交付前重建、xhslink真实短链样本两项P3。
- 清零单本次明确授权说话人分离，覆盖旧P0“另立需求”状态：自动/指定人数真实双人样本、SRT标签已测，非多人复杂会议质量结论。XMind在线查看器已打开；三篇合集真实聚合2次调用（首次引用格式拒绝）、缓存零新增；频道筛选单测通过。见ZERO_GAP_GUIDE.md。
- 清零单独立审查待转交；新控件GUI点验、更多说话人/重叠语音人工质量、更新full模型后真实离线重装未验。core仍冻结，历史G包未重建，旧种子缺说话人模型时明确拒绝离线构建。其余外部条件挂账不自动清除。


## 2026-10-30 P1 金句切片终态（待独立审查）
文稿/CLI→一次模型挑选与逐段译文→ASS双语→1080×1920成片；合集每篇3条复用串行媒体队列。连续来源ID限定中文和起止时间，失败只补缺失阶段；只有音频明确提示纯色成片，无媒体拒绝。零新增依赖，客户包冻结。交付CLIPS_GUIDE.md与runtime/clips-20261030/（350后端/98前端、六条真实成片、1280/390截图）。挂账：49集压力与真手机/人工听校；剪映草稿、智能裁剪、封面模板另立需求。审查请求见该runtime目录。
