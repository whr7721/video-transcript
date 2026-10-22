# V1-D 部署演练证据

RESULTS_20261022.json 只含脱敏环境、下载和长素材链路指标，不含密钥、识别正文、用户笔记或模型输出。

复跑路径：

1. 构建核心前端后运行 `python build_core_package.py`，取得白名单 ZIP。
2. 在新的中文/空格目录解压，完全按包内 README 创建新 venv、安装锁定依赖、pip check、运行检查器与模型准备器。
3. `setup_models.py --report model-download-report.json` 默认显式直连。真实的独立无代理测试，还需测试者核对系统代理、VPN/TUN与网络，不以程序报告替代环境确认。`--verify-only` 不联网。
4. 用 `start-core.ps1 -Port 8771` 启动独立目录。在测试服务已具备模型后，内部工作区运行 `python experiments/workbench/verify_chain.py --file <真实两小时中文文件> --port 8771 --timeout 1800 --output <runtime结果路径>`，会创建测试编辑版本和手动笔记，不要指向生产数据。
5. 对长稿单独测量 GET document、PUT document、draft/raw export。HTTP 耗时不等于浏览器渲染和用户操作耗时。记录头中尾回听与术语差错，未听校不能报质量通过。
6. 停止测试服务再重启，比对稿件版本/内容摘要、原始结果和笔记；不可重启其他工作台服务。

本次机器仍是开发机，新 venv 安装使用现有 wheel 缓存，模型由新下载器真实下载到新目录、通过固定发布哈希后复制到演练目录；没有借此声称同学独立部署或纯净无代理机器验收已通过。资源峰值为采样窗口内结果，不代表完整运行的绝对峰值。
