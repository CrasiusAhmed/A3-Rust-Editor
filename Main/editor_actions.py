"""
Editor actions and functionality for split editor.
"""
import os
from functools import partial
from PySide6.QtCore import QFileInfo, Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QPushButton, QTabBar, QSplitter, QTabWidget, QWidget, QHBoxLayout
from Details.Main_Code_Editor import CodeEditor


class EditorActionsManager:
    """Manages editor actions for split editor functionality."""
    
    def __init__(self, main_window):
        self.main_window = main_window

    def split_editor_right(self):
        """Splits the current editor to the right with the same file (VS Code style)."""
        current_editor = self.main_window.get_current_editor()
        if not current_editor or not self.main_window.current_file_path:
            self.main_window.statusBar().showMessage("No file is currently open to split.", 3000)
            return
        
        # Check if we already have a split view
        if hasattr(self.main_window, 'editor_splitter') and self.main_window.editor_splitter:
            self.main_window.statusBar().showMessage("Editor is already split.", 2000)
            return
        
        # Get the current tab index and editor
        current_tab_index = self.main_window.editor_tabs.currentIndex()
        current_tab_text = self.main_window.editor_tabs.tabText(current_tab_index)
        
        # Remove toolbar from left editor tabs
        self.main_window.editor_tabs.setCornerWidget(None)
        
        # Create a horizontal splitter for the editors
        self.main_window.editor_splitter = QSplitter(Qt.Horizontal)
        
        # Remove the current editor tabs from its parent
        editor_container = self.main_window.editor_tabs.parent()
        editor_layout = editor_container.layout()
        editor_layout.removeWidget(self.main_window.editor_tabs)
        
        # Create right side editor tabs
        self.main_window.right_editor_tabs = self.create_editor_tabs_widget()

        # Set the toolbar on the new right-side tab widget
        self.main_window.right_editor_tabs.setCornerWidget(self.main_window.editor_toolbar, Qt.TopRightCorner)
        
        # Add both tab widgets to the splitter
        self.main_window.editor_splitter.addWidget(self.main_window.editor_tabs)
        self.main_window.editor_splitter.addWidget(self.main_window.right_editor_tabs)
        
        # Set equal sizes
        self.main_window.editor_splitter.setSizes([400, 400])

        # Add the splitter directly back to the layout
        editor_layout.addWidget(self.main_window.editor_splitter)
        
        # Create a new editor with the same content for the right side
        new_editor = CodeEditor(self.main_window)
        # Set the font from settings
        settings_font = QFont(self.main_window.settings['font_family'], self.main_window.settings['font_size'])
        new_editor.setFont(settings_font)
        # Update the base font for Ctrl+0 reset to use the settings font, not the default Qt font
        try:
            new_editor._base_font = QFont(settings_font)
        except Exception:
            pass
        self.main_window.setup_completer_for_editor(new_editor)
        
        # Copy content from current editor
        new_editor.setPlainText(current_editor.toPlainText())
        
        # Connect modification signal
        new_editor.document().modificationChanged.connect(
            partial(self.main_window.on_modification_changed, new_editor)
        )
        
        # Add the new editor to the right side
        tab_index = self.main_window.right_editor_tabs.addTab(new_editor, current_tab_text)
        self.main_window.right_editor_tabs.setCurrentWidget(new_editor)
        
        # Custom close button on split tab; ensure it stays behind scroller arrows
        close_button = QPushButton("X")
        close_button.setStyleSheet("border:none; background:transparent; color: #BDC1C6; font-weight: bold; font-size: 14px; padding: 2px 6px;")
        close_button.clicked.connect(lambda checked=False: self.close_split_editor())
        self.main_window.right_editor_tabs.tabBar().setTabButton(tab_index, QTabBar.RightSide, close_button)
        close_button.lower()
        
        # Store reference to the split editor
        self.main_window.split_editor = new_editor

        self.update_editor_toolbar_visibility()
        self.main_window.statusBar().showMessage(f"Editor split created for {current_tab_text}", 2000)

    def create_editor_tabs_widget(self):
        """Creates a new QTabWidget with the same styling as the main editor tabs."""
        from PySide6.QtWidgets import QTabWidget
        
        tabs = QTabWidget()
        tabs.setTabsClosable(True)
        tabs.tabCloseRequested.connect(self.close_split_editor)
        tabs.setStyleSheet("""
            QTabWidget::pane { border-top: 1px solid #282A2E; }
            QTabBar::tab {
                background: #131314; color: #BDC1C6; padding: 8px 15px;
                border: 1px solid #131314; border-bottom: none;
                border-top-left-radius: 6px; border-top-right-radius: 6px;
            }
            QTabBar::tab:selected {
                background: #1E1F22; color: #E8EAED;
            }
            QTabBar::tab:!selected:hover {
                background: #282A2E;
            }
            /* Force white scroll arrows on the tab bar scroller buttons */
            QTabBar::scroller { width: 36px; }
            QTabBar QToolButton { background: transparent; border: none; }
            QTabBar QToolButton::right-arrow { image: url(img/arrow-right.svg); }
            QTabBar QToolButton::left-arrow { image: url(img/arrow-left.svg); }
            QTabBar QToolButton::right-arrow:disabled { image: url(img/arrow-right.svg); }
            QTabBar QToolButton::left-arrow:disabled { image: url(img/arrow-left.svg); }
            QTabBar QToolButton::right-arrow:hover { image: url(img/arrow-right.svg); }
            QTabBar QToolButton::left-arrow:hover { image: url(img/arrow-left.svg); }
            QTabBar QToolButton::right-arrow:pressed { image: url(img/arrow-right.svg); }
            QTabBar QToolButton::left-arrow:pressed { image: url(img/arrow-left.svg); }
        """)
        
        # No toolbar on the right side - keep it simple
        return tabs

    def close_split_editor(self):
        """Closes the split editor and returns to single editor view."""
        if not hasattr(self.main_window, 'editor_splitter') or not self.main_window.editor_splitter:
            return

        editor_container = self.main_window.editor_splitter.parentWidget()
        editor_layout = editor_container.layout()

        # Remove the splitter from the layout
        editor_layout.removeWidget(self.main_window.editor_splitter)

        # Reparent the main editor tabs before the splitter is deleted
        self.main_window.editor_tabs.setParent(editor_container)
        editor_layout.addWidget(self.main_window.editor_tabs)

        # Clean up the splitter and its children
        self.main_window.editor_splitter.deleteLater()
        self.main_window.editor_splitter = None

        # Delete attributes
        if hasattr(self.main_window, 'right_editor_tabs'):
            delattr(self.main_window, 'right_editor_tabs')
        if hasattr(self.main_window, 'split_editor'):
            delattr(self.main_window, 'split_editor')

        # Restore the corner widget on the main editor tabs
        self.main_window.editor_tabs.setCornerWidget(self.main_window.editor_toolbar, Qt.TopRightCorner)
        self.update_editor_toolbar_visibility()

        self.main_window.statusBar().showMessage("Split editor closed", 2000)

    def update_editor_toolbar_visibility(self):
        """Shows or hides the editor toolbar based on whether code editors are open."""
        has_code_editors = False
        # Check main editor tabs
        for i in range(self.main_window.editor_tabs.count()):
            widget = self.main_window.editor_tabs.widget(i)
            if isinstance(widget, CodeEditor):
                has_code_editors = True
                break
        
        # Check right editor tabs if they exist
        if not has_code_editors and hasattr(self.main_window, 'right_editor_tabs'):
            for i in range(self.main_window.right_editor_tabs.count()):
                widget = self.main_window.right_editor_tabs.widget(i)
                if isinstance(widget, CodeEditor):
                    has_code_editors = True
                    break

        if has_code_editors:
            self.main_window.editor_toolbar.show()
        else:
            self.main_window.editor_toolbar.hide()