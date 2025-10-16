"""
Project Management Dialogs
Handles file selection and function selection for creating projects
Uses the same design as Details/dialogs.py
"""

import os
from PySide6.QtCore import Qt, Signal, QSize, QPoint, QRect
from PySide6.QtGui import QIcon, QPixmap, QPainter, QPen, QFont, QColor, QBrush
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTreeWidget, QTreeWidgetItem, QFileSystemModel, QTreeView,
    QWidget, QFrame
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


class FileSelectionDialog(QDialog):
    """Dialog for selecting Rust files to add to project"""
    
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
        subtitle = QLabel("Choose one or more .rs files to include in your project")
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


class UnsavedChangesDialog(QDialog):
    """Custom dialog for unsaved changes confirmation"""
    
    def __init__(self, project_name, parent=None):
        super().__init__(parent)
        self.project_name = project_name
        self.result_action = None  # 'save', 'discard', or 'cancel'
        self.setup_ui()
    
    def setup_ui(self):
        """Setup the unsaved changes dialog UI"""
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setStyleSheet("background-color: transparent;")
        self.resize(500, 250)
        
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
        self.title_bar = CustomTitleBarDialog("Unsaved Changes", self)
        container_layout.addWidget(self.title_bar)

        # Content
        content_layout = QVBoxLayout()
        content_layout.setContentsMargins(30, 10, 30, 20)
        content_layout.setSpacing(15)
        container_layout.addLayout(content_layout)
        
        # Warning icon and message
        message_layout = QHBoxLayout()
        message_layout.setSpacing(15)
        
        # Warning icon
        icon_label = QLabel()
        try:
            warning_icon = QIcon("img/Warning.png")
            icon_label.setPixmap(warning_icon.pixmap(100, 100))
        except Exception:
            icon_label.setText("⚠")
            icon_label.setStyleSheet("font-size: 48px; color: #FFA500;")
        message_layout.addWidget(icon_label)
        
        # Message text
        text_layout = QVBoxLayout()
        text_layout.setSpacing(0)
        
        title_label = QLabel(f"Do you want to save '{self.project_name}'?")
        title_label.setStyleSheet("color: #E0E2E6; font-size: 14px; font-weight: bold; background: transparent; border: none;")
        text_layout.addWidget(title_label)
        
        subtitle_label = QLabel("Your changes will be lost if you don't save them.")
        subtitle_label.setStyleSheet("color: #9AA0A6; font-size: 12px; background: transparent; border: none;")
        subtitle_label.setWordWrap(True)
        text_layout.addWidget(subtitle_label)
        
        message_layout.addLayout(text_layout, 1)
        content_layout.addLayout(message_layout)
        
        content_layout.addStretch()
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)
        button_layout.addStretch()
        
        # Don't Save button
        discard_btn = QPushButton("Don't Save")
        discard_btn.setStyleSheet("""
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
        discard_btn.clicked.connect(self.on_discard)
        button_layout.addWidget(discard_btn)
        
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
        cancel_btn.clicked.connect(self.on_cancel)
        button_layout.addWidget(cancel_btn)
        
        # Save button (highlighted)
        save_btn = QPushButton("Save")
        save_btn.setStyleSheet("""
            QPushButton {
                background-color: #60A5FA;
                color: #FFFFFF;
                border: 1px solid #60A5FA;
                border-radius: 4px;
                padding: 8px 20px;
                min-width: 80px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #4A8FE7;
            }
            QPushButton:pressed {
                background-color: #3A7FD7;
            }
        """)
        save_btn.clicked.connect(self.on_save)
        button_layout.addWidget(save_btn)
        
        content_layout.addLayout(button_layout)
    
    def on_save(self):
        """User chose to save"""
        self.result_action = 'save'
        self.accept()
    
    def on_discard(self):
        """User chose to discard changes"""
        self.result_action = 'discard'
        self.accept()
    
    def on_cancel(self):
        """User chose to cancel"""
        self.result_action = 'cancel'
        self.reject()


class RenameProjectDialog(QDialog):
    """Custom dialog for renaming a project"""
    
    def __init__(self, current_name, parent=None):
        super().__init__(parent)
        self.current_name = current_name
        self.new_name = None
        self.setup_ui()
    
    def setup_ui(self):
        """Setup the rename dialog UI"""
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setStyleSheet("background-color: transparent;")
        self.resize(450, 200)
        
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
        self.title_bar = CustomTitleBarDialog("Rename Project", self)
        container_layout.addWidget(self.title_bar)

        # Content
        content_layout = QVBoxLayout()
        content_layout.setContentsMargins(30, 20, 30, 20)
        content_layout.setSpacing(15)
        container_layout.addLayout(content_layout)
        
        # Message
        message_label = QLabel("Enter a new name for the project:")
        message_label.setStyleSheet("color: #E0E2E6; font-size: 13px; background: transparent; border: none;")
        content_layout.addWidget(message_label)
        
        # Input field
        from PySide6.QtWidgets import QLineEdit
        self.name_input = QLineEdit()
        self.name_input.setText(self.current_name)
        self.name_input.selectAll()
        self.name_input.setStyleSheet("""
            QLineEdit {
                background-color: #1E1F22;
                color: #E0E2E6;
                border: 1px solid #4A4D51;
                border-radius: 4px;
                padding: 8px 12px;
                font-size: 13px;
            }
            QLineEdit:focus {
                border: 1px solid #60A5FA;
            }
        """)
        self.name_input.returnPressed.connect(self.on_ok)
        content_layout.addWidget(self.name_input)
        
        content_layout.addStretch()
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)
        button_layout.addStretch()
        
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
        
        # OK button (highlighted)
        ok_btn = QPushButton("Rename")
        ok_btn.setStyleSheet("""
            QPushButton {
                background-color: #60A5FA;
                color: #FFFFFF;
                border: 1px solid #60A5FA;
                border-radius: 4px;
                padding: 8px 20px;
                min-width: 80px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #4A8FE7;
            }
            QPushButton:pressed {
                background-color: #3A7FD7;
            }
        """)
        ok_btn.clicked.connect(self.on_ok)
        button_layout.addWidget(ok_btn)
        
        content_layout.addLayout(button_layout)
        
        # Focus on input
        self.name_input.setFocus()
    
    def on_ok(self):
        """User confirmed rename"""
        new_name = self.name_input.text().strip()
        if new_name and new_name != self.current_name:
            self.new_name = new_name
            self.accept()
        elif not new_name:
            # Show error if empty
            self.name_input.setStyleSheet("""
                QLineEdit {
                    background-color: #1E1F22;
                    color: #E0E2E6;
                    border: 2px solid #E81123;
                    border-radius: 4px;
                    padding: 8px 12px;
                    font-size: 13px;
                }
            """)
        else:
            # Same name, just close
            self.reject()


class DeleteProjectDialog(QDialog):
    """Custom dialog for deleting a project"""
    
    def __init__(self, project_name, parent=None):
        super().__init__(parent)
        self.project_name = project_name
        self.confirmed = False
        self.setup_ui()
    
    def setup_ui(self):
        """Setup the delete dialog UI"""
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setStyleSheet("background-color: transparent;")
        self.resize(500, 250)
        
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
        self.title_bar = CustomTitleBarDialog("Delete Project", self)
        container_layout.addWidget(self.title_bar)

        # Content
        content_layout = QVBoxLayout()
        content_layout.setContentsMargins(30, 10, 30, 20)
        content_layout.setSpacing(15)
        container_layout.addLayout(content_layout)
        
        # Warning icon and message
        message_layout = QHBoxLayout()
        message_layout.setSpacing(15)
        
        # Warning icon
        icon_label = QLabel()
        try:
            warning_icon = QIcon("img/Warning.png")
            icon_label.setPixmap(warning_icon.pixmap(100, 100))
        except Exception:
            icon_label.setText("⚠")
            icon_label.setStyleSheet("font-size: 48px; color: #E81123;")
        message_layout.addWidget(icon_label)
        
        # Message text
        text_layout = QVBoxLayout()
        text_layout.setSpacing(0)
        
        title_label = QLabel(f"Delete '{self.project_name}'?")
        title_label.setStyleSheet("color: #E0E2E6; font-size: 14px; font-weight: bold; background: transparent; border: none;")
        text_layout.addWidget(title_label)
        
        subtitle_label = QLabel("This action cannot be undone. The project will be permanently deleted.")
        subtitle_label.setStyleSheet("color: #9AA0A6; font-size: 12px; background: transparent; border: none;")
        subtitle_label.setWordWrap(True)
        text_layout.addWidget(subtitle_label)
        
        message_layout.addLayout(text_layout, 1)
        content_layout.addLayout(message_layout)
        
        content_layout.addStretch()
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)
        button_layout.addStretch()
        
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
        
        # Delete button (danger style)
        delete_btn = QPushButton("Delete")
        delete_btn.setStyleSheet("""
            QPushButton {
                background-color: #E81123;
                color: #FFFFFF;
                border: 1px solid #E81123;
                border-radius: 4px;
                padding: 8px 20px;
                min-width: 80px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #D00010;
            }
            QPushButton:pressed {
                background-color: #C00000;
            }
        """)
        delete_btn.clicked.connect(self.on_delete)
        button_layout.addWidget(delete_btn)
        
        content_layout.addLayout(button_layout)
    
    def on_delete(self):
        """User confirmed deletion"""
        self.confirmed = True
        self.accept()


class FunctionSelectionDialog(QDialog):
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
        subtitle = QLabel("Choose a function or class to add to your project canvas")
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
        """Load functions and classes from selected Rust files, filtering out already-added nodes"""
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


class SaveSuccessDialog(QDialog):
    """Custom dialog for successful save confirmation"""
    
    def __init__(self, file_path, num_projects, has_whole_file=False, parent=None):
        super().__init__(parent)
        self.file_path = file_path
        self.num_projects = num_projects
        self.has_whole_file = has_whole_file
        self.setup_ui()
    
    def setup_ui(self):
        """Setup the save success dialog UI"""
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setStyleSheet("background-color: transparent;")
        self.resize(550, 280)
        
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
        self.title_bar = CustomTitleBarDialog("Save A3 Project", self)
        container_layout.addWidget(self.title_bar)

        # Content
        content_layout = QVBoxLayout()
        content_layout.setContentsMargins(30, 20, 30, 20)
        content_layout.setSpacing(15)
        container_layout.addLayout(content_layout)
        
        # Success icon and message
        message_layout = QHBoxLayout()
        message_layout.setSpacing(15)
        
        # Success icon (checkmark)
        icon_label = QLabel()
        icon_label.setText("✓")
        icon_label.setStyleSheet("font-size: 64px; color: #4CAF50; font-weight: bold;")
        icon_label.setAlignment(Qt.AlignCenter)
        icon_label.setFixedSize(80, 80)
        message_layout.addWidget(icon_label)
        
        # Message text
        text_layout = QVBoxLayout()
        text_layout.setSpacing(8)
        
        title_label = QLabel("Project saved successfully!")
        title_label.setStyleSheet("color: #E0E2E6; font-size: 16px; font-weight: bold; background: transparent; border: none;")
        text_layout.addWidget(title_label)
        
        # File path
        path_label = QLabel(f"<b>Location:</b> {os.path.basename(self.file_path)}")
        path_label.setStyleSheet("color: #9AA0A6; font-size: 12px; background: transparent; border: none;")
        path_label.setWordWrap(True)
        text_layout.addWidget(path_label)
        
        # Details
        details_text = f"• {self.num_projects} Layer menu project{'s' if self.num_projects != 1 else ''}"
        if self.has_whole_file:
            details_text += "\n• Whole File view saved"
        
        details_label = QLabel(details_text)
        details_label.setStyleSheet("color: #9AA0A6; font-size: 12px; background: transparent; border: none;")
        text_layout.addWidget(details_label)
        
        message_layout.addLayout(text_layout, 1)
        content_layout.addLayout(message_layout)
        
        content_layout.addStretch()
        
        # OK button
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        ok_btn = QPushButton("OK")
        ok_btn.setStyleSheet("""
            QPushButton {
                background-color: #60A5FA;
                color: #FFFFFF;
                border: 1px solid #60A5FA;
                border-radius: 4px;
                padding: 10px 30px;
                min-width: 100px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #4A8FE7;
            }
            QPushButton:pressed {
                background-color: #3A7FD7;
            }
        """)
        ok_btn.clicked.connect(self.accept)
        button_layout.addWidget(ok_btn)
        
        button_layout.addStretch()
        content_layout.addLayout(button_layout)


class LoadSuccessDialog(QDialog):
    """Custom dialog for successful load confirmation"""
    
    def __init__(self, num_projects, num_nodes, has_whole_file=False, parent=None):
        super().__init__(parent)
        self.num_projects = num_projects
        self.num_nodes = num_nodes
        self.has_whole_file = has_whole_file
        self.setup_ui()
    
    def setup_ui(self):
        """Setup the load success dialog UI"""
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setStyleSheet("background-color: transparent;")
        self.resize(550, 280)
        
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
        self.title_bar = CustomTitleBarDialog("Load A3 Project", self)
        container_layout.addWidget(self.title_bar)

        # Content
        content_layout = QVBoxLayout()
        content_layout.setContentsMargins(30, 20, 30, 20)
        content_layout.setSpacing(15)
        container_layout.addLayout(content_layout)
        
        # Success icon and message
        message_layout = QHBoxLayout()
        message_layout.setSpacing(15)
        
        # Success icon (checkmark)
        icon_label = QLabel()
        icon_label.setText("✓")
        icon_label.setStyleSheet("font-size: 64px; color: #4CAF50; font-weight: bold;")
        icon_label.setAlignment(Qt.AlignCenter)
        icon_label.setFixedSize(80, 80)
        message_layout.addWidget(icon_label)
        
        # Message text
        text_layout = QVBoxLayout()
        text_layout.setSpacing(8)
        
        title_label = QLabel("Successfully loaded!")
        title_label.setStyleSheet("color: #E0E2E6; font-size: 16px; font-weight: bold; background: transparent; border: none;")
        text_layout.addWidget(title_label)
        
        # Build details text
        details_parts = []
        if self.has_whole_file:
            details_parts.append(f"• Whole File view ({self.num_nodes} node{'s' if self.num_nodes != 1 else ''})")
        elif self.num_nodes > 0:
            details_parts.append(f"• {self.num_nodes} node{'s' if self.num_nodes != 1 else ''} on canvas")
        else:
            details_parts.append("• Empty canvas (use Layer menu to switch projects)")
        
        details_parts.append(f"• {self.num_projects} Layer menu project{'s' if self.num_projects != 1 else ''}")
        
        details_label = QLabel("\n".join(details_parts))
        details_label.setStyleSheet("color: #9AA0A6; font-size: 12px; background: transparent; border: none;")
        text_layout.addWidget(details_label)
        
        message_layout.addLayout(text_layout, 1)
        content_layout.addLayout(message_layout)
        
        content_layout.addStretch()
        
        # OK button
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        ok_btn = QPushButton("OK")
        ok_btn.setStyleSheet("""
            QPushButton {
                background-color: #60A5FA;
                color: #FFFFFF;
                border: 1px solid #60A5FA;
                border-radius: 4px;
                padding: 10px 30px;
                min-width: 100px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #4A8FE7;
            }
            QPushButton:pressed {
                background-color: #3A7FD7;
            }
        """)
        ok_btn.clicked.connect(self.accept)
        button_layout.addWidget(ok_btn)
        
        button_layout.addStretch()
        content_layout.addLayout(button_layout)
