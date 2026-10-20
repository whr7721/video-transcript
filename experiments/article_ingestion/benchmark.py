"""Public smoke corpus, not the promised 30-sample human quality benchmark.

Run from the repo: .venv/Scripts/python -X utf8 experiments/article_ingestion/benchmark.py
Private source bodies/results remain in ignored runtime/, never in Git.
"""
import concurrent.futures
import json
from pathlib import Path
import subprocess
import sys
import time
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
import article_fetch
import article_parser
import trafilatura
from bs4 import BeautifulSoup,UnicodeDammit

SAMPLES=[
 ('wechat-comfy','https://mp.weixin.qq.com/s/wgCzv0mZPYMzbLzz1avdBA'),
 ('zhihu-comfy-1','https://zhuanlan.zhihu.com/p/1892123380083300102'),
 ('zhihu-comfy-2','https://zhuanlan.zhihu.com/p/902286718'),
 ('zhihu-knowledge','https://zhuanlan.zhihu.com/p/107509391'),
 ('sspai-knowledge','https://sspai.com/post/89852'),
 ('sspai-guide','https://sspai.com/post/76154'),
 ('v2ex-reader','https://www.v2ex.com/t/1069521'),
 ('obsidian-template','https://obsidian.md/help/web-clipper/templates'),
]

def run(sample):
    key,url=sample;out=ROOT/'runtime/article-eval/corpus';out.mkdir(parents=True,exist_ok=True)
    row={'id':key,'url':url,'manual_quality':'not_reviewed'};start=time.monotonic()
    try:
        path=out/(key+'.html')
        if '--cached' in sys.argv and path.exists():
            data=path.read_bytes();ctype='text/html';final=url;row['fetch_mode']='cached_html'
        else:data,ctype,final=article_fetch.fetch(url)
        if 'html' not in ctype:raise ValueError('not HTML')
        html=UnicodeDammit(data,is_html=True).unicode_markup or ''
        path.write_text(html,encoding='utf-8')
        row.update(fetch='received_html',fetch_ms=round((time.monotonic()-start)*1000),bytes=len(data))
        try:
            then=time.monotonic();value=article_parser.parse(html,'html',final)
            row['candidate']={'parser':value['parser'],'chars':sum(len(b['text']) for b in value['blocks']),
                              'images':sum(b['type']=='image' for b in value['blocks']),
                              'code':sum(b['type']=='code' for b in value['blocks']),
                              'tables':sum(b['type']=='table' for b in value['blocks']),
                              'ms':round((time.monotonic()-then)*1000),'warnings':value['warnings']}
            (out/(key+'.json')).write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
        except ValueError as e:row['candidate']={'rejected':str(e)}
        then=time.monotonic();xml=trafilatura.extract(html,output_format='xml',include_images=True,include_formatting=True,include_links=True,include_comments=False)
        tree=BeautifulSoup(xml or '','xml')
        row['trafilatura']={'chars':len(tree.get_text()),'images':len(tree.find_all('graphic')),'code':len(tree.find_all('code')),'tables':len(tree.find_all('table')),'ms':round((time.monotonic()-then)*1000)}
        p=subprocess.run(['node',str(Path(__file__).with_name('defuddle.cjs')),str(path),final],capture_output=True,text=True,encoding='utf-8',timeout=25)
        row['defuddle']=json.loads(p.stdout) if p.returncode==0 else {'error':p.stderr[:250]}
    except Exception as e:row.update(fetch='failed',error=str(e) if isinstance(e,ValueError) else type(e).__name__)
    return row

if __name__=='__main__':
    rows=[]
    private_manifest=ROOT/'runtime/article-eval/user-samples.json'
    if private_manifest.exists():SAMPLES.extend(json.loads(private_manifest.read_text(encoding='utf-8')))
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        for row in pool.map(run,SAMPLES):
            rows.append(row);print(json.dumps(row,ensure_ascii=False),flush=True)
    (ROOT/'runtime/article-eval/results.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
