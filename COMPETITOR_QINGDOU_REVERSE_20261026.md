# 轻抖小程序逆向与商用路径分析（2026-10-26）

对象：微信小程序「轻抖」，appid `wx7869c97260909c66`，本地缓存版本 106，包体 2,801,573 字节。
方法：读取本机微信小程序缓存包（`%APPDATA%\Tencent\xwechat\radium\users\<id>\applet\packages\wx7869c97260909c66\106\__APP__.wxapkg`），按 V1MMWX 格式解密后解包，静态阅读 `app-config.json` 与 `app-service.js`（1.57MB）。
边界：只做静态阅读，未登录、未调用其接口、未抓包、未破任何鉴权；未复制其代码或资源进本项目。文中接口与文案是从包内字符串还原的**观察结果**，"推测"单独标注。

---

## 1. 一句话结论

轻抖不是"视频转文字工具"，是**抖音运营工具箱**：用免费的去水印/提文案/查权重拉人，用"看广告解锁当天免费"和"视频超时长→升级会员"做成本闸门，用带货榜单、课程、云盘、配音做二次变现；会员购买甚至放在**另一个小程序**里完成。
它能证明"链接转文字"这个形态可以商用并赚钱，**不能证明这条路径对你的产品成立**——它的钱来自抖音带货生态，你没有那个生态。

---

## 2. 技术形态（观察）

### 2.1 域名与分层

包内配置对象原文：

```
v1: https://api.qingdou.vip      // 主业务 API
v2: https://gateway.aipie.top    // 网关/AI 能力
h5: https://h5.qingdou.vip       // H5 兜底
```

其他出现的域名：`imgadmin.qingdou.vip`（素材/图片 CDN，52 处）、`img.qingdou.vip`、`qingdou.vip`（官网，引导"复制网址去电脑浏览器打开"）、`aweme.snssdk.com`（抖音接口域名）、`p1-dy-ipv6.byteimg.com`（抖音 CDN）、`sls-qdou-front.cn-hangzhou.log.aliyuncs.com`（阿里云日志）、`umini.shujupie.com` / `ulogs.umeng.com`（友盟统计）。

分层很清楚：**小程序只做壳与交互，解析、转写、存储、计费全在服务端**。客户端看不到 ASR 模型、看不到 ffmpeg、看不到第三方语音厂商 SDK。

### 2.2 任务模型

两条链都是"提交 → 轮询 → 取结果"，与拾文的 `chapter_jobs` 同构：

| 能力 | 提交 | 轮询 | 结果 |
|---|---|---|---|
| 视频文案提取 | 页面提交链接 | `GET /miniApp/video_extract/getTaskStatus?taskId=` | `status` / `queryTime` / `needSec` / `result` |
| 文案提取（新版） | 同上 | `GET /miniApp/video_extract/getTaskStatusV2` | 同上，带 `queryTime` 动态间隔 |
| 去水印 | `POST /api/v1/tinker/video/upload`（原始 url + videoItemId + uploadType） | `POST /api/v1/tinker/video/getResult` | `tencentUrl`（腾讯云 COS 地址） |
| 图片提文案 | `POST /miniApp/ocr/videoOcr` | `GET /miniApp/ocr/queryResult` | 识别文本 |

细节：轮询间隔由服务端下发（`queryTime`、`needSec`），前端 `setTimeout` 递归；去水印遇到 `70001` 用 300ms 重试。**进度与等待时间都由后端控制**，不是前端写死。

### 2.2.1 "链接转文字"的完整客户端链路（补记）

从包内代码可以还原出五步，全部在客户端可见：

1. **剪贴板自动检测**：`wx.getClipboardData()` 取剪贴板，与 `GET /miniApp/waterMark/getVideoDoMain` 返回的域名列表比对；命中即弹"检测到链接，是否去水印？"。本地用 `waterMarkLink` 数组去重，同一条链接不重复弹。
2. **平台列表服务端下发**：输入框 `placeholder` 来自 `GET /miniApp/waterMark/getValidPlatform` 返回的数组，渲染成"支持 XX、XX 等～"。支持哪些平台不写死在客户端。
3. **提交前来源分流**：`POST /common/video/url/source/check {url}` 返回 `needJump`、`sourceType`、`miniAppId`、`videoExtractMiniAppPath`、`popupText`。命中它不做的来源时，`navigateToMiniProgram` 直接跳合作小程序处理——**它不硬做所有平台，而是把做不了的转出去**。
4. **带参进任务页**：`/pages/videoTextExtractNew/videoTextExtractNew?url=<encodeURIComponent(url)>`；PC 端（`platform` 为 `windows`/`mac`）弹窗引导去电脑。
5. **轮询取结果**：`GET /miniApp/video_extract/getTaskStatusV2?taskId=`；`status` 0 处理中 / 1 完成 / -1 失败，另有 `percentage`、`queryTime`、`needSec`。完成弹"您的文案已提取完成"，非会员先走激励视频。

