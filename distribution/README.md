# 拾文 · 本地内容工作台（V1-B 文件链路预览）

目标环境：Windows 10/11、Python 3.11 x64、FFmpeg。当前交付本地文件处理接口和命令行入口，图形化上传与独立部署验收在后续阶段。不要把本预览当成最终安装包。

已包含共享编辑器、文章导入、正文阅读、选段研究、专题笔记及导出。模型及搜索需要自行配置 Key 才可调用；未配置可阅读、手动编辑。所有网络操作由你主动触发。

## 启动

在解压目录运行 PowerShell：

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock.txt
.\start-core.ps1
```

访问 http://127.0.0.1:8766/studio/ 。前端已编译，无需 Node；若要修改前端，进入 frontend 执行 `npm ci`、`npm run build`。后端入口 `app_core:app`；请每个入口独立启动进程。仅监听本机，不直接暴露公网。

## 数据与边界

数据默认保存至解压目录的 `data-core`。可在启动前设置 `SHIWEN_CORE_DATA_DIR` 为另一个独立目录。不要指向其他应用的数据目录。清空或重新解压程序不会自动迁移用户数据，请自行备份。

本地文件任务按序处理、重启可恢复；未知来源任务不会执行。5GB 缓冲包括上传暂存、受管原文件、临时/完成 WAV 和转换预留。先清理已确认且未固定/未回听的媒体，不够则暂停；文稿和版本长期保留。原文件在缓冲清理后需要重新选择同一文件，不能按链接恢复。本包不包含模型、用户素材、配置密钥、运行数据、历史仓库或开发依赖目录。

模型下载工具尚未交付，因此缺少模型时 health 会如实显示未就绪；这不影响核心启动与文章功能。转写前需要模型文件已经就位；自动下载和无代理机器实测保留到独立部署阶段。

## 本地文件链路

已有模型且服务启动后，使用随包客户端：

```powershell
.\.venv\Scripts\python.exe import_file.py "C:\素材\讲话.mp3" --wait
```

支持 MP3/M4A/WAV/FLAC/MP4/MOV，单文件 1GB 以内、最长两小时；会检查容器与完整音轨解码，不仅检查后缀。多音轨仅识别第一条，并返回 audio_tracks 数量。重复字节改名仍复用同一任务，同名不同字节独立；重新导入已清理的同一文件仅补回媒体，不重写原稿/编辑版本。

API 为 `POST /api/files/uploads` 创建会话（filename、可选 size_bytes），`PUT /api/files/uploads/{upload_id}` 发送原始请求体，`DELETE` 同一路径取消暂存。无需 multipart。客户端取消/断连后重新创建会话，不支持半文件续传；已入队的文件不能按上传暂存删除。转写失败或等待空间时可 `POST /api/files/tasks/{task_id}/retry`，已完成片段会复用。设置与正文同样限制本机同源写入。

前端采用 React、Tiptap、Radix、Tailwind 等，后端采用 FastAPI、SQLite 及现有文本/语音处理依赖；具体版本见两个 lock 文件。本预览为本地交付，尚未对外发布。
