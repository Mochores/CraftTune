from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional

from PyQt5.QtCore import QByteArray, QSize, Qt
from PyQt5.QtGui import QColor, QIcon, QPainter, QPixmap
from PyQt5.QtSvg import QSvgRenderer


APP_ROOT = Path(__file__).resolve().parent.parent
ASSETS = APP_ROOT / "assets"

COLORS = {
    "bg": "#080d11",
    "bg_soft": "#0b1218",
    "panel": "#0f171e",
    "panel_2": "#121c24",
    "panel_3": "#17232c",
    "line": "#1c2a32",
    "line_strong": "#2b3e43",
    "text": "#e9f2ec",
    "text_soft": "#c2d0c9",
    "muted": "#8d9e96",
    "dim": "#5f7068",
    "mint": "#76e6b4",
    "mint_deep": "#35c98c",
    "amber": "#edb668",
    "red": "#ff8585",
    "blue": "#7eb9ff",
    "violet": "#b9a4ff",
}

SVG_ICONS: Dict[str, str] = {
    "cube": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"><path d="M12 2.6 21 7.4v9.2L12 21.4 3 16.6V7.4L12 2.6Z"/><path d="m3.4 7.6 8.6 4.7 8.6-4.7M12 12.3v8.6" opacity=".55"/><path d="m7.3 5 8.7 4.8v4.1" opacity=".45"/></svg>""",
    "grid": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><rect x="3.5" y="3.5" width="7" height="7" rx="1.5"/><rect x="13.5" y="3.5" width="7" height="7" rx="1.5"/><rect x="3.5" y="13.5" width="7" height="7" rx="1.5"/><rect x="13.5" y="13.5" width="7" height="7" rx="1.5"/></svg>""",
    "home": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"><path d="m3.5 10.5 8.5-7 8.5 7V20a1 1 0 0 1-1 1h-5v-6h-5v6h-5a1 1 0 0 1-1-1v-9.5Z"/></svg>""",
    "info": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><circle cx="12" cy="12" r="9"/><path d="M12 11v5.5" stroke-linecap="round"/><circle cx="12" cy="7.8" r="1.1" fill="currentColor" stroke="none"/></svg>""",
    "save": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"><path d="M5 3.8h11.2L20 7.6v12.2a1.4 1.4 0 0 1-1.4 1.4H5a1.4 1.4 0 0 1-1.4-1.4V5.2A1.4 1.4 0 0 1 5 3.8Z"/><path d="M8 3.8v5h7v-5M8 21v-7h8v7"/></svg>""",
    "folder": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"><path d="M3.5 7.5a2 2 0 0 1 2-2h4l2 2h7a2 2 0 0 1 2 2v8.5a2 2 0 0 1-2 2h-13a2 2 0 0 1-2-2V7.5Z"/></svg>""",
    "refresh": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M20 7v5h-5M4 17v-5h5"/><path d="M18.2 16.1A7.5 7.5 0 0 1 5.5 15M5.8 7.9A7.5 7.5 0 0 1 18.5 9"/></svg>""",
    "back": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M19 12H5m6-6-6 6 6 6"/></svg>""",
    "forward": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14m-6-6 6 6-6 6"/></svg>""",
    "search": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><circle cx="10.7" cy="10.7" r="6.2"/><path d="m15.4 15.4 4.1 4.1" stroke-linecap="round"/></svg>""",
    "code": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="m8 6-5 6 5 6m8-12 5 6-5 6"/></svg>""",
    "external": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M14 4h6v6M20 4l-9 9"/><path d="M19 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1h5"/></svg>""",
    "sliders": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"><path d="M4 6h7m4 0h5M4 12h3m4 0h9M4 18h10m4 0h2"/><circle cx="8" cy="12" r="2.2"/><circle cx="13" cy="6" r="2.2"/><circle cx="16" cy="18" r="2.2"/></svg>""",
    "alert": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"><path d="M12 3.2 21.2 20H2.8L12 3.2Z"/><path d="M12 9v5" stroke-linecap="round"/><circle cx="12" cy="17.1" r="1" fill="currentColor" stroke="none"/></svg>""",
    "check": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m4.5 12.5 5 5 10-11"/></svg>""",
    "close": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><path d="m6 6 12 12M18 6 6 18"/></svg>""",
    "chevron": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="m8 5 7 7-7 7"/></svg>""",
    "undo": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="m9 7-5 5 5 5M4 12h9a6 6 0 0 1 6 6"/></svg>""",
    "package": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"><path d="m12 2.8 8.5 4.6v9.2L12 21.2l-8.5-4.6V7.4L12 2.8Z"/><path d="m3.8 7.6 8.2 4.5 8.2-4.5M12 12.1v8.5" opacity=".6"/></svg>""",
    "file": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"><path d="M6 2.8h7.2L19 8.6v12.6H6V2.8Z"/><path d="M13 3v6h6"/></svg>""",
    "spark": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"><path d="m12 2 1.7 6.3L20 10l-6.3 1.7L12 18l-1.7-6.3L4 10l6.3-1.7L12 2Z"/><path d="m19 16 .7 2.3L22 19l-2.3.7L19 22l-.7-2.3L16 19l2.3-.7L19 16Z" fill="currentColor" stroke="none" opacity=".7"/></svg>""",
    "lock": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><rect x="4.5" y="10" width="15" height="11" rx="2"/><path d="M8 10V7.5a4 4 0 0 1 8 0V10" stroke-linecap="round"/></svg>""",
    "play": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor"><path d="M8 4.8 19 12 8 19.2V4.8Z"/></svg>""",
}


