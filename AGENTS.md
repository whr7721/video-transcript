# 拾文 · 本机自用版

这个仓库只做一件事：**把音视频变成带时间码的文字**，并告诉你原始文件在哪。

完整产品版（Web 工作台、前端、云端）封存在 git tag `v1.0-portfolio`，需要时 `git worktree add ../shiwen-full v1.0-portfolio` 取出。

## 入口

```powershell
.\.venv\Scripts\python.exe -X utf8 grab.py "<链接或本地文件>"
```

产出在 `data/jobs/<job_id>/`：`transcript.txt`（全文）、`transcript.srt`（时间码）、`transcript.json`（分段）、`audio.wav`、`original.mp4`（原始视频）。

两个可选视图，想要才要：

```powershell
.\.venv\Scripts\python.exe -X utf8 facts.py <job_id> --facts   # 事实卡：人/年/数/引语，带时间码
.\.venv\Scripts\python.exe -X utf8 facts.py <job_id> --steps   # 操作流：操作句按时间排开
```

榜单 / 活动页 / 专题页 / 搜索页不属于单条作品，这两个入口都不处理。用 `data/browser` 的登录态自己开浏览器读，签名由页面 JS 算。做法和实测结论见 `skills/shiwen/SKILL.md` 的「页面型内容」。

## 关注源

记住一批在跟的人，每次只处理新作品：

```powershell
.\.venv\Scripts\python.exe -X utf8 follow.py add "https://www.douyin.com/user/MS4w..."  # 加一个
.\.venv\Scripts\python.exe -X utf8 follow.py          # 扫一遍：共几条、最新一条、有没有新的
.\.venv\Scripts\python.exe -X utf8 follow.py new      # 看有哪些新的还没转
.\.venv\Scripts\python.exe -X utf8 follow.py run      # 要转才转（--seq 3 只转某条）
.\.venv\Scripts\python.exe -X utf8 follow.py list     # 看关注了谁，以及各建没建基线
.\.venv\Scripts\python.exe -X utf8 follow.py sync     # 扫 + 转，一次跑完
```

第一次扫描只建基线，不转历史；之后按作品 id 比对，只把没见过的记成新的。**扫描默认不转写**，转写要显式要。

支持抖音博主主页、RSS / 播客、YouTube 频道、B站 UP 主。状态存在 `data/tasks.sqlite3` 的 `channels` / `feed_items` 表，转写完把 `job_id` 写回对应条目。

转完打印里带 `original.mp4` 的绝对路径。口播在描述画面（「点这里」「选这个」）时可读性会明显发虚，那部分信息在画面里，自己抽帧看。

平台：抖音 / 小红书 / B站 / YouTube / TikTok / X / 小宇宙 / Spotify / RSS / 本地文件。抖音和小红书走本机已有登录态，验证码或登录过期请用户本人处理。

转完之后的事——摘要、金句、二创、切片、导图、选题判断——由你直接读产物完成。这条稿子该怎么用，用户可能有完全不同的打算。

## 硬规则

1. 转写原稿、事实卡、编辑稿是用户内容，任何改动不得使其被动变更或丢失。
2. `link_ingest` / `transcribe` / `store` / `asr_hotwords` 是稳定实现，只读使用；新逻辑写进 `grab.py` 或 `facts.py`。
3. MediaCrawler / meme-lab 等外部项目的配置与定时任务由它们自己维护，登录态改动请交回用户。
4. 不提交密钥、登录态、`data/`、模型权重、日志、`.venv`。
5. 说"已完成/已验证"必须附实际输出；命令退出码为 0 不等于产出质量合格。

## 已知误差

转写的**数字和年份基本可信**，**专名成系统错**（`Halifax → halififax`、`Nova Scotia → novava scotia`）。要上屏的人名地名必须核。

补 `data/hotwords.json` 只对**新转写**生效；已有稿子要跑 `facts.py <job_id> --recorrect`。细节与三个踩过的坑见 `SELFUSE.md`。
