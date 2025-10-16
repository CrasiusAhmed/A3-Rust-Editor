"""
Custom title bar component for the main window.
"""
from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QPainter, QColor, QPixmap
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel, QPushButton


class CustomTitleBar(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.setFixedHeight(35)
        self.m_old_pos = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Logo
        self.logo_label = QLabel(self)
        pixmap = QPixmap("img/logo.png")
        self.logo_label.setPixmap(pixmap.scaled(35, 35, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        self.logo_label.setFixedSize(40, 35)
        self.logo_label.setAlignment(Qt.AlignCenter)
        self.logo_label.setStyleSheet("background-color: transparent;")
        layout.addWidget(self.logo_label)

        # Menu Bar
        self.menu_bar = self.parent.create_menu()
        layout.addWidget(self.menu_bar)

        layout.addStretch()

        # Window Title
        self.title_label = QLabel(self.parent.windowTitle(), self)
        self.title_label.setAlignment(Qt.AlignCenter)
        self.title_label.setStyleSheet("background-color: transparent; color: #BDC1C6; font-size: 14px;")
        layout.addWidget(self.title_label)

        layout.addStretch()

        # Window buttons
        self.minimize_button = QPushButton("_", self)
        self.maximize_button = QPushButton("☐", self)
        self.close_button = QPushButton("✕", self)
        
        # Store reference to maximize button for updating icon
        self.parent.maximize_button = self.maximize_button

        for btn, hover_color in [(self.minimize_button, "#3C4043"), (self.maximize_button, "#3C4043"), (self.close_button, "#E81123")]:
            btn.setFixedSize(45, 35)
            btn.setStyleSheet(f'''
                QPushButton {{
                    background-color: transparent;
                    color: #BDC1C6;
                    border: none;
                    font-size: 16px;
                }}
                QPushButton:hover {{
                    background-color: {hover_color};
                }}
            ''')
            layout.addWidget(btn)

        self.minimize_button.clicked.connect(self.parent.showMinimized)
        self.maximize_button.clicked.connect(self.toggle_maximize_restore)
        self.close_button.clicked.connect(self.parent.close)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#18181A"))

    def toggle_maximize_restore(self):
        # IMPORTANT: Capture geometry BEFORE changing state
        if not self.parent.isMaximized():
            # About to maximize - capture current normal geometry
            try:
                if hasattr(self.parent, 'window_state_manager'):
                    current_geom = self.parent.geometry()
                    self.parent.window_state_manager._last_normal_geometry = current_geom
            except Exception:
                pass
        
        # Now toggle the state
        if self.parent.isMaximized():
            self.parent.showNormal()
        else:
            self.parent.showMaximized()
        
        # Save window state after toggling
        try:
            if hasattr(self.parent, 'window_state_manager'):
                self.parent.window_state_manager.save_window_state()
        except Exception:
            pass

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.m_old_pos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event):
        if self.m_old_pos is not None:
            delta = event.globalPosition().toPoint() - self.m_old_pos
            self.parent.move(self.parent.x() + delta.x(), self.parent.y() + delta.y())
            self.m_old_pos = event.globalPosition().toPoint()

    def mouseReleaseEvent(self, event):
        self.m_old_pos = None