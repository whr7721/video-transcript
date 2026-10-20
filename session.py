"""Create a private, isolated session without launching the production profile."""
import shutil
from pathlib import Path

import psutil

ROOT = Path(__file__).resolve().parent
SOURCE = Path(r"D:\zcode1\mediacrawler\browser_data\dy_user_data_dir")
PROFILE = ROOT / "data" / "browser"


def prepare_session():
    if (PROFILE / "Default").exists():
        return
    if not SOURCE.is_dir():
        raise RuntimeError("未找到可复用的抖音会话，请先打开登录窗口。")
    for process in psutil.process_iter(["name", "cmdline"]):
        try:
            if (process.info["name"] or "").lower() not in {"chrome.exe", "chromium.exe", "msedge.exe"}:
                continue
            args = " ".join(process.info["cmdline"] or []).lower().replace("/", "\\")
            if str(SOURCE).lower() in args:
                raise RuntimeError("原采集浏览器正在使用登录目录，请待它退出后重试；原任务不会被关闭。")
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    PROFILE.mkdir(parents=True, exist_ok=True)
    # Copy only the browser identity, preferences and session stores. All further
    # Chromium writes go to PROFILE. Never remove locks in the production profile.
    for name in ["Local State", "Last Version"]:
        source = SOURCE / name
        if source.is_file():
            shutil.copy2(source, PROFILE / name)
    default = PROFILE / "Default"
    default.mkdir(exist_ok=True)
    for name in ["Network", "Local Storage", "Session Storage", "IndexedDB", "Preferences", "Secure Preferences", "Sessions", "Cookies", "Cookies-journal"]:
        source = SOURCE / "Default" / name
        if source.is_dir():
            shutil.copytree(source, default / name, dirs_exist_ok=True,
                            ignore=shutil.ignore_patterns("LOCK", "*.tmp"))
        elif source.is_file():
            shutil.copy2(source, default / name)


if __name__ == "__main__":
    prepare_session()
    print("独立会话已准备；未启动或改动原采集浏览器。")
