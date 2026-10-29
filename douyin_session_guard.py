"""One cross-process lock for Shiwen-owned Douyin session operations."""
import os,time,threading,sys
from pathlib import Path
from contextlib import contextmanager
_LOCAL=threading.local()
@contextmanager
def session_guard():
 if getattr(_LOCAL,'active',False):
  yield;return
 module=sys.modules.get('store')
 data=getattr(module,'DATA',Path(os.environ.get('SHIWEN_DATA_DIR',Path(__file__).resolve().parent/'data')))
 path=Path(data)/'douyin-session.lock';path.parent.mkdir(parents=True,exist_ok=True)
 with path.open('a+b') as f:
  if f.tell()==0:f.write(b'0');f.flush()
  deadline=time.monotonic()+600
  while True:
   try:
    f.seek(0)
    if os.name=='nt':
     import msvcrt;msvcrt.locking(f.fileno(),msvcrt.LK_NBLCK,1)
    else:
     import fcntl;fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
    break
   except (OSError,BlockingIOError):
    if time.monotonic()>deadline:raise RuntimeError('抖音会话正在使用，请稍后重试')
    time.sleep(.3)
  _LOCAL.active=True
  try:yield
  finally:
   _LOCAL.active=False
   time.sleep(2);f.seek(0)
   if os.name=='nt':msvcrt.locking(f.fileno(),msvcrt.LK_UNLCK,1)
   else:fcntl.flock(f,fcntl.LOCK_UN)
