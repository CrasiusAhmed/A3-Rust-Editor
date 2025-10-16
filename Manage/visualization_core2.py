    
import os
import math
import json
import time
import socket
import threading
from typing import Optional

from PySide6.QtCore import Qt, QRectF, QPointF, QTimer
from PySide6.QtGui import QPainter, QPen, QBrush, QColor, QFont, QFontMetrics, QPixmap, QLinearGradient, QRadialGradient, QMouseEvent, QWheelEvent, QKeyEvent
from PySide6.QtWidgets import QWidget, QFileDialog

try:
    from .document_io import SaveLoadManager
except Exception:
    SaveLoadManager = None

# Safe no-op trace logger to avoid NameError during imports/binding
# visualization_core will provide its own _trace_log; this fallback prevents crashes
# if the base logger isn't accessible at this import moment.
def _trace_log(msg: str):
    return

from .data_analysis import DARK_THEME, FunctionNode, Connection, FunctionAnalyzer
from .ui_components import ResizablePanel, ResizableCodeViewer

# ---------------------- Undo/Redo ----------------------
def _push_undo(self, action: dict):
    try:
        self._undo_stack.append(action)
        self._redo_stack.clear()
    except Exception:
        pass

def undo(self):
    if not self._undo_stack:
        return
    action = self._undo_stack.pop()
    t = action.get('type')
    if t == 'add_connection_node':
        # Remove the node and connection that were added
        node = action.get('node')
        connection = action.get('connection')
        if node:
            try:
                self.nodes.remove(node)
            except Exception:
                pass
        if connection:
            try:
                self.connections.remove(connection)
            except Exception:
                pass
        # Rebuild index
        self._node_by_name = {}
        for n in self.nodes:
            self._index_node(n)
        self._redo_stack.append(action)
        self.update()
    elif t == 'hide_connections':
        for c in action.get('items', []):
            try:
                setattr(c, 'hidden', False)
            except Exception:
                pass
        self._redo_stack.append(action)
        self.update()
    elif t == 'delete_node':
        node = action.get('node')
        conns = action.get('connections', [])
        if node:
            try:
                self.nodes.append(node)
            except Exception:
                pass
        for c in conns:
            try:
                if c not in self.connections:
                    self.connections.append(c)
            except Exception:
                pass
        # Rebuild index
        self._node_by_name = {}
        for n in self.nodes:
            self._index_node(n)
        self._redo_stack.append(action)
        self.update()
    elif t == 'move_node':
        node = action.get('node')
        frm = action.get('from')
        if node and isinstance(frm, (tuple, list)) and len(frm) == 2:
            try:
                node.x, node.y = float(frm[0]), float(frm[1])
                node.original_x, node.original_y = node.x, node.y
            except Exception:
                pass
        self._redo_stack.append(action)
        self.update()
    elif t == 'ann_add_stroke':
        # Remove the stroke that was added
        idx = int(action.get('index', -1))
        try:
            if 0 <= idx < len(self._strokes):
                self._strokes.pop(idx)
            else:
                # fallback remove last
                if self._strokes:
                    self._strokes.pop()
        except Exception:
            pass
        self._redo_stack.append(action)
        self.update()
    elif t == 'ann_add_text':
        # Remove the text that was added
        idx = int(action.get('index', -1))
        try:
            if 0 <= idx < len(self._texts):
                self._texts.pop(idx)
            else:
                if self._texts:
                    self._texts.pop()
        except Exception:
            pass
        self._redo_stack.append(action)
        self.update()
    elif t == 'ann_erase':
        # Restore pre-erase state
        try:
            before_strokes = action.get('before_strokes')
            before_texts = action.get('before_texts')
            if before_strokes is not None:
                self._strokes = list(before_strokes)
            if before_texts is not None:
                self._texts = list(before_texts)
        except Exception:
            pass
        self._redo_stack.append(action)
        self.update()

def redo(self):
    if not self._redo_stack:
        return
    action = self._redo_stack.pop()
    t = action.get('type')
    if t == 'add_connection_node':
        # Re-add the node and connection that were removed
        node = action.get('node')
        connection = action.get('connection')
        if node:
            try:
                self.nodes.append(node)
            except Exception:
                pass
        if connection:
            try:
                self.connections.append(connection)
            except Exception:
                pass
        # Rebuild index
        self._node_by_name = {}
        for n in self.nodes:
            self._index_node(n)
        self._undo_stack.append(action)
        self.update()
    elif t == 'hide_connections':
        for c in action.get('items', []):
            try:
                setattr(c, 'hidden', True)
            except Exception:
                pass
        self._undo_stack.append(action)
        self.update()
    elif t == 'delete_node':
        node = action.get('node')
        if node:
            try:
                self.nodes.remove(node)
            except Exception:
                pass
        # Remove its connections
        conns = action.get('connections', [])
        try:
            self.connections = [c for c in self.connections if c not in conns]
        except Exception:
            pass
        # Rebuild index
        self._node_by_name = {}
        for n in self.nodes:
            self._index_node(n)
        self._undo_stack.append(action)
        self.update()
    elif t == 'move_node':
        node = action.get('node')
        to = action.get('to')
        if node and isinstance(to, (tuple, list)) and len(to) == 2:
            try:
                node.x, node.y = float(to[0]), float(to[1])
                node.original_x, node.original_y = node.x, node.y
            except Exception:
                pass
        self._undo_stack.append(action)
        self.update()
    elif t == 'ann_add_stroke':
        # Re-add the stroke at recorded index
        stroke = action.get('stroke')
        idx = int(action.get('index', len(self._strokes)))
        try:
            if stroke is not None:
                if 0 <= idx <= len(self._strokes):
                    self._strokes.insert(idx, stroke)
                else:
                    self._strokes.append(stroke)
        except Exception:
            pass
        self._undo_stack.append(action)
        self.update()
    elif t == 'ann_add_text':
        # Re-add the text at recorded index
        text_obj = action.get('text')
        idx = int(action.get('index', len(self._texts)))
        try:
            if text_obj is not None:
                if 0 <= idx <= len(self._texts):
                    self._texts.insert(idx, text_obj)
                else:
                    self._texts.append(text_obj)
        except Exception:
            pass
        self._undo_stack.append(action)
        self.update()
    elif t == 'ann_erase':
        # Restore post-erase state
        try:
            after_strokes = action.get('after_strokes')
            after_texts = action.get('after_texts')
            if after_strokes is not None:
                self._strokes = list(after_strokes)
            if after_texts is not None:
                self._texts = list(after_texts)
        except Exception:
            pass
        self._undo_stack.append(action)
        self.update()

