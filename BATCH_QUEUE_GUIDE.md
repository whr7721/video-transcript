# 批量链接队列 · 私有版（2026-10-29）

## 使用

重启自己的app.py，打开 `/studio/`，展开“批量链接队列”。一行一条，支持YouTube/B站/抖音/RSS混合，每批1—50条；分享文字也可。先预览，再确认开始。RSS先选单集并更新预览，不会默认下载整个Feed。无效行独立标识；同一任务身份重复行去重，重复项的整理选择合并到首项。

勾选整理时，预览显示“约2×N次请求，当日配额剩余M”；可逐篇取消整理，再更新预览。预估保守，不扣额度，也不预留请求；缓存可能减少实际调用。超额提示：**转写将完成、整理需次日或减少勾选**。

转写与整理分开派发。额度不足仍完成转写，保留为“等待整理”；运行期间额度恢复时继续。真正请求仍由现有共享每日限额保护；与其他功能竞争额度时若被上限拒绝，该项回到等待整理。模型内容失败、Key或服务错误独立显示，支持仅重试失败项，不掩盖为成功。没有增加任何免费额度或重置真实账本。

控制：暂停后续派发、继续、停止未开始项、重试失败项。正在运行项正常收尾；已排队且仅归该批次所有的项会取消执行，若已有单条请求/其他批次引用则只停止本批引用，不取消共享任务。已停止项不自动恢复。服务重启时未结束批次暂停，手动继续；中断项重用原稿和成功阶段缓存。

随时下载已有成果ZIP：每篇“序号＋标题＋任务ID”目录，含已有TXT/JSON/SRT、已存在的摘要与离线导图。`batch-manifest.json`记录每行状态、任务/工作流引用、实际文件和缺失文件。没有生成的文件不会为导出额外调用模型。重复行仅列清单，不重复拷贝；不包含媒体、Cookie、数据库或浏览器目录。

## 实现

- `link_batches.py`仅注册到app.py。SQLite专用link_batches表保存批次及有序引用；复用既有tasks/generations与缓存，不复制文稿。
- `link_jobs.submit`抽为单项服务，Web单条和批次共用。单条处理中追加整理需求不会被丢弃；进度保存保留追加标志，结束决策加锁。免费引用不因共享付费整理失败而失败。
- 新增轻量派发线程，只做协调，不执行下载/ASR/LLM。各批次轮转，每次只派发一项；与单条共用既有唯一媒体worker，全局重任务并发1。已有单条排队时不继续塞入批次任务。旧博主批量功能不重写。
- 来源预览不会创建单项任务或触发模型/下载；仅RSS预览读取Feed。确认后引用/创建单项任务。跨批引用已有活动/完成结果；失败项经相同服务恢复。
- 整理先计算cli_summary当前指纹缓存需0/1/2次请求，再检查剩余配额；实际请求与成本账本仍走原链，预估不替代服务端限额。无新增依赖。
- 新UI通过SourceUI私有插槽接入；原单条和文档保留。批次面板可收起，展开时限制高度滚动。客户ZIP继续冻结，本轮不构建、不验证、不维护。

## 验证与证据

真实隔离服务：http://127.0.0.1:8781/studio/ 。数据在runtime/batch-20261029/data，未改原8765服务，未向真实data写夹具。所有测试素材、导出ZIP与模拟额度仅在runtime。

真实六行混合批次：四平台各一条、重复一条、无效一条。结果4完成、0失败、1重复、1无效（批次partial表示无效输入存在）。四项执行阶段时间不重叠；YouTube字幕快路，B站/抖音/RSS本地ASR。B站本次隔离目录未登录，匿名回落符合预期，不代表登录快路回退。

真实ZIP：13个成员（12个原稿文件＋清单），六行清单齐全，CRC通过。证据：`runtime/batch-20261029/acceptance.json`、`completed-batch.json`、`real-export.zip`。

配额实验明确是**runtime夹具**：隔离账本模拟当日已用30次，第二批引用两篇已有文稿，预估4次、剩余0；两项等待整理、零失败，复用原单项job_id，全部transcript.*哈希不变。本轮没有真实模型收费请求。证据：`quota-cache-acceptance.json`。该模拟不是真实消费，不复制到正式数据。

实际重启隔离服务后，等待整理批次变paused，引用与等待状态保留；没有自动重放模型请求。证据：`restart-acceptance.json`。预览环境保留模拟额度用尽，供ZCode核对警告与手动继续；不要把它当正式账号额度。

后端74项回归、前端73项测试及私有build通过。覆盖去重、RSS选择、轮转、全局忙碌、跨批引用、处理中补整理、低配额等待、共享失败隔离、停止任务归属、重启恢复及部分导出。

```powershell
.\.venv\Scripts\python.exe -X utf8 -m unittest tests.test_link_batches tests.test_bilibili_auth tests.test_link_jobs tests.test_shiwen_cli tests.test_cli_summary tests.test_core tests.test_local_files tests.test_podcasts -q
npm.cmd --prefix frontend test -- --reporter=dot
npm.cmd --prefix frontend run build
```

## ZCode交接与边界

- 浏览器交互、中文输入法、手机宽度预览/任务结果点验与截图按用户安排交ZCode，测试/HTTP不替代GUI。
- 在8781/studio/展开批量面板可查看真实完成批次与额度夹具批次；选两条已存在链接、勾选整理并预览，可见约4次/剩余0及超额提示。不要移除额度夹具后触发真实付费调用作为GUI验收。
- 本轮未重新真实收费生成摘要；批量引用现有cli_summary，恢复/配额路径用受控测试覆盖，不宣称模型质量新增验收。
- 并发固定1，本轮不开放任意调高，也不做Feed订阅、分享、视觉分析、外部笔记直写或新CLI/MCP功能。
- 其他长期挂账沿用AGENTS.md；用户已确认B站登录单审查通过，字幕快路挂账解除，POSIX/GUI两项仍保留。

## 调研取舍

沿用现有串行媒体队列和标准库，不引入外部任务服务。Python queue保证线程间任务交接；ZIP使用相对arcname及固定产物白名单，避免把绝对路径或运行素材打入包：https://docs.python.org/3.12/library/queue.html 、 https://docs.python.org/3.11/library/zipfile.html 。状态提示按WAI使用可感知的文本、status/alert，不靠颜色：https://www.w3.org/WAI/WCAG22/Understanding/status-messages.html 。
