# 拾文最终冲刺 D–H 使用说明

## D · 每篇笔记与导出

已完成文稿右侧“笔记”里可新增、编辑、删除多条笔记；选择原文段落时自动记录其时间戳，点“回到原文”定位。无锚点的笔记属于整篇。笔记版本冲突会提示刷新，不覆盖较新修改。

设置页的“笔记与导出”：填写已存在的Obsidian vault绝对目录，模板支持{title}/{id}/{date}/{platform}。导出包含标题、来源、已保存文稿、摘要和笔记。请先保存编辑稿再导出。再次导出仅更新拾文上次写入且未被手改的文件；检测到已有外部内容时拒绝覆盖，请改模板。不会修改vault配置。

Notion是可选通道：配置integration token与父页面ID，并在Notion给integration共享该父页面。token本机加密，GET不返回明文。无token/父页面时按钮禁用。点击后才向Notion发送本篇；按每块1800字、每批100块导出。成功的相同内容不重复创建；部分写入保留页面ID并提示人工核对，不自动重复创建。网络中断可能远端已落地，请核对后再操作。本轮无真实Notion凭据，仅验证HTTP契约模拟，未宣称真实工作区导出验收。

D全量私有版测试312后端/85前端与构建通过；证据runtime/final-sprint-20261029/D-*.txt。Obsidian真实临时文件写入与外部修改保护、笔记锚点/版本/隔离与原稿不变已测。

## E · 离线分享快照

在文档右侧“笔记”点“生成分享快照”，再下载只读HTML。文件名share-文稿ID.html，含标题/来源/平台/时间、已保存文稿、原文时间轴、摘要、现有导图和笔记，页脚“由拾文生成”。可以直接把文件发给别人，用浏览器打开，无账号/服务器/CDN。

导图沿用固定版本D3+Markmap并内嵌许可，支持缩放/折叠和适应窗口，只读不可编辑。没有摘要/导图时如实显示缺失，不自动花钱补生成。生成时的内容是固定快照；本机后续编辑不会改变已经发出的文件。分享前请自行核对其中原文和笔记是否适合对外发送。E全量314后端/85前端与构建通过；离线实际浏览器验证在H统一完成。

## F · 视频画面分析

文稿详情主区域“画面”：先设置间隔（默认30秒）和帧数（默认最多30），点免费抽帧；再勾选帧，点模型描述。只支持本机仍保留original视频的任务，音频/仅字幕或视频已清理会明确说明。采样时点是请求提取的时间，不能代表两个帧之间发生的全部事情。超过30帧覆盖范围会提示仅前段采样。

逐帧显示缩略图、中文描述/待核对、该时点附近的原文。模型沿用现有Qwen/Qwen3.5-35B-A3B视觉请求、硅基流动Key、共享每日配额及既有视觉预算账本；点击前预检所选数量与当日剩余额度。已完成描述缓存复用，失败/重启只需显式补失败帧；不会自动重试付费请求。预算预留是保守保护，不是实际账单。

真实验收2次视觉请求、2帧中文描述完成，重复选择额外0次；原视频字节不变。usage折算约0.0015元，具体以供应商账单为准。证据F-live-calls.json/F-live-acceptance.json与visual-data；硬上限5次。单元回归使用模拟模型及真实合成视频抽帧，不再调用模型。317后端/87前端与构建通过。未做OCR全文或画面搜索。

## G · 全功能 Windows 包

构建命令：

```powershell
.\.venv\Scripts\python.exe build_customer_package.py --full --output runtime/final-sprint-20261029/packages
.\.venv\Scripts\python.exe build_customer_package.py --offline-full --runtime-seed "已安装full包的目录" --output runtime/final-sprint-20261029/packages
```

普通full约7MB，仅代码/网页/离线导图资源/采集客户端代码；用户首次运行install.cmd按需下载包内Python、媒体工具、Chromium、语音/OCR依赖及模型。也可用-ModelDir和-BrowserDir提供已校验的本地资源。offline-full约889MB，包含相同功能及全部工具/解释器/依赖wheel/Chromium/模型，解包后运行install.ps1 -Offline；不需要系统Python/Node/MediaCrawler。下载网页内容和云端AI仍需网络，不能把离线安装误解为云端模型也离线。

新包只用自己的data-full与运行目录，登录态永不入包；首次抖音/B站都需本人扫码。USER_GUIDE.html有自绘四步流程图和操作文案。抖音带客户端代码及原非商用学习许可，本变体用于个人自用，不构成商业采集授权。旧core白名单客户包不顺带改造。

真实runtime干净解包安装、Chromium启动、采集客户端导入、ASR/OCR模型校验与服务启动通过；四源API提交均200/排队（在安装后的app用TestClient检查接线，实际服务另验health与Studio）。没有登录态，不声称四源内容全量重新提取。离线全包在另一个新目录以-Offline/无索引/本地wheel安装并完成全套自检，不联网下载依赖。320后端/87前端与构建通过。真实另一台Windows机器仍待外部设备验收。

证据：G-install.txt、G-start.txt、G-admission.txt、full-install/shiwen/.runtime/check.json与admission.json、G-offline-install.txt、offline-install-v2/shiwen/.runtime/check.json、G-archive-check.json。失败尝试也保留：漏web静态目录与uv Python minor链接被错误拷贝问题已修复；最终包只收真实版本目录。

## H · 收尾（2026-10-30）

订阅页支持纯文字话题，须点“确认订阅抖音话题”，仅手动检查，按视频ID集合去重；取消不访问平台。本地术语表支持常见中英关键词互搜，不是通用翻译，未命中术语可换词；不调用翻译API。324后端、87前端与构建通过。WSL Ubuntu24.04 Python3.12实跑3项POSIX锁测试通过，不再挂“未实测”。

mobile-batch-390.png、mobile-subscriptions-390.png、mobile-library-390.png位于runtime/final-sprint-20261029；三页viewport/scrollWidth都是390。分享HTTP直连生成/下载均200，环境代理请求502已复现，属本地请求经过代理导致；调用本地API应配置NO_PROXY=127.0.0.1,localhost或httpx trust_env=False，不更改用户全局代理。离线HTML实开外部请求0。

Notion真实凭据仍未提供，保留远端验收挂账，不用模拟宣称完成。离线包约848MiB，推荐网盘或U盘交付，预留至少5GB解压/安装空间；普通full约7MB需联网下载。D/E/F/G已按独立审查关单，H待终审。
