from __future__ import annotations

import argparse
import logging
import os
import sys
import traceback
from pathlib import Path

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont, QIcon
from PyQt5.QtWidgets import QApplication, QMessageBox

from backend.settings import APP_ROOT, DATA_DIR
from backend import __release__
from ui.main_window import MainWindow
from ui.theme import ASSETS, stylesheet


def setup_logging() -> None:
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    if any(isinstance(handler, logging.FileHandler) for handler in root.handlers):
        return
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        handler = logging.FileHandler(str(DATA_DIR / "crafttune.log"), encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        root.addHandler(handler)
    except Exception:
        logging.basicConfig(level=logging.INFO)


def install_exception_hook() -> None:
    def hook(exc_type, exc, tb):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc, tb)
            return
        logging.error("Unhandled exception", exc_info=(exc_type, exc, tb))
        try:
            QMessageBox.critical(
                None,
                "CraftTune 遇到错误",
                "程序遇到未处理的错误：\n\n%s\n\n详细信息已写入 data/crafttune.log。" % exc,
            )
        except Exception:
            pass

    sys.excepthook = hook


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="CraftTune - Minecraft 模组参数工坊")
    parser.add_argument("--screenshot", default="", help="开发用：窗口加载完成后截图并退出")
    parser.add_argument("--page", default="home", choices=["home", "mods", "editor"])
    parser.add_argument("--version", default="", help="截图时使用的版本 ID")
    parser.add_argument("--mod", default="", help="截图时使用的模组 key")
    return parser.parse_args()


def main() -> None:
    setup_logging()
    install_exception_hook()
    os.environ.setdefault("QT_AUTO_SCREEN_SCALE_FACTOR", "1")
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    app = QApplication(sys.argv)
    app.setApplicationName("CraftTune")
    app.setApplicationDisplayName(__release__ + " · 模组参数工坊")
    app.setStyle("Fusion")
    font = QFont("Microsoft YaHei UI", 10)
    app.setFont(font)
    app.setStyleSheet(stylesheet())
    icon_path = ASSETS / "app.ico"
    if icon_path.is_file():
        app.setWindowIcon(QIcon(str(icon_path)))
    args = parse_args()
    capture = None
    if args.screenshot:
        capture = {
            "path": args.screenshot,
            "page": args.page,
            "version": args.version,
            "mod": args.mod,
        }
    window = MainWindow(capture=capture)
    window.show()
    if capture:
        QTimer.singleShot(25000, app.quit)
    raise SystemExit(app.exec_())


if __name__ == "__main__":
    main()
