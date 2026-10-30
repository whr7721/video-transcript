"""Optional pinned speaker models; hashes measured from official release assets."""
from pathlib import Path
import shutil,tarfile,tempfile,urllib.request
import setup_models
SEG='sherpa-onnx-pyannote-segmentation-3-0/model.int8.onnx'
EMBED='3dspeaker_speech_campplus_sv_zh_en_16k-common_advanced.onnx'
FILES={SEG:(1540506,'d582f4b4c6b48205de7e0643c57df0df5615a3c176189be3fc461e9d18827b5d'),EMBED:(28281164,'aa3cfc16963a10586a9393f5035d6d6b57e98d358b347f80c2a30bf4f00ceba2')}
def verify(root):return {n:setup_models.valid(Path(root)/n,v) for n,v in FILES.items()}
def prepare(root=None,local=None,offline=False):
 root=Path(root or Path(__file__).parent/'models');root.mkdir(parents=True,exist_ok=True)
 for n,expected in FILES.items():
  dest=root/n
  if setup_models.valid(dest,expected):continue
  dest.parent.mkdir(parents=True,exist_ok=True)
  if local:
   source=Path(local)/n
   if not setup_models.valid(source,expected):raise ValueError('说话人模型未通过校验：'+n)
   shutil.copyfile(source,dest);continue
  if offline:raise ValueError('离线说话人模型缺失：'+n)
  archive=n==SEG
  url='https://github.com/k2-fsa/sherpa-onnx/releases/download/'+('speaker-segmentation-models/sherpa-onnx-pyannote-segmentation-3-0.tar.bz2' if archive else 'speaker-recongition-models/'+n)
  with tempfile.TemporaryDirectory(dir=root) as tmp:
   download=Path(tmp)/'download';opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
   limit=6958444 if archive else expected[0]
   with opener.open(url,timeout=60) as response,download.open('wb') as f:
    count=0
    while block:=response.read(1024*1024):
     count+=len(block)
     if count>limit:raise ValueError('说话人模型下载超出大小')
     f.write(block)
   if archive:
    if not setup_models.valid(download,(6958444,'24615ee884c897d9d2ba09bb4d30da6bb1b15e685065962db5b02e76e4996488')):raise ValueError('说话人模型压缩包校验失败')
    with tarfile.open(download) as t:
     m=t.getmember(n)
     if not m.isfile() or m.size!=expected[0]:raise ValueError('说话人模型成员错误')
     data=Path(tmp)/'model';data.write_bytes(t.extractfile(m).read())
   else:data=download
   if not setup_models.valid(data,expected):raise ValueError('说话人模型哈希校验失败')
   data.replace(dest)
 return verify(root)
if __name__=='__main__':print(prepare())
