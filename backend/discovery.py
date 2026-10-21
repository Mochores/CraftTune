from __future__ import annotations

import json
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from .modmeta import jar_name_tokens, read_jar_metadata
from .util import human_size, normalize_token, sha1_text, unique

CONFIG_SUFFIXES = {
    ".toml",
    ".json",
    ".json5",
    ".jsonc",
    ".hjson",
    ".properties",
    ".cfg",
    ".conf",
    ".ini",
    ".yaml",
    ".yml",
    ".txt",
    ".snbt",
    ".xml",
}
IGNORED_DIRS = {".git", ".svn", "backups", "backup", "cache", "logs", "log", "__pycache__"}
JAR_SUFFIXES = (".jar", ".jar.disabled")
LOADER_WORDS = {
    "fabric",
    "forge",
    "neoforge",
    "quilt",
    "common",
    "client",
    "server",
    "universal",
    "all",
    "mc",
    "minecraft",
}
GENERIC_IDS = {"api", "lib", "library", "core", "config", "mod", "common", "util", "utils"}


def file_format(rel_path: str) -> str:
    suffix = Path(rel_path).suffix.lower()
    return {
        ".toml": "toml",
        ".json": "json",
        ".json5": "json5",
        ".jsonc": "json",
        ".hjson": "json5",
        ".properties": "properties",
        ".cfg": "cfg",
        ".conf": "properties",
        ".ini": "properties",
        ".yaml": "yaml",
        ".yml": "yaml",
        ".txt": "text",
        ".snbt": "text",
        ".xml": "text",
    }.get(suffix, "text")


def format_label(fmt: str) -> str:
    return {
        "toml": "TOML",
        "json": "JSON",
        "json5": "JSON5",
        "yaml": "YAML",
        "properties": "Properties",
        "cfg": "CFG",
        "text": "文本",
    }.get(fmt, fmt.upper())


def _read_json(path: Path) -> Dict:
    try:
        with path.open("r", encoding="utf-8-sig") as handle:
            data = json.load(handle)
            return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _game_version_from(text: str) -> str:
    match = re.search(r"(?<!\d)(1\.\d{1,2}(?:\.\d{1,2})?)(?!\d)", text or "")
    return match.group(1) if match else ""


def _loader_from_libraries(libraries: Iterable[Any]) -> Tuple[List[str], Dict[str, str]]:
    loaders: List[str] = []
    versions: Dict[str, str] = {}
    for library in libraries:
        if isinstance(library, dict):
            name = str(library.get("name") or "")
        else:
            name = str(library)
        low = name.lower()
        if low.startswith("net.fabricmc:fabric-loader:"):
            loaders.append("Fabric")
            versions["Fabric"] = name.split(":")[-1]
        elif low.startswith("org.quiltmc:quilt-loader:"):
            loaders.append("Quilt")
            versions["Quilt"] = name.split(":")[-1]
        elif low.startswith("net.neoforged:neoforge:"):
            loaders.append("NeoForge")
            versions["NeoForge"] = name.split(":")[-1]
        elif low.startswith("net.minecraftforge:forge:"):
            loaders.append("Forge")
            versions["Forge"] = name.split(":")[-1]
        elif low.startswith("net.minecraftforge:fmlloader:"):
            loaders.append("Forge")
            versions["Forge"] = name.split(":")[-1].split("-")[-1]
        elif low.startswith("net.neoforged:fmlloader:"):
            loaders.append("NeoForge")
            versions["NeoForge"] = name.split(":")[-1].split("-")[-1]
        elif low.startswith("optifine:optifine:"):
            loaders.append("OptiFine")
            versions["OptiFine"] = name.split(":")[-1]
    return unique(loaders), versions


