# 复现表清零：四项功能（2026-10-30）

本单补齐功能入口，不等于所有平台/模型质量挂账自动结清；私有app.py主线，core客户包继续冻结。

## 1. 说话人

先运行 `.venv/Scripts/python.exe setup_speakers.py` 下载校验可选模型；已有模型跳过。仍用原SenseVoice，仅加本地分段/声纹聚类，无云端费用：

```powershell
.venv/Scripts/python.exe -X utf8 shiwen.py add '你的音频.wav' --diarize
.venv/Scripts/python.exe -X utf8 shiwen.py add '你的音频.wav' --speakers 2 --summarize
```

--diarize自动估计，--speakers 1—20指定人数并启用；网页链接提取勾“识别说话人”。只在实际本地转写时执行；字幕与图文来源明确提示无说话人信息，不为字幕强制下载音频。标签为说话人1/2，不识别人名；按ASR段与说话人区间的重叠时长归属，不提供重叠语音分轨，也不切字伪造精确边界。原文视图保留文字，增加颜色及前缀，SRT含标签；JSON含speaker_turns、segments.speaker与subtitlesArray.speaker。

缓存身份包含是否分离/人数，普通原稿不会被开启分离的请求改写。识别文字与聚类分开；抖音已完成本地转写但聚类失败时，重试可补聚类，不将普通转写缓存冒充已分离。普通文件导出/旧文稿兼容无speaker。

模型：INT8 pyannote分段1,540,506字节 + 中英3D-Speaker CAM++28,281,164字节，合计约28.4MiB。中文CAM++28,281,138字节，只小26字节，故默认中英版；不下载第二套embedding。setup_speakers.py固定大小/SHA256、压缩包与选定成员双检；哈希是本次官方release下载后固定的实测指纹，release API未提供digest，不能描述为官方签名。下载来源/数值见runtime/zero-gap-20261030/model-download.json，许可随full源码包保留。full安装与offline种子校验纳入此模型；旧种子缺模型明确拒绝构建，不生成不完整离线包。历史G包尚未重建。

## 2. XMind

导图区“导出 XMind”；CLI summarize生成同目录mindmap.xmind，--json含其绝对路径。分享快照有导图时内嵌下载，保持单文件离线；没有导图不会付费补生成。三入口共用mindmap.validate树，标准库ZIP/JSON转换，零模型调用。

本机生成acceptance.xmind，在 https://tools.visoraapp.com/xmind-viewer/ 实际打开，中文根节点/两分支显示；仅使用自写验收树，不提交用户材料到第三方。截图runtime/zero-gap-20261030/xmind-viewer.png。首个ATools查看器选文件无显示，未当作兼容通过；XMind桌面软件自身未测。

## 3. 合集聚合摘要

文稿页选合集→“生成聚合摘要”，结果持久化于SHIWEN_DATA_DIR/collections/<id>/aggregate.json，并由合集摘要接口提供；导出ZIP含aggregate-summary.md。成员/文本/模型版本变化显示过期，不删旧摘要；失败不覆盖旧成果。来源引用为[audio:<id>]等真实资料ID。

短合集直接聚合；超限分篇分块归纳后再合并，所有块均处理，不静默截断。阶段缓存支持失败后重用，调用沿用organizer.request_json共享30次配额；长合集可能多次请求，额度不足会停下并保留阶段缓存。自动引用校验只验证来源ID，不证明语义正确。

实测三篇来自上一单的小宇宙、小红书视频/图文：共2次请求，第一份因引用格式不合格拒绝，第二份562字通过；随后缓存0新增调用。真实结果/usage在runtime/zero-gap-20261030/aggregate-real.json与aggregate-response.json；首次失败usage未落盘，调用次数记账为2，不再次付费重跑。单测另覆盖长文map/reduce、缓存、失效和失败保留；ZIP真实含摘要，见collection.zip。

## 4. 频道

新提取元数据channelId/channelTitle：yt-dlp、B站探针、抖音、小红书、RSS及小宇宙可用字段映射；无值留空。资料库“频道”筛选经后端匹配。旧稿不会为补字段自动重抓/改写；同一平台旧缓存无字段时保持为空。测试验证匹配/不匹配筛选。

## 验收与边界

证据目录runtime/zero-gap-20261030/，全部隔离：two-speakers.wav为sherpa官方双人英文样本，指定2人与自动估计均得到同样四段，两段说话人1、两段说话人2；SRT与JSON真实生成，见acceptance.json、diarization-auto.json及data/jobs/65099279f7c39194/transcript.*。这是小样本功能验收，不是DER/真实多人会议质量指标，重叠/短语/噪声仍需人工听校。

私有回归340后端、87前端、生产构建通过，命令沿用DEVELOPMENT_ROADMAP.md，日志backend.txt/frontend.txt/build.txt；排除冻结core包两组，包含full构建测试。真实LLM总2次，没有额外付费验收。新Web控件、真实客户设备/离线重装、更多声音质量留给ZCode/用户点验；XMind在线查看器已实测，不泛称全GUI通过。其余挂账见AGENTS.md。
