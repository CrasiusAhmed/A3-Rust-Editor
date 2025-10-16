"""
Visualization Core 3 Module
Contains context menus, connection drawing, error handling, and background rendering
Also includes connection drag dialogs for adding functions via drag-and-drop
"""

import math
import os
import time
from typing import Optional

from PySide6.QtCore import Qt, QTimer, QPointF, Signal, QSize, QRect
from PySide6.QtGui import (
    QPainter, QPen, QBrush, QColor, QFont, QPainterPath,
    QLinearGradient, QRadialGradient, QIcon, QPixmap
)
from PySide6.QtWidgets import (
    QMenu, QMessageBox, QFileDialog, QDialog, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QTreeWidget, QTreeWidgetItem, QFileSystemModel,
    QTreeView, QWidget
)


class CustomFileSystemModel(QFileSystemModel):
    """Custom file system model with Rust icon support"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.rust_main_icon = self.create_rust_icon()
        self.folder_icon = QIcon("img/folder.png")
    
    def create_rust_icon(self):
        """Create a simple Rust-like icon with an 'R' letter in Rust crate color."""
        pixmap = QPixmap(24, 24)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        # Background subtle circle
        painter.setPen(QPen(QColor("#2C2E33"), 0))
        painter.setBrush(QColor("#1E1F22"))
        painter.drawEllipse(1, 1, 22, 22)
        # 'R' glyph
        painter.setPen(QPen(QColor("#DEA584"), 2))  # Rust color tone
        font = QFont()
        font.setBold(True)
        font.setPointSize(14)
        painter.setFont(font)
        painter.drawText(QRect(0, 0, 24, 24), Qt.AlignCenter, "R")
        painter.end()
        return QIcon(pixmap)
    
    def data(self, index, role):
        if role == Qt.DecorationRole and index.column() == 0:
            file_info = self.fileInfo(index)
            if file_info.isFile():
                suffix_lower = file_info.suffix().lower()
                # All .rs files get the Rust icon
                if suffix_lower == "rs":
                    return self.rust_main_icon
            elif file_info.isDir():
                return self.folder_icon
        return super().data(index, role)

# Import necessary components
try:
    from .data_analysis import DARK_THEME, FunctionNode, Connection
except ImportError:
    from data_analysis import DARK_THEME, FunctionNode, Connection

# Apply app-wide context menu styling
try:
    from Main.menu_style_right_click import apply_default_menu_style
except Exception:
    apply_default_menu_style = None

# Document save/load
try:
    from .document_io import SaveLoadManager
except Exception:
    SaveLoadManager = None

# ---------------------- Connection Drag Dialogs (100% same as Manage2) ----------------------

class ConnectionTypeChoiceDialog(QDialog):
    """Initial dialog for choosing between Rust code or Custom content"""
    
    choice_made = Signal(str)  # Emits "rust" or "custom"
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        
    def setup_ui(self):
        """Setup the choice dialog UI"""
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setStyleSheet("background-color: transparent;")
        self.resize(500, 350)
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        self.container = QWidget()
        self.container.setStyleSheet("""
            QWidget {
                background-color: #1C1C1C;
                border: 1px solid #4A4D51;
                border-radius: 8px;
            }
            QLabel {
                background: transparent;
                border: none;
            }
        """)
        main_layout.addWidget(self.container)
        
        container_layout = QVBoxLayout(self.container)
        container_layout.setContentsMargins(1, 1, 1, 1)
        container_layout.setSpacing(0)

        # Custom Title Bar
        self.title_bar = CustomTitleBarDialog("Add Connection Node", self)
        container_layout.addWidget(self.title_bar)

        # Content
        content_layout = QVBoxLayout()
        content_layout.setContentsMargins(30, 20, 30, 30)
        content_layout.setSpacing(20)
        container_layout.addLayout(content_layout)
        
        # Title
        title = QLabel("Choose Connection Type")
        title.setStyleSheet("color: #E0E2E6; font-size: 16px; font-weight: bold; background: transparent; border: none;")
        title.setAlignment(Qt.AlignCenter)
        content_layout.addWidget(title)
        
        # Subtitle
        subtitle = QLabel("Select what type of content you want to add to your connection")
        subtitle.setStyleSheet("color: #9AA0A6; font-size: 13px; background: transparent; border: none;")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setWordWrap(True)
        content_layout.addWidget(subtitle)
        
        content_layout.addSpacing(10)
        
        # Options container
        options_layout = QHBoxLayout()
        options_layout.setSpacing(20)
        content_layout.addLayout(options_layout)
        
        # Rust Option
        rust_container = QWidget()
        rust_container.setFixedWidth(225)
        rust_container.setStyleSheet("""
            QWidget {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #3a3d41, stop:1 #202124);
                border: 1px solid rgba(255, 255, 255, 25);
                border-radius: 12px;
            }
            QWidget:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #4a4d51, stop:1 #2a2d31);
                border: 1px solid #60A5FA;
            }
        """)
        rust_container.setCursor(Qt.PointingHandCursor)
        rust_container.mousePressEvent = lambda e: self.on_choice_selected("rust")
        
        rust_layout = QVBoxLayout(rust_container)
        rust_layout.setContentsMargins(25, 35, 25, 35)
        rust_layout.setSpacing(15)
        
        # Rust icon (no border, no hover effect on icon itself)
        rust_icon_label = QLabel()
        rust_icon_label.setStyleSheet("background: transparent; border: none;")
        rust_pixmap = QIcon("img/Rust.png").pixmap(80, 80)
        rust_icon_label.setPixmap(rust_pixmap)
        rust_icon_label.setAlignment(Qt.AlignCenter)
        rust_layout.addWidget(rust_icon_label)
        
        # Rust title
        rust_title = QLabel("Rust Code")
        rust_title.setStyleSheet("color: #E0E2E6; font-size: 15px; font-weight: bold; background: transparent; border: none;")
        rust_title.setAlignment(Qt.AlignCenter)
        rust_layout.addWidget(rust_title)
        
        # Rust description
        rust_desc = QLabel("Add functions, structs, or implementations from Rust files")
        rust_desc.setStyleSheet("color: #9AA0A6; font-size: 11px; background: transparent; border: none;")
        rust_desc.setAlignment(Qt.AlignCenter)
        rust_desc.setWordWrap(True)
        rust_layout.addWidget(rust_desc)
        
        options_layout.addWidget(rust_container)
        
        # Custom Option
        custom_container = QWidget()
        custom_container.setFixedWidth(225)
        custom_container.setStyleSheet("""
            QWidget {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #3a3d41, stop:1 #202124);
                border: 1px solid rgba(255, 255, 255, 25);
                border-radius: 12px;
            }
            QWidget:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #4a4d51, stop:1 #2a2d31);
                border: 1px solid #60A5FA;
            }
        """)
        custom_container.setCursor(Qt.PointingHandCursor)
        custom_container.mousePressEvent = lambda e: self.on_choice_selected("custom")
        
        custom_layout = QVBoxLayout(custom_container)
        custom_layout.setContentsMargins(25, 35, 25, 35)
        custom_layout.setSpacing(15)
        
        # Custom icon (no border, no hover effect on icon itself)
        custom_icon_label = QLabel()
        custom_icon_label.setStyleSheet("background: transparent; border: none;")
        custom_pixmap = QIcon("img/Warning.png").pixmap(80, 80)
        custom_icon_label.setPixmap(custom_pixmap)
        custom_icon_label.setAlignment(Qt.AlignCenter)
        custom_layout.addWidget(custom_icon_label)
        
        # Custom title
        custom_title = QLabel("Custom Content")
        custom_title.setStyleSheet("color: #E0E2E6; font-size: 15px; font-weight: bold; background: transparent; border: none;")
        custom_title.setAlignment(Qt.AlignCenter)
        custom_layout.addWidget(custom_title)
        
        # Custom description
        custom_desc = QLabel("Add custom text, images, videos, or other content")
        custom_desc.setStyleSheet("color: #9AA0A6; font-size: 11px; background: transparent; border: none;")
        custom_desc.setAlignment(Qt.AlignCenter)
        custom_desc.setWordWrap(True)
        custom_layout.addWidget(custom_desc)
        
        options_layout.addWidget(custom_container)
        
        content_layout.addStretch()
        
        # Cancel button
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #3C4043;
                color: #E0E2E6;
                border: 1px solid #4A4D51;
                border-radius: 4px;
                padding: 8px 20px;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #4A4D51;
            }
            QPushButton:pressed {
                background-color: #5A5D61;
            }
        """)
        cancel_btn.clicked.connect(self.reject)
        content_layout.addWidget(cancel_btn, alignment=Qt.AlignCenter)
    
    def on_choice_selected(self, choice):
        """Handle choice selection"""
        self.choice_made.emit(choice)
        self.accept()


