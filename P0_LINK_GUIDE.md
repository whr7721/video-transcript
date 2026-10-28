# P0 链接转文字

在项目根目录安装依赖：`.venv/Scripts/python.exe -m pip install -r requirements.txt`。新增依赖固定为 `yt-dlp==2026.10.26`，本轮未增加模型。需要既有 ffmpeg 和 SenseVoice/VAD 模型。

PowerShell：

```powershell
.\shiwen.cmd add 'https://youtu.be/作品ID' --language auto
.\shiwen.cmd add 'https://www.bilibili.com/video/BV作品ID' --language zh
.\shiwen.cmd add 'https://v.douyin.com/分享ID/'
.\shiwen.cmd add 'https://节目站点/feed.xml'
.\shiwen.cmd add 'https://节目站点/feed.xml' --episode 1 --language en
```

若希望当前终端直接用 `shiwen add`，执行 `$env:Path="$PWD;$env:Path"`，不修改永久系统设置。跨目录也可用完整路径调用 `shiwen.cmd`。旧 `cli.py <抖音链接>` 入口保留。

RSS 默认只列候选，明确选择一集；按稳定的单集 ID 缓存，不把会变动的列表序号当单集身份。首版仅收公开 HTTPS RSS，不支持私密付费 Feed。未知域名按 RSS 尝试解析，非 RSS 会明确失败。

YouTube/B站先读 yt-dlp 的 `subtitles` / `automatic_captions`（对应官方工具的 `--write-subs` / `--write-auto-subs` 能力），仅下载所选字幕，成功则不下载音频。B站额外查询社区文档描述的播放器字幕接口；无可用字幕则下载音频并用现有 SenseVoice 本地转写。RSS 优先发布者文字，失败时可改音频；抖音复用既有独立登录态提取。B站走直连，YouTube 保留既有网络环境。

输出在 `SHIWEN_DATA_DIR/jobs/<任务ID>`，默认 `data/jobs`：TXT、JSON、可用时间轴对应的 SRT。JSON 保留现有 `segments`，新增 `subtitlesArray:[{startTime,end,text,index}]`，时间为秒、index 从0开始；保留 `cover/duration/publishedDate` 字段，未知为 null。日期当前沿来源原始表示（yt-dlp YYYYMMDD、RSS 日期文本、抖音 Unix 秒），调用端应按平台解析；不宣称整个 BibiGPT API 兼容。原稿没有经过摘要改写。

`--language` 支持 auto/zh/en/ja/ko/yue，只切换同一个多语言模型参数。缓存按语言隔离；原有中文缓存键保持兼容。ASR 时间轴是 VAD 语音段边界，不是词级对齐。发布者纯文本没有时间轴时不伪造 SRT。

当前支持3小时以内媒体，下载和 ASR 复用已有文件/分段缓存；中断后重复同一命令继续。字幕获取不成功时仍可能需要平台授权或触发风控；不会绕过验证码。YouTube 依赖 Deno 和匹配的 EJS，安装说明见 README。2026-10-28 审查修复已安装 Deno 2.9.8、yt-dlp-ejs 0.8.0，并在全新隔离目录真实取得英文字幕；不代表所有 YouTube 音频格式均已验收。

抖音只在用户现有 MediaCrawler 环境中调用既有客户端，原 browser_data 只读复制，不修改配置、锁文件和定时任务；复制后的目录受 SHIWEN_DATA_DIR 控制。MediaCrawler 相关能力限自用，不进入商业云端包。

## 本轮证据与边界

- 52项 CLI/核心/RSS/批量/文件/分发相关 unittest 通过，另2项转写测试（含真实样本中断续跑）在合并运行的29项测试中通过。开发 venv 无 pytest，使用既有 unittest，不添加测试依赖。
- `runtime/p0-link-20261028` 隔离真实联调：YouTube `jNQXAC9IVRw` 19秒，字幕路径6条；B站 `BV1GJ411x7h7` 212.31秒，本地识别16段；抖音 intel 示例 213.37秒，本地识别10段；NPR `https://feeds.npr.org/500005/podcast.xml` 第1集，英语本地识别。使用原链接重复命令复用结果，无云端模型调用。
- B站首次随系统代理请求412，直连后真实成功；未将412隐藏成字幕不存在。RSS Lex Fridman Feed 真实预览成功。
- 两小时稀疏合成音频的时间轴/中断缓存证据见隔离目录 `long-report.json`；自然长播客的人声质量仍见 AGENTS.md 原挂账，不把合成音频等同真实长节目。
- B站额外播放器接口为备用路径，单测与四平台实测不等同该备用路径独立成功验收。平台未提供的封面/日期可能为空。
- 不做说话人分离、博主批量收集、成片、云端接线。本轮无新增付费 API。

## 审查请求

意图：在现有 Python 自用栈补齐统一链接 CLI、字幕优先、语言配置、兼容导出；不增加第二套模型或后端。重点审查字幕回落、RSS身份、时间戳契约、缓存语言隔离、只读会话与数据目录路径。独立审查尚待 ZCode，提交区间由交付消息提供。