def _infer_from_mods(version_dir: Path) -> Tuple[List[str], str]:
    """Best-effort loader/game version inference for packs without a version JSON."""
    names: List[str] = []
    for candidate in (version_dir / "mods", version_dir / ".minecraft" / "mods"):
        if not candidate.is_dir():
            continue
        try:
            names.extend(name for name in os.listdir(str(candidate)) if name.lower().endswith(".jar"))
        except OSError:
            pass
    if not names:
        return [], ""
    lower = [name.lower() for name in names]
    loaders: List[str] = []
    if sum("neoforge" in name for name in lower) > 0:
        loaders.append("NeoForge")
    if sum("fabric" in name for name in lower) >= max(1, sum("forge" in name for name in lower)):
        if "Fabric" not in loaders:
            loaders.insert(0, "Fabric")
    elif any("forge" in name for name in lower):
        loaders.append("Forge")
    if any("quilt" in name for name in lower) and "Quilt" not in loaders:
        loaders.append("Quilt")
    counts: Dict[str, int] = {}
    for name in names:
        for match in re.findall(r"(?<!\d)(1\.\d{1,2}(?:\.\d{1,2})?)(?!\d)", name):
            counts[match] = counts.get(match, 0) + 1
    game_version = ""
    if counts:
        game_version = sorted(counts.items(), key=lambda item: (-item[1], len(item[0]), item[0]))[0][0]
    return loaders, game_version


def _version_meta(version_dir: Path, version_id: str, root: Path) -> Dict:
    json_path = version_dir / ("%s.json" % version_id)
    data = _read_json(json_path) if json_path.is_file() else {}
    libraries = data.get("libraries") or []
    loaders, loader_versions = _loader_from_libraries(libraries)
    inherits = str(data.get("inheritsFrom") or "")
    game_version = _game_version_from(inherits) or _game_version_from(str(data.get("id") or "")) or _game_version_from(version_id)
    if not game_version:
        game_version = _game_version_from(" ".join(loader_versions.values()))
    if not loaders or not game_version:
        inferred_loaders, inferred_game = _infer_from_mods(version_dir)
        if not loaders and inferred_loaders:
            loaders = inferred_loaders
        if not game_version and inferred_game:
            game_version = inferred_game
    if not game_version:
        game_version = _game_version_from(" ".join(loader_versions.values()))
    if not loaders:
        lower_name = version_id.lower()
        for needle, label in (
            ("neoforge", "NeoForge"),
            ("fabric", "Fabric"),
            ("quilt", "Quilt"),
            ("forge", "Forge"),
            ("optifine", "OptiFine"),
        ):
            if needle in lower_name:
                loaders.append(label)
    icon = None
    for name in ("icon.png", "icon.jpg", "icon.jpeg", "icon.webp", "PCL/Logo.png"):
        candidate = version_dir / name
        if candidate.is_file():
            icon = candidate
            break
    if icon is None:
        root_icon = root / "icon.png"
        if root_icon.is_file():
            icon = root_icon
    return {
        "game_version": game_version or "未知",
        "loader": " + ".join(loaders) if loaders else ("模组加载器" if (version_dir / "mods").is_dir() else "原版"),
        "loaders": loaders,
        "loader_version": loader_versions.get(loaders[0], "") if loaders else "",
        "loader_versions": loader_versions,
        "has_json": json_path.is_file(),
        "json_path": json_path,
        "inherits_from": inherits,
        "icon_path": icon,
        "last_used": data.get("lastUsed") or "",
    }


def _count_configs(config_dir: Optional[Path]) -> int:
    if not config_dir or not config_dir.is_dir():
        return 0
    count = 0
    for current, dirs, files in os.walk(str(config_dir)):
        dirs[:] = [name for name in dirs if name.lower() not in IGNORED_DIRS and not name.startswith(".")]
        for name in files:
            if Path(name).suffix.lower() in CONFIG_SUFFIXES and not name.lower().endswith((".bak", ".old")):
                count += 1
    return count


def _version_counts(version_dir: Path) -> Tuple[int, int, int]:
    mods_dir_candidates = [version_dir / "mods"]
    nested_mc = version_dir / ".minecraft"
    if nested_mc.is_dir():
        mods_dir_candidates.append(nested_mc / "mods")
    enabled = 0
    disabled = 0
    for mods_dir in mods_dir_candidates:
        if not mods_dir.is_dir():
            continue
        for name in os.listdir(str(mods_dir)):
            low = name.lower()
            if low.endswith(".jar"):
                enabled += 1
            elif low.endswith(".jar.disabled"):
                disabled += 1
    config_count = 0
    for candidate in (version_dir / "config", nested_mc / "config"):
        if candidate.is_dir():
            config_count += _count_configs(candidate)
    return enabled, disabled, config_count


