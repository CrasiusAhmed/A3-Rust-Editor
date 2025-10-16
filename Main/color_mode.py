import os
from PySide6.QtCore import Qt, QRect, QSize
from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor, QPen, QLinearGradient
from PySide6.QtWidgets import QStyle


class ColorModeManager:
    """
    Encapsulates the Change Color mode behavior and UI interactions.
    This class manipulates the provided window instance (MainWindow) to avoid bloating Rust.py.
    """

    def __init__(self, window):
        self.w = window

    # Public API used by MainWindow wrappers
    def enable_color_change_mode(self):
        """Enable persistent Change Color mode and update toolbar icon to a color swatch."""
        if getattr(self.w, 'color_change_mode_active', False):
            return
        self.w.color_change_mode_active = True
        try:
            # Ensure toolbar is visible and adjust size for larger icon
            self.w.editor_toolbar.show()
            try:
                self.w.editor_toolbar.setFixedHeight(32)
            except Exception:
                pass
            try:
                self.w.run_python_btn.setFixedSize(32, 32)
            except Exception:
                pass
            self.w.run_python_btn.setToolTip("Change Color mode — click hex in editor; click icon to disable")
            # Rewire button action to toggle color mode
            try:
                self.w.run_python_btn.clicked.disconnect()
            except Exception:
                pass
            self.w.run_python_btn.clicked.connect(self.w.toggle_color_change_mode)
            # Set initial color icon
            self.set_color_icon(getattr(self.w, 'current_color_hex', '#1E1F22'))
            # Enable click-to-color on all open editors
            try:
                for ed in list(self.w.open_files.values()):
                    try:
                        ed.enable_change_color_click = True
                    except Exception:
                        pass
            except Exception:
                pass
            # Update icon from current cursor position if available
            self.update_color_icon_from_cursor()
        except Exception:
            pass

    def set_color_icon(self, hex_color: str):
        """Render a rounded color swatch icon on the run button using the given hex color."""
        try:
            size = 30 if getattr(self.w, 'color_change_mode_active', False) else 28
            pix = QPixmap(size, size)
            pix.fill(Qt.transparent)
            p = QPainter(pix)
            p.setRenderHint(QPainter.Antialiasing)
            # Parse hex color with RGBA support (#RRGGBB or #RRGGBBAA with alpha at the end)
            col = None
            try:
                t = (hex_color or '').strip()
                if not t:
                    raise ValueError('empty color')
                if not t.startswith('#'):
                    t = '#' + t
                hp = t[1:]
                a = 255
                if len(hp) == 3:
                    hp = ''.join(ch * 2 for ch in hp)
                if len(hp) == 8:
                    # Treat as RGBA (last two are alpha)
                    r = int(hp[0:2], 16)
                    g = int(hp[2:4], 16)
                    b = int(hp[4:6], 16)
                    a = int(hp[6:8], 16)
                    col = QColor(r, g, b, a)
                elif len(hp) == 6:
                    r = int(hp[0:2], 16)
                    g = int(hp[2:4], 16)
                    b = int(hp[4:6], 16)
                    col = QColor(r, g, b, a)
                else:
                    # Fallback to Qt parser
                    c2 = QColor(t)
                    col = c2 if c2.isValid() else QColor('#1E1F22')
            except Exception:
                col = QColor('#1E1F22')
            # Optional: checkerboard background for transparent colors
            try:
                if col.alpha() < 255:
                    tile = 4
                    rrect = QRect(3, 3, size - 6, size - 6)
                    for yy in range(rrect.top(), rrect.bottom(), tile):
                        for xx in range(rrect.left(), rrect.right(), tile):
                            c2 = QColor(200, 200, 200) if ((xx//tile + yy//tile) % 2 == 0) else QColor(240, 240, 240)
                            p.fillRect(QRect(xx, yy, tile, tile), c2)
            except Exception:
                pass
            # Fill color box
            p.setPen(Qt.NoPen)
            p.setBrush(col)
            p.drawRoundedRect(3, 3, size - 6, size - 6, 4, 4)
            # Gradient border when active
            if getattr(self.w, 'color_change_mode_active', False):
                try:
                    grad = QLinearGradient(0, 0, 0, size)
                    grad.setColorAt(0.0, QColor('#00E5FF'))
                    grad.setColorAt(0.5, QColor('#7C4DFF'))
                    grad.setColorAt(1.0, QColor('#00E5FF'))
                    pen = QPen()
                    pen.setWidth(2)
                    pen.setBrush(grad)
                    p.setBrush(Qt.NoBrush)
                    p.setPen(pen)
                    p.drawRoundedRect(2, 2, size - 4, size - 4, 6, 6)
                except Exception:
                    p.setPen(QPen(QColor('#2C2E33'), 1))
                    p.setBrush(Qt.NoBrush)
                    p.drawRoundedRect(2, 2, size - 4, size - 4, 6, 6)
            p.end()
            self.w.run_python_btn.setIcon(QIcon(pix))
            try:
                self.w.run_python_btn.setIconSize(QSize(size - 2, size - 2))
            except Exception:
                pass
        except Exception:
            pass

    def extract_hex_under_cursor(self, editor) -> str | None:
        """Return a hex color literal under the editor cursor if present (e.g., #RGB, #RRGGBB, #RRGGBBAA)."""
        try:
            import re as _re
            tc = editor.textCursor()
            block = tc.block()
            text = block.text()
            col = tc.position() - block.position()
            allowed = set('#0123456789abcdefABCDEF')
            s = col
            while s > 0 and text[s - 1] in allowed:
                s -= 1
            e = col
            while e < len(text) and text[e] in allowed:
                e += 1
            token = text[s:e]
            if _re.fullmatch(r"#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})", token or ""):
                return token
        except Exception:
            pass
        return None

    def update_color_icon_from_cursor(self):
        """If in Change Color mode, update the toolbar color icon to the hex under the cursor (if any)."""
        if not getattr(self.w, 'color_change_mode_active', False):
            return
        editor = self.w.get_current_editor()
        if not editor:
            return
        try:
            hex_val = self.extract_hex_under_cursor(editor)
            if hex_val:
                self.w.current_color_hex = hex_val.upper()
                self.set_color_icon(self.w.current_color_hex)
        except Exception:
            pass

    def disable_color_change_mode(self):
        """Disable Change Color mode, restore icon and turn off click-to-color."""
        if not getattr(self.w, 'color_change_mode_active', False):
            return
        self.w.color_change_mode_active = False
        try:
            # Restore run action on button to toggle mode by default
            try:
                self.w.run_python_btn.clicked.disconnect()
            except Exception:
                pass
            self.w.run_python_btn.clicked.connect(self.w.toggle_color_change_mode)
            self.w.run_python_btn.setToolTip("Toggle Color Mode (F1)")
            # Restore toolbar and button sizing to defaults
            try:
                self.w.editor_toolbar.setFixedHeight(25)
            except Exception:
                pass
            try:
                self.w.run_python_btn.setFixedSize(28, 28)
            except Exception:
                pass
            # Restore neutral icon (let icon size default)
            self.w.run_python_btn.setIcon(QIcon("img/Brush.png"))
            # Reset icon size to style default (smaller) so it matches the original look
            try:
                small = self.w.style().pixelMetric(QStyle.PM_SmallIconSize)
                self.w.run_python_btn.setIconSize(QSize(small, small))
            except Exception:
                pass
            # Disable click-to-color on all open editors
            try:
                for ed in list(self.w.open_files.values()):
                    try:
                        ed.enable_change_color_click = False
                    except Exception:
                        pass
            except Exception:
                pass
        except Exception:
            pass

    def toggle_color_change_mode(self):
        if getattr(self.w, 'color_change_mode_active', False):
            self.disable_color_change_mode()
        else:
            self.enable_color_change_mode()
