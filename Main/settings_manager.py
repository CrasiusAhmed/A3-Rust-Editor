"""
Settings Management Module for A³ Rust Editor
Contains all settings-related operations extracted from Rust.py
"""

import os
import json
import sys
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QMenu
from PySide6.QtCore import QPoint

from Main.settings_dialogs import SettingsDialog
from Main.menu_style_right_click import apply_default_menu_style


class SettingsManager:
    """Manages all settings operations for the main window."""
    
    def __init__(self, main_window):
        """
        Initialize the settings manager.
        
        Args:
            main_window: Reference to the MainWindow instance
        """
        self.window = main_window
    
    def load_settings(self):
        """Load settings from the settings file."""
        try:
            with open(self.window.settings_file, 'r') as f:
                settings = json.load(f)
                self.window.settings.update(settings)
                self.window.recent_files = settings.get('recent_files', [])
        except (FileNotFoundError, json.JSONDecodeError):
            pass

    def save_settings(self):
        """Save settings to the settings file."""
        try:
            with open(self.window.settings_file, 'w') as f:
                settings_to_save = self.window.settings.copy()
                settings_to_save['recent_files'] = self.window.recent_files
                json.dump(settings_to_save, f, indent=4)
        except Exception as e:
            print(f"Error saving settings: {e}")

    def apply_settings(self):
        """Apply the current settings to all open editors and terminals."""
        font = QFont(self.window.settings['font_family'], self.window.settings['font_size'])
        for editor in self.window.open_files.values():
            editor.setFont(font)

    def open_settings_dialog(self):
        """Open the settings dialog and apply changes if accepted."""
        available_interpreters = []
        
        dialog = SettingsDialog(self.window.settings, available_interpreters, self.window)
        if dialog.exec():
            self.window.settings = dialog.get_settings()
            self.apply_settings()
            self.save_settings()
            self.window.statusBar().showMessage("Settings updated.", 2000)

    def show_settings_menu(self):
        """Create and show a context menu for the settings button."""
        settings_menu = QMenu(self.window)
        apply_default_menu_style(settings_menu)

        settings_action = settings_menu.addAction("Settings")
        settings_action.setShortcut("Ctrl+,")
        settings_action.triggered.connect(self.open_settings_dialog)

        kb_shortcuts_action = settings_menu.addAction("Keyboard Shortcuts")
        kb_shortcuts_action.triggered.connect(self.window.menu_actions.show_keyboard_shortcuts)

        settings_menu.addSeparator()

        license_action = settings_menu.addAction("View License")
        license_action.triggered.connect(self.window.menu_actions.view_license)

        updates_action = settings_menu.addAction("Check for Updates")
        updates_action.triggered.connect(self.window.menu_actions.check_for_updates)

        # Position relative to the settings button; only adjust Y by a configurable offset
        btn_rect = self.window.settings_button.rect()
        menu_size = settings_menu.sizeHint()

        # Window bounds in global coords
        window_top_left = self.window.mapToGlobal(QPoint(0, 0))
        window_left = window_top_left.x()
        window_top = window_top_left.y()
        window_right = window_left + self.window.width()
        window_bottom = window_top + self.window.height()

        # Anchor points
        anchor_top_right = self.window.settings_button.mapToGlobal(btn_rect.topRight())
        anchor_bottom_right = self.window.settings_button.mapToGlobal(btn_rect.bottomRight())

        # Prefer opening above if there is enough space
        if menu_size.height() <= (anchor_top_right.y() - window_top):
            x = anchor_top_right.x()  # keep X unchanged
            y = anchor_top_right.y() - menu_size.height() + getattr(self.window, 'settings_menu_y_offset', 0)
        else:
            x = anchor_bottom_right.x()  # keep X unchanged
            y = anchor_bottom_right.y() + getattr(self.window, 'settings_menu_y_offset', 0)

        # Clamp to window bounds without altering X unless it overflows
        if x + menu_size.width() > window_right:
            x = window_right - menu_size.width()
        if x < window_left:
            x = window_left
        if y + menu_size.height() > window_bottom:
            y = window_bottom - menu_size.height()
        if y < window_top:
            y = window_top

        settings_menu.exec(QPoint(x + 6, y + 45))