def _draw_node(self, painter: QPainter, node: FunctionNode):
    """Draw a function node"""
    # Check if this node is the source of a connection drag - make it semi-transparent
    base_opacity = node.opacity
    if getattr(self, '_connection_drag_mode', False):
        source_node = getattr(self, '_connection_source_node', None)
        if source_node is node:
            base_opacity = 0.7  # Make source node semi-transparent during drag
    
    painter.setOpacity(base_opacity)
    
    # Check if this is the special Add tool node
    is_add_tool = getattr(node, 'is_add_tool', False)
    
    if is_add_tool:
        # Special rendering for Add tool: just border and icon, no 3D background
        icon_size = 80 * node.scale
        border_padding = 20 * node.scale
        
        # Calculate box size
        width = icon_size + border_padding * 2
        height = icon_size + border_padding * 2
        
        x = node.x - width / 2
        y = node.y - height / 2
        
        # Draw border only (no background)
        border_radius = 15
        rect = QRectF(x, y, width, height)
        
        # Determine border color based on state
        if node.selected or node.highlighted:
            border_color = QColor(node.color)
            border_width = 3
        else:
            border_color = QColor('#4A4D51')
            border_width = 2
        
        painter.setPen(QPen(border_color, border_width))
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(rect, border_radius, border_radius)
        
        # Draw the Add.png icon in center
        if node.icon_path:
            pixmap = QPixmap(node.icon_path)
            icon_x = node.x - icon_size / 2
            icon_y = node.y - icon_size / 2
            target_rect = QRectF(icon_x, icon_y, icon_size, icon_size)
            painter.drawPixmap(target_rect, pixmap, pixmap.rect())
        
        painter.setOpacity(1.0)
        return
    
    # Check if this is a custom content node (text/image/video)
    is_custom_content = False
    content_type = None
    try:
        if hasattr(node, 'data') and isinstance(node.data, dict):
            content_type = node.data.get('content_type')
            if content_type in ('text', 'image', 'video'):
                is_custom_content = True
    except Exception:
        pass
    
    if is_custom_content:
        # Custom content node: square box with only icon, no text
        icon_size = 60 * node.scale
        border_padding = 20 * node.scale
        
        # Make it square
        width = icon_size + border_padding * 2
        height = width  # Same as width for square
        
        x = node.x - width / 2
        y = node.y - height / 2
        
        # Draw main box with 3D effect
        self._draw_3d_box(painter, x, y, width, height, node)
        
        # Draw icon only (no text) - preserve aspect ratio
        icon_map = {
            'text': 'img/Connection2.png',
            'image': 'img/Manage_Image.png',
            'video': 'img/Manage_Video.png'
        }
        icon_path = icon_map.get(content_type)
        if icon_path and os.path.exists(icon_path):
            pixmap = QPixmap(icon_path)
            if not pixmap.isNull():
                # Calculate scaled dimensions while preserving aspect ratio
                orig_w = pixmap.width()
                orig_h = pixmap.height()
                aspect_ratio = orig_w / orig_h if orig_h > 0 else 1.0
                
                # Fit within icon_size
                if orig_w > orig_h:
                    scaled_w = icon_size
                    scaled_h = icon_size / aspect_ratio
                else:
                    scaled_h = icon_size
                    scaled_w = icon_size * aspect_ratio
                
                # Center the image
                icon_x = node.x - scaled_w / 2
                icon_y = node.y - scaled_h / 2
                
                # Draw directly - let painter handle smooth scaling
                target_rect = QRectF(icon_x, icon_y, scaled_w, scaled_h)
                painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
                painter.drawPixmap(target_rect, pixmap, pixmap.rect())
    else:
        # Normal node rendering
        # Calculate dimensions based on text
        font = QFont("Arial", 14)
        font.setBold(True)
        fm = QFontMetrics(font)
        text_width = fm.horizontalAdvance(node.name)
        
        width = max(100, min(text_width + 40, 300)) * node.scale
        height = (fm.height() + 20) * self.height_multiplier * node.scale
        
        # If it's a main script node, increase its height to accommodate the icon
        if node.icon_path:
            height = max(height, (self.main_node_icon_size + fm.height() + 40) * node.scale)
        
        x = node.x - width / 2
        y = node.y - height / 2
        
        # Draw main box with 3D effect
        self._draw_3d_box(painter, x, y, width, height, node)
        
        # Draw status circle
        circle_radius = 8
        circle_x = node.x - (width / 2) - circle_radius - 8
        circle_y = node.y
        self._draw_3d_circle(painter, circle_x, circle_y, circle_radius, node.color)
        
        # Draw text
        self._draw_node_text(painter, node, width, height)
    
    painter.setOpacity(1.0)
    

def _draw_3d_box(self, painter: QPainter, x: float, y: float, 
                width: float, height: float, node: FunctionNode):
    """Draw 3D inset box effect matching the original design"""
    rect = QRectF(x, y, width, height)
    border_radius = 15
    
    # Base shadow (drop shadow)
    shadow_rect = QRectF(x + 3, y + 6, width, height)
    painter.setBrush(QBrush(QColor(0, 0, 0, 100)))
    painter.setPen(Qt.NoPen)
    painter.drawRoundedRect(shadow_rect, border_radius, border_radius)
    
    # Main gradient (matching original)
    gradient = QLinearGradient(x, y, x, y + height)
    try:
        is_err = bool(getattr(node, 'error_state', None) or (isinstance(getattr(node, 'data', None), dict) and (node.data.get('error_line') or node.data.get('error_msg'))))
    except Exception:
        is_err = False
    if is_err:
        gradient.setColorAt(0, QColor('#5a1e1e'))
        gradient.setColorAt(1, QColor('#2a0e0e'))
    else:
        gradient.setColorAt(0, QColor('#3a3d41'))
        gradient.setColorAt(1, QColor('#202124'))
    
    painter.setBrush(QBrush(gradient))
    painter.setPen(Qt.NoPen)
    painter.drawRoundedRect(rect, border_radius, border_radius)
    
    # Inner highlight (top-left inset)
    painter.save()
    painter.setClipRect(rect)
    highlight_gradient = QLinearGradient(x, y, x + width * 0.8, y + height * 0.8)
    highlight_gradient.setColorAt(0, QColor(255, 255, 255, 25))
    highlight_gradient.setColorAt(1, QColor(255, 255, 255, 0))
    painter.setBrush(QBrush(highlight_gradient))
    painter.setPen(Qt.NoPen)
    painter.drawRoundedRect(rect, border_radius, border_radius)
    painter.restore()
    
    # Inner shadow (bottom-right inset)
    painter.save()
    painter.setClipRect(rect)
    shadow_gradient = QLinearGradient(x + width, y + height, x, y)
    shadow_gradient.setColorAt(0, QColor(0, 0, 0, 76))
    shadow_gradient.setColorAt(1, QColor(0, 0, 0, 0))
    painter.setBrush(QBrush(shadow_gradient))
    painter.setPen(Qt.NoPen)
    painter.drawRoundedRect(rect, border_radius, border_radius)
    painter.restore()
    
    # Border
    is_active = bool(getattr(node, '_active_on', False))
    # Determine error-state
    try:
        is_err = bool(getattr(node, 'error_state', None) or (isinstance(getattr(node, 'data', None), dict) and (node.data.get('error_line') or node.data.get('error_msg'))))
    except Exception:
        is_err = False
    if is_active:
        border_width = 4
        # Use the node's own color for active border
        border_color = QColor(node.color)
        border_color.setAlpha(255)
    else:
        border_width = 2 if node.selected else (1.5 if node.highlighted else 1)
        if is_err:
            if node.selected:
                border_color = QColor('#c23a3a')  # reddish border on selection for errors
            elif node.highlighted:
                border_color = QColor('#a83232')  # subtle red when hovered/highlighted
            else:
                border_color = QColor(255, 255, 255, 25)
        else:
            if node.selected:
                border_color = QColor(node.color)
            elif node.highlighted:
                border_color = QColor(node.color).lighter(150)
            else:
                border_color = QColor(255, 255, 255, 25)
    
    painter.setPen(QPen(border_color, border_width))
    painter.setBrush(Qt.NoBrush)
    painter.drawRoundedRect(rect, border_radius, border_radius)

    # Blink overlay (high-contrast, thick border) when guided
    if getattr(node, 'blink_opacity', 0.0) > 0.0:
        phase = node.blink_opacity
        strong_color = QColor(node.color).lighter(180)
        strong_color.setAlpha(int(230 * phase + 25))
        # Thick inner border
        pen = QPen(strong_color, 6)
        pen.setCapStyle(Qt.RoundCap)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(rect, border_radius, border_radius)
        # Outer glow ring
        glow = QColor(strong_color)
        glow.setAlpha(int(120 * phase))
        painter.setPen(QPen(glow, 10))
        painter.drawRoundedRect(rect, border_radius, border_radius)
    
    # Outer glow: use strong glow when runtime-active, otherwise standard selection glow
    if getattr(node, '_active_on', False):
        painter.save()
        glow_color = QColor(node.color).lighter(150)
        glow_color.setAlpha(150)
        for i in range(2):
            glow_width = border_width + i * 2
            glow_alpha = 150 - i * 60
            c = QColor(glow_color)
            c.setAlpha(max(0, glow_alpha))
            painter.setPen(QPen(c, glow_width))
            painter.drawRoundedRect(rect, border_radius, border_radius)
        painter.restore()
    elif (node.selected or node.highlighted):
        painter.save()
        # If error-state, tint the selection/highlight glow red
        try:
            is_err = bool(getattr(node, 'error_state', None) or (isinstance(getattr(node, 'data', None), dict) and (node.data.get('error_line') or node.data.get('error_msg'))))
        except Exception:
            is_err = False
        glow_color = QColor('#c23a3a') if is_err else QColor(node.color)
        glow_color.setAlpha(180)
        
        # Create glow effect
        for i in range(5):
            glow_width = border_width + i * 2
            glow_alpha = 180 - i * 30
            glow_color.setAlpha(max(0, glow_alpha))
            painter.setPen(QPen(glow_color, glow_width))
            painter.drawRoundedRect(rect, border_radius, border_radius)
        painter.restore()
    
    # Subtle 1px border to match toolbar buttons
    try:
        subtle = QColor(DARK_THEME['border'])
    except Exception:
        subtle = QColor('#4A4D51')
    painter.setPen(QPen(subtle, 1.0))
    painter.setBrush(Qt.NoBrush)
    painter.drawRoundedRect(rect, border_radius, border_radius)
    