服务端部分在包外，按字段与接口推断：解析作品 ID → 取播放地址 → 下载并转存 COS（去水印链路的 `tencentUrl` 可证）→ ASR → 文案入库 → 状态推进。**提交任务的具体接口名没有在包内以字面量出现**（页面逻辑里只有轮询与来源检查），此处不做断言。

### 2.3 存储与转存

去水印结果字段名是 `tencentUrl`，变量里有 `needTencent` —— 说明拿到源地址后转存到腾讯云 COS，再给小程序一个自家可控的临时地址。这类地址会过期，包内对应文案是"视频链接已过期，请重新提文案"。

### 2.4 登录与授权

- 微信登录：`/miniApp/user/login`、`/miniApp/user/newLogin`、`/miniApp/user/wxAppAuth`。
- 抖音授权：`/miniApp/dy_auth/authQrCode`、`/miniApp/dy_auth/getDefaultAuth`、`/api/v1/dyAuth/canGetUserScopeData`、`/miniApp/user/isDyAuth`。
- 用途：查权重、账号诊断、视频诊断都需要用户抖音账号数据，所以它把"抖音授权"做成了功能的入场券。

> 推测：抖音授权大概率走的是抖音开放平台的扫码授权（`authQrCode`），不是抓 cookie。这是它能长期存在的重要前提之一。

### 2.5 客户端还能看到的风控与合规设施

- 内容安全：`/api/v1/common/contentCheck`，命中微信限制时提示"微信限制黄暴内容输入，请修改后提交"。
- 停机开关：错误码 `9527` → 跳 `/pages/shutDown/index`（可远程整体停服）。
- 错误码：`4001` 视频超时长→弹"升级会员"；`4004` 404；`21001` 内容违规；`4005/50000/403000` 特殊放行。
- 日志：阿里云 SLS + 友盟双通道，`errorLog` 带 path/functionName/describe。

---

## 3. 功能矩阵（98 个页面）

| 组 | 页面/能力 | 作用 |
|---|---|---|
| 提文案 | `videoTextExtract(New)`、`copyText`、`audiototext`、`importVoice`、`recordToText`、`audioExtraction`、`ocrtext`、`textRecognition`、`videoFrame` | 视频/音频/录音/图片四个入口提文案，与拾文能力几乎一一对应 |
| 去水印 | `waterMark`、`waterMarkNew` | 免费引流主入口，tabbar 正中间 |
| 字幕/配音 | `subtitle`、`subtitleLand`、`textDub`、`voicePrompt` | 字幕、文本转语音、语音提词 |
| 提词器 | `teleprompter`、`teleprompterAudio` | 口播辅助 |
| 文案库 | `videoTextLibrary` + 编辑页 + 搜索页 + 结果页 | **对标拾文的素材库/专题**：存文案、编辑、检索 |
| 带货 | `commodityList`（榜单 tab）、`searchGoods`、`goodsDetails`、`shortVideoDelivery`、`videoCommerce`、`chooseGoodList` | 选品、挂车、佣金 |
| 数据诊断 | `bigDiagnosis`（查权重 tab）、`accountDiagnosis`、`videoDiagnosis`、`singleVideoDiagnosis`、`douyinMarket`、`dataMonitor`、`bigGun`（爆款） | 账号/视频/市场数据 |
| 变现 | `memberCenter`、`vipPurchase`、`accountExchange`、`exchangeQB`、`teamRank`、`course`、`downloadCourse` | 会员、兑换、团队分销、课程 |
| 工具 | `cloudDisk`、`sensitiveWord`、`checkWeight`、`valuation` | 云盘、违禁词、查权重、估值 |

页面数量本身就说明了策略：**工具是入口，数据与交易是主体**。

---

