"""冻结的客户包构建链：2026-11-01 从仓库根目录归档，保留可读、不参与默认测试。

客户包（core / customer 白名单 ZIP）自 2026-10-29 冻结，自用主线只走 app.py。
三个脚本原样搬来，必要时用 git 历史取回：`git log --follow vendor-archive/build_core_package.py`。
跑这里的归档测试：

    .venv/Scripts/python.exe -m pytest vendor-archive/tests -q

它们假设仓库根目录在 sys.path 上（由 `_archive_path.py` 注入），并且需要本机已构建
frontend/dist 等构建产物；默认全量测试不收集本目录。
"""
