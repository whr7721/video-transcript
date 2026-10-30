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

## 2026-10-23 · R2-B/R2-C 继续实施与统一审查授权

- 用户要求直接完成R2后一起审查，故不等待R2-A单独结果；仍分阶段提交。范围为有界语义目录、按章整理、范围研究/笔记/导出；M2不启动。
- 补核Readwise阅读中选段与Open Notebook派生产物分层官方资料，采用已有阅读工作台/后台任务/模型额度，不移植完整服务栈。UI继续用已安装设计skills。
- 真实模型暴露链式过度合并：范围完整但单章过大且导读两千多字。用跨窗口限制、正文/导读长度门禁修复，重用已验证窗口，不重新付费跑整篇。
- 真实模型会略写片段ID/微调引用：唯一父段别名才规范化；原话不精确则程序取原文作为位置参考，显式标未确认语义支持，不能冒充已验证引用。非法范围继续拒绝。细节见R2_B_MILESTONE_20261023.md，最终效果与用量待总验收记录。

## 2026-10-23 · R2-C 贯通与统一交付（待独立审查/人工质量确认）

- 完成单章预览、显式目录采用、改名/拆并、精确章内研究/手动笔记/导出；源引用含章节版本和Unicode码点选区，旧笔记不随目录漂移。
- 三份真实长稿完成AI目录，仍偏细（43/50/59章）。5114字同输入：章稿3653字/约39.8秒/1次请求，旧完整稿3821字/约52.2秒/2次请求；不能把调用目标差异包装成普遍性能提升。10个关键词候选新旧均出现，不等于语义质量已通过。
- 全套163后端/38前端、双前端构建、真实HTTP编辑/研究/笔记/导出、21表重启摘要及干净解压包链路有证据。共28次196509 token，ledger28，未放宽当日30次限制；费用须看实际账单。
- 实验坑已记录并修正：自建旧流程控制漏status导致首次重启失败；干净包先import store触发核心隔离保护。只修实验脚本/自建记录，不弱化业务保护，不把实验错误说成旧数据损坏。
- 官方目录真实样本、语义质量、浏览器视觉和既有外部验收仍待。工具已准备30处来源/导读对照和同输入整理对照供人工确认，不用模型自评替代。详见R2_MILESTONE_20261023.md，M2/K1均未启动。

## 2026-10-24 · K1-E0 中文检索候选评测（独立实验，待审查/用户标注）

- 用户授权先冻结中文题集、测关键词基线，再据数据决定语义层。R2审查未转达，本轮没有修改待审业务代码或页面；10份真实文字只读投影，215段约9.64万索引字符，AI生成稿/测试假笔记不当原始证据。
- 查SQLite FTS5官方分词/排名、rank_bm25原始源码/Apache-2.0、jieba官方搜索模式/MIT和ir-measures指标。采用已有SQLite的trigram与双字预分词BM25，无新增包；不复制另一套BM25实现。Success与来源命中/范围命中分开，不冒充完整Recall。
- 先冻30题（24正例+6无答案），dev/heldout各15；标签是作者准备的候选，4个ASR意图需听校，不称用户金标准或第三方盲测。精确范围Top5：标题整句2/24，正文整句7/24，trigram16/24，双字22/24；双字在6个无答案题均返回候选，不能称已完成答案判断。
- 用户另给4个真实方向，独立probe不回填v1。发现幼教错排幼儿园就业材料，应用/业务方向潜在相关来源排到31/17名，收入方向也缺直接变现证明。不能据22/24夸大自然语言搜索可用性；用户问题及正文仅保留runtime，Git只记query_hash和范围诊断。
- 当前决定：保留词法召回，暂缓向量库；先补真实意图v2标注，再对比查询约束/词法重排与轻量语义重排。语义重排只是候选，未采用；只有确认词法候选池漏掉同义材料，再评语义召回。缺来源、ASR误名和排序错误不能一概归因“没RAG”。
- 规范化预缓存优化不改150组Top5；新增7项测试及全套170项通过。0付费调用/0新依赖，原文/数据库不入Git。具体结果、局限与复跑见K1_EVAL_MILESTONE_20261024.md及experiments/retrieval。M2/K2未启动。

## 2026-10-24 · K1-E1 查询约束/词法/轻量语义对照（待独立审查）

- 用户转达K1-E0通过，要求paraphrase逐题单列、失分集中时提升语义候选。固定同一v1题集和BM25 Top50，无正例注入；v1旧留出仅作回归。用户真实问题另列，不合并成绩。
- 采用官方Retrieve & Re-Rank机制，实验选官方mmarco MiniLM量化ONNX，固定revision/官方SHA/Apache-2.0，独立venv的onnxruntime/tokenizers，CPU本地推理；未引入Torch、向量库、远端API或生产依赖。BAAI/Jina仅作来源与取舍比较，未测效果不冒称集成。
- 真实总体Top5：BM25 22/24、硬约束20/24、词法22/24、小语义21/24。硬约束使6个无答案输入为空，但误删3处原Top50依据；不包装成正确拒答。语义不校准答案充分性。
- paraphrase四题逐题：16/3/1/1 → 语义9/1/1/1，仍3/4；BM25失分paraphrase/ASR各1，未建立改写类集中失分，故不提升为优先候选或默认启用。小语义新增1个ASR定位失分；局部收益和退步均保留。详见PARAPHRASE_20261024.md。
- 34输入977对评分约43.9秒，加载约0.92秒，CPU每题中位1.43秒；176后端测试及真实ONNX边界检查通过。模型约136MB、实验venv约244MB，非进程内存结论；无付费API调用。主环境没有新增模型依赖。
- 下一步先补真实意图分级标注与证据充分性，必要时前后文/中文适配对照；本实验未赢不推论全部语义模型无用。来源不足与ASR错名分别处理，向量库/M2/K2仍暂缓。详见K1_RERANK_MILESTONE_20261024.md，R2业务代码及页面未改。

## 2026-10-24 · faster-whisper / VoiceStudio 调研（未安装、未实测）

- 来源：官方仓库 https://github.com/SYSTRAN/faster-whisper ，已读 README 与 faster_whisper/transcribe.py；VoiceStudio 按 https://github.com/debpalash/VoiceStudio 识别，已读 README_CN、pyproject.toml、LICENSE-NOTICE、Windows 安装文档、功能目录及 https://voicestudio.sh/docs/transcription 。同名工具若非此仓库需重新核对。
- 本站实情：transcribe.py 使用 sherpa-onnx SenseVoice INT8、CPU四线程与 Silero VAD，输出语音段边界并逐段缓存；并非原版 Whisper。faster-whisper 的官方加速基线是 openai/whisper，不能据此断言比本站更快或中文更准。它是 CTranslate2 推理实现，需另下载 Whisper 权重；批处理吞吐提升可能增大内存/显存，VAD不能保证消除幻觉。
- 候选：仅为中文夹英文术语、较难听辨段做同音频引擎对照，保留原稿并分开存候选。可选 large-v3-turbo / large-v3，实际速度、数字/专名错误、漏句、静音误报、内存与显存由本机实测决定；不先接整套软件，不承诺 GPU 可用。GPU依赖 CUDA/cuDNN/CTranslate2版本匹配，公开CPU基础包暂不增加依赖。MIT实现与具体权重条款分别核对。
- VoiceStudio 是语音创作应用，包含转写、配音、有声书、听写、本地API/MCP等；pyproject 已列 WhisperX/faster-whisper 及 Torch 等依赖。因此整套接入不等于更好的识别引擎，且部署成本高于当前核心。可借鉴模型就绪状态、引擎选择与任务队列交互，不复制整套UI或后端。
- 后续实际结合点：校对后文稿→试听/个人学习音频；确认有需求后，可让本站通过独立本地服务API调用语音生成并保存稿件版本与产物对应关系。固定服务集成优先HTTP API；MCP是智能体调用选项，不是必要前提。转写接口 verbose_json 声明支持分段和时间，但仍须核验具体引擎精度与本站原始时间轴映射。
- 许可取舍：VoiceStudio应用AGPL-3.0-only，官方说明允许按条款商用，闭源嵌入有商业授权渠道；不能把“开源”直接等同于可任意复制进未来闭源网站。默认 OmniVoice 权重在其许可说明中记录为 CC-BY-NC，模型与应用授权独立，付费应用许可不自动覆盖模型。未来选TTS需逐模型确认。
- 当前决定：faster-whisper列为ASR对照候选；VoiceStudio列为后续声音输出与产品交互参考，不进入核心依赖。没有安装/下载模型/付费调用，也没有运行时或业务代码变更。以上除本地源码现状外均为文档/源码核对与方案判断，非效果验收，不改变K1路线。