class MinecraftLibrary:
    def __init__(self, root: Path):
        self.root = Path(root).resolve()
        self.versions_dir = self.root / "versions"
        self._jar_cache: Dict[str, Dict] = {}

    def list_versions(self) -> List[Dict]:
        versions: List[Dict] = []
        if not self.versions_dir.is_dir():
            return versions
        for entry in sorted(self.versions_dir.iterdir(), key=lambda item: item.name.lower()):
            if not entry.is_dir() or entry.name.startswith("."):
                continue
            nested_mc = entry / ".minecraft"
            has_data = (entry / "mods").is_dir() or (entry / "config").is_dir() or (entry / ("%s.json" % entry.name)).is_file()
            if not has_data and nested_mc.is_dir():
                has_data = (nested_mc / "mods").is_dir() or (nested_mc / "config").is_dir()
            if not has_data:
                continue
            enabled, disabled, config_count = _version_counts(entry)
            meta = _version_meta(entry, entry.name, self.root)
            try:
                mtime = entry.stat().st_mtime
            except OSError:
                mtime = 0
            versions.append(
                {
                    "id": entry.name,
                    "name": entry.name,
                    "dir": str(entry),
                    "game_version": meta["game_version"],
                    "loader": meta["loader"],
                    "loaders": meta["loaders"],
                    "loader_version": meta["loader_version"],
                    "has_json": meta["has_json"],
                    "icon": bool(meta["icon_path"]),
                    "icon_path": str(meta["icon_path"]) if meta["icon_path"] else "",
                    "mod_count": enabled + disabled,
                    "enabled_mod_count": enabled,
                    "disabled_mod_count": disabled,
                    "config_count": config_count,
                    "mtime": mtime,
                    "isolated": (entry / "mods").is_dir() or (entry / "config").is_dir(),
                }
            )
        versions.sort(key=lambda item: (-(item.get("mtime") or 0), item["name"].lower()))
        return versions

    def find_version(self, version_id: str) -> Optional[Dict]:
        for version in self.list_versions():
            if version["id"] == version_id:
                return version
        return None

    def version_paths(self, version: Dict) -> Tuple[Optional[Path], Optional[Path]]:
        base = Path(version["dir"])
        nested = base / ".minecraft"
        if (base / "mods").is_dir() or (base / "config").is_dir() or not nested.is_dir():
            mods_dir = base / "mods" if (base / "mods").is_dir() else None
            config_dir = base / "config" if (base / "config").is_dir() else None
            return mods_dir, config_dir
        mods_dir = nested / "mods" if (nested / "mods").is_dir() else None
        config_dir = nested / "config" if (nested / "config").is_dir() else None
        return mods_dir, config_dir

    def scan_configs(self, config_dir: Optional[Path]) -> List[Dict]:
        if not config_dir or not config_dir.is_dir():
            return []
        results: List[Dict] = []
        root = config_dir.resolve()
        for current, dirs, files in os.walk(str(root)):
            dirs[:] = sorted(
                [name for name in dirs if name.lower() not in IGNORED_DIRS and not name.startswith(".")],
                key=str.lower,
            )
            for name in sorted(files, key=str.lower):
                suffix = Path(name).suffix.lower()
                if suffix not in CONFIG_SUFFIXES or name.lower().endswith((".bak", ".old")):
                    continue
                full = Path(current) / name
                try:
                    stat = full.stat()
                except OSError:
                    continue
                rel = full.relative_to(root).as_posix()
                parts = rel.split("/")
                stem = Path(name).stem
                results.append(
                    {
                        "path": rel,
                        "name": name,
                        "stem": stem,
                        "ext": suffix.lstrip("."),
                        "format": file_format(rel),
                        "format_label": format_label(file_format(rel)),
                        "size": stat.st_size,
                        "size_label": human_size(stat.st_size),
                        "mtime": stat.st_mtime,
                        "top": parts[0] if len(parts) > 1 else stem,
                        "depth": len(parts),
                    }
                )
        results.sort(key=lambda item: item["path"].lower())
        return results

    def scan_mods(self, mods_dir: Optional[Path]) -> List[Dict]:
        if not mods_dir or not mods_dir.is_dir():
            return []
        jars: List[Tuple[Path, str]] = []
        for current, dirs, files in os.walk(str(mods_dir)):
            dirs[:] = [name for name in dirs if not name.startswith(".")]
            for name in files:
                low = name.lower()
                if low.endswith(JAR_SUFFIXES):
                    full = Path(current) / name
                    rel = full.relative_to(mods_dir).as_posix()
                    jars.append((full, rel))
        jars.sort(key=lambda item: item[1].lower())
        metas: List[Dict] = []
        with ThreadPoolExecutor(max_workers=8) as executor:
            future_map = {}
            for full, rel in jars:
                cache_key = "%s|%s|%s" % (str(full), full.stat().st_size if full.exists() else 0, full.stat().st_mtime if full.exists() else 0)
                cached = self._jar_cache.get(cache_key)
                if cached is not None:
                    metas.append(dict(cached))
                else:
                    future = executor.submit(read_jar_metadata, full, rel)
                    future_map[future] = (full, rel, cache_key)
            for future in as_completed(future_map):
                full, rel, cache_key = future_map[future]
                try:
                    meta = future.result()
                except Exception as exc:  # pragma: no cover - defensive
                    meta = {
                        "id": normalize_token(Path(rel).stem) or "unknown",
                        "ids": [],
                        "name": Path(rel).stem,
                        "version": "",
                        "authors": [],
                        "description": "",
                        "format": "unknown",
                        "icon_entry": None,
                        "error": str(exc),
                        "filename": Path(rel).name,
                        "enabled": not rel.lower().endswith(".disabled"),
                    }
                meta["rel_path"] = rel
                meta["jar_path"] = str(full)
                meta["key"] = "m" + sha1_text(rel)[:12]
                meta["size"] = full.stat().st_size if full.exists() else 0
                meta["size_label"] = human_size(meta["size"])
                meta["config_files"] = []
                self._jar_cache[cache_key] = dict(meta)
                metas.append(meta)
        metas.sort(key=lambda item: (not item.get("enabled", True), str(item.get("name", "")).lower()))
        return metas

    def version_icon_path(self, version_id: str) -> Optional[Path]:
        version = self.find_version(version_id)
        if not version:
            return None
        path = version.get("icon_path")
        return Path(path) if path and Path(path).is_file() else None