def _draw_3d_circle(self, painter: QPainter, x: float, y: float, 
                    radius: float, color_str: str):
    """Draw 3D circle with gradient"""
    color = QColor(color_str)
    
    # Create radial gradient
    gradient = QRadialGradient(x - radius * 0.3, y - radius * 0.3, radius)
    gradient.setColorAt(0, QColor(255, 255, 255, 50))
    gradient.setColorAt(0.7, color)
    gradient.setColorAt(1, color.darker(130))
    
    painter.setBrush(QBrush(gradient))
    painter.setPen(QPen(QColor(255, 255, 255, 75), 2))
    painter.drawEllipse(QPointF(x, y), radius, radius)
    

def _draw_port_dots(self, painter: QPainter, box_x: float, box_y: float, box_w: float, box_h: float, node: FunctionNode):
    """Draw small input/output port dots like n8n on left/right centers."""
    painter.save()
    try:
        port_r = 6.0
        offset = 10.0
        cy = node.y
        left_cx = box_x - offset - port_r
        right_cx = box_x + box_w + offset + port_r

        # Base style
        base_fill = QColor('#3a3d41')
        base_border = QColor('#9AA0A6')
        if node.selected or node.highlighted:
            base_fill = base_fill.lighter(120)
            try:
                base_border = QColor(DARK_THEME['accent'])
            except Exception:
                base_border = base_border.lighter(140)

        def draw_port(cx: float, cy: float):
            # Fill
            painter.setPen(Qt.NoPen)
            grad = QRadialGradient(QPointF(cx - port_r * 0.35, cy - port_r * 0.35), port_r)
            grad.setColorAt(0, QColor(255, 255, 255, 40))
            grad.setColorAt(1, base_fill)
            painter.setBrush(QBrush(grad))
            painter.drawEllipse(QPointF(cx, cy), port_r, port_r)
            # Border
            painter.setBrush(Qt.NoBrush)
            painter.setPen(QPen(base_border, 1.6))
            painter.drawEllipse(QPointF(cx, cy), port_r, port_r)

        draw_port(left_cx, cy)
        draw_port(right_cx, cy)
    except Exception:
        pass
    painter.restore()
    

def _draw_node_text(self, painter: QPainter, node: FunctionNode,
                    box_width: float, box_height: float):
    """Draw node text with proper formatting and icon."""
    painter.setPen(QPen(QColor(DARK_THEME['text_primary'])))

    font_size = 14
    font = QFont("Segoe UI", font_size)
    font.setBold(True)
    painter.setFont(font)

    y_offset = 0
    # If an icon exists, draw it and adjust text position
    if node.icon_path:
        # Load the original pixmap without pre-scaling
        pixmap = QPixmap(node.icon_path)
        
        # Define the target area for the icon in world coordinates
        icon_width = self.main_node_icon_size
        icon_height = self.main_node_icon_size
        icon_x = node.x - icon_width / 2
        icon_y = node.y - box_height / 2 + 15  # Padding from top

        target_rect = QRectF(icon_x, icon_y, icon_width, icon_height)
        
        # Let the painter handle the scaling for better quality on zoom
        painter.drawPixmap(target_rect, pixmap, pixmap.rect())

        y_offset = icon_height + 10  # Space between icon and text

    # The rectangle for the text, with some padding
    text_rect = QRectF(node.x - box_width / 2 + 10,
                        node.y - box_height / 2 + 10 + y_offset,
                        box_width - 20,
                        box_height - 20 - y_offset)

    # Draw the text with word wrapping and centered alignment
    painter.drawText(text_rect, Qt.AlignCenter | Qt.TextWordWrap, node.name)

    # Draw arguments when selected or hovered
    if (node.selected or node.hovered) and node.data.get('args'):
        args = node.data['args'][:3]  # Show first 3 args
        args_text = f"({', '.join(args)}{'...' if len(node.data['args']) > 3 else ''})"

        font.setPointSize(max(int(font_size * 0.7), 8))
        font.setBold(False)
        painter.setFont(font)
        painter.setPen(QPen(QColor('#A9A9A9')))

        args_y = text_rect.bottom() - font_size * 1.2 # Position below the main text
        args_rect = QRectF(node.x - box_width / 2, args_y, box_width, font_size)
        painter.drawText(args_rect, Qt.AlignCenter, args_text)
        

def mousePressEvent(self, event: QMouseEvent):
    """Handle mouse press events"""
    if event.button() == Qt.LeftButton:
        # Check if selection box mode is active
        if getattr(self, '_selection_box_mode', False):
            # Start selection box drag
            self._selection_box_active = True
            self._selection_box_start = (event.x(), event.y())
            self._selection_box_end = (event.x(), event.y())
            self._selection_box_nodes = []
            self.update()
            return
        
        # Delegate to annotation tools first
        try:
            if self.annotations.handle_mouse_press(event):
                return
        except Exception:
            pass
        
        # Check for node at position FIRST
        clicked_node = self.get_node_at_position(event.x(), event.y())
        
        # Check if Ctrl is held down for connection dragging
        if (event.modifiers() & Qt.ControlModifier) and clicked_node:
            # BLOCK connection dragging for text/image/video content nodes
            is_content_node = False
            try:
                if hasattr(clicked_node, 'data') and isinstance(clicked_node.data, dict):
                    content_type = clicked_node.data.get('content_type')
                    if content_type in ('text', 'image', 'video'):
                        is_content_node = True
            except Exception:
                pass
            
            # Only start connection drag if it's NOT a content node
            if not is_content_node:
                # Start connection drag mode with Ctrl+Click
                self._connection_drag_mode = True
                self._connection_source_node = clicked_node
                self._connection_drag_start = (event.x(), event.y())
                self._connection_drag_current = (event.x(), event.y())
                self.mouse_down = False  # Don't set mouse_down for connection dragging
                self.dragging = False
                self._drag_node = None
                self.setCursor(Qt.CrossCursor)
                return
        
        # Default canvas handling - allow normal selection/dragging
        self.mouse_down = True
        self.last_mouse_x = event.x()
        self.last_mouse_y = event.y()
        
        if clicked_node:
            self._drag_node = clicked_node
            self._drag_start_pos = (clicked_node.x, clicked_node.y)
            self._node_moved = False
            self.select_node(clicked_node)
        else:
            self.select_node(None)
            self.dragging = True
            self.setCursor(Qt.ClosedHandCursor)
            self._drag_node = None
            self._drag_start_pos = None
            self._node_moved = False
            

