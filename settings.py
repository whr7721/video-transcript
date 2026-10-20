import base64
import ctypes
import json
import os
import threading

from store import DATA, atomic_json

FILE = DATA / "settings.json"
SAVE_LOCK = threading.RLock()


class Blob(ctypes.Structure):
    _fields_ = [("size", ctypes.c_ulong), ("data", ctypes.POINTER(ctypes.c_ubyte))]


def protect(value, decrypt=False):
    raw = base64.b64decode(value) if decrypt else value.encode()
    buffer = ctypes.create_string_buffer(raw)
    source = Blob(len(raw), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)))
    output = Blob()
    crypt = ctypes.windll.crypt32
    if decrypt:
        ok = crypt.CryptUnprotectData(ctypes.byref(source), None, None, None, None, 0, ctypes.byref(output))
    else:
        ok = crypt.CryptProtectData(ctypes.byref(source), "拾文 API Key", None, None, None, 0, ctypes.byref(output))
    if not ok:
        raise RuntimeError("无法使用 Windows 账户加密保存 Key。")
    try:
        data = ctypes.string_at(output.data, output.size)
        return data.decode() if decrypt else base64.b64encode(data).decode()
    finally:
        ctypes.windll.kernel32.LocalFree(output.data)


def read():
    if FILE.exists():
        return json.loads(FILE.read_text(encoding="utf-8"))
    return {"provider": "local"}


def cloud_key():
    configured = os.environ.get("SILICONFLOW_API_KEY", "")
    if configured:
        return configured
    encrypted = read().get("encrypted_key", "")
    return protect(encrypted, decrypt=True) if encrypted else ""


def search_key():
    configured = os.environ.get("DEEPSEEK_API_KEY", "")
    if configured: return configured
    encrypted = read().get("encrypted_search_key", "")
    return protect(encrypted, decrypt=True) if encrypted else ""


def public():
    value = read()
    return {"provider": value.get("provider", "local"),
            "key_configured": bool(value.get("encrypted_key") or os.environ.get("SILICONFLOW_API_KEY")),
            "monthly_budget_yuan": 10, "search_key_configured": bool(value.get("encrypted_search_key") or os.environ.get("DEEPSEEK_API_KEY")),
            "paid_models_enabled": True, "text_model": "deepseek-ai/DeepSeek-V4.1-Flash"}


def save(provider, key=None, deepseek_key=None):
    with SAVE_LOCK:
        value = read()
        value["provider"] = provider
        if key is not None and key.strip(): value["encrypted_key"] = protect(key.strip())
        if deepseek_key is not None and deepseek_key.strip(): value["encrypted_search_key"] = protect(deepseek_key.strip())
        atomic_json(FILE, value)
