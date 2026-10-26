# 第三方来源与许可范围

本候选包没有附带模型权重、FFmpeg 可执行文件、Python 运行时或后端依赖。前端静态资源已编译，第三方代码仍适用各自条款。此说明不为本项目自身授予新的开源或商业许可；公开发布前仍须确定自身许可和完成分发审核。

## 模型（用户单独下载）

- sherpa-onnx：[项目](https://github.com/k2-fsa/sherpa-onnx)、[Apache-2.0](https://github.com/k2-fsa/sherpa-onnx/blob/master/LICENSE)。使用固定2024-07-17 SenseVoice INT8导出模型，来源与指纹在 setup_models.py。
- SenseVoice：[上游](https://github.com/QwenAudio/SenseVoice)，代码仓库采用 MIT；[模型卡](https://huggingface.co/FunAudioLLM/SenseVoiceSmall)明确标记自定义 model-license，指向 [FunASR MODEL_LICENSE](https://github.com/modelscope/FunASR/blob/main/MODEL_LICENSE)，不等同 Apache/MIT 权重许可。使用前应阅读具体模型条款；本包不附权重，不用代码仓库许可替代模型条件。
- Silero VAD：[上游及 MIT 许可](https://github.com/snakers4/silero-vad/blob/master/LICENSE)，使用官方 sherpa-onnx 发布的 ONNX 导出文件。
- FFmpeg：用户从[官方下载入口](https://ffmpeg.org/download.html)单独安装；[具体构建配置决定 LGPL/GPL 条款](https://ffmpeg.org/legal.html)。本包不重新分发其二进制。

## 后端（pip 按锁文件安装）

RSS新增 feedparser 6.0.14（BSD-2-Clause）与 feedparser-sgmllib 2.1.0（PSF-2.0），以安装包自带许可为准。发布wheel的实际依赖与main分支声明不同，本版锁定验证过的wheel依赖，不隐式增加第二套HTTP客户端。

FastAPI（MIT）、Starlette（BSD-3-Clause）、Uvicorn（BSD-3-Clause）、HTTPX（BSD-3-Clause）、NumPy（BSD-3-Clause）、psutil（BSD-3-Clause）、Pydantic（MIT）、sherpa-onnx（Apache-2.0）、Trafilatura（Apache-2.0）、BeautifulSoup（MIT）。完整精确版本及传递依赖见 requirements.lock.txt；许可证全文随各自 wheel/dist-info 安装，不能把本表视作所有传递依赖的许可替代品。Python 和 SQLite 使用各自运行时条款。

## 前端

可选图片识别使用单独requirements-ocr.lock.txt：RapidOCR 3.9.2及其PaddleOCR衍生模型（官方MODEL_LICENSES.md记录Apache-2.0来源）、ONNX Runtime 1.23.2、Pillow 12.0.0等。依赖和模型不直接随本ZIP分发，按固定wheel安装，保留wheel内LICENSE/NOTICE；本段不替代各传递依赖条款。来源：https://github.com/RapidAI/RapidOCR 、https://github.com/microsoft/onnxruntime 、https://github.com/python-pillow/Pillow 。实际引擎参数和模型指纹见ocr_worker.py。

shadcn/ui 组件来自官方 registry，Copyright (c) 2023 shadcn，MIT。Tiptap core/StarterKit/UniqueID/Markdown 为 MIT，Copyright Tiptap GmbH。Radix Primitives、React、react-resizable-panels、Vite、Tailwind CSS 为 MIT，TypeScript 为 Apache-2.0，jsdiff 为 BSD-3-Clause；Lucide 为 ISC，继承图标还保留其 MIT 声明。未使用付费编辑器扩展或托管协作服务。

版本和传递依赖见 frontend/package-lock.json。随包 THIRD_PARTY_LICENSES.txt 收录构建环境中前端包自带的许可/NOTICE 文本，保留上游版权声明；构建工具本身不随应用安装。新增或升级依赖后应重新生成并核对该清单。
