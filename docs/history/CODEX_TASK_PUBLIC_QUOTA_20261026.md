# Codex 任务单：公开版防刷（§3-①）2026-10-26

> 实现方：Codex。审查方：ZCode。本文档由调研会话产出，代码已全部回滚，仓库干净（HEAD 321e697）。
> 完成后按 AGENTS.md 输出审查请求，不要自行宣布通过。

## 0. 目标与红线

**目标**：公开部署（`SHIWEN_PUBLIC=1`）时，所有会消耗硅基流动配额的接口按"每设备/每 IP/每天"限额，超限 429；`/api/settings` 拒绝读写；公网 Host 放行。

**红线（违反即返工）**：
1. 不设置 `SHIWEN_PUBLIC` 时，**所有行为与现状完全一致**——私有版零影响，这是最优先验收项。
2. 不改动任何用户数据文件与既有测试语义；只新增文件与新增判断分支。
3. `public_quota.py` 必须加入 `build_core_package.py` 的 `BACKEND` 白名单，否则公开包缺文件（Codex 最容易漏的一步）。
4. 配额库用独立 SQLite 文件（`data-core/public_quota.db`），**不碰 `store.py` 的既有 schema**。

## 1. 设计决策（已定，不必重新发明）

| 决策 | 内容 | 理由 |
|---|---|---|
| 开关 | 环境变量 `SHIWEN_PUBLIC=1`，模块级常量 `PUBLIC` | 私有版零影响；服务器注环境变量即启用 |
| 配额维度 | 每设备每日 + 每 IP 每日，本地时区自然日 | 双层防脚本；单维度都够被绕 |
| 限额 | editorial/classify 3/10，question 10/20，research 5/10（设备/IP） | 来自 CLEAN_PUBLIC_MVP §3-①，可再调 |
| 设备标识 | 请求头 `X-Device-Id`，前端 localStorage UUID | 无登录体系下最轻方案 |
| IP 来源 | `X-Forwarded-For` 首值，兜底 `request.client.host` | Nginx 反代后必须这么取 |
| 挂点 | 只挂"花模型钱"的 4 个写接口 | 导入/笔记/阅读/导出不花钱，不挂 |
| 超限语义 | 尝试先检查后计数；被设备限拒绝的不消耗 IP 池 | 防止无意义双扣 |
| 云转写 | 本轮**不挂**（`LIMITS` 预留注释） | 云 provider 接线是 §3-⑤，届时一起 |

## 2. 参考实现（已写好并验证过设计，可直接采用或改进）

`public_quota.py`（新文件，放仓库根目录）：

```python
"""Public-build request quotas.

Inert by default: every gate is a no-op unless the deployment sets SHIWEN_PUBLIC=1,
so the private workbench keeps its exact current behavior. When enabled, each
model-spending endpoint counts per-device and per-client-IP usages per local day
and rejects with 429 once either limit is reached.

Cloud transcription tasks are not gated yet; wire a 'transcribe' entry into LIMITS
when the cloud provider path goes public (CLEAN_PUBLIC_MVP section 3-5).
"""
import os
import re
import sqlite3
import threading
import time

from fastapi import HTTPException, Request

PUBLIC = os.environ.get("SHIWEN_PUBLIC", "") == "1"
# kind -> (per-device daily limit, per-IP daily limit).
LIMITS = {
    "editorial": (3, 10),
    "classify": (3, 10),
    "question": (10, 20),
    "research": (5, 10),
}
DEVICE_PATTERN = re.compile(r"^[A-Za-z0-9_-]{8,64}$")
OVER_LIMIT_MESSAGE = "今日免费次数已用完，明天再来。"

_LOCK = threading.Lock()
_CONN: sqlite3.Connection | None = None


def _connection() -> sqlite3.Connection:
    global _CONN
    if _CONN is None:
        import store
        _CONN = sqlite3.connect(str(store.DATA / "public_quota.db"), check_same_thread=False)
        _CONN.execute(
            "CREATE TABLE IF NOT EXISTS usage ("
            "day TEXT NOT NULL, kind TEXT NOT NULL, subject TEXT NOT NULL, "
            "count INTEGER NOT NULL DEFAULT 0, PRIMARY KEY (day, kind, subject))"
        )
        _CONN.commit()
    return _CONN


def _reset_for_tests() -> None:
    global _CONN
    with _LOCK:
        if _CONN is not None:
            _CONN.close()
        _CONN = None


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    first = forwarded.split(",")[0].strip()
    if first:
        return first[:64]
    return (request.client.host if request.client else "unknown")[:64]


def gate(kind: str, device: str, ip: str, today: str | None = None) -> dict:
    """Count one usage; raise 429 when over limit. Pure logic for tests."""
    if kind not in LIMITS:
        raise ValueError(f"unknown quota kind: {kind}")
    device_limit, ip_limit = LIMITS[kind]
    day = today or time.strftime("%Y-%m-%d")
    device_key = device if device else f"ip:{ip}"
    with _LOCK:
        conn = _connection()
        rows = {}
        for subject in {device_key, f"ip:{ip}"}:
            row = conn.execute(
                "SELECT count FROM usage WHERE day=? AND kind=? AND subject=?", (day, kind, subject)
            ).fetchone()
            rows[subject] = row[0] if row else 0
        if rows[device_key] >= device_limit or rows[f"ip:{ip}"] >= ip_limit:
            raise HTTPException(429, OVER_LIMIT_MESSAGE)
        for subject in {device_key, f"ip:{ip}"}:
            conn.execute(
                "INSERT INTO usage (day, kind, subject, count) VALUES (?,?,?,1) "
                "ON CONFLICT(day, kind, subject) DO UPDATE SET count=count+1",
                (day, kind, subject),
            )
        conn.commit()
        return {
            "device_remaining": max(0, device_limit - rows[device_key] - 1),
            "ip_remaining": max(0, ip_limit - rows[f"ip:{ip}"] - 1),
        }


def require_quota(kind: str):
    def dependency(request: Request) -> None:
        if not PUBLIC:
            return
        header = request.headers.get("x-device-id", "")
        device = header if DEVICE_PATTERN.match(header) else ""
        gate(kind, device, client_ip(request))

    return dependency


def settings_guard() -> None:
    if PUBLIC:
        raise HTTPException(403, "公开版不支持在线查看或修改设置。")
```

