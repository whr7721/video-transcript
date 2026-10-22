"""Internal distribution builder. This verifier is deliberately outside the public package."""
import hashlib
import json
import shutil
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FORBIDDEN = (b'douyin', b'mediacrawler')
BACKEND = (
    'app_core.py', 'app_shared.py', 'source_contract.py', 'store.py', 'settings.py',
    'media_io.py', 'transcript_stage.py', 'transcribe.py', 'media_buffer.py',
    'local_files.py', 'local_media.py', 'core_instance.py', 'import_file.py',
    'documents.py', 'organizer.py', 'manuscript.py', 'research.py', 'verification.py',
    'research_api.py', 'studio_api.py', 'articles.py', 'article_api.py',
    'article_parser.py', 'article_fetch.py', 'requirements.lock.txt', 'requirements.txt',
)
FRONTEND = (
    'src/Studio.tsx', 'src/source-ui.ts', 'src/ArticleLibrary.tsx', 'src/ResearchPanel.tsx',
    'src/styles.css', 'src/articles.css', 'src/lib/utils.ts',
    'core/main.tsx', 'core/index.html', 'core/public/logo.svg',
    'core/FileCapture.tsx','core/files.css',
    'vite.core.config.ts', 'tsconfig.json', 'package-lock.json',
)
COMPONENTS = ('button.tsx', 'tabs.tsx', 'dialog.tsx', 'tooltip.tsx')


def verify(directory):
    """Inspect every path and every byte, including hidden/binary files. No grep ignores."""
    directory = Path(directory)
    checked = 0
    for path in directory.rglob('*'):
        relative = path.relative_to(directory).as_posix()
        if path.is_symlink() or getattr(path.lstat(), 'st_file_attributes', 0) & 0x400:
            raise ValueError(f'链接不能进入公开包: {relative}')
        if any(word in relative.lower().encode('utf-8') for word in FORBIDDEN):
            raise ValueError(f'禁止路径: {relative}')
        if path.is_file():
            content = path.read_bytes().lower()
            # Also cover common UTF-16 exports, not only UTF-8/ASCII text.
            for word in FORBIDDEN:
                if word in content or word.decode().encode('utf-16le') in content or word.decode().encode('utf-16be') in content:
                    raise ValueError(f'禁止内容: {relative}')
            checked += 1
    return checked


def copy(source, target):
    source = Path(source)
    if source.is_symlink() or getattr(source.lstat(), 'st_file_attributes', 0) & 0x400:
        raise ValueError('不能复制链接')
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)


def build(output=None):
    output = Path(output or ROOT/'runtime'/'v1-c').resolve()
    output.mkdir(parents=True, exist_ok=True)
    # Fresh staging prevents an old output or accidental extra file being carried forward.
    with tempfile.TemporaryDirectory(prefix='core-package-') as temporary:
        staging = Path(temporary)/'shiwen-core'
        for name in BACKEND:
            copy(ROOT/name, staging/name)
        for name in FRONTEND:
            copy(ROOT/'frontend'/name, staging/'frontend'/name)
        for name in COMPONENTS:
            copy(ROOT/'frontend/src/components/ui'/name, staging/'frontend/src/components/ui'/name)
        assets = ROOT/'frontend/dist-core'
        if not (assets/'index.html').is_file():
            raise RuntimeError('请先构建核心前端')
        for file in assets.rglob('*'):
            if file.is_file():
                copy(file, staging/'frontend/dist-core'/file.relative_to(assets))
        package = json.loads((ROOT/'frontend/package.json').read_text(encoding='utf-8'))
        package['scripts'] = {'build': 'tsc -b && vite build --config vite.core.config.ts', 'dev': 'vite --config vite.core.config.ts'}
        (staging/'frontend/package.json').write_text(json.dumps(package, ensure_ascii=False, indent=2), encoding='utf-8')
        copy(ROOT/'distribution/README.md', staging/'README.md')
        copy(ROOT/'distribution/start-core.ps1', staging/'start-core.ps1')
        verify(staging)
        manifest = {p.relative_to(staging).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in sorted(staging.rglob('*'),key=lambda p:p.relative_to(staging).as_posix()) if p.is_file()}
        (staging/'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
        count = verify(staging)
        archive = output/'shiwen-core-v1-c.zip'
        with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as z:
            for p in sorted(staging.rglob('*'),key=lambda p:p.relative_to(staging).as_posix()):
                if p.is_file():
                    info=zipfile.ZipInfo(p.relative_to(staging).as_posix(),(1980,1,1,0,0,0))
                    info.create_system=3
                    info.external_attr=0o100644 << 16
                    info.compress_type=zipfile.ZIP_DEFLATED
                    z.writestr(info,p.read_bytes(),compress_type=zipfile.ZIP_DEFLATED,compresslevel=9)
        with tempfile.TemporaryDirectory(prefix='core-verify-') as extracted:
            with zipfile.ZipFile(archive) as z:
                z.extractall(extracted)
            assert verify(extracted) == count
        return {'archive': str(archive), 'files': count, 'sha256': hashlib.sha256(archive.read_bytes()).hexdigest()}


if __name__ == '__main__':
    print(json.dumps(build(), ensure_ascii=False))
