"""
Project Canvas Widget
Displays project items with 3D nodes like manage native
"""

from PySide6.QtCore import Qt, Signal, QSize, QPoint, QRectF, QPointF
from PySide6.QtGui import (
    QIcon, QPainter, QPen, QBrush, QColor, QLinearGradient, 
    QRadialGradient, QPixmap, QFont, QFontMetrics, QWheelEvent, QMouseEvent
)
from PySide6.QtWidgets import QWidget, QLabel


class AddProjectNode(QWidget):
    """Custom Add button as a draggable node with 3D effect (like manage native)"""
    
    clicked = Signal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(150, 150)
        self.setCursor(Qt.PointingHandCursor)
        self.dragging = False
        self.drag_offset = QPoint()
        self.highlighted = False
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        width = self.width()
        height = self.height()
        x = 0
        y = 0
        
        # Draw 3D box effect (same as manage native)
        self._draw_3d_box(painter, x, y, width, height)
        
        # Draw Add.png icon in center
        try:
            pixmap = QPixmap("img/Add.png")
            if not pixmap.isNull():
                icon_size = 80
                icon_x = (width - icon_size) / 2
                icon_y = (height - icon_size) / 2
                target_rect = QRectF(icon_x, icon_y, icon_size, icon_size)
                painter.drawPixmap(target_rect, pixmap, pixmap.rect())
        except Exception:
            pass
    
    def _draw_3d_box(self, painter, x, y, width, height):
        """Draw 3D inset box effect matching manage native"""
        rect = QRectF(x, y, width, height)
        border_radius = 15
        
        # Base shadow (drop shadow)
        shadow_rect = QRectF(x + 3, y + 6, width, height)
        painter.setBrush(QBrush(QColor(0, 0, 0, 100)))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(shadow_rect, border_radius, border_radius)
        
        # Main gradient
        gradient = QLinearGradient(x, y, x, y + height)
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
        border_width = 2 if self.highlighted else 1
        border_color = QColor('#60A5FA') if self.highlighted else QColor(255, 255, 255, 25)
        
        painter.setPen(QPen(border_color, border_width))
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(rect, border_radius, border_radius)
        
        # Subtle 1px border
        painter.setPen(QPen(QColor('#4A4D51'), 1.0))
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(rect, border_radius, border_radius)
    
    def enterEvent(self, event):
        self.highlighted = True
        self.update()
    
    def leaveEvent(self, event):
        self.highlighted = False
        self.update()
    
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drag_offset = event.pos()
            self.dragging = True
    
    def mouseMoveEvent(self, event):
        if self.dragging:
            new_pos = self.mapToParent(event.pos() - self.drag_offset)
            self.move(new_pos)
    
    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.dragging = False
            # Check if it was a click (not a drag)
            if (event.pos() - self.drag_offset).manhattanLength() < 5:
                self.clicked.emit()


