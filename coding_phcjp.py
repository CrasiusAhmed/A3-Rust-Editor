import os
import sys
from PySide6.QtCore import (
    Qt, QDir, QFileInfo, QUrl, QRegularExpression, QCoreApplication, QRect, QSize, QProcess, Slot, QTimer, QRunnable, QThreadPool, QObject, Signal, QEvent, QPoint
)
from PySide6.QtGui import (
    QFont, QSyntaxHighlighter, QTextCharFormat, QColor, QPalette, QPainter, QTextFormat, QTextCursor, QIcon, QPen, QGuiApplication, QLinearGradient
)
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QSplitter, QTreeView, QTextEdit,
    QVBoxLayout, QWidget, QFileDialog, QTabWidget, QPlainTextEdit,
    QMessageBox, QFileSystemModel, QMenuBar, QHeaderView,
    QHBoxLayout, QPushButton, QCompleter,
    QDialog, QDialogButtonBox, QFontComboBox, QSpinBox, QFormLayout,
    QMenu, QInputDialog, QLineEdit, QSlider,
    QStackedWidget, QLabel, QTabBar, QStyledItemDelegate, QStyle, QScrollBar, QColorDialog
)
from Main.menu_style_right_click import build_editor_context_menu
from Details.multi_cursor import MultiCursorManager

class MinimapScrollbar(QScrollBar):
    def __init__(self, editor):
        super().__init__(editor)
        self.editor = editor
        self.search_markers = []
        self.linter_error_markers = []  # list of line numbers (1-based)
        self.runtime_error_markers = []  # list of line numbers (1-based)
        # Syntax diagnostic markers by severity (1-based lines)
        self.syntax_red_markers = []
        self.syntax_yellow_markers = []
        self.syntax_warning_markers = []

        # Slightly increase width to make room for markers if needed

    def set_search_markers(self, markers):
        self.search_markers = markers
        self.update()

    def set_linter_error_markers(self, markers):
        """Set linter error markers by line numbers (1-based)."""
        norm = []
        for m in markers or []:
            try:
                norm.append(int(m))
            except Exception:
                pass
        self.linter_error_markers = norm
        self.update()

    def set_runtime_error_markers(self, markers):
        """Set runtime error markers by line numbers (1-based)."""
        norm = []
        for m in markers or []:
            try:
                norm.append(int(m))
            except Exception:
                pass
        self.runtime_error_markers = norm
        self.update()

    def set_syntax_markers(self, yellow=None, red=None, warning=None):
        """Set syntax diagnostic markers by severity (1-based lines)."""
        def _norm(vals):
            out = []
            for v in vals or []:
                try:
                    out.append(int(v))
                except Exception:
                    pass
            return sorted(set(out))
        self.syntax_yellow_markers = _norm(yellow)
        self.syntax_red_markers = _norm(red)
        self.syntax_warning_markers = _norm(warning)
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Draw search markers (subtle orange)
        if self.search_markers:
            marker_color = QColor(206, 145, 120, 180)  # Orange-brown with some transparency
            marker_height = 3
            marker_width = self.width() - 4  # A bit of padding

            total_blocks = max(1, self.editor.blockCount())
            for cursor in self.search_markers:
                block = cursor.block()
                if not block.isValid():
                    continue
                y_pos = (block.blockNumber() / total_blocks) * self.height()
                painter.fillRect(2, int(y_pos), marker_width, marker_height, marker_color)

        # Draw diagnostic markers: red (errors), yellow (syntax), orange (warnings)
        # VS Code-style: small rectangles on the right edge of the scrollbar
        total_blocks = max(1, self.editor.blockCount())
        marker_width_diag = 6  # Width of the marker rectangle
        marker_height_diag = 4  # Height of the marker rectangle

        # Red markers: combine linter, runtime, and syntax reds (ERRORS)
        red_lines = []
        if self.linter_error_markers:
            red_lines.extend(self.linter_error_markers)
        if self.runtime_error_markers:
            red_lines.extend(self.runtime_error_markers)
        if getattr(self, 'syntax_red_markers', None):
            red_lines.extend(self.syntax_red_markers)
        if red_lines:
            err_color = QColor(220, 53, 69, 255)  # Bright red for errors
            for line_num in sorted(set(red_lines)):
                ln0 = max(1, min(line_num, total_blocks))
                y_pos = ((ln0 - 1) / total_blocks) * self.height()
                # Draw on the right edge of the scrollbar
                painter.fillRect(
                    self.width() - marker_width_diag - 1, 
                    int(y_pos), 
                    marker_width_diag, 
                    marker_height_diag, 
                    err_color
                )

        # Yellow markers for syntax-level hints
        if getattr(self, 'syntax_yellow_markers', None):
            yellow = QColor(255, 193, 7, 255)  # Bright yellow
            for line_num in self.syntax_yellow_markers:
                ln0 = max(1, min(line_num, total_blocks))
                y_pos = ((ln0 - 1) / total_blocks) * self.height()
                painter.fillRect(
                    self.width() - marker_width_diag - 1, 
                    int(y_pos), 
                    marker_width_diag, 
                    marker_height_diag, 
                    yellow
                )

        # Orange markers for warnings
        if getattr(self, 'syntax_warning_markers', None):
            orange = QColor(255, 165, 0, 255)  # Bright orange for warnings
            for line_num in self.syntax_warning_markers:
                ln0 = max(1, min(line_num, total_blocks))
                y_pos = ((ln0 - 1) / total_blocks) * self.height()
                painter.fillRect(
                    self.width() - marker_width_diag - 1, 
                    int(y_pos), 
                    marker_width_diag, 
                    marker_height_diag, 
                    orange
                )

class LineNumberArea(QWidget):
    """
    A widget that displays line numbers next to a QPlainTextEdit.
    """
    def __init__(self, editor):
        super().__init__(editor)
        self.editor = editor

    def sizeHint(self):
        """
        Returns the recommended size for the line number area.
        """
        return QSize(self.editor.lineNumberAreaWidth(), 0)

    def paintEvent(self, event):
        """
        Paints the line numbers in the area.
        """
        self.editor.lineNumberAreaPaintEvent(event)

class ColorOverlay(QWidget):
    def __init__(self, editor):
        super().__init__(editor.viewport())
        self.editor = editor
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setObjectName("colorOverlay")
        self.show()
        self.raise_()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        try:
            if hasattr(self.editor, '_draw_color_swatches'):
                self.editor._draw_color_swatches(painter)
        except Exception:
            pass

