# 思维导图里程碑（2026-10-27，待独立审查）

用户确认方案见 MINDMAP_PLAN_20261027.md。音视频与 RSS 原文工作台增加按需生成、只读导图页签、拖拽缩放/折叠/大图、文字大纲与 PNG/Markdown 导出；文章和图文入口暂未接入。原稿、编辑稿不随生成修改。

采用 DSH 备份中的树结构与现有 organizer 框架，重写边界验证、缓存和接线。原稿上限 24000 字，输出最多 80 节点、4 层、每标签 40 字；超限失败而不裁剪。结构化 schema 限定生成分支，另做独立校验。缓存按任务、原稿 hash、模型和提示版本匹配，修改编辑稿仍复用结果；失败保留上次成功结果，重试需显式点击。公开模式新增 mindmap action 共用 editorial 配额，其他付费 action 的公开保护范围没有扩大。

渲染复用本地锁版 markmap-view 0.18.12 / markmap-common 0.18.9（MIT），比较后暂缓 G6 和 simple-mind-map。标签转义、组件按需加载、无需 CDN；导出展开整棵树并重建纯 SVG 文字，避免 foreignObject 栅格化与 CSP blob 图片限制。XML 序列化重复 xmlns 问题已通过解析测试发现并修复。Markmap/D3 与内置 d3-flextree（WTFPL v2）许可已附包；官方 npm registry 的生产依赖 audit 为 0 漏洞。

## 工程证据

- `PYTHONPATH=runtime/public-quota-tools .venv/Scripts/python.exe -m pytest tests/ -q`：236 passed，36.44 秒；一条现有 Starlette/httpx 弃用警告。
- `cd frontend; npm test -- --run`：13 文件、62 测试通过，含缓存重开、显式重试、不可用状态、大图开关、转义/完整树 XML 与工作台集成。
- `npm run build`、`npm run build:core`：通过；导图库独立块 72.66 kB，gzip 24.66 kB。
- `.venv/Scripts/python.exe -X utf8 build_core_package.py`：95 文件，白名单、清单和解包校验通过；候选包在忽略的 runtime/k1-production/package/shiwen-core-k1.zip。构建于提交前，不将其元数据误称为最终干净提交构建。
- 隔离 HTTP：文档及指定任务导图 Markdown 均 200，Markdown 附件 2627 字节；原 CSP 保留。

## 真实模型验证与预算

沿用原累计 10 元开发账本，不重置额度。最终 schema 版本：真实 1282 字短稿生成 61 节点，8.593 秒，输入/输出 1029/807 token；23000 字真实文稿合集生成 63 节点，14.797 秒，输入/输出 13311/1074 token。合集明确不是单篇长音频质量样本。缓存重跑返回相同任务 ID，未增加模型调用。

共做 6 次付费尝试：早期长稿出现 134 节点/5 层而被拒绝，另一轮输出截断失败，随后改用有界 schema；运行时没有自动付费重试。累计账本 36 次、预留累计 8.57 元、已知估算 0.608984 元；截断请求未返回 usage，仍保留预留，估算不作为账户账单。运行素材、候选输出与账本均仅存忽略的 runtime，未纳入 Git。

## 用户页面验收

人工验收挂账见 AGENTS.md；用户已明确“验收我来”，尚不声称浏览器交互或 PNG 实际通过。

隔离无 Key 预览：http://127.0.0.1:8776/studio/?task=9b9a219360ac23c5 （已有缓存，不需再生成）。23000 字合集任务参数为 bbbbbbbbbbbbbbbb，原 8765 服务未动。

1. 打开“思维导图”页签，检查内容覆盖与大纲。
2. 拖拽、缩放、折叠/全部展开，打开并关闭大图。
3. 导出 PNG，检查中文、换行、完整展开树与边界；对照 Markdown。
4. 刷新重开确认缓存仍可用；按实际使用设备点验布局。

独立审查应覆盖 c817f51 至本里程碑最终提交，重点看原稿不变、缓存身份/版本、异常与限额、公开 quota、标签安全及全树导出。写码方不自行宣布审查通过。

## 审查反馈处理（2026-10-27）

用户转达 P3：真实库残留一条开发孤儿任务。核实 task_id=eeeeeeeeeeeeeeee 在 tasks 中不存在，generation=dbf5e02d7a078467 为 failed mindmap/mock 数据。先将原行备份到忽略的 runtime/mindmap-orphan-cleanup-20261027，再在 BEGIN IMMEDIATE 事务中按 id 和原 payload 精确删除一行；事务内逐表比较确认其余所有记录不变。此清理未改额度、预留或用户内容。此前“运行素材仅存 runtime”的表述不涵盖这条已确认的早期违规遗留；本次明确纠正，并在 AGENTS.md 加入进程启动前隔离要求。

用户同时确认旧账：第18单 P2-1 unittest discover 兼容问题、第18单 P2-2 其他付费 action/chapter-jobs 公开保护缺口、第17单 P3 限额拒绝仍烧预留，均未在本次修复。遗留错误显示共享每日限额实际拦截过该开发调用，不因此清零或返还账本。人工页面验收状态仍引用 AGENTS.md。
