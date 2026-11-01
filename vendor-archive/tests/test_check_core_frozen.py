"""冻结链的归档测试：默认全量测试不收集，按 vendor-archive/README.md 手动运行。"""
import _archive_path  # noqa: F401  把仓库根与 vendor-archive 放进 sys.path
import hashlib
import io
import json
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import setup_models as models
import socket
import check_core


class DeploymentTests(unittest.TestCase):


    def test_preflight_missing_models_optional_or_required_without_creating_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'requirements.lock.txt').write_text('')
            (root/'frontend/dist-core').mkdir(parents=True);(root/'frontend/dist-core/index.html').touch()
            with socket.socket() as held:
                held.bind(('127.0.0.1',0));held.listen();port=held.getsockname()[1]
                with patch.object(check_core,'ROOT',root),patch.dict('os.environ',{'SHIWEN_CORE_DATA_DIR':str(root/'absent-data')}),patch.object(models,'verify',return_value={'model':False}):
                    report=check_core.check(port)
                    indexed={x['name']:x for x in report['checks']}
                    self.assertFalse(indexed['port']['ok'])
                    self.assertFalse(indexed['model:model']['required'])
                    self.assertTrue({x['name']:x for x in check_core.check(port,True)['checks']}['model:model']['required'])
                    self.assertFalse((root/'absent-data').exists())
                    (root/'models').mkdir();(root/'models/model').write_bytes(b'corrupt')
                    self.assertTrue({x['name']:x for x in check_core.check(port)['checks']}['model:model']['required'])

    def test_preflight_rejects_foreign_directory_without_mutation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'requirements.lock.txt').write_text('');foreign=root/'foreign';foreign.mkdir();(foreign/'keep').write_text('unchanged')
            with patch.object(check_core,'ROOT',root),patch.dict('os.environ',{'SHIWEN_CORE_DATA_DIR':str(foreign)}),patch.object(models,'verify',return_value={}):
                report=check_core.check(0)
                self.assertFalse({x['name']:x for x in report['checks']}['data-profile']['ok'])
            self.assertEqual([x.name for x in foreign.iterdir()],['keep'])


if __name__=='__main__':unittest.main()
