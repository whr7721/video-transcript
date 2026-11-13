# 拾文 · 本机自用版

**这个仓库在本机只保留一条链路：把音视频变成带时间码的文字和事实卡片。**

Web 工作台、云端服务、前端、二创改写、金句切片、思维导图、OCR、分类——这些产品层代码已从工作区移除。完整实现保存在 git tag `v1.0-portfolio`：需要时 `git show v1.0-portfolio:<路径>` 单看，或 `git worktree add ../shiwen-full v1.0-portfolio` 取出整份。

**不要凭 README 的历史章节或任何 `*_GUIDE.md` 去找功能，那些文件也已移除。以本文件为准。**

## 唯一入口

```powershell
.\.venv\Scripts\python.exe -X utf8 grab.py "<链接或本地文件>"
```

产出在 `data/jobs/<job_id>/`：`transcript.txt`（全文）、`transcript.srt`（时间码）、`transcript.json`（分段）、`facts.md`（事实卡）。

已转过、只想重出事实卡：

```powershell
.\.venv\Scripts\python.exe -X utf8 facts.py <job_id> --top 25
```

平台：抖音 / 小红书 / B站 / YouTube / TikTok / X / 小宇宙 / Spotify / RSS / 本地文件。私有平台依赖本机已有登录态；验证码或登录过期交给用户本人，不绕过。

## 不要做的事

| 别做 | 原因 |
| --- | --- |
| 调用 `summarize` / `clips` / `rewrite` / `shiwen.py` | 模块已移除；这些加工由 agent 直接读 `transcript.txt` 完成 |
| 启动 `app.py` / `studio_api.py` / 任何前端 | 已移除，自用不需要 |
| 改用云端 ASR | 本地 SenseVoice 约 30 倍实时、零费用、离线、内容不出本机 |
| 运行 `tests/` | 已移除，那些测试针对的是产品层 |

## 硬规则

1. 转写原稿、事实卡、编辑稿是用户内容，任何改动不得使其被动变更或丢失。
2. **核心模块只读使用**：`link_ingest` / `transcribe` / `store` / `asr_hotwords` 等是产品版遗留的稳定实现，新逻辑写进 `grab.py` 或 `facts.py`。
3. 不提交密钥、登录态、`data/`、模型权重、日志、`.venv`。
4. 外部项目（MediaCrawler / meme-lab / douyin-discovery）只读，不改其配置与定时任务。
5. 任何"已完成/已验证"必须附实际输出；接口成功 ≠ 质量通过。

## 已知误差

转写的**数字和年份基本可信**，**专名成系统错**（`Halifax → halififax`、`Nova Scotia → novava scotia`）。要上屏的人名地名必须核。

补 `data/hotwords.json` 只对**新转写**生效；已有稿子要跑 `facts.py <job_id> --recorrect`。细节与三个踩过的坑见 `SELFUSE.md`。
