from __future__ import annotations

import os
import shutil
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from . import __version__
from .discovery import MinecraftLibrary, build_details, file_format, format_label
from .modmeta import icon_bytes_from_jar
from .parsers import ConfigParseError, parse_config_text, public_fields, update_config_text
from .settings import (
    BACKUP_DIR,
    current_launcher,
    detect_launcher,
    detection_candidates,
    set_launcher,
    validate_config_file,
)
from .util import atomic_write, human_size, safe_filename, sha1_text, sha256_bytes


MAX_CONFIG_BYTES = 8 * 1024 * 1024
CACHE_TTL_SECONDS = 120
BACKUP_KEEP = 120


class ApiError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message = message
        self.status = status


class ConflictError(ApiError):
    def __init__(self, message: str):
        super().__init__(message, 409)


def decode_config_bytes(data: bytes) -> Tuple[str, str, bytes]:
    if len(data) > MAX_CONFIG_BYTES:
        raise ApiError("配置文件超过 %s，暂不支持编辑" % human_size(MAX_CONFIG_BYTES))
    if data.startswith(b"\xef\xbb\xbf"):
        try:
            return data[3:].decode("utf-8"), "utf-8", b"\xef\xbb\xbf"
        except UnicodeDecodeError:
            pass
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        try:
            text = data.decode("utf-16")
            if data.startswith(b"\xff\xfe"):
                return text, "utf-16-le", b"\xff\xfe"
            return text, "utf-16-be", b"\xfe\xff"
        except UnicodeDecodeError:
            pass
    if b"\x00" in data:
        raise ApiError("该文件看起来是二进制文件，无法作为配置编辑")
    for encoding in ("utf-8", "gbk", "cp1252"):
        try:
            return data.decode(encoding), encoding, b""
        except UnicodeDecodeError:
            continue
    try:
        return data.decode("latin-1"), "latin-1", b""
    except UnicodeDecodeError:  # pragma: no cover - latin-1 always decodes bytes
        raise ApiError("无法识别配置文件编码")


def encode_config_text(text: str, encoding: str, bom: bytes) -> bytes:
    try:
        return bom + text.encode(encoding)
    except UnicodeEncodeError:
        raise ApiError("修改后的内容包含当前文件编码无法表示的字符（%s）" % encoding)


def _resize_icon(data: bytes, size: int = 128) -> Optional[bytes]:
    try:
        from io import BytesIO

        from PIL import Image

        image = Image.open(BytesIO(data))
        image.load()
        if image.mode not in ("RGBA", "RGB"):
            image = image.convert("RGBA")
        image.thumbnail((size, size), Image.LANCZOS)
        buffer = BytesIO()
        image.save(buffer, format="PNG", optimize=True)
        return buffer.getvalue()
    except Exception:
        return None