class InlineColorPickerPopup(QWidget):
    """Lightweight inline color picker popup with live updates (VS Code-like).
    Left: SV color square. Right: two lines (Hue and Alpha sliders). Top: Hex field.
    Writes back to the editor immediately without OK/Cancel.
    """
    def __init__(self, editor: QPlainTextEdit, anchor_global_pos: QPoint, start: int, length: int, initial_text: str):
        super().__init__(editor)
        self.setWindowFlags(Qt.Popup | Qt.FramelessWindowHint)
        self.editor = editor
        self.entry_start = start
        self.entry_length = length
        self.setObjectName("inlineColorPicker")

        # Parse initial color (#RRGGBB or #RRGGBBAA)
        col, a = self._parse_hex(initial_text)
        self._h, self._s, self._v, _ = col.getHsv()
        if self._h < 0:
            self._h = 0
        self._a = a

        # Start a single undo block for the whole picker session
        try:
            # Use a view-linked cursor to keep undo/redo anchored to this editor
            self._saved_view_cursor = self.editor.textCursor()
            self._edit_cursor = QTextCursor(self._saved_view_cursor)
            self._edit_cursor.beginEditBlock()
        except Exception:
            self._edit_cursor = None

        # UI
        # Custom hex field with integrated half-background preview
        class HexLineEdit(QLineEdit):
            def __init__(self, outer):
                super().__init__(outer)
                self.outer = outer
                self.setObjectName("hexField")
                self.setAttribute(Qt.WA_StyledBackground, True)
            def paintEvent(self, ev):
                try:
                    p = QPainter(self)
                    p.setRenderHint(QPainter.Antialiasing)
                    r = self.rect()
                    inner = r.adjusted(2, 2, -2, -2)
                    # Full checkerboard base to visualize transparency
                    tile = 6
                    for yy in range(inner.top(), inner.bottom(), tile):
                        for xx in range(inner.left(), inner.right(), tile):
                            c2 = QColor(200, 200, 200) if ((xx//tile + yy//tile) % 2 == 0) else QColor(240, 240, 240)
                            p.fillRect(QRect(xx, yy, tile, tile), c2)
                    # Overlay current color across the entire field with its alpha
                    col = self.outer._current_color()
                    p.fillRect(inner, QColor(col.red(), col.green(), col.blue(), col.alpha()))
                except Exception:
                    pass
                # Draw text and border on top
                super().paintEvent(ev)
        self.hex_edit = HexLineEdit(self)
        self.hex_edit.setText(self._compose_hex())
        self.hex_edit.setMaxLength(9)  # #RRGGBB or #RRGGBBAA
        self.hex_edit.textChanged.connect(self._on_hex_changed)
        # Ensure initial text color has good contrast on the preview background
        try:
            self._update_hex_text_contrast()
        except Exception:
            pass

        # SV square widget
        class SVSquare(QWidget):
            def __init__(self, outer):
                super().__init__(outer)
                self.outer = outer
                self.setFixedSize(180, 140)
                self.setMouseTracking(True)
            def paintEvent(self, ev):
                p = QPainter(self)
                p.setRenderHint(QPainter.Antialiasing)
                r = self.rect()
                # Checkerboard background to visualize alpha
                tile = 8
                for yy in range(r.top(), r.bottom(), tile):
                    for xx in range(r.left(), r.right(), tile):
                        c = QColor(200, 200, 200) if ((xx//tile + yy//tile) % 2 == 0) else QColor(240, 240, 240)
                        p.fillRect(QRect(xx, yy, tile, tile), c)
                # Base: pure hue color at full sat/value
                hue = self.outer._h
                base = QColor.fromHsv(max(0, min(359, hue)), 255, 255)
                p.fillRect(r, base)
                # Overlay white->transparent (left to right) for saturation
                grad_sat = QLinearGradient(r.topLeft(), r.topRight())
                grad_sat.setColorAt(0.0, QColor(255, 255, 255))
                grad_sat.setColorAt(1.0, QColor(255, 255, 255, 0))
                p.fillRect(r, grad_sat)
                # Overlay transparent->black (top to bottom) for value
                grad_val = QLinearGradient(r.topLeft(), r.bottomLeft())
                grad_val.setColorAt(0.0, QColor(0, 0, 0, 0))
                grad_val.setColorAt(1.0, QColor(0, 0, 0))
                p.fillRect(r, grad_val)
                # Draw handle
                x = int(self.outer._s / 255.0 * (self.width() - 1))
                y = int((1.0 - (self.outer._v / 255.0)) * (self.height() - 1))
                handle = QRect(x - 5, y - 5, 10, 10)
                # Border with contrast
                curr = self.outer._current_color()
                rr, gg, bb, _ = curr.getRgb()
                lum = 0.299*rr + 0.587*gg + 0.114*bb
                p.setPen(QPen(QColor(30, 30, 30) if lum > 186 else QColor(240, 240, 240), 2))
                p.setBrush(Qt.NoBrush)
                p.drawEllipse(handle)
            def mousePressEvent(self, e):
                self._update_from_pos(e.position().toPoint() if hasattr(e, 'position') else e.pos())
            def mouseMoveEvent(self, e):
                if e.buttons() & Qt.LeftButton:
                    self._update_from_pos(e.position().toPoint() if hasattr(e, 'position') else e.pos())
            def _update_from_pos(self, pt):
                w, h = self.width() - 1, self.height() - 1
                x = max(0, min(w, pt.x()))
                y = max(0, min(h, pt.y()))
                self.outer._s = int((x / max(1, w)) * 255)
                self.outer._v = int((1.0 - (y / max(1, h))) * 255)
                self.outer._apply_and_update_ui()
                self.update()
        self.sv_square = SVSquare(self)

        # Right side bars: Hue and Alpha (vertical, full height of SV)
        class HueBar(QWidget):
            def __init__(self, outer):
                super().__init__(outer)
                self.outer = outer
                self.setFixedWidth(16)
                self.setMouseTracking(True)
            def paintEvent(self, ev):
                p = QPainter(self)
                p.setRenderHint(QPainter.Antialiasing)
                r = self.rect()
                grad = QLinearGradient(r.topLeft(), r.bottomLeft())
                stops = [
                    (0.00, QColor.fromHsv(0, 255, 255)),
                    (1/6, QColor.fromHsv(60, 255, 255)),
                    (2/6, QColor.fromHsv(120, 255, 255)),
                    (3/6, QColor.fromHsv(180, 255, 255)),
                    (4/6, QColor.fromHsv(240, 255, 255)),
                    (5/6, QColor.fromHsv(300, 255, 255)),
                    (1.00, QColor.fromHsv(359, 255, 255)),
                ]
                for pos, col in stops:
                    grad.setColorAt(pos, col)
                p.fillRect(r, grad)
                # marker
                y = int((self.outer._h / 359.0) * (self.height()-1))
                p.setPen(QPen(QColor(255,255,255), 2))
                p.drawLine(r.left(), y, r.right(), y)
                p.setPen(QPen(QColor(0,0,0), 1))
                p.drawLine(r.left(), y+1, r.right(), y+1)
            def mousePressEvent(self, e):
                self._set_from_pos(e)
            def mouseMoveEvent(self, e):
                if e.buttons() & Qt.LeftButton:
                    self._set_from_pos(e)
            def _set_from_pos(self, e):
                pt = e.position().toPoint() if hasattr(e, 'position') else e.pos()
                h = int(max(0, min(359, (pt.y() / max(1, self.height()-1)) * 359)))
                self.outer._h = h
                self.outer.sv_square.update()
                self.outer.alpha_bar.update()
                self.outer._apply_and_update_ui()
                self.update()

        class AlphaBar(QWidget):
            def __init__(self, outer):
                super().__init__(outer)
                self.outer = outer
                self.setFixedWidth(16)
                self.setMouseTracking(True)
            def paintEvent(self, ev):
                p = QPainter(self)
                p.setRenderHint(QPainter.Antialiasing)
                r = self.rect()
                # checkerboard
                tile = 6
                for yy in range(r.top(), r.bottom(), tile):
                    for xx in range(r.left(), r.right(), tile):
                        c = QColor(200, 200, 200) if ((xx//tile + yy//tile) % 2 == 0) else QColor(240, 240, 240)
                        p.fillRect(QRect(xx, yy, tile, tile), c)
                # overlay gradient from opaque to transparent of current hue/sat/val
                rgb = QColor.fromHsv(max(0, min(359, self.outer._h)), max(0, min(255, self.outer._s)), max(0, min(255, self.outer._v)))
                grad = QLinearGradient(r.topLeft(), r.bottomLeft())
                grad.setColorAt(0.0, QColor(rgb.red(), rgb.green(), rgb.blue(), 255))
                grad.setColorAt(1.0, QColor(rgb.red(), rgb.green(), rgb.blue(), 0))
                p.fillRect(r, grad)
                # marker
                y = int(((255 - self.outer._a) / 255.0) * (self.height()-1))
                p.setPen(QPen(QColor(255,255,255), 2))
                p.drawLine(r.left(), y, r.right(), y)
                p.setPen(QPen(QColor(0,0,0), 1))
                p.drawLine(r.left(), y+1, r.right(), y+1)
            def mousePressEvent(self, e):
                self._set_from_pos(e)
            def mouseMoveEvent(self, e):
                if e.buttons() & Qt.LeftButton:
                    self._set_from_pos(e)
            def _set_from_pos(self, e):
                pt = e.position().toPoint() if hasattr(e, 'position') else e.pos()
                a = int(max(0, min(255, 255 - (pt.y() / max(1, self.height()-1)) * 255)))
                self.outer._a = a
                self.outer._apply_and_update_ui()
                self.update()

        self.hue_bar = HueBar(self)
        self.alpha_bar = AlphaBar(self)
        # Match bars height to SV square
        self.hue_bar.setFixedHeight(self.sv_square.height())
        self.alpha_bar.setFixedHeight(self.sv_square.height())

        bars_layout = QHBoxLayout()
        bars_layout.setContentsMargins(0, 0, 0, 0)
        bars_layout.setSpacing(6)
        bars_layout.addWidget(self.hue_bar)
        bars_layout.addWidget(self.alpha_bar)

        center_layout = QHBoxLayout()
        center_layout.setContentsMargins(8, 4, 8, 8)
        center_layout.setSpacing(8)
        center_layout.addWidget(self.sv_square)
        center_layout.addLayout(bars_layout)

        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)
        layout.addWidget(self.hex_edit)
        layout.addLayout(center_layout)

        self.setStyleSheet("""
            #inlineColorPicker { background: #1E1F22; border: 1px solid #3C3C3C; border-radius: 6px; }
            #hexField { background: transparent; color: #D4D4D4; border: 1px solid #3C3C3C; padding: 4px 6px; }
            QSlider::groove:vertical { background: #2B2D30; width: 6px; border-radius: 3px; }
            QSlider::handle:vertical { background: #D4D4D4; height: 10px; margin: -2px; border-radius: 3px; }
        """)

        # Place popup near the clicked swatch
        self.adjustSize()
        desired = anchor_global_pos
        # Ensure on-screen: simple shift if near right/bottom
        screen = QGuiApplication.primaryScreen().availableGeometry()
        pos_x = min(desired.x(), screen.right() - self.width() - 4)
        pos_y = min(desired.y(), screen.bottom() - self.height() - 4)
        self.move(QPoint(max(screen.left()+4, pos_x), max(screen.top()+4, pos_y)))

        # Initialize S/V from current color if not set
        if not hasattr(self, '_s'):
            self._s = 255
        if not hasattr(self, '_v'):
            self._v = 255

    def _current_color(self) -> QColor:
        return QColor.fromHsv(max(0, min(359, int(self._h))), max(0, min(255, int(self._s))), max(0, min(255, int(self._v))), max(0, min(255, int(self._a))))

    def _compose_hex(self) -> str:
        c = self._current_color()
        r, g, b, a = c.red(), c.green(), c.blue(), c.alpha()
        # Always include alpha if not fully opaque
        if a != 255:
            return f"#{r:02X}{g:02X}{b:02X}{a:02X}"
        return f"#{r:02X}{g:02X}{b:02X}"

    def _update_hex_text_contrast(self):
        # Compute perceived luminance against checkerboard background and set text color for readability
        try:
            c = self._current_color()
            a = c.alpha() / 255.0
            # Checkerboard approximate average luminance ~ 220
            cb = 220.0
            # Perceived luminance of foreground color
            y = 0.2126 * c.red() + 0.7152 * c.green() + 0.0722 * c.blue()
            eff = a * y + (1.0 - a) * cb
            text = QColor(0, 0, 0) if eff > 160 else QColor(255, 255, 255)
            # Apply only color property so other styles from #hexField remain
            self.hex_edit.setStyleSheet(f"color: {text.name()};")
        except Exception:
            pass

    def _parse_hex(self, text: str):
        t = (text or '').strip()
        if not t.startswith('#'):
            t = '#' + t
        hexpart = t[1:]
        a = 255
        if len(hexpart) == 3:
            hexpart = ''.join(ch*2 for ch in hexpart)
        elif len(hexpart) == 8:
            a = int(hexpart[6:8], 16)
            hexpart = hexpart[:6]
        if len(hexpart) != 6:
            return QColor(255, 255, 255), 255
        r = int(hexpart[0:2], 16)
        g = int(hexpart[2:4], 16)
        b = int(hexpart[4:6], 16)
        return QColor(r, g, b, a), a

    def _apply_and_update_ui(self):
        # Update hex field and write to document
        hex_text = self._compose_hex()
        try:
            # Write into the document at stored range and keep caret near the edited literal
            cur = self._edit_cursor or QTextCursor(self.editor.textCursor())
            # Temporarily suppress editor updates and signals to avoid re-entrant paint/highlight during live edits
            try:
                self.editor.setUpdatesEnabled(False)
            except Exception:
                pass
            try:
                self.editor.blockSignals(True)
            except Exception:
                pass
            doc = None
            try:
                doc = self.editor.document()
                if doc is not None:
                    doc.blockSignals(True)
            except Exception:
                doc = None
            try:
                cur.setPosition(self.entry_start)
                cur.setPosition(self.entry_start + self.entry_length, QTextCursor.KeepAnchor)
                cur.insertText(hex_text)
                # Place caret at end of the inserted text
                self.editor.setTextCursor(cur)
                # Update cached length to reflect new literal including optional alpha
                self.entry_length = len(hex_text)
                # Update hex field without causing recursive textChanged
                if self.hex_edit.text() != hex_text:
                    self.hex_edit.blockSignals(True)
                    self.hex_edit.setText(hex_text)
                    self.hex_edit.blockSignals(False)
            finally:
                try:
                    if doc is not None:
                        doc.blockSignals(False)
                except Exception:
                    pass
                try:
                    self.editor.blockSignals(False)
                except Exception:
                    pass
                try:
                    self.editor.setUpdatesEnabled(True)
                except Exception:
                    pass
            # Ensure visibility after re-enabling updates
            try:
                self.editor.ensureCursorVisible()
            except Exception:
                pass

            # Update hex input text color for readability
            try:
                self._update_hex_text_contrast()
            except Exception:
                pass
        except Exception:
            pass
        # Update main window toolbar color icon live during edits (Change Color mode)
        try:
            win = self.editor.window()
            if hasattr(win, 'color_change_mode_active') and getattr(win, 'color_change_mode_active', False):
                win.current_color_hex = hex_text.upper()
                if hasattr(win, 'set_color_icon'):
                    win.set_color_icon(win.current_color_hex)
        except Exception:
            pass
        self.update()
        try:
            self.hex_edit.update()
        except Exception:
            pass
        if hasattr(self.editor, 'viewport'):
            self.editor.viewport().update()

    def _on_hex_changed(self, s: str):
        col, a = self._parse_hex(s)
        h, sat, val, _ = col.getHsv()
        if h < 0:
            h = self._h
        self._h, self._s, self._v, self._a = h, sat, val, a
        self.sv_square.update()
        self._apply_and_update_ui()

    def _on_hue_changed(self, v: int):
        self._h = int(v)
        if hasattr(self, 'hue_bar'):
            try:
                self.hue_bar.update()
            except Exception:
                pass
        if hasattr(self, 'alpha_bar'):
            try:
                self.alpha_bar.update()
            except Exception:
                pass
        self.sv_square.update()
        self._apply_and_update_ui()

    def _on_alpha_changed(self, v: int):
        self._a = int(v)
        self._apply_and_update_ui()

    
    def keyPressEvent(self, e):
        if e.key() in (Qt.Key_Escape,):
            self.close()
            return
        super().keyPressEvent(e)

    def closeEvent(self, e):
        try:
            if getattr(self, '_edit_cursor', None):
                try:
                    self._edit_cursor.endEditBlock()
                except Exception:
                    pass
            # Only clear the active picker if it still references this instance
            try:
                if getattr(self.editor, '_active_color_picker', None) is self:
                    self.editor._active_color_picker = None
            except Exception:
                pass
            # Do not restore a saved cursor position; keep caret at edit location
        except Exception:
            pass
        super().closeEvent(e)

class RustSyntaxHighlighter(QSyntaxHighlighter):
    """
    Perfect Rust syntax highlighter matching RustRover (JetBrains) color scheme.
    Handles all Rust syntax: keywords, types, macros, attributes, lifetimes,
    strings, chars, numbers, functions, operators, brackets, and comments.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        # RustRover (JetBrains) inspired color scheme
        self.colors = {
            'default': QColor('#D4D4D4'),          # Default text
            'comment': QColor('#808080'),          # Comments (gray)
            'doc_comment': QColor('#629755'),      # Doc comments (green)
            'control_keyword': QColor('#CC7832'),  # Control flow (if, else, try, match) - Orange
            'keyword': QColor('#CC7832'),          # Other keywords (fn, struct, enum) - Orange
            'let_keyword': QColor('#CC7832'),      # let keyword - Orange
            'mut_keyword': QColor('#CC7832'),      # mut keyword - Orange
            'type': QColor('#4EC9B0'),             # Types (i32, String, Vec) - Cyan
            'type_param': QColor('#20999D'),       # Generic type parameters - Teal
            'lifetime': QColor('#20999D'),         # Lifetimes 'a - Teal
            'attribute': QColor('#BBB529'),        # Attributes #[derive(...)] - Yellow
            'macro': QColor('#A9B7C6'),            # Macros println! - Light gray
            'function': QColor('#56A8F5'),         # Function names - Blue (like Python)
            'method': QColor('#56A8F5'),           # Method calls - Blue
            'const_static': QColor('#9876AA'),     # Constants and statics - Purple
            'enum_variant': QColor('#9876AA'),     # Enum variants - Purple
            'number': QColor('#6897BB'),           # Numbers - Blue
            'string': QColor('#6A8759'),           # Strings - Green
            'char': QColor('#6A8759'),             # Characters - Green
            'escape': QColor('#CC7832'),           # Escape sequences - Orange
            'operator': QColor('#A9B7C6'),         # Operators - Light gray
            'punctuation': QColor('#A9B7C6'),      # Punctuation - Light gray
            'brace': QColor('#FFD700'),            # Braces {} - Gold
            'bracket': QColor('#DA70D6'),          # Brackets [] - Orchid
            'paren': QColor('#FFD700'),            # Parentheses () - Gold
            'namespace': QColor("#AF7EC9"),        # Module/crate names - Purple
            'variable': QColor('#A9B7C6'),         # Variables - Light gray
            'parameter': QColor('#A9B7C6'),        # Function parameters - Light gray
            'field': QColor("#DAA07E"),            # Struct fields - Purple
            'self_keyword': QColor("#C764BB"),     # self/Self - Dark purple
        }
        
        # Keywords by category
        control_keywords = ['if', 'else', 'match', 'loop', 'while', 'for', 'break', 'continue', 'return', 'try']
        declaration_keywords = ['fn', 'struct', 'enum', 'trait', 'impl', 'type', 'mod', 'use', 'const', 'static']
        let_mut_keywords = ['let', 'mut']
        other_keywords = ['as', 'async', 'await', 'crate', 'dyn', 'extern', 'in', 'move', 'pub', 'ref', 'super', 'unsafe', 'where']
        bool_keywords = ['true', 'false']
        self_keywords = ['self', 'Self']
        
        all_keywords = control_keywords + declaration_keywords + let_mut_keywords + other_keywords + bool_keywords + self_keywords
        
        # Compile regex patterns
        self.re_control_keywords = QRegularExpression(r"\b(" + '|'.join(control_keywords) + r")\b")
        self.re_keywords = QRegularExpression(r"\b(" + '|'.join(declaration_keywords + other_keywords + bool_keywords) + r")\b")
        self.re_let_mut = QRegularExpression(r"\b(let|mut)\b")
        self.re_self = QRegularExpression(r"\b(self|Self)\b")
        
        # Crate/module names in use statements (e.g., use eframe::egui;)
        self.re_use_crate = QRegularExpression(r"\buse\s+([a-z_][a-z0-9_]*(?:::[a-z_][a-z0-9_]*)*)")
        
        # Primitive and common types
        prim_types = ['i8','i16','i32','i64','i128','isize','u8','u16','u32','u64','u128','usize','f32','f64','bool','char','str']
        common_types = ['String','Vec','Option','Result','Box','Arc','Rc','Mutex','RwLock','Cell','RefCell',
                       'HashMap','HashSet','BTreeMap','BTreeSet','LinkedList','VecDeque','BinaryHeap',
                       'Path','PathBuf','File','Error','Iterator','Fn','FnMut','FnOnce']
        self.re_types = QRegularExpression(r"\b(" + '|'.join(prim_types + common_types) + r")\b")
        
        # Generic type parameters (T, U, K, V, etc.)
        self.re_type_param = QRegularExpression(r"\b[A-Z]\b")
        
        # Custom types (PascalCase: TaskFilter, Priority, MyApp, etc.)
        self.re_custom_type = QRegularExpression(r"\b[A-Z][A-Za-z0-9_]*\b")
        
        # Lifetimes
        self.re_lifetime = QRegularExpression(r"'[_a-zA-Z][_a-zA-Z0-9]*\b")
        
        # Namespace/crate path segments (lowercase identifiers in paths like std::io::Read)
        self.re_namespace_path = QRegularExpression(r"\b([a-z_][a-z0-9_]*)(?=::)")
        
        # Attributes
        self.re_attribute = QRegularExpression(r"#!?\[[^\]]*\]")
        
        # Macros (name followed by !)
        self.re_macro = QRegularExpression(r"\b([A-Za-z_][A-Za-z0-9_]*)!")
        
        # Function definitions
        self.re_fn_def = QRegularExpression(r"\bfn\s+([A-Za-z_][A-Za-z0-9_]*)")
        
        # Function/method calls
        self.re_call = QRegularExpression(r"\b([a-z_][A-Za-z0-9_]*)\s*(?=\()")
        self.re_method = QRegularExpression(r"\.([a-z_][A-Za-z0-9_]*)\s*(?=\()")
        
        # Struct field access
        self.re_field = QRegularExpression(r"\.([a-z_][A-Za-z0-9_]*)\b(?!\s*\()")
        
        # Constants and enum variants (SCREAMING_SNAKE_CASE)
        self.re_const = QRegularExpression(r"\b[A-Z][A-Z0-9_]{1,}\b")
        
        # Numbers with type suffixes
        self.re_number = QRegularExpression(
            r"\b(?:0x[0-9A-Fa-f_]+|0b[01_]+|0o[0-7_]+|\d[\d_]*(?:\.\d[\d_]*)?(?:[eE][+-]?\d[\d_]*)?)(?:[iu](?:8|16|32|64|128|size)|f(?:32|64))?\b"
        )
        
        # Strings (including raw strings)
        self.re_string = QRegularExpression(r'(?:r#*"[^"]*"#*|"(?:[^"\\]|\\.)*")')
        
        # Characters
        self.re_char = QRegularExpression(r"'(?:[^'\\]|\\.)+'")
        
        # Escape sequences in strings
        self.re_escape = QRegularExpression(r'\\[nrt\\"\']|\\x[0-9A-Fa-f]{2}|\\u\{[0-9A-Fa-f]+\}')
        
        # Doc comments
        self.re_doc_line = QRegularExpression(r"^\s*(///|//!).*$")
        
        # Line comments
        self.re_line_comment = QRegularExpression(r"//.*$")
        
        # Block comment delimiters
        self.block_start = QRegularExpression(r"/\*")
        self.block_end = QRegularExpression(r"\*/")
        
        # Operators
        self.re_operators = QRegularExpression(r"[+\-*/%=!<>&|^~?:]")
        
        # Track formatted regions to avoid re-coloring
        self.formatted = []

    def _apply_regex(self, text: str, regex: QRegularExpression, color: QColor, cap_group: int = 0):
        """Apply color to all matches of a regex pattern."""
        it = regex.globalMatch(text)
        while it.hasNext():
            m = it.next()
            s = m.capturedStart(cap_group)
            l = m.capturedLength(cap_group)
            if l > 0:
                self.setFormat(s, l, color)
                # Mark as formatted
                for i in range(s, min(s + l, len(self.formatted))):
                    self.formatted[i] = True

    def _is_formatted(self, start: int, length: int) -> bool:
        """Check if a region is already formatted."""
        if start >= len(self.formatted):
            return False
        return any(self.formatted[i] for i in range(start, min(start + length, len(self.formatted))))

    def highlightBlock(self, text: str):
        """Main highlighting function."""
        if not text:
            return
            
        # Initialize formatted tracker
        self.formatted = [False] * len(text)
        
        # State: 0 = normal, 1 = inside block comment
        state = self.previousBlockState()
        i = 0
        length = len(text)

        # Handle continued block comment from previous line
        if state == 1:
            end = self.block_end.match(text, 0)
            if end.hasMatch():
                end_pos = end.capturedStart()
                self.setFormat(0, end_pos + 2, self.colors['comment'])
                for j in range(0, end_pos + 2):
                    self.formatted[j] = True
                i = end_pos + 2
                self.setCurrentBlockState(0)
            else:
                self.setFormat(0, length, self.colors['comment'])
                self.setCurrentBlockState(1)
                return

        # Find and color block comments
        start = self.block_start.match(text, i)
        while start.hasMatch():
            s = start.capturedStart()
            end = self.block_end.match(text, s + 2)
            if end.hasMatch():
                e = end.capturedStart() + 2
                self.setFormat(s, e - s, self.colors['comment'])
                for j in range(s, e):
                    self.formatted[j] = True
                i = e
                start = self.block_start.match(text, i)
            else:
                self.setFormat(s, length - s, self.colors['comment'])
                for j in range(s, length):
                    self.formatted[j] = True
                self.setCurrentBlockState(1)
                return

        # Doc comments (before strings) - mark entire line as formatted
        it = self.re_doc_line.globalMatch(text)
        while it.hasNext():
            m = it.next()
            s = m.capturedStart()
            l = m.capturedLength()
            if not self._is_formatted(s, l):
                self.setFormat(s, l, self.colors['doc_comment'])
                for j in range(s, min(s + l, len(self.formatted))):
                    self.formatted[j] = True
        
        # Line comments - mark entire comment as formatted
        it = self.re_line_comment.globalMatch(text)
        while it.hasNext():
            m = it.next()
            s = m.capturedStart()
            l = m.capturedLength()
            if not self._is_formatted(s, l):
                self.setFormat(s, l, self.colors['comment'])
                for j in range(s, min(s + l, len(self.formatted))):
                    self.formatted[j] = True

        # Strings (after comments so strings in comments keep comment color)
        it = self.re_string.globalMatch(text)
        while it.hasNext():
            m = it.next()
            s = m.capturedStart()
            l = m.capturedLength()
            if not self._is_formatted(s, l):
                self.setFormat(s, l, self.colors['string'])
                for j in range(s, min(s + l, len(self.formatted))):
                    self.formatted[j] = True
                # Highlight escape sequences within strings (only if not in comment)
                string_text = text[s:s+l]
                esc_it = self.re_escape.globalMatch(string_text)
                while esc_it.hasNext():
                    esc_m = esc_it.next()
                    esc_s = s + esc_m.capturedStart()
                    esc_l = esc_m.capturedLength()
                    self.setFormat(esc_s, esc_l, self.colors['escape'])

        # Characters (after comments so chars in comments keep comment color)
        it = self.re_char.globalMatch(text)
        while it.hasNext():
            m = it.next()
            s = m.capturedStart()
            l = m.capturedLength()
            if not self._is_formatted(s, l):
                self.setFormat(s, l, self.colors['char'])
                for j in range(s, min(s + l, len(self.formatted))):
                    self.formatted[j] = True

        # Attributes
        self._apply_regex(text, self.re_attribute, self.colors['attribute'])

        # Macros (name and !)
        it = self.re_macro.globalMatch(text)
        while it.hasNext():
            m = it.next()
            s = m.capturedStart()
            l = m.capturedLength()
            if not self._is_formatted(s, l):
                self.setFormat(s, l, self.colors['macro'])
                for j in range(s, min(s + l, len(self.formatted))):
                    self.formatted[j] = True

        # Control keywords (if, else, try, match, etc.) - Orange (skip if in comment)
        it = self.re_control_keywords.globalMatch(text)
        while it.hasNext():
            m = it.next()
            s = m.capturedStart()
            l = m.capturedLength()
            if l > 0 and not self._is_formatted(s, l):
                self.setFormat(s, l, self.colors['control_keyword'])
                for j in range(s, min(s + l, len(self.formatted))):
                    self.formatted[j] = True
        
        # Other keywords (fn, struct, enum, etc.) - Orange (skip if in comment)
        it = self.re_keywords.globalMatch(text)
        while it.hasNext():
            m = it.next()
            s = m.capturedStart()
            l = m.capturedLength()
            if l > 0 and not self._is_formatted(s, l):
                self.setFormat(s, l, self.colors['keyword'])
                for j in range(s, min(s + l, len(self.formatted))):
                    self.formatted[j] = True
        
        # let and mut - Orange (skip if in comment)
        it = self.re_let_mut.globalMatch(text)
        while it.hasNext():
            m = it.next()
            s = m.capturedStart()
            l = m.capturedLength()
            if l > 0 and not self._is_formatted(s, l):
                self.setFormat(s, l, self.colors['let_keyword'])
                for j in range(s, min(s + l, len(self.formatted))):
                    self.formatted[j] = True
        
        # self and Self - Dark purple (skip if in comment)
        it = self.re_self.globalMatch(text)
        while it.hasNext():
            m = it.next()
            s = m.capturedStart()
            l = m.capturedLength()
            if l > 0 and not self._is_formatted(s, l):
                self.setFormat(s, l, self.colors['self_keyword'])
                for j in range(s, min(s + l, len(self.formatted))):
                    self.formatted[j] = True
        
        # Namespace/crate names in paths (e.g., std::io, eframe::egui) - Purple (skip if in comment)
        # This must come before function calls to avoid conflicts
        it = self.re_namespace_path.globalMatch(text)
        while it.hasNext():
            m = it.next()
            s = m.capturedStart()
            l = m.capturedLength()
            if l > 0 and not self._is_formatted(s, l):
                self.setFormat(s, l, self.colors['namespace'])
                for j in range(s, min(s + l, len(self.formatted))):
                    self.formatted[j] = True
        
        # Unsafe keyword gets underline
        unsafe_it = QRegularExpression(r"\bunsafe\b").globalMatch(text)
        while unsafe_it.hasNext():
            m = unsafe_it.next()
            s = m.capturedStart()
            l = m.capturedLength()
            if l > 0:
                fmt = QTextCharFormat()
                fmt.setForeground(self.colors['keyword'])
                fmt.setFontUnderline(True)
                self.setFormat(s, l, fmt)

        # Types (built-in) (skip if in comment)
        it = self.re_types.globalMatch(text)
        while it.hasNext():
            m = it.next()
            s = m.capturedStart()
            l = m.capturedLength()
            if l > 0 and not self._is_formatted(s, l):
                self.setFormat(s, l, self.colors['type'])
                for j in range(s, min(s + l, len(self.formatted))):
                    self.formatted[j] = True
        
        # Constants and enum variants (SCREAMING_SNAKE_CASE) (skip if in comment)
        it = self.re_const.globalMatch(text)
        while it.hasNext():
            m = it.next()
            s = m.capturedStart()
            l = m.capturedLength()
            if l > 0 and not self._is_formatted(s, l):
                self.setFormat(s, l, self.colors['const_static'])
                for j in range(s, min(s + l, len(self.formatted))):
                    self.formatted[j] = True
        
        # Custom types (PascalCase: TaskFilter, Priority, MyApp, etc.) - only if not already formatted
        it = self.re_custom_type.globalMatch(text)
        while it.hasNext():
            m = it.next()
            s = m.capturedStart()
            l = m.capturedLength()
            if l > 0 and not self._is_formatted(s, l):
                self.setFormat(s, l, self.colors['type'])
                for j in range(s, min(s + l, len(self.formatted))):
                    self.formatted[j] = True
        
        # Generic type parameters (single capital letters) (skip if in comment)
        it = self.re_type_param.globalMatch(text)
        while it.hasNext():
            m = it.next()
            s = m.capturedStart()
            l = m.capturedLength()
            if l > 0 and not self._is_formatted(s, l):
                self.setFormat(s, l, self.colors['type_param'])
                for j in range(s, min(s + l, len(self.formatted))):
                    self.formatted[j] = True
        
        # Lifetimes (skip if in comment)
        it = self.re_lifetime.globalMatch(text)
        while it.hasNext():
            m = it.next()
            s = m.capturedStart()
            l = m.capturedLength()
            if l > 0 and not self._is_formatted(s, l):
                self.setFormat(s, l, self.colors['lifetime'])
                for j in range(s, min(s + l, len(self.formatted))):
                    self.formatted[j] = True

        # Numbers (skip if in comment)
        it = self.re_number.globalMatch(text)
        while it.hasNext():
            m = it.next()
            s = m.capturedStart()
            l = m.capturedLength()
            if l > 0 and not self._is_formatted(s, l):
                self.setFormat(s, l, self.colors['number'])
                for j in range(s, min(s + l, len(self.formatted))):
                    self.formatted[j] = True

        # Function definitions
        it = self.re_fn_def.globalMatch(text)
        while it.hasNext():
            m = it.next()
            s = m.capturedStart(1)
            l = m.capturedLength(1)
            if l > 0 and not self._is_formatted(s, l):
                self.setFormat(s, l, self.colors['function'])

        # Method calls
        it = self.re_method.globalMatch(text)
        while it.hasNext():
            m = it.next()
            s = m.capturedStart(1)
            l = m.capturedLength(1)
            if l > 0 and not self._is_formatted(s, l):
                self.setFormat(s, l, self.colors['method'])

        # Function calls (exclude keywords)
        excluded = {'if','while','loop','match','return','unsafe','as','in','move','for','break','continue'}
        it = self.re_call.globalMatch(text)
        while it.hasNext():
            m = it.next()
            name = m.captured(1)
            if name and name not in excluded:
                s = m.capturedStart(1)
                l = m.capturedLength(1)
                if not self._is_formatted(s, l):
                    self.setFormat(s, l, self.colors['function'])

        # Struct field access
        it = self.re_field.globalMatch(text)
        while it.hasNext():
            m = it.next()
            s = m.capturedStart(1)
            l = m.capturedLength(1)
            if l > 0 and not self._is_formatted(s, l):
                self.setFormat(s, l, self.colors['field'])

        # Operators (skip if in comment)
        it = self.re_operators.globalMatch(text)
        while it.hasNext():
            m = it.next()
            s = m.capturedStart()
            l = m.capturedLength()
            if l > 0 and not self._is_formatted(s, l):
                self.setFormat(s, l, self.colors['operator'])
                for j in range(s, min(s + l, len(self.formatted))):
                    self.formatted[j] = True

        # Brackets, braces, and parentheses
        self._highlight_brackets(text)

    def _highlight_brackets(self, text: str):
        """Highlight brackets, braces, and parentheses with distinct colors."""
        for i, ch in enumerate(text):
            if self.formatted[i]:
                continue
            
            if ch in '{}':
                self.setFormat(i, 1, self.colors['brace'])
            elif ch in '[]':
                self.setFormat(i, 1, self.colors['bracket'])
            elif ch in '()':
                self.setFormat(i, 1, self.colors['paren'])

class SearchReplaceWidget(QWidget):
    def __init__(self, editor):
        super().__init__(editor)
        self.editor = editor
        self.setObjectName("searchReplaceWidget")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.original_palette = self.editor.palette()

        self.matches = []
        self.current_match_index = -1

        # Timer for delayed search
        self.search_timer = QTimer(self)
        self.search_timer.setSingleShot(True)
        self.search_timer.setInterval(100)  # 250ms delay
        self.search_timer.timeout.connect(self.find_all)

        self._create_ui()
        self.hide()

    def _create_ui(self):
        self.setStyleSheet("""
            #searchReplaceWidget {
                background-color: #1E1F22;
                border-left: 2px solid #4a4a4a;
                border-bottom: 1px solid #4a4a4a;
                border-right: 1px solid #4a4a4a;
                border-radius: 4px;
            }
            #replace_container {
                background: transparent;
            }
            QLineEdit {
                background-color: #3C3C3C;
                color: #D4D4D4;
                border: 1px solid #3C3C3C;
                padding: 4px;
            }
            QPushButton {
                background-color: #3C3C3C;
                color: #D4D4D4;
                border: none;
                padding: 4px 8px;
            }
            QPushButton:hover {
                background-color: #4C4C4C;
            }
            QLabel {
                color: #A0A0A0;
                background-color: transparent;
            }
        """)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(5)

        # Search row
        search_layout = QHBoxLayout()
        search_layout.setSpacing(5)
        self.toggle_replace_btn = QPushButton("▶")
        self.toggle_replace_btn.setCheckable(True)
        self.toggle_replace_btn.setFixedWidth(25)
        self.toggle_replace_btn.setStyleSheet("background: transparent; border: none; color: #a0a0a0; font-size: 16px;")
        self.toggle_replace_btn.toggled.connect(self._toggle_replace_visibility)
        search_layout.addWidget(self.toggle_replace_btn)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search")
        self.search_input.textChanged.connect(self.search_timer.start)
        self.search_input.setFixedWidth(250)
        search_layout.addWidget(self.search_input)

        self.match_count_label = QLabel("No results")
        search_layout.addWidget(self.match_count_label)

        self.prev_match_btn = QPushButton("↑")
        self.prev_match_btn.setToolTip("Previous match (Shift+F3)")
        self.prev_match_btn.clicked.connect(self.find_previous)
        self.prev_match_btn.setFixedSize(25, 25)
        self.prev_match_btn.setStyleSheet("font-size: 16px;")
        search_layout.addWidget(self.prev_match_btn)

        self.next_match_btn = QPushButton("↓")
        self.next_match_btn.setToolTip("Next match (F3)")
        self.next_match_btn.clicked.connect(self.find_next)
        self.next_match_btn.setFixedSize(25, 25)
        self.next_match_btn.setStyleSheet("font-size: 16px;")
        search_layout.addWidget(self.next_match_btn)

        self.close_btn = QPushButton("✕")
        self.close_btn.setToolTip("Close (Esc)")
        self.close_btn.clicked.connect(self.hide)
        search_layout.addWidget(self.close_btn)
        main_layout.addLayout(search_layout)

        # Replace row
        self.replace_widget = QWidget()
        self.replace_widget.setObjectName("replace_container")
        replace_layout = QHBoxLayout(self.replace_widget)
        replace_layout.setContentsMargins(24, 0, 0, 0)
        replace_layout.setSpacing(2)
        self.replace_input = QLineEdit()
        self.replace_input.setPlaceholderText("Replace")
        self.replace_input.setFixedWidth(250)
        replace_layout.addWidget(self.replace_input)

        # Create a nested layout for the buttons to control their spacing independently
        button_layout = QHBoxLayout()
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.setSpacing(5)

        self.replace_btn = QPushButton("⮂")
        self.replace_btn.setToolTip("Replace (Ctrl+H)")
        self.replace_btn.clicked.connect(self.replace_current)
        self.replace_btn.setFixedSize(25, 25)
        button_layout.addWidget(self.replace_btn)

        self.replace_all_btn = QPushButton("⮃")
        self.replace_all_btn.setToolTip("Replace All (Ctrl+Alt+Enter)")
        self.replace_all_btn.clicked.connect(self.replace_all)
        self.replace_all_btn.setFixedSize(25, 25)
        button_layout.addWidget(self.replace_all_btn)
        
        replace_layout.addLayout(button_layout)
        main_layout.addWidget(self.replace_widget)

        self.replace_widget.setVisible(False)

    def _toggle_replace_visibility(self, checked):
        self.replace_widget.setVisible(checked)
        self.toggle_replace_btn.setText("▼" if checked else "▶")
        self.adjustSize()

    def _update_match_count_label(self):
        if not self.matches:
            self.match_count_label.setText("No results")
        else:
            self.match_count_label.setText(f"{self.current_match_index + 1} of {len(self.matches)}")

    def set_search_text(self, text):
        self.search_input.setText(text)
        self.search_input.setFocus()
        self.search_input.selectAll()
        self.find_all()

    def find_all(self, start_from_cursor=None):
        self.matches.clear()
        self.current_match_index = -1
        
        text_to_find = self.search_input.text()
        if not text_to_find:
            self.match_count_label.setText("No results")
            self.highlight_matches() # Clear highlights
            return

        # Find all occurrences in the document
        cursor = self.editor.document().find(text_to_find)
        while not cursor.isNull():
            self.matches.append(cursor)
            cursor = self.editor.document().find(text_to_find, cursor)

        if self.matches:
            # If the search was started from a selection, try to find that selection
            if start_from_cursor and start_from_cursor.hasSelection():
                for i, match in enumerate(self.matches):
                    if match.selectionStart() == start_from_cursor.selectionStart() and \
                       match.selectionEnd() == start_from_cursor.selectionEnd():
                        self.current_match_index = i
                        break
            
            # If no specific selection, or selection not found, find the next one from cursor
            if self.current_match_index == -1:
                start_pos = start_from_cursor.position() if start_from_cursor else 0
                for i, match in enumerate(self.matches):
                    if match.position() >= start_pos:
                        self.current_match_index = i
                        break

            # If still not found (e.g., cursor was after last match), wrap around
            if self.current_match_index == -1:
                self.current_match_index = 0
            
            self.select_current_match()
        else:
            self.match_count_label.setText("No results")
            self.highlight_matches()

    def find_next(self):
        if not self.matches:
            return
        self.current_match_index = (self.current_match_index + 1) % len(self.matches)
        self.select_current_match()

    def find_previous(self):
        if not self.matches:
            return
        self.current_match_index = (self.current_match_index - 1 + len(self.matches)) % len(self.matches)
        self.select_current_match()

    def replace_current(self):
        if self.current_match_index == -1 or not self.matches:
            return

        cursor = self.matches[self.current_match_index]
        cursor.insertText(self.replace_input.text())
        self.find_all()
        self.find_next()

    def replace_all(self):
        if not self.matches:
            return

        for cursor in reversed(self.matches):
            cursor.insertText(self.replace_input.text())
        self.find_all()

    def highlight_matches(self):
        selections = []
        if self.matches:
            # Using more subtle orange/brown tones for better text visibility
            other_match_color = QColor(206, 145, 120, 80)  # More transparent for other matches

            for i, cursor in enumerate(self.matches):
                if i == self.current_match_index:
                    continue  # Skip the current match, it will be handled by the main selection
                selection = QTextEdit.ExtraSelection()
                selection.cursor = cursor
                selection.format.setBackground(other_match_color)
                selections.append(selection)

        if hasattr(self.editor, 'setSearchSelections'):
            self.editor.setSearchSelections(selections)

        # Update scrollbar markers
        if hasattr(self.editor.verticalScrollBar(), 'set_search_markers'):
            self.editor.verticalScrollBar().set_search_markers(self.matches)

    def select_current_match(self):
        if self.current_match_index != -1:
            self._update_match_count_label()
            self.highlight_matches() # Update highlights
            cursor = self.matches[self.current_match_index]
            self.editor.setTextCursor(cursor)
            self.editor.ensureCursorVisible()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.hide()
            self.editor.setFocus()
        else:
            super().keyPressEvent(event)

    def hideEvent(self, event):
        super().hideEvent(event)
        self.matches = []
        self.current_match_index = -1
        self.highlight_matches()
        self.editor.setFocus()
        self.match_count_label.setText("No results")
        self.editor.setPalette(self.original_palette)

    def showEvent(self, event):
        super().showEvent(event)
        self.update_position()

        custom_palette = self.editor.palette()
        # Use a semi-transparent color for the highlight.
        custom_palette.setColor(QPalette.Highlight, QColor(206, 145, 120, 128)) # Semi-transparent orange/brown
        # Explicitly set the highlighted text color to match the default text color.
        custom_palette.setColor(QPalette.HighlightedText, QColor("#D4D4D4"))
        self.editor.setPalette(custom_palette)

    def update_position(self):
        if not self.editor: return
        editor_rect = self.editor.viewport().rect()
        self.move(editor_rect.right() - self.width() - 10, 10)