class CustomContentTypeDialog(QDialog):
    """Dialog for choosing custom content type (Text, Image, Video) with navigation"""
    
    content_type_selected = Signal(str)  # Emits "text", "image", or "video"
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_index = 0
        self.content_types = [
            {"type": "text", "title": "Text", "icon": "img/Connection2.png", "desc": "Add custom text content"},
            {"type": "image", "title": "Image", "icon": "img/Manage_Image.png", "desc": "Add image content"},
            {"type": "video", "title": "Video", "icon": "img/Manage_Video.png", "desc": "Add video content"}
        ]
        self.setup_ui()
        self.update_card()
        
    def setup_ui(self):
        """Setup the custom content type dialog UI"""
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setStyleSheet("background-color: transparent;")
        self.resize(400, 450)
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        self.container = QWidget()
        self.container.setStyleSheet("""
            QWidget {
                background-color: #1C1C1C;
                border: 1px solid #4A4D51;
                border-radius: 8px;
            }
            QLabel {
                background: transparent;
                border: none;
            }
        """)
        main_layout.addWidget(self.container)
        
        container_layout = QVBoxLayout(self.container)
        container_layout.setContentsMargins(1, 1, 1, 1)
        container_layout.setSpacing(0)

        # Custom Title Bar
        self.title_bar = CustomTitleBarDialog("Add Custom Content", self)
        container_layout.addWidget(self.title_bar)

        # Content
        content_layout = QVBoxLayout()
        content_layout.setContentsMargins(30, 20, 30, 30)
        content_layout.setSpacing(20)
        container_layout.addLayout(content_layout)
        
        # Title
        title = QLabel("Choose Content Type")
        title.setStyleSheet("color: #E0E2E6; font-size: 16px; font-weight: bold; background: transparent; border: none;")
        title.setAlignment(Qt.AlignCenter)
        content_layout.addWidget(title)
        
        # Subtitle
        subtitle = QLabel("Select the type of custom content you want to add")
        subtitle.setStyleSheet("color: #9AA0A6; font-size: 13px; background: transparent; border: none;")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setWordWrap(True)
        content_layout.addWidget(subtitle)
        
        content_layout.addSpacing(20)
        
        # Single card container (centered)
        card_container_layout = QHBoxLayout()
        card_container_layout.addStretch()
        
        # Card
        self.card_container = QWidget()
        self.card_container.setFixedWidth(220)
        self.card_container.setStyleSheet("""
            QWidget {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #3a3d41, stop:1 #202124);
                border: 1px solid rgba(255, 255, 255, 25);
                border-radius: 12px;
            }
            QWidget:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #4a4d51, stop:1 #2a2d31);
                border: 1px solid #60A5FA;
            }
        """)
        self.card_container.setCursor(Qt.PointingHandCursor)
        self.card_container.mousePressEvent = lambda e: self.on_card_clicked()
        
        self.card_layout = QVBoxLayout(self.card_container)
        self.card_layout.setContentsMargins(30, 40, 30, 40)
        self.card_layout.setSpacing(15)
        
        # Icon
        self.card_icon_label = QLabel()
        self.card_icon_label.setStyleSheet("background: transparent; border: none;")
        self.card_icon_label.setAlignment(Qt.AlignCenter)
        self.card_layout.addWidget(self.card_icon_label)
        
        # Title
        self.card_title = QLabel()
        self.card_title.setStyleSheet("color: #E0E2E6; font-size: 15px; font-weight: bold; background: transparent; border: none;")
        self.card_title.setAlignment(Qt.AlignCenter)
        self.card_layout.addWidget(self.card_title)
        
        # Description
        self.card_desc = QLabel()
        self.card_desc.setStyleSheet("color: #9AA0A6; font-size: 11px; background: transparent; border: none;")
        self.card_desc.setAlignment(Qt.AlignCenter)
        self.card_desc.setWordWrap(True)
        self.card_layout.addWidget(self.card_desc)
        
        card_container_layout.addWidget(self.card_container)
        card_container_layout.addStretch()
        content_layout.addLayout(card_container_layout)
        
        content_layout.addSpacing(20)
        
        # Navigation arrows with label
        nav_layout = QHBoxLayout()
        nav_layout.setSpacing(15)
        
        # Left arrow
        self.left_arrow = QPushButton("◀")
        self.left_arrow.setFixedSize(40, 40)
        self.left_arrow.setStyleSheet("""
            QPushButton {
                background-color: #3C4043;
                color: #E0E2E6;
                border: 1px solid #4A4D51;
                border-radius: 20px;
                font-size: 16px;
            }
            QPushButton:hover {
                background-color: #4A4D51;
                border: 1px solid #60A5FA;
            }
            QPushButton:pressed {
                background-color: #5A5D61;
            }
            QPushButton:disabled {
                background-color: #2C2E33;
                color: #5A5D61;
                border: 1px solid #3C4043;
            }
        """)
        self.left_arrow.clicked.connect(self.previous_card)
        nav_layout.addWidget(self.left_arrow)
        
        # Current type label
        self.type_label = QLabel()
        self.type_label.setStyleSheet("color: #E0E2E6; font-size: 14px; font-weight: bold; background: transparent; border: none;")
        self.type_label.setAlignment(Qt.AlignCenter)
        self.type_label.setMinimumWidth(100)
        nav_layout.addWidget(self.type_label)
        
        # Right arrow
        self.right_arrow = QPushButton("▶")
        self.right_arrow.setFixedSize(40, 40)
        self.right_arrow.setStyleSheet("""
            QPushButton {
                background-color: #3C4043;
                color: #E0E2E6;
                border: 1px solid #4A4D51;
                border-radius: 20px;
                font-size: 16px;
            }
            QPushButton:hover {
                background-color: #4A4D51;
                border: 1px solid #60A5FA;
            }
            QPushButton:pressed {
                background-color: #5A5D61;
            }
            QPushButton:disabled {
                background-color: #2C2E33;
                color: #5A5D61;
                border: 1px solid #3C4043;
            }
        """)
        self.right_arrow.clicked.connect(self.next_card)
        nav_layout.addWidget(self.right_arrow)
        
        # Add navigation layout centered
        nav_container = QHBoxLayout()
        nav_container.addStretch()
        nav_container.addLayout(nav_layout)
        nav_container.addStretch()
        content_layout.addLayout(nav_container)
        
        content_layout.addStretch()
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)
        
        # Cancel button
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #3C4043;
                color: #E0E2E6;
                border: 1px solid #4A4D51;
                border-radius: 4px;
                padding: 8px 20px;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #4A4D51;
            }
            QPushButton:pressed {
                background-color: #5A5D61;
            }
        """)
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        
        # Select button
        select_btn = QPushButton("Select")
        select_btn.setStyleSheet("""
            QPushButton {
                background-color: #60A5FA;
                color: #FFFFFF;
                border: 1px solid #60A5FA;
                border-radius: 4px;
                padding: 8px 20px;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #4A8FE7;
            }
            QPushButton:pressed {
                background-color: #3A7FD7;
            }
        """)
        select_btn.clicked.connect(self.on_card_clicked)
        button_layout.addWidget(select_btn)
        
        # Add button layout centered
        button_container = QHBoxLayout()
        button_container.addStretch()
        button_container.addLayout(button_layout)
        button_container.addStretch()
        content_layout.addLayout(button_container)
    
    def update_card(self):
        """Update the card display based on current index"""
        content = self.content_types[self.current_index]
        
        # Update icon
        icon_pixmap = QIcon(content["icon"]).pixmap(90, 90)
        self.card_icon_label.setPixmap(icon_pixmap)
        
        # Update title and description
        self.card_title.setText(content["title"])
        self.card_desc.setText(content["desc"])
        self.type_label.setText(content["title"])
        
        # Update arrow states
        self.left_arrow.setEnabled(self.current_index > 0)
        self.right_arrow.setEnabled(self.current_index < len(self.content_types) - 1)
    
    def previous_card(self):
        """Navigate to previous card"""
        if self.current_index > 0:
            self.current_index -= 1
            self.update_card()
    
    def next_card(self):
        """Navigate to next card"""
        if self.current_index < len(self.content_types) - 1:
            self.current_index += 1
            self.update_card()
    
    def on_card_clicked(self):
        """Handle card selection"""
        content_type = self.content_types[self.current_index]["type"]
        self.content_type_selected.emit(content_type)
        self.accept()


class CustomTitleBarDialog(QWidget):
    """Custom title bar matching Details/dialogs.py"""
    def __init__(self, title, parent):
        super().__init__(parent)
        self.parent_dialog = parent
        self.setFixedHeight(35)
        self.m_old_pos = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 0, 5, 0)
        layout.setSpacing(5)

        self.title_label = QLabel(title, self)
        self.title_label.setStyleSheet("color: #BDC1C6; font-size: 14px; font-weight: bold;")
        layout.addWidget(self.title_label)

        layout.addStretch()

        self.close_button = QPushButton("✕", self)
        self.close_button.setFixedSize(30, 30)
        self.close_button.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #BDC1C6;
                border: none;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #E81123;
                color: white;
            }
        """)
        self.close_button.clicked.connect(self.parent_dialog.reject)
        layout.addWidget(self.close_button)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.m_old_pos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event):
        if self.m_old_pos is not None:
            delta = event.globalPosition().toPoint() - self.m_old_pos
            self.parent_dialog.move(self.parent_dialog.x() + delta.x(), self.parent_dialog.y() + delta.y())
            self.m_old_pos = event.globalPosition().toPoint()

    def mouseReleaseEvent(self, event):
        self.m_old_pos = None


