# 拾文文稿工作台：复用调研与实施方案

日期：2026-10-19。状态：**用户已确认并开始实施。编辑工作台及5GB缓冲已接入；见README与VALIDATION中的实际验证记录，下面保留原方案及选型依据。**

## 1. 目标与范围

用户最新方向是偏AI应用，以真实使用和效率为优先：链接→原稿→整理编辑→确认稿，之后再做图文输出。ASR纠错与评测保留为支线，不作为本阶段必须完成的研究项目。

本阶段做：保留不可变原稿、手动编辑、基础排版、自动保存/恢复、按需整理段落/摘要/金句、来源核对、文稿确认和TXT/Markdown/JSON导出，及已确认的5GB媒体缓冲。

图文排版与图片导出是下一阶段；本阶段只让文稿结构可延续使用，不提前安装画布/海报渲染依赖。暂不加多人协作、账户体系、复杂Agent编排或模型训练。

## 2. 已使用的技能与项目约束

- frontend-design：先形成颜色、字体、布局与交互原则，再实施和视觉复查。
- ui-ux-pro-max：已运行设计系统查询及保存状态UX查询。首轮结果混入营销页结构，随后具体文稿编辑检索无命中；**不把它当作已验证的编辑器模板**。采纳符合任务的可见焦点、异步状态、对比度、响应式及反馈原则，保留现有品牌，由真实编辑器源码与产品案例补足布局。
- web-design-guidelines：已读取最新原始规则，后续审查新增界面和实际交互，尤其输入法、自动保存、焦点、语义和窄屏。
- Sites：按local-only工作流沿用当前checkout，不注册/部署云端Site。本地浏览器会话、模型和媒体仍在电脑上，不能只上传静态页就得到完整在线服务。

当前是FastAPI+SQLite+原生HTML/CSS/JS，没有React工程。已检查本机Node v26.4.0/npm11.17.0可用；这只说明有构建工具，不代表新栈已安装或构建验证通过。

## 3. 推荐架构及备选

**推荐：React + TypeScript + Vite + Tailwind CSS + shadcn/ui（Radix变体）+ Tiptap；后端继续FastAPI + Pydantic + SQLite。**

新增编辑区涉及活动文稿、原稿/整理稿、异步生成结果、版本保存、来源回听与未来图文预览，适合组件化；React可直接接入已核验的编辑器、可调整分栏及界面组件。引入构建链有成本，但能减少后续大量界面交互的手写维护。

| 路线 | 优点 | 成本与限制 | 决策 |
|---|---|---|---|
| React/Vite + shadcn + Tiptap | 组件、编辑器及分栏复用完整；后续卡片编辑可延续 | 新增前端构建、TS和依赖维护；需迁移部分UI | **推荐**，先只做独立编辑入口，回归后再整合导航 |
| 保留原生JS + Tiptap vanilla | 对当前页面改动小，同样能用编辑内核 | 多面板/异步版本状态仍要手写；shadcn React组件不能直接照搬 | 轻量备选，不同时维护两套完整新UI |
| 整套Next.js/全栈模板 | 可用大量网站模板 | 当前不需要SSR、登录/云后端；与FastAPI重复 | 本阶段不采用 |

开发时前端构建输出静态文件，由现有本地服务同源提供；不为使用编辑器另起一个长期Node后端。生产运行不依赖外部CDN、字体服务或远程编辑器。

## 4. GitHub候选核验

### 4.1 编辑器：核验4种

