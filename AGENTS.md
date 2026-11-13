# 拾文 · 本机自用版

这个仓库只做一件事：**把音视频变成带时间码的文字，并分清它该怎么用。**

完整产品版（Web 工作台、前端、云端）封存在 git tag `v1.0-portfolio`，需要时 `git worktree add ../shiwen-full v1.0-portfolio` 取出。

## 入口

```powershell
.\.venv\Scripts\python.exe -X utf8 grab.py "<链接或本地文件>"
```

产出在 `data/jobs/<job_id>/`：`transcript.txt`（全文）、`transcript.srt`（时间码）、`transcript.json`（分段）。

转完先判类型，再出一个：

| 判成 | 产出 | 用法 |
|---|---|---|
| 教程 | `steps.md` | 按时间顺序的操作流＋参数＋坑。照着做，或交给 AI 学；**不是拿去洗稿的** |
| 案例 | `facts.md` | 带时间码的事实卡，洗稿做动画的素材 |
| 观点 | `note.md` | 说明它为什么不适合做素材 |

类型判错用 `--type tutorial\|case\|note` 覆盖。

已转过、只想重出产出：

```powershell
.\.venv\Scripts\python.exe -X utf8 facts.py <job_id> --top 25
```

平台：抖音 / 小红书 / B站 / YouTube / TikTok / X / 小宇宙 / Spotify / RSS / 本地文件。抖音和小红书走本机已有登录态，验证码或登录过期请用户本人处理。

转完之后的事——摘要、金句、二创、切片、导图、选题判断——由你直接读产物完成。

## 硬规则

1. 转写原稿、事实卡、编辑稿是用户内容，任何改动不得使其被动变更或丢失。
2. `link_ingest` / `transcribe` / `store` / `asr_hotwords` 是稳定实现，只读使用；新逻辑写进 `grab.py` 或 `facts.py`。
3. MediaCrawler / meme-lab 等外部项目的配置与定时任务由它们自己维护，登录态改动请交回用户。
4. 不提交密钥、登录态、`data/`、模型权重、日志、`.venv`。
5. 说"已完成/已验证"必须附实际输出；命令退出码为 0 不等于产出质量合格。

## 已知误差

转写的**数字和年份基本可信**，**专名成系统错**（`Halifax → halififax`、`Nova Scotia → novava scotia`）。要上屏的人名地名必须核。

补 `data/hotwords.json` 只对**新转写**生效；已有稿子要跑 `facts.py <job_id> --recorrect`。细节与三个踩过的坑见 `SELFUSE.md`。