## 4. 商业模型（从代码还原）

### 4.1 五层收入结构

1. **广告**：激励视频。去水印页 `_waterMarkAds` 拉广告，成功后解锁保存；原文提示"因近期频繁有用户恶意消耗资源，现每天须看一次视频广告，当天即可免费使用"。
2. **会员**：`/api/v1/vip/miniApp/vipPage`、`/api/v3/home/vipMiniApp/index` 拉套餐；`4001` 视频超时长直接弹"升级会员"。
3. **带货佣金**：榜单按日销量/日销售额/佣金率/佣金排序，页面说明"榜单根据抖音官方的商品分享热榜生成…每天 6:00/15:00 更新"；配套 `payment/applyDouyin`、`payment/applyKuaishou`（收款账户申请）。
4. **课程/知识付费**：`course`、`downloadCourse`、`classArticle`，`bigDiagnosis` 是"大诊断"付费点。
5. **增值工具**：云盘（`cloudDisk` 上传/重命名/移动/取播放地址）、配音（`/api/v1/tts/*`）、兑换（`accountExchange`、`exchangeQB`）、团队榜分销（`teamRank`、`commission/invite/checkInviteRelation`）。

### 4.2 两个关键的产品决策

**决策一：会员不在本小程序卖。**
`skipVip` 直接 `navigateToMiniProgram({path:'/pages/vipPurchase/vipPurchase', appId:'wxea1b9bfeca2c2cc1'})` —— 跳到另一个小程序完成购买。同时 `copyUrl` 复制 `qingdou.vip` 让用户"去电脑浏览器打开"。
这是对"小程序虚拟支付受限（尤其 iOS）"的标准应对：**工具小程序不收钱，收钱的小程序另立**，再留一条网页端兜底。

**决策二：把"免费"做成条件式免费。**
不是"每天 3 次免费"，而是"看一次广告，当天免费用"。前者消耗次数，后者消耗注意力并产生广告收入，同时用"恶意消耗资源"的说法给限制一个正当理由。

### 4.3 成本闸门

| 闸门 | 实现 | 目的 |
|---|---|---|
| 单条视频时长上限 | `4001` → 升级会员 | 挡住长视频的高 ASR 成本 |
| 每日查询次数 | `/app/v2/big_diagnose/getIsMaxTimes`，"每日仅支持查询 N 次，今日已达上限" | 挡住数据类高频调用 |
| 广告解锁 | 每天一次激励视频 | 用广告收入覆盖免费用户成本 |
| 上传前校验 | `/app/v3/mini/watermark/canUpload` | 提交前就拦截，不做无效计算 |

这套闸门的设计逻辑值得直接借用：**先拦截、再计费、最后才计算**。

---

## 5. 合规叙事（原文摘录，仅作分析）

去水印弹窗原文：

> 去水印功能由本平台完全免费提供，不收取任何费用，不进行任何商业性目的使用。本平台作为提供技术服务的中立工具，提供的去水印功能仅帮助用户提取视频自行学习、观看……若用户滥用该功能实施侵权行为，用户应自行承担由此产生的法律责任。

要点：
- 把"去水印"这件敏感事**定性为免费、中立、非商业**；
- 把侵权责任推给用户；
- 收费发生在会员（时长）、课程、带货上，不在"去水印"这个动作上。

这是一个**叙事隔离**：敏感功能免费且免责，商业收入放在别处。它降低了被指"以侵权功能牟利"的风险，但不等于没有风险——平台条款与不正当竞争的风险依然存在，且这类产品历史上被下架/起诉的先例不少。**它能上线运营，不等于它绝对安全。**

---

## 6. 与拾文的对照

| 维度 | 轻抖 | 拾文 |
|---|---|---|
| 定位 | 抖音运营工具箱 | 学习资料整理工作台 |
| 链接转文字的角色 | 引流工具（免费） | 核心入口（用户认为不可去） |
| 真正的产品 | 数据 + 带货 + 课程 | 整理稿 + 精华 + 专题检索 |
| 变现 | 广告 / 会员 / 佣金 / 课程 | 尚无 |
| 技术 | 全服务端，客户端零模型 | 全本地，客户端即引擎 |
| 数据资产 | 商品榜、账号诊断 | 个人资料库、专题 |
| 合规叙事 | 免费 + 免责 + 用户自担 | 未建立 |

