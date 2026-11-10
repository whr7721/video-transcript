---
name: creator-workbench
description: 在Codex中用本机采集工具制作抖音、快手、小红书等自媒体内容。适用于指定博主最新作品转图文、按活动规则选题、已有材料做发布包，以及修改单篇图片或文案。宿主直接读原文和创作，不调用拾文内置文本AI；不自动发布。
---

# 自媒体创作工作流（Codex自用）

本技能组织既有工具，不是独立AI服务或新网站。用户表达目标后，直接完成授权范围内的取材、编辑、生图与打包。普通选择自行决定；账号登录、素材缺失或发布等需要用户实际操作时再交接。

## 本机入口

Python：`D:/zcode1/video-transcript/.venv/Scripts/python.exe -X utf8`。
本技能脚本：安装后用本SKILL.md同目录的 `scripts/workbench.py`；仓库源在 `D:/zcode1/video-transcript/skills/creator-workbench/`。
活动工具：`node D:/dsh/actwatch/actwatch.mjs ...`，cwd必须是 `D:/dsh/actwatch`。活动任务先读现有 hotspot-radar 技能；最终判断由当前Codex做，不直接采纳自动配方。

日常作品保存到 `D:/codex/creator-workbench-output/<日期>-<主题>/`。实验用 `SHIWEN_DATA_DIR=D:/zcode1/video-transcript/runtime/<本次>/data`；不把测试任务写真实data库。已完成原稿可显式复用，不复制凭据。环境支持SHIWEN_HOME更换拾文位置。

## 登录与故障

`node actwatch.mjs login --site ks --check-only`可验证快手实际业务接口；退出0且JSON status=verified才算本次验证有效，非0不等于一定是Cookie过期。status中的已保存不代表有效。需要扫码时去掉--check-only，用户完成登录；只管理工具自有浏览器，不关闭用户其他窗口。其余平台沿用现有登录命令，不宣称本轮已逐个实测。

## 三种任务

- 博主取材：`workbench.py latest "主页URL" --output listing.json`，核对发布时间、作者和返回范围，再 `ingest "作品URL" --output source.json`。支持当前拾文的枚举平台，不替不支持的平台编造最新作品。
- 活动驱动：获取活动清单和原始规则，核对时间、资格、主题、图片数量、音乐与奖励门槛。相关题材不代表已满足参赛规则，过期/仅元数据的活动标待核实。
- 已有材料：优先直接读取文件/原稿；不重复抓取。需要转写才 `ingest`。RSS必须显式--episode选一集。

`ingest`默认本地ASR/字幕/OCR，无summarize/classify参数，不调外部文本模型。只输出路径与元数据，必须继续读transcript_path全文，长文分段读完，不只看标题或前部。先区分原作者主张、经历、操作步骤与自己的建议。原稿有错误和时效限制要保留判断，不把作者经历写成用户经历。

## 创作与输出

1. `workbench.py init "作品目录" --platform douyin --images 4 --brief "目标/受众/风格"`。已有作品先status续做，不重建。
2. 当前Codex阅读原文、选择角度、写标题与正文；查看完整主线后决定取舍。默认不调用拾文summarize/rewrite/personal_kb等文本AI；原功能保留，不删源文件。不要用外部模型改写替代宿主判断。
3. 图文生图使用现有imagegen；有baoyu-xhs-images时借鉴其结构。先封面定调，再以封面作参考生成剩余图；先保存提示词。统一3:4，每张独立，生成后逐张看文字和画面。需要确定性文字排版可按用户选择使用现有md2card，不伪装成生图。
4. 配乐先核对原作者署名、活动指定曲目或平台实际曲库。找不到纯伴奏入口时明确仅确认曲名；含口播原声不能充当已验证纯BGM。此环节无需生成音乐。
5. 标题存title.txt、正文存正文.md、图片按images/01.png编号、配乐写music.md。在manifest.json登记sources、图片顺序、music核验级别、steps进度、reviews检查结论。详见[作品格式](references/package.md)。
6. `workbench.py status "作品目录"`检查缺项与源稿变化；确认实际内容后 `pack`。输出ZIP、标题正文、音乐名称/入口及实质未验项。打包不代表已发布。

## 修改与恢复

收到“继续/换第三张/换平台文案”先读manifest、brief和已有成品，只重做受影响步骤。先确认文件真实存在，再复用；不把脚本缓存命中当作语义质量合格。图片生成失败仅补失败图片，不重跑原稿和其他图。

宿主工具负责判断、脚本负责采集/渲染/确定性检查。skill本身不是脱离Codex的常驻agent，用户不在会话时不会自行创作。收藏定时由原后台承担，不新增开机任务。发布、发消息、账号经营不包含在本技能默认动作内。

现有CLI `clips`包含模型挑选，不是纯渲染入口。用户需要视频成片时先读clips模块，使用已选时间范围调用可复用的本地渲染函数；不擅自用整条clips命令消耗文本额度，不为本轮新增切片接口。
