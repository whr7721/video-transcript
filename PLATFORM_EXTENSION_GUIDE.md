# 平台扩展使用与验收（2026-10-30）

私有 `app.py` / CLI / 批量输入新增五个平台；仍共用link_ingest与既有任务体系，不新增订阅枚举。本单不是旧core客户包升级。

| 平台 | 使用方式及边界 | 实测 |
|---|---|---|
| TikTok | 视频完整链接、vm/vt短链、vxtiktok别名；yt-dlp字幕优先，无字幕本地ASR | 本机无HTTPS_PROXY，直连提取失败；未宣称真链通过 |
| Twitter/X | 视频推文链接；无视频明确提示“仅支持视频推文” | 同上，原生适配/错误区分单测覆盖 |
| 小宇宙 | 单集episode链接；公开页面完整音频→本地ASR；取不到则建议RSS | 真实179秒《字面量，变量》完成 |
| Spotify播客 | 仅episode；有明确公开完整音频才处理，预览/DRM/无直链建议RSS；音乐拒绝 | 真实单集请求返回400+RSS提示，未验证完整直链正向样本 |
| 小红书 | 设置→登录小红书→扫码→已登录，再贴完整分享链接或xhslink短链；视频ASR，图文OCR | 用户扫码一次，视频22段/454字、图文73字真实完成 |

## 操作

安装私有依赖：`.venv/Scripts/python.exe -m pip install -r requirements-private.txt`，首次浏览器安装：`.venv/Scripts/python.exe -m playwright install chromium`。原有MediaCrawler依赖/模型约定不变。新依赖仅MIT xhshow==0.2.0用于签名，传递依赖pycryptodome；full构建已加入它及许可全文。旧core不注册这些私有功能，C档在白名单检查时拒绝，不触发认证。

重启自己的私有app后，首页粘贴单条链接，或批量页按行粘贴。小红书请保留分享URL中的xsec_token，不能仅凭缺令牌的笔记ID保证可读。命令示例：

```powershell
.venv/Scripts/python.exe -X utf8 shiwen.py add 'https://www.xiaoyuzhoufm.com/episode/6932cccd4ef12f9fe91a2411'
# 其他平台同样用 add <完整链接>；加 --summarize 才进入付费整理
# TikTok/X需要可用代理时，在启动CLI/服务前设置自己的HTTPS_PROXY
```

有字幕复用原字幕快路，无字幕本地SenseVoice，图文使用现有本地OCR。提取不烧整理配额；勾整理沿用原额度保护。本单真实付费调用0次。

小红书Cookie位于SHIWEN_DATA_DIR/cookies/xiaohongshu.json，owned浏览器位于browser-xiaohongshu；Windows DACL限制本机用户，登出清理两者并阻止旧扫码写回。显式API仅允许edith.xiaohongshu.com两个固定路径，不跟随跳转；媒体/CDN请求不附Cookie。登录浏览器自身正常使用本站会话。短链仅允许XHS域跳转。缓存按笔记ID+语言，不因分享令牌轮换复制任务。请勿分享Cookie或把数据目录放进安装包。

## 验收与证据

目录：`runtime/platform-extension-20261030/`，均为隔离素材，不进Git。

- `A-network.json`：两站真实提取失败及未配置代理；单测覆盖TikTok字幕免下载、代理默认继承、X文本推文与网络失败区分。
- `B-xiaoyuzhou-result.json`、`data/jobs/b52e7e5a16237ef3/transcript.*`：真实下载、本地转写与时间轴；`B-spotify.json`：真实RSS降级。
- `login-status.json`、`C-acceptance.json`、`C-images-result.json`、`C-video-result.json`：登录有效、两种产物；视频task ac9c4bfc9e8869b5，图文task ea69be8de9f70f86。
- `batch-acceptance.json`：上述三篇真实混合批量复用缓存，3/3完成、无新付费调用。分享令牌及登录材料仅在隔离数据内，不提交。
- `backend-final.txt` / `frontend-final.txt` / `build-final.txt`：私有全量回归（排除冻结旧客户包两组），前端测试与构建；包含full包排除凭据测试。

本次运行8787为隔离验收服务，扫码只保存在该runtime，未迁移到真实data；日常工作台需在自己的设置登录。未重建历史full/offline-full ZIP，既有包仍是G单版本；构建脚本的新源码/依赖/平台清单已同步，原core冻结。

## 未验项

TikTok/X待可用代理真链；Spotify公开完整音频正向样本；xhslink真实短链正向样本（跳转边界单测已测）；新设置页GUI点验交ZCode。视频样本为粤语/配乐混合，自动稿明显错字，不把出稿等同质量通过；图文OCR仅转文字，不推断图解关系。平台风控、删除、令牌过期时明确失败，不伪造原文。本轮没有修改外部MediaCrawler/meme-lab配置或登录态，其他长期挂账见AGENTS.md。
