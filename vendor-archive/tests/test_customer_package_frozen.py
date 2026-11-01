"""冻结链的归档测试：默认全量测试不收集，按 vendor-archive/README.md 手动运行。"""
import _archive_path  # noqa: F401  把仓库根与 vendor-archive 放进 sys.path
import argparse
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import shiwen
import store
import build_customer_package as builder


class CustomerPackage(unittest.TestCase):


    def test_delivery_cli_has_no_private_import(self):
        import ast
        tree=ast.parse(builder.delivery_cli())
        imports=[n.names[0].name for n in ast.walk(tree) if isinstance(n,ast.Import)]
        self.assertNotIn('pipeline',imports)
        self.assertIn('customer_env',imports)


if __name__=='__main__':unittest.main()
