from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import time
import urllib.request
import uuid as uuid_lib
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from minecraft_launcher_lib import command as mc_command
from minecraft_launcher_lib import natives as mc_natives

from .settings import CACHE_DIR, current_launcher
from .util import atomic_write

CREATE_NO_WINDOW = 0x08000000
DEFAULT_MEMORY_MB = 4096


def _recommended_memory() -> int:
    try:
        import ctypes
        from ctypes import wintypes

        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [
                ("dwLength", wintypes.DWORD),
                ("dwMemoryLoad", wintypes.DWORD),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        status = MEMORYSTATUSEX()
        status.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            total_mb = int(status.ullTotalPhys / 1024 / 1024)
            return max(4096, min(8192, int(total_mb * 0.45)))
    except Exception:
        pass
    return DEFAULT_MEMORY_MB



class LaunchError(Exception):
    def __init__(self, message: str, code: str = "launch_error"):
        super().__init__(message)
        self.message = message
        self.code = code


# ---------------------------------------------------------------------------
# Account


def _offline_uuid(username: str) -> str:
    digest = hashlib.md5(("OfflinePlayer:" + username).encode("utf-8")).hexdigest()
    return "%s-%s-%s-%s-%s" % (digest[:8], digest[8:12], digest[12:16], digest[16:20], digest[20:])


def _account_from_ms_store(root: Path) -> Optional[Dict]:
    path = root / "launcher_accounts_microsoft_store.json"
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    active_id = str(data.get("activeAccountLocalId") or "")
    accounts = data.get("accounts") or {}
    account = accounts.get(active_id) if isinstance(accounts, dict) else None
    if not isinstance(account, dict):
        return None
    profile = account.get("minecraftProfile") or {}
    username = str(profile.get("name") or account.get("username") or "").strip()
    if not username:
        return None
    profile_id = str(profile.get("id") or "").replace("-", "")
    token = str(account.get("accessToken") or "").strip()
    expires = str(account.get("accessTokenExpiresAt") or "").strip()
    valid = False
    if token and expires:
        try:
            from datetime import datetime, timezone

            expiry = datetime.fromisoformat(expires.replace("Z", "+00:00"))
            valid = expiry > datetime.now(timezone.utc)
        except Exception:
            valid = False
    return {
        "username": username,
        "uuid": profile_id or _offline_uuid(username),
        "token": token if valid else "0",
        "offline": not valid,
    }


def _account_from_profiles(root: Path) -> Optional[Dict]:
    path = root / "launcher_profiles.json"
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    auth = data.get("authenticationDatabase") or {}
    if not isinstance(auth, dict):
        return None
    for entry in auth.values():
        if not isinstance(entry, dict):
            continue
        profiles = entry.get("profiles") or {}
        if not isinstance(profiles, dict) or not profiles:
            continue
        profile_id, profile = next(iter(profiles.items()))
        username = str((profile or {}).get("displayName") or entry.get("username") or "").strip()
        if not username:
            continue
        token = str(entry.get("accessToken") or "").strip()
        return {
            "username": username,
            "uuid": str(profile_id).replace("-", "") or _offline_uuid(username),
            "token": token or "0",
            "offline": not bool(token),
        }
    return None


def detect_account(root: Path) -> Dict:
    account = _account_from_ms_store(root) or _account_from_profiles(root)
    if account:
        return account
    return {"username": "Player", "uuid": _offline_uuid("Player"), "token": "0", "offline": True}


# ---------------------------------------------------------------------------
# Java / client jar / Fabric profile


def _version_json(root: Path, version_id: str) -> Tuple[Path, Path, Dict]:
    version_dir = root / "versions" / version_id
    json_path = version_dir / (version_id + ".json")
    if not json_path.is_file():
        raise LaunchError("该版本缺少版本清单（%s），无法直接启动" % json_path.name, "missing_json")
    try:
        data = json.loads(json_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise LaunchError("版本清单无法读取：%s" % exc, "bad_json")
    return version_dir, json_path, data


def _java_from_runtime(root: Path, major: int) -> Optional[Path]:
    candidates = []
    if major >= 21:
        candidates += [
            root / "runtime" / "java-runtime-delta" / "bin" / "javaw.exe",
            Path("C:/Program Files/Java/jdk-21/bin/javaw.exe"),
            Path("C:/Program Files/Java/jdk-21/bin/java.exe"),
        ]
    if major >= 25:
        candidates += [
            root / "runtime" / "java-runtime-epsilon" / "bin" / "javaw.exe",
        ]
    candidates += [
        root / "runtime" / "java-runtime-gamma" / "bin" / "javaw.exe",
        root / "runtime" / "java-runtime-gamma-snapshot" / "bin" / "javaw.exe",
        root / "runtime" / "jre-legacy" / "bin" / "javaw.exe",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    java_home = os.environ.get("JAVA_HOME")
    if java_home:
        for name in ("javaw.exe", "java.exe"):
            candidate = Path(java_home) / "bin" / name
            if candidate.is_file():
                return candidate
    return None


def _java_executable(root: Path, data: Dict) -> Path:
    java_info = data.get("javaVersion") or {}
    major = 17
    try:
        major = int(java_info.get("majorVersion") or 17)
    except (TypeError, ValueError):
        major = 17
    candidate = _java_from_runtime(root, major)
    if candidate:
        return candidate
    # Last resort: javaw from PATH.
    import shutil

    found = shutil.which("javaw") or shutil.which("java")
    if found:
        return Path(found)
    raise LaunchError("没有找到 Java %d 运行环境，无法启动游戏" % major, "missing_java")


def _sha1_file(path: Path) -> str:
    digest = hashlib.sha1()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _client_jar(root: Path, version_id: str, version_dir: Path, data: Dict) -> Optional[Path]:
    existing = version_dir / (version_id + ".jar")
    if existing.is_file():
        return existing
    client = (data.get("downloads") or {}).get("client") or {}
    url = str(client.get("url") or "")
    expected = str(client.get("sha1") or "")
    if not url:
        return None
    cache = CACHE_DIR / "clients"
    cache.mkdir(parents=True, exist_ok=True)
    target = cache / ((expected or hashlib.sha1(url.encode()).hexdigest()) + ".jar")
    if target.is_file():
        if not expected or _sha1_file(target) == expected:
            return target
        try:
            target.unlink()
        except OSError:
            pass
    temp = target.with_suffix(".part")
    try:
        try:
            import requests

            response = requests.get(url, stream=True, timeout=45, headers={"User-Agent": "CraftTune/1.0"})
            response.raise_for_status()
            with temp.open("wb") as handle:
                for chunk in response.iter_content(1024 * 1024):
                    if chunk:
                        handle.write(chunk)
        except ImportError:
            request = urllib.request.Request(url, headers={"User-Agent": "CraftTune/1.0"})
            with urllib.request.urlopen(request, timeout=45) as response, temp.open("wb") as handle:
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    handle.write(chunk)
    except Exception as exc:
        try:
            temp.unlink()
        except OSError:
            pass
        raise LaunchError("该版本缺少客户端 JAR，自动下载失败：%s" % exc, "client_download_failed")
    if expected and _sha1_file(temp) != expected:
        temp.unlink(missing_ok=True)
        raise LaunchError("客户端 JAR 校验失败，请检查网络或游戏完整性", "client_hash_mismatch")
    os.replace(temp, target)
    return target


def _find_library(root: Path, group: str, artifact: str, version: str, classifier: str = "") -> Optional[Path]:
    base = root / "libraries" / Path(*group.split(".")) / artifact / version
    name = "%s-%s" % (artifact, version)
    if classifier:
        name += "-" + classifier
    path = base / (name + ".jar")
    return path if path.is_file() else None


def _find_latest_library(root: Path, group: str, artifact: str, pattern: str = "*") -> Optional[Path]:
    base = root / "libraries" / Path(*group.split(".")) / artifact
    if not base.is_dir():
        return None
    candidates = sorted(base.glob(pattern + "/*.jar"), key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0] if candidates else None


def _fabric_libraries(root: Path, version_id: str, game_version: str) -> List[Path]:
    lower = version_id.lower()
    match = re.search(r"fabric[_-]?(\d+\.\d+\.\d+)", lower)
    loader_version = match.group(1) if match else ""
    loader = None
    if loader_version:
        loader = _find_library(root, "net.fabricmc", "fabric-loader", loader_version)
    if loader is None:
        loader = _find_latest_library(root, "net.fabricmc", "fabric-loader")
    intermediary = _find_library(root, "net.fabricmc", "intermediary", game_version)
    mixin = _find_latest_library(root, "net.fabricmc", "sponge-mixin")
    libs: List[Path] = []
    for item in (loader, intermediary, mixin):
        if item:
            libs.append(item)
    for name in ("asm", "asm-analysis", "asm-commons", "asm-tree", "asm-util"):
        jar = _find_latest_library(root, "org.ow2.asm", name, "9.*")
        if jar:
            libs.append(jar)
    return libs


def _patch_classpath(cmd: List[str], root: Path, version_id: str, version_dir: Path, data: Dict) -> Tuple[List[str], List[str]]:
    warnings: List[str] = []
    try:
        index = cmd.index("-cp")
    except ValueError:
        return cmd, warnings
    if index + 1 >= len(cmd):
        return cmd, warnings
    entries = [entry for entry in cmd[index + 1].split(os.pathsep) if entry]
    kept = []
    missing = []
    for entry in entries:
        if Path(entry).is_file():
            kept.append(entry)
        else:
            missing.append(entry)
    client = _client_jar(root, version_id, version_dir, data)
    if client and str(client) not in kept:
        kept.append(str(client))
    # A missing version jar is normal for old PCL-created Fabric profiles; the
    # official client jar above replaces it.
    cmd[index + 1] = os.pathsep.join(kept)
    return cmd, warnings


def _patch_fabric(cmd: List[str], root: Path, version_id: str, data: Dict) -> Tuple[List[str], List[str]]:
    warnings: List[str] = []
    libraries = data.get("libraries") or []
    names = " ".join(str(item.get("name") or "") for item in libraries if isinstance(item, dict))
    if "fabric-loader" in names:
        return cmd, warnings
    if "fabric" not in version_id.lower():
        return cmd, warnings
    game_version = str(data.get("inheritsFrom") or data.get("id") or "1.20.1")
    libs = _fabric_libraries(root, version_id, game_version)
    if not libs:
        raise LaunchError("该 Fabric 版本缺少加载器库，无法直接启动", "missing_fabric")
    try:
        index = cmd.index("-cp")
        cmd[index + 1] = os.pathsep.join([cmd[index + 1]] + [str(path) for path in libs])
        main_index = index + 2
        if main_index < len(cmd) and cmd[main_index] == "net.minecraft.client.main.Main":
            cmd[main_index] = "net.fabricmc.loader.impl.launch.knot.KnotClient"
            cmd.insert(main_index, "-DFabricMcEmu=net.minecraft.client.main.Main")
        elif main_index < len(cmd):
            cmd[main_index] = "net.fabricmc.loader.impl.launch.knot.KnotClient"
            cmd.insert(main_index, "-DFabricMcEmu=net.minecraft.client.main.Main")
    except ValueError:
        raise LaunchError("无法生成 Fabric 启动命令", "fabric_patch_failed")
    warnings.append("已自动补全 Fabric 加载器")
    return cmd, warnings


def _write_launch_log(game_dir: Path, command: List[str], account: Dict) -> Path:
    logs = game_dir / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    path = logs / "crafttune-direct.log"
    safe = []
    redact_next = False
    for item in command:
        if redact_next:
            safe.append("********")
            redact_next = False
            continue
        safe.append(item)
        if item == "--accessToken":
            redact_next = True
    header = (
        "CraftTune direct launch\n"
        "account=%s offline=%s\n"
        "command=%s\n\n" % (account.get("username"), account.get("offline"), subprocess.list2cmdline(safe))
    )
    path.write_text(header, encoding="utf-8", errors="replace")
    return path


def launch(version_id: str, launcher_root: Optional[Path] = None) -> Dict:
    """Launch the selected Minecraft version directly with Java.

    The account is the locally stored Minecraft profile. If its token is
    expired, an offline session is used so single-player still starts.
    """
    root = Path(launcher_root) if launcher_root else current_launcher()
    if not root:
        raise LaunchError("没有找到 Minecraft 目录", "no_launcher")
    version_dir, json_path, data = _version_json(root, version_id)
    java = _java_executable(root, data)
    account = detect_account(root)
    game_dir = version_dir
    natives_dir = version_dir / "natives"
    natives_dir.mkdir(parents=True, exist_ok=True)
    try:
        mc_natives.extract_natives(version_id, str(root), str(natives_dir))
    except Exception as exc:
        raise LaunchError("无法解压游戏运行库：%s" % exc, "natives_failed")
    options = {
        "username": account["username"],
        "uuid": account["uuid"],
        "token": account["token"],
        "executablePath": str(java),
        "jvmArguments": [
            "-Xms1024m",
            "-Xmx%dm" % _recommended_memory(),
            "-XX:+UseG1GC",
            "-Dfile.encoding=UTF-8",
            "-Dstdout.encoding=UTF-8",
            "-Dstderr.encoding=UTF-8",
        ],
        "launcherName": "CraftTune",
        "launcherVersion": "1.0",
        "gameDirectory": str(game_dir),
        "nativesDirectory": str(natives_dir),
    }
    try:
        cmd = mc_command.get_minecraft_command(version_id, str(root), options)
    except Exception as exc:
        raise LaunchError("无法生成启动命令：%s" % exc, "command_failed")
    cmd = ["" if item in ("${clientid}", "${auth_xuid}") else item for item in cmd]
    cmd, warnings = _patch_classpath(cmd, root, version_id, version_dir, data)
    cmd, fabric_warnings = _patch_fabric(cmd, root, version_id, data)
    warnings.extend(fabric_warnings)
    # Offline sessions should not claim to be MSA sessions.
    if account.get("offline"):
        for index, item in enumerate(cmd):
            if item == "--userType" and index + 1 < len(cmd):
                cmd[index + 1] = "legacy"
                break
    # Use the selected version name in logs and mod metadata.
    for index, item in enumerate(cmd):
        if item == "--version" and index + 1 < len(cmd):
            cmd[index + 1] = version_id
            break
    try:
        cmd.index("-cp")
    except ValueError:
        raise LaunchError("启动命令缺少 classpath", "command_failed")
    log_path = _write_launch_log(game_dir, cmd, account)
    handle = log_path.open("a", encoding="utf-8", errors="replace")
    try:
        process = subprocess.Popen(
            cmd,
            cwd=str(game_dir),
            stdout=handle,
            stderr=subprocess.STDOUT,
            creationflags=CREATE_NO_WINDOW,
        )
    except OSError as exc:
        handle.close()
        raise LaunchError("无法启动 Java 进程：%s" % exc, "spawn_failed")
    time.sleep(2.2)
    if process.poll() is not None:
        handle.close()
        try:
            tail = log_path.read_text(encoding="utf-8", errors="replace")[-3200:]
        except OSError:
            tail = ""
        raise LaunchError("游戏进程启动后立即退出。\n\n" + tail, "early_exit")
    return {
        "pid": process.pid,
        "version": version_id,
        "account": account["username"],
        "offline": account["offline"],
        "java": str(java),
        "log": str(log_path),
        "warnings": warnings,
    }