## 2026-10-25 · K1-P 专题内搜索生产化（统一审查通过，K1收官）

- 用户转达统一审查通过、无发现；接受共享FTS的BM25统计漂移，记录不处理，不自动形成新任务。人工点验等既有挂账不由代码审查替代。

- 用户转达E1无发现并批准生产化方案。采用现有FastAPI/Python SQLite FTS5 + 已测中文双字/ASCII BM25；不引入向量库、语义模型或外部依赖，E1升级条件维持。参考SQLite官方 https://www.sqlite.org/fts5.html 与Datasette搜索 https://datasette.io/for/search / 查询处理源码 https://github.com/simonw/datasette/blob/main/datasette/utils/__init__.py ，不复制代码或引入其服务。中文拼音扩展 https://github.com/wangfenjin/simple 当前无需求收益，暂缓。
- 实际结合点：research_notes→research_jobs→tasks解析专题成员；个人理解、保存选段、去重原稿，读取全部笔记而非旧列表200条；不把未关联的文章/其他专题/AI结果混入。没有独立文章专题关系，此边界已在开工更新中说明。历史编辑/整理选段按来源标签显示。
- 新派生索引事务核对更新，专题/类型过滤在Top50前，分10条分页。同来源聚合仅改变展示，不改排序；标题另列并仅打开来源开头，不冒充正文命中。纯文本Unicode高亮，重新读取原文核对指纹/范围；源变化拒绝猜测定位。查询上限200字；单汉字明确字面回退，标点提示。分数不作答案可信度。
- frontend-design/ui-ux-pro-max用于沿用工作台样式、空结果建议、键盘焦点和输入法处理。未保存理解有浏览器备份与版本冲突保护。依照实际桌面能力尝试Chrome，启动成功但窗口读取被工具因URL置信不足停止；无截图/真实输入法验收，引用AGENTS挂账。
- 验证：原30题Top5来源/范围逐题与旧BM25相同；paraphrase单列仍3/4，22/24只表示已知范围定位。4条真实查询在隔离8份转写专题通过HTTP与前5条上下文回查；前列仍有明显不相关，生产化不包装成问答质量改善。人工相关性检查不是用户确认真值，详情experiments/topic_search/QUALITY_20261025.md。
- 合成1万原稿片段：首次建索引+查询约2.58秒、25次热查询中位约154ms/P95约159ms，数据库约80MiB；不能推论所有机器/语料。冻结10源原库只读且前后快照一致；文章夹具仅用于算法回归，不冒称文章专题产品已接入。
- 184后端/46前端测试、私有与核心构建通过；白名单候选包确定ZIP复建、全目录门、解压后无Key搜索/修改/过期引用/重启通过。未付费调用、未下载模型、未改原用户内容、未对外发布。M2/K2仍未启动。详见K1_PRODUCTION_MILESTONE_20261025.md。

## 2026-10-25 · 产品梳理与面试证据（仅文档）

- 用户反馈后续迭代缺少产品理解。新增USER_GUIDE.md讲清功能、实际操作、不同数据环境和未贯通处；PROJECT_INTERVIEW_GUIDE.md把已实现、实验、未实现技术分开。README首页历史路线过时，已改为指向当前指南。未修改运行代码、未迁移数据、未重新打包或公开发布。
- 刚检查仅8775监听，为无Key/无音轨的夹具预览，不是全部历史资料的日常环境。建议先确认日常入口并走通实际素材，不把新增框架作为解决入口割裂的办法；未来带引用专题问答仍需单独确定。
- 技术概念核对官方：MCP https://modelcontextprotocol.io/docs/getting-started/intro （工具/系统连接），LangGraph https://docs.langchain.com/oss/python/langgraph/overview （有状态编排、持久化与人工介入），工作流和Agent区分 https://www.anthropic.com/research/building-effective-agents 。当前产品使用Python/SQLite有界工作流，未采用LangGraph/MCP服务或运行时Skill路由；开发工具使用不冒充产品实现。
- 简历建议侧重现有可复现的评测/失败分析、长上下文与恢复、来源约束和人工采用。30条候选标签非独立真值、22/24非答案准确率、合成性能非线上SLA，均保留限定。下一步路线为建议，非本轮新功能开工授权。

## 2026-10-25 · 图片资料导入与利用（方案，未实施）

- 用户给多图面试材料与单图工具介绍作为真实用途。两短链重定向至note作品7683044048454544229/7698766932971949235，但未取得原图；第二条返回验证码中间页。HTTP200不算内容成功，没有绕验证、登录或运行生产采集。
- 只读源码复用：MediaCrawler媒体模块已有有序图集地址提取；既有发现适配器仅承诺video元数据，保持schema1，新作品图集获取须独立适配。素材库已有图片保存/阅读，article问答会排除图片，K1也未关联文章/图片，均不能冒称已读图。
- 研究官方RapidOCR（pyproject/依赖/模型许可）、PaddleOCR及Qwen3-VL。建议先本地OCR基线，再对难页实测视觉增益，不宣称某模型最便宜/最准；未安装、下载模型或付费调用。主机sherpa-onnx不等于已有独立OCR运行包。
- 候选方案为原图→有序OCR/区域→对照核疑→按需面试问题/工具笔记→显式加入专题→原图回查，复用素材库，不另造站。图片属于原文资料，保留受现有图片库配额约束，裁切缓存与音视频缓冲分别管理。图解解释/AI补充与原文分层。
- 优先级建议改为先图文阅读与专题统一，再考虑引用式专题回答；尚待用户确认，不动已收官K1的统计风险。完整来源、边界、阶段与验收见IMAGE_KNOWLEDGE_PLAN_20261025.md。


## 2026-10-26 · 图片资料自用落地

- 用户授权使用既有爬虫。采用独立私有图集适配器，复用既有隔离登录及下载保护；生产采集配置与定时任务未改。公开核心仅保留通用图片链路，包内机械禁词检查通过。
- 采用RapidOCR 3.9.2 / ONNX Runtime 1.23.2 / Pillow 12.0.0的可选独立环境，模型固定路径与哈希。复用文章库、显式专题和FTS，暂不新增云视觉、向量库或工作流框架。
- 真实45图/单图得到23,600/459字；逐页OCR合计84.814/1.594秒（不含下载）。原图保留。2次文本说明调用成功，0次云视觉调用，引用与OCR稿逐条匹配；未将此等同于语义或OCR准确率验收。
- 真实失败经验：切换工作目录导致相对输出路径错误，已改绝对路径；长图切片重叠产生重复识别，按区域重叠去重，不做跨页删重。计时元数据变化不得导致原文引用过期。
- 站内结合点：原图坐标阅读/人工修订、按页提问、明确加入专题及回查原图。图解关系理解未实现，真实GUI验收受浏览器URL识别限制未完成。细节与测试见IMAGE_IMPORT_MILESTONE_20261026.md；K1已接受风险不重开。

## 2026-10-26 · OCR筛选式净化阅读

- 用户批准规则先行、AI仅筛区域、不许改写，并授权本阶段开发AI预算10元。复用原区域、图片、专题FTS和模型接口，新增派生分类，不重跑OCR。
- 借鉴Docling的body/furniture分层与provenance：https://github.com/docling-project/docling/blob/main/docs/concepts/docling_document.md ；PaddleOCR版面类别作为分类参考：https://github.com/PaddlePaddle/PaddleOCR/blob/main/docs/version3.x/module_usage/layout_detection.en.md 。两库本轮只参考设计，不引入其运行依赖/模型；文档和维护源已查阅，不复制实现。
- 本站实际结合点：ImageReader默认净化阅读、按页对照；ocr_reading统一只读投影供UI/导出/专题搜索；独立人工标签与原图红框评测，低分折叠不等同杂讯分类。AI解释仍是既有独立功能，不混进净化原文。
- 实测16批460候选成功，1984区域文字和原始OCR全等，46原图哈希不变；估算0.12477元，保守预留1.60元。缓存再次运行零新增模型调用。语义去噪收益尚待用户人工标签，不能以排除数或模型自评代替。
- 已知代价：严格不纠字意味着OCR错误仍在；规则0.85阈值需人工样本量化误折叠；位置/重复不足以删除，只触发语义候选。分层200样本的指标仅代表该小样本，不能当全量总体准确率。详见OCR_READING_PROGRESS.md。

## 2026-10-26 · 图文以完整整理稿作为默认阅读

