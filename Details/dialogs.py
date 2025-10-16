from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
    QPushButton, QWidget, QApplication, QMessageBox, QTableWidget, QHeaderView, QTableWidgetItem, QSlider
)
from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QPainter, QColor, QPixmap

class CustomTitleBarDialog(QWidget):
    def __init__(self, title, parent):
        super().__init__(parent)
        self.parent_dialog = parent
        self.setFixedHeight(35)
        self.m_old_pos = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 0, 5, 0)
        layout.setSpacing(10)

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

class CustomInputDialog(QDialog):
    def __init__(self, title, label, text="", parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setStyleSheet("background-color: transparent;")

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)

        self.container = QWidget()
        self.container.setStyleSheet("""
            QWidget {
                background-color: #282A2E;
                border: 1px solid #4A4D51;
                border-radius: 8px;
            }
        """)
        self.main_layout.addWidget(self.container)
        
        container_layout = QVBoxLayout(self.container)
        container_layout.setContentsMargins(1, 1, 1, 1)
        container_layout.setSpacing(0)

        # Custom Title Bar
        self.title_bar = CustomTitleBarDialog(title, self)
        container_layout.addWidget(self.title_bar)

        # Content
        content_layout = QVBoxLayout()
        content_layout.setContentsMargins(20, 10, 20, 20)
        content_layout.setSpacing(10)
        container_layout.addLayout(content_layout)

        # Simple label and input (no Ollama image)
        self.label = QLabel(label, self)
        self.label.setStyleSheet("color: #E0E2E6; font-size: 14px; border: none;")
        content_layout.addWidget(self.label)

        self.line_edit = QLineEdit(self)
        self.line_edit.setText(text)
        self.line_edit.setStyleSheet("""
            QLineEdit {
                background-color: #1E1F22;
                color: #E0E2E6;
                border: 1px solid #4A4D51;
                border-radius: 4px;
                padding: 8px;
                font-size: 14px;
            }
            QLineEdit:focus {
                border: 1px solid #007ACC;
            }
        """)
        content_layout.addWidget(self.line_edit)


        # Buttons
        button_layout = QHBoxLayout()
        button_layout.setContentsMargins(0, 10, 0, 0)
        button_layout.addStretch()
        content_layout.addLayout(button_layout)

        self.ok_button = QPushButton("OK", self)
        self.cancel_button = QPushButton("Cancel", self)
        
        for btn in [self.ok_button, self.cancel_button]:
            btn.setStyleSheet("""
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
            button_layout.addWidget(btn)

        self.ok_button.clicked.connect(self.accept)
        self.cancel_button.clicked.connect(self.reject)
        self.line_edit.returnPressed.connect(self.accept)

        self.result_text = ""

    def accept(self):
        self.result_text = self.line_edit.text()
        super().accept()

    @staticmethod
    def getText(parent, title, label, text=""):
        dialog = CustomInputDialog(title, label, text, parent)
        if dialog.exec() == QDialog.Accepted:
            return dialog.result_text, True
        return "", False

class CustomMessageBox(QDialog):
    def __init__(self, title, text, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setStyleSheet("background-color: transparent;")

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)

        self.container = QWidget()
        self.container.setStyleSheet("""
            QWidget {
                background-color: #282A2E;
                border: 1px solid #4A4D51;
                border-radius: 8px;
            }
        """)
        self.main_layout.addWidget(self.container)
        
        container_layout = QVBoxLayout(self.container)
        container_layout.setContentsMargins(1, 1, 1, 1)
        container_layout.setSpacing(0)

        # Custom Title Bar
        self.title_bar = CustomTitleBarDialog(title, self)
        container_layout.addWidget(self.title_bar)

        # Content
        content_layout = QVBoxLayout()
        content_layout.setContentsMargins(20, 10, 20, 20)
        content_layout.setSpacing(10)
        container_layout.addLayout(content_layout)

        # Image centered above the text
        logo_label = QLabel()
        pixmap = QPixmap("img/Rust.png")
        logo_label.setPixmap(pixmap.scaled(220, 220, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        logo_label.setAlignment(Qt.AlignCenter)
        logo_label.setStyleSheet("border: none;")
        content_layout.addWidget(logo_label)

        # Rich text label centered below the image
        self.label = QLabel(text, self)
        self.label.setStyleSheet("color: #E0E2E6; font-size: 14px; border: none;")
        self.label.setWordWrap(True)
        self.label.setTextFormat(Qt.RichText)
        self.label.setAlignment(Qt.AlignCenter)
        content_layout.addWidget(self.label)
        self.setFixedWidth(500)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.setContentsMargins(0, 10, 0, 0)
        button_layout.addStretch()
        content_layout.addLayout(button_layout)

        self.yes_button = QPushButton("Yes", self)
        self.no_button = QPushButton("No", self)
        
        for btn in [self.yes_button, self.no_button]:
            btn.setStyleSheet("""
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
            button_layout.addWidget(btn)

        self.yes_button.clicked.connect(self.accept)
        self.no_button.clicked.connect(self.reject)

    @staticmethod
    def question(parent, title, text):
        dialog = CustomMessageBox(title, text, parent)
        if dialog.exec() == QDialog.Accepted:
            return QMessageBox.Yes
        return QMessageBox.No

    @staticmethod
    def information(parent, title, text):
        dialog = CustomMessageBox(title, text, parent)
        dialog.no_button.hide()
        dialog.exec()

    @staticmethod
    def about(parent, title, text):
        dialog = CustomMessageBox(title, text, parent)
        dialog.no_button.hide()
        dialog.yes_button.setText("OK")
        dialog.exec()

class RightImageInfoDialog(QDialog):
    def __init__(self, title, text, image_path="img/AI_Olama.png", parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setStyleSheet("background-color: transparent;")
        self.setFixedWidth(600)

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)

        self.container = QWidget()
        self.container.setStyleSheet(
            """
            QWidget {
                background-color: #282A2E;
                border: 1px solid #4A4D51;
                border-radius: 8px;
            }
            """
        )
        self.main_layout.addWidget(self.container)

        container_layout = QVBoxLayout(self.container)
        container_layout.setContentsMargins(1, 1, 1, 1)
        container_layout.setSpacing(0)

        # Custom Title Bar
        self.title_bar = CustomTitleBarDialog(title, self)
        container_layout.addWidget(self.title_bar)

        # Content row: text on the left, image on the right
        content_layout = QVBoxLayout()
        content_layout.setContentsMargins(20, 10, 20, 20)
        content_layout.setSpacing(10)
        container_layout.addLayout(content_layout)

        row = QHBoxLayout()
        row.setSpacing(12)
        content_layout.addLayout(row)

        # Left: rich text message
        self.label = QLabel(text, self)
        self.label.setWordWrap(True)
        self.label.setTextFormat(Qt.RichText)
        self.label.setStyleSheet("color: #E0E2E6; font-size: 14px; border: none;")
        self.label.setMinimumWidth(320)
        row.addWidget(self.label, 1)

        # Right: image
        img_lbl = QLabel()
        pixmap = QPixmap(image_path)
        if not pixmap.isNull():
            img_lbl.setPixmap(pixmap.scaled(200, 200, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        img_lbl.setAlignment(Qt.AlignCenter)
        img_lbl.setStyleSheet("border: none;")
        row.addWidget(img_lbl, 0, Qt.AlignRight | Qt.AlignVCenter)

        # Buttons (OK only)
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        ok_btn = QPushButton("OK", self)
        ok_btn.setStyleSheet(
            """
            QPushButton {
                background-color: #3C4043;
                color: #E0E2E6;
                border: 1px solid #4A4D51;
                border-radius: 4px;
                padding: 8px 20px;
                min-width: 60px;
            }
            QPushButton:hover { background-color: #4A4D51; }
            QPushButton:pressed { background-color: #5A5D61; }
            """
        )
        ok_btn.clicked.connect(self.accept)
        btn_row.addWidget(ok_btn)
        content_layout.addLayout(btn_row)

    @staticmethod
    def information(parent, title, text, image_path="img/AI_Olama.png"):
        dlg = RightImageInfoDialog(title, text, image_path, parent)
        dlg.exec()


class LicenseDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("View License")
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setStyleSheet("background-color: transparent;")
        self.setFixedWidth(600) 
        self.setFixedHeight(550)

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)

        self.container = QWidget()
        self.container.setStyleSheet("""
            QWidget {
                background-color: #282A2E;
                border: 1px solid #4A4D51;
                border-radius: 8px;
            }
        """)
        self.main_layout.addWidget(self.container)
        
        container_layout = QVBoxLayout(self.container)
        container_layout.setContentsMargins(1, 1, 1, 1)
        container_layout.setSpacing(0)

        # Custom Title Bar
        self.title_bar = CustomTitleBarDialog("View License", self)
        container_layout.addWidget(self.title_bar)

        # Content
        content_layout = QVBoxLayout()
        content_layout.setContentsMargins(20, 10, 20, 20)
        content_layout.setSpacing(10)
        container_layout.addLayout(content_layout)

        # Logo
        logo_label = QLabel()
        pixmap = QPixmap("img/Rust.png")
        logo_label.setPixmap(pixmap.scaled(256, 128, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        logo_label.setAlignment(Qt.AlignCenter)
        logo_label.setStyleSheet("border: none;")
        content_layout.addWidget(logo_label)

        # License Text
        license_text = """
        <p style="color: #59a1ff; font-weight: bold; font-size: 16px;">MIT License</p>
        <p>Copyright (c) 2025 <span style="color: #ffc559; font-weight: bold;">Ahmed Rabiee</span></p>

        <p>Permission is hereby granted, free of charge, to any person obtaining a copy
        of this software and associated documentation files (the "Software"), to deal
        in the Software without restriction, including without limitation the rights
        to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
        copies of the Software, and to permit persons to whom the Software is
        furnished to do so, subject to the following conditions:</p>

        <p>The above copyright notice and this permission notice shall be included in all
        copies or substantial portions of the Software.</p>

        <p>THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
        IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
        FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
        AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
        LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
        OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
        SOFTWARE.</p>
        """
        license_label = QLabel(license_text)
        license_label.setWordWrap(True)
        license_label.setStyleSheet("color: #E0E2E6; font-size: 12px; border: none;")
        license_label.setTextFormat(Qt.RichText)
        content_layout.addWidget(license_label)

        # OK Button
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        ok_button = QPushButton("OK")
        ok_button.setStyleSheet("""
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
        ok_button.clicked.connect(self.accept)
        button_layout.addWidget(ok_button)
        content_layout.addLayout(button_layout)

class KeyboardShortcutsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Keyboard Shortcuts")
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setStyleSheet("background-color: transparent;")
        self.setFixedWidth(800)
        self.setFixedHeight(550)

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)

        self.container = QWidget()
        self.container.setStyleSheet("""
            QWidget {
                background-color: #282A2E;
                border: 1px solid #4A4D51;
                border-radius: 8px;
            }
        """)
        self.main_layout.addWidget(self.container)
        
        container_layout = QVBoxLayout(self.container)
        container_layout.setContentsMargins(1, 1, 1, 1)
        container_layout.setSpacing(0)

        self.title_bar = CustomTitleBarDialog("Keyboard Shortcuts", self)
        container_layout.addWidget(self.title_bar)

        content_layout = QVBoxLayout()
        content_layout.setContentsMargins(20, 10, 20, 20)
        content_layout.setSpacing(15)
        container_layout.addLayout(content_layout)

        search_layout = QHBoxLayout()
        search_label = QLabel("Search:")
        search_label.setStyleSheet("color: #E0E2E6; font-size: 14px; border: none;")
        self.search_input = QLineEdit()
        self.search_input.setStyleSheet("""
            QLineEdit {
                background-color: #1E1F22;
                color: #E0E2E6;
                border: 1px solid #4A4D51;
                border-radius: 4px;
                padding: 8px;
                font-size: 14px;
            }
            QLineEdit:focus {
                border: 1px solid #007ACC;
            }
        """)
        self.search_input.textChanged.connect(self.filter_shortcuts)
        search_layout.addWidget(search_label)
        search_layout.addWidget(self.search_input)
        content_layout.addLayout(search_layout)

        self.shortcuts_table = QTableWidget()
        self.shortcuts_table.setColumnCount(2)
        self.shortcuts_table.setHorizontalHeaderLabels(["Command", "Shortcut"])
        self.shortcuts_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.shortcuts_table.setCornerButtonEnabled(False)
        self.shortcuts_table.setStyleSheet("""
            QTableWidget {
                background-color: #1E1F22;
                color: #E0E2E6;
                border: 1px solid #4A4D51;
                gridline-color: #4A4D51;
                alternate-background-color: #282A2E; /* Remove white background square */
            }
            QTableCornerButton::section {
                background-color: #1E1F22;
                border: 1px solid #4A4D51;
            }
            QHeaderView::section {
                background-color: #282A2E;
                color: #E0E2E6;
                padding: 4px;
                border: 1px solid #4A4D51;
            }
            QTableWidget::item {
                padding: 5px;
            }
            QScrollBar:vertical {
                background: #1E1F22;
                width: 12px;
                border: none;
                border-radius: 0px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: rgba(85, 85, 85, 0.6);
                border-radius: 0px;
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
                background: #1E1F22;
                height: 12px;
                border: none;
                border-radius: 0px;
                margin: 0px;
            }
            QScrollBar::handle:horizontal {
                background: rgba(85, 85, 85, 0.6);
                border-radius: 0px;
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
            QScrollBar:vertical:hover {
                background: #333333;
            }
            QScrollBar:horizontal:hover {
                background: #333333;
            }
        """)
        content_layout.addWidget(self.shortcuts_table)

        self.populate_shortcuts()

        button_layout = QHBoxLayout()
        button_layout.addStretch()
        ok_button = QPushButton("OK")
        ok_button.setStyleSheet("""
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
        ok_button.clicked.connect(self.accept)
        button_layout.addWidget(ok_button)
        content_layout.addLayout(button_layout)

    def populate_shortcuts(self):
        shortcuts = [
            # File Operations
            ("New File", "Ctrl+N"),
            ("New Window", "Ctrl+Shift+N"),
            ("New Cargo Project", "Ctrl+Alt+C"),
            ("Open File", "Ctrl+O"),
            ("Open Folder", "Ctrl+K Ctrl+O"),
            ("Save", "Ctrl+S"),
            ("Save As", "Ctrl+Shift+S"),
            ("Save All", "Ctrl+K S"),
            ("Close Editor", "Ctrl+F4"),
            ("Close Folder", "Ctrl+K F"),
            ("Close Window", "Alt+F4"),
            
            # Edit Operations
            ("Undo", "Ctrl+Z"),
            ("Redo", "Ctrl+Y"),
            ("Cut", "Ctrl+X"),
            ("Copy", "Ctrl+C"),
            ("Paste", "Ctrl+V"),
            ("Select All", "Ctrl+A"),
            ("Find", "Ctrl+F"),
            ("Replace", "Ctrl+H"),
            
            # Code Editing
            ("Toggle Line Comment", "Ctrl+/"),
            ("Toggle Block Comment", "Shift+Alt+A"),
            ("Format Code", "Shift+Alt+F"),
            ("Indent", "Tab"),
            ("Unindent", "Shift+Tab"),
            ("Insert Line Below", "Ctrl+Enter"),
            
            # Line Operations
            ("Move Line Up", "Alt+Up"),
            ("Move Line Down", "Alt+Down"),
            ("Copy Line Up", "Alt+Shift+Up"),
            ("Copy Line Down", "Alt+Shift+Down"),
            ("Delete Line", "Ctrl+Shift+K"),
            
            # Selection
            ("Expand Selection", "Alt+Shift+Right"),
            ("Shrink Selection", "Alt+Shift+Left"),
            ("Select Next Occurrence", "Ctrl+D"),
            ("Select All Occurrences", "Ctrl+F2"),
            
            # Multi-Cursor
            ("Add Cursor Above", "Ctrl+Alt+Up"),
            ("Add Cursor Below", "Ctrl+Alt+Down"),
            ("Add Cursors to Line Ends", "Alt+Shift+I"),
            
            # View & Navigation
            ("Split Editor Right", "Ctrl+\\"),
            ("Zoom In", "Ctrl+="),
            ("Zoom Out", "Ctrl+-"),
            ("Reset Zoom", "Ctrl+0"),
            
            # Run & Build
            ("Run Rust", "F5"),
            ("Cargo Check", "F6"),
            
            # Terminal
            ("New Terminal", "Ctrl+Shift+`"),
            
            # Help
            ("Keyboard Shortcuts", "Ctrl+K Ctrl+R"),
            ("Settings", "Ctrl+,"),
        ]

        self.shortcuts_table.setRowCount(len(shortcuts))
        for row, (command, shortcut) in enumerate(shortcuts):
            self.shortcuts_table.setItem(row, 0, QTableWidgetItem(command))
            self.shortcuts_table.setItem(row, 1, QTableWidgetItem(shortcut))

    def filter_shortcuts(self, text):
        for i in range(self.shortcuts_table.rowCount()):
            command_item = self.shortcuts_table.item(i, 0)
            shortcut_item = self.shortcuts_table.item(i, 1)
            if text.lower() in command_item.text().lower() or text.lower() in shortcut_item.text().lower():
                self.shortcuts_table.setRowHidden(i, False)
            else:
                self.shortcuts_table.setRowHidden(i, True)