class ConfigService:
    def __init__(self):
        self._lock = threading.RLock()
        self._libraries: Dict[str, MinecraftLibrary] = {}
        self._details_cache: Dict[str, Dict] = {}
        self._detail_time: Dict[str, float] = {}
        self._parse_cache: Dict[str, Tuple[Tuple[int, int], Dict]] = {}
        self._icon_cache: Dict[str, Tuple[bytes, str]] = {}
        self._version_icon_cache: Dict[str, Tuple[Tuple[int, int], bytes, str]] = {}

    # ------------------------------------------------------------------
    # Launcher / versions

    def library(self) -> Tuple[Path, MinecraftLibrary]:
        root = current_launcher()
        if not root:
            raise ApiError("没有找到 Minecraft 目录，请先手动选择 .minecraft 文件夹", 404)
        key = str(root).lower()
        library = self._libraries.get(key)
        if library is None:
            library = MinecraftLibrary(root)
            self._libraries[key] = library
        return root, library

    def status(self) -> Dict:
        root = current_launcher()
        detected = detect_launcher()
        candidates = []
        for candidate in detection_candidates():
            try:
                if candidate.is_dir():
                    candidates.append(str(candidate))
            except OSError:
                pass
        return {
            "app": "CraftTune",
            "version": __version__,
            "launcher": str(root) if root else "",
            "detected": str(detected) if detected else "",
            "candidates": candidates[:6],
            "platform": os.name,
            "backup_dir": str(BACKUP_DIR),
        }

    def choose_launcher(self, raw_path: str) -> Dict:
        try:
            root = set_launcher(raw_path)
        except ValueError as exc:
            raise ApiError(str(exc), 400)
        self._libraries.clear()
        self._details_cache.clear()
        self._detail_time.clear()
        return {"ok": True, "launcher": str(root), "versions": self.list_versions()}

    def list_versions(self) -> List[Dict]:
        root = current_launcher()
        if not root:
            return []
        _, library = self.library()
        versions = library.list_versions()
        for version in versions:
            # The icon_path is internal; the browser uses /api/version-icon.
            version.pop("icon_path", None)
        return versions

    def version_summary(self, version_id: str) -> Tuple[Path, MinecraftLibrary, Dict]:
        root, library = self.library()
        version = library.find_version(version_id)
        if not version:
            raise ApiError("游戏版本不存在：%s" % version_id, 404)
        return root, library, version

    def details(self, version_id: str, force: bool = False) -> Dict:
        root, library, version = self.version_summary(version_id)
        now = time.time()
        cached = self._details_cache.get(version_id)
        cached_at = self._detail_time.get(version_id, 0)
        if cached is not None and not force and now - cached_at < CACHE_TTL_SECONDS:
            return cached
        with self._lock:
            cached = self._details_cache.get(version_id)
            if cached is not None and not force and time.time() - self._detail_time.get(version_id, 0) < CACHE_TTL_SECONDS:
                return cached
            data = build_details(library, version)
            data["root"] = str(root)
            self._details_cache[version_id] = data
            self._detail_time[version_id] = time.time()
            return data

    def refresh(self, version_id: Optional[str] = None) -> Dict:
        with self._lock:
            if version_id:
                self._details_cache.pop(version_id, None)
                self._detail_time.pop(version_id, None)
                for key in [key for key in self._parse_cache if key.startswith(version_id + "\x1f")]:
                    self._parse_cache.pop(key, None)
            else:
                self._details_cache.clear()
                self._detail_time.clear()
                self._parse_cache.clear()
                self._libraries.clear()
        return {"ok": True}

    def mods_payload(self, version_id: str) -> Dict:
        details = self.details(version_id)
        version = details["version"]
        mods = []
        for mod in details["mods"]:
            public = dict(mod)
            public.pop("config_files", None)
            public.pop("jar_path", None)
            public.pop("rel_path", None)
            public["icon"] = bool(mod.get("icon_entry"))
            mods.append(public)
        return {
            "version": version,
            "mods": mods,
            "stats": details["stats"],
            "paths": {
                "mods": details.get("mods_dir", ""),
                "config": details.get("config_dir", ""),
            },
        }

    def _mod_and_files(self, version_id: str, mod_key: str) -> Tuple[Dict, List[Dict], Dict]:
        details = self.details(version_id)
        if mod_key == "__other__":
            mod = details.get("other")
            if not mod:
                raise ApiError("没有未归属的配置文件", 404)
            files = list(mod.get("config_files") or [])
        else:
            mod = details["mods_by_key"].get(mod_key)
            if not mod:
                raise ApiError("模组不存在或尚未扫描完成", 404)
            files = list(mod.get("config_files") or [])
        return mod, files, details

    def mod_payload(self, version_id: str, mod_key: str) -> Dict:
        mod, files, details = self._mod_and_files(version_id, mod_key)
        file_payload = []
        total_fields = 0
        count_all = len(files) <= 60 and sum(int(item.get("size") or 0) for item in files) <= 20 * 1024 * 1024
        for file_info in files:
            entry = {key: value for key, value in file_info.items() if key not in ("mtime", "depth", "top")}
            size = int(file_info.get("size") or 0)
            if not count_all or size > 1_500_000:
                entry["field_count"] = None
                entry["warnings"] = []
                entry["detected_format"] = "源码模式" if size > 1_500_000 else ""
                file_payload.append(entry)
                if size > 1_500_000:
                    count_all = False
                continue
            try:
                parsed = self._parse_file(Path(details["config_dir"]) / file_info["path"], file_info, version_id)
                count = len(parsed["fields"])
                entry["field_count"] = count
                entry["warnings"] = parsed.get("warnings", [])[:2]
                entry["detected_format"] = parsed.get("detected_format") or format_label(parsed.get("format", ""))
                if parsed.get("raw_only"):
                    entry["warnings"] = parsed.get("warnings", [])[:1]
                total_fields += count
            except (ApiError, OSError, ValueError) as exc:
                entry["field_count"] = None
                entry["warnings"] = [str(exc)]
            file_payload.append(entry)
        file_payload.sort(key=lambda item: item["path"].lower())
        public_mod = {key: value for key, value in mod.items() if key not in ("config_files", "jar_path", "rel_path")}
        public_mod["icon"] = bool(mod.get("icon_entry"))
        return {
            "version": details["version"],
            "mod": public_mod,
            "configs": file_payload,
            "total_fields": total_fields if count_all else None,
            "config_dir": details.get("config_dir", ""),
            "is_virtual": bool(mod.get("is_virtual")),
        }

    # ------------------------------------------------------------------
    # Config files

    def _cache_key(self, version_id: str, path: Path) -> str:
        return version_id + "\x1f" + str(path.resolve()).lower()

    def _read_file(self, version_id: str, path: Path) -> Tuple[str, str, bytes, str, int]:
        try:
            data = path.read_bytes()
        except OSError as exc:
            raise ApiError("无法读取配置文件：%s" % exc)
        text, encoding, bom = decode_config_bytes(data)
        return text, encoding, bom, sha256_bytes(data), len(data)

    def _parse_file(self, path: Path, file_info: Optional[Dict] = None, version_id: str = "") -> Dict:
        try:
            stat = path.stat()
        except OSError as exc:
            raise ApiError("无法访问配置文件：%s" % exc)
        cache_key = self._cache_key(version_id, path) if version_id else ""
        stamp = (int(stat.st_mtime_ns), int(stat.st_size))
        if cache_key:
            cached = self._parse_cache.get(cache_key)
            if cached and cached[0] == stamp:
                return cached[1]
        text, _, _, _, _ = self._read_file(version_id or "_", path)
        rel = (file_info or {}).get("path") or path.name
        fmt = (file_info or {}).get("format") or file_format(rel)
        parsed = parse_config_text(text, fmt)
        if file_info is not None:
            file_info["field_count"] = len(parsed["fields"])
        if cache_key:
            self._parse_cache[cache_key] = (stamp, parsed)
        return parsed

    def _config_target(self, details: Dict, rel_path: str) -> Path:
        config_dir = details.get("config_dir")
        if not config_dir:
            raise ApiError("该版本没有 config 目录", 404)
        try:
            return validate_config_file(Path(config_dir), rel_path)
        except FileNotFoundError as exc:
            raise ApiError(str(exc), 404)
        except (ValueError, OSError) as exc:
            raise ApiError(str(exc), 400)

    def config_payload(self, version_id: str, mod_key: str, rel_path: str) -> Dict:
        mod, files, details = self._mod_and_files(version_id, mod_key)
        target = self._config_target(details, rel_path)
        text, encoding, bom, digest, size = self._read_file(version_id, target)
        fmt = file_format(rel_path)
        parsed = parse_config_text(text, fmt)
        file_info = next((item for item in files if item["path"].replace("\\", "/") == rel_path.replace("\\", "/")), None)
        if not file_info:
            # Be permissive: a valid file inside config can still be opened through a mod page.
            file_info = {
                "path": rel_path,
                "name": target.name,
                "format": fmt,
                "format_label": format_label(fmt),
                "size": size,
                "size_label": human_size(size),
            }
        public = {
            "file": {key: value for key, value in file_info.items() if key not in ("mtime", "depth", "top")},
            "format": parsed.get("format", fmt),
            "format_label": parsed.get("detected_format") or format_label(parsed.get("format", fmt)),
            "fields": public_fields(parsed["fields"]),
            "warnings": parsed.get("warnings", []),
            "note": parsed.get("note", ""),
            "raw": text,
            "raw_only": bool(parsed.get("raw_only")),
            "hash": digest,
            "encoding": encoding,
            "has_bom": bool(bom),
            "size": size,
            "size_label": human_size(size),
            "line_count": text.count("\n") + (0 if text.endswith("\n") else 1),
            "editable": True,
            "mod": {
                "key": mod.get("key"),
                "name": mod.get("name"),
                "id": mod.get("id"),
                "icon": bool(mod.get("icon_entry")),
            },
        }
        return public

    def save_config(
        self,
        version_id: str,
        mod_key: str,
        rel_path: str,
        base_hash: str,
        changes: Optional[List[Dict]] = None,
        raw: Optional[str] = None,
    ) -> Dict:
        mod, files, details = self._mod_and_files(version_id, mod_key)
        target = self._config_target(details, rel_path)
        current_bytes = target.read_bytes()
        current_hash = sha256_bytes(current_bytes)
        if base_hash and base_hash != current_hash:
            raise ConflictError("文件已被外部修改，请重新载入后再保存")
        text, encoding, bom, _, _ = self._read_file(version_id, target)
        fmt = file_format(rel_path)
        warnings: List[str] = []
        if raw is not None:
            # Browser textareas normalise line endings to LF. Restore the file's
            # original newline style so a source-mode save does not rewrite it.
            original_newline = "\r\n" if "\r\n" in text else "\n"
            new_text = raw.replace("\r\n", "\n").replace("\r", "\n")
            if original_newline == "\r\n":
                new_text = new_text.replace("\n", "\r\n")
            if "\x00" in new_text:
                raise ApiError("内容中不能包含 NUL 字符")
            parsed_after = parse_config_text(new_text, fmt)
            warnings = parsed_after.get("warnings", [])
        else:
            if not changes:
                raise ApiError("没有需要保存的修改")
            try:
                new_text, warnings = update_config_text(text, fmt, changes)
            except ConfigParseError as exc:
                raise ApiError(str(exc))
        new_bytes = encode_config_text(new_text, encoding, bom)
        if new_bytes == current_bytes:
            return {
                "ok": True,
                "unchanged": True,
                "hash": current_hash,
                "message": "内容没有变化",
            }
        backup_label = self._backup(version_id, rel_path, current_bytes)
        try:
            atomic_write(target, new_bytes)
        except OSError as exc:
            raise ApiError("写入失败：%s" % exc)
        parsed_after = parse_config_text(new_text, fmt)
        self._parse_cache.pop(self._cache_key(version_id, target), None)
        return {
            "ok": True,
            "hash": sha256_bytes(new_bytes),
            "raw": new_text,
            "fields": public_fields(parsed_after["fields"]),
            "warnings": parsed_after.get("warnings", warnings),
            "format": parsed_after.get("format", fmt),
            "format_label": parsed_after.get("detected_format") or format_label(parsed_after.get("format", fmt)),
            "size": len(new_bytes),
            "size_label": human_size(len(new_bytes)),
            "line_count": new_text.count("\n") + (0 if new_text.endswith("\n") else 1),
            "backup": backup_label,
            "saved_at": datetime.now().strftime("%H:%M:%S"),
        }

    def _backup(self, version_id: str, rel_path: str, data: bytes) -> str:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        folder = BACKUP_DIR / stamp / safe_filename(version_id)
        target = folder / rel_path
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        except OSError:
            return ""
        self._trim_backups()
        return "%s/%s/%s" % (stamp, safe_filename(version_id), rel_path)

    def _trim_backups(self) -> None:
        try:
            folders = sorted([item for item in BACKUP_DIR.iterdir() if item.is_dir()], key=lambda item: item.name, reverse=True)
            for old in folders[BACKUP_KEEP:]:
                if old.resolve().parent == BACKUP_DIR.resolve():
                    shutil.rmtree(str(old), ignore_errors=True)
        except OSError:
            pass

    # ------------------------------------------------------------------
    # Icons

    def mod_icon(self, version_id: str, mod_key: str) -> Optional[Tuple[bytes, str]]:
        mod, files, details = self._mod_and_files(version_id, mod_key)
        icon_entry = mod.get("icon_entry")
        jar_path = mod.get("jar_path")
        if not icon_entry or not jar_path:
            return None
        cache_key = sha1_text(str(jar_path) + "|" + str(icon_entry))
        cached = self._icon_cache.get(cache_key)
        if cached:
            return cached
        data, mime = icon_bytes_from_jar(Path(jar_path), icon_entry)
        if not data:
            return None
        if mime == "image/svg+xml":
            result = (data, mime)
            self._icon_cache[cache_key] = result
            return result
        resized = _resize_icon(data, 128)
        result = (resized, "image/png") if resized else (data, "image/png")
        self._icon_cache[cache_key] = result
        return result

    def version_icon(self, version_id: str) -> Optional[Tuple[bytes, str]]:
        _, library, version = self.version_summary(version_id)
        path = version.get("icon_path")
        if not path:
            return None
        target = Path(path)
        try:
            stat = target.stat()
        except OSError:
            return None
        stamp = (int(stat.st_mtime_ns), stat.st_size)
        cached = self._version_icon_cache.get(version_id)
        if cached and cached[0] == stamp:
            return cached[1], cached[2]
        try:
            data = target.read_bytes()
        except OSError:
            return None
        suffix = target.suffix.lower()
        if suffix == ".svg":
            mime = "image/svg+xml"
            payload = data
        else:
            resized = _resize_icon(data, 128)
            mime = "image/png"
            payload = resized if resized else data
            if not resized:
                if suffix in (".jpg", ".jpeg"):
                    mime = "image/jpeg"
                elif suffix == ".webp":
                    mime = "image/webp"
        self._version_icon_cache[version_id] = (stamp, payload, mime)
        return payload, mime

    # ------------------------------------------------------------------
    # Misc actions

    def reveal(self, version_id: str, rel_path: Optional[str] = None) -> Dict:
        details = self.details(version_id)
        config_dir = details.get("config_dir")
        if not config_dir:
            raise ApiError("该版本没有 config 目录", 404)
        target = Path(config_dir)
        if rel_path:
            try:
                target = validate_config_file(target, rel_path)
            except (ValueError, OSError) as exc:
                raise ApiError(str(exc), 404)
        try:
            if os.name == "nt":
                if target.is_file():
                    subprocess.Popen(["explorer", "/select,", str(target)])
                else:
                    os.startfile(str(target))  # type: ignore[attr-defined]
            elif sys.platform == "darwin":  # type: ignore[name-defined]
                subprocess.Popen(["open", str(target if target.is_dir() else target.parent)])
            else:
                subprocess.Popen(["xdg-open", str(target if target.is_dir() else target.parent)])
        except OSError as exc:
            raise ApiError("无法打开文件夹：%s" % exc)
        return {"ok": True, "path": str(target)}

    def open_backups(self) -> Dict:
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        try:
            if os.name == "nt":
                os.startfile(str(BACKUP_DIR))  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(BACKUP_DIR)])
            else:
                subprocess.Popen(["xdg-open", str(BACKUP_DIR)])
        except OSError as exc:
            raise ApiError("无法打开备份目录：%s" % exc)
        return {"ok": True, "path": str(BACKUP_DIR)}

    def pick_folder(self) -> Dict:
        try:
            import tkinter as tk
            from tkinter import filedialog

            root = tk.Tk()
            root.withdraw()
            root.attributes("-topmost", True)
            initial = ""
            try:
                initial = str(current_launcher() or Path.home())
            except Exception:
                initial = str(Path.home())
            chosen = filedialog.askdirectory(title="选择 Minecraft 的 .minecraft 文件夹", initialdir=initial)
            root.destroy()
            return {"path": chosen or ""}
        except Exception as exc:
            raise ApiError("无法打开系统文件夹选择框，请手动输入路径（%s）" % exc, 400)
