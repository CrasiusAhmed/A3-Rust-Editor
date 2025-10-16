import os
from PySide6.QtCore import (
    Qt, QDir, QFileInfo, QUrl, QRegularExpression, QCoreApplication, QRect, QSize, QProcess, Slot, QTimer, QRunnable, QThreadPool, QObject, Signal, QPropertyAnimation, QEasingCurve
)
from PySide6.QtGui import (
    QFont, QSyntaxHighlighter, QTextCharFormat, QColor, QPalette, QPainter, QTextFormat, 
    QTextCursor, QIcon, QPixmap, QPen
)
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QSplitter, QTreeView, QTextEdit,
    QVBoxLayout, QWidget, QFileDialog, QTabWidget, QPlainTextEdit,
    QMessageBox, QFileSystemModel, QMenuBar, QHeaderView,
    QHBoxLayout, QPushButton, QCompleter,
    QDialog, QDialogButtonBox, QFontComboBox, QSpinBox, QFormLayout,
    QMenu, QInputDialog, QLineEdit,
    QStackedWidget, QLabel, QTabBar, QStyledItemDelegate, QStyle,
    QStyleOptionViewItem, QGraphicsOpacityEffect
)

class CustomFileSystemModel(QFileSystemModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.python_icon = QIcon("img/python.png")
        self.json_icon = self.create_json_icon()
        # Custom icons for Rust ecosystem files
        self.cargo_toml_icon = QIcon("img/Setting.png")  # Use provided Setting icon for Cargo.toml
        self.rust_main_icon = self.create_rust_icon()     # Custom drawn Rust "R" icon for main.rs
        self.lock_icon = self.create_lock_icon()          # Simple padlock icon for Cargo.lock

    def hasChildren(self, index):
        # This ensures that an arrow is shown for all directories, even empty ones.
        if self.isDir(index):
            return True
        return super().hasChildren(index)

    def data(self, index, role):
        if role == Qt.DecorationRole and index.column() == 0:
            file_info = self.fileInfo(index)
            if file_info.isFile():
                name_lower = file_info.fileName().lower()
                suffix_lower = file_info.suffix().lower()
                # Specific file name matches first
                if name_lower == "cargo.toml":
                    return self.cargo_toml_icon
                if name_lower == "cargo.lock":
                    return self.lock_icon
                # All .rs files get the Rust icon
                if suffix_lower == "rs":
                    return self.rust_main_icon
                # Other file types
                if suffix_lower == "py":
                    return self.python_icon
                elif suffix_lower == "json":
                    return self.json_icon
        return super().data(index, role)

    def create_json_icon(self):
        pixmap = QPixmap(24, 24)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QPen(QColor("#FFF172"), 2))
        font = QFont()
        font.setPointSize(16)
        painter.setFont(font)
        painter.drawText(QRect(0, 0, 24, 24), Qt.AlignCenter, "{ }")
        painter.end()
        return QIcon(pixmap)

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

    def create_lock_icon(self):
        """Create a simple padlock icon for lock files like Cargo.lock."""
        pixmap = QPixmap(24, 24)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        # Shackle
        painter.setPen(QPen(QColor("#9AA0A6"), 2))
        painter.setBrush(Qt.NoBrush)
        painter.drawArc(QRect(7, 5, 10, 8), 0, 180 * 16)
        # Body
        painter.setPen(QPen(QColor("#9AA0A6"), 1))
        painter.setBrush(QColor("#F1C40F"))  # golden lock body
        painter.drawRoundedRect(6, 10, 12, 10, 3, 3)
        # Keyhole
        painter.setPen(QPen(QColor("#5D4037"), 2))
        painter.drawPoint(12, 15)
        painter.end()
        return QIcon(pixmap)

from PySide6.QtCore import QSortFilterProxyModel