## 3. 接线清单（Codex 依次做）

**① 新建 `public_quota.py`**（上文全文）。

**② `article_api.py`** 三处挂依赖：
- 文件头 import 区加 `import public_quota`，`APIRouter` 行加 `Depends`：
  `from fastapi import APIRouter, Depends, HTTPException, Request`
- `@router.post('/image-items/{ident}/editorial')` → 加 `dependencies=[Depends(public_quota.require_quota('editorial'))]`
- `@router.post('/image-items/{ident}/classify')` → 同上，kind=`'classify'`
- `@router.post('/items/{ident}/question')` → 同上，kind=`'question'`

**③ `research_api.py`** 一处：
- import 区加 `import public_quota` 与 `Depends`
- `@router.post('/documents/{ident}')` → kind=`'research'`
- 注意 `manual-note` 不挂（不调模型）

**④ `app_core.py`** settings 双路由加守卫（两个函数体第一行）：
```python
import public_quota
public_quota.settings_guard()
```

**⑤ `app_shared.py`** `install_shared` 里 TrustedHost 分支：
```python
import os
if os.environ.get("SHIWEN_PUBLIC") == "1":
    allowed = [h.strip() for h in os.environ.get("SHIWEN_ALLOWED_HOSTS", "*").split(",") if h.strip()]
else:
    allowed = ["localhost", "127.0.0.1", "testserver"]
app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed)
```
理由：现白名单只有 localhost，公网 IP/域名访问会 400，内测都过不去。

**⑥ `frontend/core/main.tsx`** 设备头注入（渲染前，fetch 包装）：
```tsx
const DEVICE_KEY='shiwen-device-id'
function ensureDeviceId(){try{
  let v=localStorage.getItem(DEVICE_KEY)
  if(!v){v=crypto.randomUUID();localStorage.setItem(DEVICE_KEY,v)}
  return localStorage.getItem(DEVICE_KEY)||''
}catch{return ''}}
if(import.meta.env.MODE!=='test'){
  const originalFetch=window.fetch.bind(window)
  window.fetch=(input,init)=>{
    const headers=new Headers(init?.headers||{})
    const id=ensureDeviceId()
    if(id&&!headers.has('X-Device-Id'))headers.set('X-Device-Id',id)
    return originalFetch(input,{...init,headers})
  }
  createRoot(document.getElementById('root')!).render(<CoreApp/>)
}
```

**⑦ `build_core_package.py`**：`BACKEND` 元组加 `'public_quota.py'`。

**⑧ 新增 `tests/test_public_quota.py`**，覆盖：
- `PUBLIC=False` 时依赖直接放行（回归保护）
- `gate()` 设备超限 / IP 超限 → 429；跨日（注入 `today`）重置
- `monkeypatch.setattr(public_quota,'PUBLIC',True)` 后 `TestClient(app.app)` 连打 question 第 N 次得 429（ident 用不存在的即可——FastAPI 依赖先于路由执行，配额照样计数）
- `_reset_for_tests()` 配合 tmp 数据目录隔离

**⑨ 构建**：`cd frontend && npm run build:core`。

## 4. 验收命令（做完贴给用户，Windows 本机跑）

```powershell
# 1. 私有版回归：不设 SHIWEN_PUBLIC，全部测试通过
cd D:\zcode1\video-transcript
.venv\Scripts\python.exe -m pytest tests\ -q

# 2. 公开模式冒烟（独立数据目录，不碰日常资料库）
$env:SHIWEN_PUBLIC="1"; $env:SHIWEN_CORE_DATA_DIR="D:\tmp\quota-demo"
.venv\Scripts\python.exe -m uvicorn app_core:app --port 8766
# 另开一个终端：
curl.exe -i http://127.0.0.1:8766/api/settings
#   期望 403（公开版禁读写设置）

curl.exe -i -X POST "http://127.0.0.1:8766/api/library/image-items/nonexistent/editorial" -H "X-Device-Id: deviceabc12345"
#   连打 4 次：前 3 次 400（素材不存在，正常），第 4 次 429（配额生效）

curl.exe -i -X POST "http://127.0.0.1:8766/api/library/image-items/nonexistent/editorial" -H "X-Device-Id: deviceabc99999"
#   换设备头连打：同 IP 第 11 次起 429（IP 池兜底）

# 3. 私有版确认零影响：去掉环境变量重启 uvicorn，/api/settings 恢复 200
```

## 5. 审查请求模板（完成后输出）

改动区间 `<commit>`；意图：公开部署防刷；已知风险：X-Forwarded-For 可伪造（Nginx 层 `proxy_set_header X-Forwarded-For $remote_addr` 覆盖可缓解，部署文档需写明）；未验证项：真机公网 Host 放行、Nginx 反代下 IP 提取。