def _config_candidates(file_info: Dict) -> List[Tuple[str, int]]:
    """Return normalized candidate tokens with descending specificity."""
    candidates: List[Tuple[str, int]] = []
    stem = file_info["stem"]
    raw_tokens = [token for token in re.split(r"[-_\s.]+", stem) if token]
    normal_tokens: List[str] = []
    for token in raw_tokens:
        if re.fullmatch(r"v?\d[\w.]*", token, flags=re.IGNORECASE):
            break
        if token.lower() in LOADER_WORDS:
            continue
        normal_tokens.append(token)
    if normal_tokens:
        full = normalize_token("".join(normal_tokens))
        if full:
            candidates.append((full, 104))
        # Strip common config role suffixes.
        if normal_tokens and normal_tokens[-1].lower() in {"client", "common", "server", "config", "settings", "options"}:
            stripped = normalize_token("".join(normal_tokens[:-1]))
            if stripped:
                candidates.append((stripped, 100))
        for size in range(len(normal_tokens) - 1, 0, -1):
            token = normalize_token("".join(normal_tokens[:size]))
            if token:
                candidates.append((token, 80 + min(len(token), 19)))
    # A config inside config/<modid>/... belongs to that folder in almost all packs.
    if int(file_info.get("depth") or 1) > 1:
        top = normalize_token(str(file_info.get("top") or ""))
        if top:
            candidates.append((top, 110))
    # De-duplicate while keeping the highest score for each token.
    best: Dict[str, int] = {}
    for token, score in candidates:
        if len(token) < 3:
            continue
        if token not in best or score > best[token]:
            best[token] = score
    return sorted(best.items(), key=lambda item: -item[1])