def icon(name: str, color: str = COLORS["muted"], size: int = 18) -> QIcon:
    source = SVG_ICONS.get(name)
    if not source:
        return QIcon()
    source = source.replace("currentColor", color)
    renderer = QSvgRenderer(QByteArray(source.encode("utf-8")))
    ratio = 2
    pixmap = QPixmap(size * ratio, size * ratio)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing, True)
    renderer.render(painter)
    painter.end()
    pixmap.setDevicePixelRatio(ratio)
    return QIcon(pixmap)


def pixmap_from_bytes(data: bytes, mime: str = "", size: int = 128) -> QPixmap:
    if mime == "image/svg+xml":
        renderer = QSvgRenderer(QByteArray(data))
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing, True)
        renderer.render(painter)
        painter.end()
        return pixmap
    pixmap = QPixmap()
    if pixmap.loadFromData(data):
        return pixmap
    return QPixmap()


def chip_style(variant: str = "") -> str:
    palette = {
        "": ("#8d9e96", "rgba(255,255,255,0.045)", "rgba(255,255,255,0.07)"),
        "mint": ("#76e6b4", "rgba(118,230,180,0.07)", "rgba(118,230,180,0.14)"),
        "blue": ("#7eb9ff", "rgba(126,185,255,0.07)", "rgba(126,185,255,0.14)"),
        "amber": ("#edb668", "rgba(237,182,104,0.09)", "rgba(237,182,104,0.17)"),
        "violet": ("#b9a4ff", "rgba(185,164,255,0.07)", "rgba(185,164,255,0.14)"),
        "red": ("#ff8585", "rgba(255,133,133,0.08)", "rgba(255,133,133,0.16)"),
    }
    color, bg, border = palette.get(variant, palette[""])
    return (
        "QLabel { color: %s; background: %s; border: 1px solid %s; border-radius: 4px;"
        " padding: 1px 6px; font-family: 'Cascadia Code', 'Consolas'; font-size: 8.5pt; }" % (color, bg, border)
    )


