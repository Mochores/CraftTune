from __future__ import annotations

import json
import re
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .util import first_line, normalize_token, unique

try:  # Python 3.11+
    import tomllib as _toml_reader  # type: ignore

    def _loads_toml(text: str) -> Dict:
        return _toml_reader.loads(text)

except ImportError:  # Python 3.8 - 3.10
    try:
        import toml as _toml  # type: ignore

        def _loads_toml(text: str) -> Dict:
            return _toml.loads(text)

    except ImportError:
        _loads_toml = None  # type: ignore


MAX_METADATA_BYTES = 2 * 1024 * 1024
LOADER_WORDS = {
    "fabric",
    "forge",
    "neoforge",
    "quilt",
    "common",
    "client",
    "server",
    "all",
    "universal",
    "mc",
    "minecraft",
    "mod",
}


def _read_entry(archive: zipfile.ZipFile, name: str) -> Optional[str]:
    try:
        info = archive.getinfo(name)
        if info.file_size > MAX_METADATA_BYTES:
            return None
        raw = archive.read(info)
        for encoding in ("utf-8-sig", "utf-8", "gbk", "latin-1"):
            try:
                return raw.decode(encoding)
            except UnicodeDecodeError:
                continue
    except (KeyError, OSError, RuntimeError, zipfile.BadZipFile):
        return None
    return None


def _as_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [part.strip() for part in re.split(r"[,;]", value) if part.strip()]
    if isinstance(value, dict):
        return [str(value.get("name") or value.get("id") or "")]
    if isinstance(value, (list, tuple)):
        out = []
        for item in value:
            if isinstance(item, str):
                out.append(item)
            elif isinstance(item, dict):
                out.append(str(item.get("name") or item.get("id") or ""))
        return [item for item in out if item]
    return [str(value)]


