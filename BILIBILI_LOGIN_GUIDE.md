# B站登录与字幕快路（私有版）

## 安装与使用

仅在拾文私有版自己的venv安装，不使用MediaCrawler的解释器或配置：

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-private.txt
.\.venv\Scripts\python.exe -m playwright install chromium
```

本轮已在该venv安装Playwright 1.64.0并执行Chromium安装命令。私有新增依赖单列requirements-private.txt，未修改核心依赖锁、客户构建脚本或客户ZIP。

重启私有app.py后，进入 `/studio/` → 设置 → B站登录。点击登录，用手机扫码；检测到SESSDATA并通过nav.isLogin校验后自动保存、关闭窗口。可取消登录、刷新状态或登出。状态包括未登录、已登录、已失效，以及网络/风控等原因导致的暂时无法验证。验证缓存30秒，避免每次轮询重复请求。

未登录、Cookie失效或验证暂不可用时，继续匿名字幕尝试；仍不可用则下载音频并本地转写。没有承诺任意视频都有字幕或固定1秒完成。

已有转写缓存不会因为登录被覆盖或重写。新链接/新的语言任务使用字幕探针；验收为同一视频分别使用auto与zh，形成两个冷缓存任务，未删除任何原稿。

## 数据与实现

- Cookie：`SHIWEN_DATA_DIR/cookies/bilibili.json`，临时文件原子替换；POSIX文件0600、目录0700。Windows替换DACL，仅当前用户FullControl，关闭权限继承。浏览器目录也施加同等用户隔离。
- 浏览器：`SHIWEN_DATA_DIR/browser-bilibili`，Playwright独立持久上下文。最多等待扫码5分钟，不使用主Chrome、抖音或MediaCrawler目录。
- 登出：取消当前登录任务，删除Cookie、缓存及B站专属浏览器目录。删除前校验目录解析后仍在拾文数据目录内；不终止其他浏览器。登录代次检查阻止登出后后台线程重新写回Cookie。
- API：GET `/api/bilibili/status`、POST `/api/bilibili/login`、DELETE `/api/bilibili/login`，仅app.py注册；公开模式拒绝。Cookie不返回网页、日志或任务记录。
- `bilibili_api_get`统一向固定B站API主机携带Cookie；nav校验成功才让字幕请求使用Cookie；字幕CDN请求不携带账号Cookie。
- 私有适配器前置探针通过现有共享层的PRECHECKS注册，字幕命中后不创建yt-dlp媒体提取器；读取view元数据及播放器字幕，支持WBI签名接口和既有接口回落，再匿名回落。
- 设置组件通过SourceUI可选私有插槽接入；本轮不构建、不验证、不维护客户包。此冻结约束适用于后续单，直至用户重新明确恢复。

## 2026-10-29实测

用户亲自扫码一次；nav确认已登录、浏览器自动关闭。在runtime/bili-login-20261029隔离数据目录完成，未写默认真实data，未改原登录态。

|BV1GJ411x7h7冷缓存|耗时|产物|阶段|
|---|---|---|---|
|匿名，auto|22.097秒|SenseVoice，742字/16段|字幕→下载→ASR→完成|
|登录后，zh|1.819秒|B站字幕，522字/47段|字幕→完成，无下载/ASR阶段|

登录任务目录没有audio.wav、original.m4a或其他音视频文件，文档API HTTP200。不同文字数来自平台字幕与语音识别结果，不代表准确率评价。

Windows真实Cookie ACL：保护继承、唯一一条规则、仅当前用户。任务数据库与jobs文件扫描未发现SESSDATA值；响应只含状态。实际登出后Cookie和浏览器目录均不存在、状态未登录，前后所有transcript.*哈希一致。真实Cookie已清理，不保留验收账号登录态。

机器证据：`runtime/bili-login-20261029/acceptance.json`、`logout.json`。不提交Cookie、浏览器数据或运行数据库。

测试：后端62项通过，前端71项通过，私有前端build通过。覆盖失效/验证网络错误、匿名回落、快路不创建媒体提取器、CDN不携Cookie、登录窗口单例/取消、登出清理及禁止迟到保存；现有CLI/链接/整理/文件/RSS回归。

```powershell
.\.venv\Scripts\python.exe -X utf8 -m unittest tests.test_bilibili_auth tests.test_link_jobs tests.test_shiwen_cli tests.test_cli_summary tests.test_core tests.test_local_files tests.test_podcasts -q
npm.cmd --prefix frontend test -- --reporter=dot
npm.cmd --prefix frontend run build
```

浏览器扫码流程由用户实际完成；设置页按钮的完整手工点验、移动端截图仍不冒充已完成。POSIX权限分支有实现，本轮仅Windows实测。原8765服务未重启；隔离页面为 http://127.0.0.1:8780/studio/ 。日常使用需重启自己的私有服务，并在该服务设置页登录；隔离验收Cookie不会复制到生产数据。

## 调研与取舍

- Playwright独立持久上下文：https://playwright.dev/python/docs/api/class-browsertype#browser-type-launch-persistent-context 。沿用上下文能力，自己管理本工具专属目录。
- B站登录信息：https://github.com/bilibili-plugins/bilibili-api-collect/blob/master/docs/login/login_info.md ，以nav.isLogin作为判断，不凭Cookie存在认定成功。
- 播放器字幕：https://github.com/bilibili-plugins/bilibili-api-collect/blob/master/docs/video/player.md 。复用已有HTTP依赖和B站补充分支，增加认证及前置探针。
- 本机yt-dlp bilibili.py已有WBI实现（Unlicense），参考其公开排列和签名规则，用标准库实现本次所需固定字段；不引入新B站SDK。BBDown仅作为登录态管理候选参考，未依赖或拷入整个客户端。
