from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional

from .util import atomic_write, is_within


if getattr(sys, "frozen", False):
    APP_ROOT = Path(sys.executable).resolve().parent
else:
    APP_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = APP_ROOT / "data"
SETTINGS_FILE = DATA_DIR / "settings.json"
CACHE_DIR = DATA_DIR / "cache"
BACKUP_DIR = DATA_DIR / "backups"


def load_settings() -> Dict:
    try:
        with SETTINGS_FILE.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
            return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_settings(settings: Dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    atomic_write(SETTINGS_FILE, json.dumps(settings, ensure_ascii=False, indent=2).encode("utf-8"))


def looks_like_launcher(path: Path) -> bool:
    if not path or not path.is_dir():
        return False
    candidates = ("versions", "mods", "config")
    return any((path / name).is_dir() for name in candidates)


def normalize_launcher_path(raw: str) -> Optional[Path]:
    if not raw:
        return None
    text = raw.strip().strip('"').strip("'")
    if not text:
        return None
    path = Path(os.path.expandvars(os.path.expanduser(text)))
    # Accept a "versions" folder or a version folder and jump to its parent.
    if path.name.lower() == "versions" and path.is_dir():
        path = path.parent
    elif path.parent.name.lower() == "versions" and path.is_dir():
        path = path.parent.parent
    if looks_like_launcher(path):
        return path
    nested = path / ".minecraft"
    if looks_like_launcher(nested):
        return nested
    return None


def detection_candidates() -> List[Path]:
    candidates: List[Path] = []
    for env_name in ("MINECRAFT_HOME", "APPDATA", "LOCALAPPDATA"):
        value = os.environ.get(env_name)
        if not value:
            continue
        base = Path(value)
        if env_name == "MINECRAFT_HOME":
            candidates.append(base)
        else:
            candidates.append(base / ".minecraft")
    candidates.extend(
        [
            Path.home() / "AppData" / "Roaming" / ".minecraft",
            APP_ROOT / ".minecraft",
            APP_ROOT.parent / ".minecraft",
            Path("C:/Program Files (x86)/Minecraft Launcher/.minecraft"),
        ]
    )
    if os.name != "nt":
        candidates.extend([Path.home() / ".minecraft", Path.home() / "Library/Application Support/minecraft"])
    seen = set()
    result = []
    for path in candidates:
        key = str(path).lower()
        if key not in seen:
            seen.add(key)
            result.append(path)
    return result


def detect_launcher() -> Optional[Path]:
    for path in detection_candidates():
        normalized = normalize_launcher_path(str(path))
        if normalized:
            return normalized
    return None


def current_launcher() -> Optional[Path]:
    settings = load_settings()
    saved = normalize_launcher_path(str(settings.get("launcher", "")))
    if saved:
        return saved
    detected = detect_launcher()
    if detected:
        settings["launcher"] = str(detected)
        try:
            save_settings(settings)
        except OSError:
            pass
    return detected


def set_launcher(raw: str) -> Path:
    normalized = normalize_launcher_path(raw)
    if not normalized:
        raise ValueError("该路径不是有效的 Minecraft 启动器目录（需要包含 versions、mods 或 config）")
    settings = load_settings()
    settings["launcher"] = str(normalized)
    save_settings(settings)
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return normalized


def validate_config_file(config_root: Path, rel_path: str) -> Path:
    if not rel_path or "\x00" in rel_path:
        raise ValueError("配置文件路径无效")
    rel = Path(rel_path.replace("\\", "/"))
    if rel.is_absolute() or ".." in rel.parts:
        raise ValueError("配置文件路径无效")
    target = (config_root / rel).resolve()
    if not is_within(config_root, target):
        raise ValueError("配置文件不在当前配置目录中")
    if not target.is_file():
        raise FileNotFoundError("配置文件不存在")
    return target
