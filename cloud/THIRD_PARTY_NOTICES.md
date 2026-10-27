# 第三方说明

本云端源码不包含本地采集模块、模型权重或FFmpeg/ffmpeg.wasm。音频通过标准Web Audio API解码并自行编码PCM WAV；源格式的解码能力来自用户浏览器。

生产前端使用React/ReactDOM 19.2.0（MIT）、Supabase JS 2.118.0及其传递依赖（许可随包）、Markmap view 0.18.12/common 0.18.9（MIT）、D3（ISC）及内置d3-flextree（WTFPL v2）。精确版本与所有传递包见package-lock.json；生产许可文本附public/THIRD_PARTY_LICENSES.txt并随前端发布。开发工具Wrangler、Vite、TypeScript、Vitest和测试工具不进入生产页面，但源代码和npm包仍适用各自条款。

Cloudflare Workers AI、Supabase、SiliconFlow及登录/邮件提供商分别适用其服务条款和数据政策，不能以本说明代替账户协议。Cloudflare托管Whisper不在此包内分发权重。本项目自身尚未通过本文件授予新的公开开源许可。
