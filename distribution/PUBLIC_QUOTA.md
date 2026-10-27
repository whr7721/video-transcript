# Public request quotas

The quota gates are inactive unless the server process sets `SHIWEN_PUBLIC=1`.
The four endpoints in the public-quota task are covered. The new mindmap action
also shares the editorial bucket (it does not add another free allowance):

| Endpoint | Per device/day | Per IP/day |
|---|---:|---:|
| POST /api/library/image-items/{id}/editorial | 3 | 10 |
| POST /api/library/image-items/{id}/classify | 3 | 10 |
| POST /api/library/items/{id}/question | 10 | 20 |
| POST /api/studio/research/documents/{id} | 5 | 10 |
| POST /api/studio/documents/{id}/generate, action=mindmap | shares editorial | shares editorial |

Counts use the server's local calendar day. Missing/invalid device IDs fall back
to the IP bucket under the device limit. Rejected over-limit attempts do not
consume either bucket. Accepted attempts count even if the material is missing
or the downstream operation fails or uses a cached result. The independent
database is `public_quota.db` inside the selected core data directory; restarting
the service does not reset it. Deploy one core process per data directory as
already required by the core instance lock.

Public mode blocks GET/POST `/api/settings`. `SHIWEN_ALLOWED_HOSTS` is a comma
separated allowlist; the public default is `*`. Set explicit domain names/IPs
for deployment. Private mode keeps its existing localhost allowlist regardless
of that variable. Existing cross-origin write protection remains active.

## Reverse proxy

The application trusts the first `X-Forwarded-For` value. A caller can forge it
if allowed to reach the backend directly. Bind Uvicorn to loopback, expose only
the reverse proxy, and overwrite rather than append the client-supplied header:

```nginx
location / {
    proxy_pass http://127.0.0.1:8766;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $remote_addr;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```

Set the process timezone to the intended quota day (for example Asia/Shanghai).
The device UUID is an anonymous client identifier, not authentication; resetting
browser storage can change it, while the IP quota still applies. HTTPS is needed
for `crypto.randomUUID` on public origins; unavailable browser storage/UUID falls
back to the IP quota.

This task is not permission to expose the entire existing application publicly.
Other model-spending endpoints (studio generate, chapter jobs, verification
confirmation), cloud transcription, and multi-user data isolation are outside
this four-endpoint gate and still need their own public-release decisions.

Sources: [FastAPI decorator dependencies](https://fastapi.tiangolo.com/tutorial/dependencies/dependencies-in-path-operation-decorators/),
[SQLite transactions](https://www.sqlite.org/lang_transaction.html),
[Nginx proxy headers](https://nginx.org/en/docs/http/ngx_http_proxy_module.html#proxy_set_header).