class ConnectionFileSelectionDialog(QDialog):
    """Dialog for selecting Rust files to add to connection"""
    
    files_selected = Signal(list)  # Emits list of selected file paths
    
    def __init__(self, root_path, parent=None):
        super().__init__(parent)
        self.root_path = root_path
        self.selected_files = []
        self.setup_ui()
        
    def setup_ui(self):
        """Setup the file selection dialog UI"""
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setStyleSheet("background-color: transparent;")
        self.resize(600, 500)
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        self.container = QWidget()
        self.container.setStyleSheet("""
            QWidget {
                background-color: #1C1C1C;
                border: 1px solid #4A4D51;
                border-radius: 8px;
            }
            QLabel {
                background: transparent;
                border: none;
            }
        """)
        main_layout.addWidget(self.container)
        
        container_layout = QVBoxLayout(self.container)
        container_layout.setContentsMargins(1, 1, 1, 1)
        container_layout.setSpacing(0)

        # Custom Title Bar
        self.title_bar = CustomTitleBarDialog("Select Rust Files", self)
        container_layout.addWidget(self.title_bar)

        # Content
        content_layout = QVBoxLayout()
        content_layout.setContentsMargins(20, 10, 20, 20)
        content_layout.setSpacing(10)
        container_layout.addLayout(content_layout)
        
        # Subtitle
        subtitle = QLabel("Choose one or more .rs files to include in your connection")
        subtitle.setStyleSheet("color: #E0E2E6; font-size: 13px; background: transparent; border: none;")
        content_layout.addWidget(subtitle)
        
        # File tree view
        self.file_model = CustomFileSystemModel()
        self.file_model.setRootPath(self.root_path)
        self.file_model.setNameFilters(["*.rs"])
        self.file_model.setNameFilterDisables(False)
        
        self.tree_view = QTreeView()
        self.tree_view.setModel(self.file_model)
        self.tree_view.setRootIndex(self.file_model.index(self.root_path))
        self.tree_view.setSelectionMode(QTreeView.ExtendedSelection)
        self.tree_view.setColumnWidth(0, 300)
        self.tree_view.setMinimumHeight(300)
        # Import scrollbar styling
        try:
            from file_showen import apply_modern_scrollbar_style
            scrollbar_style = apply_modern_scrollbar_style()
        except Exception:
            scrollbar_style = ""
        
        self.tree_view.setStyleSheet("""
            QTreeView {
                background-color: #1E1F22;
                color: #E0E2E6;
                border: 1px solid #4A4D51;
                border-radius: 4px;
                selection-background-color: #2C2E33;
            }
            QTreeView::item:hover {
                background-color: #2C2E33;
            }
            QTreeView::item:selected {
                background-color: #60A5FA;
                color: #FFFFFF;
            }
            QTreeView::branch:closed:has-children {
                image: url(img/branch-closed.svg);
            }
            QTreeView::branch:open:has-children {
                image: url(img/branch-open.svg);
            }
            QHeaderView::section {
                background-color: #252729;
                color: #E0E2E6;
                border: none;
                padding: 8px;
                font-weight: bold;
            }
        """ + scrollbar_style)
        
        # Hide unnecessary columns
        for i in range(1, self.file_model.columnCount()):
            self.tree_view.hideColumn(i)
        
        content_layout.addWidget(self.tree_view)
        
        # Selected files label
        self.selected_label = QLabel("No files selected")
        self.selected_label.setStyleSheet("font-size: 12px; color: #9AA0A6; padding: 5px; background: transparent; border: none;")
        content_layout.addWidget(self.selected_label)
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #3C4043;
                color: #E0E2E6;
                border: 1px solid #4A4D51;
                border-radius: 4px;
                padding: 8px 20px;
                min-width: 60px;
            }
            QPushButton:hover {
                background-color: #4A4D51;
            }
            QPushButton:pressed {
                background-color: #5A5D61;
            }
        """)
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        
        self.ok_btn = QPushButton("OK")
        self.ok_btn.setStyleSheet("""
            QPushButton {
                background-color: #3C4043;
                color: #E0E2E6;
                border: 1px solid #4A4D51;
                border-radius: 4px;
                padding: 8px 20px;
                min-width: 60px;
            }
            QPushButton:hover {
                background-color: #4A4D51;
            }
            QPushButton:pressed {
                background-color: #5A5D61;
            }
        """)
        self.ok_btn.clicked.connect(self.accept_selection)
        button_layout.addWidget(self.ok_btn)
        
        content_layout.addLayout(button_layout)
        
        # Connect selection changed and double-click
        self.tree_view.selectionModel().selectionChanged.connect(self.on_selection_changed)
        self.tree_view.doubleClicked.connect(self.on_item_double_clicked)
        
    def on_item_double_clicked(self, index):
        """Handle double-click on file - auto-accept selection"""
        file_path = self.file_model.filePath(index)
        if os.path.isfile(file_path) and file_path.endswith('.rs'):
            # Double-clicked on a .rs file - accept immediately
            self.accept_selection()
    
    def on_selection_changed(self):
        """Update selected files label"""
        indexes = self.tree_view.selectedIndexes()
        self.selected_files = []
        
        for index in indexes:
            file_path = self.file_model.filePath(index)
            if os.path.isfile(file_path) and file_path.endswith('.rs'):
                self.selected_files.append(file_path)
        
        count = len(self.selected_files)
        if count == 0:
            self.selected_label.setText("No files selected")
        elif count == 1:
            self.selected_label.setText(f"1 file selected: {os.path.basename(self.selected_files[0])}")
        else:
            self.selected_label.setText(f"{count} files selected")
    
    def accept_selection(self):
        """Accept and emit selected files"""
        if self.selected_files:
            self.files_selected.emit(self.selected_files)
            self.accept()


class ConnectionFunctionSelectionDialog(QDialog):
    """Dialog for selecting functions/classes from Rust files"""
    
    function_selected = Signal(str, str)  # Emits (function_name, function_type)
    
    def __init__(self, file_paths, parent=None, existing_nodes=None):
        super().__init__(parent)
        self.file_paths = file_paths
        self.existing_nodes = existing_nodes or []  # List of node names already on canvas
        self.setup_ui()
        self.load_functions()
        
    def setup_ui(self):
        """Setup the function selection dialog UI"""
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setStyleSheet("background-color: transparent;")
        self.resize(500, 600)
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        self.container = QWidget()
        self.container.setStyleSheet("""
            QWidget {
                background-color: #1C1C1C;
                border: 1px solid #4A4D51;
                border-radius: 8px;
            }
            QLabel {
                background: transparent;
                border: none;
            }
        """)
        main_layout.addWidget(self.container)
        
        container_layout = QVBoxLayout(self.container)
        container_layout.setContentsMargins(1, 1, 1, 1)
        container_layout.setSpacing(0)

        # Custom Title Bar
        self.title_bar = CustomTitleBarDialog("Select Function or Class", self)
        container_layout.addWidget(self.title_bar)

        # Content
        content_layout = QVBoxLayout()
        content_layout.setContentsMargins(20, 10, 20, 20)
        content_layout.setSpacing(15)
        container_layout.addLayout(content_layout)
        
        # Subtitle
        subtitle = QLabel("Choose a function or class to add to your connection")
        subtitle.setStyleSheet("color: #E0E2E6; font-size: 13px; background: transparent; border: none;")
        content_layout.addWidget(subtitle)
        
        # Function tree
        self.function_tree = QTreeWidget()
        self.function_tree.setHeaderLabels(["Name", "Type"])
        self.function_tree.setColumnWidth(0, 300)
        self.function_tree.setMinimumHeight(400)
        self.function_tree.setIconSize(QSize(40, 40))  # Set larger icon size
        self.function_tree.itemDoubleClicked.connect(self.on_item_double_clicked)
        # Import scrollbar styling
        try:
            from file_showen import apply_modern_scrollbar_style
            scrollbar_style = apply_modern_scrollbar_style()
        except Exception:
            scrollbar_style = ""
        
        self.function_tree.setStyleSheet("""
            QTreeWidget {
                background-color: #1E1F22;
                color: #E0E2E6;
                border: 1px solid #4A4D51;
                border-radius: 4px;
            }
            QTreeWidget::item {
                padding: 8px;
                border-bottom: 1px solid #2C2E33;
            }
            QTreeWidget::item:hover {
                background-color: #2C2E33;
            }
            QTreeWidget::item:selected {
                background-color: #60A5FA;
                color: #FFFFFF;
            }
            QTreeWidget::branch:closed:has-children {
                image: url(img/branch-closed.svg);
            }
            QTreeWidget::branch:open:has-children {
                image: url(img/branch-open.svg);
            }
            QHeaderView::section {
                background-color: #1C1C1C;
                color: #E0E2E6;
                border: none;
                padding: 8px;
                font-weight: bold;
            }
        """ + scrollbar_style)
        content_layout.addWidget(self.function_tree)
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #3C4043;
                color: #E0E2E6;
                border: 1px solid #4A4D51;
                border-radius: 4px;
                padding: 8px 20px;
                min-width: 60px;
            }
            QPushButton:hover {
                background-color: #4A4D51;
            }
            QPushButton:pressed {
                background-color: #5A5D61;
            }
        """)
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        
        add_btn = QPushButton("Add to Canvas")
        add_btn.setStyleSheet("""
            QPushButton {
                background-color: #3C4043;
                color: #E0E2E6;
                border: 1px solid #4A4D51;
                border-radius: 4px;
                padding: 8px 20px;
                min-width: 60px;
            }
            QPushButton:hover {
                background-color: #4A4D51;
            }
            QPushButton:pressed {
                background-color: #5A5D61;
            }
        """)
        add_btn.clicked.connect(self.add_selected)
        button_layout.addWidget(add_btn)
        
        content_layout.addLayout(button_layout)
    
    def load_functions(self):
        """Load functions and classes from selected Rust files"""
        for file_path in self.file_paths:
            file_item = QTreeWidgetItem(self.function_tree)
            file_item.setText(0, os.path.basename(file_path))
            file_item.setText(1, "File")
            # Larger icon for file (48x48)
            rust_icon = QIcon("img/Rust.png")
            file_item.setIcon(0, rust_icon)
            file_item.setSizeHint(0, QSize(40, 40))
            
            # Parse Rust file for functions and structs
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                # Simple parsing for functions
                for line in content.split('\n'):
                    line = line.strip()
                    
                    # Find functions
                    if line.startswith('fn ') or line.startswith('pub fn '):
                        func_name = line.split('(')[0].replace('fn ', '').replace('pub ', '').strip()
                        # Skip if already exists on canvas
                        if func_name in self.existing_nodes:
                            continue
                        func_item = QTreeWidgetItem(file_item)
                        func_item.setText(0, func_name)
                        func_item.setText(1, "Function")
                        func_item.setIcon(0, QIcon("img/Connection.png"))
                        func_item.setSizeHint(0, QSize(32, 32))
                        func_item.setData(0, Qt.UserRole, file_path)
                        func_item.setData(1, Qt.UserRole, "function")
                    
                    # Find structs
                    elif line.startswith('struct ') or line.startswith('pub struct '):
                        struct_name = line.split('{')[0].split('<')[0].replace('struct ', '').replace('pub ', '').strip()
                        # Skip if already exists on canvas
                        if struct_name in self.existing_nodes:
                            continue
                        struct_item = QTreeWidgetItem(file_item)
                        struct_item.setText(0, struct_name)
                        struct_item.setText(1, "Struct")
                        struct_item.setIcon(0, QIcon("img/Warning.png"))
                        struct_item.setSizeHint(0, QSize(32, 32))
                        struct_item.setData(0, Qt.UserRole, file_path)
                        struct_item.setData(1, Qt.UserRole, "struct")
                    
                    # Find enums
                    elif line.startswith('enum ') or line.startswith('pub enum '):
                        enum_name = line.split('{')[0].split('<')[0].replace('enum ', '').replace('pub ', '').strip()
                        # Skip if already exists on canvas
                        if enum_name in self.existing_nodes:
                            continue
                        enum_item = QTreeWidgetItem(file_item)
                        enum_item.setText(0, enum_name)
                        enum_item.setText(1, "Enum")
                        enum_item.setIcon(0, QIcon("img/Warning.png"))
                        enum_item.setSizeHint(0, QSize(32, 32))
                        enum_item.setData(0, Qt.UserRole, file_path)
                        enum_item.setData(1, Qt.UserRole, "enum")
                    
                    # Find traits
                    elif line.startswith('trait ') or line.startswith('pub trait '):
                        trait_name = line.split('{')[0].split('<')[0].replace('trait ', '').replace('pub ', '').strip()
                        # Skip if already exists on canvas
                        if trait_name in self.existing_nodes:
                            continue
                        trait_item = QTreeWidgetItem(file_item)
                        trait_item.setText(0, trait_name)
                        trait_item.setText(1, "Trait")
                        trait_item.setIcon(0, QIcon("img/Trait.png"))
                        trait_item.setSizeHint(0, QSize(32, 32))
                        trait_item.setData(0, Qt.UserRole, file_path)
                        trait_item.setData(1, Qt.UserRole, "trait")
                    
                    # Find impl blocks
                    elif line.startswith('impl ') or line.startswith('pub impl '):
                        impl_name = line.split('{')[0].split('<')[0].replace('impl ', '').replace('pub ', '').strip()
                        # Skip if already exists on canvas (check with "impl " prefix)
                        if f"impl {impl_name}" in self.existing_nodes:
                            continue
                        impl_item = QTreeWidgetItem(file_item)
                        impl_item.setText(0, f"impl {impl_name}")
                        impl_item.setText(1, "Implementation")
                        impl_item.setIcon(0, QIcon("img/Error.png"))
                        impl_item.setSizeHint(0, QSize(32, 32))
                        impl_item.setData(0, Qt.UserRole, file_path)
                        impl_item.setData(1, Qt.UserRole, "impl")
                    
                    # Find type aliases
                    elif line.startswith('type ') or line.startswith('pub type '):
                        type_name = line.split('=')[0].replace('type ', '').replace('pub ', '').strip()
                        # Skip if already exists on canvas
                        if type_name in self.existing_nodes:
                            continue
                        type_item = QTreeWidgetItem(file_item)
                        type_item.setText(0, type_name)
                        type_item.setText(1, "Type Alias")
                        type_item.setIcon(0, QIcon("img/Type.png"))
                        type_item.setSizeHint(0, QSize(32, 32))
                        type_item.setData(0, Qt.UserRole, file_path)
                        type_item.setData(1, Qt.UserRole, "type")
                    
                    # Find const declarations
                    elif line.startswith('const ') or line.startswith('pub const '):
                        const_name = line.split(':')[0].replace('const ', '').replace('pub ', '').strip()
                        # Skip if already exists on canvas
                        if const_name in self.existing_nodes:
                            continue
                        const_item = QTreeWidgetItem(file_item)
                        const_item.setText(0, const_name)
                        const_item.setText(1, "Constant")
                        const_item.setIcon(0, QIcon("img/Const.png"))
                        const_item.setSizeHint(0, QSize(32, 32))
                        const_item.setData(0, Qt.UserRole, file_path)
                        const_item.setData(1, Qt.UserRole, "const")
                    
                    # Find modules
                    elif line.startswith('mod ') or line.startswith('pub mod '):
                        mod_name = line.split('{')[0].split(';')[0].replace('mod ', '').replace('pub ', '').strip()
                        # Skip if already exists on canvas
                        if mod_name in self.existing_nodes:
                            continue
                        mod_item = QTreeWidgetItem(file_item)
                        mod_item.setText(0, mod_name)
                        mod_item.setText(1, "Module")
                        mod_item.setIcon(0, QIcon("img/Module.png"))
                        mod_item.setSizeHint(0, QSize(32, 32))
                        mod_item.setData(0, Qt.UserRole, file_path)
                        mod_item.setData(1, Qt.UserRole, "mod")
                        
            except Exception as e:
                print(f"Error parsing {file_path}: {e}")
        
        self.function_tree.expandAll()
    
    def on_item_double_clicked(self, item, column):
        """Handle double click on item"""
        if item.text(1) != "File":
            self.add_item(item)
    
    def add_selected(self):
        """Add selected item to canvas"""
        current_item = self.function_tree.currentItem()
        if current_item and current_item.text(1) != "File":
            self.add_item(current_item)
    
    def add_item(self, item):
        """Emit signal to add item to canvas"""
        name = item.text(0)
        item_type = item.text(1)
        self.function_selected.emit(name, item_type)
        self.accept()