def stylesheet() -> str:
    return r"""
* { outline: none; }
QWidget {
    color: #e9f2ec;
    font-family: "Microsoft YaHei UI", "PingFang SC", "Segoe UI";
    font-size: 10pt;
}
QMainWindow, QWidget#Root { background: #080d11; }
QWidget#MainArea { background: #080d11; }
QStackedWidget { background: transparent; }
QScrollArea { background: transparent; border: none; }
QScrollArea > QWidget > QWidget { background: transparent; }
QScrollArea > QWidget > QScrollBar { background: transparent; }
QLabel { background: transparent; }
QLabel#BrandName { font-size: 15pt; font-weight: bold; letter-spacing: 0.2px; }
QLabel#BrandSub { color: #5f7068; font-family: "Cascadia Code", "Consolas"; font-size: 7.2pt; letter-spacing: 0.7px; }
QLabel#SideLabel { color: #5f7068; font-family: "Cascadia Code", "Consolas"; font-size: 7.5pt; letter-spacing: 1.5px; }
QLabel#Eyebrow { color: #76e6b4; font-family: "Cascadia Code", "Consolas"; font-size: 8pt; letter-spacing: 2.4px; }
QLabel#HeroTitle { font-size: 36px; font-weight: bold; letter-spacing: -1px; line-height: 1.1; }
QLabel#HeroLead { color: #8d9e96; font-size: 10.5pt; line-height: 1.7; }
QLabel#SectionTitle { font-size: 14pt; font-weight: bold; }
QLabel#Muted { color: #8d9e96; }
QLabel#Dim { color: #5f7068; }
QLabel#Path { color: #c2d0c9; font-family: "Cascadia Code", "Consolas"; font-size: 8.5pt; }
QLabel#Mono { font-family: "Cascadia Code", "Consolas"; font-size: 8.5pt; color: #8d9e96; }
QLabel#StatNum { font-family: "Cascadia Code", "Consolas"; font-size: 15pt; color: #e9f2ec; }
QLabel#StatLabel { color: #5f7068; font-size: 7.5pt; }
QLabel#CardTitle { font-size: 12pt; font-weight: bold; }
QLabel#CardId { color: #5f7068; font-family: "Cascadia Code", "Consolas"; font-size: 8pt; }
QLabel#FieldLabel { color: #c2d0c9; font-size: 10pt; font-weight: bold; }
QLabel#FieldKey {
    color: #5f7068; background: rgba(255,255,255,0.035);
    border: 1px solid rgba(255,255,255,0.05); border-radius: 3px;
    padding: 0px 4px; font-family: "Cascadia Code", "Consolas"; font-size: 7.5pt;
}
QLabel#FieldDesc { color: #8d9e96; font-size: 8.5pt; }
QLabel#FieldMeta { color: #5f7068; font-family: "Cascadia Code", "Consolas"; font-size: 7.5pt; }
QLabel#FieldError { color: #ff8585; font-size: 8pt; }
QLabel#GroupTitle { color: #c2d0c9; font-size: 9.5pt; font-weight: bold; }
QLabel#GroupCount { color: #5f7068; font-family: "Cascadia Code", "Consolas"; font-size: 7.5pt; }
QLabel#Warn { color: #dcc094; font-size: 8.5pt; }

QFrame#Sidebar { background: #0b1218; border-right: 1px solid #17232b; }
QFrame#SideVersion {
    background: rgba(118,230,180,0.045);
    border: 1px solid #1c2f2a; border-radius: 10px;
}
QFrame#Tip {
    border: 1px dashed #23332f; border-radius: 9px;
}
QFrame#VersionCard, QFrame#ModCard {
    background: #101920;
    border: 1px solid #1c2a32; border-radius: 13px;
}
QFrame#VersionCard:hover, QFrame#ModCard:hover {
    background: #13202a; border-color: #35624f;
}
QFrame#VersionCard[pressed="true"], QFrame#ModCard[pressed="true"] {
    background: #152530; border-color: #76e6b4;
}
QFrame#ModCard[virtual="true"] {
    background: rgba(36,30,21,0.42);
    border: 1px dashed rgba(237,182,104,0.24);
}
QFrame#ModCard[virtual="true"]:hover {
    background: rgba(44,36,24,0.52);
    border-color: rgba(237,182,104,0.45);
}
QFrame#Banner {
    background: #101a21;
    border: 1px solid #1c2a32; border-radius: 14px;
}
QFrame#LauncherCard {
    background: #0f1920;
    border: 1px solid #1c2a32; border-radius: 12px;
}
QFrame#GroupCard {
    background: #0f181f;
    border: 1px solid #1b2a32; border-radius: 12px;
}
QFrame#FieldRow {
    border-bottom: 1px solid #17252c;
    background: transparent;
}
QFrame#FieldRow:hover { background: rgba(255,255,255,0.015); }
QFrame#FieldRow[dirty="true"] {
    background: rgba(118,230,180,0.035);
    border-left: 2px solid #4ecf98;
}
QFrame#ConfigToolbar {
    background: #101a21;
    border: 1px solid #1c2a32; border-radius: 12px;
}
QFrame#WarnBanner {
    background: rgba(237,182,104,0.06);
    border: 1px solid rgba(237,182,104,0.18); border-radius: 8px;
}
QFrame#SaveDock {
    background: #0e1a1f;
    border: 1px solid #274639; border-radius: 11px;
}
QFrame#SaveDock[error="true"] { border-color: #683b3b; }
QFrame#FilePanel {
    background: #0f171e;
    border: 1px solid #1c2a32; border-radius: 12px;
}
QFrame#Step {
    background: #0d151b;
    border: 1px solid #1c2a32; border-radius: 10px;
}
QFrame#Empty {
    background: rgba(13,21,27,0.60);
    border: 1px dashed #2b3e43; border-radius: 12px;
}
QFrame#Divider { background: #1c2a32; border: none; }

QPushButton {
    background: rgba(255,255,255,0.035);
    border: 1px solid #2b3e43;
    border-radius: 8px;
    color: #c2d0c9;
    padding: 7px 12px;
    min-height: 18px;
}
QPushButton:hover { background: rgba(118,230,180,0.06); border-color: #3f6556; color: #e9f2ec; }
QPushButton:pressed { background: rgba(118,230,180,0.10); }
QPushButton:disabled { color: #5f7068; border-color: #1c2a32; background: rgba(255,255,255,0.02); }
QPushButton#Primary {
    background: #6fe3b1; color: #062417; border: 1px solid #7fe9ba; font-weight: bold;
}
QPushButton#Primary:hover { background: #85efc2; }
QPushButton#Primary:disabled { background: #2d5b46; color: #7d9a8c; border-color: #2d5b46; }
QPushButton#Ghost {
    background: transparent; border-color: transparent; color: #8d9e96; padding: 6px 8px;
}
QPushButton#Ghost:hover { background: rgba(255,255,255,0.04); border-color: #1c2a32; color: #c2d0c9; }
QPushButton#Danger {
    background: rgba(255,133,133,0.07); border-color: rgba(255,133,133,0.25); color: #ff8585;
}
QPushButton#Danger:hover { background: rgba(255,133,133,0.12); }
QPushButton#Nav {
    text-align: left; background: transparent; border: none; border-radius: 8px;
    color: #8d9e96; padding: 9px 11px;
}
QPushButton#Nav:hover { background: rgba(255,255,255,0.035); color: #c2d0c9; }
QPushButton#Nav:checked {
    background: rgba(118,230,180,0.10); color: #76e6b4;
    border-left: 2px solid #76e6b4;
}
QPushButton#IconButton {
    background: transparent; border: none; border-radius: 6px; padding: 4px;
}
QPushButton#IconButton:hover { background: rgba(255,255,255,0.06); }
QPushButton#FilterChip {
    background: transparent; border: none; border-radius: 6px; padding: 5px 10px;
    color: #5f7068; font-size: 8.5pt;
}
QPushButton#FilterChip:hover { color: #c2d0c9; background: rgba(255,255,255,0.03); }
QPushButton#FilterChip:checked { color: #76e6b4; background: rgba(118,230,180,0.10); }
QPushButton#ResetField {
    background: transparent; border: none; border-radius: 5px; padding: 4px;
}
QPushButton#ResetField:hover { background: rgba(118,230,180,0.08); }
QPushButton#LaunchGame {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #7be9b8, stop:1 #43cd94);
    color: #062417; border: 1px solid #8af0c2;
    border-radius: 9px; padding: 8px 12px; min-height: 36px;
    font-weight: bold; font-size: 10pt;
    text-align: left;
}
QPushButton#LaunchGame:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #8df3c5, stop:1 #50dda2);
    border-color: #a5f7d4;
}
QPushButton#LaunchGame:pressed { background: #4bd49c; }
QPushButton#LaunchGame:disabled {
    background: #20312b; color: #63766d; border-color: #284237;
}

QLineEdit, QPlainTextEdit, QComboBox {
    background: rgba(0,0,0,0.16);
    border: 1px solid #2b3e43;
    border-radius: 7px;
    color: #e9f2ec;
    padding: 6px 9px;
    selection-background-color: #2b6e55;
    selection-color: #ffffff;
}
QLineEdit:hover, QPlainTextEdit:hover, QComboBox:hover { border-color: #3c534a; }
QLineEdit:focus, QPlainTextEdit:focus, QComboBox:focus {
    border-color: #4d9f7b; background: rgba(118,230,180,0.02);
}
QLineEdit[invalid="true"], QPlainTextEdit[invalid="true"] {
    border-color: rgba(255,133,133,0.60);
    background: rgba(255,133,133,0.025);
}
QLineEdit:disabled, QPlainTextEdit:disabled, QComboBox:disabled { color: #5f7068; }
QLineEdit#Search { padding-left: 8px; }
QComboBox::drop-down { border: none; width: 22px; }
QComboBox QAbstractItemView {
    background: #111b22; border: 1px solid #2b3e43; border-radius: 6px;
    selection-background-color: #2b6e55; padding: 4px; outline: none;
}
QCheckBox { color: #8d9e96; spacing: 7px; font-size: 8.5pt; }
QCheckBox::indicator {
    width: 14px; height: 14px; border-radius: 3px;
    border: 1px solid #2b3e43; background: rgba(0,0,0,0.2);
}
QCheckBox::indicator:checked { background: #6fe3b1; border-color: #6fe3b1; }
QCheckBox::indicator:hover { border-color: #4d9f7b; }

QScrollBar:vertical { background: transparent; width: 10px; margin: 0; }
QScrollBar::handle:vertical {
    background: rgba(160,190,175,0.16); min-height: 28px; border-radius: 4px;
    margin: 2px;
}
QScrollBar::handle:vertical:hover { background: rgba(160,190,175,0.30); }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
QScrollBar:horizontal { background: transparent; height: 10px; margin: 0; }
QScrollBar::handle:horizontal {
    background: rgba(160,190,175,0.16); min-width: 28px; border-radius: 4px; margin: 2px;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }

QListWidget#FileList {
    background: transparent; border: none; outline: none;
    padding: 4px;
}
QListWidget#FileList::item { border: none; }
QListWidget#FileList::item:selected { background: transparent; }

QToolTip {
    background: #121c24; color: #e9f2ec; border: 1px solid #2b3e43;
    border-radius: 5px; padding: 5px 7px;
}
QSplitter::handle { background: transparent; width: 6px; }
QMessageBox, QDialog, QInputDialog { background: #0f171e; }
QMessageBox QLabel { color: #c2d0c9; }
QMessageBox QPushButton, QInputDialog QPushButton { min-width: 72px; }
QProgressBar {
    background: rgba(255,255,255,0.05); border: none; border-radius: 2px;
    height: 4px; text-align: center;
}
QProgressBar::chunk { background: #6fe3b1; border-radius: 2px; }
"""