def _clean_description(value: Any) -> str:
    if isinstance(value, list):
        value = " ".join(str(item) for item in value)
    if not isinstance(value, str):
        return ""
    value = value.replace("\\n", "\n")
    value = re.sub(r"§.", "", value)
    value = re.sub(r"\r\n?", "\n", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    return value.strip()


def _normalize_icon_path(value: Any) -> Optional[str]:
    if not isinstance(value, str):
        return None
    path = value.strip().replace("\\", "/").lstrip("/")
    if not path or path.startswith("../") or "/../" in path:
        return None
    return path


def _fabric_metadata(text: str, fmt: str) -> Optional[Dict]:
    try:
        data = json.loads(text)
    except ValueError:
        return None
    mod_id = str(data.get("id") or "").strip()
    if not mod_id:
        return None
    authors = _as_list(data.get("authors"))
    authors += _as_list(data.get("contributors"))
    icon = data.get("icon")
    if isinstance(icon, dict):
        icon = icon.get("64") or icon.get("128") or icon.get("256") or next(iter(icon.values()), None)
    contact = data.get("contact") or {}
    homepage = contact.get("homepage") if isinstance(contact, dict) else None
    return {
        "id": mod_id,
        "ids": [mod_id],
        "name": str(data.get("name") or mod_id),
        "version": str(data.get("version") or ""),
        "authors": unique(authors),
        "description": _clean_description(data.get("description")),
        "homepage": str(homepage) if homepage else "",
        "environment": str(data.get("environment") or ""),
        "icon_entry": _normalize_icon_path(icon),
        "format": fmt,
        "license": str(data.get("license") or ""),
    }


def _quilt_metadata(text: str) -> Optional[Dict]:
    try:
        data = json.loads(text)
    except ValueError:
        return None
    loader = data.get("quilt_loader") or {}
    metadata = loader.get("metadata") or {}
    mod_id = str(loader.get("id") or "").strip()
    if not mod_id:
        return None
    return {
        "id": mod_id,
        "ids": [mod_id],
        "name": str(metadata.get("name") or mod_id),
        "version": str(loader.get("version") or ""),
        "authors": unique(_as_list(metadata.get("contributors"))),
        "description": _clean_description(metadata.get("description")),
        "homepage": str(metadata.get("contact", {}).get("homepage") or "")
        if isinstance(metadata.get("contact"), dict)
        else "",
        "environment": "",
        "icon_entry": _normalize_icon_path(metadata.get("icon")),
        "format": "quilt",
        "license": "",
    }


def _fallback_toml_mods(text: str) -> List[Dict]:
    """Very small fallback used only when no TOML library is available."""
    blocks = re.split(r"^\s*\[\[mods\]\]\s*$", text, flags=re.MULTILINE)
    mods = []
    for block in blocks[1:]:
        block = re.split(r"^\s*\[\[", block, maxsplit=1, flags=re.MULTILINE)[0]
        data: Dict[str, Any] = {}
        for key in ("modId", "displayName", "version", "authors", "description", "logoFile"):
            match = re.search(r'^\s*%s\s*=\s*(.+)$' % key, block, flags=re.MULTILINE)
            if not match:
                continue
            raw = match.group(1).strip()
            if raw.startswith("'''") or raw.startswith('"""'):
                continue
            if raw.startswith('"') and raw.endswith('"'):
                try:
                    raw = json.loads(raw)
                except ValueError:
                    raw = raw[1:-1]
            data[key] = raw
        if data.get("modId"):
            mods.append(data)
    return mods


def _forge_metadata(text: str, fmt: str) -> Optional[Dict]:
    data: Optional[Dict] = None
    if _loads_toml is not None:
        try:
            data = _loads_toml(text)
        except Exception:
            data = None
    mods: List[Dict] = []
    if isinstance(data, dict):
        raw_mods = data.get("mods")
        if isinstance(raw_mods, list):
            mods = [item for item in raw_mods if isinstance(item, dict)]
        elif isinstance(raw_mods, dict):
            mods = [raw_mods]
    if not mods:
        mods = _fallback_toml_mods(text)
    if not mods:
        return None
    primary = mods[0]
    mod_id = str(primary.get("modId") or primary.get("modid") or "").strip()
    if not mod_id:
        return None
    ids = [str(item.get("modId") or "").strip() for item in mods]
    ids = [item for item in ids if item]
    authors = []
    for item in mods:
        authors += _as_list(item.get("authors"))
        authors += _as_list(item.get("authorList"))
    return {
        "id": mod_id,
        "ids": unique(ids),
        "name": str(primary.get("displayName") or primary.get("displayName") or mod_id),
        "version": str(primary.get("version") or ""),
        "authors": unique(authors),
        "description": _clean_description(primary.get("description")),
        "homepage": str(primary.get("displayURL") or primary.get("issueTrackerURL") or ""),
        "environment": "",
        "icon_entry": _normalize_icon_path(primary.get("logoFile") or primary.get("logoFile")),
        "format": fmt,
        "license": str(primary.get("license") or ""),
    }


def _mcmod_metadata(text: str) -> Optional[Dict]:
    cleaned = re.sub(r"^\s*//.*$", "", text, flags=re.MULTILINE)
    try:
        data = json.loads(cleaned)
    except ValueError:
        return None
    if isinstance(data, dict):
        data = data.get("modList") or data.get("modlist") or [data]
    if not isinstance(data, list) or not data:
        return None
    primary = data[0] if isinstance(data[0], dict) else {}
    mod_id = str(primary.get("modid") or primary.get("modId") or "").strip()
    if not mod_id:
        return None
    ids = []
    for item in data:
        if isinstance(item, dict):
            value = str(item.get("modid") or item.get("modId") or "").strip()
            if value:
                ids.append(value)
    return {
        "id": mod_id,
        "ids": unique(ids),
        "name": str(primary.get("name") or mod_id),
        "version": str(primary.get("version") or ""),
        "authors": unique(_as_list(primary.get("authorList") or primary.get("author"))),
        "description": _clean_description(primary.get("description")),
        "homepage": str(primary.get("url") or ""),
        "environment": "",
        "icon_entry": _normalize_icon_path(primary.get("logoFile")),
        "format": "legacy",
        "license": "",
    }


def _manifest_metadata(text: str) -> Dict:
    fields: Dict[str, str] = {}
    current = None
    for line in text.splitlines():
        if line.startswith(" ") and current:
            fields[current] += line.strip()
            continue
        if ":" in line:
            key, value = line.split(":", 1)
            current = key.strip()
            fields[current] = value.strip()
    title = fields.get("Implementation-Title") or fields.get("Specification-Title") or ""
    version = fields.get("Implementation-Version") or fields.get("Specification-Version") or ""
    return {"name": title, "version": version, "authors": [], "description": "", "homepage": ""}


def filename_hint(filename: str) -> str:
    name = filename
    for suffix in (".jar.disabled", ".jar", ".disabled", ".zip"):
        if name.lower().endswith(suffix):
            name = name[: -len(suffix)]
            break
    name = re.sub(r"^[\[【(（][^\]】)）]{0,40}[\]】)）]\s*", "", name)
    name = re.sub(r"\.(fabric|forge|neoforge|quilt)$", "", name, flags=re.IGNORECASE)
    tokens = re.split(r"[-_+.\s]+", name)
    cleaned = []
    for token in tokens:
        low = token.lower()
        if re.fullmatch(r"v?\d[\w.]*", low):
            break
        if low in LOADER_WORDS and cleaned:
            continue
        cleaned.append(token)
    if not cleaned:
        cleaned = [name]
    return " ".join(cleaned[:6]).strip() or name


def jar_name_tokens(filename: str) -> List[str]:
    """Produce useful filename prefixes for config-to-mod matching."""
    name = filename
    for suffix in (".jar.disabled", ".jar", ".disabled", ".zip"):
        if name.lower().endswith(suffix):
            name = name[: -len(suffix)]
            break
    name = re.sub(r"^[\[【(（][^\]】)）]{0,48}[\]】)）]\s*", "", name)
    name = re.sub(r"\.(fabric|forge|neoforge|quilt)$", "", name, flags=re.IGNORECASE)
    parts = [part for part in re.split(r"[-_+.\s]+", name) if part]
    prefixes = []
    for index in range(1, min(len(parts), 7) + 1):
        chunk = parts[:index]
        if any(re.fullmatch(r"v?\d[\w.]*", item, flags=re.IGNORECASE) for item in chunk):
            break
        words = [item for item in chunk if item.lower() not in LOADER_WORDS]
        if words:
            prefixes.append(normalize_token("".join(words)))
    return unique([item for item in prefixes if len(item) >= 3])


def read_jar_metadata(jar_path: Path, rel_name: str) -> Dict:
    filename = Path(rel_name).name
    meta: Dict = {
        "id": "",
        "ids": [],
        "name": "",
        "version": "",
        "authors": [],
        "description": "",
        "homepage": "",
        "environment": "",
        "icon_entry": None,
        "format": "unknown",
        "license": "",
        "error": "",
    }
    try:
        with zipfile.ZipFile(str(jar_path), "r") as archive:
            names = set(archive.namelist())
            if "fabric.mod.json" in names:
                parsed = _fabric_metadata(_read_entry(archive, "fabric.mod.json") or "", "fabric")
                if parsed:
                    meta.update(parsed)
            if not meta["id"] and "quilt.mod.json" in names:
                parsed = _quilt_metadata(_read_entry(archive, "quilt.mod.json") or "")
                if parsed:
                    meta.update(parsed)
            if not meta["id"]:
                for entry in ("META-INF/neoforge.mods.toml", "META-INF/mods.toml"):
                    if entry in names:
                        fmt = "neoforge" if "neoforge" in entry else "forge"
                        parsed = _forge_metadata(_read_entry(archive, entry) or "", fmt)
                        if parsed:
                            meta.update(parsed)
                            break
            if not meta["id"] and "mcmod.info" in names:
                parsed = _mcmod_metadata(_read_entry(archive, "mcmod.info") or "")
                if parsed:
                    meta.update(parsed)
            if not meta["name"] or not meta["version"]:
                manifest = _manifest_metadata(_read_entry(archive, "META-INF/MANIFEST.MF") or "")
                if not meta["name"]:
                    meta["name"] = manifest["name"]
                if not meta["version"]:
                    meta["version"] = manifest["version"]
    except (OSError, zipfile.BadZipFile, RuntimeError) as exc:
        meta["error"] = "无法读取 JAR：%s" % exc

    if not meta["id"]:
        meta["id"] = normalize_token(filename_hint(filename)) or normalize_token(filename) or "unknown"
        meta["format"] = "unknown"
    if not meta["ids"]:
        meta["ids"] = [meta["id"]]
    if not meta["name"]:
        meta["name"] = filename_hint(filename)
    meta["name"] = str(meta["name"]).strip() or meta["id"]
    meta["description"] = _clean_description(meta.get("description"))
    meta["authors"] = unique(_as_list(meta.get("authors")))
    meta["filename"] = filename
    meta["enabled"] = not filename.lower().endswith((".disabled", ".disabled.jar"))
    return meta


def icon_bytes_from_jar(jar_path: Path, icon_entry: Optional[str]) -> Tuple[Optional[bytes], str]:
    if not icon_entry:
        return None, ""
    normalized = icon_entry.lstrip("/")
    try:
        with zipfile.ZipFile(str(jar_path), "r") as archive:
            try:
                info = archive.getinfo(normalized)
            except KeyError:
                candidates = [name for name in archive.namelist() if name.lower().endswith(Path(normalized).name.lower())]
                if not candidates:
                    return None, ""
                info = archive.getinfo(candidates[0])
            if info.file_size > 3 * 1024 * 1024:
                return None, ""
            data = archive.read(info)
    except (OSError, zipfile.BadZipFile, RuntimeError):
        return None, ""
    suffix = Path(normalized).suffix.lower()
    if suffix == ".svg":
        return data, "image/svg+xml"
    return data, ""


def describe_meta(meta: Dict) -> str:
    return first_line(meta.get("description") or "", 300)
