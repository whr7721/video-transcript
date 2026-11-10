# Codex自用创作流程与旧功能封存

2026-11-10：当前日常入口为Codex技能creator-workbench。工具提供材料与执行，当前宿主负责阅读完整原稿、选题、文案、分镜和审核。不新增前端，不运行第二套文本AI服务。

## 使用

技能已安装D:/codex/.codex/skills/creator-workbench；源码在本仓库skills/creator-workbench。新会话可说“用creator-workbench取大麦哥最新一期做抖音图文”或显式$creator-workbench。当前会话工具目录若未刷新，直接读取该SKILL.md即可，不把已安装当作新会话自动触发已实测。

脚本支持latest / ingest / init / status / pack；使用本机.venv/Scripts/python.exe -X utf8运行。latest返回本次列表中的最新及范围；ingest输出原文路径、作者、发布时间与哈希，不接外部文本AI；修改单篇前status，完善manifest后pack。日常输出D:/codex/creator-workbench-output；开发隔离到runtime。

## 封存边界

现有两个前端、云端、客户包和内置LLM摘要/二创/追问等保留原代码、历史测试和演示，用于简历及日后恢复；本次不删除、不迁移、不改变既有用户入口语义。新skill不默认调用这些命令。通用旧shiwen技能仍保留其独立产品能力，做自媒体时使用creator-workbench。

保留链接解析、下载、字幕、ASR、OCR、缓存、原稿导出与ffmpeg等执行能力。现有clips包含模型挑选，当前skill不把整条clips命令当纯渲染调用。后台订阅/收藏定时仍可依赖app.py，不用前端不等于停掉后台；本次不配置开机启动或新计划。

## 本轮验证

- 大麦哥：真实重新查主页20条，最新仍为7705318744909729074；从此前实测原稿复制进runtime隔离缓存，新ingest命中缓存，复用已生成四图，标准发布包成功；未重新ASR或调用rewrite。配乐仅确认曲名，纯配乐入口仍待核实。
- 活动：读取当日实际采集的快手《秋日艺术日记》完整规则；当前宿主写作并原生生图，按4张3:4原创AI绘画交付，不伪装实拍；没有自动发布，奖励资格/优质判定不保证。
- 定向脚本测试9项；私有版全量435项；未改前端，不重复构建冻结前端。无新增依赖。
- actwatch外部项目两处脚本修复：login.mjs快手探针POST，--check-only；actwatch.mjs传递子进程退出码、进程启动失败码、已保存标未验证、report失败不报完成。保留DSH新增小红书等逻辑，未修改任何DSH技能。
- 实测快手--check-only HTTP200/businessCode1 verified；六子命令模拟失败均传回7。语法检查通过。外部改动备份、补丁、日志及两份发布包位于runtime/creator-workbench-20261110。

质量边界：文件检查不代替语义审核；imagegen图片需宿主逐张看；没有新会话隐式触发验收、所有平台逐一登录验收或自动发布。审查待独立方进行。
