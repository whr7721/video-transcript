# 公开版配额接线 · 2026-10-26

按CODEX_TASK_PUBLIC_QUOTA_20261026.md第3节①—⑨实施，基础提交9d08085。用户已转达上一轮审查无问题；本轮待ZCode独立审查。

## 实现与取舍

- 新增public_quota.py，仅SHIWEN_PUBLIC=1启用。editorial/classify设备3、IP10；question设备10、IP20；research设备5、IP10。服务器本地自然日。
- 独立public_quota.db位于核心数据目录，不改store.py或既有schema。BEGIN IMMEDIATE将检查和双计数放在同一事务，拒绝不扣IP；坏设备头回退IP键，只计一次。重启不清零。
- article_api三处及research_api一处挂依赖，manual-note不挂。计数为请求尝试，包括素材不存在、下游失败和缓存命中，不是模型调用次数。
- app_core设置GET/POST首行守卫；公开Host允许配置、默认*，私有原白名单和跨站保护不变。
- 仅核心前端包装fetch：localStorage UUID、保留Request头/请求体/显式设备头、仅发本站API；存储或UUID不可用回退IP。私有前端入口未改。
- public_quota.py进入BACKEND白名单，PUBLIC_QUOTA.md随包复制。无新增生产依赖、无付费调用、无云部署。

来源：[FastAPI装饰器依赖](https://fastapi.tiangolo.com/tutorial/dependencies/dependencies-in-path-operation-decorators/)、[SQLite事务](https://www.sqlite.org/lang_transaction.html)、[Nginx头覆盖](https://nginx.org/en/docs/http/ngx_http_proxy_module.html#proxy_set_header)。复用任务单参考实现和既有SQLite/HTTPException，不引入限流服务。

## 验收结果

- 私有模式完整pytest：**228 passed, 1 warning，36.84秒**；警告为既有Starlette/httpx弃用提醒。新增12项覆盖私有无副作用、双限额、拒绝不扣IP、跨日、坏设备头、并发、重开持久化、四路由、manual-note及Host配置。
- 前端**57 passed**；核心构建成功。新增2项覆盖头和请求体保留、ID复用、显式头、外站不注入、存储不可用。
- 真HTTP公开服务：settings GET/POST均403；模拟公网Host访问health为200。
- editorial逐次：设备1为400/400/400/429；设备2为400/400/400/429；设备3为400/400/400；设备4为400/429。累计10次被接受请求后，新设备也429。
- 移除公开开关重启同一隔离目录：settings恢复200；原设备连续12次editorial均400、无429；公网Host恢复400。
- 最终核心包**88文件**扫描与manifest验证通过，ZIP包含public_quota.py及PUBLIC_QUOTA.md；输出runtime/public-quota-final-package，未发布。冒烟服务已停止，未操作日常服务。

主环境缺pytest，隔离安装pytest==8.4.2及其测试依赖到runtime/public-quota-tools，生产依赖/锁文件未变。D:/tmp无写权限，实际使用runtime/public-quota-smoke/data-core，未修改既有用户数据。外部未跟踪HANDOVER_20261026.md未动。

## 第4节验收命令

本轮使用以下等价命令。pytest前设置隔离工具路径；重复验证额度序列须选择新的空隔离目录，重启不会清空旧额度。

```powershell
cd D:\zcode1\video-transcript
$env:PYTHONPATH=(Resolve-Path runtime/public-quota-tools).Path
Remove-Item Env:SHIWEN_PUBLIC -ErrorAction SilentlyContinue
.venv\Scripts\python.exe -m pytest tests\ -q
cd frontend
npm test -- --reporter=dot
npm run build:core
cd ..
$env:SHIWEN_PUBLIC='1'
$env:SHIWEN_CORE_DATA_DIR='D:/zcode1/video-transcript/runtime/public-quota-smoke/data-core'
.venv\Scripts\python.exe -m uvicorn app_core:app --host 127.0.0.1 --port 8766
```

另开终端：

```powershell
curl.exe -i http://127.0.0.1:8766/api/settings
curl.exe -i -X POST http://127.0.0.1:8766/api/settings -H 'Content-Type: application/json' --data-raw '{"provider":"cloud"}'
1..4 | ForEach-Object { curl.exe -s -o NUL -w '%{http_code}\n' -X POST http://127.0.0.1:8766/api/library/image-items/nonexistent/editorial -H 'X-Device-Id: deviceabc12345' }
1..4 | ForEach-Object { curl.exe -s -o NUL -w '%{http_code}\n' -X POST http://127.0.0.1:8766/api/library/image-items/nonexistent/editorial -H 'X-Device-Id: deviceabc99999' }
1..3 | ForEach-Object { curl.exe -s -o NUL -w '%{http_code}\n' -X POST http://127.0.0.1:8766/api/library/image-items/nonexistent/editorial -H 'X-Device-Id: deviceabc88888' }
1..2 | ForEach-Object { curl.exe -s -o NUL -w '%{http_code}\n' -X POST http://127.0.0.1:8766/api/library/image-items/nonexistent/editorial -H 'X-Device-Id: deviceabc77777' }
```

停止本轮服务后，在启动它的终端移除开关并重启；另开终端GET settings应恢复200：

```powershell
Remove-Item Env:SHIWEN_PUBLIC -ErrorAction SilentlyContinue
.venv\Scripts\python.exe -m uvicorn app_core:app --host 127.0.0.1 --port 8766
# 另开终端
curl.exe -i http://127.0.0.1:8766/api/settings
```

## 第5节审查边界

意图：指定四接口的公开部署防刷，私有模式保持原行为。已知风险：X-Forwarded-For可伪造；部署必须用Nginx的proxy_set_header X-Forwarded-For $remote_addr覆盖，后端仅loopback监听、禁止直连。匿名设备码可更换，IP池兜底，不是登录认证。

范围限制：studio generate、chapter-jobs、verification confirm等既有付费入口不在本轮清单；云转写按任务单押后，多用户隔离未做，不能据此宣布全应用可直接暴露公网。

未验证：真机公网Host访问、Nginx反代下IP提取。本机Host模拟不替代真实部署；既有人工验收挂账见AGENTS.md，本轮无变化。
