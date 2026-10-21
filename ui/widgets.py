from __future__ import annotations

import json
import math
from typing import Any, Dict, List, Optional

from PyQt5.QtCore import (
    QEasingCurve,
    QEvent,
    QPointF,
    QRectF,
    QSize,
    Qt,
    QTimer,
    QVariantAnimation,
    pyqtSignal,
)
from PyQt5.QtGui import (
    QColor,
    QFont,
    QFontMetrics,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)
from PyQt5.QtWidgets import (
    QAbstractButton,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QVBoxLayout,
    QWidget,
)

from .theme import COLORS, chip_style, icon


def clear_layout(layout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        child = item.layout()
        if widget is not None:
            widget.deleteLater()
        elif child is not None:
            clear_layout(child)


def hline() -> QFrame:
    line = QFrame()
    line.setObjectName("Divider")
    line.setFixedHeight(1)
    return line


def format_variant(fmt: str) -> str:
    low = (fmt or "").lower()
    if "toml" in low:
        return "mint"
    if "json" in low:
        return "blue"
    if "yaml" in low:
        return "violet"
    if "properties" in low or "cfg" in low:
        return "amber"
    return ""


def loader_variant(loader: str) -> str:
    low = (loader or "").lower()
    if "neoforge" in low or "quilt" in low:
        return "violet"
    if "forge" in low:
        return "amber"
    if "fabric" in low:
        return "mint"
    if "optifine" in low:
        return "blue"
    return ""


def type_label(value_type: str) -> str:
    return {
        "boolean": "布尔",
        "integer": "整数",
        "float": "小数",
        "string": "文本",
        "array": "数组",
        "object": "对象",
        "null": "空值",
    }.get(value_type, value_type)


def deep_equal(a: Any, b: Any) -> bool:
    if isinstance(a, float) and isinstance(b, float) and math.isnan(a) and math.isnan(b):
        return True
    return a == b


class ElidedLabel(QLabel):
    def __init__(self, text: str = "", parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._full_text = text
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.setText(text)

    def set_full_text(self, text: str) -> None:
        self._full_text = text or ""
        self.setToolTip(self._full_text)
        self._update_elide()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._update_elide()

    def _update_elide(self) -> None:
        metrics = QFontMetrics(self.font())
        value = metrics.elidedText(self._full_text, Qt.ElideMiddle, max(0, self.width() - 4))
        super().setText(value)


class IconTile(QWidget):
    def __init__(
        self,
        size: int = 48,
        radius: int = 12,
        text: str = "?",
        parent: Optional[QWidget] = None,
        accent: str = COLORS["mint"],
    ):
        super().__init__(parent)
        self._size = size
        self._radius = radius
        self._text = (text or "?")[:1].upper()
        self._pixmap: Optional[QPixmap] = None
        self._accent = QColor(accent)
        self.setFixedSize(size, size)

    def set_text(self, text: str) -> None:
        self._text = (text or "?")[:1].upper()
        self.update()

    def set_pixmap(self, pixmap: Optional[QPixmap]) -> None:
        self._pixmap = pixmap if pixmap and not pixmap.isNull() else None
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        rect = QRectF(0.5, 0.5, self.width() - 1, self.height() - 1)
        path = QPainterPath()
        path.addRoundedRect(rect, self._radius, self._radius)
        bg = QColor(self._accent)
        bg.setAlpha(24)
        painter.fillPath(path, bg)
        border = QColor(self._accent)
        border.setAlpha(42)
        painter.setPen(QPen(border, 1))
        painter.drawPath(path)
        if self._pixmap:
            painter.save()
            painter.setClipPath(path)
            scaled = self._pixmap.scaled(
                self.width(),
                self.height(),
                Qt.KeepAspectRatioByExpanding,
                Qt.SmoothTransformation,
            )
            x = (self.width() - scaled.width()) / 2
            y = (self.height() - scaled.height()) / 2
            painter.drawPixmap(int(x), int(y), scaled)
            painter.restore()
        else:
            font = QFont(self.font())
            font.setBold(True)
            font.setPointSize(max(8, int(self._size * 0.30)))
            painter.setFont(font)
            painter.setPen(self._accent)
            painter.drawText(self.rect(), Qt.AlignCenter, self._text)
        painter.end()


class Chip(QLabel):
    def __init__(self, text: str, variant: str = "", parent: Optional[QWidget] = None):
        super().__init__(text, parent)
        self.setAlignment(Qt.AlignCenter)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.set_variant(variant)

    def set_variant(self, variant: str) -> None:
        self.setStyleSheet(chip_style(variant))


class ToggleSwitch(QAbstractButton):
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setFixedSize(42, 23)
        self.setCursor(Qt.PointingHandCursor)
        self._position = 0.0
        self._animation = QVariantAnimation(self)
        self._animation.setDuration(130)
        self._animation.setEasingCurve(QEasingCurve.OutCubic)
        self._animation.valueChanged.connect(self._on_anim)
        self.toggled.connect(self._on_toggled)
        self._on_toggled(False)

    def _on_anim(self, value) -> None:
        self._position = float(value)
        self.update()

    def _on_toggled(self, checked: bool) -> None:
        start = self._position if self.isVisible() else (1.0 if checked else 0.0)
        end = 1.0 if checked else 0.0
        self._animation.stop()
        self._animation.setStartValue(start)
        self._animation.setEndValue(end)
        self._animation.start()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        rect = QRectF(0.5, 0.5, self.width() - 1, self.height() - 1)
        if self.isChecked():
            track = QColor("#2f8e68")
            border = QColor("#6fe3b1")
        else:
            track = QColor("#202c33")
            border = QColor("#3a4a50")
        painter.setBrush(track)
        painter.setPen(QPen(border, 1))
        painter.drawRoundedRect(rect, rect.height() / 2, rect.height() / 2)
        knob_x = 2 + self._position * (self.width() - 20)
        knob = QRectF(knob_x, 2.5, 18, 18)
        painter.setBrush(QColor("#76e6b4") if self.isChecked() else QColor("#aebbb5"))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(knob)
        painter.end()


class BusyOverlay(QWidget):
    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self._text = "正在读取…"
        self._angle = 0
        self._timer = QTimer(self)
        self._timer.setInterval(35)
        self._timer.timeout.connect(self._tick)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, False)
        self.hide()

    def _tick(self) -> None:
        self._angle = (self._angle + 28) % 360
        self.update()

    def start(self, text: str = "正在读取…") -> None:
        self._text = text
        self.setGeometry(self.parentWidget().rect())
        self.raise_()
        self.show()
        self._timer.start()

    def stop(self) -> None:
        self._timer.stop()
        self.hide()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(8, 13, 17, 232))
        center = QPointF(self.width() / 2, self.height() / 2 - 18)
        painter.setRenderHint(QPainter.Antialiasing, True)
        pen = QPen(QColor("#2b4a3b"), 3)
        pen.setCapStyle(Qt.RoundCap)
        painter.setPen(pen)
        circle = QRectF(center.x() - 13, center.y() - 13, 26, 26)
        painter.drawArc(circle, 0, 360 * 16)
        pen.setColor(QColor("#76e6b4"))
        painter.setPen(pen)
        painter.drawArc(circle, (-self._angle) * 16, 110 * 16)
        font = QFont(self.font())
        font.setPointSize(9)
        painter.setFont(font)
        painter.setPen(QColor("#8d9e96"))
        painter.drawText(
            QRectF(0, center.y() + 24, self.width(), 24),
            Qt.AlignHCenter | Qt.AlignTop,
            self._text,
        )
        painter.end()


