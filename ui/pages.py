from __future__ import annotations

import json
from typing import Any, Callable, Dict, List, Optional

from PyQt5.QtCore import QSize, Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QFont, QPixmap
from PyQt5.QtWidgets import (
    QCheckBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from .theme import COLORS, chip_style, icon
from .widgets import (
    BasePage,
    FieldRow,
    FileDelegate,
    GroupCard,
    IconTile,
    ModCard,
    VersionCard,
    clear_layout,
    deep_equal,
    format_variant,
    hline,
    loader_variant,
)


VersionIconProvider = Callable[[str], Optional[QPixmap]]
ModIconRequester = Callable[[str, str, Callable[[QPixmap], None]], None]


class HomePage(BasePage):
    version_selected = pyqtSignal(str)
    choose_folder = pyqtSignal()
    manual_launcher = pyqtSignal()
    refresh_requested = pyqtSignal()

    def __init__(self, version_icon_provider: VersionIconProvider, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._version_icon_provider = version_icon_provider
        self._versions: List[Dict] = []
        self._launcher = ""
        self._columns = 2
        self._build()

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        root.addWidget(self.scroll)
        content = QWidget()
        self.scroll.setWidget(content)
        self.content_layout = QVBoxLayout(content)
        self.content_layout.setContentsMargins(38, 30, 38, 50)
        self.content_layout.setSpacing(0)

        eyebrow = QLabel("MINECRAFT JAVA  ·  MOD CONFIG STUDIO")
        eyebrow.setObjectName("Eyebrow")
        self.content_layout.addWidget(eyebrow)
        self.content_layout.addSpacing(12)
        hero = QLabel('让每一个参数，<br><span style="color:#76e6b4;">都听你的。</span>')
        hero.setObjectName("HeroTitle")
        hero.setTextFormat(Qt.RichText)
        self.content_layout.addWidget(hero)
        self.content_layout.addSpacing(16)
        lead = QLabel(
            "从整合包的模组列表中找到配置文件，把晦涩的键值变成清晰的开关、数字和选项。"
            "<b>自动关联模组、保留注释格式、保存前备份</b>，安心调出最顺手的整合包。"
        )
        lead.setObjectName("HeroLead")
        lead.setWordWrap(True)
        lead.setMaximumWidth(680)
        self.content_layout.addWidget(lead)
        self.content_layout.addSpacing(28)

        self.launcher_card = QFrame()
        self.launcher_card.setObjectName("LauncherCard")
        card_layout = QHBoxLayout(self.launcher_card)
        card_layout.setContentsMargins(16, 13, 16, 13)
        card_layout.setSpacing(13)
        self.launcher_icon = QLabel()
        self.launcher_icon.setFixedSize(38, 38)
        self.launcher_icon.setAlignment(Qt.AlignCenter)
        self.launcher_icon.setStyleSheet("background:rgba(118,230,180,0.07); border:1px solid rgba(118,230,180,0.14); border-radius:9px;")
        self.launcher_icon.setPixmap(icon("folder", COLORS["mint"], 18).pixmap(18, 18))
        card_layout.addWidget(self.launcher_icon)
        path_box = QVBoxLayout()
        path_box.setSpacing(2)
        self.launcher_label = QLabel("当前 Minecraft 目录")
        self.launcher_label.setObjectName("StatLabel")
        path_box.addWidget(self.launcher_label)
        self.launcher_path = QLabel("尚未选择")
        self.launcher_path.setObjectName("Path")
        self.launcher_path.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        path_box.addWidget(self.launcher_path)
        card_layout.addLayout(path_box, 1)
        manual = QPushButton("指定目录")
        manual.setIcon(icon("folder", COLORS["muted"], 15))
        manual.setIconSize(QSize(15, 15))
        manual.setCursor(Qt.PointingHandCursor)
        manual.clicked.connect(self.manual_launcher)
        card_layout.addWidget(manual)
        browse = QPushButton("浏览")
        browse.setObjectName("Primary")
        browse.setIcon(icon("search", "#062417", 15))
        browse.setIconSize(QSize(15, 15))
        browse.setCursor(Qt.PointingHandCursor)
        browse.clicked.connect(self.choose_folder)
        card_layout.addWidget(browse)
        self.content_layout.addWidget(self.launcher_card)
        self.content_layout.addSpacing(36)

        section = QHBoxLayout()
        title_box = QVBoxLayout()
        title_box.setSpacing(3)
        title = QLabel("选择游戏版本")
        title.setObjectName("SectionTitle")
        title_box.addWidget(title)
        self.section_sub = QLabel("不同版本拥有独立的 mods 与 config 目录")
        self.section_sub.setObjectName("Muted")
        self.section_sub.setStyleSheet("color:#5f7068; font-size:8.5pt;")
        title_box.addWidget(self.section_sub)
        section.addLayout(title_box)
        section.addStretch(1)
        refresh = QPushButton("重新扫描")
        refresh.setObjectName("Ghost")
        refresh.setIcon(icon("refresh", COLORS["muted"], 14))
        refresh.setIconSize(QSize(14, 14))
        refresh.setCursor(Qt.PointingHandCursor)
        refresh.clicked.connect(self.refresh_requested)
        section.addWidget(refresh)
        self.content_layout.addLayout(section)
        self.content_layout.addSpacing(16)

        self.version_grid = QGridLayout()
        self.version_grid.setContentsMargins(0, 0, 0, 0)
        self.version_grid.setHorizontalSpacing(14)
        self.version_grid.setVerticalSpacing(14)
        self.content_layout.addLayout(self.version_grid)
        self.empty_widget = QFrame()
        self.empty_widget.setObjectName("Empty")
        empty_layout = QVBoxLayout(self.empty_widget)
        empty_layout.setContentsMargins(30, 42, 30, 42)
        empty_layout.setSpacing(9)
        empty_icon = QLabel()
        empty_icon.setAlignment(Qt.AlignCenter)
        empty_icon.setPixmap(icon("package", COLORS["mint"], 28).pixmap(28, 28))
        empty_layout.addWidget(empty_icon)
        self.empty_title = QLabel("还没有可用的游戏版本")
        self.empty_title.setAlignment(Qt.AlignCenter)
        self.empty_title.setStyleSheet("font-size:12pt; font-weight:bold;")
        empty_layout.addWidget(self.empty_title)
        self.empty_text = QLabel("选择 .minecraft 文件夹后，会自动读取 versions、mods 和 config。")
        self.empty_text.setAlignment(Qt.AlignCenter)
        self.empty_text.setWordWrap(True)
        self.empty_text.setStyleSheet("color:#5f7068; font-size:9pt;")
        empty_layout.addWidget(self.empty_text)
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        empty_browse = QPushButton("选择 .minecraft 文件夹")
        empty_browse.setObjectName("Primary")
        empty_browse.setCursor(Qt.PointingHandCursor)
        empty_browse.clicked.connect(self.choose_folder)
        buttons.addWidget(empty_browse)
        empty_manual = QPushButton("手动输入路径")
        empty_manual.setCursor(Qt.PointingHandCursor)
        empty_manual.clicked.connect(self.manual_launcher)
        buttons.addWidget(empty_manual)
        buttons.addStretch(1)
        empty_layout.addLayout(buttons)
        self.content_layout.addWidget(self.empty_widget)
        self.empty_widget.hide()

        self.content_layout.addSpacing(34)
        steps = QHBoxLayout()
        steps.setSpacing(10)
        for index, (title, desc) in enumerate(
            (
                ("01", "选择游戏版本"),
                ("02", "找到目标模组"),
                ("03", "调整并保存"),
            )
        ):
            step = QFrame()
            step.setObjectName("Step")
            step_layout = QHBoxLayout(step)
            step_layout.setContentsMargins(16, 14, 16, 14)
            step_layout.setSpacing(12)
            number = QLabel(title)
            number.setStyleSheet("color:#76e6b4; font-family:'Cascadia Code','Consolas'; font-size:9pt;")
            step_layout.addWidget(number, 0, Qt.AlignTop)
            text_box = QVBoxLayout()
            text_box.setSpacing(3)
            step_title = QLabel(desc)
            step_title.setStyleSheet("font-size:9.5pt; font-weight:bold; color:#c2d0c9;")
            text_box.addWidget(step_title)
            hint = QLabel(
                "读取每个版本的模组与配置。"
                if index == 0
                else ("按名称搜索，配置自动归类。" if index == 1 else "开关、数字、文本与数组可视化编辑。")
            )
            hint.setStyleSheet("color:#5f7068; font-size:8.5pt;")
            hint.setWordWrap(True)
            text_box.addWidget(hint)
            step_layout.addLayout(text_box, 1)
            steps.addWidget(step, 1)
        self.content_layout.addLayout(steps)

    # ---------------------------------------------------------------- data
    def set_data(self, status: Dict, versions: List[Dict]) -> None:
        self._versions = versions or []
        self._launcher = str(status.get("launcher") or "")
        self.launcher_path.setText(self._launcher or "尚未选择 .minecraft 文件夹")
        self.launcher_path.setToolTip(self._launcher)
        self.launcher_label.setText("当前 Minecraft 目录" if self._launcher else "尚未找到 Minecraft 目录")
        self.section_sub.setText(f"不同版本拥有独立的 mods 与 config 目录 · 共 {len(self._versions)} 个实例")
        self._rebuild_versions()
        self.empty_widget.setVisible(not self._versions)

    def _rebuild_versions(self) -> None:
        clear_layout(self.version_grid)
        if not self._versions:
            return
        for index, version in enumerate(self._versions):
            card = VersionCard(version)
            card.clicked.connect(self.version_selected)
            pixmap = self._version_icon_provider(version.get("id", ""))
            if pixmap:
                card.set_icon(pixmap)
            row, col = divmod(index, self._columns)
            self.version_grid.addWidget(card, row, col)
        for col in range(self._columns):
            self.version_grid.setColumnStretch(col, 1)
        self.version_grid.setRowStretch(len(self._versions) // self._columns + 1, 1)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        columns = 1 if self.width() < 980 else 2
        if columns != self._columns:
            self._columns = columns
            self._rebuild_versions()


class ModsPage(BasePage):
    back_requested = pyqtSignal()
    mod_selected = pyqtSignal(str)
    refresh_requested = pyqtSignal()

    def __init__(self, icon_requester: ModIconRequester, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._icon_requester = icon_requester
        self._data: Optional[Dict] = None
        self._query = ""
        self._filter = "all"
        self._cards: List[ModCard] = []
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(120)
        self._debounce.timeout.connect(self._rebuild_grid)
        self._build()

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(38, 22, 38, 18)
        root.setSpacing(0)

        crumb = QHBoxLayout()
        crumb.setSpacing(8)
        back = QPushButton("版本库")
        back.setObjectName("Ghost")
        back.setCursor(Qt.PointingHandCursor)
        back.clicked.connect(self.back_requested)
        crumb.addWidget(back)
        sep = QLabel("/")
        sep.setStyleSheet("color:#3f4d47;")
        crumb.addWidget(sep)
        self.crumb_current = QLabel("")
        self.crumb_current.setObjectName("Muted")
        crumb.addWidget(self.crumb_current)
        crumb.addStretch(1)
        back2 = QPushButton("返回版本列表")
        back2.setObjectName("Ghost")
        back2.setIcon(icon("back", COLORS["muted"], 14))
        back2.setIconSize(QSize(14, 14))
        back2.setCursor(Qt.PointingHandCursor)
        back2.clicked.connect(self.back_requested)
        crumb.addWidget(back2)
        root.addLayout(crumb)
        root.addSpacing(16)

        self.banner = QFrame()
        self.banner.setObjectName("Banner")
        banner_layout = QHBoxLayout(self.banner)
        banner_layout.setContentsMargins(20, 18, 20, 18)
        banner_layout.setSpacing(16)
        self.version_icon = IconTile(62, 15, "?")
        banner_layout.addWidget(self.version_icon)
        info = QVBoxLayout()
        info.setSpacing(7)
        self.version_name = QLabel("")
        self.version_name.setObjectName("SectionTitle")
        info.addWidget(self.version_name)
        self.version_chips = QHBoxLayout()
        self.version_chips.setSpacing(6)
        info.addLayout(self.version_chips)
        banner_layout.addLayout(info, 1)
        self.stats_box = QHBoxLayout()
        self.stats_box.setSpacing(24)
        banner_layout.addLayout(self.stats_box)
        refresh = QPushButton("刷新")
        refresh.setIcon(icon("refresh", COLORS["muted"], 14))
        refresh.setIconSize(QSize(14, 14))
        refresh.setCursor(Qt.PointingHandCursor)
        refresh.clicked.connect(self.refresh_requested)
        banner_layout.addWidget(refresh)
        root.addWidget(self.banner)
        root.addSpacing(18)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(10)
        search_box = QWidget()
        search_layout = QHBoxLayout(search_box)
        search_layout.setContentsMargins(0, 0, 0, 0)
        self.search = QLineEdit()
        self.search.setPlaceholderText("搜索模组名称、ID 或描述…")
        self.search.setClearButtonEnabled(True)
        self.search.addAction(icon("search", COLORS["dim"], 14), QLineEdit.LeadingPosition)
        self.search.textChanged.connect(self._on_search)
        search_layout.addWidget(self.search)
        search_box.setMaximumWidth(430)
        toolbar.addWidget(search_box, 1)
        self.filter_buttons = []
        filter_box = QFrame()
        filter_box.setStyleSheet("background:rgba(255,255,255,0.025); border:1px solid #1c2a32; border-radius:7px;")
        filter_layout = QHBoxLayout(filter_box)
        filter_layout.setContentsMargins(3, 3, 3, 3)
        filter_layout.setSpacing(2)
        for label, key in (("全部", "all"), ("有配置", "configured"), ("无配置", "empty")):
            button = QPushButton(label)
            button.setObjectName("FilterChip")
            button.setCheckable(True)
            button.setChecked(key == "all")
            button.setCursor(Qt.PointingHandCursor)
            button.clicked.connect(lambda checked, value=key: self._set_filter(value))
            filter_layout.addWidget(button)
            self.filter_buttons.append((key, button))
        self._sync_filter_styles()
        toolbar.addWidget(filter_box)
        toolbar.addStretch(1)
        note = QLabel("配置文件按模组 ID / 文件名自动关联")
        note.setObjectName("Mono")
        toolbar.addWidget(note)
        root.addLayout(toolbar)
        root.addSpacing(13)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        content = QWidget()
        self.scroll.setWidget(content)
        self.grid = QGridLayout(content)
        self.grid.setContentsMargins(0, 0, 0, 12)
        self.grid.setHorizontalSpacing(11)
        self.grid.setVerticalSpacing(11)
        root.addWidget(self.scroll, 1)

        self.empty = QLabel("没有符合条件的模组。试试清空搜索，或切换筛选条件。")
        self.empty.setAlignment(Qt.AlignCenter)
        self.empty.setStyleSheet("color:#5f7068; border:1px dashed #2b3e43; border-radius:10px; padding:34px;")
        self.empty.hide()
        root.addWidget(self.empty)

    def _on_search(self, text: str) -> None:
        self._query = text.strip().lower()
        self._debounce.start()

    def _set_filter(self, value: str) -> None:
        self._filter = value
        for key, button in self.filter_buttons:
            button.setChecked(key == value)
        self._sync_filter_styles()
        self._rebuild_grid()

    def _sync_filter_styles(self) -> None:
        for key, button in self.filter_buttons:
            if key == self._filter:
                button.setStyleSheet(
                    "QPushButton { color:#76e6b4; background:rgba(118,230,180,0.10);"
                    " border:none; border-radius:6px; padding:5px 10px; font-size:8.5pt; }"
                )
            else:
                button.setStyleSheet("")

    def set_data(self, data: Dict) -> None:
        self._data = data
        version = data.get("version") or {}
        self.crumb_current.setText(str(version.get("name") or ""))
        self.version_name.setText(str(version.get("name") or ""))
        while self.version_chips.count():
            item = self.version_chips.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        game = QLabel(str(version.get("game_version") or "未知"))
        game.setStyleSheet(chip_style("blue"))
        self.version_chips.addWidget(game)
        loader = QLabel(str(version.get("loader") or "未知"))
        loader.setStyleSheet(chip_style(loader_variant(str(version.get("loader") or ""))))
        self.version_chips.addWidget(loader)
        if (data.get("stats") or {}).get("disabled_mods"):
            disabled = QLabel(f"{data['stats']['disabled_mods']} 个模组已禁用")
            disabled.setStyleSheet(chip_style("amber"))
            self.version_chips.addWidget(disabled)
        self.version_chips.addStretch(1)
        while self.stats_box.count():
            item = self.stats_box.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                clear_layout(item.layout())
        stats = data.get("stats") or {}
        for number, label in (
            (stats.get("mods", 0), "模组"),
            (stats.get("configs", 0), "配置"),
            (stats.get("orphan_configs", 0), "未归属"),
        ):
            box = QVBoxLayout()
            box.setSpacing(0)
            num = QLabel(str(number))
            num.setObjectName("StatNum")
            lab = QLabel(label)
            lab.setObjectName("StatLabel")
            box.addWidget(num)
            box.addWidget(lab)
            self.stats_box.addLayout(box)
        if hasattr(self, "_version_pixmap") and self._version_pixmap:
            self.version_icon.set_pixmap(self._version_pixmap)
        self._rebuild_grid()

    def set_version_icon(self, pixmap: Optional[QPixmap]) -> None:
        self._version_pixmap = pixmap
        self.version_icon.set_pixmap(pixmap)

    def _rebuild_grid(self) -> None:
        if not self._data:
            return
        clear_layout(self.grid)
        self._cards = []
        mods = list(self._data.get("mods") or [])
        query = self._query
        if query:
            mods = [
                mod
                for mod in mods
                if query
                in " ".join(
                    str(mod.get(key) or "")
                    for key in ("name", "id", "description", "filename")
                ).lower()
            ]
        if self._filter == "configured":
            mods = [mod for mod in mods if (mod.get("config_count") or 0) > 0]
        elif self._filter == "empty":
            mods = [mod for mod in mods if not (mod.get("config_count") or 0)]
        if not query and self._filter == "all":
            mods.sort(key=lambda mod: (1 if mod.get("is_virtual") else 0, str(mod.get("name") or "").lower()))
        version_id = str((self._data.get("version") or {}).get("id") or "")
        for index, mod in enumerate(mods):
            card = ModCard(mod)
            card.clicked.connect(self.mod_selected)
            pixmap = self._icon_cache_get(version_id, mod.get("key", ""))
            if pixmap:
                card.set_icon(pixmap)
            elif mod.get("icon") and mod.get("key") != "__other__":
                self._icon_requester(version_id, mod["key"], lambda pm, c=card: c.set_icon(pm) if pm else None)
            row, col = divmod(index, 2)
            self.grid.addWidget(card, row, col)
            self._cards.append(card)
        self.grid.setColumnStretch(0, 1)
        self.grid.setColumnStretch(1, 1)
        self.grid.setRowStretch(len(mods) // 2 + 1, 1)
        self.empty.setVisible(not mods)
        self.scroll.setVisible(bool(mods))
        if not mods:
            self.empty.show()
        else:
            self.empty.hide()
        if hasattr(self, "_icon_cache"):
            pass

    def _icon_cache_get(self, version: str, key: str):
        parent = self.window()
        cache = getattr(parent, "icon_cache", None)
        if cache:
            return cache.get(("mod", version, key))
        return None

    def focus_search(self) -> None:
        self.search.setFocus()
        self.search.selectAll()


class EditorPage(BasePage):
    back_requested = pyqtSignal()
    refresh_requested = pyqtSignal()
    reveal_mod_requested = pyqtSignal()
    open_file_requested = pyqtSignal(str)
    save_requested = pyqtSignal()
    reload_requested = pyqtSignal()
    reveal_file_requested = pyqtSignal()

    def __init__(self, icon_requester: ModIconRequester, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._icon_requester = icon_requester
        self._mod_data: Optional[Dict] = None
        self._config: Optional[Dict] = None
        self._active_file: Optional[str] = None
        self._changes: Dict[str, Any] = {}
        self._errors: Dict[str, str] = {}
        self._rows: Dict[str, FieldRow] = {}
        self._field_limit = 400
        self._field_query = ""
        self._only_dirty = False
        self._raw_mode = False
        self._raw_text = ""
        self._raw_dirty = False
        self._loading_raw = False
        self._selecting_file = False
        self._file_query = ""
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(100)
        self._debounce.timeout.connect(self._rebuild_fields)
        self._build()

    # ------------------------------------------------------------------ UI
    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(38, 20, 38, 16)
        root.setSpacing(0)
        crumb = QHBoxLayout()
        crumb.setSpacing(8)
        back = QPushButton("版本库")
        back.setObjectName("Ghost")
        back.clicked.connect(self.back_requested)
        crumb.addWidget(back)
        sep = QLabel("/")
        sep.setStyleSheet("color:#3f4d47;")
        crumb.addWidget(sep)
        self.crumb_version = QPushButton("")
        self.crumb_version.setObjectName("Ghost")
        self.crumb_version.clicked.connect(self.back_requested)
        crumb.addWidget(self.crumb_version)
        sep2 = QLabel("/")
        sep2.setStyleSheet("color:#3f4d47;")
        crumb.addWidget(sep2)
        self.crumb_mod = QLabel("")
        self.crumb_mod.setObjectName("Muted")
        crumb.addWidget(self.crumb_mod)
        crumb.addStretch(1)
        back2 = QPushButton("返回模组列表")
        back2.setObjectName("Ghost")
        back2.setIcon(icon("back", COLORS["muted"], 14))
        back2.setIconSize(QSize(14, 14))
        back2.clicked.connect(self.back_requested)
        crumb.addWidget(back2)
        root.addLayout(crumb)
        root.addSpacing(15)

        self.hero = QFrame()
        self.hero.setObjectName("Banner")
        hero_layout = QHBoxLayout(self.hero)
        hero_layout.setContentsMargins(20, 16, 20, 16)
        hero_layout.setSpacing(16)
        self.mod_icon = IconTile(62, 15, "?")
        hero_layout.addWidget(self.mod_icon)
        hero_info = QVBoxLayout()
        hero_info.setSpacing(7)
        self.mod_title = QLabel("")
        self.mod_title.setObjectName("SectionTitle")
        hero_info.addWidget(self.mod_title)
        self.mod_meta = QHBoxLayout()
        self.mod_meta.setSpacing(6)
        hero_info.addLayout(self.mod_meta)
        hero_layout.addLayout(hero_info, 1)
        reveal_mod = QPushButton("配置目录")
        reveal_mod.setIcon(icon("folder", COLORS["muted"], 14))
        reveal_mod.setIconSize(QSize(14, 14))
        reveal_mod.clicked.connect(self.reveal_mod_requested)
        hero_layout.addWidget(reveal_mod)
        refresh = QPushButton("刷新")
        refresh.setIcon(icon("refresh", COLORS["muted"], 14))
        refresh.setIconSize(QSize(14, 14))
        refresh.clicked.connect(self.refresh_requested)
        hero_layout.addWidget(refresh)
        root.addWidget(self.hero)
        root.addSpacing(16)

        body = QHBoxLayout()
        body.setSpacing(16)
        root.addLayout(body, 1)

        self.file_panel = QFrame()
        self.file_panel.setObjectName("FilePanel")
        self.file_panel.setFixedWidth(274)
        file_layout = QVBoxLayout(self.file_panel)
        file_layout.setContentsMargins(12, 12, 12, 10)
        file_layout.setSpacing(9)
        header = QHBoxLayout()
        heading = QLabel("配置文件")
        heading.setObjectName("GroupTitle")
        header.addWidget(heading)
        header.addStretch(1)
        self.file_count = QLabel("0")
        self.file_count.setObjectName("GroupCount")
        header.addWidget(self.file_count)
        file_layout.addLayout(header)
        self.file_search = QLineEdit()
        self.file_search.setPlaceholderText("筛选文件…")
        self.file_search.setClearButtonEnabled(True)
        self.file_search.addAction(icon("search", COLORS["dim"], 13), QLineEdit.LeadingPosition)
        self.file_search.textChanged.connect(self._on_file_search)
        file_layout.addWidget(self.file_search)
        self.file_list = QListWidget()
        self.file_list.setObjectName("FileList")
        self.file_list.setItemDelegate(FileDelegate(self.file_list))
        self.file_list.setMouseTracking(True)
        self.file_list.currentItemChanged.connect(self._on_file_changed)
        file_layout.addWidget(self.file_list, 1)
        body.addWidget(self.file_panel)

        right = QVBoxLayout()
        right.setSpacing(9)
        self.toolbar_holder = QVBoxLayout()
        self.toolbar_holder.setSpacing(9)
        right.addLayout(self.toolbar_holder)
        self.warn = QFrame()
        self.warn.setObjectName("WarnBanner")
        warn_layout = QHBoxLayout(self.warn)
        warn_layout.setContentsMargins(11, 9, 11, 9)
        warn_layout.setSpacing(8)
        warn_icon = QLabel()
        warn_icon.setPixmap(icon("alert", COLORS["amber"], 15).pixmap(15, 15))
        warn_icon.setFixedWidth(16)
        warn_layout.addWidget(warn_icon, 0, Qt.AlignTop)
        self.warn_text = QLabel("")
        self.warn_text.setObjectName("Warn")
        self.warn_text.setWordWrap(True)
        warn_layout.addWidget(self.warn_text, 1)
        self.warn.hide()
        right.addWidget(self.warn)

        param_bar = QHBoxLayout()
        param_bar.setSpacing(10)
        self.param_search = QLineEdit()
        self.param_search.setPlaceholderText("筛选参数、说明…")
        self.param_search.setClearButtonEnabled(True)
        self.param_search.addAction(icon("search", COLORS["dim"], 14), QLineEdit.LeadingPosition)
        self.param_search.setMaximumWidth(310)
        self.param_search.textChanged.connect(self._on_field_search)
        param_bar.addWidget(self.param_search)
        self.only_dirty = QCheckBox("只看已修改")
        self.only_dirty.toggled.connect(self._on_only_dirty)
        param_bar.addWidget(self.only_dirty)
        param_bar.addStretch(1)
        self.param_count = QLabel("")
        self.param_count.setObjectName("Mono")
        param_bar.addWidget(self.param_count)
        right.addLayout(param_bar)

        self.field_scroll = QScrollArea()
        self.field_scroll.setWidgetResizable(True)
        self.field_scroll.setFrameShape(QFrame.NoFrame)
        self.field_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.field_content = QWidget()
        self.field_scroll.setWidget(self.field_content)
        self.field_layout = QVBoxLayout(self.field_content)
        self.field_layout.setContentsMargins(0, 0, 4, 8)
        self.field_layout.setSpacing(9)
        right.addWidget(self.field_scroll, 1)

        self.save_dock = QFrame()
        self.save_dock.setObjectName("SaveDock")
        save_layout = QHBoxLayout(self.save_dock)
        save_layout.setContentsMargins(15, 9, 10, 9)
        save_layout.setSpacing(10)
        save_info = QVBoxLayout()
        save_info.setSpacing(0)
        self.dirty_label = QLabel("0 项未保存的修改")
        self.dirty_label.setStyleSheet("font-size:9.5pt; font-weight:bold; color:#c2d0c9;")
        save_info.addWidget(self.dirty_label)
        self.save_hint = QLabel("保存时会自动备份原文件")
        self.save_hint.setObjectName("Mono")
        save_info.addWidget(self.save_hint)
        save_layout.addLayout(save_info)
        save_layout.addStretch(1)
        discard = QPushButton("撤销全部")
        discard.setIcon(icon("undo", COLORS["muted"], 14))
        discard.setIconSize(QSize(14, 14))
        discard.clicked.connect(self.discard_changes)
        save_layout.addWidget(discard)
        self.save_button = QPushButton("保存到文件")
        self.save_button.setObjectName("Primary")
        self.save_button.setIcon(icon("save", "#062417", 14))
        self.save_button.setIconSize(QSize(14, 14))
        self.save_button.clicked.connect(self.save_requested)
        save_layout.addWidget(self.save_button)
        self.save_dock.hide()
        right.addWidget(self.save_dock)

        body.addLayout(right, 1)

    # ------------------------------------------------------------------ data
    def set_mod(self, data: Dict) -> None:
        self._mod_data = data
        self._config = None
        self._active_file = None
        self._changes.clear()
        self._errors.clear()
        self._rows.clear()
        self._mod_pixmap = None
        self._raw_mode = False
        self._raw_dirty = False
        self._raw_text = ""
        self._field_limit = 400
        self._field_query = ""
        self._only_dirty = False
        self.param_search.blockSignals(True)
        self.param_search.clear()
        self.param_search.blockSignals(False)
        self.only_dirty.blockSignals(True)
        self.only_dirty.setChecked(False)
        self.only_dirty.blockSignals(False)
        version = data.get("version") or {}
        mod = data.get("mod") or {}
        self.crumb_version.setText(str(version.get("name") or ""))
        self.crumb_mod.setText(str(mod.get("name") or ""))
        self.mod_title.setText(str(mod.get("name") or "未命名模组"))
        self.mod_icon.set_text(str(mod.get("name") or "?"))
        self.mod_icon.set_pixmap(None)
        if hasattr(self, "_mod_pixmap") and self._mod_pixmap:
            self.mod_icon.set_pixmap(self._mod_pixmap)
        elif mod.get("icon") and mod.get("key") and mod.get("key") != "__other__":
            version_id = str(version.get("id") or "")
            self._icon_requester(version_id, mod["key"], lambda pm: self.mod_icon.set_pixmap(pm) if pm else None)
        while self.mod_meta.count():
            item = self.mod_meta.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        if not data.get("is_virtual"):
            ident = QLabel(str(mod.get("id") or "unknown"))
            ident.setStyleSheet(chip_style(""))
            self.mod_meta.addWidget(ident)
        if mod.get("version"):
            ver = QLabel(f"v{mod['version']}")
            ver.setStyleSheet(chip_style(""))
            self.mod_meta.addWidget(ver)
        if data.get("is_virtual"):
            virtual = QLabel("未归属配置")
            virtual.setStyleSheet(chip_style("amber"))
            self.mod_meta.addWidget(virtual)
        else:
            fmt = QLabel(str(mod.get("format") or "unknown"))
            fmt.setStyleSheet(chip_style("mint" if str(mod.get("format")) == "fabric" else "amber"))
            self.mod_meta.addWidget(fmt)
        count_label = QLabel(f"{len(data.get('configs') or [])} 个配置文件")
        count_label.setStyleSheet("color:#5f7068; font-size:8.5pt;")
        self.mod_meta.addWidget(count_label)
        total = data.get("total_fields")
        if total:
            total_label = QLabel(f"约 {total} 个参数")
            total_label.setStyleSheet("color:#5f7068; font-size:8.5pt;")
            self.mod_meta.addWidget(total_label)
        self.mod_meta.addStretch(1)
        self._populate_file_list()

    def set_mod_icon(self, pixmap: QPixmap) -> None:
        self._mod_pixmap = pixmap
        self.mod_icon.set_pixmap(pixmap)

    def _populate_file_list(self) -> None:
        self._selecting_file = True
        self.file_list.clear()
        configs = (self._mod_data or {}).get("configs") or []
        for item in configs:
            entry = {
                "name": item.get("name") or item.get("path"),
                "path": item.get("path") or "",
                "format": item.get("format_label") or item.get("format") or "",
                "field_count": item.get("field_count"),
                "warning": bool(item.get("warnings")),
            }
            list_item = QListWidgetItem()
            list_item.setData(Qt.UserRole, entry)
            list_item.setSizeHint(QSize(180, 56))
            list_item.setToolTip(str(item.get("path") or ""))
            self.file_list.addItem(list_item)
        self.file_count.setText(str(len(configs)))
        self._selecting_file = False
        self._apply_file_filter()

    def _apply_file_filter(self) -> None:
        query = self._file_query.lower()
        for index in range(self.file_list.count()):
            item = self.file_list.item(index)
            entry = item.data(Qt.UserRole) or {}
            text = f"{entry.get('name')} {entry.get('path')} {entry.get('format')}".lower()
            item.setHidden(bool(query) and query not in text)

    def _on_file_search(self, text: str) -> None:
        self._file_query = text.strip()
        self._apply_file_filter()

    def _on_file_changed(self, current: Optional[QListWidgetItem], previous: Optional[QListWidgetItem]) -> None:
        if self._selecting_file or current is None:
            return
        entry = current.data(Qt.UserRole) or {}
        path = entry.get("path")
        if path and path != self._active_file:
            self.open_file_requested.emit(path)

    def select_file(self, path: str) -> None:
        self._selecting_file = True
        for index in range(self.file_list.count()):
            item = self.file_list.item(index)
            if (item.data(Qt.UserRole) or {}).get("path") == path:
                self.file_list.setCurrentItem(item)
                self.file_list.scrollToItem(item, QListWidget.PositionAtCenter)
                break
        self._selecting_file = False

    def current_file(self) -> Optional[str]:
        return self._active_file

    # ---------------------------------------------------------------- config
    def set_config(self, config: Dict) -> None:
        self._config = config
        self._active_file = config.get("file", {}).get("path")
        self._changes.clear()
        self._errors.clear()
        self._rows.clear()
        self._raw_mode = bool(config.get("raw_only")) or (
            not (config.get("fields") or [])
            and str(config.get("format")) in ("text", "snbt", "xml")
        )
        self._raw_text = config.get("raw") or ""
        self._raw_dirty = False
        self._field_limit = 400
        self._field_query = ""
        self._only_dirty = False
        self.param_search.blockSignals(True)
        self.param_search.clear()
        self.param_search.blockSignals(False)
        self.only_dirty.blockSignals(True)
        self.only_dirty.setChecked(False)
        self.only_dirty.blockSignals(False)
        self.select_file(self._active_file or "")
        self._update_file_item()
        self._build_toolbar()
        self._build_warnings()
        self._build_config_view()

    def _update_file_item(self) -> None:
        for index in range(self.file_list.count()):
            item = self.file_list.item(index)
            entry = item.data(Qt.UserRole)
            if entry and entry.get("path") == self._active_file:
                entry["field_count"] = len((self._config or {}).get("fields") or [])
                entry["warning"] = bool((self._config or {}).get("warnings"))
                item.setData(Qt.UserRole, entry)
                break

    def _build_toolbar(self) -> None:
        clear_layout(self.toolbar_holder)
        if not self._config:
            return
        file_info = self._config.get("file") or {}
        bar = QFrame()
        bar.setObjectName("ConfigToolbar")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(16, 12, 12, 12)
        layout.setSpacing(10)
        info = QVBoxLayout()
        info.setSpacing(4)
        name_row = QHBoxLayout()
        name_row.setSpacing(8)
        file_icon = QLabel()
        file_icon.setPixmap(icon("file", COLORS["mint"], 15).pixmap(15, 15))
        name_row.addWidget(file_icon)
        name = QLabel(str(file_info.get("name") or "配置文件"))
        name.setStyleSheet("font-size:10.5pt; font-weight:bold;")
        name_row.addWidget(name)
        fmt = QLabel(str(self._config.get("format_label") or self._config.get("format") or ""))
        fmt.setStyleSheet(chip_style(format_variant(str(self._config.get("format") or ""))))
        name_row.addWidget(fmt)
        name_row.addStretch(1)
        info.addLayout(name_row)
        path = QLabel(str(file_info.get("path") or ""))
        path.setObjectName("Mono")
        path.setToolTip(path.text())
        info.addWidget(path)
        meta = QHBoxLayout()
        meta.setSpacing(6)
        fields = len(self._config.get("fields") or [])
        meta_count = QLabel(f"{fields} 个参数")
        meta_count.setStyleSheet(chip_style("mint"))
        meta.addWidget(meta_count)
        encoding = QLabel(str(self._config.get("encoding") or ""))
        encoding.setStyleSheet(chip_style(""))
        meta.addWidget(encoding)
        if self._config.get("has_bom"):
            bom = QLabel("BOM")
            bom.setStyleSheet(chip_style("amber"))
            meta.addWidget(bom)
        meta.addStretch(1)
        info.addLayout(meta)
        layout.addLayout(info, 1)
        source = QPushButton("参数视图" if self._raw_mode else "源码模式")
        source.setIcon(icon("code", COLORS["muted"], 14))
        source.setIconSize(QSize(14, 14))
        source.clicked.connect(self.toggle_raw)
        layout.addWidget(source)
        reveal = QPushButton("打开位置")
        reveal.setIcon(icon("external", COLORS["muted"], 14))
        reveal.setIconSize(QSize(14, 14))
        reveal.clicked.connect(self.reveal_file_requested)
        layout.addWidget(reveal)
        reload_button = QPushButton("重新载入")
        reload_button.setIcon(icon("refresh", COLORS["muted"], 14))
        reload_button.setIconSize(QSize(14, 14))
        reload_button.clicked.connect(self.reload_requested)
        layout.addWidget(reload_button)
        self.toolbar_holder.addWidget(bar)

    def _build_warnings(self) -> None:
        warnings = (self._config or {}).get("warnings") or []
        if not warnings:
            self.warn.hide()
            return
        text = "解析时发现 %d 条提示，修改前建议先备份。<br>" % len(warnings)
        text += "<br>".join(str(item) for item in warnings[:3])
        self.warn_text.setText(text)
        self.warn.show()

    def _build_config_view(self) -> None:
        clear_layout(self.field_layout)
        self._rows.clear()
        if self._raw_mode:
            self._build_raw_view()
            self._update_dirty_ui()
            return
        fields = (self._config or {}).get("fields") or []
        if not fields:
            empty = QFrame()
            empty.setObjectName("Empty")
            layout = QVBoxLayout(empty)
            layout.setContentsMargins(24, 44, 24, 44)
            layout.setSpacing(8)
            title = QLabel("没有识别到结构化参数")
            title.setAlignment(Qt.AlignCenter)
            title.setStyleSheet("font-size:11pt; font-weight:bold;")
            layout.addWidget(title)
            desc = QLabel("这个文件可能是特殊格式。切换到源码模式，仍然可以安全地编辑原始内容。")
            desc.setAlignment(Qt.AlignCenter)
            desc.setWordWrap(True)
            desc.setStyleSheet("color:#5f7068; font-size:9pt;")
            layout.addWidget(desc)
            buttons = QHBoxLayout()
            buttons.addStretch(1)
            source = QPushButton("源码模式")
            source.setObjectName("Primary")
            source.clicked.connect(self.toggle_raw)
            buttons.addWidget(source)
            buttons.addStretch(1)
            layout.addLayout(buttons)
            self.field_layout.addWidget(empty)
            self.field_layout.addStretch(1)
            self._update_param_count(0, 0)
            self._update_dirty_ui()
            return
        self._rebuild_fields()

    def _rebuild_fields(self) -> None:
        if not self._config or self._raw_mode:
            return
        clear_layout(self.field_layout)
        self._rows.clear()
        fields = (self._config or {}).get("fields") or []
        query = self._field_query.lower()
        filtered = []
        for field in fields:
            if self._only_dirty and field.get("path") not in self._changes:
                continue
            if query:
                hay = " ".join(
                    str(field.get(key) or "")
                    for key in ("key", "label", "section", "description", "value")
                ).lower()
                if query not in hay:
                    continue
            filtered.append(field)
        visible = filtered[: self._field_limit]
        groups: Dict[str, List[Dict]] = {}
        order: List[str] = []
        for field in visible:
            section = str(field.get("section") or "基础参数")
            if section not in groups:
                groups[section] = []
                order.append(section)
            groups[section].append(field)
        for section in order:
            group = GroupCard(section, len(groups[section]))
            for field in groups[section]:
                row = FieldRow(field)
                row.changed.connect(self._on_field_changed)
                if field.get("path") in self._changes:
                    row.set_value_silent(self._changes[field["path"]])
                    row.set_dirty(True)
                if field.get("path") in self._errors:
                    row.error_label.setText(self._errors[field["path"]])
                    row.error_label.show()
                group.add_row(row)
                self._rows[field["path"]] = row
            self.field_layout.addWidget(group)
        if len(filtered) > len(visible):
            more = QFrame()
            more.setStyleSheet("border:1px dashed #2b3e43; border-radius:9px;")
            more_layout = QHBoxLayout(more)
            more_layout.setContentsMargins(14, 10, 14, 10)
            label = QLabel(f"已显示 {len(visible)} / {len(filtered)} 个参数")
            label.setObjectName("Mono")
            more_layout.addWidget(label)
            more_layout.addStretch(1)
            button = QPushButton("再显示 400 个")
            button.setIcon(icon("chevron", COLORS["muted"], 13))
            button.setIconSize(QSize(13, 13))
            button.clicked.connect(self._show_more)
            more_layout.addWidget(button)
            self.field_layout.addWidget(more)
        if not visible:
            no_match = QLabel("没有匹配的参数。")
            no_match.setAlignment(Qt.AlignCenter)
            no_match.setStyleSheet("color:#5f7068; border:1px dashed #2b3e43; border-radius:10px; padding:30px;")
            self.field_layout.addWidget(no_match)
        self.field_layout.addStretch(1)
        self._update_param_count(len(filtered), len(groups))
        self._update_dirty_ui()

    def _build_raw_view(self) -> None:
        raw = QPlainTextEdit()
        raw.setPlainText(self._raw_text)
        raw.setLineWrapMode(QPlainTextEdit.NoWrap)
        font = QFont("Cascadia Code")
        font.setStyleHint(QFont.Monospace)
        font.setPointSizeF(9.5)
        raw.setFont(font)
        raw.setStyleSheet(
            "QPlainTextEdit { background:#090f13; border:1px solid #1c2a32; border-radius:10px;"
            " padding:12px; color:#c8ddd2; selection-background-color:#2b6e55; }"
        )
        raw.textChanged.connect(self._on_raw_changed)
        self.raw_editor = raw
        self.field_layout.addWidget(raw)
        self.field_layout.addStretch(1)
        self._update_param_count(0, 0)

    def _on_raw_changed(self) -> None:
        if self._loading_raw:
            return
        self._raw_text = self.raw_editor.toPlainText()
        self._raw_dirty = self._raw_text != (self._config or {}).get("raw", "")
        self._update_dirty_ui()

    def _show_more(self) -> None:
        self._field_limit += 400
        self._rebuild_fields()

    def _on_field_search(self, text: str) -> None:
        self._field_query = text.strip()
        self._debounce.start()

    def _on_only_dirty(self, checked: bool) -> None:
        self._only_dirty = bool(checked)
        self._debounce.start()

    def _on_field_changed(self, path: str, value: Any, valid: bool, error: str) -> None:
        fields = {field.get("path"): field for field in (self._config or {}).get("fields") or []}
        field = fields.get(path)
        if field is None:
            return
        if not valid:
            self._errors[path] = error
            self._changes.pop(path, None)
        else:
            self._errors.pop(path, None)
            if deep_equal(value, field.get("value")):
                self._changes.pop(path, None)
            else:
                self._changes[path] = value
        row = self._rows.get(path)
        if row is not None:
            row.set_dirty(path in self._changes)
        self._update_dirty_ui()

    def _update_param_count(self, visible: int, groups: int) -> None:
        total = len((self._config or {}).get("fields") or [])
        self.param_count.setText(f"{visible} / {total} 个参数" + (f" · {groups} 组" if groups else ""))

    def _update_dirty_ui(self) -> None:
        count = self.dirty_count()
        self.save_dock.setVisible(count > 0 or bool(self._errors))
        self.dirty_label.setText(f"{count} 项未保存的修改")
        if self._errors:
            self.save_hint.setText(f"有 {len(self._errors)} 个输入无效，修正后才能保存")
        else:
            self.save_hint.setText("保存时会自动备份原文件")
        self.save_dock.setProperty("error", "true" if self._errors else "false")
        self.save_dock.style().unpolish(self.save_dock)
        self.save_dock.style().polish(self.save_dock)
        self.save_button.setEnabled(not self._errors and count > 0)
        self.save_button.setText("保存到文件")

    # --------------------------------------------------------------- actions
    def dirty_count(self) -> int:
        return 1 if self._raw_mode and self._raw_dirty else 0 if self._raw_mode else len(self._changes)

    def is_dirty(self) -> bool:
        return self.dirty_count() > 0

    def clear_changes(self) -> None:
        self._changes.clear()
        self._errors.clear()
        self._raw_dirty = False
        self._raw_text = (self._config or {}).get("raw", "")
        if self._raw_mode and hasattr(self, "raw_editor"):
            self._loading_raw = True
            self.raw_editor.setPlainText(self._raw_text)
            self._loading_raw = False
        else:
            self._rebuild_fields()
        self._update_dirty_ui()

    def discard_changes(self) -> None:
        self._changes.clear()
        self._errors.clear()
        self._raw_dirty = False
        self._raw_text = (self._config or {}).get("raw", "")
        self._build_config_view()
        self._update_dirty_ui()

    def toggle_raw(self) -> None:
        if not self._config:
            return
        if not self._raw_mode:
            if self.is_dirty():
                if not self._confirm_discard("切换到源码模式会丢弃当前尚未保存的参数修改。"):
                    return
            self._raw_mode = True
            self._raw_text = self._config.get("raw", "")
            self._raw_dirty = False
            self._changes.clear()
            self._errors.clear()
            self._build_toolbar()
            self._build_config_view()
        else:
            if self._raw_dirty:
                if not self._confirm_discard("源码修改尚未保存，切换回参数视图会丢弃这些修改。"):
                    return
            self._raw_mode = False
            self._raw_dirty = False
            self._raw_text = self._config.get("raw", "")
            self._build_toolbar()
            self._build_config_view()

    def _confirm_discard(self, message: str) -> bool:
        box = QMessageBox(self)
        box.setWindowTitle("放弃未保存的修改？")
        box.setText(message)
        box.setIcon(QMessageBox.Warning)
        box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        box.button(QMessageBox.Yes).setText("放弃并继续")
        box.button(QMessageBox.No).setText("取消")
        return box.exec_() == QMessageBox.Yes

    def build_save_payload(self) -> Optional[Dict]:
        if not self._config or not self._mod_data:
            return None
        version = self._mod_data.get("version") or {}
        mod = self._mod_data.get("mod") or {}
        payload = {
            "version": version.get("id"),
            "key": mod.get("key"),
            "file": self._config.get("file", {}).get("path"),
            "hash": self._config.get("hash"),
        }
        if self._raw_mode:
            payload["raw"] = self._raw_text
        else:
            payload["changes"] = [{"path": path, "value": value} for path, value in self._changes.items()]
        return payload

    def apply_saved(self, result: Dict) -> None:
        if not self._config:
            return
        fields = result.get("fields")
        if fields is not None:
            self._config["fields"] = fields
        if result.get("raw") is not None:
            self._config["raw"] = result["raw"]
            self._raw_text = result["raw"]
        self._config["hash"] = result.get("hash") or self._config.get("hash")
        self._config["warnings"] = result.get("warnings") or []
        self._config["size"] = result.get("size") or self._config.get("size")
        self._config["size_label"] = result.get("size_label") or self._config.get("size_label")
        self._config["line_count"] = result.get("line_count") or self._config.get("line_count")
        self._config["format"] = result.get("format") or self._config.get("format")
        self._config["format_label"] = result.get("format_label") or self._config.get("format_label")
        self._changes.clear()
        self._errors.clear()
        self._raw_dirty = False
        self._update_file_item()
        self._build_toolbar()
        self._build_warnings()
        if self._raw_mode:
            self._build_config_view()
        else:
            self._rebuild_fields()
        self._update_dirty_ui()

    def current_hash(self) -> str:
        return str((self._config or {}).get("hash") or "")

    def set_saving(self, saving: bool) -> None:
        if saving:
            self.save_button.setEnabled(False)
            self.save_button.setText("保存中…")
        else:
            self.save_button.setText("保存到文件")
            self.save_button.setEnabled(not self._errors and self.dirty_count() > 0)

    def focus_params(self) -> None:
        self.param_search.setFocus()
        self.param_search.selectAll()
