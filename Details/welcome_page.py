import os
from PySide6.QtCore import Qt, QUrl, QSize
from PySide6.QtGui import QFont, QPixmap, QDesktopServices, QIcon
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QScrollArea, QFrame, QSpacerItem, QSizePolicy
)

class WelcomePageWidget(QWidget):
    """
    A VS Code-style welcome page widget.
    Clean, simple, and modern design.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self.setup_ui()
        
    def setup_ui(self):
        """Set up the welcome page UI"""
        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Scroll area for content
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setStyleSheet("""
            QScrollArea {
                background-color: #1E1E1E;
                border: none;
            }
            QScrollBar:vertical {
                background: #1E1E1E;
                width: 14px;
                border: none;
            }
            QScrollBar::handle:vertical {
                background: #424242;
                border-radius: 7px;
                min-height: 30px;
            }
            QScrollBar::handle:vertical:hover {
                background: #4E4E4E;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)
        
        # Content widget
        content = QWidget()
        content.setStyleSheet("background-color: #1E1E1E;")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(60, 40, 60, 40)
        content_layout.setSpacing(0)
        
        # Logo and title section
        self.create_header(content_layout)
        
        # Add spacing
        content_layout.addSpacing(50)
        
        # Two-column layout for Start and Help sections
        columns_layout = QHBoxLayout()
        columns_layout.setSpacing(80)
        columns_layout.setAlignment(Qt.AlignTop)
        
        # Left column - Start section
        left_column = QVBoxLayout()
        left_column.setSpacing(0)
        self.create_start_section(left_column)
        columns_layout.addLayout(left_column, 1)
        
        # Right column - Help section
        right_column = QVBoxLayout()
        right_column.setSpacing(0)
        self.create_help_section(right_column)
        columns_layout.addLayout(right_column, 1)
        
        content_layout.addLayout(columns_layout)
        
        # Add stretch to push content to top
        content_layout.addStretch()
        
        # Footer
        content_layout.addSpacing(40)
        self.create_footer(content_layout)
        
        scroll_area.setWidget(content)
        main_layout.addWidget(scroll_area)
        
    def create_header(self, layout):
        """Create header with logo and title"""
        header_layout = QHBoxLayout()
        header_layout.setSpacing(20)
        header_layout.setAlignment(Qt.AlignLeft)
        
        # Logo
        logo_label = QLabel()
        if os.path.exists("img/Rust.png"):
            pixmap = QPixmap("img/Rust.png")
            logo_label.setPixmap(pixmap.scaled(64, 64, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            logo_label.setText("🦀")
            logo_label.setFont(QFont("Segoe UI", 48))
        logo_label.setAlignment(Qt.AlignCenter)
        header_layout.addWidget(logo_label)
        
        # Title
        title_layout = QVBoxLayout()
        title_layout.setSpacing(5)
        
        title = QLabel("A³ Rust Editor")
        title.setFont(QFont("Segoe UI", 24, QFont.Bold))
        title.setStyleSheet("color: #CCCCCC;")
        title_layout.addWidget(title)
        
        subtitle = QLabel("Version 1.0")
        subtitle.setFont(QFont("Segoe UI", 11))
        subtitle.setStyleSheet("color: #858585;")
        title_layout.addWidget(subtitle)
        
        header_layout.addLayout(title_layout)
        header_layout.addStretch()
        
        layout.addLayout(header_layout)
        
    def create_start_section(self, layout):
        """Create Start section with quick actions"""
        # Section title
        title = QLabel("Start")
        title.setFont(QFont("Segoe UI", 13, QFont.Bold))
        title.setStyleSheet("color: #CCCCCC;")
        layout.addWidget(title)
        
        layout.addSpacing(15)
        
        # Action items
        actions = [
            ("New File...", "Ctrl+N", self.new_file),
            ("Open File...", "Ctrl+O", self.open_file),
            ("Open Folder...", "Ctrl+K Ctrl+O", self.open_folder),
            ("New Cargo Project...", "Ctrl+Alt+C", self.new_cargo_project),
        ]
        
        for text, shortcut, callback in actions:
            btn = self.create_link_button(text, shortcut)
            btn.clicked.connect(callback)
            layout.addWidget(btn)
            layout.addSpacing(8)
            
    def create_help_section(self, layout):
        """Create Help section with resources"""
        # Section title
        title = QLabel("Help")
        title.setFont(QFont("Segoe UI", 13, QFont.Bold))
        title.setStyleSheet("color: #CCCCCC;")
        layout.addWidget(title)
        
        layout.addSpacing(15)
        
        # Help items
        help_items = [
            ("Keyboard Shortcuts Reference", "Ctrl+K Ctrl+R", self.show_shortcuts),
            ("Rust Documentation", "", lambda: QDesktopServices.openUrl(QUrl("https://doc.rust-lang.org/"))),
            ("Video Tutorials", "", lambda: QDesktopServices.openUrl(QUrl("https://www.youtube.com/@Crasius-madman"))),
            ("Join Us On YouTube", "", lambda: QDesktopServices.openUrl(QUrl("https://www.youtube.com/@Crasius-madman"))),
            ("Report Issue", "", lambda: QDesktopServices.openUrl(QUrl("https://github.com/CrasiusAhmed"))),
            ("Settings", "", self.open_settings),
            ("Check for Updates", "", self.check_updates),
        ]
        
        for text, shortcut, callback in help_items:
            btn = self.create_link_button(text, shortcut)
            btn.clicked.connect(callback)
            layout.addWidget(btn)
            layout.addSpacing(8)
            
    def create_link_button(self, text, shortcut=""):
        """Create a VS Code-style link button"""
        btn = QPushButton()
        btn.setCursor(Qt.PointingHandCursor)
        btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                text-align: left;
                padding: 6px 8px;
                color: #3794FF;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 0.05);
                text-decoration: underline;
            }
        """)
        
        # Create layout for button content
        btn_layout = QHBoxLayout(btn)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.setSpacing(10)
        
        # Text label
        text_label = QLabel(text)
        text_label.setStyleSheet("color: #3794FF; background: transparent; border: none;")
        text_label.setFont(QFont("Segoe UI", 13))
        btn_layout.addWidget(text_label)
        
        # Shortcut label (if provided)
        if shortcut:
            shortcut_label = QLabel(shortcut)
            shortcut_label.setStyleSheet("color: #858585; background: transparent; border: none;")
            shortcut_label.setFont(QFont("Segoe UI", 11))
            btn_layout.addWidget(shortcut_label)
        
        btn_layout.addStretch()
        
        return btn
        
    def create_footer(self, layout):
        """Create footer with additional info"""
        footer_layout = QHBoxLayout()
        footer_layout.setSpacing(20)
        
        # Rust info
        rust_info = QLabel("🦀 Rust Development Environment")
        rust_info.setFont(QFont("Segoe UI", 10))
        rust_info.setStyleSheet("color: #858585;")
        footer_layout.addWidget(rust_info)
        
        footer_layout.addStretch()
        
        # Made by
        made_by = QLabel("Made with ❤️ by Ahmed Rabiee")
        made_by.setFont(QFont("Segoe UI", 10))
        made_by.setStyleSheet("color: #858585;")
        footer_layout.addWidget(made_by)
        
        layout.addLayout(footer_layout)
        
    # Action callbacks
    def new_file(self):
        """Create new file"""
        if self.parent_window:
            self.parent_window.create_new_file()
            
    def open_file(self):
        """Open file"""
        if self.parent_window:
            self.parent_window.open_file()
            
    def open_folder(self):
        """Open folder"""
        if self.parent_window:
            self.parent_window.open_folder()
            
    def new_cargo_project(self):
        """Create new Cargo project"""
        if self.parent_window:
            self.parent_window.create_cargo_project_here()
            
    def open_settings(self):
        """Open settings"""
        if self.parent_window:
            self.parent_window.open_settings_dialog()
            
    def show_shortcuts(self):
        """Show keyboard shortcuts"""
        if self.parent_window:
            self.parent_window.show_keyboard_shortcuts()
            
    def check_updates(self):
        """Check for updates"""
        if self.parent_window:
            self.parent_window.check_for_updates()
