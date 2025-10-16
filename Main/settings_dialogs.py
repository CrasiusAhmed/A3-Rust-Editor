"""
Settings dialogs and configuration management.
"""
import os
import sys
from PySide6.QtCore import Qt, QDir
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QWidget, QHBoxLayout, QFormLayout,
    QFontComboBox, QSpinBox, QComboBox, QPushButton, QFileDialog
)
from Details.dialogs import CustomTitleBarDialog


class SettingsDialog(QDialog):
    """
    A dialog to let users customize editor settings.
    """
    def __init__(self, settings, interpreters, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setStyleSheet("background-color: transparent;")

        self.settings = settings

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)

        self.container = QWidget()
        self.container.setStyleSheet("""
            QWidget {
                background-color: #282A2E;
                border: 1px solid #4A4D51;
                border-radius: 8px;
            }
            QLabel {
                color: #E0E2E6;
            }
        """)
        self.main_layout.addWidget(self.container)
        
        container_layout = QVBoxLayout(self.container)
        container_layout.setContentsMargins(1, 1, 1, 1)
        container_layout.setSpacing(0)

        # Custom Title Bar
        self.title_bar = CustomTitleBarDialog("Settings", self)
        container_layout.addWidget(self.title_bar)

        # Content
        content_layout = QVBoxLayout()
        content_layout.setContentsMargins(20, 10, 20, 20)
        content_layout.setSpacing(10)
        container_layout.addLayout(content_layout)

        form_layout = QFormLayout()
        form_layout.setSpacing(10)
        form_layout.setLabelAlignment(Qt.AlignRight)

        # Font Family
        self.font_combo = QFontComboBox()
        self.font_combo.setCurrentFont(QFont(self.settings['font_family']))
        self.font_combo.setStyleSheet("""
            QFontComboBox {
                background-color: #1E1F22;
                color: #E0E2E6;
                border: none;
                border-radius: 4px;
                padding: 8px;
                font-size: 14px;
            }
            QFontComboBox:focus {
                border: 1px solid #007ACC;
            }
            QFontComboBox QAbstractItemView {
                background-color: #282A2E;
                color: #E0E2E6;
                selection-background-color: #4A4D51;
            }
        """)
        form_layout.addRow("Font Family:", self.font_combo)

        # Font Size
        self.font_size_spinbox = QSpinBox()
        self.font_size_spinbox.setRange(8, 48)
        self.font_size_spinbox.setValue(self.settings['font_size'])
        self.font_size_spinbox.setStyleSheet("""
            QSpinBox {
                background-color: #1E1F22;
                color: #E0E2E6;
                border: none;
                border-radius: 4px;
                padding: 8px;
                font-size: 14px;
            }
            QSpinBox:focus {
                border: 1px solid #007ACC;
            }
        """)
        form_layout.addRow("Font Size:", self.font_size_spinbox)

        content_layout.addLayout(form_layout)

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

    def get_settings(self):
        """
        Returns the selected settings.
        """
        return {
            'font_family': self.font_combo.currentFont().family(),
            'font_size': self.font_size_spinbox.value()
        }