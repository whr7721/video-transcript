# Web 链接入口 · 2026-10-29

本轮主线为自用 app.py 全平台；app_core 仅 YouTube/RSS。未实现批量、Feed 订阅、AI追问、分享或视觉分析。

## 使用

进入 `/studio/`，在首页输入链接或整段分享文字，Enter提交（Shift+Enter换行、中文输入法组合期间不提交）。RSS先读取单集列表再选一集。进度卡支持失败重试；完成后打开既有文档编辑区。可勾选同时整理，也可在文档详情点击“整理与离线导图”；原稿本地免费，整理复用cli_summary的两阶段模型请求、共享每日配额及缓存。支持预览summary.md和下载摘要、离线单文件导图。

原有首页 `/` 的批量管理保留；本轮新入口位于编辑工作台 `/studio/`。私有服务8765未重启；隔离验收服务为 http://127.0.0.1:8778/studio/ ，数据在 runtime/link-web-20261029/data。

## 架构与边界

- shiwen.py为薄CLI。link_ingest.py共用识别、字幕优先、RSS单集、下载、转写和产物导出；JSON保留subtitlesArray、cover、duration、publishedDate。
- link_private.py显式注册私有抖音适配器与B站字幕补充；不复制pipeline/session的登录态机制。客户ZIP不含该模块或pipeline/session/extractor。
- link_jobs.py将工作流存于generations，action=link_ingest，保留task_id/arguments/stages。媒体仍由各入口既有串行队列执行，无新增媒体线程池。organizer恢复跳过此action，链接自己的恢复将中断任务标失败等待显式重试，旧队列不会自动接管。
- 来源source.kind=link，source.platform明确平台；稳定文稿ID继续兼容CLI。future批量可引用这些单项任务，Feed可引用单集identity，追问/笔记/资料库沿用现有task_id与sources，不提前建立新系统。
- 转写产物存在时整理重试只补整理，保留已成功阶段和transcript.*。同链接重复提交返回缓存。RSS仍需读取Feed以核对当前单集identity，本机缓存返回约1.4秒，其余约4毫秒。
- RSS音频原来经yt-dlp generic遇到TLS EOF；现复用已有article_fetch.stream下载（分块写入part文件、1GB限制、完成后rename），CLI和Web同时受益。视频仍用yt-dlp。
- 旧core包“douyin字节即拒绝”的检查与显式不支持提示/共享识别器冲突。新构建使用link_profile检查：允许平台名称，仍禁止私有实现文件、MediaCrawler字节和链接文件；旧默认严格检查保留。客户包实际独立启动验证未导入私有模块。无AST删分支。
- requirements.lock.txt补齐既有yt-dlp==2026.10.26、yt-dlp-ejs==0.8.0，与现有requirements.txt一致；无新增第三方库。

## 验证证据

隔离根目录runtime/link-web-20261029；未向真实data库写夹具。本轮没有真实模型收费调用，摘要收费链沿用前单实测；本轮注入失败验证接线和原稿不变。

|真实输入|结果|字符/片段|阶段与缓存|
|---|---|---|---|
|YouTube jNQXAC9IVRw|文档HTTP200|217/6|publisher_subtitles，未出现downloading/transcribing；缓存4ms|
|B站 BV1GJ411x7h7|文档HTTP200|742/16|无字幕→下载→SenseVoice；缓存4ms|
|抖音 Dv4LnzQVp8E|文档HTTP200|1009/10|原只读隔离会话→SenseVoice；缓存4ms|
|NPR RSS 500005 第1集|文档HTTP200|4753/19|Feed→下载→SenseVoice；缓存1406ms|

机器结果：acceptance.json、live-results.json、bili-subtitle-probes.json、customer-smoke.txt，均在隔离根目录。

- 后端67项通过：`.venv/Scripts/python.exe -X utf8 -m unittest tests.test_link_jobs tests.test_shiwen_cli tests.test_cli_summary tests.test_customer_package tests.test_distribution tests.test_core tests.test_local_files tests.test_podcasts -q`。
- 前端69项通过：`npm.cmd --prefix frontend test -- --reporter=dot`；包括capabilities、IME Enter、结果打开和失败重试。
- 私有/核心前端分别build、build:core通过。
- 新客户ZIP解包后在独立进程启动app_core：capabilities仅youtube/rss；Web贴抖音明确400“此版本不支持抖音链接”，B站400；私有模块导入数0。
- 摘要失败/重试测试逐字节比较transcript.*，禁止再次下载/ASR；恢复测试确认organizer不接管链接任务。

## 未验证项与ZCode交接

1. B站真实有字幕快路未完成：三个匿名接口样本均返回空轨；不引入本单明确排除的B站cookie。字幕分支有自动测试，YouTube真实快路有阶段记录，但不能替代B站真实验收。
2. 浏览器交互、移动宽度输入态/结果态两张截图按用户要求交ZCode。访问8778/studio/，点击已有四个平台文稿；验证中文Enter、RSS选择、失败重试、摘要下载与手机宽度。不是GUI已验收。
3. 本轮未再次真实付费生成；整理沿用既有cli_summary链。本轮测试不冒充模型质量验收。
4. 其他长期挂账见AGENTS.md，本轮不扩大公开模式保护范围。

客户包：runtime/link-web-20261029/delivery/shiwen-windows-customer.zip。开发机隔离解包接口验收不替代全新Windows安装验收。
