from __future__ import annotations

import argparse
import os
import socket
import sys
import threading
import traceback
import webbrowser
from pathlib import Path
from typing import Any

from flask import Flask, Response, jsonify, request, send_from_directory
from werkzeug.exceptions import HTTPException

from backend.service import ApiError, ConfigService

APP_ROOT = Path(__file__).resolve().parent
if getattr(sys, "frozen", False):
    WEB_DIR = Path(getattr(sys, "_MEIPASS", APP_ROOT)) / "web"
else:
    WEB_DIR = APP_ROOT / "web"
SERVICE = ConfigService()


def create_app() -> Flask:
    app = Flask(__name__, static_folder=None)
    app.config["JSON_AS_ASCII"] = False
    app.config["MAX_CONTENT_LENGTH"] = 12 * 1024 * 1024

    @app.after_request
    def add_headers(response: Response) -> Response:
        if request.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        elif request.path.startswith("/assets/"):
            response.headers["Cache-Control"] = "no-cache, must-revalidate"
        elif request.path == "/":
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.errorhandler(ApiError)
    def handle_api_error(error: ApiError) -> Any:
        return jsonify({"ok": False, "error": error.message, "status": error.status}), error.status

    @app.errorhandler(404)
    def handle_404(error: Any) -> Any:
        if request.path.startswith(("/api/", "/assets/")):
            return jsonify({"ok": False, "error": "资源不存在", "status": 404}), 404
        return send_from_directory(str(WEB_DIR), "index.html")

    @app.get("/favicon.ico")
    def favicon() -> Any:
        return send_from_directory(str(WEB_DIR / "assets"), "favicon.svg", mimetype="image/svg+xml")

    @app.errorhandler(HTTPException)
    def handle_http_error(error: HTTPException) -> Any:
        if request.path.startswith("/api/"):
            return jsonify({"ok": False, "error": error.description, "status": error.code}), error.code
        return error

    @app.errorhandler(Exception)
    def handle_unexpected(error: Exception) -> Any:
        traceback.print_exc()
        return jsonify({"ok": False, "error": "服务器内部错误：%s" % error, "status": 500}), 500

    @app.get("/")
    def index() -> Any:
        return send_from_directory(str(WEB_DIR), "index.html")

    @app.get("/assets/<path:filename>")
    def assets(filename: str) -> Any:
        return send_from_directory(str(WEB_DIR / "assets"), filename)

    @app.get("/api/health")
    def health() -> Any:
        return jsonify({"ok": True, "app": "CraftTune"})

    @app.get("/api/status")
    def status() -> Any:
        return jsonify({"ok": True, **SERVICE.status()})

    @app.get("/api/versions")
    def versions() -> Any:
        return jsonify({"ok": True, "versions": SERVICE.list_versions(), **{k: v for k, v in SERVICE.status().items() if k in ("launcher", "detected")}})

    @app.post("/api/launcher")
    def launcher() -> Any:
        body = request.get_json(silent=True) or {}
        result = SERVICE.choose_launcher(str(body.get("path") or ""))
        return jsonify({"ok": True, **result})

    @app.post("/api/pick-folder")
    def pick_folder() -> Any:
        return jsonify({"ok": True, **SERVICE.pick_folder()})

    @app.post("/api/open-backups")
    def open_backups() -> Any:
        return jsonify({"ok": True, **SERVICE.open_backups()})

    @app.get("/api/mods")
    def mods() -> Any:
        version = request.args.get("version") or ""
        if not version:
            raise ApiError("缺少 version 参数")
        return jsonify({"ok": True, **SERVICE.mods_payload(version)})

    @app.get("/api/mod")
    def mod() -> Any:
        version = request.args.get("version") or ""
        key = request.args.get("key") or ""
        if not version or not key:
            raise ApiError("缺少 version 或 key 参数")
        return jsonify({"ok": True, **SERVICE.mod_payload(version, key)})

    @app.get("/api/config")
    def config() -> Any:
        version = request.args.get("version") or ""
        key = request.args.get("key") or ""
        file_path = request.args.get("file") or ""
        if not version or not key or not file_path:
            raise ApiError("缺少 version、key 或 file 参数")
        return jsonify({"ok": True, **SERVICE.config_payload(version, key, file_path)})

    @app.post("/api/config/save")
    def save_config() -> Any:
        body = request.get_json(silent=True) or {}
        version = str(body.get("version") or "")
        key = str(body.get("key") or "")
        file_path = str(body.get("file") or "")
        base_hash = str(body.get("hash") or "")
        if not version or not key or not file_path:
            raise ApiError("缺少 version、key 或 file 参数")
        changes = body.get("changes")
        raw = body.get("raw", None)
        if changes is not None and not isinstance(changes, list):
            raise ApiError("changes 必须是数组")
        result = SERVICE.save_config(version, key, file_path, base_hash, changes=changes, raw=raw)
        return jsonify({"ok": True, **result})

    @app.post("/api/refresh")
    def refresh() -> Any:
        body = request.get_json(silent=True) or {}
        version = body.get("version")
        return jsonify({"ok": True, **SERVICE.refresh(str(version) if version else None)})

    @app.post("/api/reveal")
    def reveal() -> Any:
        body = request.get_json(silent=True) or {}
        version = str(body.get("version") or "")
        if not version:
            raise ApiError("缺少 version 参数")
        return jsonify({"ok": True, **SERVICE.reveal(version, body.get("file") or None)})

    @app.get("/api/icon")
    def icon() -> Any:
        version = request.args.get("version") or ""
        key = request.args.get("key") or ""
        if not version or not key:
            return Response(status=404)
        result = SERVICE.mod_icon(version, key)
        if not result:
            return Response(status=404)
        data, mime = result
        return Response(data, mimetype=mime, headers={"Cache-Control": "public, max-age=300"})

    @app.get("/api/version-icon")
    def version_icon() -> Any:
        version = request.args.get("version") or ""
        if not version:
            return Response(status=404)
        result = SERVICE.version_icon(version)
        if not result:
            return Response(status=404)
        data, mime = result
        return Response(data, mimetype=mime, headers={"Cache-Control": "public, max-age=300"})

    return app


def _find_free_port(start: int = 8765) -> int:
    for port in range(start, start + 60):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    raise RuntimeError("找不到可用的本地端口")


def main() -> None:
    parser = argparse.ArgumentParser(description="CraftTune - Minecraft 模组参数工坊")
    parser.add_argument("--port", type=int, default=None, help="监听端口（默认自动选择 8765 起）")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--no-browser", action="store_true", help="不自动打开浏览器")
    args = parser.parse_args()
    try:
        if os.name == "nt":
            import ctypes

            ctypes.windll.kernel32.SetConsoleOutputCP(65001)
            ctypes.windll.kernel32.SetConsoleCP(65001)
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except Exception:
        pass
    port = args.port or _find_free_port(8765)
    url = "http://%s:%d" % (args.host, port)
    app = create_app()
    print("")
    print("  CraftTune · Minecraft 模组参数工坊")
    print("  ------------------------------------------------")
    print("  已启动：%s" % url)
    print("  按 Ctrl+C 停止服务")
    print("")
    if not args.no_browser:
        def open_browser() -> None:
            try:
                webbrowser.open(url)
            except Exception:
                pass

        threading.Timer(0.9, open_browser).start()
    app.run(host=args.host, port=port, debug=False, threaded=True, use_reloader=False)


if __name__ == "__main__":
    main()