**最重要的差异**：轻抖的"提文案"可以免费，因为它不靠这个赚钱；你的"整理稿"是产品本身，所以收费点必须落在整理稿上，而"转文字"应该是获客成本，不是收入来源。

---

## 7. 你的"非商用"问题，拆成三件事

GPT 说的"非商用部分不能上线"，指的很可能是 MediaCrawler。但这里其实是**三个独立问题**，混在一起会得出错误结论。

### 7.1 开源许可证（可以确定）

`D:\zcode1\video-transcript\extractor.py` 第 1–4 行自己写着：

> Read-only integration with the user's existing MediaCrawler client. … MediaCrawler's non-commercial learning license continues to apply to its imported modules.

MediaCrawler 的 LICENSE 是 `NON-COMMERCIAL LEARNING LICENSE 1.1`，原文条件第 3 条：

> Without the written consent of the copyright owner, the Software may not be used for any commercial purposes.

而 `extractor.py` 直接 `import media_platform.douyin.client`，`pipeline.py` / `discovery.py` 调用它的 venv，`session.py` 用它的 `browser_data` 登录态。**只要这条链路在商业版本里被调用，就落在许可证禁止范围内。** 这一条没有解释空间。

其余组件核实结果：

| 组件 | 许可 | 商用 |
|---|---|---|
| SenseVoice（代码） | MIT | 可以 |
| Silero VAD | MIT | 可以（模型文件发布页仍需按下载页复核） |
| RapidOCR | Apache-2.0 | 可以 |
| sherpa-onnx | Apache-2.0 | 可以 |
| DeepSeek / 硅基流动 API | 服务条款 | 按平台条款，通常允许 |

所以"非商用"**只集中在 MediaCrawler 这一个依赖**，不在你的 ASR/OCR/模型链路上。这是好消息：要换的是一小块，不是整套。

### 7.2 平台条款（与许可证无关，换实现也不会消失）

抓抖音页面、解析播放地址、去水印，通常违反平台用户协议；这与"你是不是用了 MediaCrawler"无关。轻抖用"免费+免责"降低叙事风险，但风险仍在。

### 7.3 主体与类目（上线门槛，与代码无关）

微信小程序个人主体可选类目有限，AI/工具类通常需要企业或个体工商户；虚拟支付在 iOS 端受限。轻抖用"另一个小程序卖会员 + 网页兜底"来应对，这需要多个主体/小程序额度。

**结论**：GPT 说的"不能上线"，准确说法是——**不能带着 MediaCrawler 上线**；"链接转文字"本身不是非商用的。

---

## 8. 保留"链接转文字"的四条商用路径

| 路径 | 做法 | 许可证 | 平台风险 | 成本 | 适合你吗 |
|---|---|---|---|---|---|
| A. 自研最小解析 | 只用自己的 Playwright 逻辑打开分享页取 `video`/`note` 结构，不 import MediaCrawler 任何模块 | 干净 | 仍有（与轻抖同级） | 中（要自己维护页面结构变化） | 想保留链接入口时选它 |
| B. 商用解析 API | 买第三方按次解析服务 | 干净 | 风险转移到供应商，但仍在你名下 | 按次几分钱 | 想省开发时间时选它 |
| C. 官方开放平台 | 抖音开放平台授权接口 | 干净 | 最低 | 需企业资质 + 应用审核 | 长期正规化的唯一路径 |
| D. 用户侧提供内容 | 用户上传视频/音频/图片，或浏览器插件在用户本机解析 | 干净 | 最低 | 低 | **建议先做这个** |

轻抖客户端里看不到任何开源采集器，`aweme.snssdk.com` 只出现 1 次，主要走自家 `api.qingdou.vip` 的任务链——它选的是 A（自研服务端解析），并用 7.2 的话术隔离风险。

---

## 9. 我的建议

**先把"链接"和"价值"分开。** 你说去掉链接转文字就没兴趣了——但你要的其实是"打开就有全文"的便利，不是"链接"这个形式。微信里长按视频保存、或从聊天选文件，只多一步，却能把平台风险降到接近零。

推荐顺序：

