from urllib.parse import urlsplit,urlunsplit
import re
def canonical(url):
 p=urlsplit(url);host=(p.hostname or '').lower()
 if host in {'vxtiktok.com','www.vxtiktok.com','tiktok.com'}:host='www.tiktok.com'
 if host in {'x.com','www.x.com','mobile.twitter.com','www.twitter.com'}:host='twitter.com'
 if host=='twitter.com' and not re.fullmatch(r'/[^/]+/status/\d+(?:/(?:video|photo)/\d+)?/?|/i/web/status/\d+/?',p.path):raise ValueError('仅支持视频推文，请提供单条推文链接')
 return urlunsplit(('https',host,p.path,p.query,''))
