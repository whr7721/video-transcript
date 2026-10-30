# 拾文阅读工作台重设计（2026-10-30）

用户否定原UI并要求GitHub搜索设计skill后直接重做。本轮以此前Sana参考图的安静工作区为方向：232px知识空间侧栏、收集输入区、资料卡片、可读的文稿与来源面板；首页/资料库/阅读页统一。后端、任务体系、原稿与整理逻辑保留。

## 使用

- 自用：原app.py入口，frontend生产构建包含本轮界面；普通请求走真实API。
- 设计预览：`npm --prefix frontend run dev:preview`，打开 `/studio/?preview=1`。当前验收服务8790，入口 http://127.0.0.1:8790/studio/?preview=1 。
- “查看全部”进入 `?view=documents`；保留原 `?view=library` 图文入口；批量、订阅、设置、资料助手与发现仍可到达。
- 卡片标题/封面/阅读入口均可进文稿；处理选项收进可展开面板，整理/说话人选项与原提交API不变。移动导航有焦点圈定、Esc关闭与返回焦点。
- 设计模式是显式URL opt-in，只返回内存示例，所有API写入409拒绝，不请求模型、不修改真实资料；普通接口失败显示错误，已移除v0的“接口失败自动展示假资料”行为。

## 调研与采用

| 原始来源 | 核验与取舍 |
|---|---|
| [Anthropic frontend-design](https://github.com/anthropics/skills/tree/main/skills/frontend-design) | 与本机已有skill对应，读取并应用布局/字体/一致性与截图自评，不重复安装。 |
| [interface-design](https://github.com/Dammyjay93/interface-design) | 阅读原始SKILL，对工具型工作台的层级、控件、状态作参考；没有复制其命令/执行钩子，也未宣称已安装。 |
| 本机ui-ux-pro-max | 阅读已安装技能及无障碍规则，应用焦点、降动效、触屏与响应式；find-skills核对skills.sh与GitHub原始来源。 |
| [React Bits](https://github.com/DavidHDev/react-bits) | 阅读AnimatedContent源，其依赖GSAP/ScrollTrigger；当前许可MIT+Commons Clause，不称纯MIT。本轮采用交互反馈思路，自写少量CSS，不vendor组件。 |
| [Uiverse官方galaxy](https://github.com/uiverse-io/galaxy) | README确认是Uiverse收录库、MIT；用户提供Confessionandsacrifice路径不是官方owner。本轮作按钮/输入态参考，不整包引入。 |
| [GalaxyJS](https://github.com/Edwson/GalaxyJS) | README为零必需依赖，部分3D场景可懒加载three；20kB是上游声明未本机benchmark。宇宙动画与阅读任务不匹配，本轮不用。 |
| [Anime.js](https://github.com/juliangarnier/anime) | 官方MIT已核对；本轮的输入聚焦、导航与卡片反馈CSS足够，不新增运行依赖。 |
| [Aceternity Tabs](https://ui.aceternity.com/components/tabs) | 查看官方源码/交互说明，参考交互反馈；保留已有Radix标签逻辑，不为视觉换掉编辑器/面板实现。license页面本轮未成功读取，不复制其代码。 |
| [MotionSites](https://motionsites.org/about) | 有免费与付费内容，并非全站永久免费；同名域名众多，只作方向搜索，未购买或复制受限提示词。 |

## 设计与实现

基色：canvas #fafbf9、paper #fff、text #202722、line #e8ece7、accent #3e6953。字体优先MiSans/HarmonyOS Sans SC/PingFang/微软雅黑本机中文字体，不发外部字体请求。边栏与正文分层，主输入聚焦为唯一强交互；卡片按来源用低饱和底色，自写音轨/书页感图形，不伪装真实缩略图。动效只做一次短入场与用户反馈，prefers-reduced-motion关闭。

Home负责工作区导航；Library复用原搜索/收藏/合集/频道接口，首页compact显示最近6篇；LinkCapture重排控件不改提交；Studio保留Tiptap、来源、导图/笔记/追问/导出，仅换视觉和logo标记。新增preview-api为明确开启的设计适配层。新增SVG为拾文自绘声波标记，无外部位图，无新增npm包。

## 验证与边界

证据runtime/ui-redesign-20261030/：tests.txt前端90通过；build.txt生产构建通过；browser.json首页1440/手机390/资料库/阅读页均无pageerror和横向溢出；interaction.json手机菜单/Esc、搜索、资料库与文稿跳转通过；home.png/mobile.png/library.png/reader.png/reader-mobile.png真实浏览器截图。无真实LLM调用，无生产库写入。

本轮纯前端，未重复跑Python后端全套或模型验收。前端旧settings测试仍有controlled/uncontrolled提示，测试通过，未将它当渲染错误。设计预览的写操作刻意拒绝，不能当作真实转写/整理验收；真实链路原有测试继续保留。视觉是否符合用户审美仍由用户判定，代码方不自称审查通过。

独立分支交付，未合并main。审查请求见runtime/ui-redesign-20261030/REVIEW-REQUEST.md；此前说话人/合集等功能审查范围与本UI范围分段看待。
