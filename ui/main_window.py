from __future__ import annotations

import logging
import os
import traceback
from typing import Callable, Dict, List, Optional

from PyQt5.QtCore import QSize, Qt, QTimer, QUrl, pyqtSignal
from PyQt5.QtGui import QDesktopServices, QIcon, QKeySequence, QPixmap
from PyQt5.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QShortcut,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from backend.service import ApiError, ConfigService
from backend import __release__
from backend import direct_launcher
from backend.settings import load_settings, save_settings
from .async_utils import TaskRunner
from .pages import EditorPage, HomePage, ModsPage
from .theme import ASSETS, COLORS, chip_style, icon, pixmap_from_bytes
from .widgets import ElidedLabel, IconTile, ToastManager, clear_layout, loader_variant


class MainWindow(QMainWindow):
    page_ready = pyqtSignal(str)

    def __init__(self, capture: Optional[Dict] = None):
        super().__init__()
        self.service = ConfigService()
        self.runner = TaskRunner(self, 6)
        self.status: Dict = {}
        self.versions: List[Dict] = []
        self.current_version: Optional[Dict] = None
        self.mods_data: Optional[Dict] = None
        self.mod_data: Optional[Dict] = None
        self.icon_cache: Dict[tuple, QPixmap] = {}
        self._icon_pending: Dict[tuple, List[Callable[[QPixmap], None]]] = {}
        self._nav_token = 0
        self._config_token = 0
        self._home_ready = False
        self._capture = capture
        self._capture_done = False
        self._capture_page = None
        self._save_in_progress = False
        self._launching = False

        self.setWindowTitle(__release__ + " · 模组参数工坊")
        self.setMinimumSize(1120, 740)
        self.resize(1440, 900)
        icon_path = ASSETS / "app.ico"
        if icon_path.is_file():
            self.setWindowIcon(QIcon(str(icon_path)))
        self._build()
        self._connect()
        QShortcut(QKeySequence.Save, self, activated=self.save_current)
        QShortcut(QKeySequence.Find, self, activated=self.focus_search)
        QShortcut(QKeySequence("Alt+Left"), self, activated=self.go_back)
        QTimer.singleShot(0, self.load_initial)
        if capture:
            self.page_ready.connect(self._on_capture_ready)
            self._capture_page = capture.get("page", "home")
            if self._home_ready:
                QTimer.singleShot(0, lambda: self._on_capture_ready("home"))

    # ------------------------------------------------------------------ UI
    def _build(self) -> None:
        root = QWidget()
        root.setObjectName("Root")
        self.setCentralWidget(root)
        outer = QHBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.sidebar = QFrame()
        self.sidebar.setObjectName("Sidebar")
        self.sidebar.setFixedWidth(238)
        side = QVBoxLayout(self.sidebar)
        side.setContentsMargins(18, 24, 18, 18)
        side.setSpacing(0)

        brand = QHBoxLayout()
        brand.setSpacing(11)
        mark = QLabel()
        mark.setFixedSize(40, 40)
        mark.setAlignment(Qt.AlignCenter)
        mark.setStyleSheet(
            "background:rgba(118,230,180,0.08); border:1px solid rgba(118,230,180,0.20);"
            " border-radius:11px;"
        )
        mark.setPixmap(icon("cube", COLORS["mint"], 24).pixmap(24, 24))
        brand.addWidget(mark)
        brand_text = QVBoxLayout()
        brand_text.setSpacing(0)
        brand_name = QLabel('Craft<span style="color:#76e6b4">Tune</span>')
        brand_name.setObjectName("BrandName")
        brand_name.setTextFormat(Qt.RichText)
        brand_text.addWidget(brand_name)
        brand_sub = QLabel(__release__)
        brand_sub.setObjectName("BrandSub")
        brand_sub.setToolTip("CraftTune 第一个大版本")
        brand_text.addWidget(brand_sub)
        brand.addLayout(brand_text)
        brand.addStretch(1)
        side.addLayout(brand)
        side.addSpacing(28)

        label = QLabel("工作台")
        label.setObjectName("SideLabel")
        side.addWidget(label)
        side.addSpacing(8)
        self.nav_versions = QPushButton("版本库")
        self.nav_versions.setObjectName("Nav")
        self.nav_versions.setCheckable(True)
        self.nav_versions.setChecked(True)
        self.nav_versions.setIcon(icon("grid", COLORS["mint"], 16))
        self.nav_versions.setIconSize(QSize(16, 16))
        self.nav_versions.setCursor(Qt.PointingHandCursor)
        side.addWidget(self.nav_versions)
        self.nav_help = QPushButton("使用说明")
        self.nav_help.setObjectName("Nav")
        self.nav_help.setIcon(icon("info", COLORS["muted"], 16))
        self.nav_help.setIconSize(QSize(16, 16))
        self.nav_help.setCursor(Qt.PointingHandCursor)
        side.addWidget(self.nav_help)
        self.nav_backups = QPushButton("安全备份")
        self.nav_backups.setObjectName("Nav")
        self.nav_backups.setIcon(icon("save", COLORS["muted"], 16))
        self.nav_backups.setIconSize(QSize(16, 16))
        self.nav_backups.setCursor(Qt.PointingHandCursor)
        side.addWidget(self.nav_backups)
        side.addSpacing(20)

        self.side_version = QFrame()
        self.side_version.setObjectName("SideVersion")
        sv = QVBoxLayout(self.side_version)
        sv.setContentsMargins(11, 11, 11, 10)
        sv.setSpacing(7)
        sv_top = QHBoxLayout()
        sv_top.setSpacing(8)
        self.sv_icon = IconTile(30, 8, "?")
        sv_top.addWidget(self.sv_icon)
        sv_text = QVBoxLayout()
        sv_text.setSpacing(0)
        self.sv_name = QLabel("")
        self.sv_name.setStyleSheet("font-size:9pt; font-weight:bold; color:#c2d0c9;")
        self.sv_name.setWordWrap(False)
        sv_text.addWidget(self.sv_name)
        self.sv_meta = QLabel("")
        self.sv_meta.setObjectName("Mono")
        sv_text.addWidget(self.sv_meta)
        sv_top.addLayout(sv_text, 1)
        sv.addLayout(sv_top)
        self.sv_stats = QLabel("")
        self.sv_stats.setObjectName("Mono")
        self.sv_stats.setStyleSheet("color:#5f7068; font-size:8pt; border-top:1px solid #1c2a32; padding-top:6px;")
        sv.addWidget(self.sv_stats)
        switch = QPushButton("切换游戏版本")
        switch.setObjectName("Ghost")
        switch.setIcon(icon("refresh", COLORS["mint"], 13))
        switch.setIconSize(QSize(13, 13))
        switch.setStyleSheet("text-align:left; color:#76e6b4; padding:2px 0; font-size:8pt;")
        switch.setCursor(Qt.PointingHandCursor)
        sv.addWidget(switch)
        self.side_version.hide()
        side.addWidget(self.side_version)
        side.addStretch(1)

        self.launch_button = QPushButton("启动游戏")
        self.launch_button.setObjectName("LaunchGame")
        self.launch_button.setIcon(icon("play", "#062417", 18))
        self.launch_button.setIconSize(QSize(18, 18))
        self.launch_button.setCursor(Qt.PointingHandCursor)
        self.launch_button.setEnabled(False)
        self.launch_button.setToolTip("选择游戏版本后，直接启动 Minecraft")
        side.addWidget(self.launch_button)
        launch_hint = QLabel("直接启动 Minecraft")
        launch_hint.setObjectName("Mono")
        launch_hint.setAlignment(Qt.AlignCenter)
        launch_hint.setStyleSheet("color:#4f6259; font-size:7.5pt; margin-top:1px;")
        side.addWidget(launch_hint)
        side.addSpacing(10)

        tip = QFrame()
        tip.setObjectName("Tip")
        tip_layout = QVBoxLayout(tip)
        tip_layout.setContentsMargins(11, 10, 11, 10)
        tip_layout.setSpacing(2)
        tip_title = QLabel("安全第一")
        tip_title.setStyleSheet("color:#c2d0c9; font-size:8.5pt; font-weight:bold;")
        tip_layout.addWidget(tip_title)
        tip_text = QLabel("每次保存都会自动备份原文件，参数修改可随时撤销。")
        tip_text.setWordWrap(True)
        tip_text.setStyleSheet("color:#5f7068; font-size:8pt;")
        tip_layout.addWidget(tip_text)
        side.addWidget(tip)
        side.addSpacing(12)

        self.live_dot = QLabel("●")
        self.live_dot.setStyleSheet("color:#76e6b4; font-size:7pt;")
        footer = QHBoxLayout()
        footer.setSpacing(4)
        footer.addWidget(self.live_dot, 0, Qt.AlignTop)
        footer_text = QVBoxLayout()
        footer_text.setSpacing(2)
        self.footer_status = QLabel("正在检测启动器目录")
        self.footer_status.setStyleSheet("color:#8d9e96; font-size:7.5pt;")
        footer_text.addWidget(self.footer_status)
        self.footer_path = ElidedLabel("")
        self.footer_path.setObjectName("Mono")
        footer_text.addWidget(self.footer_path)
        footer.addLayout(footer_text, 1)
        side.addLayout(footer)
        outer.addWidget(self.sidebar)

        self.main_area = QWidget()
        self.main_area.setObjectName("MainArea")
        main_layout = QVBoxLayout(self.main_area)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        self.stack = QStackedWidget()
        main_layout.addWidget(self.stack)
        outer.addWidget(self.main_area, 1)

        self.home = HomePage(self.version_pixmap)
        self.mods = ModsPage(self.request_mod_icon)
        self.editor = EditorPage(self.request_mod_icon)
        self.stack.addWidget(self.home)
        self.stack.addWidget(self.mods)
        self.stack.addWidget(self.editor)
        self.stack.setCurrentWidget(self.home)
        self.toast = ToastManager(self.main_area)

    def _connect(self) -> None:
        self.nav_versions.clicked.connect(self.go_home)
        self.nav_help.clicked.connect(self.show_help)
        self.nav_backups.clicked.connect(self.show_backups)
        self.launch_button.clicked.connect(self.launch_game)
        self.home.version_selected.connect(self.open_version)
        self.home.choose_folder.connect(self.choose_launcher)
        self.home.manual_launcher.connect(self.manual_launcher)
        self.home.refresh_requested.connect(self.refresh_home)
        self.mods.back_requested.connect(self.go_home)
        self.mods.mod_selected.connect(self.open_mod)
        self.mods.refresh_requested.connect(self.refresh_mods)
        self.editor.back_requested.connect(self.back_to_mods)
        self.editor.refresh_requested.connect(self.refresh_editor)
        self.editor.reveal_mod_requested.connect(self.reveal_mod)
        self.editor.open_file_requested.connect(self.on_file_requested)
        self.editor.save_requested.connect(self.save_current)
        self.editor.reload_requested.connect(lambda: self.open_config(self.editor.current_file() or "", guard=True))
        self.editor.reveal_file_requested.connect(self.reveal_file)
        for button in self.side_version.findChildren(QPushButton):
            if button.text() == "切换游戏版本":
                button.clicked.connect(self.go_home)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if hasattr(self, "toast"):
            self.toast._reposition()

    # ------------------------------------------------------------------ launch
    def launch_game(self) -> None:
        if self._launching or not self.current_version:
            return
        version = self.current_version
        if not version.get("has_json"):
            self.toast.show_message("该版本缺少版本清单，无法直接启动", "warn")
            return
        version_id = version.get("id", "")
        self._launching = True
        self.launch_button.setEnabled(False)
        self.launch_button.setText("正在启动…")
        self._run(
            lambda: direct_launcher.launch(version_id),
            lambda result: self._on_game_launched(result, version),
            self._on_launch_error,
        )

    def _on_game_launched(self, result: Dict, version: Dict) -> None:
        self._launching = False
        self.launch_button.setText("启动游戏")
        self._update_sidebar()
        version_name = str(version.get("name") or version.get("id") or "")
        offline = bool(result.get("offline"))
        detail = "直接启动 · " + version_name + (" · 离线账号" if offline else "")
        warnings = result.get("warnings") or []
        if warnings:
            detail += " · " + "；".join(str(item) for item in warnings[:2])
        self.toast.show_message("游戏正在启动", "success", detail)

    def _on_launch_error(self, message: str, trace: str) -> None:
        self._launching = False
        self.launch_button.setText("启动游戏")
        self._update_sidebar()
        self.show_error(message, trace)

    def focus_search(self) -> None:
        if self.stack.currentWidget() is self.editor:
            self.editor.focus_params()
        elif self.stack.currentWidget() is self.mods:
            self.mods.focus_search()

    def go_back(self) -> None:
        if self.stack.currentWidget() is self.editor:
            self.back_to_mods()
        else:
            self.go_home()

    # ------------------------------------------------------------------ async
    def _run(self, fn, on_result, on_error=None) -> None:
        self.runner.run(fn, on_result, on_error or self.show_error)

    def show_error(self, message: str, trace: str = "") -> None:
        if trace:
            try:
                from backend.settings import DATA_DIR

                DATA_DIR.mkdir(parents=True, exist_ok=True)
                with (DATA_DIR / "crafttune-error.log").open("a", encoding="utf-8") as handle:
                    handle.write(trace + "\n")
            except Exception:
                pass
        self.toast.show_message("操作失败", "error", message)
        QMessageBox.warning(self, "操作失败", message)

    # ------------------------------------------------------------------ load
    def load_initial(self) -> None:
        self.home.set_loading("正在读取整合包…")
        self._home_ready = False
        self._run(
            lambda: (self.service.status(), self.service.list_versions()),
            self._on_initial,
            self._on_initial_error,
        )

    def _on_initial(self, result) -> None:
        self.status, self.versions = result
        if self.current_version is None or self.current_version.get("id") not in {v.get("id") for v in self.versions}:
            self.current_version = self._default_version()
        self.home.set_data(self.status, self.versions)
        self.home.finish_loading()
        self._update_sidebar()
        self.footer_status.setText("已检测到启动器目录" if self.status.get("launcher") else "等待选择启动器目录")
        self.footer_path.set_full_text(str(self.status.get("launcher") or "未选择 .minecraft 目录"))
        self._home_ready = True
        self.page_ready.emit("home")

    def _default_version(self) -> Optional[Dict]:
        if not self.versions:
            return None
        last = str(load_settings().get("last_version") or "")
        for version in self.versions:
            if version.get("id") == last and version.get("has_json"):
                return version
        for version in self.versions:
            if version.get("has_json"):
                return version
        return self.versions[0]

    def _on_initial_error(self, message: str, trace: str) -> None:
        self.home.finish_loading()
        self.show_error(message, trace)

    def version_pixmap(self, version_id: str) -> Optional[QPixmap]:
        key = ("version", version_id)
        if key in self.icon_cache:
            return self.icon_cache[key]
        try:
            result = self.service.version_icon(version_id)
        except Exception:
            return None
        if not result:
            return None
        data, mime = result
        pixmap = pixmap_from_bytes(data, mime, 128)
        if not pixmap.isNull():
            self.icon_cache[key] = pixmap
            return pixmap
        return None

    def request_mod_icon(self, version_id: str, key: str, callback: Callable[[QPixmap], None]) -> None:
        cache_key = ("mod", version_id, key)
        if cache_key in self.icon_cache:
            pixmap = self.icon_cache[cache_key]
            if not pixmap.isNull():
                callback(pixmap)
            return
        if cache_key in self._icon_pending:
            self._icon_pending[cache_key].append(callback)
            return
        self._icon_pending[cache_key] = [callback]

        def work():
            return self.service.mod_icon(version_id, key)

        def done(result):
            pixmap = QPixmap()
            if result:
                data, mime = result
                pixmap = pixmap_from_bytes(data, mime, 128)
            if not pixmap.isNull():
                self.icon_cache[cache_key] = pixmap
            for cb in self._icon_pending.pop(cache_key, []):
                try:
                    cb(pixmap)
                except RuntimeError:
                    pass

        def failed(message, trace):
            self._icon_pending.pop(cache_key, None)

        self._run(work, done, failed)

    def _update_sidebar(self) -> None:
        if self.current_version:
            v = self.current_version
            self.side_version.show()
            self.sv_name.setText(str(v.get("name") or ""))
            self.sv_name.setToolTip(str(v.get("name") or ""))
            self.sv_meta.setText(f"{v.get('game_version', '未知')} · {v.get('loader', '')}")
            self.sv_stats.setText(f"{v.get('mod_count', 0)} 模组    {v.get('config_count', 0)} 配置")
            pixmap = self.version_pixmap(v.get("id", ""))
            if pixmap:
                self.sv_icon.set_pixmap(pixmap)
        else:
            self.side_version.hide()
        enabled = (
            not self._launching
            and self.current_version is not None
            and bool(self.current_version.get("has_json"))
        )
        self.launch_button.setEnabled(enabled)
        if self.current_version and not self.current_version.get("has_json"):
            tooltip = "该版本缺少版本清单，无法直接启动"
        elif self.current_version:
            tooltip = "直接启动 " + str(self.current_version.get("name") or "")
        else:
            tooltip = "选择游戏版本后，直接启动 Minecraft"
        self.launch_button.setToolTip(tooltip)
        self.nav_versions.setChecked(True)

    # ------------------------------------------------------------------ nav
    def go_home(self) -> None:
        if self.stack.currentWidget() is self.editor and not self._confirm_leave_editor():
            return
        self.mods_data = None
        self.mod_data = None
        self._nav_token += 1
        self._config_token += 1
        self.stack.setCurrentWidget(self.home)
        self._update_sidebar()
        if self.status:
            self.home.set_data(self.status, self.versions)

    def open_version(self, version_id: str) -> None:
        version = next((item for item in self.versions if item.get("id") == version_id), None)
        if version is None:
            return
        if self.stack.currentWidget() is self.editor and not self._confirm_leave_editor():
            return
        self.current_version = version
        try:
            settings = load_settings()
            settings["last_version"] = version_id
            save_settings(settings)
        except OSError:
            pass
        self.mods_data = None
        self.mod_data = None
        self._update_sidebar()
        self.stack.setCurrentWidget(self.mods)
        self.mods.set_loading("正在读取模组与配置…")
        self.mods.crumb_current.setText(str(version.get("name") or ""))
        token = self._nav_token = self._nav_token + 1
        self._run(
            lambda: self.service.mods_payload(version_id),
            lambda result: self._on_mods_loaded(result, token),
            lambda message, trace: self._on_mods_error(message, trace, token),
        )

    def _on_mods_loaded(self, data: Dict, token: int) -> None:
        if token != self._nav_token:
            return
        self.mods_data = data
        self.mods.set_loading("正在读取模组与配置…")
        self.mods.set_version_icon(self.version_pixmap(self.current_version.get("id", "")) if self.current_version else None)
        self.mods.set_data(data)
        self.mods.finish_loading()
        self.page_ready.emit("mods")

    def _on_mods_error(self, message: str, trace: str, token: int) -> None:
        if token != self._nav_token:
            return
        self.mods.finish_loading()
        self.show_error(message, trace)

    def open_mod(self, mod_key: str) -> None:
        if not self.current_version:
            return
        if self.stack.currentWidget() is self.editor and not self._confirm_leave_editor():
            return
        version_id = self.current_version.get("id", "")
        self.stack.setCurrentWidget(self.editor)
        self.editor.set_loading("正在读取模组配置…")
        token = self._nav_token = self._nav_token + 1
        self._run(
            lambda: self.service.mod_payload(version_id, mod_key),
            lambda result: self._on_mod_loaded(result, token),
            lambda message, trace: self._on_mod_error(message, trace, token),
        )

    def _on_mod_loaded(self, data: Dict, token: int) -> None:
        if token != self._nav_token:
            return
        self.mod_data = data
        self.editor.set_mod(data)
        configs = data.get("configs") or []
        if not configs:
            self.editor.finish_loading()
            self.page_ready.emit("editor")
            return
        preferred = next((item for item in configs if item.get("field_count") not in (None, 0)), configs[0])
        self.open_config(str(preferred.get("path") or ""), guard=False)

    def _on_mod_error(self, message: str, trace: str, token: int) -> None:
        if token != self._nav_token:
            return
        self.editor.finish_loading()
        self.show_error(message, trace)

    def on_file_requested(self, path: str) -> None:
        if not path or path == self.editor.current_file():
            return
        if self.editor.is_dirty():
            if not self._confirm_discard("切换配置文件会丢弃当前尚未保存的参数修改。"):
                if self.editor.current_file():
                    self.editor.select_file(self.editor.current_file())
                return
        self.open_config(path, guard=False)

    def open_config(self, path: str, guard: bool = True) -> None:
        if not path or not self.current_version or not self.mod_data:
            return
        if guard and self.editor.is_dirty():
            if not self._confirm_discard("重新载入会丢弃当前尚未保存的修改。"):
                return
        version_id = self.current_version.get("id", "")
        mod_key = (self.mod_data.get("mod") or {}).get("key", "")
        self.editor.set_loading("正在解析配置参数…")
        token = self._config_token = self._config_token + 1
        old_file = self.editor.current_file()
        self._run(
            lambda: self.service.config_payload(version_id, mod_key, path),
            lambda result: self._on_config_loaded(result, token),
            lambda message, trace: self._on_config_error(message, trace, token, old_file),
        )

    def _on_config_loaded(self, config: Dict, token: int) -> None:
        if token != self._config_token:
            return
        self.editor.set_config(config)
        self.editor.finish_loading()
        self.page_ready.emit("editor")

    def _on_config_error(self, message: str, trace: str, token: int, old_file: Optional[str]) -> None:
        if token != self._config_token:
            return
        self.editor.finish_loading()
        if old_file:
            self.editor.select_file(old_file)
        self.show_error(message, trace)

    # ------------------------------------------------------------------ save
    def save_current(self) -> None:
        if self._save_in_progress or not self.mod_data or not self.current_version:
            return
        if self.editor._errors:
            self.toast.show_message("请先修正无效的输入", "warn")
            return
        payload = self.editor.build_save_payload()
        if not payload:
            return
        count = self.editor.dirty_count()
        if count == 0:
            self.toast.show_message("没有需要保存的修改", "info")
            return
        self._save_in_progress = True
        self.editor.set_saving(True)
        self._run(
            lambda: self.service.save_config(
                payload["version"],
                payload["key"],
                payload["file"],
                payload["hash"],
                changes=payload.get("changes"),
                raw=payload.get("raw"),
            ),
            lambda result: self._on_saved(result, count),
            self._on_save_error,
        )

    def _on_saved(self, result: Dict, count: int) -> None:
        self._save_in_progress = False
        if result.get("unchanged"):
            self.editor.set_saving(False)
            self.toast.show_message("内容没有变化", "info")
            return
        self.editor.apply_saved(result)
        self.editor.set_saving(False)
        backup = result.get("backup") or ""
        self.toast.show_message(
            f"已保存 {count} 项修改",
            "success",
            ("原文件已备份 · " + backup.split("/")[0]) if backup else "原文件已自动备份",
        )

    def _on_save_error(self, message: str, trace: str) -> None:
        self._save_in_progress = False
        self.editor.set_saving(False)
        if "已被外部修改" in message or "重新载入" in message:
            box = QMessageBox(self)
            box.setWindowTitle("文件已被外部修改")
            box.setText("在编辑期间，这个配置文件被其他程序修改了。为了避免覆盖新内容，CraftTune 已停止保存。")
            box.setInformativeText("是否重新载入？")
            box.setIcon(QMessageBox.Warning)
            box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
            box.button(QMessageBox.Yes).setText("重新载入")
            box.button(QMessageBox.No).setText("取消")
            if box.exec_() == QMessageBox.Yes:
                self.open_config(self.editor.current_file() or "", guard=False)
            return
        self.show_error(message, trace)

    # ------------------------------------------------------------------ refresh
    def refresh_home(self) -> None:
        self.home.set_loading("正在重新扫描…")
        self._run(
            lambda: (self.service.status(), self.service.list_versions()),
            self._on_refreshed_home,
            self._on_initial_error,
        )

    def _on_refreshed_home(self, result) -> None:
        self.status, self.versions = result
        if self.current_version is None or self.current_version.get("id") not in {v.get("id") for v in self.versions}:
            self.current_version = self._default_version()
        self.home.set_data(self.status, self.versions)
        self.home.finish_loading()
        self._update_sidebar()
        self.footer_path.set_full_text(str(self.status.get("launcher") or ""))
        self.toast.show_message("已重新扫描", "success")

    def refresh_mods(self) -> None:
        if self.current_version:
            self.open_version(self.current_version.get("id", ""))

    def refresh_editor(self) -> None:
        if self.current_version and self.mod_data:
            mod_key = (self.mod_data.get("mod") or {}).get("key", "")
            self.open_mod(mod_key)

    def back_to_mods(self) -> None:
        if not self._confirm_leave_editor():
            return
        self.stack.setCurrentWidget(self.mods)
        if self.mods_data:
            self.mods.set_data(self.mods_data)

    # ------------------------------------------------------------------ launcher
    def choose_launcher(self) -> None:
        start = str(self.status.get("launcher") or "")
        path = QFileDialog.getExistingDirectory(self, "选择 Minecraft 的 .minecraft 文件夹", start)
        if path:
            self.apply_launcher(path)

    def manual_launcher(self) -> None:
        current = str(self.status.get("launcher") or "")
        path, ok = QInputDialog.getText(
            self,
            "指定 .minecraft 目录",
            "请输入包含 versions 文件夹的 .minecraft 路径：",
            text=current,
        )
        if ok and path.strip():
            self.apply_launcher(path.strip().strip('"'))

    def apply_launcher(self, path: str) -> None:
        self.home.set_loading("正在读取新的 Minecraft 目录…")
        self._run(
            lambda: self.service.choose_launcher(path),
            self._on_launcher_changed,
            self._on_launcher_error,
        )

    def _on_launcher_changed(self, result: Dict) -> None:
        self.status["launcher"] = result.get("launcher") or ""
        self.status["detected"] = result.get("launcher") or ""
        self.versions = result.get("versions") or []
        self.current_version = self._default_version()
        self.mods_data = None
        self.mod_data = None
        self.stack.setCurrentWidget(self.home)
        self.home.set_data(self.status, self.versions)
        self.home.finish_loading()
        self.footer_path.set_full_text(str(self.status.get("launcher") or ""))
        self.toast.show_message("已切换 Minecraft 目录", "success", f"发现 {len(self.versions)} 个游戏版本")

    def _on_launcher_error(self, message: str, trace: str) -> None:
        self.home.finish_loading()
        self.show_error(message, trace)

    # ------------------------------------------------------------------ dialogs
    def show_help(self) -> None:
        text = (
            "<b>1. 选择游戏版本</b><br>"
            "CraftTune 会读取版本隔离目录中的 mods 与 config，不会移动或上传任何文件。<br><br>"
            "<b>2. 选择模组</b><br>"
            "配置文件通过模组 ID、JAR 文件名和目录名自动关联；未匹配的文件会集中到“未归属配置文件”。<br><br>"
            "<b>3. 修改与保存</b><br>"
            "开关、数字、文本、数组会以不同控件展示。保存时只替换目标值，并自动备份原文件。<br><br>"
            "<span style='color:#edb668'>提示：修改配置前建议关闭游戏；部分模组只会在重启后读取配置。</span>"
            "<br><br><span style='color:#5f7068'>" + __release__ + "</span>"
        )
        box = QMessageBox(self)
        box.setWindowTitle(__release__ + " 使用说明")
        box.setTextFormat(Qt.RichText)
        box.setText(text)
        box.setIcon(QMessageBox.Information)
        box.exec_()

    def show_backups(self) -> None:
        path = str((self.status or {}).get("backup_dir") or "")
        box = QMessageBox(self)
        box.setWindowTitle("安全备份")
        box.setText("每次保存前，CraftTune 会把原文件复制到本地备份目录。")
        box.setInformativeText(path or "暂无备份目录")
        box.setIcon(QMessageBox.Information)
        open_button = box.addButton("打开备份目录", QMessageBox.ActionRole)
        box.addButton("关闭", QMessageBox.AcceptRole)
        box.exec_()
        if box.clickedButton() is open_button:
            try:
                self.service.open_backups()
            except Exception as exc:
                self.show_error(str(exc))

    def reveal_mod(self) -> None:
        if not self.current_version:
            return
        try:
            self.service.reveal(self.current_version.get("id", ""))
        except Exception as exc:
            self.show_error(str(exc))

    def reveal_file(self) -> None:
        if not self.current_version or not self.editor.current_file():
            return
        try:
            self.service.reveal(self.current_version.get("id", ""), self.editor.current_file())
        except Exception as exc:
            self.show_error(str(exc))

    # ------------------------------------------------------------------ guards
    def _confirm_discard(self, message: str) -> bool:
        box = QMessageBox(self)
        box.setWindowTitle("放弃未保存的修改？")
        box.setText(message)
        box.setIcon(QMessageBox.Warning)
        box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        box.button(QMessageBox.Yes).setText("放弃并继续")
        box.button(QMessageBox.No).setText("取消")
        return box.exec_() == QMessageBox.Yes

    def _confirm_leave_editor(self) -> bool:
        if self.stack.currentWidget() is not self.editor:
            return True
        if not self.editor.is_dirty():
            return True
        return self._confirm_discard("当前配置文件还有未保存的修改，离开会丢失这些修改。")

    def closeEvent(self, event) -> None:
        if not self._confirm_leave_editor():
            event.ignore()
            return
        self.runner.wait(1500)
        event.accept()

    # ------------------------------------------------------------------ capture
    def _on_capture_ready(self, page: str) -> None:
        if not self._capture or self._capture_done:
            return
        target = self._capture.get("page", "home")
        version_id = self._capture.get("version") or ""
        if target == "home":
            self._grab_capture()
            return
        if target == "mods":
            if page == "home":
                self.open_version(version_id or (self.versions[0]["id"] if self.versions else ""))
            elif page == "mods":
                self._grab_capture()
            return
        if target == "editor":
            if page == "home":
                self.open_version(version_id or (self.versions[0]["id"] if self.versions else ""))
            elif page == "mods":
                mod_key = self._capture.get("mod") or ""
                if not mod_key:
                    candidates = [
                        item for item in (self.mods_data or {}).get("mods", [])
                        if (item.get("config_count") or 0) > 0 and not item.get("is_virtual")
                    ]
                    mod_key = candidates[0]["key"] if candidates else ""
                if mod_key:
                    self.open_mod(mod_key)
            elif page == "editor":
                self._grab_capture()

    def _grab_capture(self) -> None:
        if self._capture_done:
            return
        self._capture_done = True
        path = self._capture.get("path")
        if not path:
            QApplication.instance().quit()
            return

        def save():
            try:
                self.grab().save(path)
                logging.info("Saved screenshot: %s", path)
            finally:
                QApplication.instance().quit()

        QTimer.singleShot(1000, save)
