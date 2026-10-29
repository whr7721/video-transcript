"""Build the commercial local delivery from explicit core source files only."""
import argparse
import ast
import json
import shutil
import tempfile
import zipfile
from datetime import date
from pathlib import Path
import build_core_package

ROOT=Path(__file__).resolve().parent


def delivery_cli():
    tree=ast.parse((ROOT/'shiwen.py').read_text(encoding='utf8'))
    class StripPrivate(ast.NodeTransformer):
        def visit_If(self,node):
            node=self.generic_visit(node)
            if ast.unparse(node.test)=="kind == 'douyin'":return node.orelse
            return node
    tree=StripPrivate().visit(tree)
    text=ast.unparse(ast.fix_missing_locations(tree))
    assert 'import pipeline' not in text
    return 'import customer_env\ncustomer_env.configure()\n'+text+'\n'


def build(customer='验收客户',output=None):
    if not customer.strip() or len(customer)>100:raise ValueError('客户名为空或过长')
    output=Path(output or ROOT/'runtime/private-install-20261029/delivery');output.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(dir=ROOT/'runtime') as tmp:
        stage=Path(tmp)/'shiwen-customer';stage.mkdir()
        for name in build_core_package.BACKEND:
            if name in {'requirements.txt','requirements.lock.txt','requirements-ocr.lock.txt'}:continue
            shutil.copyfile(ROOT/name,stage/name)
        shutil.copyfile(ROOT/'cli_summary.py',stage/'cli_summary.py')
        shutil.copytree(ROOT/'cli_assets',stage/'cli_assets')
        (stage/'shiwen.py').write_text(delivery_cli(),encoding='utf8')
        req=(ROOT/'requirements.lock.txt').read_text().strip()+'\nyt-dlp==2026.10.26\nyt-dlp-ejs==0.8.0\n'
        (stage/'requirements.txt').write_text(req,encoding='utf8')
        assets=ROOT/'frontend/dist-core'
        if not (assets/'index.html').exists():raise RuntimeError('请先构建核心前端')
        shutil.copytree(assets,stage/'frontend/dist-core')
        for p in (ROOT/'private_delivery').iterdir():
            if p.is_file():shutil.copyfile(p,stage/p.name)
        for name in ['THIRD_PARTY_NOTICES.md','THIRD_PARTY_LICENSES.txt']:
            shutil.copyfile(ROOT/'distribution'/name,stage/name)
        (stage/'customer-package.json').write_text(json.dumps({'version':1,'customer':customer,'date':date.today().isoformat(),'platforms':['local_file','rss','youtube']},ensure_ascii=False),encoding='utf8')
        (stage/'LICENSE.txt').write_text(f'拾文客户授权\n客户：{customer}\n交付日期：{date.today().isoformat()}\n授权客户在自己的Windows设备内部署使用本交付版本。不得转售、转授权或公开分发本交付包；额外支持服务以双方约定为准。\n第三方软件、模型保留各自许可，以上限制不取代其原有权利。AI服务费用由客户自行向供应商支付；不保证识别和生成内容绝对准确。\n',encoding='utf8')
        wrappers={'install':'install.ps1','start':'start.ps1','uninstall':'uninstall.ps1'}
        for name,script in wrappers.items():
            (stage/(name+'.cmd')).write_text('@echo off\r\npowershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0'+script+'" %*\r\nset "result=%errorlevel%"\r\npause\r\nexit /b %result%\r\n',encoding='ascii')
        (stage/'stop.cmd').write_text('@echo off\r\npowershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0uninstall.ps1" -StopOnly\r\nset "result=%errorlevel%"\r\npause\r\nexit /b %result%\r\n',encoding='ascii')
        (stage/'shiwen.cmd').write_text('@echo off\r\npowershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0run-cli.ps1" %*\r\n',encoding='ascii')
        for p in stage.glob('*.ps1'):
            # Windows PowerShell 5 requires BOM for Chinese paths/messages in source.
            p.write_text(p.read_text(encoding='utf8'),encoding='utf-8-sig')
        for forbidden in ['pipeline.py','session.py','extractor.py','app.py','data','models','.venv','.git']:
            if (stage/forbidden).exists():raise RuntimeError('Forbidden delivery file: '+forbidden)
        archive=output/'shiwen-windows-customer.zip'
        with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
            for p in stage.rglob('*'):
                if p.is_file():z.write(p,Path('shiwen')/p.relative_to(stage))
    return archive.resolve()


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--customer',default='验收客户');p.add_argument('--output',type=Path);a=p.parse_args()
    print(build(a.customer,a.output))
