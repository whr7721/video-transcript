import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


class SessionConfig(unittest.TestCase):
    def test_environment_source_is_copied_without_modifying_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/'original';(source/'Default').mkdir(parents=True)
            (source/'Default'/'Preferences').write_text('fixture')
            env={**os.environ,'SHIWEN_DOUYIN_PROFILE':str(source),'SHIWEN_DATA_DIR':str(root/'isolated')}
            code='import session; session.prepare_session(); print(session.SOURCE); print(session.PROFILE)'
            p=subprocess.run([sys.executable,'-c',code],env=env,capture_output=True,text=True,check=True)
            self.assertIn(str(source.resolve()),p.stdout)
            self.assertEqual((source/'Default'/'Preferences').read_text(),'fixture')
            self.assertEqual((root/'isolated'/'browser'/'Default'/'Preferences').read_text(),'fixture')

    def test_default_source_is_unchanged(self):
        env={k:v for k,v in os.environ.items() if k!='SHIWEN_DOUYIN_PROFILE'}
        p=subprocess.run([sys.executable,'-c','import session; print(session.SOURCE)'],env=env,capture_output=True,text=True,check=True)
        self.assertEqual(Path(p.stdout.strip()),Path(r'D:\zcode1\mediacrawler\browser_data\dy_user_data_dir').resolve())
