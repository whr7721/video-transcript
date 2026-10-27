# 思维导图 · 用户确认方案（2026-10-27）

用户已确认：先做现有音视频/播客文稿工作台的只读交互导图，原稿→按需生成→页签预览→放大/折叠/缩放→PNG与Markdown导出；文章、多图入口后续再接。

复用DSH备份的树形提示与organizer action/generations框架，不直接套patch。修正静默children[:8]、错误类型转空列表、全局文字去重、摘要分块条件误用、旧导出选择和未注入同步执行器的测试问题。

原稿非空且≤24000字；树≤80节点、≤4层、标签≤40字、每节点≤8分支，超限明确失败不静默裁剪。仅同父节点同名判重复，跨主题允许同名。只读原稿，不把概括当逐字引用；RSS出版文字标记immutable_publisher，其余为immutable_asr。

缓存包含task身份、原稿hash、模型和导图提示版本；不随编辑稿版本重复调用。失败保留旧成功结果，不自动付费重试。新mindmap action在公开模式复用editorial设备/IP配额，其他action不改。

渲染采用本地锁版markmap-view/markmap-common（MIT），标签纯文字转义，不用CDN或外部资源。按需加载，保留现有蓝白阅读风格，工具栏提供缩放/适配/展开折叠/大图与键盘可读大纲。PNG需实际核验中文、换行及完整展开树，不能只截当前视口。核心白名单与许可同步。

参考：[Markmap文档](https://markmap.js.org/docs/packages--markmap-view)、[Markmap源码/许可](https://github.com/markmap/markmap)、[G6依赖](https://github.com/antvis/G6/blob/v5/packages/g6/package.json)、[simple-mind-map依赖](https://github.com/wanglin2/mind-map/blob/main/simple-mind-map/package.json)。后两者因本轮只读树需求而暂缓。

分段实现后统一请ZCode审查。验证包括隔离网络单测、并发/重复生成缓存、原稿与编辑稿不变、导出和公开配额；真实短稿/近上限稿、实际浏览器交互与图片导出另外记录。实测沿用原累计10元账本（开工预留累计7.76元），不清零或放宽限制。

第一段后端：新增7项导图测试与既有studio共19项通过；尚未完成前端/真实模型/浏览器验收。