- 用户将便利性置于第一位，同时要求按证据选择方案。旧图文已能采集/识别/对照/问答/搜索，但没有默认长文阅读，筛选本身不能替代整理。采用整份OCR直读→整理稿→精华，人工标签暂停，不当使用门槛。
- 复用本站manuscript结构校验/精华提示及organizer API，而非新增框架。官方截断检查 https://docs.siliconflow.cn/docs/api/chat-completions-post 与长上下文页标识实践 https://www.anthropic.com/news/prompting-long-context 支持保留完整输入及明确页边界；不以这些资料声称模型对本样本准确。
- 实际45页25,603字可一次输入；第二次生成9916字整理稿与658字精华，单图461字整理稿。首轮被硬字数比例拒收，取消该不可靠质量门槛，保留结构与截断保护；不同请求长短并不等同质量。主题出现检查不能证明逐点完整和事实正确。
- 新稿与OCR/笔记分开，缓存避免反复收费，精华失败保留完整稿，原文变化提示旧稿。增量5次请求约0.279348元，无新依赖。详见IMAGE_EDITORIAL_MILESTONE_20261026.md。

## 2026-10-26 · 原图阅读对照（实验收尾，未接产品）

- 用户批准比较并接入有收益的路线，45图约1元可接受作为处理成本参考；原10元累计预算不清零，不等于小程序售价已确定。
- 核对供应商视觉文档 https://docs.siliconflow.cn/docs/userguide/capabilities/vision 和价格 https://www.siliconflow.cn/pricing ，Qwen官方模型卡 https://huggingface.co/Qwen/Qwen3.5-35B-A3B 、GLM原始仓库 https://github.com/zai-org/GLM-V 、PaddleOCR-VL文档 https://github.com/PaddlePaddle/PaddleOCR/blob/main/docs/version3.x/pipeline_usage/PaddleOCR-VL.md 。采用既有HTTPX/API与原图存储，不安装视觉权重或文档解析服务，不复制上游代码。Qwen模型卡Apache-2.0；GLM-V仓库已声明停止维护，不据旧仓库做长期绑定。
- 真实6页两模型×两输入：Qwen原图/联合分别93.12/75.56秒、0.0154808/0.014340元；GLM分别28.52/32.16秒、0.034682/0.036833元，按返回usage和当时单价估算，非账单。GLM另有2次JSON mode不支持的400失败，无usage，不计为免费成功。
- 对照原图发现：Qwen评估表比GLM保留更全；但联合输入给无标签箭头补了Resume，不能认定OCR联合更优。OCR保留作索引/区域对照，候选阅读默认原图。复杂连线仍有风险，无独立人工准确率成绩。
- 单次45图等待600秒超时，无正文/usage；随后24页非流式请求也失败，无正文/usage；最后45图流式请求127.907秒ReadTimeout，未收到响应头、正文或usage。不能将后两次失败都推断为模型生成太慢，也不能认定接口永远不支持多图。保留失败费用预留，不将无usage当零收费。
- 由于大批路径未验证成功，撤回本轮所有产品默认/界面/核心包接入改动，恢复原完整阅读稿；只保留experiments/vision内实验工具和请求计数/按模型记费复用。原图、OCR区域和笔记与实验前快照相同。没有宣称45图视觉链路或复杂关系准确率通过。
- 后续先以已经成功的6页规模做小批及7页跨批恢复，复用原稿而不重新采集；确认小批稳定后再跑整份45图。客户端候选包含流式结束校验、失败候选保存、连续页段缓存，但这些单测不等于真实流式或跨批质量通过。不先装本地视觉模型、不扩展框架。
- 已有每日30次限制继续共用。6次早期探针最初直接调用，已一次性补记到当日计数，再将新视觉入口纳入共享计数；未重置旧账本或放宽限额。供应商token换算不跨模型套用，按返回usage及Qwen上下文档位记费。
- 最终当日30次、开发账本30条；累计已知usage估算0.505454元（本轮增量0.101336），保守预留累计7.76元。3次大批失败无usage，实际收费未知；预算和每日上限均不重置。详见VISION_READING_EXPERIMENT_20261026.md。

## 2026-10-26 · 竞品小程序调研（仅文档，未改代码）

- 用户要求分析竞品小程序可借鉴的流程/界面/功能线索，用于拾文后续设计与复现，且不预设照搬。本轮只读外部资料与本站代码，未真机体验任何竞品，未安装插件，未改代码/数据/Key/外部采集资产。新增 COMPETITOR_MINIAPP_ANALYSIS_20261026.md。
- 证据分级执行：官方定价/文档为A，官方产品页与媒体报道为B，第三方教程与合集为C，未验证为D并在文中标注。竞品额度数字来自官方页面，不等于当前账户可用；界面只到信息结构层级，非像素级记录。
- 参考来源：通义听悟计费 https://help.aliyun.com/zh/tingwu/pricing-and-billing-rules （ASR 0.6元/小时，每个大模型能力0.064元/小时并按使用数量叠加，试用90天）；讯飞听见权益包 https://zskzs.iflytek.com/myfiles/b277725a-e1ef-4686-b546-666e7811ff25/gzhqd.html （免费20分钟/月，连续包月每月赠3小时导入权益跨端通用，小程序未登录5分钟）；BibiGPT 官方 pricing.md https://bibigpt.co/pricing.md （免费单条30分钟/总120分钟，Plus 2小时，Pro 6小时并提示长视频走异步流水线）；百度网盘视频AI笔记与腾讯ima小程序报道（钛媒体）；NotebookLM中文教程（C，仅流程参考）。
- 采用（仅作为设计线索，未开工）：首屏双入口（粘贴链接/选图）；任务异步+可离开+订阅消息提示；阅读稿优先、原稿第三位（与现有三tab一致）；引用可点回原位置；单份资料出5道自测题；导出/复制作为最低成本外流。
- 候选（需用户确认与真机验证后才做）：能力拆分计费（转写/整理/精华/视觉四类）与小额包混合；未登录试用1份；权益跨端同一池；微信聊天文件导入。
- 暂缓：专题分享/多人共读（需账号与权限体系）；微信端侧OCR替代本地OCR（官方有OCR检测能力，精度与限制未测）。
- 已否定：全平台链接解析承诺（本站边界明确，公众号/知乎/小红书不能通用）；AI播客/音频概览；通用AI助手式全网问答；把采集登录态或MediaCrawler生产配置搬进小程序；在2核2GB ECS跑ASR/解码重任务。
- 成本对照（本站实测，不对外报价）：45图整理+精华5次调用约0.279348元；单图两调用约0.006816元；视觉6页Qwen/GLM分别约0.014-0.037元；本地ASR无按次API费用。据此判断边际成本在文本/视觉token而非转写，付费设计不应照抄按分钟卖转写。
- 硬约束（需按官方文档与真机复核，本文不代替结论）：请求域名须HTTPS并在小程序后台配置；小程序端不能跑SenseVoice/RapidOCR，重任务留worker；iOS虚拟支付政策需分端设计；微信内打开抖音/小红书链接的可用性随平台策略变化，须实测。
- 未验证项：竞品真实质量与限额触发、订阅消息触达率、微信聊天文件大小与长图压缩后OCR质量、单份成本分布（当前仅2份图文样本，定"1份=多少点"需≥20份记录）。
- 本轮无付费调用、无新依赖、无构建影响；纯文档提交，不宣称任何小程序能力已实现。

## 2026-10-26 · 轻抖小程序逆向与商用边界（仅文档）

