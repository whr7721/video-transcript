"""Bounded public HTTP downloads. Each redirect is resolved and pinned independently."""
import ipaddress
import socket
import time
from urllib.parse import urlsplit, urlunsplit
import httpx


def public_url(value):
    try:
        p=urlsplit(value.strip())
        if p.scheme not in {'http','https'} or not p.hostname or p.username or p.password or p.port not in {None,80,443}:
            raise ValueError()
        host=p.hostname.encode('idna').decode().lower()
        if '.' not in host or host.endswith(('.local','.localhost','.internal')):raise ValueError()
        try:
            if not ipaddress.ip_address(host).is_global:raise ValueError()
        except ValueError:
            # Numeric addresses must not fall through as hostnames.
            if host.replace('.','').isdigit() or ':' in host:raise ValueError()
        return urlunsplit((p.scheme,p.netloc,p.path or '/',p.query,''))
    except (ValueError,UnicodeError):raise ValueError('仅支持公开的 HTTP/HTTPS 链接，不能访问本机或内网。') from None


class PublicTransport(httpx.HTTPTransport):
    def handle_request(self,request):
        public_url(str(request.url))
        host=request.url.host
        addresses=socket.getaddrinfo(host,request.url.port or (443 if request.url.scheme=='https' else 80),type=socket.SOCK_STREAM)
        ips=list(dict.fromkeys(a[4][0] for a in addresses))
        if not ips or any(not ipaddress.ip_address(ip).is_global for ip in ips):
            raise ValueError('该链接解析到非公开地址，已停止获取。')
        # Connect to the already checked IP, retaining original Host and TLS identity.
        headers=dict(request.headers);headers['host']=request.url.netloc.decode()
        pinned=httpx.Request(request.method,request.url.copy_with(host=ips[0]),headers=headers,
                             stream=request.stream,extensions={**request.extensions,'sni_hostname':host})
        return super().handle_request(pinned)


def fetch(url,limit=3_000_000,referer=''):
    from urllib.parse import urljoin
    url=public_url(url);started=time.monotonic()
    headers={'User-Agent':'Shiwen/0.1 article-reader','Accept':'text/html,image/*;q=0.8'}
    if referer:
        p=urlsplit(public_url(referer));headers['Referer']=urlunsplit((p.scheme,p.netloc,'/','',''))
    with httpx.Client(transport=PublicTransport(),trust_env=False,follow_redirects=False,
                      timeout=httpx.Timeout(15,connect=8),headers=headers) as client:
        for _ in range(6):
            with client.stream('GET',url) as response:
                if response.status_code in {301,302,303,307,308}:
                    if not response.headers.get('location'):raise ValueError('来源返回了无目标的跳转。')
                    url=public_url(urljoin(url,response.headers['location']));continue
                if response.status_code!=200:raise ValueError(f'来源暂时无法读取（HTTP {response.status_code}），可改用粘贴正文或网页 HTML。')
                if int(response.headers.get('content-length','0'))>limit:raise ValueError('来源文件超过本次大小上限。')
                parts=[];total=0
                for chunk in response.iter_bytes(chunk_size=65536):
                    total+=len(chunk)
                    if total>limit or time.monotonic()-started>30:raise ValueError('来源过大或读取超时，已停止。')
                    parts.append(chunk)
                return b''.join(parts),response.headers.get('content-type',''),url
    raise ValueError('来源跳转过多，已停止获取。')