# ---------------------- Context Menus ----------------------
def contextMenuEvent(self, event):
    try:
        pos = event.pos()
        node = self.get_node_at_position(pos.x(), pos.y())
        if node:
            self._show_node_context_menu(event.globalPos(), node)
        else:
            self._show_background_context_menu(event.globalPos())
    except Exception:
        pass

def _show_node_context_menu(self, global_pos, node):
    menu = QMenu(self)
    try:
        if apply_default_menu_style:
            apply_default_menu_style(menu)
    except Exception:
        pass
    # Go To File: only enabled for module/main nodes with a file path
    go_to_file = menu.addAction('Go To File')
    fp = None
    try:
        fp = (node.data or {}).get('file_path')
    except Exception:
        fp = None
    go_to_file.setEnabled(bool(fp))
    go_to_file.setShortcut('Ctrl+G')
    # Open Editor: enables always; behavior handled by host
    open_editor = menu.addAction('Open Editor')
    open_editor.setShortcut('Return')
    # Remove Connection (UI only)
    remove_conn = menu.addAction('Remove Connection')
    remove_conn.setShortcut('Shift+Delete')
    # Information
    info_act = menu.addAction('Information')
    info_act.setShortcut('I')
    # Delete
    del_act = menu.addAction('Delete')
    del_act.setShortcut('Delete')

    act = menu.exec(global_pos)
    if not act:
        return
    if act == go_to_file and fp:
        self.request_open_file.emit(fp)
    elif act == open_editor:
        self.request_open_editor.emit(node, fp or '')
    elif act == remove_conn:
        # Hide all connections to/from this node
        try:
            affected = []
            for c in self.connections:
                if c.from_node is node or c.to_node is node:
                    affected.append(c)
                    setattr(c, 'hidden', True)
            # Push undo
            self._push_undo({'type': 'hide_connections', 'items': affected})
            self.update()
        except Exception:
            pass
    elif act == info_act:
        try:
            outgoing = len([c for c in self.connections if c.from_node is node and not getattr(c, 'hidden', False)])
            incoming = len([c for c in self.connections if c.to_node is node and not getattr(c, 'hidden', False)])
            file_info = (node.data or {}).get('file_path') if hasattr(node, 'data') else None
            msg = f"Name: {node.name}\nCalls: {outgoing}\nCalled by: {incoming}"
            if file_info:
                msg += f"\nFile: {file_info}"
            QMessageBox.information(self, 'Connection Info', msg)
        except Exception:
            pass
    elif act == del_act:
        try:
            # Prepare undo payload
            removed_conns = [c for c in self.connections if c.from_node is node or c.to_node is node]
            # Remove node and its connections
            self.connections = [c for c in self.connections if c.from_node is not node and c.to_node is not node]
            try:
                self.nodes.remove(node)
            except ValueError:
                pass
            # Push undo
            self._push_undo({'type': 'delete_node', 'node': node, 'connections': removed_conns})
            # Rebuild index
            self._node_by_name = {}
            for n in self.nodes:
                self._index_node(n)
            self.update()
        except Exception:
            pass