1. **做 D 版本上线**：上传音视频/图片/文件 → 本地或云端转写 → 整理稿/精华 → 专题。这条链路没有任何许可证和平台条款问题，可以立刻走审核。
2. **收费点放在整理稿/精华/自测题/专题检索**，不要卖"转文字"。转文字是成本项，用免费额度 + 时长上限 + 广告闸门控制（直接借 4.3 的四道闸门）。
3. **链接解析作为灰度能力**：在 D 版本跑通、有付费用户之后，再用 A 或 B 实现，并明确标注"仅支持公开可访问内容，失败请改用上传"。不要一上线就把链接解析做成主入口——那是把风险放在最前面。
4. **主体先解决**：个体工商户即可认证小程序；类目选工具/效率；准备用户协议、隐私政策、侵权投诉与删除通道。没有主体，前面都白谈。
5. **保留你的差异化**：轻抖有 98 个页面但没有"整理稿 + 精华 + 来源回查"。这是你唯一不需要跟它比的地方，也是唯一可能收费的地方。

一句话：**别为了保留一个入口，把整个产品押在别人的许可证和平台容忍度上；把入口降级成可选项，产品才立得住。**

---

## 10. 证据附录

### 10.1 本地文件

- 包路径：`%APPDATA%\Tencent\xwechat\radium\users\596dadfc15bb28596ede6aaad3fed776\applet\packages\wx7869c97260909c66\106\__APP__.wxapkg`
- 解密：`V1MMWX` 头 + AES-256-CBC（PBKDF2-HMAC-SHA1(appid, "saltiest", 1000, 32)，iv = `the iv: 16 bytes`），前 1024 字节解密、其余按 appid 倒数第二字符异或；解包索引头 18 字节，条目为大端。
- 解包产物与提取结果在临时目录（`%TEMP%\re-tmp\`），**未写入本项目仓库**。

### 10.2 关键接口（去重后 40 条，按用途分组）

```
登录/授权  /miniApp/user/login  /miniApp/user/newLogin  /miniApp/user/wxAppAuth
           /miniApp/dy_auth/authQrCode  /miniApp/dy_auth/getDefaultAuth  /miniApp/user/isDyAuth
文案提取   /miniApp/video_extract/getTaskStatus  /miniApp/video_extract/getTaskStatusV2
           /api/v4/video/extract/analysis/detail  /api/v4/video/extract/analysis/task/detail
图片/OCR   /miniApp/ocr/videoOcr  /miniApp/ocr/queryResult  /miniApp/ocr/generateVideoPlayUrl
去水印     /api/v1/tinker/video/upload  /api/v1/tinker/video/getResult
           /app/v3/mini/watermark/canUpload  /app/v3/mini/watermark/getLowResolutionUrl
           /miniApp/watermark/getTaskStatus  /miniApp/watermark/getVideoDoMain
会员       /api/v1/vip/miniApp/vipPage  /api/v3/home/vipMiniApp/index  /api/v1/tool/vip/vipInfo
           /api/v1/tool/vip/showAd
广告       /api/v1/ads/show/get  /api/v1/ads/finish/callback
AI 助手    /ai/auth/assistant/newSession  /ai/auth/assistant/copywriting
           /ai/auth/assistant/copywritingRecord  /ai/auth/assistant/usageLimit
带货       /api/v3/miniApp/goods/list  /api/v3/miniApp/goods/categoryList
           /miniApp/goods/hotList  /miniApp/goods/hotVideoProduct  /miniApp/goods/shopRank
           /api/v1/material/goodsList  /api/v1/material/video/url/get
诊断       /app/v2/big_diagnose/getIsMaxTimes  /app/v2/big_diagnose/video/hotVideos
           /miniApp/diagnose/diagnose  /miniApp/monitor/canAdd
云盘       /api/cloudDisk/upload  /api/cloudDisk/folderList  /api/cloudDisk/get_play_url
内容安全   /api/v1/common/contentCheck  /common/url/getAgreementInfo
```

### 10.3 未验证

- 未登录、未调用任何接口，接口语义来自路径命名与调用处上下文。
- 会员价格未取到：套餐由服务端返回，包内没有硬编码价格。
- 未确认其抖音数据来源是官方开放平台还是页面解析；`aweme.snssdk.com` 仅出现 1 次，不足以判定。
- 未做任何真机交互与视觉记录。

### 10.4 使用边界

本文件仅供内部产品判断，不复制其代码、素材、文案进产品，不随核心包分发。逆向他人小程序包用于功能分析，与"照抄其实现"是两件事；后者的著作权与不正当竞争风险由复制行为产生。
