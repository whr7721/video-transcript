# RSS单集真实验收与复跑

RESULTS_20261022.json只包含脱敏状态、耗时和hash，不包含转写正文、笔记正文、Key或数据库。

运行一个独立核心测试服务（不要指向生产数据），然后显式选一个标题：

```powershell
.venv/Scripts/python.exe experiments/podcasts/verify_import.py --feed https://audience.castos.com/feed --title "And That's a Wrap" --mode text --port 8772 --output runtime/r1/replay.json
```

脚本拒绝多标题匹配，一次只导入一集，会创建测试编辑版本和手动笔记并校验导出；不自动调用模型。音频路径使用`--mode audio`，需要本地模型。该脚本是HTTP验收，不是浏览器或听校测试。

本次五个真实单集覆盖三个feed。节目文字为官方链接的VTT；ASR为完整中文单集，没有循环/静音拼接。只有一次AI选段说明调用，使用临时服务进程内存中的既有Key，结束后服务恢复未配置Key；没有把Key复制到核心配置。

首次真实取消验收暴露终态与清理竞态，首次重启对照发现终态会话重复写入；RESULTS分别记录修复后重跑结果，不隐藏失败尝试。对容量的单元边界测试使用缩小配额，不宣称重做了V1-B的5GB长音频真实压力。

最终发行校验还需对照里程碑中的当前ZIP SHA256；运行目录、素材、全量AI输出和安装报告仅留runtime。新环境使用本机wheel缓存，不代表独立机器冷网络部署通过。