class BasePage(QWidget):
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.overlay = BusyOverlay(self)

    def set_loading(self, text: str = "正在读取…") -> None:
        self.overlay.start(text)

    def finish_loading(self) -> None:
        self.overlay.stop()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.overlay.setGeometry(self.rect())


class VersionCard(QFrame):
    clicked = pyqtSignal(str)

    def __init__(self, version: Dict, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.version = version
        self.setObjectName("VersionCard")
        self.setCursor(Qt.PointingHandCursor)
        self.setAttribute(Qt.WA_Hover, True)
        self.setMinimumHeight(174)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._pressed = False
        self._build()

    def _build(self) -> None:
        v = self.version
        outer = QVBoxLayout(self)
        outer.setContentsMargins(18, 16, 18, 15)
        outer.setSpacing(12)

        top = QHBoxLayout()
        top.setSpacing(12)
        self.icon_tile = IconTile(54, 13, v.get("name", "?"))
        top.addWidget(self.icon_tile)
        title_box = QVBoxLayout()
        title_box.setSpacing(5)
        name = QLabel(v.get("name") or "未命名版本")
        name.setObjectName("CardTitle")
        name.setToolTip(name.text())
        title_box.addWidget(name)
        chips = QHBoxLayout()
        chips.setSpacing(6)
        game = QLabel(str(v.get("game_version") or "未知"))
        game.setStyleSheet(chip_style("blue"))
        chips.addWidget(game)
        loader = QLabel(str(v.get("loader") or "未知"))
        loader.setStyleSheet(chip_style(loader_variant(str(v.get("loader") or ""))))
        chips.addWidget(loader)
        if v.get("disabled_mod_count"):
            disabled = QLabel(f"{v['disabled_mod_count']} 个已禁用")
            disabled.setStyleSheet(chip_style("amber"))
            chips.addWidget(disabled)
        chips.addStretch(1)
        title_box.addLayout(chips)
        top.addLayout(title_box, 1)
        arrow = QLabel()
        arrow.setPixmap(icon("chevron", COLORS["dim"], 16).pixmap(16, 16))
        top.addWidget(arrow, 0, Qt.AlignTop)
        outer.addLayout(top)

        stats = QHBoxLayout()
        stats.setSpacing(28)
        stats.addWidget(self._stat(str(v.get("mod_count", 0)), "模组"))
        stats.addWidget(self._stat(str(v.get("config_count", 0)), "配置文件"))
        checklist = QLabel("✓ 已识别" if v.get("has_json") else "— 无清单")
        checklist.setStyleSheet("color:%s; font-size:8.5pt;" % (COLORS["mint"] if v.get("has_json") else COLORS["dim"]))
        check_box = QVBoxLayout()
        check_box.setSpacing(1)
        check_box.addWidget(checklist)
        check_label = QLabel("版本清单")
        check_label.setObjectName("StatLabel")
        check_box.addWidget(check_label)
        stats.addLayout(check_box)
        stats.addStretch(1)
        outer.addLayout(stats)

        footer = QHBoxLayout()
        path = QLabel("versions/" + str(v.get("name") or ""))
        path.setObjectName("Mono")
        path.setToolTip(path.text())
        footer.addWidget(path, 1)
        isolated = QLabel("版本隔离" if v.get("isolated") else "共享目录")
        isolated.setObjectName("Mono")
        footer.addWidget(isolated)
        outer.addLayout(footer)
        self.icon_tile.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        for label in self.findChildren(QLabel):
            label.setAttribute(Qt.WA_TransparentForMouseEvents, True)

    def _stat(self, number: str, label: str) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(1)
        num = QLabel(str(number))
        num.setObjectName("StatNum")
        lab = QLabel(label)
        lab.setObjectName("StatLabel")
        layout.addWidget(num)
        layout.addWidget(lab)
        return widget

    def set_icon(self, pixmap: QPixmap) -> None:
        self.icon_tile.set_pixmap(pixmap)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self._pressed = True
            self.setProperty("pressed", "true")
            self.style().unpolish(self)
            self.style().polish(self)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            was = self._pressed
            self._pressed = False
            self.setProperty("pressed", "false")
            self.style().unpolish(self)
            self.style().polish(self)
            if was and self.rect().contains(event.pos()):
                self.clicked.emit(self.version.get("id", ""))
        super().mouseReleaseEvent(event)


class ModCard(QFrame):
    clicked = pyqtSignal(str)

    def __init__(self, mod: Dict, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.mod = mod
        self.setObjectName("ModCard")
        self.setProperty("virtual", "true" if mod.get("is_virtual") else "false")
        self.setCursor(Qt.PointingHandCursor)
        self.setAttribute(Qt.WA_Hover, True)
        self.setMinimumHeight(92)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._pressed = False
        self._build()

    def _build(self) -> None:
        mod = self.mod
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 13, 14, 13)
        layout.setSpacing(13)
        self.icon_tile = IconTile(46, 11, mod.get("name", "?"), accent=COLORS["amber"] if mod.get("is_virtual") else COLORS["mint"])
        layout.addWidget(self.icon_tile)

        body = QVBoxLayout()
        body.setSpacing(2)
        name = QLabel(mod.get("name") or "未命名模组")
        name.setObjectName("CardTitle")
        name.setToolTip(name.text())
        name.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        body.addWidget(name)
        ident = QLabel("未匹配到具体模组" if mod.get("is_virtual") else str(mod.get("id") or "unknown"))
        ident.setObjectName("CardId")
        ident.setToolTip(ident.text())
        body.addWidget(ident)

        foot = QHBoxLayout()
        foot.setSpacing(8)
        count = mod.get("config_count") or 0
        config_badge = QLabel(f"{count} 个配置" if count else "无配置")
        config_badge.setStyleSheet(chip_style("amber" if mod.get("is_virtual") and count else ("mint" if count else "")))
        foot.addWidget(config_badge)
        fmt = self._format_name(mod.get("format"))
        if fmt and not mod.get("is_virtual"):
            fmt_label = QLabel(fmt)
            fmt_label.setObjectName("Mono")
            foot.addWidget(fmt_label)
        if mod.get("enabled") is False:
            disabled = QLabel("已禁用")
            disabled.setStyleSheet("color:%s; font-size:8pt;" % COLORS["amber"])
            foot.addWidget(disabled)
        if mod.get("is_virtual"):
            note = QLabel("仍可安全编辑")
            note.setObjectName("Mono")
            foot.addWidget(note)
        foot.addStretch(1)
        body.addLayout(foot)
        layout.addLayout(body, 1)
        arrow = QLabel()
        arrow.setPixmap(icon("chevron", COLORS["dim"], 15).pixmap(15, 15))
        layout.addWidget(arrow)
        if mod.get("enabled") is False:
            self.setGraphicsEffect(None)
        self.icon_tile.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        for label in self.findChildren(QLabel):
            label.setAttribute(Qt.WA_TransparentForMouseEvents, True)

    @staticmethod
    def _format_name(fmt: Optional[str]) -> str:
        if not fmt or fmt == "unknown":
            return ""
        return {
            "fabric": "Fabric",
            "forge": "Forge",
            "neoforge": "NeoForge",
            "quilt": "Quilt",
            "legacy": "Legacy",
        }.get(str(fmt).lower(), str(fmt))

    def set_icon(self, pixmap: QPixmap) -> None:
        self.icon_tile.set_pixmap(pixmap)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self._pressed = True
            self.setProperty("pressed", "true")
            self.style().unpolish(self)
            self.style().polish(self)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            was = self._pressed
            self._pressed = False
            self.setProperty("pressed", "false")
            self.style().unpolish(self)
            self.style().polish(self)
            if was and self.rect().contains(event.pos()):
                self.clicked.emit(self.mod.get("key", ""))
        super().mouseReleaseEvent(event)


class FileDelegate(QStyledItemDelegate):
    def sizeHint(self, option: QStyleOptionViewItem, index) -> QSize:
        return QSize(200, 56)

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index) -> None:
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing, True)
        rect = QRectF(option.rect).adjusted(2, 2, -2, -2)
        selected = bool(option.state & QStyle.State_Selected)
        hover = bool(option.state & QStyle.State_MouseOver)
        if selected:
            painter.setBrush(QColor(118, 230, 180, 25))
            painter.setPen(QPen(QColor(118, 230, 180, 43), 1))
            painter.drawRoundedRect(rect, 8, 8)
        elif hover:
            painter.setBrush(QColor(255, 255, 255, 9))
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(rect, 8, 8)

        data = index.data(Qt.UserRole) or {}
        name = data.get("name") or ""
        fmt = data.get("format") or ""
        count = data.get("field_count")
        warning = data.get("warning") or ""
        active_color = COLORS["mint"] if selected else COLORS["text_soft"]
        file_icon = icon("file", COLORS["mint"] if selected else COLORS["dim"], 13).pixmap(13, 13)
        painter.drawPixmap(int(rect.left()) + 9, int(rect.top()) + 10, file_icon)
        font = QFont(option.font)
        font.setPointSizeF(max(8.5, option.font.pointSizeF() - 0.2))
        font.setBold(selected)
        painter.setFont(font)
        painter.setPen(QColor(active_color))
        name_rect = QRectF(rect.left() + 29, rect.top() + 8, rect.width() - 39, 19)
        metrics = QFontMetrics(font)
        painter.drawText(name_rect, Qt.AlignLeft | Qt.AlignVCenter, metrics.elidedText(name, Qt.ElideRight, int(name_rect.width())))
        meta_font = QFont(option.font)
        meta_font.setPointSizeF(max(7.2, option.font.pointSizeF() - 1.8))
        painter.setFont(meta_font)
        painter.setPen(QColor(COLORS["dim"]))
        count_text = "— 参数" if count is None else f"{count} 参数"
        meta = f"{fmt}  ·  {count_text}"
        if warning:
            meta += "  ·  提示"
        painter.drawText(
            QRectF(rect.left() + 29, rect.top() + 30, rect.width() - 39, 16),
            Qt.AlignLeft | Qt.AlignVCenter,
            meta,
        )
        if warning:
            painter.setBrush(QColor(COLORS["amber"]))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(QPointF(rect.right() - 13, rect.top() + 13), 2.6, 2.6)
        painter.restore()


