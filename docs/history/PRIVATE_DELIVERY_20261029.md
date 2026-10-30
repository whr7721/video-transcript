# Windows 私有交付 · 验收客户版

交付目标：解压后双击安装，客户不需要预装 Python、ffmpeg、Deno 或 Node.js；复用 app_core，既有本地工作台界面不修改。最终 ZIP 路径为 `runtime/private-install-20261029/delivery/shiwen-windows-customer.zip`。客户名“验收客户”、交付日期2026-10-29；真实客户版使用 `build_customer_package.py --customer "客户名" --output "输出目录"` 重新生成。

## 交付组成

- 首次运行 `install.cmd` 或 `install.ps1`。运行环境全部放在包内 `.runtime` 和 `.venv`，不向系统PATH、注册表写入Python配置，不使用全局Python/ffmpeg/Deno作为安装依赖。
- 固定 uv 0.13.6、Python 3.11.14、Deno 2.9.8、FFmpeg Essentials 9.0.2；三个工具ZIP的SHA256取自对应官方GitHub release API，保存在 runtime-lock.json。Python由uv托管下载；requirements使用现有精确版本锁，加入yt-dlp与EJS。
- SenseVoice ONNX/tokens从HF-mirror的上游同名仓库下载，已实测与setup_models现有文件大小/哈希一致；小型Silero VAD使用官方导出。权重不进入ZIP，不替换模型。`-ModelDir`可校验并复制本地模型，`-Offline`禁止网络且要求预置工具/Python/依赖缓存，缺失就明确拒绝。
- `start.cmd` 启动本机8768端口，服务就绪后打开已有工作台。`stop.cmd`停止本包Web后台；关闭浏览器不停止任务。
- `shiwen.cmd add "本地音频路径" --summarize`，或YouTube/RSS单集。CLI和Web共同使用包内data-core；通过Web设置保存的加密Key可供CLI读取。原音频只读，按流计算哈希，不整份读入内存。最大本地文件1GB、CLI媒体3小时，完整整理仍限24000字。
- 白名单复制核心源文件与已构建静态资源。ZIP无.git、运行数据库、Key、模型、原音频、MediaCrawler、pipeline/session/extractor私有模块。交付版的抖音分支通过AST删除，CLI即使未配置环境变量也明确返回“此版本不支持抖音链接”；B站不在该交付白名单。
- LICENSE.txt仅约定自有代码客户授权，第三方条款不受覆盖。现有THIRD_PARTY_NOTICES/许可文本、离线Markmap许可随包保留；安装工具/运行时各自许可保留在下载安装内容中。
- USER_GUIDE.html为离线图文说明，包含流程图和Key配置示意：解压安装 → 注册硅基流动/查看余额并自行充值/创建Key/拾文保存 → 本地导入或链接命令 → 结果与重试。平台示意不是伪造实测截图，无固定充值额承诺。

## 验证记录

环境为开发机runtime中的干净解压目录，不能等同全新Windows物理机；网络仍使用本机可用连接/代理。安装显式使用包内运行时，CLI联调清空SHIWEN、API Key、PYTHONPATH等开发配置并将PATH限制为包内工具与Windows目录。依赖校验记录见 `runtime/private-install-20261029/evidence/install-check.json`，Python base_prefix与工具实际路径均在包内。

- 57项定向回归通过：客户CLI剥离/本地输入与缓存/原文件不变、离线模型哈希拦截与复制，及整理、核心、旧分发、本地文件、导图回归。
- 冷安装真实下载 uv/ffmpeg/Deno/托管Python及44个依赖，模型SHA256通过。本地model.int8.onnx为239233841字节，tokens.txt为315894字节，VAD为643854字节。
- 最终包再次清空拾文/Key/Python配置变量、PATH只保留Windows目录后冷安装成功，日志 `evidence/final-install.log`；中文含空格音频路径通过实际shiwen.cmd处理。随后Web启动、StopOnly停止、RemoveData卸载全部成功。
- Web `/studio/` 200、设置Key接口200并返回已配置。测试Key在本机加密保存，ZIP不含此Key；卸载测试时连同测试数据清理。
- 用包内Python、ffmpeg和模型处理自生成的约16.6秒中文音频，生成TXT/SRT/JSON，继而两次真实模型请求生成三层summary.md和单文件mindmap.html。真实计费和每日次数仍写原共享账本，不靠测试空库绕过开发预算；测试文稿/任务只在隔离目录。
- 不带Key时整理失败，原稿已保存；填好Key后命中转写缓存继续成功。随后实际shiwen.cmd同命令重跑返回同一结果，抖音URL返回明确拒绝。
- `uninstall.ps1 -RemoveData`已实际停止本包venv启动器及Python子进程，清除.venv/.runtime/models/data-core/__pycache__。清理后文件集合与解压ZIP集合一致，无新增残留，外部原始音频存在。代码/说明书作为原解压文件保留，客户可自行删除文件夹。普通卸载默认保留data-core，不伪称删除客户文稿。
- 空缓存 `-Offline`明确报“Offline runtime cache missing: uv”，没有偷偷联网；失败目录随后卸载成功。完整缓存的 `-Offline` 模式复跑成功，但未物理断网验收。

实测中修复：VAD下载的直连超时改用同样的带校验流式HTTP链路；PowerShell5的Python内联引号丢失改为独立delivery_check.py；Windows venv解释器子进程/系统conhost处理；Python选择改固定受管路径，避免客户目录名含test误匹配。

## 待用户解包验收与审查

待用户在真实解压环境验证安装、界面、Key流程与离线HTML交互；不以runtime模拟宣称全新Windows/无代理网络已验收。macOS/Linux、ARM专用适配、Docker、激活、更新均不做。无Key时只有本地转写，不承诺离线LLM；YouTube仍受平台网络/风控限制。

审查重点：安装与卸载的路径边界、依赖校验和缓存、后台进程身份、客户数据保留/显式删除、交付白名单、CLI/Web数据与Key共用、本地文件原稿保护、授权与第三方说明。实现方不自行宣布独立审查通过，提交区间在交付消息提供。
