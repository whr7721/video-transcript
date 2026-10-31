---
name: shiwen
description: 使用本机拾文把视频、播客链接或本地音视频转为可引用文字、三层摘要和离线导图；适用于“总结视频”“提取字幕”“音频笔记”“分章阅读”。不负责网上搜索、跨篇问答、发布内容或云端部署。
---

# 拾文本地阅读工具

需本机已部署拾文、本地工具；此技能只调用本机 CLI，不提供云 API、MCP 或 OAuth。缺少环境时说明缺项，不自行下载陌生工具或代替用户登录。

## 先确认本机入口

在拾文安装目录运行 `shiwen.cmd commands`；PATH 已配置时可用 `shiwen commands`。也可用安装目录的 `.venv/Scripts/python.exe -X utf8 shiwen.py commands`。不要将开发机盘符硬编码为所有用户的路径。入口不存在时请用户提供拾文安装位置。

## 按意图选择命令

| 用户意图 | 命令 |
| --- | --- |
| 只要原文、字幕、转写 | `shiwen add "<url或本地文件>"` |
| 摘要、精华、金句、导图 | `shiwen summarize "<url或本地文件>" --json` |
| 按话题分章、章节导读 | `shiwen summarize "<url或本地文件>" --chapter --json` |
| 金句切片成竖屏双语视频 | `shiwen clips <task_id> --count N` |
| 多平台二创改写 | `shiwen rewrite <task_id> --style xiaohongshu\|gongzhonghao\|zhihu\|moments --json` |
| 不确定参数 | `shiwen commands` 或 `shiwen summarize --help` |

本地转写不调用付费模型；整理通常两次模型请求，章节模式额外请求，统一计入每日配额，成功缓存不重复调用。用户只要转写时不要擅自加整理。摘要需已配置硅基流动 Key，缺 Key 时引导在拾文设置填写，不能要求把 Key 粘贴到对话或命令日志。

## 示例与结果

```powershell
.\shiwen.cmd add "C:\录音\课程.wav"
.\shiwen.cmd summarize "https://www.youtube.com/watch?v=示例ID" --json
.\shiwen.cmd summarize "C:\录音\访谈.mp3" --chapter --json
.\shiwen.cmd summarize "https://example.org/podcast.xml" --episode 1 --json
```

RSS 没选单集时只列节目并要求 `--episode`，不要默认替用户处理整订阅源。平台能力以本机版本为准：YouTube/B站/播客/本地文件已接通，抖音依赖私有登录态配置；验证码或过期登录需用户操作，不绕过验证，不修改外部 MediaCrawler/meme-lab 的配置。

`--json` 成功时 stdout 是一个对象：`id`（文稿ID）、`summary`（Markdown三层摘要）、`costDuration`（本次耗时秒数，不是金额）；章节模式另有 `chapters`。进度到 stderr；失败退出码非0，错误到 stderr，原稿保留。不要把退出0、文件存在或模型有引用当作人工质量通过。

先读真实结果再回答；保持时间戳/段落引用，分清原作者观点与AI整理，不凭标题推断未处理内容。无语音、风控、配额/网络失败要如实说明。失败后仅按用户授权重试，使用同一输入可复用已完成阶段；不要偷偷批量重试或切换付费服务。CLI 不提供本技能之外的跨篇问答、订阅管理、自动发布接口，相关任务引导到拾文工作台。