class KeyboardDisplayWidget(QWidget):
    """
    A widget that displays keyboard keys being pressed at the bottom center of the screen.
    Similar to JetBrains PyCharm's keyboard display feature.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.ToolTip | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        
        # Store currently pressed keys
        self.pressed_keys = []
        self.key_timers = {}  # key -> QTimer for auto-hide
        
        # Setup UI
        layout = QHBoxLayout(self)
        layout.setContentsMargins(15, 10, 15, 10)
        layout.setSpacing(8)
        
        self.key_label = QLabel("")
        self.key_label.setAlignment(Qt.AlignCenter)
        self.key_label.setStyleSheet("""
            QLabel {
                background-color: rgba(45, 45, 45, 230);
                color: #E8EAED;
                border: 1px solid rgba(80, 80, 80, 200);
                border-radius: 6px;
                padding: 8px 16px;
                font-size: 14px;
                font-weight: bold;
                font-family: 'Segoe UI', Arial, sans-serif;
            }
        """)
        layout.addWidget(self.key_label)
        
        self.setLayout(layout)
        self.hide()
        
        # Fade animation
        self.opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.opacity_effect)
        self.fade_animation = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.fade_animation.setDuration(200)
        self.fade_animation.setEasingCurve(QEasingCurve.InOutQuad)
    
    def show_key(self, key_text):
        """Display a key press"""
        if not key_text:
            return
        
        # Check if this exact key is already being displayed
        if key_text in self.pressed_keys:
            # Just refresh the timer for this key
            if key_text in self.key_timers:
                self.key_timers[key_text].stop()
                self.key_timers[key_text].deleteLater()
            
            timer = QTimer(self)
            timer.setSingleShot(True)
            timer.timeout.connect(lambda: self.release_key(key_text))
            timer.start(1000)
            self.key_timers[key_text] = timer
            return
        
        # Check if this is a combination key (contains " + ")
        is_combination = " + " in key_text
        
        if is_combination:
            # For combinations like "Ctrl + Z" or "Ctrl + Shift + Z"
            # Remove any existing keys that are subsets of this combination
            parts = set(p.strip() for p in key_text.split(" + "))
            
            # Remove any pressed keys that are subsets of the new combination
            keys_to_remove = []
            for existing_key in self.pressed_keys:
                if existing_key != key_text:  # Don't remove the key we're about to add
                    existing_parts = set(p.strip() for p in existing_key.split(" + "))
                    # If all parts of existing key are in the new key, it's a subset
                    if existing_parts.issubset(parts):
                        keys_to_remove.append(existing_key)
            
            # Remove the subset keys
            for key_to_remove in keys_to_remove:
                if key_to_remove in self.pressed_keys:
                    self.pressed_keys.remove(key_to_remove)
                if key_to_remove in self.key_timers:
                    self.key_timers[key_to_remove].stop()
                    self.key_timers[key_to_remove].deleteLater()
                    del self.key_timers[key_to_remove]
        
        # Add to pressed keys if not already there
        if key_text not in self.pressed_keys:
            self.pressed_keys.append(key_text)
        
        # Update display
        self._update_display()
        
        # Cancel existing timer for this key
        if key_text in self.key_timers:
            self.key_timers[key_text].stop()
            self.key_timers[key_text].deleteLater()
        
        # Create auto-hide timer for this key (500ms = 0.5 seconds)
        timer = QTimer(self)
        timer.setSingleShot(True)
        timer.timeout.connect(lambda: self.release_key(key_text))
        timer.start(500)  # 500ms = 0.5 seconds
        self.key_timers[key_text] = timer
    
    def release_key(self, key_text):
        """Remove a key from display (called by timer, not by key release event)"""
        if key_text in self.pressed_keys:
            self.pressed_keys.remove(key_text)
        
        if key_text in self.key_timers:
            self.key_timers[key_text].deleteLater()
            del self.key_timers[key_text]
        
        self._update_display()
    
    def _update_display(self):
        """Update the displayed keys"""
        if not self.pressed_keys:
            # Fade out and hide
            self.fade_animation.setStartValue(1.0)
            self.fade_animation.setEndValue(0.0)
            self.fade_animation.finished.connect(self.hide)
            self.fade_animation.start()
        else:
            # Show with fade in
            if not self.isVisible():
                self.opacity_effect.setOpacity(0.0)
                self.show()
                self.fade_animation.setStartValue(0.0)
                self.fade_animation.setEndValue(1.0)
                try:
                    self.fade_animation.finished.disconnect()
                except:
                    pass
                self.fade_animation.start()
            
            # Update text
            display_text = " + ".join(self.pressed_keys)
            self.key_label.setText(display_text)
            
            # Adjust size to fit content
            self.adjustSize()
            
            # Position at bottom center of parent
            self._position_at_bottom_center()
    
    def _position_at_bottom_center(self):
        """Position the widget at the bottom center of the parent window"""
        if not self.parent():
            return
        
        parent_rect = self.parent().rect()
        widget_width = self.width()
        widget_height = self.height()
        
        # Position at bottom center with some margin
        x = (parent_rect.width() - widget_width) // 2
        y = parent_rect.height() - widget_height - 50  # 50px from bottom
        
        self.move(x, y)

class FileSorterProxyModel(QSortFilterProxyModel):
    """
    A proxy model to sort files and directories correctly, ensuring
    directories are always listed before files.
    """
    def lessThan(self, left, right):
        """ Custom comparison logic for sorting. """
        source_model = self.sourceModel()
        left_info = source_model.fileInfo(left)
        right_info = source_model.fileInfo(right)

        # Check if items are directories
        left_is_dir = left_info.isDir()
        right_is_dir = right_info.isDir()

        # Directory vs. file
        if left_is_dir and not right_is_dir:
            return True
        if not left_is_dir and right_is_dir:
            return False

        # If both are the same type, sort by name (case-insensitive)
        return left_info.fileName().lower() < right_info.fileName().lower()

class FileTreeDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        super().__init__(parent)
        
    def paint(self, painter, option, index):
        # Resolve models directly from the view to ensure mapping matches
        view = self.parent()
        model = view.model()
        if not isinstance(model, QSortFilterProxyModel) or not hasattr(model, "sourceModel"):
            # Fallback to default painting if model is unexpected
            super().paint(painter, option, index)
            return
        proxy_model = model
        source_model = proxy_model.sourceModel()

        # Save original colors
        original_bg = option.palette.color(QPalette.Base)
        original_text = option.palette.color(QPalette.Text)

        # Create a copy of the style option
        new_option = QStyleOptionViewItem(option)

        # First draw the red highlight if needed
        row_source_index = proxy_model.mapToSource(index.sibling(index.row(), 0))
        row_file_path = os.path.normpath(source_model.filePath(row_source_index))
        main_window = view.window()

        if hasattr(main_window, 'highlighted_file') and main_window.highlighted_file:
            highlighted_path = os.path.normpath(main_window.highlighted_file)
            if row_file_path.lower() == highlighted_path.lower():
                row_rect = QRect(0, option.rect.top(), view.viewport().width(), option.rect.height())
                if not (option.state & QStyle.State_Selected):
                    painter.save()
                    highlight_color = QColor(255, 0, 0, 40)
                    painter.fillRect(row_rect, highlight_color)
                    painter.restore()

        # Force text color to be bright
        if not (option.state & QStyle.State_Selected):
            new_option.palette.setColor(QPalette.Text, QColor("#E8EAED"))
            new_option.palette.setColor(QPalette.HighlightedText, QColor("#E8EAED"))

        # Draw item with bright text
        super().paint(painter, new_option, index)

        # Draw selection indicator
        if index.column() == 0 and (option.state & QStyle.State_Selected):
            painter.fillRect(
                QRect(option.rect.left(), option.rect.top(), 2, option.rect.height()),
                QColor("#007ACC")
            )


def apply_modern_scrollbar_style():
    """
    Apply modern scrollbar styling similar to coding_phcjp.py
    """
    return """
        /* Modern Animated Scrollbar Styling */
        QScrollBar:vertical {
            background: #2B2B2B;
            width: 12px;
            border: none;
            border-radius: 6px;
            margin: 0px;
        }
        
        QScrollBar::handle:vertical {
            background: rgba(85, 85, 85, 0.6);
            border-radius: 6px;
            min-height: 20px;
            margin: 2px;
        }
        
        QScrollBar::handle:vertical:hover {
            background: rgba(102, 102, 102, 0.9);
        }
        
        QScrollBar::handle:vertical:pressed {
            background: rgba(119, 119, 119, 1.0);
        }
        
        QScrollBar::add-line:vertical,
        QScrollBar::sub-line:vertical {
            height: 0px;
            background: none;
        }
        
        QScrollBar::add-page:vertical,
        QScrollBar::sub-page:vertical {
            background: none;
        }
        
        QScrollBar:horizontal {
            background: #2B2B2B;
            height: 12px;
            border: none;
            border-radius: 6px;
            margin: 0px;
        }
        
        QScrollBar::handle:horizontal {
            background: rgba(85, 85, 85, 0.6);
            border-radius: 6px;
            min-width: 20px;
            margin: 2px;
        }
        
        QScrollBar::handle:horizontal:hover {
            background: rgba(102, 102, 102, 0.9);
        }
        
        QScrollBar::handle:horizontal:pressed {
            background: rgba(119, 119, 119, 1.0);
        }
        
        QScrollBar::add-line:horizontal,
        QScrollBar::sub-line:horizontal {
            width: 0px;
            background: none;
        }
        
        QScrollBar::add-page:horizontal,
        QScrollBar::sub-page:horizontal {
            background: none;
        }
        
        /* Enhanced hover effects with opacity animation */
        QScrollBar:vertical:hover {
            background: #333333;
        }
        
        QScrollBar:horizontal:hover {
            background: #333333;
        }
    """