def mouseMoveEvent(self, event: QMouseEvent):
    """Handle mouse move events"""
    # Handle Blender-style transform mode
    if getattr(self, '_transform_mode', None):
        self._update_transform(event.x(), event.y())
        return
    
    # Handle selection box mode
    if getattr(self, '_selection_box_active', False):
        self._update_selection_box((event.x(), event.y()))
        return
    
    try:
        if self.annotations.handle_mouse_move(event):
            return
    except Exception:
        pass
    
    # Handle connection drag mode
    if getattr(self, '_connection_drag_mode', False):
        self._connection_drag_current = (event.x(), event.y())
        self.update()
        return
    
    # Update hovered node and cursor
    new_hovered = self.get_node_at_position(event.x(), event.y())
    if new_hovered != self.hovered_node:
        self.hovered_node = new_hovered
    
    # Update cursor based on position
    if not self.mouse_down:
        if new_hovered and self._is_near_node_border(event.x(), event.y(), new_hovered):
            # Near border - show grab cursor for connection dragging
            self.setCursor(Qt.OpenHandCursor)
        elif new_hovered:
            # On node but not near border - show pointing hand for selection/moving
            self.setCursor(Qt.PointingHandCursor)
        else:
            # Not on any node - show arrow
            self.setCursor(Qt.ArrowCursor)
    
    if self.mouse_down:
        if self.selected_node and not self.dragging:
            world_x = (event.x() - self.camera_x) / self.camera_zoom
            world_y = (event.y() - self.camera_y) / self.camera_zoom
            self.selected_node.x = world_x
            self.selected_node.y = world_y
            self.selected_node.original_x = world_x
            self.selected_node.original_y = world_y
            try:
                if self._drag_node is self.selected_node and self._drag_start_pos:
                    if abs(world_x - float(self._drag_start_pos[0])) > 0.5 or abs(world_y - float(self._drag_start_pos[1])) > 0.5:
                        self._node_moved = True
            except Exception:
                pass
        elif self.dragging:
            dx = event.x() - self.last_mouse_x
            dy = event.y() - self.last_mouse_y
            self.camera_x += dx
            self.camera_y += dy
            self.last_mouse_x = event.x()
            self.last_mouse_y = event.y()
    self.update()
    

def mouseReleaseEvent(self, event: QMouseEvent):
    """Handle mouse release events"""
    # Handle Blender-style transform mode confirmation (left click) or cancel (right click)
    if getattr(self, '_transform_mode', None):
        if event.button() == Qt.LeftButton:
            self._confirm_transform()
        elif event.button() == Qt.RightButton:
            self._cancel_transform()
        return
    
    # Handle selection box mode completion
    if getattr(self, '_selection_box_active', False):
        self._finalize_selection_box()
        return
    
    try:
        if self.annotations.handle_mouse_release(event):
            return
    except Exception:
        pass
    
    # Handle connection drag mode completion
    if getattr(self, '_connection_drag_mode', False):
        self._connection_drag_mode = False
        # Check if we released over empty space (not on a node)
        target_node = self.get_node_at_position(event.x(), event.y())
        if not target_node:
            # User wants to create a new box at this location
            # Convert screen to world coordinates
            world_x = (event.x() - self.camera_x) / self.camera_zoom
            world_y = (event.y() - self.camera_y) / self.camera_zoom
            # Emit signal for the host to handle (will be implemented in next step)
            try:
                if hasattr(self, 'connection_drag_completed'):
                    self.connection_drag_completed.emit(self._connection_source_node, world_x, world_y)
            except Exception:
                pass
        # Reset connection drag state
        self._connection_source_node = None
        self._connection_drag_start = None
        self._connection_drag_current = None
        self.setCursor(Qt.ArrowCursor)
        self.update()
        return
    
    self.mouse_down = False
    self.dragging = False
    self.setCursor(Qt.ArrowCursor)
    try:
        if self._drag_node and self._drag_start_pos and self._node_moved:
            end_pos = (float(self._drag_node.x), float(self._drag_node.y))
            start_pos = (float(self._drag_start_pos[0]), float(self._drag_start_pos[1]))
            if abs(end_pos[0] - start_pos[0]) > 0.01 or abs(end_pos[1] - start_pos[1]) > 0.01:
                self._push_undo({'type': 'move_node', 'node': self._drag_node, 'from': start_pos, 'to': end_pos})
    except Exception:
        pass
    finally:
        self._drag_node = None
        self._drag_start_pos = None
        self._node_moved = False
    

def mouseDoubleClickEvent(self, event: QMouseEvent):
    """Handle double click events"""
    try:
        if self.annotations.handle_mouse_double_click(event):
            return
    except Exception:
        pass
    clicked_node = self.get_node_at_position(event.x(), event.y())
    if clicked_node:
        # Check if this is the Add tool node - don't zoom, just emit signal
        is_add_tool = getattr(clicked_node, 'is_add_tool', False)
        
        self.node_double_clicked.emit(clicked_node)
        
        # Only zoom/focus if it's NOT the Add tool
        if not is_add_tool:
            self.focus_on_node(clicked_node)
    else:
        self.reset_view()
        

def wheelEvent(self, event: QWheelEvent):
    """Handle wheel events for zooming, but ignore if over a child panel."""
    # Check if the event position is inside any visible child widget that is a panel
    for child in self.findChildren(QWidget):
        if isinstance(child, (ResizablePanel, ResizableCodeViewer)):
            if child.isVisible() and child.geometry().contains(event.position().toPoint()):
                event.ignore()
                return

    factor = 1.4 if event.angleDelta().y() > 0 else 0.7
    new_zoom = max(0.1, min(3.0, self.camera_zoom * factor))
    
    # Zoom towards mouse position
    mouse_x = event.position().x()
    mouse_y = event.position().y()
    
    world_x = (mouse_x - self.camera_x) / self.camera_zoom
    world_y = (mouse_y - self.camera_y) / self.camera_zoom
    
    target_x = mouse_x - world_x * new_zoom
    target_y = mouse_y - world_y * new_zoom
    
    self._animate_camera(target_x, target_y, new_zoom)
    

