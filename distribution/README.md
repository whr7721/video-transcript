# 拾文 · 本地内容工作台（RSS 单集候选交付包）

目标环境：Windows 10/11、Python 3.11 x64、FFmpeg。选择本地音视频，转成原稿，再阅读、回听、编辑并记录自己的笔记。使用 CPU，不要求独立显卡。独立电脑部署与无代理机器下载尚待外部验收，当前为候选交付包。

已包含共享编辑器、文章导入、正文阅读、选段研究、专题笔记及导出。AI 文本整理及搜索需要自行配置 Key；语音识别使用本地模型，不需要 Key。所有网络操作由你主动触发。

## 启动

准备：建议至少 8GB 内存、6GB 可用磁盘（模型另需约 240MB，首次下载临时需要600MB）；音视频缓冲上限5GB。首次安装或升级都解压到新建、可写的空程序文件夹，例如 `C:\Shiwen`，不要在 ZIP 内运行或覆盖解压旧程序，避免遗留旧资源。升级前停服备份旧data-core，再通过SHIWEN_CORE_DATA_DIR选择旧核心数据目录；不要覆盖已有数据。

1. 从 [Python 官方](https://www.python.org/downloads/windows/) 安装 **Python 3.11 x64**，包含 Python Launcher。若没有 `py` 命令，可把以下 `py -3.11` 换成 Python 3.11 的完整可执行路径。
2. 从 [FFmpeg 官方下载页](https://ffmpeg.org/download.html) 选择 Windows 构建，解压后将包含 `ffmpeg.exe`、`ffprobe.exe` 的 bin 文件夹加入用户 PATH。重新打开 PowerShell，运行 `ffmpeg -version` 和 `ffprobe -version` 确认成功。FFmpeg 不随包分发。
3. 在解压目录打开 PowerShell，逐行执行（不需要激活 venv、不需要管理员）：

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock.txt
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe check_core.py --port 8766
.\.venv\Scripts\python.exe setup_models.py --report model-download-report.json
.\.venv\Scripts\python.exe check_core.py --require-models --port 8766 --report deployment-check.json
powershell -NoProfile -ExecutionPolicy Bypass -File .\start-core.ps1
```

访问 http://127.0.0.1:8766/studio/ ，保持服务窗口打开。按 Ctrl+C 停止服务，之后重复最后一行即可启动。ExecutionPolicy Bypass 只作用于这次 PowerShell 进程，不修改系统策略；只运行你已检查的本地脚本。若组织策略禁止，直接使用 `.\.venv\Scripts\python.exe -m uvicorn app_core:app --host 127.0.0.1 --port 8766`。

检查器逐项报告 Python/锁定依赖、FFmpeg/ffprobe、数据目录、端口、前端及模型 SHA256。完全未安装模型时可先启动阅读/文章功能；已放入部分文件或校验失败时须重新运行模型准备器修复，文件转写前须模型全部通过。8766 被占用时可 `powershell -NoProfile -ExecutionPolicy Bypass -File .\start-core.ps1 -Port 8770`，并访问8770；不要结束不认识的进程。

前端已编译，无需 Node。开发者改前端时进入 frontend 执行 `npm ci`、`npm run build`。后端入口 `app_core:app`，只监听本机，不直接暴露公网。当前没有多用户认证或公网部署承诺。

## 模型下载与离线准备

脚本固定使用 [sherpa-onnx 官方 SenseVoice INT8 2024-07-17 发布模型](https://k2-fsa.github.io/sherpa/onnx/sense-voice/pretrained.html)。首次下载约164MB，解压后约240MB。默认直连，显式禁用环境和 Windows 系统代理发现，不修改系统网络设置。VPN/TUN/网关是否存在需测试者自行记录；本机直连成功也不能代替独立无代理机器验收。

GitHub 在部分网络不可达时，脚本会超时退出，未验证文件不安装。可重试；不会自动切换未经验证的镜像。你有可用代理时才显式添加 `--proxy http://你的代理地址:端口`，报告只记录是否使用显式代理，不记录地址。不要把含密码的代理命令或 Key 复制到验收记录。

离线方式：在可访问官方发布页的电脑下载下面两个文件，再按官方包目录解压，把模型文件复制到本程序 models 中（文件夹名必须保持）：

- [模型包](https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-int8-2024-07-17.tar.bz2)：SHA256 `7d1efa2138a65b0b488df37f8b89e3d91a60676e416f515b952358d83dfd347e`。
- [VAD](https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/silero_vad.onnx)：SHA256 `9e2449e1087496d8d4caba907f23e0bd3f78d91fa552479bb9c23ac09cbb1fd6`。

可用 `Get-FileHash 文件路径 -Algorithm SHA256` 先检查下载件。最终目录需有 `models/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-int8-2024-07-17/model.int8.onnx`、同目录 `tokens.txt`、`models/silero_vad.onnx`。执行 `.\.venv\Scripts\python.exe setup_models.py --verify-only` 校验三份文件；此命令不联网。不要仅凭文件存在判断安装成功。不要在正在转写时替换模型。

## 数据与边界

数据默认保存至解压目录的 `data-core`。可在启动前设置 `SHIWEN_CORE_DATA_DIR` 为另一个独立目录。不要指向其他应用的数据目录。清空或重新解压程序不会自动迁移用户数据，请自行备份。

本地文件任务按序处理、重启可恢复；未知来源任务不会执行。5GB 缓冲包括上传暂存、受管原文件、临时/完成 WAV 和转换预留。先清理已确认且未固定/未回听的媒体，不够则暂停；文稿和版本长期保留。原文件在缓冲清理后需要重新选择同一文件，不能按链接恢复。本包不包含模型、用户素材、配置密钥、运行数据、历史仓库或开发依赖目录。

备份时先停止服务，再备份整个 data-core 目录。Windows 加密 Key 与原用户绑定，换电脑后需重新填写；文稿和笔记不依赖 Key。缓冲清理只涉及受管媒体，不移动、改名或删除你最初选择的外部原文件。卸载前先备份，尤其不要误删唯一的文稿副本。

## 本地文件链路

已有模型且服务启动后，在工作台点击“新建提取”，选择或拖入一个文件，点击“导入并转写”。发送到100%后仍需等待格式校验与入队确认。失败可重试；缓冲不足时先确认已有文稿再清理。

也可使用随包客户端：

```powershell
.\.venv\Scripts\python.exe import_file.py "C:\素材\讲话.mp3" --wait
```

支持 MP3/M4A/WAV/FLAC/MP4/MOV，单文件 1GB 以内、最长两小时；会检查容器与完整音轨解码，不仅检查后缀。多音轨仅识别第一条，并返回 audio_tracks 数量。重复字节改名仍复用同一任务，同名不同字节独立；重新导入已清理的同一文件仅补回媒体，不重写原稿/编辑版本。

API 为 `POST /api/files/uploads` 创建会话（filename、可选 size_bytes），`PUT /api/files/uploads/{upload_id}` 发送原始请求体，`DELETE` 同一路径取消暂存。无需 multipart。客户端取消/断连后重新创建会话，不支持半文件续传；已入队的文件不能按上传暂存删除。转写失败或等待空间时可 `POST /api/files/tasks/{task_id}/retry`，已完成片段会复用。设置与正文同样限制本机同源写入。

前端采用 React、Tiptap、Radix、Tailwind 等，后端采用 FastAPI、SQLite 及现有文本/语音处理依赖；具体版本见两个 lock 文件。第三方来源和条款见 THIRD_PARTY_NOTICES.md。本包用于定向部署验收，尚未对外发布或确定自身代码的对外许可。

## 阅读、笔记与模型配置

识别原稿只读，编辑稿自动保存为独立版本，可回听语音段、导出并重启读回。选中文字后点击“深入一下”，或在来源面板记录手动笔记。手动笔记无需 Key，保留来源版本，导出标记未调用 AI。

文本整理与 AI 深入需要在设置中填写硅基流动 Key；只有主动开启联网才需要另配官方搜索 Key。Key 在当前 Windows 用户下加密保存，不包含在发行包。完全不配置 Key 仍可本地转写、编辑、手动笔记与导出。

完整整理稿支持24000字以内的识别原稿；摘要/金句最多8块、每块6000字，单个来源段不能超过6000字。超限在调用模型前拒绝，不截断原稿；仍可完整阅读、编辑、导出和选段研究。原文件被缓冲清理后，重新导入同一文件可补回回听，不覆盖文稿版本。

发行 ZIP 使用固定条目时间戳、排序与权限。相同输入文件字节和构建工具版本下重复打包，整包 SHA256 一致；这不承诺不同 Python/zlib/Vite 版本的产物完全相同。

## 独立验收

使用随包 DEPLOYMENT_ACCEPTANCE.md 记录环境、网络、模型下载和一次完整操作。没有独立电脑或没有真实无代理下载时，请标记待验收，不勾选通过。记录问题和每次人工协助，不提交素材正文、密钥或数据库。

## 从 RSS 选择一集播客

点击“新建提取”→“播客 RSS”，粘贴公开RSS地址，点击“读取列表”。此时只读取节目元数据，不获取各集音频或全文、不调用模型。每页20集，可按标题筛选；最多保留前500集，超过会标记截断。平台分享网页、私密订阅和付费内容不是本版支持范围。

选择单集后明确确认导入方式：

- 节目提供UTF-8纯文本或WebVTT时，可直接导入；不下载音频或调用ASR。不是所有节目提供全文，节目简介不当全文。文字保留出处，完整性和准确性尚未人工核验；没有时间戳时不生成虚构时间轴，没有音频时不能回听。
- 选择本地转写时，只有这一集音频下载到5GB受管缓冲，再走本地媒体校验/CPU识别。仍要求模型就绪，支持音频实际格式与时长需通过探测，1GB/两小时限制不变；未知时长不等于免检。

节目文字限制2MB/20万字/2000块，已知超过两小时的单集首版不接。文字格式无效会报错，不会静默改成下载音频。当前输入格式限制不承诺英文音频识别效果。

获取过程中可取消或关闭窗口；关闭窗口后任务在服务端继续，“播客 RSS”再次打开可读回最近一次获取进度。取消要等待网络读取退出与暂存清理；若已经入库，以服务端返回的入库状态为准。失败/等待空间可重试；中断不做半文件续传。音频入库后在文稿页继续查看转写进度。确认最终稿后媒体才可清理；重新选择同一单集的本地转写路径可补回相同音频，不覆盖旧文稿。重复资产的节目来源关联会在来源面板和编辑稿JSON导出中保留。

## 路线图与验收状态

| 范围 | 状态 |
| --- | --- |
| 本地文件、编辑/手动笔记/导出 | 已实现，有真实链路记录 |
| RSS显式选单集、节目文字/本地转写 | 本候选包实现，详见对应发布清单；未标记项不能视为验收通过 |
| 长稿章节导读/按章整理 | 下一阶段，尚未实现 |
| 专题内检索、跨资料研究与创作衔接 | 后续候选 |
| 独立Windows及独立无代理机器部署、长素材人工听校 | 待外部验收 |

本版没有自动追更、批量全选或完整播客客户端。

## 校验候选发行包

分享候选以白名单ZIP及其同目录 `SHA256SUMS.txt`、`release-metadata.json` 为一组，不使用整仓库自动source archive替代。对ZIP执行 `Get-FileHash .\shiwen-core-r1.zip -Algorithm SHA256`，与SHA256SUMS和可信交付记录比对。release-metadata记录源commit、工作区是否有未提交变更、Python/zlib和依赖锁摘要；脏工作区的包只能作为开发候选。

维护者顺序为：冻结代码/依赖/README → 构建 → 白名单打包 → 校验包内manifest的文件集合和逐文件hash → 解压扫描 → 同输入独立暂存重复构建 → 最后生成ZIP外部hash副文件和发布元数据。ZIP内容有任何变化都重新生成校验值。manifest不包含自身hash，ZIP自身hash也不写回包内，避免自引用。

SHA256用于完整性比对，不是作者签名；本候选包尚无作者签名。公开发布清单见 RELEASE_CHECKLIST.md。源码仓库是否公开、正式Release和签名另行决定，本步骤不自动发布。