class FunctionBox(QWidget):
    """Custom function box widget with 3D effect (draggable like manage native nodes)"""
    
    def __init__(self, name, func_type, parent=None):
        super().__init__(parent)
        self.name = name
        self.func_type = func_type
        self.dragging = False
        self.drag_offset = QPoint()
        self.highlighted = False
        self.setup_ui()
        
    def setup_ui(self):
        """Setup the function box UI"""
        # Calculate size based on text
        font = QFont("Segoe UI", 14)
        font.setBold(True)
        fm = QFontMetrics(font)
        text_width = fm.horizontalAdvance(self.name)
        
        width = max(150, min(text_width + 40, 300))
        height = fm.height() + 60
        
        self.setFixedSize(int(width), int(height))
        self.setCursor(Qt.PointingHandCursor)
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        width = self.width()
        height = self.height()
        x = 0
        y = 0
        
        # Draw 3D box effect
        self._draw_3d_box(painter, x, y, width, height)
        
        # Draw text
        self._draw_text(painter, width, height)
    
    def _draw_3d_box(self, painter, x, y, width, height):
        """Draw 3D inset box effect matching manage native"""
        rect = QRectF(x, y, width, height)
        border_radius = 15
        
        # Base shadow (drop shadow)
        shadow_rect = QRectF(x + 3, y + 6, width, height)
        painter.setBrush(QBrush(QColor(0, 0, 0, 100)))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(shadow_rect, border_radius, border_radius)
        
        # Main gradient
        gradient = QLinearGradient(x, y, x, y + height)
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
        border_width = 2 if self.highlighted else 1
        border_color = QColor('#60A5FA') if self.highlighted else QColor(255, 255, 255, 25)
        
        painter.setPen(QPen(border_color, border_width))
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(rect, border_radius, border_radius)
        
        # Subtle 1px border
        painter.setPen(QPen(QColor('#4A4D51'), 1.0))
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(rect, border_radius, border_radius)
    
    def _draw_text(self, painter, width, height):
        """Draw node text"""
        painter.setPen(QPen(QColor('#E0E2E6')))
        
        # Function name
        font = QFont("Segoe UI", 14)
        font.setBold(True)
        painter.setFont(font)
        
        text_rect = QRectF(10, 10, width - 20, height - 30)
        painter.drawText(text_rect, Qt.AlignCenter | Qt.TextWordWrap, self.name)
        
        # Function type
        font.setPointSize(10)
        font.setBold(False)
        painter.setFont(font)
        painter.setPen(QPen(QColor('#A9A9A9')))
        
        type_rect = QRectF(10, height - 25, width - 20, 20)
        painter.drawText(type_rect, Qt.AlignCenter, self.func_type)
    
    def enterEvent(self, event):
        self.highlighted = True
        self.update()
    
    def leaveEvent(self, event):
        self.highlighted = False
        self.update()
    
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drag_offset = event.pos()
            self.dragging = True
            self.raise_()
    
    def mouseMoveEvent(self, event):
        if self.dragging:
            new_pos = self.mapToParent(event.pos() - self.drag_offset)
            self.move(new_pos)
    
    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.dragging = False