def keyPressEvent(self, event: QKeyEvent):
    """Handle key press events"""
    # Cancel inline text editor with Escape (delegated)
    try:
        if hasattr(self, '_text_editor') and self._text_editor and self._text_editor.isVisible() and event.key() == Qt.Key_Escape:
            self.annotations._cancel_text_editor()
            event.accept()
            return
    except Exception:
        pass
    # Handle local search shortcuts inside the canvas to avoid global ambiguity
    try:
        if (event.modifiers() & Qt.ControlModifier) and event.key() == Qt.Key_F:
            host = self.parent()
            if host and hasattr(host, 'trigger_search'):
                host.trigger_search()
            elif host and hasattr(host, 'show_search_box'):
                host.show_search_box()
            event.accept()
            return
        if event.key() == Qt.Key_F3:
            host = self.parent()
            if host:
                if event.modifiers() & Qt.ShiftModifier:
                    if hasattr(host, 'search_prev'):
                        host.search_prev()
                else:
                    if hasattr(host, 'search_next'):
                        host.search_next()
                event.accept()
                return
        # Manage-only shortcuts
        if ((event.modifiers() & (Qt.ControlModifier | Qt.AltModifier)) == (Qt.ControlModifier | Qt.AltModifier)) and event.key() == Qt.Key_S:
            # Save Layout (Ctrl+Alt+S to avoid clashing with editor save)
            try:
                if not SaveLoadManager:
                    pass
                else:
                    host = self.parent()
                    try:
                        analyzed = getattr(getattr(host, 'analyzer', None), 'current_file_path', None)
                    except Exception:
                        analyzed = None
                    base = os.path.splitext(os.path.basename(analyzed or 'layout'))[0]
                    default_name = f"{base}.mndoc"
                    initial_dir = os.path.dirname(analyzed) if analyzed else os.getcwd()
                    initial_path = os.path.join(initial_dir, default_name)
                    filt = "Manage Documents (*.mndoc);;All Files (*)"
                    path, _ = QFileDialog.getSaveFileName(self, 'Save Layout', initial_path, filt, 'Manage Documents (*.mndoc)')
                    if path:
                        mgr = SaveLoadManager()
                        path = mgr.ensure_extension(path)
                        try:
                            if os.path.exists(path):
                                proj = mgr.load_project(path)
                            else:
                                proj = {}
                            try:
                                if host and hasattr(host, '_merge_all_sessions_into_project'):
                                    proj = host._merge_all_sessions_into_project(proj)
                                else:
                                    proj, _ = mgr.merge_current_file_into_project(host, proj)
                            except Exception:
                                proj, _ = mgr.merge_current_file_into_project(host, proj)
                            mgr.save_project(path, proj)
                            try:
                                if host is not None:
                                    setattr(host, '_project_doc', proj)
                                    setattr(host, '_project_path', path)
                            except Exception:
                                pass
                        except Exception:
                            # Fallback single-file
                            try:
                                state = mgr.collect_state(host)
                                mgr.save_to_file(path, state)
                            except Exception:
                                pass
            except Exception:
                pass
            event.accept()
            return
        if (event.modifiers() & Qt.ControlModifier) and event.key() == Qt.Key_O:
            # Open Layout
            try:
                if SaveLoadManager:
                    filt = "Manage Documents (*.mndoc);;All Files (*)"
                    path, _ = QFileDialog.getOpenFileName(self, 'Open Layout', os.getcwd(), filt, 'Manage Documents (*.mndoc)')
                    if path:
                        mgr = SaveLoadManager()
                        host = self.parent()
                        data = mgr.load_from_file(path)
                        is_project = isinstance(data, dict) and isinstance(data.get('files'), dict)
                        if is_project:
                            proj = mgr.load_project(path)
                            try:
                                if host is not None:
                                    setattr(host, '_project_doc', proj)
                                    setattr(host, '_project_path', path)
                            except Exception:
                                pass
                            try:
                                root_dir = proj.get('project_root') or os.path.dirname(path)
                                if host and hasattr(host, 'set_root_path') and root_dir:
                                    host.set_root_path(root_dir)
                            except Exception:
                                pass
                            try:
                                # Auto-open latest modified file
                                files_map = proj.get('files') or {}
                                latest_key = None
                                latest_ts = ''
                                for k, v in files_map.items():
                                    ts = ''
                                    try:
                                        ts = str((v or {}).get('modified_at') or '')
                                    except Exception:
                                        ts = ''
                                    if latest_key is None or ts > latest_ts:
                                        latest_key, latest_ts = k, ts
                                if latest_key and host and hasattr(host, 'load_file') and os.path.exists(latest_key):
                                    host.load_file(latest_key)
                                    QTimer.singleShot(350, lambda: mgr.apply_project_file_to_canvas(self, proj, latest_key))
                                else:
                                    cur = getattr(getattr(host, 'analyzer', None), 'current_file_path', None)
                                    if cur:
                                        mgr.apply_project_file_to_canvas(self, proj, cur)
                            except Exception:
                                pass
                        else:
                            doc = data
                            target = doc.get('analyzed_file_path')
                            try:
                                root_dir = doc.get('project_root') or (os.path.dirname(target) if target else os.path.dirname(path))
                                if host and hasattr(host, 'set_root_path') and root_dir:
                                    host.set_root_path(root_dir)
                            except Exception:
                                pass
                            if target and os.path.exists(target) and hasattr(host, 'load_file'):
                                try:
                                    host.load_file(target)
                                except Exception:
                                    pass
                                QTimer.singleShot(350, lambda: mgr.apply_to_canvas(self, doc))
                            else:
                                if getattr(self, 'nodes', []):
                                    mgr.apply_to_canvas(self, doc)
            except Exception:
                pass
            event.accept()
            return
        if (event.modifiers() & Qt.ControlModifier) and (event.modifiers() & Qt.ShiftModifier) and event.key() == Qt.Key_Z:
            self.redo()
            event.accept()
            return
        if (event.modifiers() & Qt.ControlModifier) and not (event.modifiers() & Qt.ShiftModifier) and event.key() == Qt.Key_Z:
            self.undo()
            event.accept()
            return
        if (event.modifiers() & Qt.ControlModifier) and event.key() == Qt.Key_Y:
            self.redo()
            event.accept()
            return
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            try:
                node = self.selected_node
                if node:
                    fp = None
                    try:
                        fp = (node.data or {}).get('file_path')
                    except Exception:
                        fp = None
                    self.request_open_editor.emit(node, fp or '')
                    event.accept()
                    return
            except Exception:
                pass
    except Exception:
        pass
    # Annotation tool hotkeys (1..5). Ensure toolbar visible and switch modes like a game hotbar
    try:
        if event.key() in (Qt.Key_1, Qt.Key_2, Qt.Key_3, Qt.Key_4, Qt.Key_5):
            # If inline text editor is open, do not process number shortcuts
            te = getattr(self, '_text_editor', None)
            if te is not None and te.isVisible():
                QWidget.keyPressEvent(self, event)
                return
            host = self.parent()
            if host:
                try:
                    if hasattr(host, 'annotation_toolbar') and not host.annotation_toolbar.isVisible():
                        if hasattr(host, 'annotate_btn'):
                            host.annotate_btn.setChecked(True)
                            host.toggle_annotation_toolbar(True)
                except Exception:
                    pass
                if event.key() == Qt.Key_1:
                    try:
                        host._set_annotation_tool('cursor')
                    except Exception:
                        self.set_tool_mode('cursor')
                elif event.key() == Qt.Key_2:
                    try:
                        host._set_annotation_tool('brush')
                    except Exception:
                        self.set_tool_mode('brush')
                elif event.key() == Qt.Key_3:
                    try:
                        host._set_annotation_tool('text')
                    except Exception:
                        self.set_tool_mode('text')
                elif event.key() == Qt.Key_4:
                    try:
                        host._set_annotation_tool('erase')
                    except Exception:
                        self.set_tool_mode('erase')
                elif event.key() == Qt.Key_5:
                    try:
                        host.on_pick_annotation_color()
                    except Exception:
                        pass
            event.accept()
            return
    except Exception:
        pass
    # Select Box mode shortcut (S key)
    if event.key() == Qt.Key_S and not (event.modifiers() & Qt.ControlModifier):
        # S key - Toggle Select Box mode (only if Ctrl is not held)
        current_mode = getattr(self, '_selection_box_mode', False)
        self.toggle_selection_box_mode(not current_mode)
        event.accept()
        return
    # Blender-style transform shortcuts
    elif event.key() == Qt.Key_G:
        # G key - Start grab/move mode
        self._start_transform_mode('grab')
        event.accept()
        return
    elif event.key() == Qt.Key_X:
        # X key - Constrain to X axis (or switch to X if already in grab mode)
        if getattr(self, '_transform_mode', None):
            self._transform_mode = 'grab_x'
            self.setCursor(Qt.SizeHorCursor)
        else:
            self._start_transform_mode('grab_x')
        event.accept()
        return
    elif event.key() == Qt.Key_Y:
        # Y key - Constrain to Y axis (or switch to Y if already in grab mode)
        if getattr(self, '_transform_mode', None):
            self._transform_mode = 'grab_y'
            self.setCursor(Qt.SizeVerCursor)
        else:
            self._start_transform_mode('grab_y')
        event.accept()
        return
    elif event.key() == Qt.Key_Escape:
        # Escape - Cancel transform or clear selection
        if getattr(self, '_transform_mode', None):
            self._cancel_transform()
            event.accept()
            return
        self.select_node(None)
    elif event.key() == Qt.Key_Delete:
        try:
            node = self.selected_node
            if node:
                removed_conns = [c for c in self.connections if c.from_node is node or c.to_node is node]
                self.connections = [c for c in self.connections if c.from_node is not node and c.to_node is not node]
                try:
                    self.nodes.remove(node)
                except ValueError:
                    pass
                self._push_undo({'type': 'delete_node', 'node': node, 'connections': removed_conns})
                self._node_by_name = {}
                for n in self.nodes:
                    self._index_node(n)
                self.update()
                event.accept()
                return
        except Exception:
            pass
    elif event.key() in (Qt.Key_Plus, Qt.Key_Equal):
        self.zoom_in()
    elif event.key() == Qt.Key_Minus:
        self.zoom_out()
    elif event.key() == Qt.Key_R and event.modifiers() & Qt.ControlModifier:
        self.reset_view()