def _show_background_context_menu(self, global_pos):
    menu = QMenu(self)
    try:
        if apply_default_menu_style:
            apply_default_menu_style(menu)
    except Exception:
        pass
    undo_act = menu.addAction('Undo')
    redo_act = menu.addAction('Redo')
    undo_act.setEnabled(bool(self._undo_stack))
    redo_act.setEnabled(bool(self._redo_stack))
    undo_act.setShortcut('Ctrl+Z')
    redo_act.setShortcut('Ctrl+Y')
    # Save/Load layout actions
    save_layout_act = menu.addAction('Save Layout...')
    open_layout_act = menu.addAction('Open Layout...')
    save_layout_act.setShortcut('Ctrl+Alt+S')
    open_layout_act.setShortcut('Ctrl+O')
    menu.addSeparator()
    search_act = menu.addAction('Search')
    search_act.setShortcut('Ctrl+F')
    remove_file_act = menu.addAction('Remove File')
    # Toggle Activity label based on host state if available
    try:
        host = self.parent()
        enabled = bool(getattr(host, 'activity_enabled', False))
        toggle_text = 'Stop Activity' if enabled else 'Start Activity'
    except Exception:
        toggle_text = 'Stop Activity'
    toggle_activity = menu.addAction(toggle_text)

    act = menu.exec(global_pos)
    if not act:
        return
    if act == undo_act:
        self.undo()
    elif act == redo_act:
        self.redo()
    elif act == save_layout_act:
        # Use same logic as Save A3 Project from manage_native.py
        try:
            if not SaveLoadManager:
                QMessageBox.warning(self, 'Save Layout', 'Save/Load manager not available.')
            else:
                host = self.parent()
                
                # Get top toolbar with project state
                top_toolbar = None
                if hasattr(host, 'top_toolbar'):
                    top_toolbar = host.top_toolbar
                elif hasattr(host, 'parent') and hasattr(host.parent(), 'top_toolbar'):
                    top_toolbar = host.parent().top_toolbar
                
                if not top_toolbar:
                    QMessageBox.warning(self, 'Save Layout', 'Project manager not available.')
                    return
                
                # Ask user if they want to save current canvas as "whole file" default view
                save_as_whole_file = False
                if len(self.nodes) > 0:
                    reply = QMessageBox.question(
                        self,
                        "Save Whole File View?",
                        "Do you want to save the current canvas as the default 'Whole File' view?\n\n"
                        "• YES: Current canvas will be shown by default when loading this .mndoc\n"
                        "• NO: Canvas will be empty by default (only Layer menu projects saved)",
                        QMessageBox.Yes | QMessageBox.No,
                        QMessageBox.No
                    )
                    save_as_whole_file = (reply == QMessageBox.Yes)
                
                # Collect current canvas state WITH all Layer menu projects
                mgr = SaveLoadManager()
                state = mgr.collect_state(
                    host, 
                    include_projects=True,
                    save_as_whole_file=save_as_whole_file
                )
                
                # Ask user where to save
                file_path, _ = QFileDialog.getSaveFileName(
                    self,
                    "Save Layout",
                    "",
                    mgr.suggested_filter()
                )
                
                if file_path:
                    # Ensure .mndoc extension
                    file_path = mgr.ensure_extension(file_path)
                    
                    # Save to file (includes all projects)
                    mgr.save_to_file(file_path, state)
                    
                    # Mark all projects as saved
                    project_state = top_toolbar.project_state
                    for project in project_state.get_all_projects():
                        project_state.mark_project_saved(project.id)
                    
                    # Show custom success dialog
                    try:
                        from Manage2.project_dialogs import SaveSuccessDialog
                        success_dialog = SaveSuccessDialog(
                            file_path,
                            len(state.get('projects', {})),
                            save_as_whole_file,
                            self
                        )
                        success_dialog.exec()
                    except Exception:
                        QMessageBox.information(self, 'Save Layout', f'Saved layout to:\n{file_path}')
        except Exception as e:
            QMessageBox.critical(self, 'Save Layout Error', str(e))
    elif act == open_layout_act:
        # Use same logic as Load A3 Project from manage_native.py
        try:
            if not SaveLoadManager:
                QMessageBox.warning(self, 'Open Layout', 'Save/Load manager not available.')
            else:
                from Manage.data_analysis import FunctionNode
                
                mgr = SaveLoadManager()
                host = self.parent()
                
                # Get top toolbar with project state
                top_toolbar = None
                if hasattr(host, 'top_toolbar'):
                    top_toolbar = host.top_toolbar
                elif hasattr(host, 'parent') and hasattr(host.parent(), 'top_toolbar'):
                    top_toolbar = host.parent().top_toolbar
                
                if not top_toolbar:
                    QMessageBox.warning(self, 'Open Layout', 'Project manager not available.')
                    return
                
                # Ask user which file to load
                file_path, _ = QFileDialog.getOpenFileName(
                    self,
                    "Open Layout",
                    "",
                    mgr.suggested_filter()
                )
                
                if not file_path or not os.path.exists(file_path):
                    return
                
                # Load the document
                doc = mgr.load_from_file(file_path)
                
                # Restore Layer menu projects if present
                projects_data = doc.get('projects', {})
                if projects_data:
                    # Get project state manager
                    project_state = top_toolbar.project_state
                    
                    # Clear existing projects
                    project_state.projects = {}
                    
                    # Restore each project
                    from Manage2.project_state import ProjectData
                    for project_id_str, project_dict in projects_data.items():
                        try:
                            project = ProjectData.from_dict(project_dict)
                            project_state.projects[project.id] = project
                        except Exception:
                            pass
                    
                    # Restore next_project_id and active_project_id
                    if 'next_project_id' in doc:
                        project_state.next_project_id = doc['next_project_id']
                    if 'active_project_id' in doc:
                        project_state.active_project_id = doc['active_project_id']
                    
                    # Refresh Layer menu
                    top_toolbar.refresh_projects_list()
                
                # Clear canvas first
                self.clear()
                
                # Check if there's a "whole_file" view saved (new format)
                whole_file_data = doc.get('whole_file')
                if whole_file_data:
                    nodes_data = whole_file_data.get('nodes', [])
                else:
                    # Fall back to old format (nodes at root level)
                    nodes_data = doc.get('nodes', [])
                
                if nodes_data:
                    # Recreate nodes from saved data
                    for idx, node_data in enumerate(nodes_data):
                        try:
                            node_name = node_data.get('name', '')
                            node_x = node_data.get('x', 0.0)
                            node_y = node_data.get('y', 0.0)
                            
                            # Create node data dict with all saved fields
                            data = {
                                'name': node_name,
                                'lineno': node_data.get('lineno', 0),
                                'end_lineno': node_data.get('end_lineno', 0),
                                'args': [],
                                'docstring': node_data.get('docstring', ''),
                                'returns': '',
                                'complexity': 1,
                                'file_path': node_data.get('file_path'),
                                'type': node_data.get('type', 'Function'),
                            }
                            
                            # Add source_code if present (for Rust functions)
                            if node_data.get('source_code'):
                                data['source_code'] = node_data['source_code']
                            
                            # Add content_type if present (for text/image/video nodes)
                            if node_data.get('content_type'):
                                data['content_type'] = node_data['content_type']
                                # Also restore text/image/video content
                                if 'text_content' in node_data:
                                    data['text_content'] = node_data['text_content']
                                if 'image_path' in node_data:
                                    data['image_path'] = node_data['image_path']
                                if 'video_path' in node_data:
                                    data['video_path'] = node_data['video_path']
                            
                            # Create FunctionNode
                            node = FunctionNode(data, node_x, node_y)
                            
                            # Restore color and icon if available
                            if node_data.get('color'):
                                node.color = node_data['color']
                            if node_data.get('icon_path'):
                                node.icon_path = node_data['icon_path']
                            
                            # Restore is_add_tool flag if present
                            if node_data.get('is_add_tool'):
                                node.is_add_tool = True
                            
                            # Add to canvas
                            self.nodes.append(node)
                            
                            # Index the node
                            if hasattr(self, '_index_node'):
                                self._index_node(node)
                        except Exception:
                            pass
                    
                    # Apply viewport and other settings
                    # Use whole_file data if available, otherwise use root doc
                    canvas_data = whole_file_data if whole_file_data else doc
                    mgr.apply_to_canvas(self, canvas_data)
                    
                    # Update canvas
                    self.update()
                
                # Show success message
                num_projects = len(projects_data)
                num_nodes = len(nodes_data)
                has_whole_file = whole_file_data is not None
                
                # Show custom success dialog
                try:
                    from Manage2.project_dialogs import LoadSuccessDialog
                    success_dialog = LoadSuccessDialog(
                        num_projects,
                        num_nodes,
                        has_whole_file,
                        self
                    )
                    success_dialog.exec()
                except Exception:
                    QMessageBox.information(self, 'Open Layout', f'Loaded layout from:\n{file_path}')
                
        except Exception as e:
            QMessageBox.critical(self, 'Open Layout Error', str(e))
    elif act == search_act:
        # Ask host to show search UI if available
        try:
            host = self.parent()
            if host and hasattr(host, 'show_search_box'):
                host.show_search_box()
            else:
                QMessageBox.information(self, 'Search', 'Search UI not available.')
        except Exception:
            QMessageBox.information(self, 'Search', 'Search UI not available.')
    elif act == remove_file_act:
        # Clear all Layer menu projects and canvas
        try:
            # Get the host window (manage_native.py)
            host = self.parent()
            
            # Try to get the top toolbar with project state
            top_toolbar = None
            if hasattr(host, 'top_toolbar'):
                top_toolbar = host.top_toolbar
            elif hasattr(host, 'parent') and hasattr(host.parent(), 'top_toolbar'):
                top_toolbar = host.parent().top_toolbar
            
            if top_toolbar and hasattr(top_toolbar, 'project_state'):
                # Confirm with user
                reply = QMessageBox.question(
                    self,
                    "Remove All Projects?",
                    "This will remove all projects from the Layer menu and clear the canvas.\n\n"
                    "Are you sure you want to continue?",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No
                )
                
                if reply == QMessageBox.Yes:
                    project_state = top_toolbar.project_state
                    
                    # Clear all projects
                    project_state.projects = {}
                    project_state.active_project_id = None
                    project_state.next_project_id = 1
                    
                    # Clear canvas
                    self.clear()
                    
                    # Refresh Layer menu
                    top_toolbar.refresh_projects_list()
                    
                    # Show success message
                    QMessageBox.information(
                        self,
                        "Projects Removed",
                        "All projects have been removed from the Layer menu.\n"
                        "The canvas has been cleared.\n\n"
                        "You can now load a different .mndoc file or create new projects."
                    )
            else:
                # Fallback: just clear canvas if no project state found
                self.clear()
                QMessageBox.information(
                    self,
                    "Canvas Cleared",
                    "Canvas has been cleared."
                )
        except Exception as e:
            print(f"Error removing projects: {e}")
            import traceback
            traceback.print_exc()
            # Fallback: just clear canvas
            try:
                self.clear()
            except Exception:
                pass
    elif act == toggle_activity:
        # Decide desired state based on current in host if available
        try:
            host = self.parent()
            enabled = bool(getattr(host, 'activity_enabled', False))
            self.request_toggle_activity.emit(not enabled)
        except Exception:
            self.request_toggle_activity.emit(False)

