from __future__ import annotations

import math
import random
from typing import List, Optional

from PySide6.QtCore import Qt, QTimer, QRectF, QPointF
from PySide6.QtGui import QColor, QPainter, QPen, QBrush, QFont
from PySide6.QtWidgets import QWidget

# Simple color palette
PALETTE = [
    '#569CD6', '#4EC9B0', '#C586C0', '#DCDCAA', '#CE9178', '#9CDCFE', '#D16969', '#6A9955'
]

class _Chip:
    def __init__(self, text: str, color: QColor):
        self.text = text
        self.base_color = color
        self.life = 2.0  # seconds total
        self.phase = 0.0
        self.opacity = 1.0

class HUDOverlay(QWidget):
    """
    Floating HUD that shows pulsing border chips for function calls.
    Independent of the graph/canvas logic.
    """
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool)
        self._chips: List[_Chip] = []

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(16)

        # Sizing
        self._chip_w = 260
        self._chip_h = 36
        self._chip_gap = 8
        self._max_chips = 8

        self.setFixedSize(self._chip_w + 16, (self._chip_h + self._chip_gap) * self._max_chips + 16)

    def flash(self, label: str, color: Optional[QColor] = None):
        if not color:
            # Deterministic color by hash
            idx = abs(hash(label)) % len(PALETTE)
            color = QColor(PALETTE[idx])
        # Reuse if same label exists (refresh life)
        for c in self._chips:
            if c.text == label:
                c.life = 2.0
                c.phase = 0.0
                return
        chip = _Chip(label, color)
        self._chips.insert(0, chip)
        if len(self._chips) > self._max_chips:
            self._chips = self._chips[:self._max_chips]
        self.update()

    def _tick(self):
        dt = 0.016
        changed = False
        for c in list(self._chips):
            c.life -= dt
            c.phase += 2.0 * math.pi * 2.0 * dt  # ~2Hz pulse
            c.opacity = max(0.0, min(1.0, 0.5 * (1.0 + math.sin(c.phase))))
            if c.life <= 0.0:
                self._chips.remove(c)
                changed = True
            else:
                changed = True
        if changed:
            self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        # Background (subtle)
        p.fillRect(self.rect(), QColor(0, 0, 0, 0))

        x = 8
        y = 8
        for c in self._chips:
            rect = QRectF(x, y, self._chip_w, self._chip_h)

            # Base box
            p.setPen(Qt.NoPen)
            p.setBrush(QBrush(QColor(30, 30, 34, 200)))
            p.drawRoundedRect(rect, 8, 8)

            # Border pulse
            border = QColor(c.base_color)
            border.setAlpha(int(40 + 180 * c.opacity))
            pen = QPen(border, 4)
            p.setPen(pen)
            p.setBrush(Qt.NoBrush)
            p.drawRoundedRect(rect, 8, 8)

            # Text
            p.setPen(QColor(224, 226, 230))
            f = QFont('Segoe UI', 10)
            f.setBold(True)
            p.setFont(f)
            p.drawText(rect.adjusted(10, 0, -10, 0), Qt.AlignVCenter | Qt.AlignLeft, c.text)

            y += self._chip_h + self._chip_gap

        p.end()
