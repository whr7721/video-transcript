# 抖音图文（note）支持说明

抖音图文的分享链（`douyin.com/note/<id>`、`iesdouyin.com/share/note/<id>`、短链跳转到 note）以前会停在"无法从分享链接取得作品编号"。现在单条图文与视频共用一条入口，按链接路径分流：`/note/` 走图集链，其余走视频链。

## 怎么用

Web 工作台的链接输入、批量链接、CLI 三处都是一条链接：

```powershell
.venv/Scripts/python.exe -X utf8 shiwen.py add "https://www.douyin.com/note/7702009006068248037"
```

短链（`v.douyin.com/...`）会被逐跳展开，作品类型取最后一跳：只有最后一跳是 `/share/note/<id>` 或 `/note/<id>` 才按图文处理，短链中间跳转不会误判。

## 做了什么

1. **编号识别**：`pipeline.id_from_url` 同时认 `/video/`、`/note/`、`/share/note/`、`?modal_id=`，并加数字边界——23 位数字不会再被截成 22 位当成作品编号。`kind_from_url` 只按路径判断类型。
2. **分流**：`run_task` 解出 `(作品编号, 类型)` 后写 `task.media_kind`（`video`/`note`），图文直接进 `_run_note`，不碰下载视频、不探时长、不转写音频。
3. **图集**：沿用已有 `extractor.py images`（登录态会话 + 作品详情接口，MediaCrawler 代码只读），拿 `images[].urls`；同一作品缓存在 `data/image-sources/<id>/source.json`，重跑不再开浏览器。图片只发 `p3-pc-sign.douyinpic.com` 这类 CDN，加 Referer、不带 Cookie，单张 8MB / 单份 64MB 上限。
4. **文字稿**：图片落到 `image_documents` 的图集产物（原图 + 逐页 OCR 区域），再由 `image_documents.to_document()` 拼成文字稿。这个函数是把小红书图文原来的图集逻辑抽出来的共用实现，两个平台走同一条路，产物结构一致（`engine=image_ocr`、`timing_precision=none`、`article_id` 指向图文素材库里的那份图集）。
5. **出稿产物**：`transcript.json/txt/md`，`media_kind=note`、`media_available=false`；不产生 `original.mp4`/`audio.wav`。标题、作者、`publishedDate`、话题标签、`sec_uid` 都从作品详情带出。
6. **界面**：来源链接按 `media_kind` 拼 `/note/` 或 `/video/`，不再一律指向视频页。

## 依赖

本地识字用固定版本的 rapidocr：`requirements-private.txt` 现在包含 `requirements-ocr.lock.txt`，**主 venv 装完就能跑 OCR**（模型文件名与 sha256 在 `ocr_worker.MODEL_HASHES` 里校验，缺模型或版本不符直接报错，不自动下载替换）。选解释器顺序：`SHIWEN_OCR_PYTHON` → `.venv-ocr` → `runtime/image-ocr/venv` → 主 venv（能 import rapidocr 才用）。客户包仍冻结，不含这些依赖。

## 边界

- 只支持单条图文；图文不进"按博主批量"（`expected_sec_uid` 会明确拒绝，不静默降级）。
- 单份最多 64 张；超过拒绝，不截断后宣布完整。
- OCR 是空间顺序，不是语义顺序：图里的「标签／数值」可能被打散，图解箭头不会被理解；`review_note` 与图集 `warnings` 都写明"可能漏字、错序，需对照原图核对"。引用与结论仍要人工看原图。
- 视频链没有改动：仍走 `get_metadata → 下载 → 抽音 → 转写`，本轮只多了一次分流判断。

## 验收证据（runtime/note-20261031/）

- `add.log`/`add2.log`：真实图文 `note/7702009006068248037` 全链出稿，8 张原图、OCR 8/8、文字 6478 字、298 个文字区域，任务 `completed`、`media_kind=note`、无音视频文件；图集 `image_status=completed`、`completeness=unverified`。
- `video.log`：同一份代码在隔离目录跑真实抖音视频，确认视频链仍出转写稿。
- `tests/test_douyin_note.py`：note/视频编号与类型、短链展开、CDN 允许清单、图文出稿与重跑复用、缺图拒绝、无图拒绝、视频分流不误入、OCR 解释器回退；另含小红书图文走同一 `to_document` 的回归用例。
- 全量后端/前端与构建见同目录 `backend.txt`、`frontend.txt`、`build.txt`。

未验：图文 OCR 的语义顺序（需人工对照原图）；抖音图文在手机端 Web 输入的点验；超过 64 张、图文含视频混合内容的样本。