class ProjectCanvas(QWidget):
    """Canvas widget for displaying project items with proper world coordinates"""
    
    add_function_requested = Signal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.project_name = ""
        self.function_boxes = []  # List of dicts with {name, type, x, y, width, height}
        self.camera_zoom = 1.0
        self.camera_x = 0.0
        self.camera_y = 0.0
        
        # Add node in world coordinates
        self.add_node_x = 0.0
        self.add_node_y = 0.0
        self.add_node_width = 150.0
        self.add_node_height = 150.0
        self.add_node_highlighted = False
        
        # Mouse interaction
        self.mouse_down = False
        self.last_mouse_x = 0
        self.last_mouse_y = 0
        self.dragging = False
        self.dragging_node = None
        self.drag_offset_x = 0.0
        self.drag_offset_y = 0.0
        
        self.setup_ui()
        
    def setup_ui(self):
        """Setup the canvas UI"""
        self.setStyleSheet("background-color: #1C1C1C;")
        self.setMouseTracking(True)
        
        # Project name label (top-left, floating in screen space)
        self.project_name_label = QLabel(self)
        self.project_name_label.setStyleSheet("""
            QLabel {
                color: #E8EAED;
                font-size: 24px;
                font-weight: bold;
                background: transparent;
                border: none;
            }
        """)
        self.project_name_label.hide()
        self.project_name_label.move(20, 20)
        
    def paintEvent(self, event):
        """Paint the canvas with world coordinates"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Fill background
        painter.fillRect(self.rect(), QColor('#1C1C1C'))
        
        # Apply camera transform
        painter.save()
        painter.translate(self.camera_x, self.camera_y)
        painter.scale(self.camera_zoom, self.camera_zoom)
        
        # Draw add node
        self._draw_add_node(painter)
        
        # Draw function boxes
        for box in self.function_boxes:
            self._draw_function_box(painter, box)
        
        painter.restore()
    
    def _draw_add_node(self, painter):
        """Draw the add node in world coordinates"""
        x = self.add_node_x - self.add_node_width / 2
        y = self.add_node_y - self.add_node_height / 2
        width = self.add_node_width
        height = self.add_node_height
        
        # Draw 3D box
        self._draw_3d_box(painter, x, y, width, height, self.add_node_highlighted)
        
        # Draw Add.png icon
        try:
            pixmap = QPixmap("img/Add.png")
            if not pixmap.isNull():
                icon_size = 80
                icon_x = self.add_node_x - icon_size / 2
                icon_y = self.add_node_y - icon_size / 2
                target_rect = QRectF(icon_x, icon_y, icon_size, icon_size)
                painter.drawPixmap(target_rect, pixmap, pixmap.rect())
        except Exception:
            pass
    
    def _draw_function_box(self, painter, box):
        """Draw a function box in world coordinates"""
        x = box['x'] - box['width'] / 2
        y = box['y'] - box['height'] / 2
        width = box['width']
        height = box['height']
        highlighted = box.get('highlighted', False)
        
        # Draw 3D box
        self._draw_3d_box(painter, x, y, width, height, highlighted)
        
        # Draw text
        painter.setPen(QPen(QColor('#E0E2E6')))
        
        # Function name
        font = QFont("Segoe UI", 14)
        font.setBold(True)
        painter.setFont(font)
        
        text_rect = QRectF(x + 10, y + 10, width - 20, height - 30)
        painter.drawText(text_rect, Qt.AlignCenter | Qt.TextWordWrap, box['name'])
        
        # Function type
        font.setPointSize(10)
        font.setBold(False)
        painter.setFont(font)
        painter.setPen(QPen(QColor('#A9A9A9')))
        
        type_rect = QRectF(x + 10, y + height - 25, width - 20, 20)
        painter.drawText(type_rect, Qt.AlignCenter, box['type'])
    
    def _draw_3d_box(self, painter, x, y, width, height, highlighted):
        """Draw 3D inset box effect matching manage native"""
        rect = QRectF(x, y, width, height)
        border_radius = 15
        
        # Base shadow (drop shadow)
        shadow_rect = QRectF(x + 3, y + 6, width, height)
        painter.setBrush(QBrush(QColor(0, 0, 0, 100)))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(shadow_rect, border_radius, border_radius)
        
        # Main gradient
        gradient = QLinearGradient(x, y, x, y + height)
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
        border_width = 2 if highlighted else 1
        border_color = QColor('#60A5FA') if highlighted else QColor(255, 255, 255, 25)
        
        painter.setPen(QPen(border_color, border_width))
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(rect, border_radius, border_radius)
        
        # Subtle 1px border
        painter.setPen(QPen(QColor('#4A4D51'), 1.0))
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(rect, border_radius, border_radius)
    
    def set_project_name(self, name):
        """Set the project name"""
        self.project_name = name
        self.project_name_label.setText(name)
        self.project_name_label.adjustSize()
        self.project_name_label.show()
    
    def on_add_clicked(self):
        """Handle add button click"""
        self.add_function_requested.emit()
    
    def add_function_box(self, name, func_type):
        """Add a function box to the canvas in world coordinates"""
        # Calculate size based on text
        font = QFont("Segoe UI", 14)
        font.setBold(True)
        fm = QFontMetrics(font)
        text_width = fm.horizontalAdvance(name)
        
        width = max(150, min(text_width + 40, 300))
        height = fm.height() + 60
        
        # Position it near the add button or last box
        if self.function_boxes:
            last_box = self.function_boxes[-1]
            x = last_box['x'] + 220
            y = last_box['y']
        else:
            # Position first box to the left of add button
            x = self.add_node_x - 220
            y = self.add_node_y
        
        box = {
            'name': name,
            'type': func_type,
            'x': x,
            'y': y,
            'width': width,
            'height': height,
            'highlighted': False
        }
        
        self.function_boxes.append(box)
        self.update()
    
    def clear_canvas(self):
        """Clear all function boxes"""
        self.function_boxes.clear()
        self.project_name_label.hide()
        self.project_name = ""
        self.update()
    
    def resizeEvent(self, event):
        """Handle resize event"""
        super().resizeEvent(event)
        self.update()
    
    def wheelEvent(self, event: QWheelEvent):
        """Handle zoom with mouse wheel"""
        factor = 1.2 if event.angleDelta().y() > 0 else 0.8
        new_zoom = max(0.3, min(3.0, self.camera_zoom * factor))
        
        # Zoom towards mouse position
        mouse_x = event.position().x()
        mouse_y = event.position().y()
        
        world_x = (mouse_x - self.camera_x) / self.camera_zoom
        world_y = (mouse_y - self.camera_y) / self.camera_zoom
        
        self.camera_x = mouse_x - world_x * new_zoom
        self.camera_y = mouse_y - world_y * new_zoom
        self.camera_zoom = new_zoom
        
        self.update()
        event.accept()
    
    def mousePressEvent(self, event: QMouseEvent):
        """Handle mouse press"""
        if event.button() == Qt.LeftButton:
            self.mouse_down = True
            self.last_mouse_x = event.x()
            self.last_mouse_y = event.y()
            
            # Check if clicking on add node
            world_x = (event.x() - self.camera_x) / self.camera_zoom
            world_y = (event.y() - self.camera_y) / self.camera_zoom
            
            if self._hit_test_add_node(world_x, world_y):
                self.dragging_node = 'add'
                self.drag_offset_x = world_x - self.add_node_x
                self.drag_offset_y = world_y - self.add_node_y
                return
            
            # Check if clicking on function box
            for i, box in enumerate(self.function_boxes):
                if self._hit_test_box(world_x, world_y, box):
                    self.dragging_node = i
                    self.drag_offset_x = world_x - box['x']
                    self.drag_offset_y = world_y - box['y']
                    return
            
            # Otherwise, pan the canvas
            self.dragging = True
            self.setCursor(Qt.ClosedHandCursor)
    
    def mouseMoveEvent(self, event: QMouseEvent):
        """Handle mouse move"""
        world_x = (event.x() - self.camera_x) / self.camera_zoom
        world_y = (event.y() - self.camera_y) / self.camera_zoom
        
        # Update hover state
        if not self.mouse_down:
            old_highlighted = self.add_node_highlighted
            self.add_node_highlighted = self._hit_test_add_node(world_x, world_y)
            
            for box in self.function_boxes:
                box['highlighted'] = self._hit_test_box(world_x, world_y, box)
            
            if old_highlighted != self.add_node_highlighted or any(box['highlighted'] for box in self.function_boxes):
                self.update()
            
            if self.add_node_highlighted or any(box['highlighted'] for box in self.function_boxes):
                self.setCursor(Qt.PointingHandCursor)
            else:
                self.setCursor(Qt.ArrowCursor)
        
        if self.mouse_down:
            if self.dragging_node == 'add':
                self.add_node_x = world_x - self.drag_offset_x
                self.add_node_y = world_y - self.drag_offset_y
                self.update()
            elif isinstance(self.dragging_node, int):
                box = self.function_boxes[self.dragging_node]
                box['x'] = world_x - self.drag_offset_x
                box['y'] = world_y - self.drag_offset_y
                self.update()
            elif self.dragging:
                dx = event.x() - self.last_mouse_x
                dy = event.y() - self.last_mouse_y
                self.camera_x += dx
                self.camera_y += dy
                self.last_mouse_x = event.x()
                self.last_mouse_y = event.y()
                self.update()
    
    def mouseReleaseEvent(self, event: QMouseEvent):
        """Handle mouse release"""
        if event.button() == Qt.LeftButton:
            # Check if it was a click (not a drag)
            if self.dragging_node == 'add':
                if abs(event.x() - self.last_mouse_x) < 5 and abs(event.y() - self.last_mouse_y) < 5:
                    self.add_function_requested.emit()
            
            self.mouse_down = False
            self.dragging = False
            self.dragging_node = None
            self.setCursor(Qt.ArrowCursor)
    
    def _hit_test_add_node(self, world_x, world_y):
        """Test if world coordinates hit the add node"""
        x = self.add_node_x - self.add_node_width / 2
        y = self.add_node_y - self.add_node_height / 2
        return (x <= world_x <= x + self.add_node_width and 
                y <= world_y <= y + self.add_node_height)
    
    def _hit_test_box(self, world_x, world_y, box):
        """Test if world coordinates hit a function box"""
        x = box['x'] - box['width'] / 2
        y = box['y'] - box['height'] / 2
        return (x <= world_x <= x + box['width'] and 
                y <= world_y <= y + box['height'])
