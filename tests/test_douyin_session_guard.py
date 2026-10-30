import os,subprocess,sys,tempfile,unittest
from pathlib import Path
import store
from unittest.mock import patch
class SessionExclusion(unittest.TestCase):
 def test_nested_guard_and_exception_release(self):
  import douyin_session_guard as guard
  with tempfile.TemporaryDirectory(dir=store.ROOT/'runtime') as tmp,patch.object(store,'DATA',Path(tmp)):
   with self.assertRaises(ValueError):
    with guard.session_guard():
     with guard.session_guard():self.assertTrue(guard._LOCAL.active)
     raise ValueError('exercise release')
   self.assertFalse(guard._LOCAL.active)
   with guard.session_guard():self.assertTrue(guard._LOCAL.active)
   self.assertFalse(guard._LOCAL.active)
 def test_guard_import_does_not_shadow_external_store_package(self):
  r=subprocess.run([sys.executable,'-c',"import douyin_session_guard,sys;assert 'store' not in sys.modules"],cwd=store.ROOT,capture_output=True,timeout=10,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
  self.assertEqual(r.returncode,0,r.stderr)
 def test_two_processes_cannot_overlap_session_use(self):
  with tempfile.TemporaryDirectory(dir=store.ROOT/'runtime') as tmp:
   env={**os.environ,'SHIWEN_DATA_DIR':tmp}
   script="from douyin_session_guard import session_guard;import time\nwith session_guard():\n print(time.monotonic(),flush=True)\n time.sleep(.2)\n print(time.monotonic(),flush=True)\n"
   options=dict(cwd=store.ROOT,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
   first=subprocess.Popen([sys.executable,'-c',script],**options)
   try:
    entered=float(first.stdout.readline());second=subprocess.Popen([sys.executable,'-c',script],**options)
    try:
     second_entered=float(second.stdout.readline());remaining,error=first.communicate(timeout=8);second.communicate(timeout=8)
     ended=float(remaining.strip());self.assertGreaterEqual(second_entered,ended+1.5);self.assertEqual(first.returncode,0);self.assertEqual(second.returncode,0)
    finally:
     if second.poll() is None:second.kill();second.wait()
   finally:
    if first.poll() is None:first.kill();first.wait()
if __name__=='__main__':unittest.main()