def _draw_connection(self, painter: QPainter, connection: Connection):
    """Draw a connection between two nodes"""
    from_node = connection.from_node
    to_node = connection.to_node
    
    painter.setOpacity(connection.opacity)

    # Create a gradient for the line
    gradient = QLinearGradient(from_node.x, from_node.y, to_node.x, to_node.y)
    gradient.setColorAt(0, QColor(from_node.color))
    gradient.setColorAt(1, QColor(to_node.color))

    # Create a pen with the gradient brush
    pen = QPen()
    pen.setBrush(QBrush(gradient))
    pen.setWidthF(4 if connection.highlighted else 2)
    pen.setCapStyle(Qt.RoundCap)
    
    painter.setPen(pen)
    
    # Draw the curved line
    start_point = QPointF(from_node.x, from_node.y)
    end_point = QPointF(to_node.x, to_node.y)
    
    dx = end_point.x() - start_point.x()
    dy = end_point.y() - start_point.y()
    distance = math.sqrt(dx * dx + dy * dy)
    # Dynamic curvature based on angle:
    # - Straight (curve=0) when aligned horizontally or vertically
    # - Maximum curve near 45 degrees
    if distance <= 1e-6:
        curve = 0.0
        mid_x = (start_point.x() + end_point.x()) / 2
        mid_y = (start_point.y() + end_point.y()) / 2
        control_point = QPointF(mid_x, mid_y)
    else:
        theta = math.atan2(dy, dx)
        # 0 at 0°/90°, 1 at 45°
        curviness = abs(math.sin(2.0 * theta))
        # Stronger base curve for diagonals
        base_curve = min(distance * 0.45, 160)
        # Shape the curve to be noticeable at diagonals while flat near alignments
        curve = base_curve * (curviness ** 0.6)
        # Snap to straight if extremely close to axis alignment
        if curviness < 0.03:
            curve = 0.0
        mid_x = (start_point.x() + end_point.x()) / 2
        mid_y = (start_point.y() + end_point.y()) / 2
        perp_x = (-dy / distance) * curve
        perp_y = (dx / distance) * curve
        # Choose curve orientation:
        # - Near-horizontal edges: bend up vs down based on dy sign
        # - Near-vertical edges: bend left vs right based on dx sign
        if abs(dx) >= abs(dy):
            sign_dir = 1.0 if dy >= 0 else -1.0
        else:
            sign_dir = 1.0 if dx >= 0 else -1.0
        perp_x *= sign_dir
        perp_y *= sign_dir
        control_point = QPointF(mid_x + perp_x, mid_y + perp_y)
    
    path = QPainterPath()
    path.moveTo(start_point)
    path.quadTo(control_point, end_point)
    
    # Ensure we are only stroking the path, not filling it
    # Skip drawing hidden connections (UI-only removal)
    if getattr(connection, 'hidden', False):
        painter.setOpacity(1.0)
        return
    painter.setBrush(Qt.NoBrush)
    painter.drawPath(path)
    # If either endpoint node is in error, overlay a red stroke to match error styling
    try:
        err_from = bool(getattr(from_node, 'error_state', None) or (isinstance(getattr(from_node, 'data', None), dict) and (from_node.data.get('error_line') or from_node.data.get('error_msg'))))
    except Exception:
        err_from = False
    try:
        err_to = bool(getattr(to_node, 'error_state', None) or (isinstance(getattr(to_node, 'data', None), dict) and (to_node.data.get('error_line') or to_node.data.get('error_msg'))))
    except Exception:
        err_to = False
    if err_from or err_to:
        err_pen = QPen(QColor('#c23a3a'), 4 if connection.highlighted else 3)
        err_pen.setCapStyle(Qt.RoundCap)
        painter.setPen(err_pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawPath(path)

    # Draw flow animation for highlighted connections
    if connection.highlighted:
        self._draw_connection_flow(painter, connection, start_point, control_point, end_point)

    painter.setOpacity(1.0)
    
def _draw_connection_flow(self, painter: QPainter, connection: Connection, 
                        start: QPointF, control: QPointF, end: QPointF):
    """Draw animated flow on highlighted connections"""
    progress = (math.sin(connection.flow_offset) + 1) / 2
    
    # Apply an easing function for smoother animation
    eased_progress = progress * progress * (3 - 2 * progress)
    
    # Calculate point on curve
    t = eased_progress
    x = (1 - t) * (1 - t) * start.x() + 2 * (1 - t) * t * control.x() + t * t * end.x()
    y = (1 - t) * (1 - t) * start.y() + 2 * (1 - t) * t * control.y() + t * t * end.y()
    
    # Draw flowing circle with gradient
    flow_radius = 7
    
    # Gradient for the circle
    from_color = QColor(connection.from_node.color)
    to_color = QColor(connection.to_node.color)
    
    # Interpolate color based on progress
    r = int(from_color.red() + (to_color.red() - from_color.red()) * t)
    g = int(from_color.green() + (to_color.green() - from_color.green()) * t)
    b = int(from_color.blue() + (to_color.blue() - from_color.blue()) * t)
    current_color = QColor(r, g, b)
    
    gradient = QRadialGradient(QPointF(x, y), flow_radius)
    gradient.setColorAt(0, current_color.lighter(150))
    gradient.setColorAt(1, current_color)
    
    painter.setBrush(QBrush(gradient))
    painter.setPen(Qt.NoPen)  # No border for a smoother look
    painter.drawEllipse(QPointF(x, y), flow_radius, flow_radius)









def _resolve_main_file_path(self) -> Optional[str]:
    try:
        if not getattr(self, 'main_script_name', None):
            return None
        import os as _os
        name = self.main_script_name
        # If it contains path separators, try absolute
        if _os.path.isabs(name) and _os.path.exists(name):
            return _os.path.abspath(name)
        # Check current analyzed file directory
        cur = getattr(self, 'current_file_path', None)
        if cur:
            d = _os.path.dirname(cur)
            cand = _os.path.join(d, name)
            if _os.path.exists(cand):
                return _os.path.abspath(cand)
        # Check project root (parent of Manage)
        root = _os.path.abspath(_os.path.join(_os.path.dirname(__file__), '..'))
        cand = _os.path.join(root, name)
        if _os.path.exists(cand):
            return _os.path.abspath(cand)
        return None
    except Exception:
        return None

def mark_error_for_file(self, file_path: str, func: str, line: int, msg: str):
    """Record an error for the given file and mark the appropriate node in the canvas.
    - If file matches current analyzed file: mark the function node.
    - Else: create/find an external module node for that file and mark it.
    """
    try:
        import os as _os
        abs_path = _os.path.abspath(file_path) if file_path else ''
        if not hasattr(self, '_file_errors') or not isinstance(self._file_errors, dict):
            self._file_errors = {}
        self._file_errors[abs_path] = {'func': func or '', 'line': int(line or 0), 'msg': msg or ''}

        # If error is in current analyzed file, tag the function node
        cur = getattr(self, 'current_file_path', None)
        if cur and abs_path and _os.path.abspath(cur) == abs_path:
            fname = (func or '').lower()
            node = None
            try:
                node = getattr(self, '_node_by_name', {}).get(fname)
            except Exception:
                node = None
            if node:
                try:
                    setattr(node, 'error_state', {'line': int(line or 0), 'msg': msg or ''})
                    if isinstance(node.data, dict):
                        node.data['error_line'] = int(line or 0)
                        node.data['error_msg'] = msg or ''
                except Exception:
                    pass
        else:
            # Aggregate under external module node
            try:
                node = self._get_or_create_module_node(abs_path)
                setattr(node, 'error_state', {'line': int(line or 0), 'msg': msg or ''})
                if isinstance(node.data, dict):
                    node.data['file_path'] = abs_path
                    node.data['error_line'] = int(line or 0)
                    node.data['error_msg'] = msg or ''
            except Exception:
                pass
        # Optionally enable focus mode to emphasize active/error nodes
        try:
            self.runtime_focus_mode = True
        except Exception:
            pass
        self.update()
    except Exception:
        pass

def clear_error_for_file(self, file_path: str):
    """Clear any error marker for the given file from the canvas and nodes.
    This resets red backgrounds/borders back to normal after a successful run.
    """
    try:
        import os as _os
        abs_path = _os.path.abspath(file_path) if file_path else ''
        # Drop from error registry
        try:
            if abs_path and hasattr(self, '_file_errors') and isinstance(self._file_errors, dict):
                self._file_errors.pop(abs_path, None)
        except Exception:
            pass
        # Clear on existing nodes (module-aggregated and per-function)
        for n in list(getattr(self, 'nodes', []) or []):
            try:
                d = getattr(n, 'data', {}) or {}
                node_fp = d.get('file_path') or ''
                same_file = bool(abs_path and node_fp and _os.path.abspath(node_fp) == abs_path)
                # Function nodes of the currently analyzed file may not carry file_path; clear by current_file_path
                if not same_file and abs_path and _os.path.abspath(getattr(self, 'current_file_path', '') or '') == abs_path:
                    same_file = True
                if same_file:
                    if hasattr(n, 'error_state'):
                        try:
                            delattr(n, 'error_state')
                        except Exception:
                            try:
                                setattr(n, 'error_state', None)
                            except Exception:
                                pass
                    if isinstance(d, dict):
                        d.pop('error_line', None)
                        d.pop('error_msg', None)
            except Exception:
                pass
        self.update()
    except Exception:
        pass

def _draw_flowing_background(self, painter: QPainter):
    """Draw the flowing ribbon background matching the original design"""
    rect = self.rect()
    # Base background
    painter.fillRect(rect, QColor(DARK_THEME['bg_primary']))
    # Flowing ribbon from right (main flow)
    ribbon_gradient = QLinearGradient(rect.width() * 0.4, 0, rect.width(), rect.height())
    ribbon_gradient.setColorAt(0, QColor(0, 0, 0, 0))
    ribbon_gradient.setColorAt(0.6, QColor(0, 0, 0, 0))
    ribbon_gradient.setColorAt(0.65, QColor(40, 40, 40, 102))
    ribbon_gradient.setColorAt(0.8, QColor(55, 55, 55, 76))
    ribbon_gradient.setColorAt(0.9, QColor(53, 53, 53, 51))
    ribbon_gradient.setColorAt(1.0, QColor(180, 180, 180, 25))
    painter.fillRect(rect, QBrush(ribbon_gradient))
    # Secondary flowing layer
    secondary_gradient = QLinearGradient(rect.width() * 0.3, 0, rect.width(), rect.height())
    secondary_gradient.setColorAt(0, QColor(0, 0, 0, 0))
    secondary_gradient.setColorAt(0.7, QColor(0, 0, 0, 0))
    secondary_gradient.setColorAt(0.8, QColor(50, 50, 50, 76))
    secondary_gradient.setColorAt(0.95, QColor(100, 100, 100, 51))
    secondary_gradient.setColorAt(1.0, QColor(0, 0, 0, 0))
    painter.fillRect(rect, QBrush(secondary_gradient))
    # Subtle horizontal texture
    for y in range(0, rect.height(), 2):
        if y % 2 == 0:
            painter.setPen(QPen(QColor(255, 255, 255, 2)))
            painter.drawLine(0, y, rect.width(), y)
    
def _draw_background_dots(self, painter: QPainter):
    """Draw dot grid background in world coordinates (n8n/Zapier style)."""
    try:
        # Compute visible world bounds given current camera
        zoom = max(self.camera_zoom, 1e-6)
        world_left = -self.camera_x / zoom
        world_top = -self.camera_y / zoom
        world_w = self.width() / zoom
        world_h = self.height() / zoom

        # Dot styling
        spacing = 28.0  # distance between dots in world units
        radius = 1.8
        dot_color = QColor(255, 255, 255, 15)  # subtle but visible on dark bg

        # Align start to grid to keep dots stable while panning
        start_x = math.floor(world_left / spacing) * spacing
        start_y = math.floor(world_top / spacing) * spacing
        end_x = world_left + world_w + spacing
        end_y = world_top + world_h + spacing

        painter.save()
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(dot_color))

        x = start_x
        while x <= end_x:
            y = start_y
            while y <= end_y:
                painter.drawEllipse(QPointF(x, y), radius, radius)
                y += spacing
            x += spacing
        painter.restore()
    except Exception:
        pass
