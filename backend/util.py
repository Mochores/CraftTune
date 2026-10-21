from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any, Iterable, Optional, Sequence


def json_dumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha1_text(value: str) -> str:
    return hashlib.sha1(value.encode("utf-8", "replace")).hexdigest()


def human_size(size: int) -> str:
    if size < 1024:
        return "%d B" % size
    if size < 1024 * 1024:
        return "%.1f KB" % (size / 1024.0)
    return "%.1f MB" % (size / 1024.0 / 1024.0)


def is_within(base: Path, target: Path) -> bool:
    """Return True when target is base itself or lives below base."""
    try:
        base_s = os.path.normcase(str(base.resolve()))
        target_s = os.path.normcase(str(target.resolve()))
        return os.path.commonpath([base_s, target_s]) == base_s
    except (ValueError, OSError):
        return False


def safe_filename(name: str) -> str:
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name)
    return name.strip(" .") or "config"


def atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=".crafttune-", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, str(path))
    finally:
        if os.path.exists(tmp_name):
            try:
                os.unlink(tmp_name)
            except OSError:
                pass


def normalize_token(value: str) -> str:
    """Normalize an id or filename for fuzzy matching."""
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def title_from_key(key: str) -> str:
    """Turn camelCase / snake_case config keys into a readable label."""
    if not key:
        return key
    text = re.sub(r"[_\-.]+", " ", key)
    text = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", text)
    text = re.sub(r"(?<=[A-Z])(?=[A-Z][a-z])", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return key
    # Keep known all-caps identifiers intact (e.g. FPS, HUD).
    words = []
    for word in text.split(" "):
        if word.isupper() and len(word) <= 5:
            words.append(word)
        else:
            words.append(word[:1].upper() + word[1:])
    return " ".join(words)


def infer_value_type(value: Any) -> str:
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int) and not isinstance(value, bool):
        return "integer"
    if isinstance(value, float):
        return "float"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    if value is None:
        return "null"
    return "string"


def json_safe(value: Any) -> Any:
    """Convert parser output into JSON-serialisable values."""
    if isinstance(value, (str, int, float, bool)) or value is None:
        if isinstance(value, float) and (value != value or value in (float("inf"), float("-inf"))):
            return str(value)
        return value
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(v) for v in value]
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def first_line(text: str, limit: int = 220) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    if len(text) > limit:
        return text[: limit - 1].rstrip() + "…"
    return text


def unique(items: Iterable[str]) -> list:
    seen = set()
    out = []
    for item in items:
        key = item.lower()
        if item and key not in seen:
            seen.add(key)
            out.append(item)
    return out