# ---------------------- Annotation public API ----------------------
def set_tool_mode(self, mode: Optional[str]):
    try:
        self.annotations.set_tool_mode(mode)
    except Exception:
        pass

def set_rgb(self, r: int, g: int, b: int):
    try:
        self.annotations.set_rgb(r, g, b)
    except Exception:
        pass

def set_current_color(self, color: QColor, apply_to_selection: bool = False):
    try:
        self.annotations.set_current_color(color, apply_to_selection)
    except Exception:
        pass

# ---------------------- Live trace integration ----------------------
def _ensure_trace_server(self):
    if self._trace_server_thread and self._trace_server_thread.is_alive():
        return
    # Choose a port in a stable range (but attempt to reuse previous)
    port = self._trace_server_port or 56789
    self._trace_server_stop.clear()
    t = threading.Thread(target=self._trace_server_loop, args=(port,), daemon=True)
    t.start()
    self._trace_server_thread = t
    self._trace_server_port = port
    _trace_log(f"trace_server: listening on 127.0.0.1:{self._trace_server_port}")


def _trace_server_loop(self, port: int):
    # Simple line-delimited JSON TCP server
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        srv.bind(('127.0.0.1', port))
        srv.listen(1)
        _trace_log(f"trace_server: bound 127.0.0.1:{port}")
    except OSError as e:
        _trace_log(f"trace_server: port {port} busy ({e}), trying fallback")
        # Try next port
        try:
            port2 = port + 1
            srv.bind(('127.0.0.1', port2))
            srv.listen(1)
            self._trace_server_port = port2
            _trace_log(f"trace_server: bound 127.0.0.1:{port2}")
        except Exception as e2:
            _trace_log(f"trace_server: failed to bind any port: {e2}")
            srv.close()
            return
    srv.settimeout(0.5)
    try:
        while not self._trace_server_stop.is_set():
            try:
                conn, _addr = srv.accept()
                conn.settimeout(0.1)
            except socket.timeout:
                continue
            with conn:
                buf = b''
                while not self._trace_server_stop.is_set():
                    try:
                        chunk = conn.recv(4096)
                        if not chunk:
                            break
                        buf += chunk
                        while b"\n" in buf:
                            line, buf = buf.split(b"\n", 1)
                            self._handle_trace_line(line)
                    except socket.timeout:
                        continue
                    except OSError:
                        break
    finally:
        try:
            srv.close()
        except Exception:
            pass

def _handle_trace_line(self, line: bytes):
    # Parse in worker thread, but schedule UI updates on the main thread
    try:
        obj = json.loads(line.decode('utf-8', errors='replace'))
    except Exception:
        return
    if obj.get('type') != 'call':
        return
    func = str(obj.get('func', '')).lower()
    module = str(obj.get('module', '') or '')
    file_path = obj.get('file', '')
    # Schedule UI work on main thread
    QTimer.singleShot(0, lambda: self._on_trace_call(func, module, file_path))

def _on_trace_call(self, func: str, module: str, file_path: str):
    # UI thread: filter noise, and flash ONLY existing nodes from the analyzed file
    try:
        if (not isinstance(file_path, str) or file_path.startswith('<') or '\\<frozen' in file_path or '/<frozen' in file_path or not file_path.lower().endswith('.py')):
            return
    except Exception:
        return

    # Enable runtime focus mode on first observed activity
    try:
        if not getattr(self, 'runtime_focus_mode', False):
            self.runtime_focus_mode = True
            # New run session: reset ever-active set
            self._ever_active_nodes = set()
    except Exception:
        pass

    # Restrict to currently analyzed file boxes
    external = False
    try:
        cur_fp = getattr(self, 'current_file_path', None)
        if cur_fp:
            a = os.path.abspath(file_path)
            b = os.path.abspath(cur_fp)
            if a != b:
                # Compare module base names; if different, treat as external module
                a_base = os.path.splitext(os.path.basename(a))[0].lower()
                b_base = os.path.splitext(os.path.basename(b))[0].lower()
                if a_base != b_base:
                    external = True
    except Exception:
        external = False

    name = (func or '').split('.')[-1]
    lookup = getattr(self, '_node_by_name', {}) or {}
    # Try exact and composite lookups against the analyzed module
    cur_base = getattr(self, 'current_module_base', '') or ''
    node = (
        lookup.get(name.lower()) or
        lookup.get(f"{module}.{name}".lower()) or
        (lookup.get(f"{cur_base}.{name}".lower()) if cur_base else None)
    )
    if not node:
        # For external modules, aggregate under a single module node with Python icon
        try:
            if external:
                node = self._get_or_create_module_node(file_path)
            else:
                node = self._create_dynamic_node(file_path, name, module=module)
        except Exception:
            node = None
        if not node:
            _trace_log(f"recv call func={func} file={file_path} -> NO NODE (dynamic/module create failed). known={list(lookup.keys())[:20]}")
            return

    # Mark node as used at least once during this run session and update last-activity time
    try:
        if not hasattr(self, '_ever_active_nodes') or not isinstance(self._ever_active_nodes, set):
            self._ever_active_nodes = set()
        self._ever_active_nodes.add(str(getattr(node, 'name', '') or ''))
        self._last_activity_time = time.monotonic()
    except Exception:
        pass

    _trace_log(f"recv call func={func} file={file_path} -> FLASH {node.name}")
    # Extend/mark runtime-active: no per-call timers
    already_on = bool(getattr(node, '_active_on', False))
    try:
        node._active_until = time.monotonic() + float(getattr(self, '_active_duration', 0.45))
    except Exception:
        pass
    if not already_on:
        try:
            node._active_refcount = getattr(node, '_active_refcount', 0) + 1
            node._active_on = True
        except Exception:
            try:
                setattr(node, '_active_refcount', 1)
                setattr(node, '_active_on', True)
            except Exception:
                pass
        node.target_opacity = 1.0
        # Only emit and update when switching from off->on
        try:
            self.trace_called.emit(node.name)
        except Exception:
            pass
        self.update()

def _soft_clear_selection(self, node: FunctionNode):
    # Only clear if this node is still the selected one
    if self.selected_node is node:
        node.selected = False
        self.selected_node = None
        # Keep highlight faintly until blink ends
        node.highlighted = True
        node.target_opacity = 1.0
        self.update()

def _clear_highlight_if_no_blink(self, node: FunctionNode):
    # Clear highlight after blink completes, but don't interfere with a user selection
    try:
        if getattr(node, 'blink_time', 0.0) <= 0.0 and not node.selected:
            node.highlighted = False
            node.target_opacity = 1.0
            self.update()
    except Exception:
        pass

