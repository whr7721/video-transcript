"""Pure rules shared by the isolated collector and local task service."""
import math
import re


def creator_id(url):
    match = re.search(r"/user/([A-Za-z0-9_-]{10,200})", url)
    return match.group(1) if match else None


def classify_post(post, max_duration_sec=600):
    ident = str(post.get("aweme_id", ""))
    if not re.fullmatch(r"\d{15,22}", ident):
        return "invalid", None
    if post.get("images") or not isinstance(post.get("video"), dict):
        return "image", None
    try:
        duration = float(post["video"].get("duration") or post.get("duration") or 0) / 1000
    except (ValueError, TypeError):
        duration = 0
    if not math.isfinite(duration) or duration <= 0:
        return "unknown", None
    return ("too_long" if duration > max_duration_sec else "eligible"), duration
