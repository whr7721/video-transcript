# 调研决策与可复用经验

每项记录：问题 → 来源与证据级别 → 本站结合点 → 采用/候选/暂缓及理由 → 改动成本/风险 → 验收方式 → 后续衔接。记录日期不代表所依赖工具永久有效，重新使用前核对版本和维护状态。

证据级别分为官方文档/源码、作者声明、本机实测、用户人工验收；功能实现和单次请求成功均不能替代质量验收。

## 2026-10-21：先修回答完整性，再补采集便利性

### 已核对的真实对照

上次后台脚本已完成结果写入，但交互被浏览器验收中断，本轮读取已有记录，没有新增付费调用。记录在忽略目录runtime/article-eval/quality-20261021.json。

用户问题要求：ComfyUI文章中图生视频的模型文件、目录、参数及RTX4060适用边界。本站说明12.73秒完成，保留4段、过滤1段；最终说明没有列出六个模型文件清单。直接全文回答27.56秒完成，列出了原文六个文件及路径，并说明作者4070 Ti SUPER的速度不能套用到4060 8GB。原文块和笔记前后相同。

结论仅适用于这次样本：直接全文回答在文件清单完整性上更好；不能据此宣布模型服务可靠性恢复或整体方案质量通过。过滤掉一段与漏文件同时发生，但没有保存第一遍完整候选响应，不能断言所有缺失都由过滤造成。

### 功能推进1：完整回答＋可回查出处

问题：当前articles.answer()限制最多5段、单段单block_id/quote，并对无效引用整段过滤。文件清单、参数或跨段解释容易不完整；正文里引用存在也不能证明整段说明的全部语义。

本站结合：articles.py的answer()、article_api.py的question入口、ArticleLibrary.tsx结果展示及导出。继续复用原始blocks、content_hash、artifacts和独立笔记，不改原稿。

拟议实现：先完整回答用户问题，再附一个或多个来源块；代码、路径和参数尽量直接展示原始块。引文校验失败保留诊断原因，并清楚提示出处未核对，不把错误引用标成已验证；如何展示未核对文字需在实施前确定，不能为了不漏内容而把编造事实伪装成有证据。回答可以自然展开，不让固定卡片数量决定信息取舍。完整性和引用质量分别验收。

验收：教程样本六个文件/目录逐字正确；参数和硬件条件完整；无原文证据的性能不补造；支持一段说明引用多个原文块；无效引用不可冒充有效；旧结果和笔记不改写。用5个实际任务与直接全文回答比较，不能只测模型JSON或引用子串。

采用状态：下一阶段首选；本轮仅确定方案，未修改业务代码。成本是输出契约、展示、导出与测试联动，无需先引入向量库/Agent框架。

### 功能推进2：用户主动的Chrome剪藏

问题：微信样本为验证页，知乎403，小红书页面壳；单纯换后端正文提取器不能解决页面获取。用户手动复制会丢图。