def _deactivate_node(self, node: FunctionNode):
    # Reduce the transient runtime-active state; repeated calls extend it
    try:
        cnt = getattr(node, '_active_refcount', 0) - 1
        if cnt <= 0:
            node._active_refcount = 0
            node._active_on = False
        else:
            node._active_refcount = cnt
        self.update()
    except Exception:
        pass

def get_trace_port(self) -> Optional[int]:
    return self._trace_server_port

def _ann_legacy_hit_test_text(self, sx: int, sy: int) -> bool:
    try:
        hit = None
        # Use bounding box of text using font metrics instead of a small radius
        for t in self._texts:
            from PySide6.QtGui import QFont as _QFont
            from PySide6.QtGui import QFontMetrics as _QFontMetrics
            size = int(t.get('size', 14) or 14)
            f = _QFont("Segoe UI", max(6, size))
            fm = _QFontMetrics(f)
            txt = str(t.get('text',''))
            tx, ty = self._world_to_screen(float(t.get('x', 0.0)), float(t.get('y', 0.0)))
            w = fm.horizontalAdvance(txt)
            # Build a hit rectangle that covers the text box
            rect_left = tx - 3
            rect_top = ty - fm.ascent() - 3
            rect_right = tx + w + 3
            rect_bottom = ty + fm.descent() + 3
            if (sx >= rect_left and sx <= rect_right and sy >= rect_top and sy <= rect_bottom):
                hit = t
                break
        self._selected_text = hit
        return hit is not None
    except Exception:
        self._selected_text = None
        return False

def _draw_arrowhead(self, painter: QPainter, p_from, p_to, color: QColor):
    try:
        x1, y1 = float(p_from[0]), float(p_from[1])
        x2, y2 = float(p_to[0]), float(p_to[1])
        dx = x2 - x1
        dy = y2 - y1
        length = math.hypot(dx, dy)
        if length < 10.0:
            return
        ux, uy = dx / length, dy / length
        size = 10.0
        w = 6.0
        bx, by = x2 - ux * size, y2 - uy * size
        px, py = -uy, ux
        p1 = QPointF(x2, y2)
        p2 = QPointF(bx + px * w, by + py * w)
        p3 = QPointF(bx - px * w, by - py * w)
        old_pen = painter.pen()
        painter.setBrush(QBrush(color))
        painter.setPen(Qt.NoPen)
        painter.drawPolygon(p1, p2, p3)
        painter.setPen(old_pen)
    except Exception:
        pass

def _index_node(self, node: FunctionNode, module: Optional[str] = None, file_path: Optional[str] = None):
    try:
        if not hasattr(self, '_node_by_name') or not isinstance(self._node_by_name, dict):
            self._node_by_name = {}
        # Defaults to current analyzed file/module if not provided
        if file_path is None:
            file_path = getattr(self, 'current_file_path', None)
        if module is None:
            module = getattr(self, 'current_module_base', None)
        # basic key by function name
        self._node_by_name[node.name.lower()] = node
        # add composite keys for better matching
        if file_path:
            base = os.path.splitext(os.path.basename(file_path))[0]
            self._node_by_name[f"{base}.{node.name}".lower()] = node
        if module:
            self._node_by_name[f"{module}.{node.name}".lower()] = node
    except Exception:
        pass

def _get_or_create_module_node(self, file_path: str) -> FunctionNode:
    # Create or return a single aggregated node representing an external Python module
    try:
        import os as _os
        abs_path = _os.path.abspath(file_path)
        if not hasattr(self, '_module_nodes') or not isinstance(self._module_nodes, dict):
            self._module_nodes = {}
        if abs_path in self._module_nodes:
            return self._module_nodes[abs_path]
        display = _os.path.basename(abs_path)
        # Position near center in a loose ring
        cx = self.width() / 2
        cy = self.height() / 2
        import random as _rnd
        angle = _rnd.random() * 6.283
        radius = 220 + _rnd.random() * 200
        x = cx + math.cos(angle) * radius
        y = cy + math.sin(angle) * radius
        data = {
            'name': display,
            'lineno': 0,
            'args': [],
            'docstring': 'External module used at runtime. Open this file to see which functions are called.',
            'returns': '',
            'complexity': 1
        }
        node = FunctionNode(data, x, y)
        node.color = '#4FC3F7'  # Cyan-ish to distinguish external module boxes
        node.icon_path = 'img/python.png'
        try:
            node.data['file_path'] = abs_path
        except Exception:
            pass
        self.nodes.append(node)
        # Map by file path
        self._module_nodes[abs_path] = node
        # Connect to main script node if present
        try:
            main_node = next((n for n in self.nodes if getattr(n, 'icon_path', None) and 'python' in str(n.icon_path).lower() and n.name == (self.main_script_name or n.name)), None)
            if main_node:
                self.connections.append(Connection(node, main_node))
        except Exception:
            pass
        # Re-layout external module nodes for tidy spacing
        try:
            self._layout_module_nodes()
        except Exception:
            pass
        self._index_node(node, module=None, file_path=abs_path)
        self.update()
        return node
    except Exception:
        # Fallback very small box if anything fails
        data = {'name': os.path.basename(file_path) if file_path else 'module', 'lineno': 0, 'args': [], 'docstring': '', 'returns': '', 'complexity': 1}
        node = FunctionNode(data, self.width()/2, self.height()/2)
        node.icon_path = 'img/python.png'
        self.nodes.append(node)
        return node

def _layout_module_nodes(self):
    """Arrange aggregated external module nodes in a tidy ring around the main node."""
    try:
        if not hasattr(self, '_module_nodes') or not self._module_nodes:
            return
        modules = list(self._module_nodes.values())
        n = len(modules)
        # Find center around main node if present
        try:
            main_node = next((n for n in self.nodes if getattr(n, 'icon_path', None) and 'python' in str(n.icon_path).lower() and n.name == (self.main_script_name or n.name)), None)
        except Exception:
            main_node = None
        cx = main_node.x if main_node else (self.width() / 2)
        cy = main_node.y if main_node else (self.height() / 2)
        # Base radius depending on canvas size and count
        base = max(220.0, min(self.width(), self.height()) * 0.32)
        radius = base + max(0, n - 6) * 22.0
        # Sort for stable placement
        modules_sorted = sorted(modules, key=lambda m: m.name.lower())
        step = (2 * math.pi) / max(1, n)
        for i, node in enumerate(modules_sorted):
            angle = i * step
            node.x = cx + math.cos(angle) * radius
            node.y = cy + math.sin(angle) * radius
            node.original_x = node.x
            node.original_y = node.y
    except Exception:
        pass

def _create_dynamic_node(self, file_path: str, func_name: str, module: Optional[str] = None) -> Optional[FunctionNode]:
    try:
        if not file_path or not os.path.isfile(file_path):
            return None
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()
        analyzer = FunctionAnalyzer()
        result = analyzer.analyze_code(content, file_path)
        funcs = result.get('functions', {})
        data = funcs.get(func_name)
        if not data:
            # Try a case-insensitive match
            for k, v in funcs.items():
                if k.lower() == func_name.lower():
                    data = v
                    break
        if not data:
            _trace_log(f"dynamic: no def for {func_name} in {file_path}")
            return None
        # Choose a position near center with slight spread
        cx = self.width() / 2
        cy = self.height() / 2
        import random
        angle = random.random() * 6.283
        radius = 150 + random.random() * 200
        x = cx + math.cos(angle) * radius
        y = cy + math.sin(angle) * radius
        node = FunctionNode(data, x, y)
        self.nodes.append(node)
        self._index_node(node, module=module, file_path=file_path)
        # Connect to main script node if present
        try:
            main_node = next((n for n in self.nodes if getattr(n, 'icon_path', None) and 'python' in str(n.icon_path).lower()), None)
            if main_node:
                self.connections.append(Connection(node, main_node))
        except Exception:
            pass
        self.update()
        return node
    except Exception as e:
        _trace_log(f"dynamic error: {e}")
        return None