- 用户指出轻抖（appid wx7869c97260909c66，本地缓存版本106）与自己产品重叠，要求分析其商用做法，并处理"借助非商用部分不能上线"的问题。本轮只读本机微信小程序缓存包，静态解包阅读 app-config.json 与 app-service.js；未登录、未调用其接口、未抓包、未破鉴权、未复制其代码或素材进项目。新增 COMPETITOR_QINGDOU_REVERSE_20261026.md。
- 观察：域名 api.qingdou.vip / gateway.aipie.top / h5.qingdou.vip；客户端零模型、零ffmpeg，解析与转写全在服务端；去水印走 /api/v1/tinker/video/upload + getResult 返回腾讯云地址；文案提取走 /miniApp/video_extract/getTaskStatus(V2) 轮询，间隔由服务端 queryTime/needSec 下发；错误码4001=视频超时长→升级会员，9527=停机开关，21001=内容违规。
- 观察：会员购买跳转到另一小程序 appId wxea1b9bfeca2c2cc1 完成，并提示复制 qingdou.vip 去浏览器；去水印页原文声明"完全免费、不进行任何商业性目的使用、用户自行承担法律责任"；首页原文"因近期频繁有用户恶意消耗资源，现每天须看一次视频广告，当天即可免费使用"。收入结构为广告/会员/带货佣金/课程/增值工具五层，工具仅作入口。
- 本站事实核对：extractor.py 第1-4行自述受 MediaCrawler 非商业许可约束，且直接 import media_platform.douyin.client；pipeline.py、discovery.py、session.py 依赖其 venv 与 browser_data。build_core_package.py 已把 douyin/mediacrawler 列为禁词，核心包已剥离，私有版仍依赖。
- 许可证核实（官方原文）：MediaCrawler = NON-COMMERCIAL LEARNING LICENSE 1.1，条件3"未经书面同意不得用于任何商业用途"；SenseVoice 代码 MIT；Silero VAD MIT；RapidOCR Apache-2.0；sherpa-onnx Apache-2.0。结论：非商用只集中在 MediaCrawler 一个依赖，ASR/OCR/模型链路可商用；Silero 模型文件与 SenseVoice 权重发布页仍需按下载页复核。
- 判断：不能带着 MediaCrawler 上线；但"链接转文字"功能本身不是非商用，需替换实现。平台条款风险（抓抖音页面/去水印）与开源许可证是两件独立的事，换实现不消除平台风险，轻抖用免费+免责话术降低叙事风险而非消除风险。
- 建议（未实施，待用户决定）：先做"用户上传音视频/图片/文件"版本上线（无许可证与平台条款问题）；收费点放整理稿/精华/自测题/专题检索，不卖转文字；链接解析降级为灰度能力，用自研最小解析或商用解析API，不走 MediaCrawler；主体先解决个体工商户与类目。四道成本闸门（提交前校验/时长上限/每日次数/广告解锁）可直接借鉴。
- 未验证：未取到会员价格（服务端下发）；未确认其抖音数据来自开放平台还是页面解析；未做真机交互与视觉记录。本文件仅供内部判断，不随核心包分发，不复制其代码/素材/文案。

## 2026-10-26 · 轻抖深度逆向与复现规格（仅文档）

- 用户要求加深逆向并产出可交给 Codex/ZCode 复现的规格。本轮继续静态解包主包（150 个 route、451KB 业务代码、1.55MB 含 npm 库），导出首页/我的/去水印/查权重/榜单页与 appId 配置、request 封装，未登录、未调其接口、未抓包。新增 QINGDOU_REPLICATION_SPEC_20261026.md。
- 新观察：conf/appId 暴露 10 个小程序矩阵（qd_goods=当前、qd_school、qd_toolbox、qd_data、qingdou_watermark、qingdou_findMaterial 等），会员收款跳 appId wxea1b9bfeca2c2cc1；会员字段为 surplusHours/expiredDay，按小时计量而非次数；错误码 4001/21001/9527/70001/4004；请求封装统一附加 token、mini-version、platform-type；埋点为 behaviorLog/errorLog/channelLog/sendViewLog + 友盟 + 阿里云SLS；主色 #5657F0、底色 #F5F7F9、三级文字 #2F2F2F/#808080/#939393。
- 复现规格采用拾文自有命名（/api/platforms、/api/intake、/api/intake/{id}、/api/account/quota），不得照抄其接口路径、文案、素材、appid；任务分解 T1-T8 约 7 个工作日，T1-T3 不依赖小程序主体可先用 H5 验证；同时给出 ZCode 十条审查项与不可复制清单。
- 判断：只借"预检→排队→轮询→出稿→复制"的节奏与"按小时计费"的成本对齐方式；不借去水印、榜单、课程、分销、跨小程序矩阵。额度与"转文字"作为获客成本，收费点仍放整理稿/精华/专题。
- 能力边界已写入文档第 0 节：可做本地包解密解包、JS/WXML 静态还原、接口与字段契约还原、规格与代码实现；不能真机操作微信界面、不能抓实时流量、不能带登录态调其接口、不能绕其风控。分包页面（提文案结果页、文案库、去水印结果页）未缓存到本地，需用户在真机各打开一次后再解包补全。
- 未验证：会员价格与小时档位（服务端下发）、ASR 供应商、抖音数据来源（开放平台或页面解析）。无付费调用、无新依赖、未复制竞品资产。

## 2026-10-26 · 单人上线路线（仅文档，未动代码）

- 用户说明自身条件：天津大学AI学生、单人、会用Codex/dsh但编程能力一般，项目从简历目标转向尝试赚钱；有阿里云2核2G杭州ECS（未备案）、已购域名未用、无备案经历。新增 LAUNCH_PLAN_20261026.md。
- 核实到的硬条件（官方A级）：微信小程序虚拟支付已对个人主体开放，条件为个人主体+居民身份证+服务类目含「工具」+已完成认证与备案；全终端月支付限额10万元；Android费率1%、T+3，iOS 12%、结算45-60天且需微信8.0.68+；不支持需电信业务资质的服务，明确列举"信息发布平台、信息搜索查询"等。来源 https://developers.weixin.qq.com/miniprogram/dev/platform-capabilities/business-capabilities/virtual-payment/person.html
- 生成式AI合规（官方A级）：面向公众的AIGC小程序需提供大模型算法备案信息，部分平台另需与模型厂商合作协议。阿里云百炼与硅基流动均有上架合规指南；个人能否取得合作协议未确认，列为上线前必须向平台确认的事项。
- 路线判断：瓶颈是ICP备案+小程序注册认证+小程序备案三张证，不是代码；2核2G可跑FastAPI/SQLite/文章提取/云模型与云ASR调用，跑不了SenseVoice长音频、视频解码；先做"文本+图片+文章→整理稿"轻链路，H5先行验证，再做小程序5页，最后接虚拟支付，定价1元/份。
- 代码边界：article_*/image_*/ocr_*/organizer/manuscript/topic_search 可上云；extractor.py、pipeline.py、session.py、discovery.py 因直接依赖MediaCrawler不得进商业版；去水印不做；新增users/quota/orders/任务表/内容安全/删除通道。
- 风险与止损：AI合规材料可能拿不到、类目可能被拒、冷启动用户量极低；建议3个月/500元止损线，不碰去水印与抖音解析。收入预期按1元/份、单份成本0.1-0.3元给出，不承诺盈利。

## 2026-10-26 · 变现打法全景（仅文档）

- 用户明确：想凭本项目赚钱，要求列出包括灰色在内的全部路径与风险，自行决策执行。新增 MONETIZATION_PLAYBOOK_20261026.md。本轮只做风险定价与排序建议，未实施任何路径，未改动代码与数据。
- 路径分四档：A卖成品/服务（资料包、代整理、卖经历）、B卖工具（虚拟支付、广告、私有化部署）、C灰色（轻抖模式链接解析、矩阵号引流、借证矩阵、Key倒卖）、D刑事区（爬数据出售、卖Key给不明买家）。每条标注见钱速度、量级、归零概率与风险等级。
- 关键风险事实：视频平台诉解析/去水印工具的不正当竞争判例公开存在（判赔百万量级，具体案号未核实、给检索方向）；个人主体民事责任为无限责任且封主体连带；刑法285条对登录态+绕风控抓取有判例；Key转售涉ToS违约及量大时帮信/非法经营先例。
- 核心判断三条：用户独家资产是学生身份+真实项目+离用户近，不是工具本身；灰产门槛在分发而非技术，单兵无分发优势；45图→9916字整理稿即现成商品，第一步收入不依赖部署上线。
- 排序建议：今天A1闲鱼上架（现成样章）+A2代整理收单；本月C2引流放大；10个付费用户后启动B1小程序；C1轻抖模式延后至有企业主体与稳定流量后作现金流工具；D不做（期望值为负，纯利弊结论）。
- 版权红线写入文档：A1/A2交付物必须是自组织笔记+来源标注，不得直接售卖他人视频文字版；A2用MediaCrawler属许可证违约但小规模追责概率≈0，已如实标注"违约≠合规"。

## 2026-10-26 · 干净公开版 MVP 方案（仅文档，未动代码）

