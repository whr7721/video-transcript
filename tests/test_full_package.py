import importlib.util,json,os,subprocess,sys,tempfile,unittest,zipfile
from pathlib import Path
from unittest.mock import patch
import build_full_package as full,store
class FullPackageTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(dir=store.ROOT/'runtime');self.root=Path(self.tmp.name);self.mc=self.root/'collector';self.mc.mkdir()
  for name in ['base','cache','model','tools','proxy','media_platform/douyin','config','browser_data/Default','libs']:(self.mc/name).mkdir(parents=True,exist_ok=True)
  (self.mc/'media_platform/douyin/client.py').write_text('class DouYinClient: pass\n');(self.mc/'var.py').write_text('');(self.mc/'LICENSE').write_text('collector license');(self.mc/'libs/douyin.js').write_text('// JS asset')
  (self.mc/'config/settings.py').write_text('COOKIES="do-not-package-fixture"');(self.mc/'browser_data/Default/Cookies').write_text('do-not-package-fixture')
  self.discovery=self.root/'discovery.py';self.discovery.write_text('import os\nfrom pathlib import Path\nMC = Path(r"D:\\zcode1\\mediacrawler")\nPROFILE = ROOT / "browser"\n')
 def tearDown(self):self.tmp.cleanup()
 def test_full_archive_has_private_features_without_sessions_or_checkout_config(self):
  archive=full.build(self.root/'out',mc=self.mc,discovery=self.discovery)
  with zipfile.ZipFile(archive) as z:
   names=z.namelist();self.assertIn('shiwen/app.py',names);self.assertIn('shiwen/USER_GUIDE.html',names);self.assertIn('shiwen/vendor/mediacrawler/LICENSE',names);self.assertIn('shiwen/cli_chapters.py',names);self.assertIn('shiwen/video_frames.py',names)
   self.assertTrue(z.read('shiwen/app.py').startswith(b'import full_env'));self.assertEqual(json.loads(z.read('shiwen/full-package.json'))['sessions_included'],False)
   self.assertFalse(any('/browser_data/' in p or '/data-full/' in p or '/.venv/' in p for p in names));self.assertNotIn(b'do-not-package-fixture',b''.join(z.read(n) for n in names));self.assertIn(b'DISABLE_SSL_VERIFY=False',z.read('shiwen/vendor/mediacrawler/config/__init__.py'))
 def test_offline_requires_installed_seed_and_requirement_union(self):
  with self.assertRaises(ValueError):full.build(self.root/'out',offline_full=True)
  req=full.requirements();self.assertEqual(req.count('certifi=='),1);self.assertIn('playwright==1.64.0',req);self.assertIn('rapidocr==3.9.2',req)
 def test_fresh_owned_login_does_not_need_or_modify_external_profile(self):
  data=self.root/'newdata';external=self.root/'not-installed'
  env={**os.environ,'SHIWEN_DATA_DIR':str(data),'SHIWEN_DOUYIN_PROFILE':str(external)}
  p=subprocess.run([sys.executable,'-c','import session;session.prepare_session(for_login=True)'],cwd=store.ROOT,env=env,capture_output=True,text=True)
  self.assertEqual(p.returncode,0,p.stderr);self.assertTrue((data/'browser/Default').is_dir());self.assertFalse(external.exists())

if __name__=='__main__':unittest.main()