来源：[Chrome activeTab](https://developer.chrome.com/docs/extensions/develop/concepts/activeTab)说明用户点击扩展后临时访问当前标签页；[扩展跨来源请求](https://developer.chrome.com/docs/extensions/develop/concepts/network-requests)说明内容脚本与扩展后台的权限区别。

本站结合：已加载页面 → 提取当前可见正文/有序图片/元信息 → 预览与缺失提示 → 本站article_api导入 → 现有原文阅读与问题整理。开发的扩展是用户收藏工具，与Codex自动控制Chrome是两件事；自动化工具未连接不意味着产品扩展不可实现。

先用HTML或导出包验证协议，再做最小Manifest V3扩展。activeTab+scripting用于当前页，不能假定自动获得跨来源图片或本机服务权限。初版可导出包后手动导入，直接送入本机服务需要配对令牌、扩展来源校验、最小主机权限；不能把local_security全局放开或只依赖CORS。

验收：用户只点击一次后读取当前页，不后台扫描历史；微信图文与图片顺序保留；展开/懒加载不足明确标记；不自动传cookie；图片下载失败有占位；本机服务未启动可保留导出文件。只覆盖能正常阅读的当前内容，不承诺获取付费或尚未加载内容。

采用状态：第二步候选。用户表示知乎/小红书看得少，因此先以公众号和普通教程为主，不围绕低频平台做大规模爬虫。

## 可直接复用与暂缓清单

| 方案/经验 | 本站结合点 | 状态、证据与取舍 | 验收/后续 |
| --- | --- | --- | --- |
| [Trafilatura](https://github.com/adbar/trafilatura)，Apache-2.0 | article_parser通用正文兜底 | 已采用，已本机比较缓存HTML。只解析，不承诺绕过获取限制 | 30条质量基准未完成；扩站需回归 |
| [Defuddle](https://github.com/kepano/defuddle)，MIT | 未来Chrome端抽正文、代码与元信息 | 候选；隔离Node评测已运行，未加入生产依赖 | 同页面与本站解析对照，验证代码及图文顺序 |
| [Obsidian Web Clipper](https://github.com/obsidianmd/obsidian-clipper)，MIT | 当前页/选段→预览→保存的交互与模板设计 | 借鉴，不迁移整套笔记软件，也不要求安装Obsidian | 小范围复用已审查模块，保留许可证通知 |
| [MagicMD微信解析](https://github.com/didilili/MagicMD/blob/main/src/magicmd/platforms/wechat.py)，MIT | 微信正文容器、懒加载图、元信息与缺失报告思路 | 已借鉴思路，自写适配；没有整套安装Camoufox | 已知微信样本受限，不能声称已支持 |
| 原始块＋AI产物＋个人笔记分离 | articles.blocks/artifacts/note及旧documents流程 | 已实现；真实对照证明原文和笔记未被改动 | 为跨素材引用、改写和导出提供基础 |
| 逐字引文检查 | 核实和article answer已有实现 | 已采用，但只能证明摘录存在，不能证明语义支持或回答完整；本次对照暴露局限 | 增加多块引用、语义抽查和完整性验收 |
| 受限页不是成功全文 | article_fetch/article_parser失败分支 | 本机实测微信验证页、知乎403、小红书壳；HTTP200不等于正文成功 | 保留失败类型，转主动剪藏而非无限重试 |
| 文章图片Referer | article_fetch.fetch与图片下载 | 本机实测：少数派图片无来源403，附来源origin后4/4保存；不是所有站点通用保证 | 不泄漏原URL查询参数，不修改代理 |
| 图文遍历而非只提取文本 | article_parser.walk | 审查发现a包图丢失，v1.2补后代遍历、顺序及失败占位测试 | 回归语料长期保留，迁移解析器也必须跑 |
| 中文FTS5 | 后续素材标题/段落检索层 | 候选；trigram两字查询有官方限制，默认中文分词需实测 | 2至5篇任务先做，再决定分词/向量/重排 |
| OCR | 图文攻略→原图关联文字 | 暂缓；RapidOCR/PaddleOCR仅调研，未测本机准确率 | 不能因图片已保存就声称图中文字可问答 |
| Jina/Firecrawl/Crawl4AI | 外部获取备用或动态任务 | 暂缓，当前不加常驻服务/接口；不能据宣传替代本站实测 | 获取成功率、依赖、费用与许可证分别评估 |
| 云端网站＋本机worker | job_id/输入快照/幂等结果协议 | 远期架构方向；未连接现有阿里云服务器 | 浏览器/OCR/视频重任务不塞进2GB节点；账号隔离另立里程碑 |

## 本轮决定与验收边界

用户明确：浏览器验收暂由用户人工执行；不把它记为通过，也不再反复尝试自动化连接来阻塞功能规划。真实手机触屏和输入法候选上屏仍需用户实测。

下一阶段先完整回答与出处，再Chrome剪藏，随后2至5篇跨素材研究。暂不推进全库聊天、知识图谱、定时追踪、小程序或公众上线。新UI仍使用已安装设计skills，实施前按模块核验选定候选，不以重新大调研替代推进。

## 后续用户调整：上述路线封存，优先讨论抖音定向批量

用户提出按话题或标题定向批量获取抖音内容。上一节的推进顺序保留为历史方案，现已封存，不继续自动实施；已上线的图文功能与所有数据保留。

本机源码核对：MediaCrawler的DouyinClient.search_info_by_keyword已有关键词、offset、搜索频道、排序、发布时间与search_id参数；meme-lab已有关键词搜索调用经验。本项目extractor.py目前仅extract/login/creator，没有搜索入口，不能说本站已经实现主题批量。现有batches.py可复用子任务去重、时长筛选、队列、失败恢复与转写，但新的搜索父任务需要显式接入worker和界面，不能只加一个参数就假定跑通。

建议最小链路：用户输入主题或关键词组合 → 搜索并保存候选元信息/命中原因/分页状态 → 用户预览选择 → 默认10分钟内 → 复用原有下载、转写和缓冲区 → 主题批次浏览与导出。先拿元信息，不先下载全部结果；视频ID去重并复用已完成稿。元信息时长不确定时复用既有unknown分支继续核验。

边界：第一版为关键词驱动的主题搜索，不等于精确话题页采集，也不保证标题逐字匹配或覆盖全部相关视频。标题/简介匹配不能证明讲话全文相关；人工选候选后再转写，后续根据全文与用户问题显示相关段落与适用条件。搜索排序可能变化，保存关键词、候选来源与本次时间，不将采样结果包装成全网共识。

不得改动正在运行的MediaCrawler配置、meme-lab定时任务或系统代理。新入口沿用本站独立集成方式和登录态。具体限量、分页与搜索返回结构仍需独立小样本验证；本轮只读源码，没有启动爬虫、下载或调用模型。

用户确认首个主题“AI工具的实际变现”。详细路线与可转交ZCode的采集器契约见[抖音主题路线](DOUYIN_TOPIC_ROUTE_20261021.md)。新增源码发现：client请求count=15而core按10计算偏移，混合条目存在只取首项路径，接入前必须实测分页与结构，不能直接复制core循环。此处仍是风险发现，不是已经复现的平台丢页结论。


## 2026-10-21：M1采用冻结v1适配器，先形成可复查的候选池

**问题与本站落点**：按“AI工具的实际变现”定向搜索，先花低成本判断题材，再决定是否转写。新增discovery.py/discovery_api.py与Discovery.tsx，独立discovery_jobs表保存输入快照、去重候选、人工勾选及版本。不把搜索记录混入原有ASR任务表；原始稿、编辑稿、图文及专题笔记不改动。

**采用**：ZCode本地douyin-discovery README及源码，schema_version=1。复用现有MediaCrawler虚拟环境与只读client，CLI参数数组+JSON文件集成；无新增依赖、MCP或云服务。浏览器单任务串行，已有任务时409；同输出文件续采，启动失败也保留本站候选快照及勾选，下一次手动续采恢复种子文件。进程240秒超时停止拥有的进程树；服务重启先读取有效部分检查点再标为中断，不自动重新搜索。

**界面复用与来源**：沿用本站React、现有Radix Button、蓝白令牌、系统中文字体；不引入第二套UI框架。[Radix原生/组件键盘语义](https://www.radix-ui.com/primitives/docs/components/checkbox)用于勾选交互参考，具体列表使用原生checkbox+label，保留Space切换和焦点。[W3C表格指导](https://www.w3.org/WAI/tutorials/tables/)比较后不采用复杂交互grid：此处主要读长标题及元信息，语义列表在窄屏更合适，无需增加表格包。[Web Interface Guidelines](https://github.com/vercel-labs/web-interface-guidelines/blob/main/command.md)落实标签、可见焦点、跳到正文、未保存提示、reduced-motion和长文本处理。ui-ux-pro-max本机检索针对Empty/Loading/Bulk Actions/Table Handling：采用明确空状态、搜索状态、批量勾选、窄屏纵向布局。设计来源是指导，不能代替本站真实浏览器验收。

**筛选逻辑**：编辑1至3组关键词，按顺序搜索且共用总候选上限，可能第一组即用完；不假装每组都搜索成功。默认本地显示600秒内，未知时长另标可隐藏；可切1200/1800秒或不限。标题/作者包含词全部匹配，排除词任意匹配。列出隐藏原因计数，筛选不会取消已勾选。非视频/类型未知不允许进入视频清单。已有完整文稿只读关联。人工勾选以revision冲突保护，轮询不更新未保存选择的基准版本。

**本机真实证据**：网站API单关键词上限10，14.23秒返回10条，9条已知时长在10分钟内；保存1条并再次读取一致；任务记录哈希及音视频文件清单前后一致。接着手动续采总上限30，18.13秒返回30条，保留之前10条和勾选，ID无重复。证据仅说明本轮请求成功，不代表全量召回、案例真实性或登录长期稳定。运行结果保存在忽略目录runtime/discovery-eval，不提交用户标题、数据库或会话。

**已知适配器边界（源码发现）**：一页返回超过总上限时，适配器会把未保留作品也记入seen_ids并推进整页游标；续采可能跳过页内剩余候选。多关键词结束判断、缺失data被当空页、启动失败覆盖输出、登录/验证/限流细分也不能仅凭契约声明视为已验收。本站对覆盖输出做数据保护；未修改ZCode适配器，M2前交ZCode修复分页语义并增加页2失败/异常数据fixtures。当前搜索候选明确标为有限采样，不提供“全部收集完成”承诺。

**暂缓/衔接**：M1不调模型扩词/打分、不下载、不转写；M2须显式冻结选择、重取详情/时长，复用下载与5GB缓冲；未知时长不能凭本页标签绕过M2限制。M3再根据全文抽客户、交付、获客、成本及证据缺口。许可证仍继承MediaCrawler非商业学习限制，CLI隔离没有改变授权；公众商业化前另行处理。


## 2026-10-21：干净核心V1方案（候选，待用户确认，未动工）

用户要求本地音视频入口优先于抖音M2，并确认独立部署验收系统为Windows 10/11。读取clean-core-v1-intel及背景报告后，核对源码发现：ASR可复用，但app/pipeline启动装配、固定媒体清单、抖音来源链接、模型下载强制7890代理和manuscript的24000字上限均需处理。“全链100%复用”和“一小时2—3分钟”不可作为实施事实或验收承诺。

推荐单份核心＋静态私有来源适配层＋白名单生成干净包；公开入口不导入、不注册、不打包抖音代码，私有启动保留原data，干净包独立data-core。不把当前私有Git历史公开。只隐藏菜单或维持两个长期分叉均不采用。V1拟支持单文件1GB、中文本地CPU、最长两小时；长稿完整阅读/导出与选段研究，不顺手扩大全文AI整理容量。

外部核验：[Buzz](https://github.com/chidiwilliams/buzz)及[file_transcriber源码](https://github.com/chidiwilliams/buzz/blob/main/buzz/transcriber/file_transcriber.py)借鉴来源/转写分段，不能直接依赖其PyQt6+yt-dlp类；[Open Notebook](https://github.com/lfnovo/open-notebook)借鉴来源/笔记分离而不迁移完整栈，不据市场报告宣布无人覆盖；[Starlette流式请求](https://starlette.dev/requests/)采用已有request.stream原始单文件体，不把multipart max_part_size误当文件大小上限；[FFmpeg协议控制](https://ffmpeg.org/ffmpeg-protocols.html)结合容器允许清单，禁止外部引用型输入。设计skills用于复用现有工作台和补上传进度/恢复，不重做视觉系统。

证据等级：本轮为本机只读源码和外部官方/原仓库核验，无新功能或长音频实测。完整候选方案、四里程碑与验收门见CLEAN_CORE_V1_PLAN_20261021.md；待用户确认后实施，Docker/RSS/公开发布/英文后排。
# 2026-10-22 · V1-A 核心装配与发行边界（已实施，待独立审查）

- 本站问题：启动模块、任务调度、前端静态 import 和 public 历史页面同时耦合私有采集器，隐藏菜单不能得到可分享的核心。
- 采用 [FastAPI 多模块 APIRouter 装配](https://fastapi.tiangolo.com/tutorial/bigger-applications/)：`app_shared.py` 统一已有编辑/研究/文章 API、安全中间件及恢复；私有 `app.py` 保持旧路由，新增 `app_core.py` 只装配核心。不是复制一套处理逻辑。
- 采用 [Vite 独立 root/publicDir 构建](https://vite.dev/config/shared-options.html)：共享 `Studio.tsx` 接收显式 `SourceUI` 组件；私有来源表单及导航移出共享文件，核心入口不 import 私有入口。独立 public 目录只含 Logo，避免历史 HTML 自动复制进发行包。沿用现有 React/Tiptap/Radix，无新增依赖。
- 不采用运行时 feature flag 隐藏私有模块、源码字符串替换或整仓库复制：这些无法可靠满足全目录排除与数据隔离。内部白名单 builder 只复制核心源码和已编译资源，并扫描所有路径和全部字节、最终 ZIP 解压重扫；验证器含禁词，故留在内部仓库。
- 本站复用点：FFmpeg 探测/音轨转换移至 `media_io.py`；转写、片段缓存调用及导出落盘移至 `transcript_stage.py`，私有管线调用共享阶段。保留旧任务 ID/结果结构，通过私有调度层解释历史来源，不批量迁移用户记录。
- 成本与边界：增加两个入口及前端组合契约，后续仍须同时回归；核心数据独立且拒绝未标记的非空目录。V1-A 不包含文件上传、长音频压力、模型下载器或同学独立部署。共享媒体阶段仍保留旧转换限制，V1-B 将完成本地文件准入和额度预留。
- 证据：现有回归与新增发行隔离测试、核心/私有前端构建、最终包扫描及私有数据前后摘要，见 `MILESTONE_V1_A_20261022.md`。没有调用付费模型、没有真实平台爬取，没有把 mock 当模型质量验收。
# 2026-10-22 · V1-B 本地文件链路（已实施，待 ZCode 审查）

- 本站采用 [Starlette Request.stream](https://starlette.dev/requests/) 和 [原始 requests.py](https://github.com/Kludex/starlette/blob/main/starlette/requests.py) 的原始请求体流。两步创建/PUT 上传会话让取消有稳定 ID；不采用 multipart、Uppy/tus 或新增中间件，避免把 multipart 字段上限误当文件总上限。按实收字节校验，Content-Length 只作一致性检查；支持无 Content-Length 请求。
- 借鉴 [Buzz 文件转写阶段划分](https://github.com/chidiwilliams/buzz/blob/main/buzz/transcriber/file_transcriber.py)，复用本站已有 ASR/cache/导出阶段；未复制其 PyQt/下载器依赖或任务框架。新增小型本地串行 worker 和源码不含平台依赖的 HTTP/CLI 入口。
- 按 [FFmpeg 协议](https://ffmpeg.org/ffmpeg-protocols.html) 与 [容器文档](https://ffmpeg.org/ffmpeg-formats.html) 限定 file 协议、四类容器，检查实际签名、音轨、有限时长，禁用 MOV 外部数据引用。强制仅第一条音轨，限制 64 轨和 probe 输出字段；完整解码失败不得进入 ASR。
- 不把 probe 时长当可信资源预算：转换先预留，输出出现后减少剩余预留，增加超时和输出上限；预留留出检测虚假时长及 muxer 尾包的空间。到达保护上限后不把截断的 WAV 宣布为完整成功。
- 落地到 `local_files.py`/`local_media.py`/`media_buffer.py`：暂存与原文件/WAV 均计费；同字节按模型/语种配置唯一去重；重导入只补媒体，不重写已有原稿/人工稿。OS 实例锁保证同一核心目录只有一个 quota writer；线程锁、串行写入和转换预留共同避免超卖。原私有任务不迁移。
- 真实经验：接近 5GB 时，仅清理少量已确认素材可能仍不足，必须保留等待状态；lease 会按实际五分钟过期，不能把一次 touch 当永久保护。显式取消还要结束等待下一网络块的协程，否则客户端不关闭 socket 时会占上传槽到超时；已补真实 socket 验收。
- 实验调度曾把六格式与长文件拒绝同时上传，收到预期单槽 409。调整为串行重跑；不把 409 当媒体解码失败。短语音格式样本、真实两小时连续播客及实写配额占位文件分别标注，不能互相替代。
- 仍待改进：本机大 WAV 的流式上传约 95 秒，说明有逐块配额盘点/路径检查开销；没有假称磁盘极限吞吐。V1-C 可按 profile 结果优化批次盘点与进度，但需保留实收计费和取消边界。长稿全文整理仍有既有容量限制，V1-C 前置提示；V1-D 的无代理模型下载未执行。
- 无新增依赖、模型或外部生产 API。本轮真实证据和复跑脚本见 `experiments/local_files/` 及 `MILESTONE_V1_B_20261022.md`；公共样本音频和转写正文仅留在 runtime，不进 Git。

## 2026-10-22 · V1-C 工作台贯通（已实施，待独立审查）

- 本站需要让文件上传的实际字节进度、服务端准入和 ASR 进度各自可解释。核对 [MDN XHR upload](https://developer.mozilla.org/en-US/docs/Web/API/XMLHttpRequest/upload) 与 [Uppy XHR 源码](https://github.com/transloadit/uppy/blob/main/packages/@uppy/xhr-upload/src/index.ts)，采用原生 XHR 直接发送 File，复用 V1-B 两步上传会话；不引入 Uppy/tus 的额外状态与依赖。100% 仅代表发送结束，仍显示校验中；取消与准入同时发生时查询会话状态，不能谎报删除成功。
- 阅读 frontend-design、ui-ux-pro-max、web-design-guidelines，并核对 [Radix Progress](https://www.radix-ui.com/primitives/docs/components/progress) 与 [Web Interface Guidelines](https://github.com/vercel-labs/web-interface-guidelines)。沿用现有蓝白、中文系统字体和编辑器，以原生 progress、焦点可见、44px 操作区、弹窗限高和文件名换行改善入口；未照搬营销页设计或新增组件框架。
- 核心入口注入 FileCapture/TaskActions，共享工作台保留现有来源组合契约。容量计算复用 organizer 的分块函数，24000 字全文整理限制在排队、检查 Key 和模型调用之前执行；保留全文阅读、编辑、导出与选段研究，不以截断掩盖容量限制。
- 无 Key 场景增加显式手动笔记：保留来源选段和版本，数据库事务同时保存研究记录、专题及笔记，导出标记未调用 AI。AI 研究仍独立，不把人工理解伪装成模型输出。现有原稿、历史稿与笔记不回填、不迁移。
- 按 [Python ZipInfo](https://docs.python.org/3/library/zipfile.html#zipfile.ZipInfo) 固定 ZIP 时间戳、Unix 普通文件权限、压缩等级、相对路径排序。相同输入在同运行环境重复打包字节一致；不承诺不同 zlib/编译资源版本仍同哈希。回归额外改变源文件 mtime，避免只验证同一秒构建。
- 本机真实证据：两条不同的连续 6 分钟中文播客片段完成 HTTP 上传/本地识别/编辑/笔记/导出；其中一次真实云模型选段说明完成，其余离线链在无 Key 进程复验；重启前后 15 张表记录摘要一致。私有 13 张表及 1669 个非数据库文件摘要未变。证据见 experiments/workbench 与里程碑文档，不提交素材或模型输出。
- 验证边界：组件 DOM 测试不是浏览器视觉验收。Chrome 连接不可用，工具清单无可操作浏览器，预览仅排队打开；触屏、中文输入法、视觉和实际点击播放仍待用户人工确认。一次 AI 成功不能代表总体质量评测。V1-D 的无代理模型下载、独立 Windows 部署不在本轮范围。

## 2026-10-22 · V1-D 干净交付准备（独立机器验收待外部条件）

- 用户确认 V1-C 审查无发现、ZIP P3 独立复验结案，并要求推进 V1-D。确认暂时没有独立电脑，先完成可交付部分；这不构成免除外部验收。本轮不公开私有仓库、不重启私有工作台。
- 本站部署阻碍是旧 setup_models.py 硬编码本机代理、下载后才记哈希、无环境检查、README依赖作者机器背景。对照 [sherpa 官方固定模型说明](https://k2-fsa.github.io/sherpa/onnx/sense-voice/pretrained.html)、[官方发布API](https://api.github.com/repos/k2-fsa/sherpa-onnx/releases/tags/asr-models)、[Python ProxyHandler](https://docs.python.org/3/library/urllib.request.html#urllib.request.ProxyHandler)，采用无新增依赖的标准库下载器，不引入 Hugging Face/ModelScope SDK 或模型运行栈迁移。
- 两个固定官方发布件预先钉住大小和 SHA256；压缩包校验后只读取两个固定普通成员，不执行通用 extractall。临时下载失败清理、不把 HTML/截断文件安装为模型；已校验文件可离线复用。默认 ProxyHandler({}) 禁用环境及 Windows 代理发现，显式 --proxy 才使用代理，不修改系统设置，不记录代理地址/凭据。VPN/TUN/网关状态仍需真人在外部测试环境确认。
- 本机实测：全新 models 目录真实直连下载163002883字节模型包及643854字节 VAD，分别27.734秒、2.375秒，发布件与三个模型文件全通过固定校验；不是独立无代理机器结论。旧模型目录只做只读校验，未替换已有权重。
- 部署复用 [pip repeatable installs](https://pip.pypa.io/en/stable/topics/repeatable-installs/) 的精确版本锁定思路，保留现有40个锁定版本，不声称版本锁等于哈希锁。在中文/空格解压目录创建新 venv、真实安装并 pip check；安装使用本机 wheel 缓存，不能称干净网络冷下载。前端预编译免Node，环境检查仅使用标准库，独立核对版本、工具、端口、数据目录和模型，不 import app 或改数据库。
- 公开 README 增加普通用户安装、模型失败/离线校验、PowerShell单进程执行、端口冲突、备份与隐私说明；配独立验收表记录人工协助。内部 README 保留私有入口历史说明，发行只取公开说明；不把含私有历史的 Git 仓库公开。
- 条款核验发现 [SenseVoiceSmall 模型卡](https://huggingface.co/FunAudioLLM/SenseVoiceSmall) 为自定义 [FunASR MODEL_LICENSE](https://github.com/modelscope/FunASR/blob/main/MODEL_LICENSE)，不能用代码 MIT 或 sherpa Apache-2.0 替代权重条款。包不附模型、FFmpeg 或 Python，保留前端依赖版权/许可文本和来源通知，自身公开许可/公众发布暂缓。
- 验证：下载故障/代理/压缩成员/离线校验与非侵入预检有回归测试；交付在本机新解压目录演练，不以目录隔离冒充另一台 Windows。真实长素材与实际听校分别记证据；机器输出首尾有字不等于识别准确。人工界面验收挂账见 AGENTS.md，未新增UI范围。

## 2026-10-22 · 下一步路线调研（候选，未实施）

- 针对真实两小时稿可转写但难阅读、文章/音视频存储分立、无跨资料索引的现状，推荐R1 RSS显式单集 → R2章节导读/按章整理 → K1统一来源引用/本地检索 → K2专题内研究 → C1创作。保留原V2 RSS方向，建议将原V4中的章节阅读部分前移；待用户确认，不自动扩大开发范围。抖音M2保留私有侧线。
- 对照 [Readwise播客阅读](https://blog.readwise.io/update-dec2025/)、[Global Ghostreader](https://docs.readwise.io/reader/guides/ghostreader/global)、[Podwise](https://docs.podwise.ai/)、[Open Notebook](https://github.com/lfnovo/open-notebook) 官方文档/实体源码，确认单纯转写/问答/引用并非独有。借鉴资料/派生产物/个人笔记分层和范围研究，不移植其完整服务栈。
- RSS首选候选为 [feedparser](https://github.com/kurtmckee/feedparser)：核对pyproject/完整LICENSE，代码BSD-2-Clause、未归档且当前支持Python3.10+，但有requests/feedparser-sgmllib依赖，并非零成本。本站HTTP先有界取字节再解析；[标准全文/章节](https://github.com/Podcastindex-org/podcast-namespace)有则用，不把shownotes误作全文。
- 只读实测一个既有RSS：约5.12MB、267集、均有enclosure、无标准全文/章节标签；初设2MB研究限制拒绝，8MB研究上限重读成功。不能由此推断全平台覆盖，生产限额需更多样本决定。本机SQLite3.45.1内存实验确认trigram三字词命中、二字“客户/蒸馏”不命中；不能直接宣传FTS5支持全部中文检索。
- 先用来源只读投影+SQLite可重建索引，原始数据不迁移；以中文短词/同义词/ASR错字/无答案题的20题候选集评测，再决定embedding。复用现有上下文/引用验证，但逐字匹配不等于语义支持。
- V2EX按章阅读/Markdown案例与Reddit导出诉求只作社区个案线索；未复制来源项目，未装依赖或调用付费API。完整候选取舍、阶段边界及验收见 NEXT_ROUTE_RESEARCH_20261022.md；本轮只增调研文档，不改V1-D待审查代码。

## 2026-10-22 · RSS单集方案细化（路线已批准，实施方案待确认）

- 用户批准先RSS单集、再长稿章节导读；明确M2（抖音选中转写）押后，两项完成后重新评估，不自动启动。私有M1及历史能力保留。
- 补读现有source_contract、local_files、article_fetch与builder后，确认三个不能直接套用的点：FileSource只接受local_file；文章fetch聚合内存且30秒不适合大音频；公开包禁词门不能因README列私有路线而破坏。拟采用明确Podcast来源/共同资产交接、受控流式下载、公开/私有路线分开记录。
- 首版RSS公开地址、选一集、节目文字text/plain/VTT或本地ASR两路径；没有音频不伪造回听，shownotes不当全文，解析预览不自动下载。feedparser固定发布版本与依赖待实施验证；原始XML仅作测试对照，不自写兼容框架。
- 按用户要求，R1验收含公开README路线图和哈希发布流程。依据GitHub官方Releases说明，整仓库自动source archive不作为干净包；先冻结/打包/验manifest/解压扫描/重复构建，最后生成ZIP外部SHA256SUMS及发布元数据，不自引用ZIP哈希，不将hash等同签名。准备流程不等于授权公众发布。
- 详细步骤与真实双路径/取消/配额/旧数据/发布验收见 RSS_SINGLE_EPISODE_PLAN_20261022.md。本轮仅调研和方案文档，未动工。

## 2026-10-22 · R1 RSS单集导入（已实施，待独立审查）

- 用户已确认实施，随后转达V1-D审查结束且无P0/P1。顺序保持RSS单集→长稿章节导读；M2押后，两项完成后再评估，不启动私有采集扩展。
- 采用已发布feedparser6.0.14 wheel，实际只依赖feedparser-sgmllib2.1.0，和此前main pyproject要求requests的声明不同；锁定实测wheel依赖，不新增HTTP客户端。核对dist-info：前者BSD-2-Clause，后者PSF-2.0，已附许可正文。原先拟写二者同BSD的判断在提交前更正。
- 已安装版本没有podcast namespace模块，不能直接读取假设存在的podcast_transcripts字段。沿用feedparser处理RSS/Atom，并从有界、禁DTD的XML树只提取官方namespace全文元数据；节点/深度/字节受限，元数据预览不获取enclosure或全文。
- 复用article_fetch.PublicTransport逐跳目标校验，新增受控流式变体，保留原文章fetch默认行为。复用local_files.upload/admission与同一worker、槽和5GB字节计量；获取记录与已入库资产分离，明确podcast来源和source_associations，不改旧资产身份或稿件。
- 节目文字使用独立publisher原稿路径、稳定块ID及缺时间戳标记；可用的节目文字不调用ASR，没有音频不假装可回听。官方文字仍标完整性/准确性未人工核验。实例包含英语节目文字，不据此宣称英文音频识别通过。
- UI采用frontend-design、ui-ux-pro-max建议的现有蓝白/中文阅读布局、原生表单、焦点可见、整行radio和20项分页，未复制外部播放器。按web-design-guidelines检查日期国际化、长标题换行、状态播报和错误焦点；CUA仅有空MCP Apps，无可操作浏览器，GUI人工挂账见AGENTS.md。
- 真实样本：Python Bytes两集、Audience两集直接导入官方VTT；知行小酒馆E253约79分钟经76.6MB下载/校验/本地ASR完成约3.09万字，ASR287.61秒，整链348.86秒（期间并行回归，非速度承诺）。五集均完成编辑、手动笔记、原稿/编辑稿导出。另一次现有文本模型选段说明成功并存专题/导出，只有一次调用，无搜索调用。
- 真实取消最初暴露终态先于finally删除的竞态，已改为清理后发布终态并加入回归；重跑在约0.66MB时取消，暂存已删且并发文件PUT为409。初次重启过严的全表比较也发现恢复反复改写干净终态会话，收窄后18表摘要一致；旧私有13表与1669文件与既有基线相同。
- 发行采用包内manifest精确文件集合+逐文件hash验证、解压禁词门、两次独立暂存ZIP比较；最后生成外部SHA256SUMS与release-metadata（commit/脏标记/工具/锁摘要），不把ZIP自身hash放回ZIP、不将hash当签名。公开README路线图/发布清单同步，私有M2排期只在内部记录。
- 某些候选feed出现超时/404或解析到非公开IP，保留拒绝与失败记录，未绕过。新venv/空模型/无Key的发行包真实节目文字链通过；独立机器等挂账未冒称完成。详见RSS_SINGLE_EPISODE_MILESTONE_20261022.md及experiments/podcasts/，未提交正文/音频/密钥/数据库。
- 最终解压复核还发现：把新包覆盖解压到上次验收目录会保留旧hash名JS，严格manifest正确拒绝额外文件。改在全新空目录复核，公开README补充升级也须新目录，保留旧数据通过显式路径选择，不靠覆盖解压“升级”。

## 2026-10-23 · R2 长稿章节导读（方案待确认，未实施）

- 用户转达 R1（71f3855）审查通过、无发现，要求 R2 先给方案。本轮只更新文档，不改功能、用户数据、依赖、模型或额度。M2 继续押后，待 R1/R2 完成后重新评估。
- 补读 Podcast 官方 JSON Chapters 标准、Open Notebook transformations 原文及 Readwise Ghostreader 官方交互文档，结合本站 documents/organizer/manuscript/research 源码：采用原稿与派生产物分层、阅读内选段操作、受控官方目录；不搬完整知识库服务栈，也不直接套用发送全文的实现。
- 关键适配：seg-i 要和原稿 hash、必要的段内范围组合；无时间全文不造时间，重复句不能只靠 find 定位。长单段用可追溯派生片段处理，旧原稿保持不变；24000 字全文整理上限保留。
- 拟以有界窗口识别语义边界、短导读，再检查跨窗边界；代码保证连续覆盖，人工评测语义价值，两者不能互相替代。官方时间落在语音段内部时披露映射精度；toc:false 不导致正文消失。无 Key 的确定性导航明确叫阅读分段。
- 拟采用请求预算预览、共享每日额度、窗口检查点与显式恢复，不自动重试付费。先做目录，点击章节才整理，缓存含原稿/范围/模型/提示版本。初始 AI 范围建议 60000 字/最多12窗，不把更大输入截断为成功。
- 方案分 R2-A 范围/目录基础、R2-B AI 导读/阅读交互、R2-C 按章整理/研究/发布。用三条真实长资料做机械范围与人工质量分开评测；同模型短稿对照旧完整稿，检查例子和条件保留。未做真实模型和人工检查前不称质量通过。
- 详细取舍、来源链接、费用边界、UI 与验收门槛见 LONG_FORM_CHAPTERS_PLAN_20261023.md。当前不需要新增 API 配置；全部参数和门槛仍是待批准方案，不是已实测性能。

## 2026-10-23 · R2-A 开始实施（尚未完成里程碑）

- 用户批准方案。新增 chapters.py 的纯函数来源快照、无损片段、离线阅读分段、顺序覆盖校验及精确范围解析；没有接入数据库/API/UI，没有调用模型或修改旧功能。
- tests.test_chapters 三项测试通过：长段和重复句无损、原对象不变、无时间片段不造时间、遗漏/重复/逆序/过期引用拒绝、空稿及极小分段边界。
- 后续仍需章节版本持久化、受控官方目录、API/工作台集成及真实数据回归；当前不能称 R2-A 完成。新模块尚未加入发行白名单，不能据此宣称发行包支持章节。

## 2026-10-23 · R2-A 章节基础实现（待独立审查）

- 接通来源hash/父段偏移、精确范围验证、单独版本表及共享API；原稿页增加本地阅读目录。原文/编辑稿不回写，章节仍是派生导航。R2-B语义目录/AI导读和R2-C章内研究尚未实现。
- 官方JSON Chapters1.2复用PublicTransport，元数据仅保存受控URL，点击才获取；隐藏目录不丢正文，无时间文字拒绝映射。显式endTime的空隙/重叠本版拒绝而不猜测，时间仅原始段级近似。真实feed探测无章节链接，官方映射未做生产样本验收。
- 验证：152后端/36前端测试通过，两套前端构建通过；四条真实长资料无损覆盖；独立副本真实HTTP保存与读取30580字符，原任务摘要不变。69文件候选包扫描/manifest验证通过，未公开发布。证据见R2_A_MILESTONE_20261023.md及experiments/chapters。
- 使用设计技能与新鲜界面规范；浏览器实际点验仍待用户，DOM结果不冒充视觉通过。未新增依赖或付费模型请求，M2继续押后。