- 用户问：剥离非商用部分后干净版还剩什么功能、能否先部署简单版边获客边打磨。核对 build_core_package.py 白名单与 app_core.py 实际入口后新增 CLEAN_PUBLIC_MVP_20261026.md。
- 干净版能力核对：文章导入、多图OCR、AI整理稿/精华、专题检索、深入研究、编辑稿分层、播客文本直读均保留且可上2核2G；本地音视频转写（SenseVoice）在2核2G跑不动，第一版不上，第二版接云ASR按分钟单独计价；抖音与话题发现已剥离不做。
- MVP定位："收藏的截图和文章，变成一篇能读的笔记"。第一版输入只有文章URL/截图/粘贴文本，输出整理稿+精华+专题库；不做登录（device_id起步）、不做音视频、不做小程序、不做付费（第6周按留存决定）。
- 上线前四件必改（生死排序）：防刷与额度（自有Key暴露公网=被刷烧钱，每设备每日3份/同IP每日10份，settings接口公开构建禁用）、多用户隔离（store全链路无user概念，需加device_id强制过滤）、内容安全（词表+协议/隐私/投诉三页）、任务排队（复用chapter_jobs，全局并发1）。合计约4天，均在Codex能力内；setup_models.py需改为ASR模型可选下载。
- 部署形态：现成app_core.py+dist-core静态托管+systemd+Nginx+certbot；备案前用IP:8766内测不阻塞。
- 获客打磨循环：北极星=每周整理份数；每周3篇素材（对比图/痛点文/实战文/身份文，均有真实数据可引）+1个功能点；微信群做反馈通道。与LAUNCH_PLAN备案时间线并行。

## 2026-10-26 · 云ASR链路核对与MVP范围修正（仅文档）

- 用户指出工作台有云ASR路径且测试过。核对代码：transcribe.py:119 cloud_transcribe 完整（180秒切片→ffmpeg 64k mp3→api.siliconflow.cn/v1/audio/transcriptions，FunAudioLLM/SenseVoiceSmall，3次重试+分片缓存），CLI链路（cli.py --provider cloud）实测成立；但网页上传路径未接通：local_files.py:171 硬编码 provider=local，:280 调 finish_transcription 未传 cloud_key（默认空，cloud 分支会报缺Key）。settings.cloud_key() 优先读 SILICONFLOW_API_KEY 环境变量，Linux 部署天然兼容 DPAPI 分支（windll 仅在 protect() 函数体内，公开版禁用 /api/settings POST 后不会触达）。
- 修正 CLEAN_PUBLIC_MVP_20261026.md：音视频从"第一版不上"改为"第一版可上（云模式）"，新增 §3-⑤ 接线任务单：provider入参化+公开构建强制cloud、run_task补传cloud_key、服务器装ffmpeg、公开版配额（单文件200MB/30分钟、media_buffer缓冲改2GB、处理完即清）、定价前置实测（10分钟与60分钟各一次，官方价格页语音区未能抓取，不以估算定价，对外=实测成本×3起）。改造总量修正为4-5天。
- 验收标准：网页上传10分钟音频出全文、账单金额可查、同文件重跑零新增费用（缓存生效）。无代码改动。

## 2026-10-26 · 防刷任务单交接（文档，代码已回滚）

- 用户明确分工：实现交Codex（额度充足），本会话只负责调研与方案。此前动手的半成品（public_quota.py及三处接线）已全部回滚，仓库回到321e697干净状态；参考实现全文保留进 CODEX_TASK_PUBLIC_QUOTA_20261026.md。
- 任务单内容：SHIWEN_PUBLIC=1开关设计（私有版零影响为最优先验收项）、四挂点（editorial/classify/question/research）与settings守卫、TrustedHost公开分支（现白名单仅localhost，公网内测会400，必须改）、前端X-Device-Id注入、build_core_package BACKEND白名单补public_quota.py（Codex最易漏）、测试覆盖点、Windows验收命令与审查请求模板。
- 设计要点：配额库独立SQLite不碰store schema；设备限被拒不消耗IP池；X-Forwarded-For可伪造风险写入部署注意（Nginx层覆盖头缓解）；云转写暂不挂、留到§3-⑤接线时一并。

## 2026-10-26 · Codex按任务单完成公开配额接线（待独立审查）

- 用户授权执行CODEX_TASK_PUBLIC_QUOTA_20261026.md第3节①—⑨，并转达前轮审查无问题。本轮复用参考实现、FastAPI依赖、SQLite与现有核心入口，不引入限流服务。原始依据：https://fastapi.tiangolo.com/tutorial/dependencies/dependencies-in-path-operation-decorators/ 、https://www.sqlite.org/lang_transaction.html 、https://nginx.org/en/docs/http/ngx_http_proxy_module.html#proxy_set_header 。
- 采用SHIWEN_PUBLIC=1模块开关、四接口设备/IP自然日配额、核心设置守卫与Host公开分支；配额独立public_quota.db，BEGIN IMMEDIATE确保检查/双扣原子性，设备拒绝不消耗IP。核心fetch保留Request头/显式设备头，只向本站API注入UUID；模块与部署注意均进入核心包。
- 未设开关的全量pytest228项通过，前端57项及核心构建通过；真实隔离HTTP验证公开设置GET/POST403、设备第4次429、IP累计10次后429、公开Host200；移除开关重启后设置200、12次请求无429、原Host白名单恢复。88文件候选包验证通过，未部署公网/未付费调用/未改用户数据。
- 任务示例D:/tmp无权限，实际隔离在runtime/public-quota-smoke/data-core；pytest8.4.2仅装入忽略的runtime/public-quota-tools，生产依赖未变。外部HANDOVER_20261026.md未动。
- 真实风险明确保留：XFF须反代覆盖且禁止后端直连；任务只列四挂点，studio generate/chapter-jobs/verification confirm等其他付费路由并未保护，云转写与多用户隔离仍未接，不据此称全站可公开。公网真机与Nginx实测未做。验收命令及范围见PUBLIC_QUOTA_MILESTONE_20261026.md。
# 2026-10-27 · 思维导图采用决策

