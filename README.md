# 拾文

把视频、播客链接或本地音视频转成**带时间码的文字**，再从文字里抽出**能直接开工的事实卡片**。

本地识别（SenseVoice INT8，约 30 倍实时，零 API 费用，内容不出本机），专名纠正走可累积的本地词表。

---

## 这个仓库现在是什么

**本机自用精简版。** 只保留采集 + 转写 + 事实抽取三层，代码约 350 行自用层 + 13 个核心模块。

原来的完整产品——Web 工作台、云端验证版、React 前端、二创改写、金句切片、思维导图、OCR、内容分类、客户交付包——已从工作区移除，实现保存在 git tag **`v1.0-portfolio`**（569 个文件，封存于 2026-11-13，不再改动）。

取出完整版：

```bash
git worktree add ../shiwen-full v1.0-portfolio
```

**为什么砍**：产品层与飞书妙记、通义听悟、剪映自动字幕直接竞争，而那三样在 2026 年已是系统级免费功能；它真正不可替代的部分只有一件——**批量、脚本化、本地、无配额、可被 agent 调用**。同一个仓库里同时供"给人用的界面"和"给 agent 用的接口"会两头都不精，所以只留后者。

---

## 一条命令

```powershell
.\.venv\Scripts\python.exe -X utf8 grab.py "<链接或本地文件>"
```

| 参数 | 用途 |
| --- | --- |
| `--top N` | 事实卡片条数，默认 40 |
| `--lang zh\|en\|auto` | 语言，默认 auto |
| `--episode N` | RSS / 播客订阅源，指定第几集 |
| `--json` | 只输出 JSON |

产出在 `data/jobs/<job_id>/`：`transcript.txt`、`transcript.srt`、`transcript.json`、`facts.md`。

已转过、只想重出事实卡或重跑专名纠正：

```powershell
.\.venv\Scripts\python.exe -X utf8 facts.py <job_id> --top 25
.\.venv\Scripts\python.exe -X utf8 facts.py <job_id> --recorrect
```

平台：抖音、小红书、B站、YouTube、TikTok、X、小宇宙、Spotify、RSS、本地文件。

---

## 依赖

```powershell
.venv/Scripts/python.exe -m pip install -r requirements.txt
```

另需 **ffmpeg / ffprobe** 和 **Deno ≥2.3.0**（`winget install --id DenoLand.Deno --exact --source winget`）。Deno 需在 PATH 中，yt-dlp 默认启用它；YouTube 的 JS 挑战还要匹配版本的 EJS 脚本，本项目固定 `yt-dlp==2026.10.26` + `yt-dlp-ejs==0.8.0`，升级须一起核对。

模型在 `models/`（约 414 MB），首次运行自动检查。

抖音源登录目录可用 `SHIWEN_DOUYIN_PROFILE` 指定，默认 `D:/zcode1/mediacrawler/browser_data/dy_user_data_dir`。

---

## 已知误差

数字、年份、金额**基本可信**；人名地名**成系统错**（`Halifax → halififax`、`Nova Scotia → novava scotia`、`加元 → 家元`）。要上屏的专名必须核。

补词表对**新转写**生效；已有稿子要 `--recorrect`。三个踩过的坑写在 [SELFUSE.md](SELFUSE.md)。

---

## 目录

```
grab.py          链接 → 转写 → 事实卡
facts.py         转写稿 → 带时间码的事实卡（含 --recorrect）
link_ingest.py   平台路由 / 下载 / 字幕提取
transcribe.py    本地 ASR
asr_hotwords.py  专名后处理（词表在 data/hotwords.json，累计增值、不入库）
store.py         任务存储
SELFUSE.md       自用层设计说明与误差边界
```