| 候选 | 已阅读的原始材料 | 功能匹配与接入成本 | 许可/依赖 | 结论 |
|---|---|---|---|---|
| [Tiptap](https://github.com/ueberdosis/tiptap) | core/react package.json；StarterKit源码；UniqueID源码及manifest；Markdown包manifest；官方React/vanilla文档 | 有标题、段落、列表、引用、撤销重做；JSON文档、节点扩展可承载来源；React和vanilla都可用 | 核心、已核验UniqueID/Markdown为MIT；依赖ProseMirror；各Tiptap包必须同版本 | **采用开源部分**，UI独立设计；不假定收费AI/协作/审阅扩展免费 |
| [Lexical](https://github.com/facebook/lexical) | 核心package.json、LICENSE及发布资料 | 强编辑基础，支持JSON；需要自行组合更多行为与工具栏 | MIT；本轮核心版本0.52.0，仍需关注版本API变化 | 有效备选，首期不同时引入两套编辑器 |
| [Vditor](https://github.com/Vanessa219/vditor) | README、package.json、LICENSE | 中文Markdown友好、可直接嵌入；Markdown优先，对稳定段落来源与未来结构化卡片需要额外转换 | MIT；部分默认资源/渲染依赖要本地化并复查 | 若最终只要Markdown笔记更合适；本方案非首选 |
| [BlockNote](https://github.com/TypeCellOS/BlockNote) | core和xl-ai package.json | 即用块编辑体验较完整，但可见功能不能全部归入同一免费许可；包含较多本次不需能力 | core为MPL-2.0；xl-ai为GPL-3.0 OR PROPRIETARY；建立于Tiptap之上 | 首期不用，避免误把XL演示当免费组件 |

### 4.2 UI及逻辑工具

| 组件/工具 | 已核验来源 | 复用部分 | 注意点 |
|---|---|---|---|
| [shadcn/ui](https://github.com/shadcn-ui/ui) | LICENSE、官方Vite安装文档、Radix版dialog.tsx与resizable.tsx原始源码 | Button/Tabs/Dialog/Sheet/Dropdown/Tooltip/ScrollArea/Select/Progress等按需组件 | MIT。它提供可维护源码，不保证插入后自动达到最终视觉/无障碍质量。官方示例部分路径失效，未取得的Mail模板**不列为已确认可复用模板** |
| [Radix Primitives](https://github.com/radix-ui/primitives) | LICENSE、shadcn对其Dialog的真实调用 | 弹层、焦点和键盘交互基础 | MIT；仍测试标签、中文文案、焦点恢复、编辑器选区，不笼统宣称全面无障碍 |
| [react-resizable-panels](https://github.com/bvaughn/react-resizable-panels) | package.json、LICENSE.md、shadcn封装源码 | 面板尺寸调整、折叠、布局持久化适配 | MIT；本轮manifest为4.14.6、React18/19 peer。不要复制旧版PanelGroup API后配新版包 |
| [Lucide](https://github.com/lucide-icons/lucide) | LICENSE | 统一SVG图标、按需React图标 | ISC及部分继承图标MIT声明；保留上游许可，不使用emoji替代操作图标 |
| [jsdiff](https://github.com/kpdecker/jsdiff) | package.json、LICENSE | 原稿与整理稿文字增删对比 | BSD-3-Clause。只是差异工具，不能判定事实正确或恢复所有来源关系；只导入需要的函数 |
| Tiptap Markdown | 包manifest及同仓库编辑器结构 | Markdown解析/序列化，避免重写完整Markdown转换器 | MIT；对本产品支持的标题/列表/引用做往返测试，自定义来源属性单独留JSON |
| 现有httpx + Pydantic | 本机源码、requirements | 模型HTTP调用、服务端输出结构校验 | 已有依赖；先少量结构化任务，不新增LangChain/LlamaIndex/多Agent框架 |
| 现有SQLite/atomic_json | 本机store.py | 文稿、修订、任务和文件持久化基础 | 要新增业务表/版本规则；现有tasks payload不能直接当完备的文档版本系统 |

维护与安全边界：上游活跃度和源码版本只作为信号。本轮读到Tiptap3.30.3、BlockNote0.56.0、Lexical0.52.0、Vditor4.0.1等主分支manifest，不将其当作已安装的稳定组合。实施时从正式发布选择相互兼容版本、锁文件、检查依赖告警，安装/构建/输入法/保存验证通过才算接入。未运行npm audit，不能声称“依赖零漏洞”。

## 5. 复用数量：按15个功能模块清点

这是方案粒度清单，**不是未经测量的代码复用率或开发工时百分比**。目前完成的是源码/许可/功能匹配核验，新组件尚未集成。

| 编号 | 模块 | 采用方式 |
|---|---|---|
| 1 | 视频获取 | 复用现有MediaCrawler适配 |
| 2 | 音频处理/转写 | 复用FFmpeg、SenseVoice、现有分段和缓存 |
| 3 | API与结构校验 | 复用FastAPI、Pydantic及同源安全层 |
| 4 | 本地持久化 | 复用SQLite和文件基础设施 |
| 5 | 前端工程 | 采用React/TS/Vite成熟基座 |
| 6 | 标准UI交互 | 采用shadcn/Radix/Tailwind |
| 7 | 富文本编辑 | 采用Tiptap/StarterKit/UniqueID |
| 8 | 分栏交互 | 采用react-resizable-panels |
| 9 | 图标 | 采用Lucide |
| 10 | 文字差异显示 | 对jsdiff做薄封装 |
| 11 | 文稿导出 | 对Tiptap Markdown及既有下载接口做适配 |
| 12 | AI整理任务 | 对httpx/Pydantic做提示词、版本、缓存和失败处理封装 |
| 13 | 文稿/任务版本与确认 | 定制业务逻辑：草稿、自动保存、冲突、异步结果对应版本、确认状态 |
| 14 | 来源映射与摘录核验 | 定制业务逻辑：段落关联、原文位置、回听与原句一致性 |
| 15 | 5GB媒体生命周期 | 定制业务策略：保护引用、配额、满额暂停与清理 |

合计：**9类可复用基础（4类现有、5类新增成熟前端基础），3类适配封装，3类必须按需求定制的领域逻辑。**

## 6. UI设计方向

定位为“安静、精致的中文编辑工作台”。沿用拾文的纸白、雾蓝、强调蓝品牌；参考[Linear](https://linear.app/features)的信息密度和操作反馈、[Craft](https://www.craft.do/)对文档阅读的重视，仅借鉴原则，不复制私有代码、商标素材或整页设计。

颜色：背景#F6F8FC、纸面#FFFFFF、正文#17243B、辅助文字#637187、强调蓝#2855D9、分隔线#E3E8F1。正文17px起、行距1.8—1.9、舒适行宽；工具区13—14px，辅助说明至少12px。标题以层级和字重区分，避免大量大号数字、渐变卡片和装饰性动效。系统中文字体优先，不让外部字体请求影响本地可用性。

桌面结构：

```text
文稿库             文档标题 / 保存状态 / 确认 / 导出
                  原稿 | 整理稿
搜索与筛选         -------------------------  来源与整理结果
博主与批次         简洁编辑工具栏              来源 / 摘要 / 金句
文稿列表           主编辑区                   原文定位 / 音频回听
                  可折叠目录                 结果预览与采用
缓冲占用           整理段落 / 生成摘要 / 摘录金句
```

- 左侧220—240px可折叠；右侧约300—340px按需展开；编辑正文保持舒适阅读宽度，布局可调。
- 原稿只读；整理稿可编辑。摘要/金句在右侧预览，用户主动采用后进入稿件；不因生成完成就覆盖正在写的内容。
- 编辑器只保留标题、加粗、列表、引用、撤销/重做等高频项，选中文字时再显示局部工具。
- 状态明确：“保存中/已保存/保存失败”，可恢复；AI任务说明处理对象和版本，不以页面转圈代替反馈。
- 小屏切为单编辑区，文稿库/来源使用抽屉；不把三栏挤在手机上。分栏除拖拽外提供折叠/恢复和键盘入口。
- 首期只做精致的浅色主题；深色主题等主流程验收后再评估。高级感主要由排版、留白、层级和完整状态形成。

## 7. 内容与AI逻辑

数据主结构是可版本化文档JSON，不以随意HTML字符串作为唯一真值；至少区分原稿、编辑稿、生成结果与确认快照。Tiptap节点ID解决“块身份”，不自动解决“这句话来自哪里”；来源段ID和区间需要产品适配层维护。

第一期AI任务限三项，均由用户主动发起：

1. 整理段落：先预览分段/标题建议，承诺范围内尽量保留原字句；任何文字变化可对比，不声称自动忠实无误。
2. 生成摘要：短摘要和观点提纲，标为归纳结果，并能跳转支持它的原稿片段。结构校验通过不等于内容正确。
3. 摘录金句：由模型返回原稿区间/段ID，程序从原稿提取实际文字；匹配不到不作为原文摘录输出。与ASR原稿一致不等于已经人工确认原音正确，界面保留回听入口。

摘要可以归纳，原文摘录不能悄悄改写；跨段摘录要清楚标识省略。人工改写的块标为编辑内容。编辑后来源若不再精确，退回片段级参考或提示待核对，不继续展示伪精确逐字定位。

AI输入按实际模型上下文预算切分；输入/输出用固定schema，缓存键含原稿/编辑稿版本、模型、提示词与参数。结果回来时若文稿已变化，展示为基于旧版本的结果，不直接覆盖新版本。没有历史答案或人校稿泄漏进输入。

新增模型任务仍通过本机后端，Key保持DPAPI存储、不进入浏览器构建包。具体模型按价格、权限、质量实测后确定，不因为框架示例而默认接付费AI服务。当前用户预算偏好继续有效。

## 8. 5GB缓冲与文稿状态

用户已确认：5GB；先清理已完成流程素材，仍不足就暂停新下载，不删除待确认内容。这里“完成流程”调整为本阶段实际产品：原稿获取→整理编辑/可选择不做AI→用户确认最终稿→最终稿持久化；不强制等待未来图文功能，也不把下载文件作为完成的必要条件。

正在处理、待确认、正在回听、失败重试与评测固定引用均受保护；最终稿和修改记录永久保存。只清理工具登记的临时媒体。既有“保留原视频”如代表永久保留，需要明确固定为受保护状态；不能被通用LRU误删。

通用缓存库的自动淘汰无法理解这些状态，因此不直接让缓存库自行删媒体。可复用SQLite事务、文件流、磁盘统计，但配额与生命周期策略需要定制并测试。当前转写成功即清理的代码尚未替换。

## 9. 实施顺序与验收

| 阶段 | 交付 | 验收重点 |
|---|---|---|
| 0 视觉与接入原型 | 新工作台入口，加载一份真实文稿，只读原稿+编辑稿区域 | 先确认布局、中文可读性和操作路径；不改动既有转写/历史文稿 |
| 1 数据与缓冲 | 5GB台账、文稿修订、确认状态、来源段标识 | 满额保护/等待恢复；重启一致性；迁移仅触及登记文件 |
| 2 手动编辑闭环 | Tiptap、自动保存、撤销重做、版本恢复、基础导出 | 中文输入法组合输入不被轮询/自动保存打断；粘贴、长文、切文稿、刷新不丢字 |
| 3 AI整理 | 三类按需操作、预览采用、来源跳转、失败重试 | 金句区间严格匹配；异步版本冲突不覆盖；摘要与原文标签清楚 |
| 4 整体验收 | 新工作台与现有单条/批量入口整合、旧深链接兼容 | 现有17项回归；新增保存/配额/AI契约测试；浏览器视觉/键盘/移动端验收 |

依赖门槛：正式包版本一致并锁定，生产静态构建成功，许可声明保留。依赖审计有告警时按真实可利用面处理，不声称装好包就可靠。

体验验收使用5/15/30分钟真实稿，记录人工整理耗时、改动量和生成结果采用率；不预先承诺效率百分比。浏览器验收覆盖375/768/1440px、输入法、焦点、抽屉、分栏、保存错误、旧版AI结果与回听失败。当前浏览器工具曾无法访问本地标签；如果实施时仍不可用，会明确留下视觉验收项，不用API检查代替截图验收。

## 10. 来源索引

- Tiptap：[仓库](https://github.com/ueberdosis/tiptap)、[React接入](https://tiptap.dev/docs/editor/getting-started/install/react)、[vanilla接入](https://tiptap.dev/docs/editor/getting-started/install/vanilla-javascript)、[StarterKit源码](https://github.com/ueberdosis/tiptap/blob/main/packages/starter-kit/src/starter-kit.ts)、[UniqueID源码](https://github.com/ueberdosis/tiptap/blob/main/packages/extension-unique-id/src/unique-id.ts)、[Markdown包](https://github.com/ueberdosis/tiptap/tree/main/packages/markdown)。
- UI：[shadcn Vite接入](https://ui.shadcn.com/docs/installation/vite)、[Dialog源码](https://github.com/shadcn-ui/ui/blob/main/apps/v4/registry/new-york-v4/ui/dialog.tsx)、[Resizable源码](https://github.com/shadcn-ui/ui/blob/main/apps/v4/registry/new-york-v4/ui/resizable.tsx)、[Radix](https://github.com/radix-ui/primitives)、[面板库](https://github.com/bvaughn/react-resizable-panels)、[Lucide](https://github.com/lucide-icons/lucide)。
- 对照：[Lexical](https://github.com/facebook/lexical)、[Vditor](https://github.com/Vanessa219/vditor)、[BlockNote core](https://github.com/TypeCellOS/BlockNote/blob/main/packages/core/package.json)、[BlockNote XL AI许可](https://github.com/TypeCellOS/BlockNote/blob/main/packages/xl-ai/package.json)、[jsdiff](https://github.com/kpdecker/jsdiff)。
- 质量：[Web Interface Guidelines](https://github.com/vercel-labs/web-interface-guidelines/blob/main/command.md)。

复用范围是可核验的开源核心、组件和现有工程；未把搜索摘要、失效模板路径、付费演示或未测包体积当作接入事实。
