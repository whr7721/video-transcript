"""Thin CLI over the shared link ingestion layer."""
import argparse
import os
from pathlib import Path
from link_ingest import platform,stamp,export,ytdlp,add,configure
def main():
    parser=argparse.ArgumentParser(prog='shiwen');sub=parser.add_subparsers(dest='command',required=True)
    p=sub.add_parser('add');p.add_argument('url');p.add_argument('--episode',type=int);p.add_argument('--language',choices=['auto','zh','en','ja','ko','yue'],default='auto');p.add_argument('--summarize',action='store_true',help='原稿保存后用模型生成完整稿、精华、金句与离线导图；共享每日请求配额')
    args=parser.parse_args()
    try:
        configure(os.environ.get('SHIWEN_PROFILE')!='core' and not (Path(__file__).parent/'customer-package.json').exists())
        add(args)
    except Exception as e:parser.exit(1,f'处理失败：{e}\n')

if __name__=="__main__":main()