def associate_configs(mods: List[Dict], configs: List[Dict]) -> Tuple[List[Dict], List[Dict]]:
    index: Dict[str, List[Dict]] = {}
    for mod in mods:
        aliases: List[str] = []
        aliases.extend(mod.get("ids") or [])
        aliases.append(mod.get("id") or "")
        aliases.extend(jar_name_tokens(str(mod.get("rel_path") or mod.get("filename") or "")))
        name = str(mod.get("name") or "")
        if name and re.match(r"^[\x00-\x7f]+$", name):
            aliases.append(name)
        for alias in aliases:
            token = normalize_token(str(alias))
            if len(token) < 3:
                continue
            bucket = index.setdefault(token, [])
            if mod not in bucket:
                bucket.append(mod)

    orphans: List[Dict] = []
    for config in configs:
        matches: List[Tuple[int, Dict, str]] = []
        for token, base_score in _config_candidates(config):
            for mod in index.get(token, []):
                score = base_score
                mod_id_token = normalize_token(str(mod.get("id") or ""))
                if token == mod_id_token:
                    score += 4
                if mod_id_token in GENERIC_IDS:
                    score -= 18
                if not mod.get("enabled", True):
                    score -= 3
                matches.append((score, mod, token))
        if not matches:
            orphans.append(config)
            continue
        matches.sort(key=lambda item: (-item[0], -len(item[2]), str(item[1].get("name", ""))))
        best_score, best_mod, _ = matches[0]
        tied = [item for item in matches if item[0] == best_score and item[1].get("key") != best_mod.get("key")]
        if tied:
            # Never guess when two different mods are equally plausible.
            orphans.append(config)
            continue
        if best_score < 82:
            orphans.append(config)
            continue
        config["mod_key"] = best_mod["key"]
        best_mod.setdefault("config_files", []).append(config)
    for mod in mods:
        files = sorted(mod.get("config_files", []), key=lambda item: item["path"].lower())
        mod["config_files"] = files
        mod["config_count"] = len(files)
    return mods, orphans


def build_details(library: MinecraftLibrary, version: Dict) -> Dict:
    mods_dir, config_dir = library.version_paths(version)
    mods = library.scan_mods(mods_dir)
    configs = library.scan_configs(config_dir)
    mods, orphans = associate_configs(mods, configs)
    total_assigned = sum(1 for config in configs if config.get("mod_key"))
    other = None
    if orphans:
        other = {
            "key": "__other__",
            "name": "未归属配置文件",
            "id": "unlinked",
            "version": "",
            "authors": [],
            "description": "这些配置文件无法根据模组 ID 或文件名自动匹配到具体模组，仍可安全编辑。",
            "format": "collection",
            "icon_entry": None,
            "enabled": True,
            "config_count": len(orphans),
            "config_files": sorted(orphans, key=lambda item: item["path"].lower()),
            "is_virtual": True,
        }
    mods_for_public = []
    for mod in mods:
        public = {key: value for key, value in mod.items() if key not in ("config_files", "jar_path", "rel_path")}
        public["config_count"] = mod.get("config_count", 0)
        mods_for_public.append(public)
    if other:
        mods_for_public.append(other)
    stats = {
        "mods": len(mods),
        "enabled_mods": sum(1 for mod in mods if mod.get("enabled", True)),
        "disabled_mods": sum(1 for mod in mods if not mod.get("enabled", True)),
        "configs": len(configs),
        "assigned_configs": total_assigned,
        "orphan_configs": len(orphans),
        "formats": len({config["format"] for config in configs}),
    }
    return {
        "version": version,
        "mods": mods_for_public,
        "mods_by_key": {mod["key"]: mod for mod in mods},
        "other": other,
        "configs": configs,
        "config_dir": str(config_dir) if config_dir else "",
        "mods_dir": str(mods_dir) if mods_dir else "",
        "stats": stats,
    }