def flash_node(self, name: str, seconds: float = 2.0):
    """Public API: flash a node by function name (case-insensitive)."""
    node = getattr(self, '_node_by_name', {}).get(name.lower())
    if not node:
        return False
    node.blink_time = max(node.blink_time, max(0.5, float(seconds)))
    node.blink_phase = 0.0
    node.target_opacity = 1.0
    node.highlighted = True
    self.update()
    return True

def _is_near_node_border(self, screen_x: int, screen_y: int, node: FunctionNode) -> bool:
    """Check if the mouse position is near the border of a node (for connection dragging)."""
    try:
        # EXCEPTION: Custom content nodes (text, image, video) cannot create connections
        if hasattr(node, 'data') and isinstance(node.data, dict):
            content_type = node.data.get('content_type')
            if content_type in ('text', 'image', 'video'):
                return False  # Disable connection dragging for custom content nodes
        
        # Use the EXACT SAME dimension calculation as _draw_node for perfect consistency
        # This is critical because _draw_node uses font metrics, not node.radius!
        
        # Check if it's an Add tool node
        is_add_tool = getattr(node, 'is_add_tool', False)
        if is_add_tool:
            icon_size = 80 * node.scale
            border_padding = 20 * node.scale
            width = icon_size + border_padding * 2
            height = icon_size + border_padding * 2
        else:
            # Normal node: calculate dimensions based on text (SAME AS _draw_node)
            font = QFont("Arial", 14)
            font.setBold(True)
            fm = QFontMetrics(font)
            text_width = fm.horizontalAdvance(node.name)
            
            width = max(100, min(text_width + 40, 300)) * node.scale
            height = (fm.height() + 20) * self.height_multiplier * node.scale
            
            # If it's a main script node, adjust height
            if node.icon_path and not is_add_tool:
                height = max(height, (self.main_node_icon_size + fm.height() + 40) * node.scale)
        
        # Convert node center to screen coordinates
        screen_node_x = node.x * self.camera_zoom + self.camera_x
        screen_node_y = node.y * self.camera_zoom + self.camera_y
        
        # Calculate screen-space box bounds
        half_w = (width * self.camera_zoom) / 2
        half_h = (height * self.camera_zoom) / 2
        
        left = screen_node_x - half_w
        right = screen_node_x + half_w
        top = screen_node_y - half_h
        bottom = screen_node_y + half_h
        
        # Check if mouse is within the node bounds first
        if screen_x < left or screen_x > right or screen_y < top or screen_y > bottom:
            return False
        
        # SOLUTION: Make the ENTIRE box grabbable for connection dragging!
        # This is the simplest and most user-friendly approach.
        # If the mouse is anywhere inside the node, allow connection dragging.
        return True
    except Exception:
        pass
        return False

def _draw_connection_drag_line(self, painter: QPainter):
    """Draw the curved line while dragging a connection with Add.png icon at the end."""
    try:
        if not getattr(self, '_connection_drag_mode', False):
            return
        
        source_node = getattr(self, '_connection_source_node', None)
        current_pos = getattr(self, '_connection_drag_current', None)
        
        if not source_node or not current_pos:
            return
        
        # Start position is the node center in world coordinates
        start_x = source_node.x
        start_y = source_node.y
        
        # Convert current mouse position (screen coords) to world coordinates
        end_x = (current_pos[0] - self.camera_x) / self.camera_zoom
        end_y = (current_pos[1] - self.camera_y) / self.camera_zoom
        
        # Calculate curve control point (same algorithm as regular connections)
        dx = end_x - start_x
        dy = end_y - start_y
        distance = math.sqrt(dx * dx + dy * dy)
        
        if distance > 1e-6:
            theta = math.atan2(dy, dx)
            curviness = abs(math.sin(2.0 * theta))
            base_curve = min(distance * 0.45, 160)
            curve = base_curve * (curviness ** 0.6)
            
            if curviness < 0.03:
                curve = 0.0
            
            mid_x = (start_x + end_x) / 2
            mid_y = (start_y + end_y) / 2
            perp_x = (-dy / distance) * curve
            perp_y = (dx / distance) * curve
            
            if abs(dx) >= abs(dy):
                sign_dir = 1.0 if dy >= 0 else -1.0
            else:
                sign_dir = 1.0 if dx >= 0 else -1.0
            
            perp_x *= sign_dir
            perp_y *= sign_dir
            control_x = mid_x + perp_x
            control_y = mid_y + perp_y
        else:
            control_x = (start_x + end_x) / 2
            control_y = (start_y + end_y) / 2
        
        # Draw the curved line in world coordinates with 0.7 opacity
        from PySide6.QtGui import QPainterPath
        path = QPainterPath()
        path.moveTo(QPointF(start_x, start_y))
        path.quadTo(QPointF(control_x, control_y), QPointF(end_x, end_y))
        
        # Use white color for the drag line with 0.7 opacity (alpha = 178)
        painter.setOpacity(0.7)
        pen = QPen(QColor(255, 255, 255, 178), 3)
        pen.setCapStyle(Qt.RoundCap)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawPath(path)
        painter.setOpacity(1.0)  # Reset opacity
        
        # Draw Add.png icon at the end point with white border (no background)
        # Calculate icon size to match 3D box size (similar to function nodes)
        font = QFont("Arial", 14)
        font.setBold(True)
        fm = QFontMetrics(font)
        
        # Base size similar to function node boxes
        base_size = (fm.height() + 20) * getattr(self, 'height_multiplier', 1.0)
        icon_size = base_size * 0.5  # Make icon slightly smaller than full box
        border_padding = 18  # Padding between icon and border
        
        # Total box size with border - make it wider (1.5x width)
        box_width = (icon_size + border_padding * 2) * 1.5
        box_height = icon_size + border_padding * 2
        half_width = box_width / 2
        half_height = box_height / 2
        
        # Draw white border only (no background) with opacity
        border_rect = QRectF(end_x - half_width, end_y - half_height, box_width, box_height)
        border_radius = 12
        
        # White border with 0.7 opacity (70% opacity = 178 alpha)
        white_border = QColor(255, 255, 255, 178)
        
        painter.setBrush(Qt.NoBrush)  # No background
        painter.setPen(QPen(white_border, 2))  # White border with opacity
        painter.drawRoundedRect(border_rect, border_radius, border_radius)
        
        # Draw the Add.png icon with 0.7 opacity
        add_icon_path = 'img/Add.png'
        if os.path.exists(add_icon_path):
            pixmap = QPixmap(add_icon_path)
            if not pixmap.isNull():
                # Set opacity for the icon
                painter.setOpacity(0.7)
                icon_x = end_x - icon_size / 2
                icon_y = end_y - icon_size / 2
                target_rect = QRectF(icon_x, icon_y, icon_size, icon_size)
                painter.drawPixmap(target_rect, pixmap, pixmap.rect())
                painter.setOpacity(1.0)  # Reset opacity
        else:
            # Fallback: draw a plus sign if image not found
            painter.setOpacity(0.7)
            painter.setPen(QPen(QColor(255, 255, 255, 178), 3))
            plus_size = icon_size * 0.4
            painter.drawLine(QPointF(end_x - plus_size, end_y), QPointF(end_x + plus_size, end_y))
            painter.drawLine(QPointF(end_x, end_y - plus_size), QPointF(end_x, end_y + plus_size))
            painter.setOpacity(1.0)  # Reset opacity
        
    except Exception:
        pass












