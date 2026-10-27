# 云端 MVP · 可部署版本（2026-10-27）

状态：用户明确尚无 Cloudflare/Supabase 账号，先交付可部署版本。没有生产 URL，未创建云端项目、迁移真实数据库或调用付费模型。基础提交为 7aca7d6；本轮仅新增 cloud/ 和根目录说明/挂账，不改本地产品逻辑与真实数据。外部 HANDOVER_20261026.md 未动。

## 交付

独立 React/Vite 页面、Cloudflare Worker、Supabase 首次迁移、PowerShell 部署脚本。上传最长5分钟/20MB音频，浏览器解码并生成30秒独立16kHz PCM WAV，服务端按字节核验时长和时间轴；成功分段缓存；一轮结构化调用生成摘要/要点/导图，本地 Markmap 渲染，Markdown与无需网络的可折叠导图HTML导出。分享为随机256位令牌，库中只存哈希；默认不含原稿，可更新/撤销，不开放匿名模型调用。

后端验证正式 Supabase 用户身份；生成物浏览器只读。数据库事务控制账号3份、IP每日6份、全站每日40任务/1200秒转写尝试/12次文本调用，日界为UTC；重试最多2次，失败仍保守保留尝试预算，不声称退款。音频不持久化，不启用R2；服务端密钥经隐藏输入和stdin上传，不进入前端或Git。

每日Worker Cron实际查询Supabase并记录时间，满足前30天每天访问的实施约束，但配置未部署时不能说已经执行。页面明确云端数据流及敏感资料限制。免费档/额度内基础设施不等于整月零费用，SiliconFlow仍按量收费。

## 最终工程证据

- `powershell -NoProfile -File tools/deploy.ps1 -PrepareOnly`：完整执行npm ci、26项测试、TypeScript检查、Vite构建和Worker dry-run，通过。测试覆盖音频片段独立解码头/尾段/时长、流式大小限制、登录与匿名身份、跨账号、缓存、配额拒绝、结构化生成/截断失败、HTML转义、分享范围与撤销、真实数据库访问的调度路径；页面测试覆盖登录、同意、分段顺序、分享及错误状态。
- 前端最终产物：主JS 433.22kB/gzip125.74kB；导图依赖77.40kB/gzip26.41kB；导图组件按需加载。Worker dry-run：19.66KiB/gzip6.30KiB。
- 原生PostgreSQL16：在忽略的runtime/cloud-validation-pg隔离集群、127.0.0.1:55437的cloud_acceptance库运行bootstrap/schema/schema.test.sql，RLS、原稿只读、RPC权限、跨账号、缓存不扣额、未完成拒绝生成、失败重试上限和过期租约全部通过。并发脚本8路申请精确放行3路，5路TRIAL_LIMIT，IP计数3。测试集群已停止；没有使用真实data/tasks.sqlite3。
- 本地真实HTTP：Worker health 200且configured=false；jobs/config在未配置时503，前端HTML200。没有凭据时关闭生成，不以mock结果伪装云端成功。
- `npm audit --audit-level=moderate --registry=https://registry.npmjs.org`：0 vulnerabilities。初始Wrangler4.152.0传递undici有已知漏洞，已更新锁版4.153.0。55项生产npm包许可及Markmap内置d3-flextree许可附public/THIRD_PARTY_LICENSES.txt，缺失项0。
- 首次重复准备在Vite/Wrangler运行时遇到Windows esbuild文件锁；已停止本轮开发进程后重新完整执行成功，README记录先停止开发进程。CLI whoami无账号会返回文本成功码的问题已改用`--json`，未登录会在输入Secret前退出。

## 待外部验收

挂账引用 AGENTS.md。没有云端账号，真实Supabase Auth/SMTP或OAuth、Cloudflare部署、真实中文5分钟音频质量、真实模型schema支持、分享链接、手机/iOS、30天每日访问和账单均未验证。Chrome窗口最小化，工具不能取得可操作窗口，本轮DOM组件与HTTP测试不替代视觉验收。原生PostgreSQL的RLS证明不替代Supabase真实两账号联调。

尚无在线支付和用户商业验证；邮件公开注册需要配置正式SMTP/域名或启用OAuth，不能依赖Supabase默认邮件服务。平台免费政策与中国大陆网络可达性以实际账户和设备为准。上线前由用户确定公开服务主体、联系渠道和适用的隐私/内容规范；现有页面说明不是法律合规结论。

## 审查请求

请ZCode审查本轮7aca7d6至最终提交：重点为前端独立切片、服务端时长校验、身份来源、service_role与RLS边界、并发额度/租约、分享默认范围与撤销、内容转义及部署Secret路径。已知未验证项如上；实现方不自行宣布独立审查通过。
