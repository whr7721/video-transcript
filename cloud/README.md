# 拾文云端版 MVP

独立的 Cloudflare Pages + Workers + Workers AI + Supabase 应用。仅收音频文件，不含本地采集、MediaCrawler、本地数据库或用户素材。当前为可部署源码，**没有账号时不等于已上线**。

## 已实现范围

登录 → 浏览器独立 WAV 切片 → 云端中文转写 → 摘要与导图 → 离线 HTML/Markdown → 可撤销分享。首版 5 分钟、20MB；音频只经过处理、不持久化存储。转写原稿只读。默认分享摘要和导图，分享原稿需另行勾选。HTML 导出为无需联网的可折叠树，在线图形采用本地打包 Markmap。

每账号最多3份不同原文件；同一文件复用任务。每 IP 每 UTC 日最多6份新任务；全站每日最多40份新任务、20分钟实际转写尝试、12次文本生成。每个步骤最多2次显式尝试，网络失败可能已经消耗服务额度，不保证退款；成功结果缓存，重复请求不再调用模型。所有计数由数据库事务控制，客户端不能指定用户身份或直接修改生成物。

## 开通与部署

需要 Node.js 22.12+、npm、免费 Cloudflare 账号、一个**新建的** Supabase 免费项目、可用的 SiliconFlow Key。不要把 Key 发到聊天或提交到 Git。

1. Supabase SQL Editor 执行本目录 `schema.sql`。仅在新项目执行；它是首次建表迁移，重复执行会明确失败，不会自动覆盖现有数据。不要执行 `tests/bootstrap.sql`，该文件仅用于隔离的本机 PostgreSQL。
2. Supabase Auth 配置登录。邮箱公开注册需正式 SMTP（例如 Resend，另需域名）并开启邮箱确认；默认内置邮件服务不适合公开注册。可先通过 Supabase Dashboard 邀请/创建已确认的体验账号，或配置 GitHub OAuth；不要为省事关闭邮箱确认后开放注册。开启提供商侧验证码可进一步减少注册滥用。
3. PowerShell 进入本目录，执行：

```powershell
npm ci
npm exec wrangler -- login
powershell -NoProfile -File tools/deploy.ps1 -SupabaseUrl 'https://项目ID.supabase.co' -SupabaseAnonKey '公开anon或publishable key'
```

脚本会运行测试、构建、核验表、隐藏输入两个服务端密钥、上传 Worker Secret、发布 Worker、构建生产前端并发布 Pages。默认项目名 `shiwen-cloud-whr7721`，可传 `-ProjectName` 改成自己的唯一名称；只对这个名称创建/更新，不操作其他项目。不要启用付费自动升级。若账户需要选择，先设置 `CLOUDFLARE_ACCOUNT_ID`。首次 Worker subdomain 开通可能需在 Cloudflare Dashboard 完成。

4. 把脚本输出的 Pages 网址填入 Supabase Auth 的 Site URL 与 Redirect URLs；GitHub OAuth 回调按 Supabase 页面给出的 URL 配置。配置 SMTP 后才邀请公众自行注册。Pages 预览网址不在 API CORS 白名单内，使用脚本输出的正式 `*.pages.dev` 地址。
5. 登录自己的两个体验账号，完成下方验收后再邀请真实用户。Supabase 账号密钥、GitHub OAuth secret、SiliconFlow Key 不得出现在前端构建产物。

只有构建包，不接云端（Windows 下先停止本目录的 Vite/Wrangler 开发进程，避免 npm ci 遇到运行中二进制文件锁）：

```powershell
powershell -NoProfile -File tools/deploy.ps1 -PrepareOnly
```

本地联调：将 `.dev.vars.example` 复制为忽略的 `.dev.vars` 并填测试项目凭据；一个终端 `npm run api:dev`，另一个 `npm run dev`。本地 localhost 和127.0.0.1:5173仅供开发；真实部署脚本使用精确生产域名。测试数据必须在独立云项目或 runtime 隔离目录，不接本地真实 data/。

## 四条约束

- 在浏览器解码、降采样到16kHz单声道，再按30秒编码为每段完整 WAV，非字节截断、非 MediaRecorder timeslice。服务端解析固定 WAV 头并按 PCM 长度验证时长；不信任前端 offset。原始格式是否能解码依赖浏览器，失败会明确提示，不会静默截取。
- 页面明确告知 Cloudflare 转写、SiliconFlow 文本处理和 Supabase 数据存储；不宣传本地隐私。勿上传敏感、未经授权的材料。
- Worker Cron 每天 UTC 02:17 查询真实数据库并记录 `cloud_maintenance.last_success`；部署后应核实连续成功，失败在 Worker 日志可见。这是保活/健康检查，不保证免费项目永不暂停。首30天每日访问为上线必验项。
- 无匿名生成；校验 Supabase 正式用户，拒绝 anonymous auth，原子限制用户/IP/全站额度。分享访客只能读被主动分享的内容，不能生成或获取其他数据。

## 费用边界

基础设施以免费档和预算内验证为目标，**不是整月零账单承诺**。Workers AI 每天10,000 Neurons为账户共享额度；全站20分钟是保守应用限额，不代表官方可用余量，账户其他任务也会消耗额度。SiliconFlow 文本调用按量付费，域名/正式邮件也可能收费。达到应用额度即拒绝，不自动升级。上线后记录实际后台用量，满一个月后才能核对整月账单。

## 验收与审查

- `npm test`；`npm run build`；`npm exec wrangler -- deploy --dry-run`。
- 本地原生 PostgreSQL 16 已验证 RLS/只读源/RPC权限/额度/租约/缓存及8路并发；脚本在 `tests/`，只能指向隔离测试库。
- 两个真实 Supabase 账号互不可见；未登录、伪造user_id、跨账号访问、超时重试与重复请求。
- 5分钟中文音频全文/边界、摘要、导图；超大/空/不支持文件；中断后重新选择原文件恢复。
- 分享默认不含原稿；更新链接使旧链接失效；撤销后不能再次读取；已下载副本不能收回。
- HTML 真正离线打开；手机浏览器解码/阅读/导出，特别是 iOS Safari，必须实机验收。
- Cloudflare/Supabase/SiliconFlow实际调用、连续每日数据库访问、真实账单另行核验。本地mock测试不证明真实模型质量。

当前证据与待验项见 `MILESTONE_20261027.md`。实现方按项目协议提交审查请求，不自行宣布独立审查通过。

参考：[Workers AI模型与响应结构](https://developers.cloudflare.com/workers-ai/models/whisper-large-v3-turbo/)、[计费](https://developers.cloudflare.com/workers-ai/platform/pricing/)、[Supabase Auth邮件](https://supabase.com/docs/guides/auth/auth-smtp)、[生产可用性](https://supabase.com/docs/guides/deployment/going-into-prod)、[W3C分段录制限制](https://www.w3.org/TR/mediastream-recording/)。