采用本地 Markmap 只读树，复用现有 organizer/generations，评估并修正 DSH 备份而不直接套 patch。对比 [Markmap](https://github.com/markmap/markmap)、[G6](https://github.com/antvis/G6)、[simple-mind-map](https://github.com/wanglin2/mind-map)：本轮无需编辑协作，后两者的集成范围更大，暂缓。使用 [Markmap view 文档](https://markmap.js.org/docs/packages--markmap-view) 的实例控制和本地 npm 锁版，保留现有蓝白界面、可读大纲与键盘入口。许可证及依赖已随核心包补齐，无 CDN。

真实长合集的提示词约束两轮未稳定满足边界，最终采用结构化 schema 限定分支，再做独立验证；无自动付费重试。236 后端、62 前端、双构建及 95 文件核心包校验通过。模型成功只证明生成链路与结构，不证明语义完整；单篇长音频质量未验证。人工验收挂账见 AGENTS.md，用户本轮自行点验。完整实测、失败记录、预算与预览见 MINDMAP_MILESTONE_20261027.md。

## 2026-10-27 · 云端需求验证版（可部署，未上线）

- 用户授权自主推进，随后明确尚无Cloudflare/Supabase账号，先交付可部署版本。采用独立cloud/目录、Pages/Worker、Supabase Auth/RLS，保留本地产品与真实数据。复用现有提示思路、结构化有界树和本地Markmap，不套用备份Worker/SQL。
- W3C规范明确MediaRecorder timeslice的单块不保证独立可播放，因此改用Web Audio解码、30秒独立PCM WAV；服务端按固定头和PCM字节验证时间，不按客户端声明或文件大小猜时长。暂缓ffmpeg.wasm、视频、R2、支付与章节，减少移动端依赖和部署面。来源：https://www.w3.org/TR/mediastream-recording/ 、https://ffmpegwasm.netlify.app/docs/faq/ 。
- 原Worker无鉴权、无真实时长检查、整块spread转base64可能栈溢出；原SQL允许客户端改写生成物、没有额度和分享。本版补服务端用户认证、service-only事务RPC、浏览器只读RLS、幂等和有限重试、账号/IP/全站额度及可撤销分享。实际模型同时兼容transcription_info.text与text结构，依据：https://developers.cloudflare.com/workers-ai/models/whisper-large-v3-turbo/ 。
- 每日Cron访问真实Supabase数据库并记成功时间；低活跃免费项目可能暂停，不能保证保活即永不暂停。默认邮件不适合公开注册，需要SMTP或OAuth。免费基础设施不等于文本调用/域名/邮件全部零成本。来源：https://supabase.com/docs/guides/deployment/going-into-prod 、https://supabase.com/docs/guides/auth/auth-smtp 、https://developers.cloudflare.com/workers-ai/platform/pricing/ 。
- 最终26项前后端流程测试、原生PostgreSQL16权限/事务/失败边界及8路并发、双端打包和部署准备脚本通过；npm audit 0漏洞。首轮Wrangler依赖漏洞已更新4.153.0；Windows运行中二进制导致npm ci文件锁，停本轮开发进程后完整重跑成功。真实云端与手机验收挂账见AGENTS.md，完整证据见cloud/MILESTONE_20261027.md。

## 2026-10-28 · 自用图文卡片接入

用户授权直接接现成工具，便利优先。复用haodongcui/md2card固定f672126c5caba634244c34aebcd5c83e11f0cc52，阅读源码App草稿恢复与export导出入口，保留MIT。Preact独立构建，通过本机/cards/挂载，不迁移React工作台。工作台编辑稿与素材库当前整理文字经一次性localStorage带入，跳过上游旧草稿恢复避免覆盖。仅/cards/允许blob图片供本地图片预览；本地公开核心/云端不新增此功能。AI沿用现有整理，不新增付费步骤。上游23项单测通过，构建通过，真实HTTP/cards/app/200；PNG视觉由用户实际使用验收，不夸称已验证。详情见tools/md2card/SHIWEN.md。

## 2026-10-28 · 自用创作稿

上轮卡片接线用户转达无问题。本轮选择“资料＋个人真实经验→AI图文创作稿→既有卡片排版”，复用模型API、现有预算/限额与md2card，不新增框架。受众、个人经验和来源分开输入；成稿单独保存，可编辑、复制发布正文、送排版，重开恢复。同输入缓存，不自动发布。3项隔离后端单测和62前端测试、构建通过；未实际付费调用或宣称生成质量通过。来源与边界见CREATION_MILESTONE_20261028.md。

- 自用创作后续扩展：五类任务、三种平台、可改受众与无Key手动模板；复用同一编辑/排版流程而非为每种任务重建工具。保存brief并区分缓存，提供来源对照与整稿导出。5项后端与62前端测试和构建通过，质量待自用验证，参见CREATION_MILESTONE_20261028.md。

## 2026-10-28 · 个人AI数据库与有界工具Agent

用户授权20元新阶段实验，不重置旧账本。研究Open Notebook的ask源码、Mem0记忆源码、SurfSense/Cognee产品与许可、Anthropic工作流/Agent区分及SiliconFlow tools协议；选择已有SQLite FTS5＋标准tool_calls循环，明确记忆由用户确认，暂缓向量库/图谱/整套框架。实现跨音视频、文章、OCR与笔记检索，动态搜索/读取最多4轮8段，引用逐字匹配与无支撑段落过滤、全库指纹缓存/历史变化提示、研究导出和转卡片。

6次真实研究、19次模型调用；预留4.34元，保守usage估算0.78752元（非账单）。跨题材NOAA与摄影记忆夹具仅在runtime隔离库，生产只保留真实调用账本。无答案任务7处不合格内容被系统过滤，音频任务1处引用移除，OCR布局推断是已观察局限；不能据此声称模型无幻觉或准确率达标。详细候选/源码链接、测试证据与取舍见PERSONAL_AI_RESEARCH_20261028.md；说明书PERSONAL_AI_GUIDE_20261028.md；简历地图AI_RESUME_CAPABILITY_MAP_20261028.md。

## 2026-10-28 · 资料到行动工作区

用户转达上一轮无问题，再次授权自由拓展。参考Anthropic Context Engineering https://www.anthropic.com/research/effective-context-engineering-for-ai-agents 与Deep Agents https://github.com/langchain-ai/deepagents 的外部状态/计划理念，不引入新框架。新增独立SQLite工作区、人工采用计划、进度/复盘、历史快照和revision冲突控制，复用现有Agent与同一20元账本。模型仍只读，不假装自动完成任务。

4项后端、2项前端新测试（总67前端）与构建通过；隔离真实研究3次模型调用，24.875秒，8节结果，采用后保存进度与引用、缓存不重复调用。累计预留4.95元，保守估算0.90821元（非账单）。修复进度保存丢引用的问题。用法、边界、审查范围见KNOWLEDGE_PROJECTS_20261028.md；未用假完成状态冒充真实任务执行。
# 2026-10-28 云端实际部署：Pages 同域 API

问题：首次云端发布发现本机 pages.dev 可访问，workers.dev TLS 握手失败；旧版部署脚本又受 Wrangler Pages 默认转发、JSON 字段及配置路径变化影响。

采用：[Pages Service Binding](https://developers.cloudflare.com/pages/functions/bindings/#service-bindings) + [Advanced mode](https://developers.cloudflare.com/pages/functions/advanced-mode/)，`public/_worker.js` 仅转发 `/api/*` 到独立后端 Worker，其他请求走静态资源；`_routes.json` 限定调用范围。无新依赖，保留后端认证、额度、服务端密钥与 Cron，后端关闭公开 workers.dev。浏览器改为同域请求，CSP 不再允许外部 Worker 地址。

不采用：关闭 TLS 校验、让用户为首发先买域名、修改本地资料库或把完整私有采集能力发到云端。

本机实测：新版 Wrangler 首次 Pages 创建需显式保留经典 Pages，列表 JSON 使用 `Project Name`；Pages 配置需标准文件名并通过工作目录发现。部署脚本及 Service Binding 已真实部署，28 项测试与构建通过；合成5分钟音频、真实云端模型、两个临时用户隔离及分享更新/撤销通过，详情 cloud/LAUNCH_20261028.md。观察到转写错字与导图部分主题遗漏，未声称质量通过。正式登录配置/GUI/手机/Cron长期健康/账单尚待验证。
# 2026-10-28 P0 链接 CLI

采用 yt-dlp 官方项目 Python 接口（固定2026.10.26）提供 metadata、subtitles/automatic_captions 和下载；参考 https://github.com/yt-dlp/yt-dlp/blob/master/README.md 。B站备用播放器字幕接口依据 https://github.com/bilibili-plugins/bilibili-api-collect/blob/master/docs/video/player.md ，不复制第三方完整实现。RSS复用本站feedparser/发布者字幕解析；抖音复用独立会话，不改 MediaCrawler。统一 `subtitlesArray` 按本机 BibiGPT openapi.json 字段设计，不调用其付费 API。

用户修正已采用：仅解锁现有多语言 SenseVoice 参数、补 cover/duration/publishedDate、声明 yt-dlp 安装、说话人分离挂账。本机四平台真实链接均获得结果，B站代理412改直连后成功；两小时稀疏合成时间轴及中断复用通过（27.55秒、复用2段、末段起点7184.266秒）。自然长录音质量不由此推定；详情 P0_LINK_GUIDE.md。未引入新后端或第二模型，无新增付费调用。
# 2026-10-28 P0 P1审查修复

采用官方 WinGet DenoLand.Deno（实装2.9.8），并按 https://github.com/yt-dlp/yt-dlp/wiki/EJS 补齐同版本要求的 yt-dlp-ejs==0.8.0；仅安装Deno不足以补齐pip默认未带的挑战脚本。源profile通过SHIWEN_DOUYIN_PROFILE参数化，默认兼容旧路径。16项针对性测试通过；新隔离目录YouTube英文字幕正向CLI成功，未命中旧文稿缓存。审查其他P2/P3暂缓，详见P0_P1_FIX_20261028.md。
# 2026-10-28 CLI整理闭环

采用现有manuscript.run完整稿/精华两阶段，精华请求一次附带五段结构、逐字金句和导图，复用现有request_json每日30次与image_editorial费用保护。备份不覆盖已合入mindmap；复用当前validate/to_markdown，HTML参考Markmap官方 https://markmap.js.org/docs/packages--markmap-view ，内嵌前端已锁定的d3 7.9.0/markmap-view 0.18.12及许可，不增加npm依赖、不用CDN。采用阶段落库和目录OS锁，导出重试无需再次模型调用。

实测：47项定向测试；真实新任务2次请求、缓存0次、transcript.*哈希不变。初次形状无效被拒绝，原稿和完整稿保留，单独补第二阶段成功，随后明确JSON示例。共5次请求如实记入旧账本。Chrome窗口最小化无法操作，离线HTML视觉交互挂账。使用说明与审查边界见CLI_SUMMARY_GUIDE.md。
# 2026-10-29 Windows 客户交付包

采用app_core白名单与已构建前端、独立客户数据目录。运行时选uv管理的Python 3.11.14（--no-bin/--no-registry），不用官方embeddable硬补pip，参考 https://docs.astral.sh/uv/guides/install-python/ 。uv/Deno/ffmpeg下载固定官方发行与SHA256；SenseVoice复用现有ONNX指纹，HF-mirror同源文件实测匹配，VAD仍用官方固定导出。只增加本地文件CLI接线与客户白名单，抖音提取分支不进交付包。

说明书依据 https://docs.siliconflow.cn/cn/userguide/quickstart 补注册/余额充值/Key创建/本机设置示意，区分本地转写与云端整理。57项回归、真实安装/两调用摘要导图/设置Key/卸载验证与网络限制详见PRIVATE_DELIVERY_20261029.md。不把开发机模拟当全新系统验收。

## 2026-10-29 Web链接共享接线

采用现有CLI链路抽取link_ingest + 显式link_private注册，而非复制一套Web实现或AST删除私有分支。任务复用generations(action=link_ingest)与各入口串行媒体队列；不采用额外进程池/Celery。参考FastAPI后台任务文档 https://fastapi.tiangolo.com/tutorial/background-tasks/ ，本项目需要重启可识别状态，因此保留已有持久记录与专属恢复。UI使用现有React与样式，状态/失败通知参考WAI https://www.w3.org/WAI/tutorials/forms/notifications/ 。

B站接口资料参考 https://github.com/bilibili-plugins/bilibili-api-collect/blob/master/docs/video/player.md ，仅复用本项目原有补充实现，不引入Cookie或新依赖。匿名真实三样本字幕为空，快路真实验收挂账；不因仓库声明推断本机可用。

实测RSS经yt-dlp generic发生TLS EOF，同地址项目已有安全流下载可读，采用article_fetch.stream写part再rename；不增加下载库。四平台真实文稿与缓存、客户ZIP独立进程拒绝私有平台已测。详情WEB_LINK_MILESTONE_20261029.md；GUI与手机截图交ZCode。

## 2026-10-29 B站登录与字幕探针

采用私有venv的Playwright 1.64.0 + 独立上下文，不借用MediaCrawler运行环境。私有依赖requirements-private.txt；客户ZIP按用户要求冻结，不构建/验证/维护。nav.isLogin校验、固定API主机Cookie、WBI/legacy播放器接口、CDN不带Cookie、Windows用户独占DACL；标准库实现，不引入B站SDK。参考 https://playwright.dev/python/docs/api/class-browsertype#browser-type-launch-persistent-context 及 https://github.com/bilibili-plugins/bilibili-api-collect/blob/master/docs/login/login_info.md 、 https://github.com/bilibili-plugins/bilibili-api-collect/blob/master/docs/video/player.md 。本机yt-dlp的Unlicense实现用于核对WBI公开签名规则；未引入完整客户端。

用户真实扫码后BV1GJ411x7h7冷缓存1.819秒取得47段字幕、无下载/ASR；匿名对照22.097秒走ASR。Windows真实ACL、Cookie不进任务数据、登出删除Cookie及专属profile、原稿哈希不变均实测。已有缓存不因登录覆盖。62后端/71前端测试及私有build通过，证据与GUI边界见BILIBILI_LOGIN_GUIDE.md。

## 2026-10-29 引用式批量队列

采用link_batches专用表引用既有单项tasks/generations；从link_jobs提取submit服务，批次轮转派发且与单条共用唯一媒体worker，不引入Redis/Celery或第二套摄取。Python标准库queue/zipfile依据 https://docs.python.org/3.12/library/queue.html 、 https://docs.python.org/3.11/library/zipfile.html 。状态通知参考 https://www.w3.org/WAI/WCAG22/Understanding/status-messages.html 。预览2×N与共享每日剩余配额，执行前按当前cli_summary缓存所需0/1/2检查，不足只等待整理，转写继续；实际限额仍由request_json执行。停止动作区分仅本批所有与共享任务，重启后手动继续。

真实四平台混合批次4完成、0失败、重复/无效各1，执行无重叠；ZIP13成员与CRC通过。runtime模拟剩余额度0，跨批复用两篇单项结果、等待整理且原稿哈希不变；模拟不是真实收费调用，不触及真实账本。客户包冻结保持。证据/限制/GUI交接见BATCH_QUEUE_GUIDE.md。

## 2026-10-29 首页产品化

采用私有入口ProductApp路由外壳：无task时Home，有明确task才挂载原Studio，根治默认首页被localStorage恢复旧文稿；保留其他view分支。复用LinkCapture/BatchCapture/设置字段，工作台仅抽取设置展示，编辑等内部逻辑不变。输入优先参考 https://bibigpt.co/about ，表单标签依据 https://www.w3.org/WAI/tutorials/forms/labels/ 。手机单列、输入16px、蓝灰既有风格，无新依赖和后端修改。79前端用例与私有构建通过；真实浏览器与手机首屏截图交ZCode，见HOME_ENTRY_GUIDE.md。

## 2026-10-29 首页视觉规格对齐

按用户实测的72px/700标题、56px一体输入栏、指定Lab边框/按钮色实施，仅首页启用LinkCapture home视觉变体；不改提交/缓存/重试/任务卡逻辑。用户确认按钮Lab为玫红而非此前口头“金黄”，以数值为准。引用 https://bibigpt.co/ 的产品形态及 https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/Values/color_value/lab 的色彩定义；未复制对方素材。79前端测试及私有构建通过；1280/390截图和并排对照交ZCode，未宣称像素级一致，见HOME_ENTRY_GUIDE.md。


## 2026-10-29 订阅与来源展开

采用共用 source_enumeration，两个入口分别落元数据时间线与原有批量预览，不新增媒体任务队列。调研依据：[yt-dlp](https://github.com/yt-dlp/yt-dlp#video-selection) 的 flat-playlist/playlist-items；[B站空间接口社区文档](https://github.com/SocialSisterYi/bilibili-API-collect/blob/master/docs/user/space.md) 与现有 WBI/nav 登录验证；[RSS 规范](https://www.rssboard.org/rss-specification) 的 guid；本地 D:/zcode1/douyin-discovery/discovery.py 搜索实现。前两者与现有依赖直接适配，不引入另一采集库；B站社区接口不是官方稳定承诺，以登录实测为准。

抖音搜索复用现有实现，由私有解释器桥接；主进程准备隔离 profile，子进程仅覆盖运行参数，不修改外部源码/配置。失败教训：MediaCrawler 环境无主项目 psutil，且自带 store 包；子进程不得导入主项目 session/store，锁使用标准库并延后读取已加载 store，避免命名冲突。补了真实子进程 namespace smoke 与 Windows 互斥测试。元数据枚举不按转写时长过滤，真正提取仍维持既有时长上限。

RSS 只保存序号或最新 Feed 不足以追溯旧节目，采用 GUID 与单集快照；发现序号作为已读游标，检查中更新保留人工标记。话题首次选取确有无语音失败，保留证据并换条验证，不制造文稿。真实四源、两条抖音选5全链、RSS快照与缓存引用证据见 SUBSCRIPTIONS_GUIDE.md / runtime/feed-20261029。自动轮询平台、推送、话题订阅暂缓；GUI/手机由 ZCode 点验。


## 2026-10-29 连发 A：资料库

调研 SQLite FTS5（https://www.sqlite.org/fts5.html）、Paperless-ngx 文档库/筛选模式（https://github.com/paperless-ngx/paperless-ngx）、WAI状态反馈（https://www.w3.org/TR/wai-aria/states_and_properties）。Paperless文档站403，未把未读页面当证据；BibiGPT本地OpenAPI仅参考library/collections语义。采用既有topic_search双字分词+SQLite FTS5，避免为中文短关键词额外安装trigram/向量库；不复制第三方源码或引入依赖。单独派生library索引，避免改变已审专题FTS的统计；B将按uid约束同一索引。收藏/合集只存引用，ZIP抽公共write_task供原批量与合集复用。UI保留首页输入优先，搜索置列表顶部，控件标签/状态反馈/可键盘排序。

## 2026-10-29 连发 B：单篇追问

调研 LightRAG 引用与检索实现（https://github.com/HKUDS/LightRAG），仅借鉴“回答带可回查片段”思路；其图索引、多存储和额外LLM建图不适合本次单篇私有工具，不引入代码或依赖。采用A的同一索引，SQL先限制uid与原文block，再排序/限量；摘要、标题与草稿不能挤占证据结果。回答后校验实际送入片段及逐字引文，并检查原稿指纹。资料/历史仅为数据，不能当指令；引用真实性不等于语义正确性，明确保留人工质量验收。

从personal_kb抽出原有费用预留/结算函数供两条链共用，原账本不重置；仍经request_json共享日配额，先检查剩余额度再预留预算。持久化每篇对话与请求ID，重复完成请求零调用；故障不自动重试，重启标记中断。只有私有sourceUI注入追问组件；不修改客户入口。没有实际付费模型调用，以确定性模型夹具覆盖链路边界。

## 2026-10-29 连发 C：CLI本地技能

参考官方Codex插件结构（https://developers.openai.com/plugins/build/plugins 、https://github.com/openai/plugins/blob/main/plugins/openai-developers/.codex-plugin/plugin.json）、DeepSeek Harness（https://github.com/deepseek-ai/deepseek-harness）及用户给定BibiGPT本地skill/DSH bundle的结构，文案/代码自写。只采用manifest+技能目录与DSH skills.register/resourceBase契约，不接MCP/OAuth；skill-creator校验与本地隔离安装实测。DSH从canonical skill打包，避免维护两份手工文案；实际宿主未安装，明确不声称宿主验收。

CLI add返回内部id供summarize复用，不改原输出；JSON进度到stderr，成功stdout单对象；costDuration明确耗时秒数而非金额。chapter复用现有chapter_jobs目录链与缓存，不引入第二个分章prompt；人工Web章节不被CLI导出覆盖。A的UID索引供B复用，C沿用task id而非创造新内容ID，三单没有冲突的存储模型。

## 2026-10-29 冲刺 D：笔记与导出

研究Obsidian纯Markdown vault（https://obsidian.md/help/data-storage）、Notion官方SDK的Pages.create/Blocks.children.append（https://github.com/makenotion/notion-sdk-js）、Notion参考端点（https://developers.notion.com/reference/post-page 、https://developers.notion.com/reference/patch-block-children），本地BibiGPT OpenAPI仅借鉴notes/notion语义。官方参考网页抓取因页面过大失败，采用官方SDK端点契约与既有httpx，不增加SDK依赖。笔记独立版本表与原文锚点，vault模板白名单并防止覆盖外部手改；Notion沿用本机DPAPI加密与明确点击导出，不做自动同步。无真实token，模拟API契约不当作远端验收。G单最新明确授权恢复私有full变体，覆盖旧冻结规则但不顺带维护core白名单包。

## 2026-10-29 冲刺 E：离线快照

复用cli_assets中固定D3 7.9.0 / markmap-view 0.18.12与既有mindmap验证，参照https://github.com/markmap/markmap 的浏览器渲染形态；无新增库。原文/标题/摘要/笔记全部HTML转义，导图标签只做纯文字，内嵌JSON转义小于号；CSP禁止远程资源/表单/默认请求。原始时间轴与编辑文稿分开显示，避免给编辑后的句子伪造时间。仅导出已有生成产物，0模型请求。测试验证单文件、无script src、内容转义、缺图提示、原文不变。

## 2026-10-29 冲刺 F：视频关键帧

调研FFmpeg seek/scale（https://ffmpeg.org/ffmpeg.html 、https://ffmpeg.org/ffmpeg-filters.html，后者抓取超时如实记录）、硅基流动视觉消息格式（https://docs.siliconflow.cn/docs/userguide/capabilities/vision）。直接复用既有experiments.vision.client.request的限额/费用账本、固定模型与usage，不另造视觉SDK。先免费本地抽帧、再明确选帧付费，单篇最大30，缓存按视频stat+间隔+帧数+模型版本隔离；失败后跳过完成帧，不自动补发。画面是局部采样，不推断不可见语音/人物身份；描述与附近时间原文并列，不做全文OCR。真实2次、缓存0增量，使用runtime隔离副本与进程内Key解密，不写密钥/登录态进Git。

## 2026-10-29 冲刺 G：私有full打包

参照uv离线/本地wheel（https://docs.astral.sh/uv/reference/cli/）、Playwright浏览器路径（https://playwright.dev/python/docs/browsers）与MediaCrawler原许可。复用原Windows安装工具锁、语音模型校验与uv包内Python，新增full变体，不修改旧core默认构建行为。完整依赖是既有应用/OCR锁合并+Playwright1.64/tenacity/PyExecJS/aiomysql供客户端导入；不把MediaCrawler整套requirements的旧FastAPI强塞主环境。仅复制客户端所需代码/JS和许可，禁复制原checkout config、browser_data、data、.env；bundled config为空安全默认，取消bundled包__init__的完整crawler副作用，原外部项目不改动。用Playwright自带Node执行已有JS签名客户端，不再另装系统Node。

运行路径全由full_env注入，扫码可初始化空的拾文owned profile，不再要求开发机已有MC浏览器。实际安装发现web漏包及ROOT/data遗留路径，补齐并改store.DATA；离线复制uv minor junction为普通目录会报145，改仅复制固定真实Python目录，已存在解释器跳过重复安装。offline-full只收bin/python/wheels/browsers/models，不收data-full与登录态；同机另目录真正离线依赖安装与启动检查，不当作真实新Windows设备验收。


## 2026-10-30 平台扩展：原生提取、公开单集与独立小红书会话

A档采用已安装yt-dlp的TikTok/TikTokVM/Twitter提取器（https://github.com/yt-dlp/yt-dlp/tree/master/yt_dlp/extractor），复用字幕优先/下载/本地ASR，不另造下载器；vxtiktok规范到tiktok，X规范到twitter，短链交原生解析。候选单独网页爬虫未采用，维护成本更高。本机没有HTTPS_PROXY，真实两站提取均失败；适配器单测不能替代可用代理下真链验收。

B档参考原始项目 https://github.com/jerryqx/dsh-xiaoyuzhou 与 https://github.com/weisi-gu/xiaoyuzhou-podcast-notes 的公开__NEXT_DATA__单集enclosure解析，采用自写小解析器接既有RSS音频处理，不引入整套项目。Spotify官方 https://developer.spotify.com/documentation/web-api/reference/get-an-episode 的audio_preview_url不是完整单集；仅接受明确公开完整音频，DRM/预览/无直链降级RSS，音乐拒绝。小宇宙179秒真实单集已出稿，Spotify真实请求降级；不是宣称Spotify全量转写已通。

C档实施前选定“自写认证/API/媒体编排 + MIT xhshow==0.2.0签名”，不vendor MediaCrawler小红书客户端。参考其原始client调用形态（https://github.com/NanmiCoder/MediaCrawler/blob/main/media_platform/xhs/client.py），核对签名组件 https://github.com/cloxl/xhshow 的原源码/安装wheel许可与依赖；仅签名复用，固定API白名单、Cookie流向、解析和下载由拾文控制。新增私有依赖xhshow及其pycryptodome传递依赖，旧core冻结。复用自有B站DACL/epoch生命周期、图集OCR，不读取/改外部采集器配置。网页登录profile自然保有本站会话；显式认证HTTP仅发edith.xiaohongshu.com，媒体请求无Cookie。视频本地ASR与图文OCR真实出稿；粤语混配乐样本错字明显，链路通过不代表语义准确率。证据：PLATFORM_EXTENSION_GUIDE.md、runtime/platform-extension-20261030/。


## 2026-10-30 复现表清零四项

说话人采用现有sherpa-onnx官方Python diarization API（https://github.com/k2-fsa/sherpa-onnx/blob/master/python-api-examples/offline-speaker-diarization.py），不引入torch/librosa；音频复用既有ffmpeg 16k单声道PCM。官方release列表显示中文/中英CAM++约28.3MB几乎相同，选择中英一个embedding搭配1.54MB INT8分段。固定官方release来源、本机实测哈希；无API digest不伪称官方校验签名。模型许可保留压缩包CNRS MIT与3D-Speaker源Apache文本（https://github.com/modelscope/3D-Speaker），不把整套模型统称SenseVoice许可。

XMind候选xmindpy现代格式实现（https://github.com/innotools/xmindpy）与官方SDK结构说明（https://github.com/xmindltd/xmind-sdk-js）作格式参照，不新增SDK依赖，标准库将既有验证树转JSON ZIP。首个ATools查看器选文件无显示，第二个Visora实际显示中文根节点/分支，保留反例与截图，不把ZIP检查冒充真实查看器。

合集复用organizer.request_json与cli_summary文件锁，按指纹缓存与来源ID校验，长文逐块归纳/归并而非截断；不新增调度体系。真实2次中第1次引用格式拒绝、第2次生成，缓存零调用；首个失败usage缺失如实标注，不补烧调用取数。频道字段只采集平台已提供值，不自动联网回填旧稿。对应源码diarization/setup_speakers/xmind_export/collection_summary，操作和证据见ZERO_GAP_GUIDE.md。