class FieldRow(QFrame):
    changed = pyqtSignal(str, object, bool, str)

    def __init__(self, field: Dict, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.field = field
        self.original = field.get("value")
        self.value = self.original
        self.valid = True
        self.error = ""
        self._loading = False
        self._dirty = False
        self.setObjectName("FieldRow")
        self.setProperty("dirty", "false")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self._build()

    # ------------------------------------------------------------------ UI
    def _build(self) -> None:
        field = self.field
        outer = QHBoxLayout(self)
        outer.setContentsMargins(16, 12, 12, 12)
        outer.setSpacing(16)

        left = QVBoxLayout()
        left.setSpacing(4)
        title = QHBoxLayout()
        title.setSpacing(8)
        label = QLabel(str(field.get("label") or field.get("key") or ""))
        label.setObjectName("FieldLabel")
        title.addWidget(label)
        key = QLabel(str(field.get("key") or ""))
        key.setObjectName("FieldKey")
        key.setToolTip(key.text())
        title.addWidget(key)
        title.addStretch(1)
        left.addLayout(title)
        desc_text = str(field.get("description") or "")
        if desc_text:
            desc = QLabel(desc_text)
            desc.setObjectName("FieldDesc")
            desc.setWordWrap(True)
            desc.setMaximumHeight(50)
            desc.setToolTip(desc_text)
            left.addWidget(desc)
        meta = [type_label(str(field.get("type") or ""))]
        if field.get("min") is not None or field.get("max") is not None:
            meta.append("%s ~ %s" % (field.get("min") if field.get("min") is not None else "−∞", field.get("max") if field.get("max") is not None else "∞"))
        if field.get("enum"):
            meta.append(f"{len(field['enum'])} 个可选值")
        if field.get("line"):
            meta.append(f"L{field['line']}")
        meta_label = QLabel("   ·   ".join(meta))
        meta_label.setObjectName("FieldMeta")
        left.addWidget(meta_label)
        outer.addLayout(left, 1)

        control_box = QVBoxLayout()
        control_box.setSpacing(4)
        control_box.setContentsMargins(0, 0, 0, 0)
        self.control_holder = QWidget()
        self.control_holder.setFixedWidth(292)
        self.control_layout = QVBoxLayout(self.control_holder)
        self.control_layout.setContentsMargins(0, 0, 0, 0)
        self.control_layout.setSpacing(3)
        self._build_control()
        control_box.addWidget(self.control_holder)
        self.error_label = QLabel("")
        self.error_label.setObjectName("FieldError")
        self.error_label.setWordWrap(True)
        self.error_label.hide()
        control_box.addWidget(self.error_label)
        outer.addLayout(control_box)

        self.reset_button = QPushButton()
        self.reset_button.setObjectName("ResetField")
        self.reset_button.setIcon(icon("undo", COLORS["muted"], 15))
        self.reset_button.setIconSize(QSize(15, 15))
        self.reset_button.setFixedSize(28, 28)
        self.reset_button.setToolTip("撤销此项修改")
        self.reset_button.setCursor(Qt.PointingHandCursor)
        self.reset_button.clicked.connect(self._reset)
        self.reset_button.hide()
        outer.addWidget(self.reset_button, 0, Qt.AlignTop)

    def _build_control(self) -> None:
        field = self.field
        value = field.get("value")
        editable = bool(field.get("editable", True))
        self.widget = None
        if not editable:
            label = QLabel()
            label.setStyleSheet(
                "color:#5f7068; border:1px dashed #2b3e43; border-radius:6px;"
                " padding:5px 8px; font-family:'Cascadia Code','Consolas'; font-size:8.5pt;"
            )
            label.setText(self._display(value))
            label.setToolTip(self._display(value))
            label.setWordWrap(False)
            self.control_layout.addWidget(label)
            return
        ftype = str(field.get("type") or "string")
        if ftype == "boolean":
            row = QHBoxLayout()
            row.addStretch(1)
            self.widget = ToggleSwitch()
            self.widget.setChecked(bool(value))
            self.widget.toggled.connect(self._on_bool)
            row.addWidget(self.widget)
            self.state_label = QLabel("开启" if value else "关闭")
            self.state_label.setObjectName("Mono")
            row.addWidget(self.state_label)
            self.control_layout.addLayout(row)
            return
        enum = field.get("enum")
        if enum and len(enum) >= 2:
            combo = QComboBox()
            combo.setMaxVisibleItems(20)
            for item in enum:
                combo.addItem(str(item), item)
            index = next((i for i, item in enumerate(enum) if deep_equal(item, value)), -1)
            if index < 0:
                combo.addItem(str(value), value)
                index = combo.count() - 1
            combo.setCurrentIndex(index)
            combo.currentIndexChanged.connect(self._on_combo)
            self.widget = combo
            self.control_layout.addWidget(combo)
            return
        if ftype in ("integer", "float"):
            edit = QLineEdit()
            edit.setText(str(value))
            edit.setPlaceholderText("数字")
            edit.textChanged.connect(self._on_text)
            self.widget = edit
            self.control_layout.addWidget(edit)
            return
        if ftype in ("array", "object"):
            text = json.dumps(value, ensure_ascii=False, indent=2)
            edit = QPlainTextEdit()
            edit.setPlainText(text)
            edit.setFixedHeight(86)
            font = QFont("Cascadia Code")
            font.setStyleHint(QFont.Monospace)
            font.setPointSizeF(8.5)
            edit.setFont(font)
            edit.textChanged.connect(self._on_text)
            self.widget = edit
            self.control_layout.addWidget(edit)
            return
        if field.get("multiline"):
            edit = QPlainTextEdit()
            edit.setPlainText("" if value is None else str(value))
            edit.setFixedHeight(64)
            edit.textChanged.connect(self._on_text)
            self.widget = edit
            self.control_layout.addWidget(edit)
            return
        edit = QLineEdit()
        edit.setText("" if value is None else str(value))
        edit.textChanged.connect(self._on_text)
        self.widget = edit
        self.control_layout.addWidget(edit)

    def _display(self, value: Any) -> str:
        if isinstance(value, (list, dict)):
            return json.dumps(value, ensure_ascii=False)
        return "null" if value is None else str(value)

    # ------------------------------------------------------------- validation
    def _set_error(self, message: str) -> None:
        self.error = message
        self.valid = not bool(message)
        self.error_label.setText(message)
        self.error_label.setVisible(bool(message))
        if self.widget is not None:
            self.widget.setProperty("invalid", "true" if message else "false")
            self.widget.style().unpolish(self.widget)
            self.widget.style().polish(self.widget)
        self.changed.emit(str(self.field.get("path")), self.value, self.valid, self.error)

    def _on_bool(self, checked: bool) -> None:
        if self._loading:
            return
        self.value = bool(checked)
        self.state_label.setText("开启" if checked else "关闭")
        self._set_error("")
        self.set_dirty(not deep_equal(self.value, self.original))

    def _on_combo(self, index: int) -> None:
        if self._loading:
            return
        value = self.widget.itemData(index)
        self.value = value
        self._set_error("")
        self.set_dirty(not deep_equal(self.value, self.original))

    def _on_text(self) -> None:
        if self._loading:
            return
        ftype = str(self.field.get("type") or "string")
        if ftype in ("integer", "float"):
            text = self.widget.text().strip()
            if text == "":
                self._set_error("请输入一个数字")
                return
            try:
                number = float(text)
            except ValueError:
                self._set_error("数字格式无效")
                return
            if ftype == "integer":
                if not number.is_integer():
                    self._set_error("这里需要整数")
                    return
                number = int(number)
            minimum = self.field.get("min")
            maximum = self.field.get("max")
            if minimum is not None and number < minimum:
                self._set_error(f"不能小于 {minimum}")
                return
            if maximum is not None and number > maximum:
                self._set_error(f"不能大于 {maximum}")
                return
            self.value = number
            self._set_error("")
        elif ftype in ("array", "object"):
            text = self.widget.toPlainText()
            if not text.strip():
                self._set_error("请输入合法的 JSON")
                return
            try:
                value = json.loads(text)
            except json.JSONDecodeError:
                self._set_error("JSON 尚未写完或格式不正确")
                return
            if ftype == "array" and not isinstance(value, list):
                self._set_error("这里需要数组，例如 [1, 2, 3]")
                return
            if ftype == "object" and not isinstance(value, dict):
                self._set_error("这里需要对象，例如 {\"key\": true}")
                return
            self.value = value
            self._set_error("")
        else:
            self.value = self.widget.toPlainText() if isinstance(self.widget, QPlainTextEdit) else self.widget.text()
            self._set_error("")
        self.set_dirty(not deep_equal(self.value, self.original))

    def _reset(self) -> None:
        self._loading = True
        self.value = self.original
        if isinstance(self.widget, ToggleSwitch):
            self.widget.setChecked(bool(self.original))
            self.state_label.setText("开启" if self.original else "关闭")
        elif isinstance(self.widget, QComboBox):
            index = next((i for i in range(self.widget.count()) if deep_equal(self.widget.itemData(i), self.original)), -1)
            if index >= 0:
                self.widget.setCurrentIndex(index)
        elif isinstance(self.widget, QPlainTextEdit):
            if str(self.field.get("type")) in ("array", "object"):
                self.widget.setPlainText(json.dumps(self.original, ensure_ascii=False, indent=2))
            else:
                self.widget.setPlainText("" if self.original is None else str(self.original))
        elif isinstance(self.widget, QLineEdit):
            self.widget.setText("" if self.original is None else str(self.original))
        self._loading = False
        self.set_dirty(False)
        self.error = ""
        self.valid = True
        self.error_label.hide()
        self.changed.emit(str(self.field.get("path")), self.original, True, "")

    def set_dirty(self, dirty: bool) -> None:
        if self._dirty == dirty:
            return
        self._dirty = dirty
        self.setProperty("dirty", "true" if dirty else "false")
        self.style().unpolish(self)
        self.style().polish(self)
        self.reset_button.setVisible(dirty)

    def set_value_silent(self, value: Any) -> None:
        self._loading = True
        self.value = value
        if isinstance(self.widget, ToggleSwitch):
            self.widget.setChecked(bool(value))
            self.state_label.setText("开启" if value else "关闭")
        elif isinstance(self.widget, QComboBox):
            index = next((i for i in range(self.widget.count()) if deep_equal(self.widget.itemData(i), value)), -1)
            if index >= 0:
                self.widget.setCurrentIndex(index)
        elif isinstance(self.widget, QPlainTextEdit):
            if str(self.field.get("type")) in ("array", "object"):
                self.widget.setPlainText(json.dumps(value, ensure_ascii=False, indent=2))
            else:
                self.widget.setPlainText("" if value is None else str(value))
        elif isinstance(self.widget, QLineEdit):
            self.widget.setText("" if value is None else str(value))
        self._loading = False
        self.error_label.hide()
        self.set_dirty(False)


class GroupCard(QFrame):
    def __init__(self, title: str, count: int, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("GroupCard")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.rows: List[FieldRow] = []
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        header = QFrame()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(15, 11, 15, 11)
        header_layout.setSpacing(8)
        dot = QLabel()
        dot.setPixmap(icon("sliders", COLORS["mint"], 13).pixmap(13, 13))
        header_layout.addWidget(dot)
        name = QLabel(title)
        name.setObjectName("GroupTitle")
        header_layout.addWidget(name)
        header_layout.addStretch(1)
        count_label = QLabel(f"{count} 项")
        count_label.setObjectName("GroupCount")
        header_layout.addWidget(count_label)
        outer.addWidget(header)
        self.body = QVBoxLayout()
        self.body.setContentsMargins(0, 0, 0, 0)
        self.body.setSpacing(0)
        outer.addLayout(self.body)

    def add_row(self, row: FieldRow) -> None:
        self.rows.append(row)
        self.body.addWidget(row)

    def any_visible(self) -> bool:
        return any(row.isVisible() for row in self.rows)


class ToastManager(QWidget):
    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self._toasts: List[QWidget] = []
        self.hide()

    def show_message(self, message: str, kind: str = "success", sub: str = "") -> None:
        colors = {
            "success": (COLORS["mint"], "rgba(118,230,180,0.10)"),
            "error": (COLORS["red"], "rgba(255,133,133,0.10)"),
            "warn": (COLORS["amber"], "rgba(237,182,104,0.10)"),
            "info": (COLORS["blue"], "rgba(126,185,255,0.10)"),
        }
        color, bg = colors.get(kind, colors["info"])
        toast = QFrame(self.parentWidget())
        toast.setObjectName("Toast")
        toast.setStyleSheet(
            "QFrame#Toast { background:#0e181d; border:1px solid %s; border-radius:9px; }"
            "QLabel { background:transparent; }" % color
        )
        layout = QHBoxLayout(toast)
        layout.setContentsMargins(12, 9, 14, 9)
        layout.setSpacing(9)
        badge = QLabel()
        icon_name = "check" if kind == "success" else "alert" if kind in ("error", "warn") else "info"
        badge.setPixmap(icon(icon_name, color, 15).pixmap(15, 15))
        layout.addWidget(badge, 0, Qt.AlignTop)
        text_box = QVBoxLayout()
        text_box.setSpacing(1)
        label = QLabel(message)
        label.setStyleSheet("color:#e9f2ec; font-size:9pt;")
        label.setWordWrap(True)
        text_box.addWidget(label)
        if sub:
            sublabel = QLabel(sub)
            sublabel.setStyleSheet("color:#5f7068; font-size:8pt;")
            sublabel.setWordWrap(True)
            text_box.addWidget(sublabel)
        layout.addLayout(text_box, 1)
        toast.adjustSize()
        toast.setMaximumWidth(380)
        toast.show()
        toast.raise_()
        self._toasts.append(toast)
        self._reposition()
        QTimer.singleShot(4200 if kind != "error" else 6200, lambda: self._remove(toast))

    def _remove(self, toast: QWidget) -> None:
        if toast in self._toasts:
            self._toasts.remove(toast)
        toast.deleteLater()
        self._reposition()

    def _reposition(self) -> None:
        parent = self.parentWidget()
        if not parent:
            return
        x = parent.width() - 24
        y = parent.height() - 24
        for toast in reversed(self._toasts):
            toast.adjustSize()
            w = min(380, max(220, toast.sizeHint().width()))
            h = toast.sizeHint().height()
            x2 = x - w
            y2 = y - h
            toast.setGeometry(x2, y2, w, h)
            y = y2 - 8
