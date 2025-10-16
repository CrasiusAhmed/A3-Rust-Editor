"""
Annotation tools extracted from VisualizationCanvas:
- Tool mode management: cursor, brush, text
- Text annotations editing, selection, moving, resizing
- Brush/text painting identical to original (delegated from canvas)
- RGB color management
- Mouse event hooks to integrate with the canvas
- Coordinate helpers (screen <-> world)

Behavior mirrors the original implementation in Manage/visualization_core.py.
"""
from __future__ import annotations

from typing import Optional, Tuple

from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import (
    QColor, QFont, QFontMetrics, QPainter, QPen, QBrush, QPainterPath, QCursor, QPixmap
)
from PySide6.QtWidgets import QLineEdit
import copy


class AnnotationTools:
    def __init__(self, canvas):
        self.canvas = canvas
        self._eraser_radius_px = 14
        self._eraser_cursor_cache: Optional[QCursor] = None

    # ---------------------- Tool mode / RGB ----------------------
    def set_tool_mode(self, mode: Optional[str]):
        """
        Match original behavior:
        - Accept None, 'cursor', 'brush', 'text'
        - Cancel inline editor when leaving text mode
        - Set cursor icon as per mode
        """
        try:
            if mode not in (None, 'cursor', 'brush', 'text', 'erase'):
                mode = None
            self.canvas.tool_mode = mode
            if mode == 'cursor' or mode is None:
                self.canvas.setCursor(Qt.ArrowCursor)
            elif mode == 'brush':
                self.canvas.setCursor(Qt.CrossCursor)
            elif mode == 'text':
                self.canvas.setCursor(Qt.IBeamCursor)
            elif mode == 'erase':
                try:
                    self.canvas.setCursor(self._get_eraser_cursor())
                except Exception:
                    self.canvas.setCursor(Qt.CrossCursor)
            if mode != 'text':
                self._cancel_text_editor()
            self.canvas.update()
        except Exception:
            pass

    def set_current_color(self, color: QColor, apply_to_selection: bool = False):
        try:
            if apply_to_selection and getattr(self.canvas, '_selected_text', None) is not None:
                self.canvas._selected_text['color'] = color
            else:
                self.canvas.draw_color = color
            self.canvas.update()
        except Exception:
            pass

    def set_rgb(self, r: int, g: int, b: int):
        try:
            r = max(0, min(255, int(r)))
            g = max(0, min(255, int(g)))
            b = max(0, min(255, int(b)))
            self.canvas.draw_color = QColor(r, g, b)
            self.canvas.update()
        except Exception:
            pass

    # ---------------------- Coordinate helpers ----------------------
    def _screen_to_world(self, sx: float, sy: float) -> Tuple[float, float]:
        try:
            wx = (float(sx) - float(self.canvas.camera_x)) / float(self.canvas.camera_zoom)
            wy = (float(sy) - float(self.canvas.camera_y)) / float(self.canvas.camera_zoom)
            return wx, wy
        except Exception:
            return sx, sy

    def _world_to_screen(self, wx: float, wy: float) -> Tuple[float, float]:
        try:
            sx = float(wx) * float(self.canvas.camera_zoom) + float(self.canvas.camera_x)
            sy = float(wy) * float(self.canvas.camera_zoom) + float(self.canvas.camera_y)
            return sx, sy
        except Exception:
            return wx, wy

    # ---------------------- Painter helpers ----------------------
    def _draw_arrowhead(self, painter: QPainter, p_from, p_to, color: QColor):
        try:
            x1, y1 = float(p_from[0]), float(p_from[1])
            x2, y2 = float(p_to[0]), float(p_to[1])
            dx = x2 - x1
            dy = y2 - y1
            import math
            ang = math.atan2(dy, dx)
            size = 10.0
            left = (x2 - size * math.cos(ang - math.pi/6), y2 - size * math.sin(ang - math.pi/6))
            right = (x2 - size * math.cos(ang + math.pi/6), y2 - size * math.sin(ang + math.pi/6))
            pen = QPen(color)
            pen.setWidthF(1.5)
            painter.setPen(pen)
            painter.setBrush(QBrush(color))
            path = QPainterPath()
            path.moveTo(QPointF(x2, y2))
            path.lineTo(QPointF(left[0], left[1]))
            path.lineTo(QPointF(right[0], right[1]))
            path.closeSubpath()
            painter.drawPath(path)
        except Exception:
            pass

    def _get_eraser_cursor(self) -> QCursor:
        if self._eraser_cursor_cache is not None:
            return self._eraser_cursor_cache
        try:
            size = 32
            pm = QPixmap(size, size)
            pm.fill(Qt.transparent)
            p = QPainter(pm)
            p.setRenderHint(QPainter.Antialiasing)
            pen = QPen(QColor(255, 255, 255))
            pen.setWidth(2)
            p.setPen(pen)
            p.setBrush(Qt.NoBrush)
            center = size // 2
            radius = max(2, min(center - 3, int(self._eraser_radius_px)))
            p.drawEllipse(QPointF(center, center), radius, radius)
            p.end()
            cur = QCursor(pm, center, center)
            self._eraser_cursor_cache = cur
            return cur
        except Exception:
            return QCursor(Qt.CrossCursor)

    def commit_pending_edits(self, flush_current_stroke: bool = True):
        """Commit any in-progress annotation edits so Save captures them reliably.
        - If a text editor is open, apply its text to the selected/new text.
        - If a brush stroke is in-progress, finalize it into _strokes.
        """
        try:
            # Commit inline text editor if open
            te = getattr(self.canvas, '_text_editor', None)
            if te is not None:
                try:
                    txt = te.text() or ''
                    # If editing an existing text, update it
                    if getattr(self.canvas, '_editing_text_ref', None) is not None:
                        self.canvas._editing_text_ref['text'] = str(txt)
                    else:
                        # New text: approximate using editor screen position
                        pos = te.pos()
                        sx, sy = int(pos.x()), int(pos.y())
                        wx, wy = self._screen_to_world(sx, sy)
                        color = getattr(self.canvas, 'draw_color', None) or QColor('#FFFFFF')
                        size_hint = 14
                        self.canvas._texts.append({
                            'x': float(wx),
                            'y': float(wy),
                            'text': str(txt),
                            'size': size_hint,
                            'color': color,
                        })
                    # Hide and clear editor
                    try:
                        te.hide()
                    except Exception:
                        pass
                    self.canvas._text_editor = None
                    self.canvas._editing_text_ref = None
                    try:
                        self.canvas.update()
                    except Exception:
                        pass
                except Exception:
                    pass
        except Exception:
            pass
        # Finalize in-progress brush stroke
        try:
            if flush_current_stroke and getattr(self.canvas, '_current_stroke', None):
                s = self.canvas._current_stroke
                pts = s.get('points') or []
                if pts:
                    try:
                        self.canvas._strokes.append(s)
                        # Push undo for adding a stroke (optional)
                        try:
                            self.canvas._push_undo({'type': 'ann_add_stroke', 'stroke': s, 'index': len(self.canvas._strokes) - 1})
                        except Exception:
                            pass
                    except Exception:
                        pass
                self.canvas._current_stroke = None
                try:
                    self.canvas.update()
                except Exception:
                    pass
        except Exception:
            pass

    # ---------------------- Painting (identical to original) ----------------------
    def paint_annotations(self, painter: QPainter):
        # Draw strokes (world space)
        try:
            pen = QPen()
            pen.setCapStyle(Qt.RoundCap)
            pen.setJoinStyle(Qt.RoundJoin)
            for s in self.canvas._strokes:
                c = s.get('color') or QColor('#FFFFFF')
                w = float(s.get('width', 2.0))
                pen.setColor(c)
                pen.setWidthF(w)
                painter.setPen(pen)
                painter.setBrush(Qt.NoBrush)
                pts = s.get('points') or []
                if not pts:
                    continue
                path = QPainterPath()
                path.moveTo(pts[0][0], pts[0][1])
                for px, py in pts[1:]:
                    path.lineTo(px, py)
                painter.drawPath(path)
            # Current stroke preview
            cs = self.canvas._current_stroke
            if cs and (cs.get('points') or []):
                c = cs.get('color') or QColor('#FFFFFF')
                w = float(cs.get('width', 2.0))
                pen.setColor(c)
                pen.setWidthF(w)
                painter.setPen(pen)
                painter.setBrush(Qt.NoBrush)
                pts = cs.get('points')
                path = QPainterPath()
                path.moveTo(pts[0][0], pts[0][1])
                for px, py in pts[1:]:
                    path.lineTo(px, py)
                painter.drawPath(path)
        except Exception:
            pass

        # Draw text annotations (on top)
        try:
            font = QFont("Segoe UI", 14)
            painter.setFont(font)
            for t in self.canvas._texts:
                col = t.get('color') or QColor('#FFFFFF')
                size = int(t.get('size', 14) or 14)
                font.setPointSize(max(6, size))
                painter.setFont(font)
                painter.setPen(QPen(col))
                tx = float(t.get('x', 0.0))
                ty = float(t.get('y', 0.0))
                txt = str(t.get('text', ''))
                painter.drawText(QPointF(tx, ty), txt)
                fm = QFontMetrics(font)
                w = fm.horizontalAdvance(txt)
                # selection underline + resize handle when selected
                if t is self.canvas._selected_text:
                    sel = QColor(col)
                    sel.setAlpha(140)
                    painter.setPen(QPen(sel, 1))
                    # Convert pixel metrics to world units using current zoom
                    z = float(getattr(self.canvas, 'camera_zoom', 1.0) or 1.0)
                    underline_off = 3.0 / z
                    painter.drawLine(QPointF(tx, ty + underline_off), QPointF(tx + (w / z), ty + underline_off))
                    handle_size_px = 15.0
                    handle_size_w = handle_size_px / z
                    hx = tx + (w + 6.0) / z
                    hy = ty - (fm.ascent() / (2.0 * z)) - handle_size_w / 2.0
                    painter.setBrush(QBrush(col))
                    painter.setPen(Qt.NoPen)
                    painter.drawRect(QRectF(hx, hy, handle_size_w, handle_size_w))
        except Exception:
            pass

    # Draw eraser overlay circle in world coordinates when active
        try:
            if getattr(self.canvas, 'tool_mode', None) == 'erase':
                pos = getattr(self.canvas, '_eraser_pos_world', None)
                if pos:
                    z = float(getattr(self.canvas, 'camera_zoom', 1.0) or 1.0)
                    r_w = float(self._eraser_radius_px) / z
                    painter.save()
                    painter.setRenderHint(QPainter.Antialiasing)
                    painter.setPen(QPen(QColor(255, 255, 255, 160), 1))
                    painter.setBrush(QBrush(QColor(255, 255, 255, 40)))
                    painter.drawEllipse(QPointF(float(pos[0]), float(pos[1])), r_w, r_w)
                    painter.restore()
        except Exception:
            pass

    # ---------------------- Text editor helpers ----------------------
    def _cancel_text_editor(self):
        try:
            te: Optional[QLineEdit] = getattr(self.canvas, '_text_editor', None)
            if te is not None:
                te.hide()
            self.canvas._text_editor = None
            self.canvas._editing_text_ref = None
            try:
                # Restore focus to canvas so number shortcuts (1..5) work immediately after Enter
                self.canvas.setFocus(Qt.OtherFocusReason)
            except Exception:
                pass
            self.canvas.update()
        except Exception:
            pass

    def _place_text_editor(self, sx: int, sy: int):
        try:
            # Cancel any existing editor
            self._cancel_text_editor()

            wx, wy = self._screen_to_world(sx, sy)
            edit = QLineEdit(self.canvas)
            edit.setPlaceholderText('Text')
            edit.setStyleSheet(
                "QLineEdit { background: #1E1F22; color: #FFFFFF; border: 1px solid #4A4D51; padding: 4px 8px; border-radius: 6px; }"
            )
            edit.move(int(sx), int(sy))
            edit.resize(200, 26)

            current_text = ''
            size_hint = 14
            color = self.canvas.draw_color or QColor('#FFFFFF')
            if self.canvas._selected_text is not None:
                t = self.canvas._selected_text
                current_text = str(t.get('text', '') or '')
                size_hint = int(t.get('size', 14) or 14)
                color = t.get('color') or color
                self.canvas._editing_text_ref = t
            else:
                self.canvas._editing_text_ref = None

            edit.setText(current_text)
            edit.setFocus()

            def _commit():
                try:
                    txt = edit.text() or ''
                    txt = str(txt)
                    if self.canvas._editing_text_ref is not None:
                        self.canvas._editing_text_ref['text'] = txt
                    else:
                        self.canvas._texts.append({
                            'x': wx,
                            'y': wy,
                            'text': txt,
                            'size': size_hint,
                            'color': color,
                        })
                        # Push undo for adding a text annotation
                        try:
                            self.canvas._push_undo({'type': 'ann_add_text', 'index': len(self.canvas._texts) - 1, 'text': self.canvas._texts[-1]})
                        except Exception:
                            pass
                finally:
                    self._cancel_text_editor()

            edit.editingFinished.connect(_commit)

            self.canvas._text_editor = edit
            edit.show()
        except Exception:
            pass

    def _hit_test_text(self, sx: int, sy: int) -> bool:
        try:
            z = float(getattr(self.canvas, 'camera_zoom', 1.0) or 1.0)
            wx, wy = self._screen_to_world(float(sx), float(sy))
            for t in reversed(self.canvas._texts):
                txt = str(t.get('text', '') or '')
                size = int(t.get('size', 14) or 14)
                font = QFont("Segoe UI", max(6, size))
                fm = QFontMetrics(font)
                tx = float(t.get('x', 0.0))
                ty = float(t.get('y', 0.0))
                # Convert pixel-based metrics into world units for consistent hit testing
                w_w = fm.horizontalAdvance(txt) / z
                h_w = fm.height() / z
                top_w = ty - (fm.ascent() / z)
                rect_w = QRectF(tx, top_w, w_w, h_w)
                if rect_w.contains(QPointF(wx, wy)):
                    self.canvas._selected_text = t
                    return True
            return False
        except Exception:
            return False

    def _hit_test_text_handle(self, sx: int, sy: int):
        try:
            # Screen-space hit test for the square resize handle of any text
            for t in reversed(self.canvas._texts):
                txt = str(t.get('text', '') or '')
                size = int(t.get('size', 14) or 14)
                font = QFont("Segoe UI", max(6, size))
                fm = QFontMetrics(font)
                tx = float(t.get('x', 0.0))
                ty = float(t.get('y', 0.0))
                px, py = self._world_to_screen(tx, ty)
                tw = fm.horizontalAdvance(txt)
                handle_size = 15
                hx = px + tw + 6
                hy = py - fm.ascent() / 2 - handle_size / 2
                if (sx >= hx and sx <= hx + handle_size and sy >= hy and sy <= hy + handle_size):
                    return t
            return None
        except Exception:
            return None

    # ---------------------- Mouse hooks ----------------------
    def handle_mouse_press(self, event) -> bool:
        try:
            if event.button() != Qt.LeftButton:
                return False
            mode = self.canvas.tool_mode
            if mode == 'cursor':
                sx, sy = event.x(), event.y()
                # First, check any handle across all texts
                t = self._hit_test_text_handle(sx, sy)
                if t is not None:
                    self.canvas._selected_text = t
                    size = int(t.get('size', 14) or 14)
                    self.canvas._resizing_text = t
                    self.canvas._resize_start = (sx, float(size))
                    return True
                if self._hit_test_text(sx, sy):
                    # Select and prepare drag (single-click does not edit in cursor mode)
                    wx, wy = self._screen_to_world(sx, sy)
                    tx = float(self.canvas._selected_text.get('x', 0.0))
                    ty = float(self.canvas._selected_text.get('y', 0.0))
                    self.canvas._drag_text = self.canvas._selected_text
                    self.canvas._drag_text_offset = (wx - tx, wy - ty)
                    self.canvas.update()
                    return True
                self.canvas._selected_text = None
                return False

            if mode == 'brush':
                self.canvas.mouse_down = True
                self.canvas.last_mouse_x = event.x()
                self.canvas.last_mouse_y = event.y()
                wx, wy = self._screen_to_world(event.x(), event.y())
                self.canvas._current_stroke = {
                    'points': [(wx, wy)],
                    'color': self.canvas.draw_color or QColor('#FFFFFF'),
                    'width': 2.5,
                }
                self.canvas.update()
                return True

            if mode == 'erase':
                self.canvas.mouse_down = True
                # Snapshot before first erase to support a single undo entry per gesture
                try:
                    self.canvas._erase_before = (copy.deepcopy(self.canvas._strokes), copy.deepcopy(self.canvas._texts))
                except Exception:
                    try:
                        self.canvas._erase_before = (list(self.canvas._strokes or []), list(self.canvas._texts or []))
                    except Exception:
                        self.canvas._erase_before = ([], [])
                self._erase_at(event.x(), event.y())
                self.canvas.update()
                return True

            if mode == 'text':
                sx, sy = event.x(), event.y()
                # If clicking the handle, start resizing instead of creating a new text
                t = self._hit_test_text_handle(sx, sy)
                if t is not None:
                    self.canvas._selected_text = t
                    size = int(t.get('size', 14) or 14)
                    self.canvas._resizing_text = t
                    self.canvas._resize_start = (sx, float(size))
                    return True
                if self._hit_test_text(sx, sy):
                    # Open editor at the selected text position (single-click edit in text mode)
                    try:
                        t = self.canvas._selected_text
                        tx, ty = self._world_to_screen(float(t.get('x', 0.0)), float(t.get('y', 0.0)))
                        self._place_text_editor(int(tx), int(ty))
                    except Exception:
                        self._place_text_editor(sx, sy)
                    self.canvas.update()
                    return True
                self._place_text_editor(sx, sy)
                return True
            return False
        except Exception:
            return False

    def handle_mouse_move(self, event) -> bool:
        try:
            mode = self.canvas.tool_mode
            if mode in ('cursor', 'text'):
                sx, sy = event.x(), event.y()
                if self.canvas._resizing_text is not None:
                    try:
                        start_sx, start_size = self.canvas._resize_start
                        dx = sx - start_sx
                        new_size = max(6.0, float(start_size) + dx / 4.0)
                        self.canvas._resizing_text['size'] = new_size
                        self.canvas.update()
                        return True
                    except Exception:
                        pass
                # Drag move only in cursor mode
                if mode == 'cursor' and self.canvas._drag_text is not None:
                    wx, wy = self._screen_to_world(sx, sy)
                    offx, offy = self.canvas._drag_text_offset
                    self.canvas._drag_text['x'] = wx - offx
                    self.canvas._drag_text['y'] = wy - offy
                    self.canvas.update()
                    return True
                return False
            if mode == 'brush' and self.canvas.mouse_down and self.canvas._current_stroke is not None:
                wx, wy = self._screen_to_world(event.x(), event.y())
                pts = self.canvas._current_stroke.get('points')
                if pts:
                    lx, ly = pts[-1]
                    if abs(wx - lx) > 0.5 or abs(wy - ly) > 0.5:
                        pts.append((wx, wy))
                else:
                    pts.append((wx, wy))
                self.canvas.update()
                return True
            if mode == 'erase':
                wx, wy = self._screen_to_world(event.x(), event.y())
                self.canvas._eraser_pos_world = (wx, wy)
                if self.canvas.mouse_down:
                    self._erase_at(event.x(), event.y())
                    self.canvas.update()
                    return True
                self.canvas.update()
                return True
            return False
        except Exception:
            return False

    def handle_mouse_release(self, event) -> bool:
        try:
            mode = self.canvas.tool_mode
            if mode == 'brush' and self.canvas._current_stroke is not None:
                pts = self.canvas._current_stroke.get('points') or []
                if len(pts) >= 1:
                    s = self.canvas._current_stroke
                    self.canvas._strokes.append(s)
                    # Push undo for adding a stroke
                    try:
                        self.canvas._push_undo({'type': 'ann_add_stroke', 'stroke': s, 'index': len(self.canvas._strokes) - 1})
                    except Exception:
                        pass
                self.canvas._current_stroke = None
                self.canvas.mouse_down = False
                self.canvas.update()
                return True
            if mode == 'cursor':
                self.canvas._drag_text = None
                self.canvas._resizing_text = None
                return False
            if mode == 'erase':
                self.canvas.mouse_down = False
                # Commit a single undo entry for the erase gesture using before/after snapshots
                try:
                    before = getattr(self.canvas, '_erase_before', None)
                    if before is not None:
                        before_strokes, before_texts = before
                        after_strokes = copy.deepcopy(self.canvas._strokes)
                        after_texts = copy.deepcopy(self.canvas._texts)
                        # Only push undo if something actually changed
                        if (before_strokes != after_strokes) or (before_texts != after_texts):
                            self.canvas._push_undo({
                                'type': 'ann_erase',
                                'before_strokes': before_strokes,
                                'after_strokes': after_strokes,
                                'before_texts': before_texts,
                                'after_texts': after_texts,
                            })
                except Exception:
                    pass
                try:
                    self.canvas._erase_before = None
                except Exception:
                    pass
                return True
            if mode == 'text':
                if self.canvas._resizing_text is not None:
                    self.canvas._resizing_text = None
                    return True
                return False
            return False
        except Exception:
            return False

    def handle_mouse_double_click(self, event) -> bool:
        try:
            if self.canvas.tool_mode in ('cursor', 'text'):
                if self._hit_test_text(event.x(), event.y()):
                    try:
                        tx, ty = self._world_to_screen(
                            float(self.canvas._selected_text.get('x', 0.0)),
                            float(self.canvas._selected_text.get('y', 0.0))
                        )
                        self._place_text_editor(int(tx), int(ty))
                    except Exception:
                        # Do not create a new text on double-click
                        pass
                    return True
            return False
        except Exception:
            return False

    # ---------------------- Erase helpers ----------------------
    def _erase_at(self, sx: int, sy: int):
        try:
            z = float(getattr(self.canvas, 'camera_zoom', 1.0) or 1.0)
            radius_w = float(self._eraser_radius_px) / z
            wx, wy = self._screen_to_world(float(sx), float(sy))
            self.canvas._eraser_pos_world = (wx, wy)
            new_strokes = []
            for s in getattr(self.canvas, '_strokes', []) or []:
                pts = list(s.get('points') or [])
                if not pts:
                    continue
                # Build segments that remain outside the erase radius
                seg = []
                segments = []
                for (px, py) in pts:
                    dx = px - wx
                    dy = py - wy
                    if (dx * dx + dy * dy) > (radius_w * radius_w):
                        seg.append((px, py))
                    else:
                        if len(seg) >= 2:
                            segments.append(seg)
                        seg = []
                if len(seg) >= 2:
                    segments.append(seg)
                if not segments:
                    # Entire stroke erased within radius; skip adding
                    continue
                # Convert segments into stroke objects preserving style
                for seg_pts in segments:
                    new_strokes.append({
                        'points': seg_pts,
                        'color': s.get('color'),
                        'width': s.get('width', 2.5),
                    })
            # Replace strokes with remaining segments
            self.canvas._strokes = new_strokes
            # Remove text annotations intersecting eraser circle
            try:
                kept_texts = []
                for t in getattr(self.canvas, '_texts', []) or []:
                    txt = str(t.get('text', '') or '')
                    size = int(t.get('size', 14) or 14)
                    font = QFont('Segoe UI', max(6, size))
                    fm = QFontMetrics(font)
                    tx = float(t.get('x', 0.0))
                    ty = float(t.get('y', 0.0))
                    w_w = fm.horizontalAdvance(txt) / z
                    h_w = fm.height() / z
                    left = tx
                    top = ty - (fm.ascent() / z)
                    right = left + w_w
                    bottom = top + h_w
                    # Find closest point on the text rect to the eraser center
                    cx = max(left, min(wx, right))
                    cy = max(top, min(wy, bottom))
                    dx = cx - wx
                    dy = cy - wy
                    if (dx * dx + dy * dy) > (radius_w * radius_w):
                        kept_texts.append(t)
                self.canvas._texts = kept_texts
            except Exception:
                pass
        except Exception:
            pass
