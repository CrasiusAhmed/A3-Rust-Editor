import os
import sys
import json
import shutil
from functools import partial

# --- Graphics / WebEngine Fixes --- U15 DMS
os.environ["QT_OPENGL"] = "desktop"
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu"
# Prevent Qt from using an internal qt.conf that can break plugin/DLL resolution in onefile builds,
# but ONLY when running as a frozen executable. When running from source, keep the internal qt.conf enabled
# so PySide6 can locate its plugins (platforms, etc.).
if getattr(sys, "frozen", False):
    os.environ["PYSIDE_DISABLE_INTERNAL_QT_CONF"] = "1"
else:
    os.environ.pop("PYSIDE_DISABLE_INTERNAL_QT_CONF", None)

from PySide6.QtCore import (
    Qt, QDir, QFileInfo, QUrl, QRegularExpression, QCoreApplication, QRect, QSize, QProcess, Slot, QTimer, QRunnable, QThreadPool, QObject, Signal, QPoint
)

from PySide6.QtGui import (
    QFont, QSyntaxHighlighter, QTextCharFormat, QColor, QPalette, QPainter, QTextFormat, QTextCursor, QIcon, QPixmap, QDesktopServices, QPen, QLinearGradient, QKeySequence, QShortcut
)

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QSplitter, QTreeView, QTextEdit,
    QVBoxLayout, QWidget, QFileDialog, QTabWidget, QPlainTextEdit,
    QMessageBox, QFileSystemModel, QMenuBar, QHeaderView,
    QHBoxLayout, QPushButton, QCompleter,
    QDialog, QDialogButtonBox, QFontComboBox, QSpinBox, QFormLayout, QComboBox,
    QMenu, QInputDialog, QLineEdit,
    QStackedWidget, QLabel, QTabBar, QStyledItemDelegate, QStyle
)

# Optional WebEngine Import
try:
    from PySide6.QtWebEngineWidgets import QWebEngineView
    WEB_ENGINE_AVAILABLE = True
except ImportError:
    WEB_ENGINE_AVAILABLE = False
    QWebEngineView = None
# Force-disable WebEngine in frozen executables to avoid recursive subprocess spawning
if getattr(sys, "frozen", False):
    WEB_ENGINE_AVAILABLE = False
    QWebEngineView = None

from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply
from PySide6.QtWidgets import QSizePolicy


# Import existing modules
from Details.Main_Code_Editor import CodeEditor
from file_showen import FileTreeDelegate, CustomFileSystemModel, FileSorterProxyModel, KeyboardDisplayWidget
from running_app import InteractiveTerminal
from manage_native import ManageWidget
from Manage.document_io import SaveLoadManager
from Details.Header_Setting import create_main_menu_bar
from Details.dialogs import CustomInputDialog, CustomMessageBox, LicenseDialog, KeyboardShortcutsDialog, CustomTitleBarDialog
from Details.welcome_page import WelcomePageWidget
from Details.file_tree_with_shortcuts import EnhancedFileTreeView

# Import new modular components
from Main.settings_dialogs import SettingsDialog
from Main.title_bar import CustomTitleBar
from Main.file_operations import FileOperationsManager
from Main.menu_actions import MenuActionsManager
from Main.terminal_manager import TerminalManager
from Main.editor_actions import EditorActionsManager
from Main.menu_style_right_click import apply_default_menu_style, show_file_tree_context_menu
from Main.color_mode import ColorModeManager
from Main.rust_runner import RustRunnerManager
from Main.rust_error_checker import RustErrorChecker, CargoCheckManager
from Main.ui_setup import UISetupManager
from Main.settings_manager import SettingsManager
from Main.window_state_manager import WindowStateManager


# Main Window
class MainWindow(QMainWindow):
    """
    The main application window for the code editor.
    Includes file tree, code editor, and preview panes.
    """
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setWindowTitle("A³ Rust Editor")
        try:
            self.setWindowIcon(QIcon("img/icon.ico"))
        except Exception:
            pass
        self.setGeometry(100, 100, 1400, 900)
        self.setStyleSheet("background-color: #131314;")
        self.current_file_path = None
        self.open_files = {}  # path: editor_widget
        self.closable_tabs_with_buttons = {}
        # Persistent color change mode state and current color for toolbar icon
        self.color_change_mode_active = False
        self.current_color_hex = "#1E1F22"
        self._cursor_move_conn = None
        # Rust execution state handled by manager
        self.rust_runner = None  # initialized later after UI

        self.settings_dir = os.path.join(os.environ.get('LOCALAPPDATA') or os.environ.get('APPDATA') or os.path.expanduser("~"), "A3PyEditor")
        try:
            os.makedirs(self.settings_dir, exist_ok=True)
        except Exception:
            pass
        self.settings_file = os.path.join(self.settings_dir, "settings.json")
        # Session persistence file (tracks open tabs, active tab, and unsaved buffers)
        self.session_file = os.path.join(self.settings_dir, "session.json")
        self.recent_files = []
        self.settings = {
            'font_family': 'Consolas',
            'font_size': 12,
            # Do NOT use the frozen EXE as a Python interpreter
            'python_interpreter_path': (sys.executable if not getattr(sys, 'frozen', False) else ''),
            'theme': 'Default',
            'restore_last_folder': True,
            'last_folder': ''
        }
        
        # Initialize managers FIRST (before loading settings)
        self.file_ops = FileOperationsManager(self)
        self.menu_actions = MenuActionsManager(self)
        self.terminal_manager = TerminalManager(self)
        self.editor_actions = EditorActionsManager(self)
        self.ui_setup = UISetupManager(self)
        self.settings_manager = SettingsManager(self)
        self.window_state_manager = WindowStateManager(self)
        
        # Initialize project manager (will be set up after UI is ready)
        self.project_manager = None
        
        # Now load settings after managers are initialized
        self.load_settings()
        # Determine initial workspace root (restore last folder if available)
        try:
            lf = (self.settings.get('last_folder') or '').strip()
            self.initial_root_path = lf if self.settings.get('restore_last_folder') and lf and os.path.isdir(lf) else ''
        except Exception:
            self.initial_root_path = ''
        # Sanitize interpreter path when running as a frozen EXE to avoid self-recursion
        try:
            if getattr(sys, 'frozen', False):
                p = (self.settings.get('python_interpreter_path') or '').strip()
                if p and os.path.abspath(p).lower() == os.path.abspath(sys.executable).lower():
                    self.settings['python_interpreter_path'] = ''
        except Exception:
            pass
        # Clipboard for file operations (copy/cut/paste)
        self.file_clipboard = {'action': None, 'paths': []}
        
        # Initialize split editor state
        self.editor_splitter = None

        # Vertical adjustment for settings menu position (pixels). Positive moves down, negative moves up.
        self.settings_menu_y_offset = 0

        # Color mode controller
        self.color_mode = ColorModeManager(self)

        self.ui_setup.setup_ui()
        # Init rust runner and cargo check manager now that self is ready
        self.rust_runner = RustRunnerManager(self)
        self.cargo_check_manager = CargoCheckManager(self)
        
        # Initialize project manager after UI is ready
        QTimer.singleShot(200, self._setup_project_manager)
        self.settings_manager.apply_settings()
        # Restore window state (size, position, maximized state, panel sizes)
        try:
            self.window_state_manager.restore_window_state()
        except Exception:
            pass
        # Restore session (open tabs and unsaved buffers like VS Code)
        try:
            self.restore_session()
        except Exception:
            pass
        # Accept drag-and-drop of files/folders into the window
        self.setAcceptDrops(True)
        # Keyboard shortcut for Change Color toggle (F1)
        try:
            self.color_change_shortcut = QShortcut(QKeySequence("F1"), self)
            self.color_change_shortcut.activated.connect(self.toggle_color_change_mode)
        except Exception:
            pass
        # Periodic session autosave to persist open tabs and unsaved edits
        try:
            self._session_autosave_timer = QTimer(self)
            self._session_autosave_timer.setInterval(2000)
            self._session_autosave_timer.timeout.connect(self.save_session_state)
            self._session_autosave_timer.start()
        except Exception:
            pass

    
    def _setup_project_manager(self):
        """Initialize the project manager for Add Project functionality"""
        try:
            from Manage2.project_manager import ProjectManager
            
            project_root = os.path.dirname(os.path.abspath(__file__))
            # Get the manage widget's canvas and toolbar
            if hasattr(self, 'manage_widget'):
                canvas = self.manage_widget.canvas
                
                # Get the toolbar that was already created by ManageWidget
                self.top_toolbar = getattr(self.manage_widget, 'top_toolbar', None)
                
                # Create project manager
                self.project_manager = ProjectManager(self, canvas, project_root)
                
                # Connect canvas double-click to check for Add node
                canvas.node_double_clicked.connect(self._on_node_double_clicked)
        except Exception:
            pass
    
    def _on_node_double_clicked(self, node):
        """Handle node double-click - check if it's the Add node"""
        try:
            # Check if this is the Add node
            is_add_tool = getattr(node, 'is_add_tool', False)
            has_add_icon = hasattr(node, 'icon_path') and node.icon_path and 'Add.png' in str(node.icon_path)
            
            if is_add_tool or has_add_icon:
                # Trigger add function dialog
                if self.project_manager:
                    self.project_manager.on_add_function_requested()
                return
            
            # Otherwise, use default behavior (show code viewer)
            if hasattr(self.manage_widget, 'on_node_double_clicked'):
                self.manage_widget.on_node_double_clicked(node)
        except Exception:
            pass
    
    def _on_menu_action(self, action_name: str):
        """Handle menu action from top right toolbar"""
        # Handle project switching
        if action_name.startswith("_load_project_"):
            try:
                project_id = int(action_name.replace("_load_project_", ""))
                from Manage2.project_loader import load_project_canvas
                load_project_canvas(self.manage_widget, self.top_toolbar.project_state, project_id)
                self.top_toolbar.refresh_projects_list()
            except Exception:
                pass
            return
        
        if action_name == "Add Project":
            if self.project_manager:
                self.project_manager.start_add_project()
            else:
                QMessageBox.warning(self, "Error", "Project manager not initialized")
        elif action_name == "Select Box":
            # Toggle selection box mode on the canvas
            if hasattr(self.manage, 'canvas'):
                current_mode = getattr(self.manage.canvas, '_selection_box_mode', False)
                self.manage.canvas.toggle_selection_box_mode(not current_mode)
        elif action_name == "Search":
            # Trigger the search box in manage widget
            try:
                if hasattr(self, 'manage_widget'):
                    self.manage_widget.trigger_search()
            except Exception:
                QMessageBox.information(self, "Search", "Search functionality")
        elif action_name == "Save A3 Project":
            self._save_layout_to_file()
        elif action_name == "Load A3 Project":
            self._open_layout_from_file()
    
    def highlight_main_python_file(self, file_path):
        """Highlight the main Python file in the file tree"""
        self.highlighted_file = file_path
        
        # Update the whole tree view to ensure all columns are highlighted
        self.tree_view.viewport().update()
        
        # Ensure the file is visible
        index = self.proxy_model.mapFromSource(self.file_model.index(file_path))
        parent_index = index.parent()
        while parent_index.isValid():
            self.tree_view.expand(parent_index)
            parent_index = parent_index.parent()
        self.tree_view.scrollTo(index)
        
        # Clear the highlight after 3 seconds
        QTimer.singleShot(3000, self.clear_main_python_highlight)
        
    def clear_main_python_highlight(self):
        """Clear the highlight from the main Python file"""
        if hasattr(self, 'highlighted_file'):
            source_index = self.file_model.index(self.highlighted_file)
            self.highlighted_file = None
            # Update all columns in the row
            for column in range(self.file_model.columnCount()):
                old_index = self.proxy_model.mapFromSource(source_index.sibling(source_index.row(), column))
                self.tree_view.update(old_index)
            # Also update the viewport to ensure complete refresh
            self.tree_view.viewport().update()
            
    
    # ++++++++++++++++++++++++++ Panel Management ++++++++++++++++++++++++++
    def show_files_panel(self):
        """Shows the file tree and restores the main editor view."""
        self.main_content_stack.setCurrentIndex(0)
        self.left_pane_stack.setCurrentIndex(0)
        # Restore preview tabs when returning to Files view
        try:
            self.preview_tabs.setVisible(True)
            self.preview_tabs.show()
            h = max(200, self.right_pane_splitter.height())
            self.right_pane_splitter.setSizes([int(h * 0.4), int(h * 0.6)])
            self.right_pane_splitter.update()
        except Exception:
            pass

    def show_search_panel(self):
        """Shows the search panel and restores the main editor view."""
        self.main_content_stack.setCurrentIndex(0)
        self.left_pane_stack.setCurrentIndex(1)
        # Update search panel root path to current workspace
        try:
            src_idx = self.proxy_model.mapToSource(self.tree_view.rootIndex())
            path = self.file_model.filePath(src_idx)
            if path and os.path.isdir(path):
                self.search_panel.set_root_path(path)
        except Exception:
            pass
        # Hide preview tabs when showing search (like VS Code)
        try:
            self.preview_tabs.setVisible(False)
            self.right_pane_splitter.setSizes([self.right_pane_splitter.height(), 0])
        except Exception:
            pass

    def show_chat_panel(self):
        """Shows the AI chat and restores the main editor view."""
        self.main_content_stack.setCurrentIndex(0)
        self.left_pane_stack.setCurrentIndex(2)
        # Hide preview tabs to maximize AI Chat height
        try:
            self.preview_tabs.setVisible(False)
            self.right_pane_splitter.setSizes([self.right_pane_splitter.height(), 0])
        except Exception:
            pass

    def show_manage_panel(self):
        """Shows the native manage panel in full screen."""
        self.main_content_stack.setCurrentIndex(1)

    
        
    def _save_layout_to_file(self):
        """Save current canvas layout AND all Layer menu projects to a .mndoc file"""
        try:
            from Manage.document_io import SaveLoadManager
            
            # Ensure Manage panel is visible
            self.show_manage_panel()
            
            # Collect current canvas state WITH all Layer menu projects
            save_manager = SaveLoadManager()
            state = save_manager.collect_state(self.manage_widget, include_projects=True)
            
            # Ask user where to save
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "Save A3 Project",
                "",
                save_manager.suggested_filter()
            )
            
            if file_path:
                # Ensure .mndoc extension
                file_path = save_manager.ensure_extension(file_path)
                
                # Save to file (includes all projects)
                save_manager.save_to_file(file_path, state)
                
                # Mark all projects as saved
                if hasattr(self, 'manage_widget') and hasattr(self.manage_widget, 'top_toolbar'):
                    project_state = self.manage_widget.top_toolbar.project_state
                    for project in project_state.get_all_projects():
                        project_state.mark_project_saved(project.id)
                
                # Show custom success dialog
                from Manage2.project_dialogs import SaveSuccessDialog
                success_dialog = SaveSuccessDialog(
                    file_path,
                    len(state.get('projects', {})),
                    False,  # Rust.py doesn't use whole_file feature
                    self
                )
                success_dialog.exec()
        except Exception as e:
            print(f"[Rust.py] Error saving layout: {e}")
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "Error", f"Failed to save project:\n{e}")
    
    def _open_layout_from_file(self):
        """Load canvas layout AND all Layer menu projects from a .mndoc file"""
        try:
            from Manage.document_io import SaveLoadManager
            from Manage.data_analysis import FunctionNode
            
            save_manager = SaveLoadManager()
            
            # Ask user which file to load
            file_path, _ = QFileDialog.getOpenFileName(
                self,
                "Load A3 Project",
                "",
                save_manager.suggested_filter()
            )
            
            if not file_path or not os.path.exists(file_path):
                return
            
            # Ensure Manage panel is visible
            self.show_manage_panel()
            
            # Load the document
            doc = save_manager.load_from_file(file_path)
            
            # Restore Layer menu projects if present
            projects_data = doc.get('projects', {})
            if projects_data and hasattr(self, 'manage_widget') and hasattr(self.manage_widget, 'top_toolbar'):
                print(f"[Rust.py] Restoring {len(projects_data)} Layer menu projects")
                
                # Get project state manager
                project_state = self.manage_widget.top_toolbar.project_state
                
                # Clear existing projects
                project_state.projects = {}
                
                # Restore each project
                from Manage2.project_state import ProjectData
                for project_id_str, project_dict in projects_data.items():
                    try:
                        project = ProjectData.from_dict(project_dict)
                        project_state.projects[project.id] = project
                        print(f"[Rust.py] ✓ Restored project: {project.name} (ID: {project.id})")
                    except Exception as e:
                        print(f"[Rust.py] ERROR restoring project {project_id_str}: {e}")
                
                # Restore next_project_id and active_project_id
                if 'next_project_id' in doc:
                    project_state.next_project_id = doc['next_project_id']
                if 'active_project_id' in doc:
                    project_state.active_project_id = doc['active_project_id']
                
                # Refresh Layer menu
                self.manage_widget.top_toolbar.refresh_projects_list()
                
                print(f"[Rust.py] ✓ Restored {len(project_state.projects)} projects to Layer menu")
            
            # Clear canvas first
            self.manage_widget.canvas.clear()
            
            # Get nodes from document (current canvas state)
            nodes_data = doc.get('nodes', [])
            
            if nodes_data:
                print(f"[Rust.py] Loading {len(nodes_data)} nodes from file")
                
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
                        self.manage_widget.canvas.nodes.append(node)
                        
                        # Index the node
                        if hasattr(self.manage_widget.canvas, '_index_node'):
                            self.manage_widget.canvas._index_node(node)
                        
                        print(f"[Rust.py] ✓ Loaded node: {node.name}")
                    except Exception as e:
                        print(f"[Rust.py] ERROR loading node: {e}")
                        import traceback
                        traceback.print_exc()
                
                # Apply viewport and other settings
                save_manager.apply_to_canvas(self.manage_widget.canvas, doc)
                
                # Update canvas
                self.manage_widget.canvas.update()
                
                print(f"[Rust.py] ✓ Loaded {len(self.manage_widget.canvas.nodes)} nodes from: {file_path}")
            
            # Show custom success dialog
            num_projects = len(projects_data)
            num_nodes = len(nodes_data)
            from Manage2.project_dialogs import LoadSuccessDialog
            success_dialog = LoadSuccessDialog(
                num_projects,
                num_nodes,
                False,  # Rust.py doesn't use whole_file feature
                self
            )
            success_dialog.exec()
            
        except Exception as e:
            print(f"[Rust.py] Error loading layout: {e}")
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "Error", f"Failed to load project:\n{e}")

    # ++++++++++++++++++++++++++ Core Methods ++++++++++++++++++++++++++
    def get_current_editor(self):
        """Returns the currently active CodeEditor widget."""
        return self.editor_tabs.currentWidget()

    def get_editor_for_path(self, file_path):
        """Returns the CodeEditor widget for a given file path."""
        return self.open_files.get(file_path)

    def close_editor_tab(self, index):
        """Closes an editor tab and removes it from tracking."""
        editor = self.editor_tabs.widget(index)
        if editor:
            self.close_editor_by_widget(editor)
            
    def close_editor_by_widget(self, editor):
        """Closes an editor tab by widget reference and removes it from tracking."""
        if not editor:
            return
        
        # If closing the Welcome tab, keep its index in sync
        if editor == getattr(self, 'welcome_page', None):
            self.welcome_tab_index = -1
            
        # Find the tab index for this editor
        tab_index = self.editor_tabs.indexOf(editor)
        if tab_index == -1:
            return
            
        # Clean up tracking dictionaries
        if editor in self.closable_tabs_with_buttons:
            del self.closable_tabs_with_buttons[editor]
            
        path_to_remove = None
        for path, e in self.open_files.items():
            if e == editor:
                path_to_remove = path
                break
                
        if path_to_remove:
            del self.open_files[path_to_remove]
                    
        # Remove the tab and clean up the editor
        self.editor_tabs.removeTab(tab_index)
        editor.deleteLater()
        
        # Update toolbar visibility
        self.update_editor_toolbar_visibility()
        # Persist session after a tab is closed
        try:
            self.save_session_state()
        except Exception:
            pass

    def close_welcome_tab(self):
        """Closes the welcome tab."""
        if self.welcome_tab_index >= 0:
            self.editor_tabs.removeTab(self.welcome_tab_index)
            self.welcome_tab_index = -1

    def on_editor_tab_changed(self, index):
        if index > -1:
            widget = self.editor_tabs.widget(index)
            for path, editor in self.open_files.items():
                if editor == widget:
                    self.current_file_path = path
                    break
            # Attach cursor move listener to update color icon when in Change Color mode
            try:
                if hasattr(self, '_cursor_move_conn') and self._cursor_move_conn:
                    prev_editor, slot = self._cursor_move_conn
                    try:
                        prev_editor.cursorPositionChanged.disconnect(slot)
                    except Exception:
                        pass
                    self._cursor_move_conn = None
                # Only connect if this is a CodeEditor instance
                if isinstance(widget, CodeEditor):
                    # Ensure Change Color click is enabled on this editor if global mode active
                    try:
                        widget.enable_change_color_click = bool(getattr(self, 'color_change_mode_active', False))
                    except Exception:
                        pass
                    slot = self.update_color_icon_from_cursor
                    widget.cursorPositionChanged.connect(slot)
                    self._cursor_move_conn = (widget, slot)
                    # Update icon immediately based on current cursor position
                    self.update_color_icon_from_cursor()
            except Exception:
                pass

    def create_menu(self):
        """Creates the application's menu bar."""
        return create_main_menu_bar(self)

    def on_file_clicked(self, index):
        """Handles file clicks in the file tree view."""
        source_index = self.proxy_model.mapToSource(index)
        path = self.file_model.filePath(source_index)
        if self.file_model.isDir(source_index):
            if self.tree_view.isExpanded(index):
                self.tree_view.collapse(index)
            else:
                self.tree_view.expand(index)
            self.file_model.dataChanged.emit(source_index, source_index)
        else:
            self.file_ops.open_file_for_editing(path)

    def on_modification_changed(self, editor, modified):
        """Updates the tab's close button to indicate unsaved changes."""
        if editor in self.closable_tabs_with_buttons:
            button = self.closable_tabs_with_buttons[editor]
            if modified:
                button.setText("●")
                button.setStyleSheet("border:none; background:transparent; color: white; font-weight: normal; font-size: 16px; padding: 0px 4px;")
            else:
                button.setText("X")
                button.setStyleSheet("border:none; background:transparent; color: #BDC1C6; font-weight: bold; font-size: 14px; padding: 2px 6px;")

    @Slot(int)
    def on_tab_changed(self, index):
        """Handles tab changes in the preview tab widget."""
        try:
            current_widget = self.preview_tabs.widget(index)
            if current_widget == getattr(self, 'python_console_output', None):
                if self.current_file_path and os.path.isfile(self.current_file_path):
                    self.run_rust_for_current_file(self.current_file_path)
            else:
                self.statusBar().showMessage(f"Switched to '{self.preview_tabs.tabText(index)}' tab.", 2000)
        except Exception:
            pass

    # ++++++++++++++++++++++++++ Linting ++++++++++++++++++++++++++
 
    def setup_completer_for_editor(self, editor):
        """Sets up the autocompleter for a given editor instance."""
        self.menu_actions.setup_completer_for_editor(editor)

    # ++++++++++++++++++++++++++ Settings ++++++++++++++++++++++++++
    def open_settings_dialog(self):
        """Opens the settings dialog and applies changes if accepted."""
        self.settings_manager.open_settings_dialog()

    def load_settings(self):
        """Load settings from file."""
        self.settings_manager.load_settings()

    def save_settings(self):
        """Save settings to file."""
        self.settings_manager.save_settings()

    def apply_settings(self):
        """Apply the current settings to all open editors and terminals."""
        self.settings_manager.apply_settings()

    # ++++++++++++++++++++++++++ Session Persistence (open tabs and unsaved buffers) ++++++++++++++++++++++++++
    def save_session_state(self):
        """Persist open tabs, active tab, and unsaved buffer contents to session_file."""
        try:
            open_tabs = []
            # Map editor widget -> file path for quick lookup
            editor_to_path = {}
            try:
                for p, e in self.open_files.items():
                    editor_to_path[e] = p
            except Exception:
                pass

            for i in range(self.editor_tabs.count()):
                w = self.editor_tabs.widget(i)
                # Skip welcome page if present
                if w == getattr(self, 'welcome_page', None):
                    continue
                path = None
                try:
                    path = editor_to_path.get(w)
                except Exception:
                    pass
                if not path:
                    # Only persist file-backed tabs for now
                    continue
                try:
                    cursor = w.textCursor()
                    pos = cursor.position()
                except Exception:
                    pos = 0
                try:
                    from PySide6.QtWidgets import QAbstractScrollArea
                    vs = getattr(w, 'verticalScrollBar', None)
                    scroll_val = vs().value() if callable(vs) else 0
                except Exception:
                    scroll_val = 0
                try:
                    modified = bool(w.document().isModified())
                except Exception:
                    modified = False
                try:
                    text = w.toPlainText() if modified else None
                except Exception:
                    text = None
                open_tabs.append({
                    'path': path,
                    'cursor_pos': pos,
                    'v_scroll': scroll_val,
                    'modified': modified,
                    'unsaved_text': text,
                })

            # Determine active path
            active_path = None
            try:
                active_path = self.current_file_path if self.current_file_path in [t['path'] for t in open_tabs] else None
            except Exception:
                active_path = None

            state = {
                'open_tabs': open_tabs,
                'active_path': active_path,
            }
            # Ensure settings dir exists
            try:
                os.makedirs(self.settings_dir, exist_ok=True)
            except Exception:
                pass
            with open(self.session_file, 'w', encoding='utf-8') as f:
                json.dump(state, f, indent=2)
        except Exception:
            pass

    def _apply_restored_states(self, saved_state: dict):
        """Apply saved cursor/scroll/unsaved buffers after tabs have been opened."""
        try:
            tabs = saved_state.get('open_tabs') or []
            # Build path->editor mapping
            editor_by_path = {}
            try:
                for p, e in self.open_files.items():
                    editor_by_path[p] = e
            except Exception:
                pass
            for t in tabs:
                p = t.get('path')
                if not p:
                    continue
                ed = editor_by_path.get(p)
                if not ed:
                    continue
                try:
                    if t.get('modified') and t.get('unsaved_text') is not None:
                        ed.blockSignals(True)
                        ed.setPlainText(t.get('unsaved_text') or "")
                        try:
                            ed.document().setModified(True)
                        except Exception:
                            pass
                        ed.blockSignals(False)
                        # Update unsaved indicator on tab
                        try:
                            self.on_modification_changed(ed, True)
                        except Exception:
                            pass
                except Exception:
                    pass
                # Restore cursor and scroll
                try:
                    cur = ed.textCursor()
                    cur.setPosition(int(t.get('cursor_pos') or 0))
                    ed.setTextCursor(cur)
                except Exception:
                    pass
                try:
                    vs = getattr(ed, 'verticalScrollBar', None)
                    if callable(vs):
                        vs().setValue(int(t.get('v_scroll') or 0))
                except Exception:
                    pass
            # Restore active tab by path
            try:
                ap = saved_state.get('active_path')
                if ap:
                    for i in range(self.editor_tabs.count()):
                        w = self.editor_tabs.widget(i)
                        if self.open_files.get(ap) == w:
                            self.editor_tabs.setCurrentIndex(i)
                            break
            except Exception:
                pass
        except Exception:
            pass

    def restore_session(self):
        """Restore previously open tabs and unsaved edits at startup."""
        try:
            if not os.path.exists(self.session_file):
                return
            with open(self.session_file, 'r', encoding='utf-8') as f:
                state = json.load(f)
            tabs = state.get('open_tabs') or []
            if not tabs:
                return
            # Open folder root to the first tab's directory for a consistent tree
            # BUT ONLY if no initial_root_path was already set from settings
            try:
                if not self.initial_root_path:
                    first_path = tabs[0].get('path')
                    if first_path and os.path.isfile(first_path):
                        folder = os.path.dirname(first_path)
                        # Prefer the Cargo project root if this file is inside a Cargo project
                        try:
                            cargo_root = self.rust_runner.find_cargo_root(folder)
                        except Exception:
                            cargo_root = None
                        root_to_open = cargo_root or folder
                        if root_to_open and os.path.isdir(root_to_open):
                            self.file_ops.open_folder_from_path(root_to_open)
            except Exception:
                pass
            # Open each tab
            for t in tabs:
                p = t.get('path')
                if p and os.path.isfile(p):
                    try:
                        self.file_ops.open_file_for_editing(p)
                    except Exception:
                        pass
            # Apply states after event loop cycles to ensure editors are created
            QTimer.singleShot(250, lambda: self._apply_restored_states(state))
            # Close welcome if we opened at least one file
            try:
                if self.editor_tabs.count() > 1:
                    self.close_welcome_tab()
            except Exception:
                pass
        except Exception:
            pass

    def show_settings_menu(self):
        """Creates and shows a context menu for the settings button."""
        self.settings_manager.show_settings_menu()

    def open_file_context_menu(self, position):
        """Opens context menu for file/folder operations (delegated to shared module)."""
        show_file_tree_context_menu(self, position)
    
    def refresh_file_tree(self):
        """Refresh the file tree view after file operations."""
        try:
            # Force the file model to refresh
            current_root = self.tree_view.rootIndex()
            if current_root.isValid():
                source_root = self.proxy_model.mapToSource(current_root)
                path = self.file_model.filePath(source_root)
                if path:
                    # Re-set the root to force a refresh
                    self.file_model.setRootPath(path)
            # Update the view
            self.tree_view.viewport().update()
        except Exception as e:
            print(f"Error refreshing file tree: {e}")

    def show_welcome_page(self):
        """Shows the welcome page tab."""
        if self.welcome_tab_index == -1:
            self.welcome_page = WelcomePageWidget(self)
            self.welcome_tab_index = self.editor_tabs.addTab(self.welcome_page, "Welcome")
            self.editor_tabs.setCurrentIndex(self.welcome_tab_index)
        else:
            self.editor_tabs.setCurrentIndex(self.welcome_tab_index)

    # ++++++++++++++++++++++++++ Delegate Methods to Managers ++++++++++++++++++++++++++
    # File operations
    def new_window(self):
        self.menu_actions.new_window()

    def create_new_file(self, base_path=None):
        self.file_ops.create_new_file(base_path)

    def open_file(self):
        self.file_ops.open_file()

    def open_folder(self):
        self.file_ops.open_folder()

    def save_file(self):
        self.file_ops.save_file()

    def save_as_file(self):
        self.file_ops.save_as_file()

    def save_all_files(self):
        self.file_ops.save_all_files()

    def close_current_editor(self):
        self.file_ops.close_current_editor()

    def close_folder(self):
        self.file_ops.close_folder()

    def create_cargo_project_here(self):
        """Create a new Cargo binary project in the currently opened folder (tree view root)."""
        try:
            # Determine the current root folder from the file tree
            src_idx = self.proxy_model.mapToSource(self.tree_view.rootIndex())
            root_path = self.file_model.filePath(src_idx)
            if not root_path or not os.path.isdir(root_path):
                QMessageBox.warning(self, "New Cargo Project", "Open a folder first (File > Open Folder...) to choose where to create the Cargo project.")
                return

            cargo_toml = os.path.join(root_path, "Cargo.toml")
            src_dir = os.path.join(root_path, "src")
            main_rs = os.path.join(src_dir, "main.rs")

            # Prevent accidental overwrite if Cargo.toml already exists
            if os.path.exists(cargo_toml):
                QMessageBox.information(self, "New Cargo Project", "Cargo.toml already exists in this folder. Aborting to avoid overwriting.")
                return

            os.makedirs(src_dir, exist_ok=True)

            # Derive a package name from the folder name (lowercase, hyphens for invalid chars)
            folder_name = os.path.basename(os.path.abspath(root_path)) or "app"
            pkg = ''.join(ch if (ch.isalnum() or ch in '-_') else '-' for ch in folder_name.lower())
            if pkg and pkg[0].isdigit():
                pkg = f"app-{pkg}"
            if not pkg:
                pkg = "app"

            cargo_contents = (
                f"[package]\n"
                f"name = \"{pkg}\"\n"
                f"version = \"0.1.0\"\n"
                f"edition = \"2021\"\n\n"
                f"[dependencies]\n"
            )
            main_rs_contents = (
                "fn main() {\n"
                "    println!(\"Hello, world!\");\n"
                "}\n"
            )

            with open(cargo_toml, 'w', encoding='utf-8') as f:
                f.write(cargo_contents)
            with open(main_rs, 'w', encoding='utf-8') as f:
                f.write(main_rs_contents)

            # Notify and open main.rs in the editor
            try:
                self.statusBar().showMessage("Cargo project created.", 4000)
            except Exception:
                pass
            try:
                self.file_ops.open_file_for_editing(main_rs)
                self.highlight_main_python_file(main_rs)
            except Exception:
                pass
        except Exception as e:
            try:
                QMessageBox.critical(self, "New Cargo Project", f"Error creating project:\n{e}")
            except Exception:
                pass

    # Edit operations
    def undo(self):
        self.menu_actions.undo()

    def redo(self):
        self.menu_actions.redo()

    def cut(self):
        self.menu_actions.cut()

    def copy(self):
        self.menu_actions.copy()

    def paste(self):
        self.menu_actions.paste()

    def find_text(self):
        self.menu_actions.find_text()

    def replace_text(self):
        self.menu_actions.replace_text()

    def select_all(self):
        self.menu_actions.select_all()

    def expand_selection(self):
        self.menu_actions.expand_selection()

    def shrink_selection(self):
        self.menu_actions.shrink_selection()

    def add_cursor_above(self):
        self.menu_actions.add_cursor_above()

    def add_cursor_below(self):
        self.menu_actions.add_cursor_below()

    def select_next_occurrence(self):
        """Select next occurrence of the current selection (Ctrl+D)."""
        editor = self.get_current_editor()
        if editor and hasattr(editor, 'multi') and editor.multi:
            editor.multi.select_next_occurrence()

    def select_all_occurrences(self):
        """Select all occurrences of the current selection (Ctrl+F2)."""
        editor = self.get_current_editor()
        if editor and hasattr(editor, 'multi') and editor.multi:
            editor.multi.select_all_occurrences()

    def copy_line_up(self):
        self.menu_actions.copy_line_up()

    def copy_line_down(self):
        self.menu_actions.copy_line_down()

    def move_line_up(self):
        self.menu_actions.move_line_up()

    def move_line_down(self):
        self.menu_actions.move_line_down()

    def toggle_line_comment(self):
        self.menu_actions.toggle_line_comment()

    def toggle_block_comment(self):
        self.menu_actions.toggle_block_comment()

    # Terminal operations
    def toggle_terminal_panel(self):
        self.terminal_manager.toggle_terminal_panel()

    # Help operations
    def show_about_dialog(self):
        self.menu_actions.show_about_dialog()

    def open_documentation(self):
        self.menu_actions.open_documentation()

    def show_welcome_message(self):
        self.menu_actions.show_welcome_message()

    def show_keyboard_shortcuts(self):
        self.menu_actions.show_keyboard_shortcuts()

    # ++++++++++++++++++++++++++ Change Color Mode ++++++++++++++++++++++++++
    def enable_color_change_mode(self):
        return self.color_mode.enable_color_change_mode()

    def set_color_icon(self, hex_color: str):
        return self.color_mode.set_color_icon(hex_color)

    def _extract_hex_under_cursor(self, editor):
        return self.color_mode.extract_hex_under_cursor(editor)

    def update_color_icon_from_cursor(self):
        return self.color_mode.update_color_icon_from_cursor()

    def disable_color_change_mode(self):
        return self.color_mode.disable_color_change_mode()

    def toggle_color_change_mode(self):
        return self.color_mode.toggle_color_change_mode()

    def view_license(self):
        self.menu_actions.view_license()

    def check_for_updates(self):
        self.menu_actions.check_for_updates()

    # Additional methods referenced in Header_Setting.py
    def open_file_for_editing(self, path, line_number=None):
        """Delegate to file operations manager."""
        self.file_ops.open_file_for_editing(path, line_number)

    def add_new_terminal(self):
        """Delegate to terminal manager."""
        self.terminal_manager.add_new_terminal()

    def open_video_tutorials(self):
        """Delegate to menu actions."""
        self.menu_actions.open_video_tutorials()

    def show_tips_and_tricks(self):
        """Delegate to menu actions."""
        self.menu_actions.show_tips_and_tricks()

    def join_youtube(self):
        """Delegate to menu actions."""
        self.menu_actions.join_youtube()

    def report_issue(self):
        """Delegate to menu actions."""
        self.menu_actions.report_issue()

    # ++++++++++++++++++++++++++ Python Run Functionality ++++++++++++++++++++++++++
   
    def split_editor_right(self):
        """Delegate to editor actions manager."""
        self.editor_actions.split_editor_right()

    def update_editor_toolbar_visibility(self):
        """Delegate to editor actions manager."""
        self.editor_actions.update_editor_toolbar_visibility()
        
    def run_current_rust(self):
        """Run Rust for the current file and focus the Rust Run output pane."""
        try:
            self.preview_tabs.setCurrentWidget(self.python_console_output)
        except Exception:
            pass
        if self.current_file_path and os.path.isfile(self.current_file_path):
            try:
                folder = os.path.dirname(os.path.abspath(self.current_file_path))
                in_cargo = bool(self.rust_runner.find_cargo_root(folder))
                is_rs = self.current_file_path.lower().endswith('.rs')
                if not in_cargo and not is_rs:
                    self.python_console_output.appendPlainText("Select a Rust file (.rs) or a file inside a Cargo project (with Cargo.toml) to run.")
                    return
            except Exception:
                pass
            self.run_rust_for_current_file(self.current_file_path)
        else:
            try:
                self.python_console_output.appendPlainText("No file selected to run. Open a Rust file and try again.")
            except Exception:
                pass

    def run_cargo_check(self):
        """Run cargo check for fast error checking without running the program."""
        # Delegate to CargoCheckManager
        self.cargo_check_manager.run_cargo_check()
    
                
    # Rust run helpers
    def run_rust_for_current_file(self, file_path: str):
        return self.rust_runner.run_for_current_file(file_path)


    # ++++++++++++++++++++++++++ Drag and Drop Support ++++++++++++++++++++++++++
    def dragEnterEvent(self, event):
        """Accept drag if it contains file/folder URLs."""
        try:
            if event.mimeData().hasUrls():
                event.acceptProposedAction()
        except Exception:
            pass

    def dropEvent(self, event):
        """Handle drop of files or folders into the app window."""
        try:
            urls = event.mimeData().urls()
            if not urls:
                return
            # Prefer to set root to the first folder, or to the parent of the first file
            root_set = False
            for url in urls:
                p = url.toLocalFile()
                if not p:
                    continue
                if os.path.isdir(p) and not root_set:
                    self.file_ops.open_folder_from_path(p)
                    try:
                        self.settings['last_folder'] = os.path.abspath(p)
                        self.save_settings()
                    except Exception:
                        pass
                    root_set = True
                    # continue to also open any files included in the drop
            for url in urls:
                p = url.toLocalFile()
                if not p:
                    continue
                if os.path.isfile(p):
                    if not root_set:
                        folder = os.path.dirname(os.path.abspath(p))
                        # Prefer the Cargo project root if this file is inside a Cargo project
                        try:
                            cargo_root = self.rust_runner.find_cargo_root(folder)
                        except Exception:
                            cargo_root = None
                        root_to_open = cargo_root or folder
                        self.file_ops.open_folder_from_path(root_to_open)
                        try:
                            self.settings['last_folder'] = root_to_open
                            self.save_settings()
                        except Exception:
                            pass
                        root_set = True
                    self.file_ops.open_file_for_editing(p)
            event.acceptProposedAction()
        except Exception:
            pass
            
    def keyPressEvent(self, event):
        """Handle keyboard shortcuts for split editor and running Rust."""
        if event.key() == Qt.Key_F5:
            try:
                self.preview_tabs.setCurrentWidget(self.python_console_output)
            except Exception:
                pass
            if self.current_file_path and os.path.isfile(self.current_file_path):
                self.run_rust_for_current_file(self.current_file_path)
            return
        elif event.key() == Qt.Key_F6:
            # Cargo Check shortcut
            self.run_cargo_check()
            return
        elif event.key() == Qt.Key_Backslash and event.modifiers() == Qt.ControlModifier:
            self.split_editor_right()
            return
        super().keyPressEvent(event)


    def resizeEvent(self, event):
        """Save window state when window is resized."""
        super().resizeEvent(event)
        # Only save if not maximized (we want to track manual resizes)
        if not self.isMaximized():
            try:
                if hasattr(self, 'window_state_manager'):
                    self.window_state_manager.save_window_state()
            except Exception:
                pass
    
    def changeEvent(self, event):
        """Handle window state changes (maximize/minimize/restore)."""
        super().changeEvent(event)
        # Detect window state changes (maximize/restore)
        if event.type() == event.Type.WindowStateChange:
            try:
                # Update the maximize button icon
                if hasattr(self, 'maximize_button'):
                    if self.isMaximized():
                        # Show restore icon (two overlapping windows)
                        self.maximize_button.setText("❐")
                    else:
                        # Show maximize icon (single window)
                        self.maximize_button.setText("☐")
                
                # Notify window state manager
                if hasattr(self, 'window_state_manager'):
                    self.window_state_manager.on_window_state_changed()
            except Exception as e:
                print(f"[Rust.py] Error in changeEvent: {e}")
    
    def closeEvent(self, event):
        """Persist last opened folder and session on exit."""
        # Check for unsaved changes in Manage panel
        try:
            if hasattr(self, 'manage_widget') and hasattr(self.manage_widget, 'top_toolbar'):
                project_state = self.manage_widget.top_toolbar.project_state
                
                # Check if ANY project has unsaved changes
                unsaved_projects = [p for p in project_state.get_all_projects() if p.is_modified]
                
                if unsaved_projects:
                    # Save current active project's canvas state first
                    active = project_state.get_active_project()
                    if active:
                        try:
                            from Manage.document_io import SaveLoadManager
                            save_manager = SaveLoadManager()
                            canvas_state = save_manager.collect_state(self.manage_widget)
                            project_state.update_project_canvas(active.id, canvas_state)
                        except Exception:
                            pass
                    
                    # Show custom dialog for unsaved changes
                    if len(unsaved_projects) == 1:
                        project_name = unsaved_projects[0].name
                    else:
                        project_name = f"{len(unsaved_projects)} projects"
                    
                    # Use the existing UnsavedChangesDialog
                    from Manage2.project_dialogs import UnsavedChangesDialog
                    
                    dialog = UnsavedChangesDialog(project_name, self)
                    dialog.exec()
                    
                    if dialog.result_action == "save":
                        # Trigger Save A3 Project
                        self._save_layout_to_file()
                        # If user cancelled the save dialog, don't close
                        if project_state.get_active_project() and project_state.get_active_project().is_modified:
                            event.ignore()
                            return
                    elif dialog.result_action == "cancel":
                        event.ignore()
                        return
                    # If discard, just continue to close
        except Exception as e:
            print(f"[Rust.py] Error checking project state: {e}")
            import traceback
            traceback.print_exc()
        
        # Clean up file tree resources (temp backup directory)
        try:
            if hasattr(self, 'tree_view') and self.tree_view:
                self.tree_view.cleanup()
        except Exception:
            pass
        
        # Stop any running Rust processes and clean up instrumented files
        try:
            if hasattr(self, 'rust_runner') and self.rust_runner:
                # Kill running process
                if self.rust_runner.process and self.rust_runner.process.state() == QProcess.Running:
                    self.rust_runner.process.kill()
                    self.rust_runner.process.waitForFinished(1000)
                
                # Clean up instrumented file and restore original
                if self.rust_runner.instrumented_file_path:
                    try:
                        from rust_auto_instrument import cleanup_instrumented_file
                        cleanup_instrumented_file(self.rust_runner.instrumented_file_path)
                    except Exception:
                        pass
                    
                    # Restore original file if we modified it (Cargo project)
                    if self.rust_runner.current_file_path:
                        backup_path = self.rust_runner.current_file_path + '.backup'
                        if os.path.exists(backup_path):
                            try:
                                shutil.copy2(backup_path, self.rust_runner.current_file_path)
                                os.remove(backup_path)
                            except Exception:
                                pass
        except Exception:
            pass
        
        # Save window state (size, position, maximized state, panel sizes)
        try:
            self.window_state_manager.save_window_state()
        except Exception:
            pass
        # Save current session state (open tabs and unsaved buffers)
        try:
            self.save_session_state()
        except Exception:
            pass
        # Persist last opened folder
        try:
            src_idx = self.proxy_model.mapToSource(self.tree_view.rootIndex())
            path = self.file_model.filePath(src_idx)
            if path and os.path.isdir(path):
                self.settings['last_folder'] = path
                self.save_settings()
        except Exception:
            pass
        super().closeEvent(event)


if __name__ == "__main__":
    # When frozen as onefile, switch CWD to the PyInstaller temp dir so relative assets like 'img/...'
    # resolve from the bundled resources extracted to sys._MEIPASS. This enables a true single-exe build.
    try:
        if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
            os.chdir(sys._MEIPASS)
    except Exception:
        pass
    # Register .mndoc file association (per-user) with this executable and icon
    try:
        if sys.platform.startswith("win") and getattr(sys, "frozen", False):
            import winreg
            exe_path = sys.executable
            prog_id = "A3Editor.mndoc"
            # Associate .mndoc with prog_id
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\\Classes\\.mndoc") as k:
                winreg.SetValueEx(k, "", 0, winreg.REG_SZ, prog_id)
            # Set prog_id description
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, fr"Software\\Classes\\{prog_id}") as k:
                try:
                    winreg.SetValueEx(k, "", 0, winreg.REG_SZ, "A³ Manage Document")
                except Exception:
                    pass
            # Default icon to this EXE's embedded icon
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, fr"Software\\Classes\\{prog_id}\\DefaultIcon") as k:
                winreg.SetValueEx(k, "", 0, winreg.REG_SZ, f'"{exe_path}",0')
            # Open command
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, fr"Software\\Classes\\{prog_id}\\shell\\open\\command") as k:
                winreg.SetValueEx(k, "", 0, winreg.REG_SZ, f'"{exe_path}" "%1"')
            # Notify Windows that associations changed so icons refresh
            try:
                import ctypes
                SHCNE_ASSOCCHANGED = 0x8000000
                SHCNF_IDLIST = 0x0000
                ctypes.windll.shell32.SHChangeNotify(SHCNE_ASSOCCHANGED, SHCNF_IDLIST, None, None)
            except Exception:
                pass
    except Exception:
        pass
    app = QApplication(sys.argv)
    
    # Set application-wide dark theme palette for text selections
    # This fixes the white background issue when selecting text and clicking another tab
    try:
        app_palette = app.palette()
        
        # Active selection colors (when widget has focus) - VS Code-like blue
        app_palette.setColor(QPalette.Active, QPalette.Highlight, QColor(38, 79, 135))  # Dark blue
        app_palette.setColor(QPalette.Active, QPalette.HighlightedText, QColor(212, 212, 212))  # Light gray text
        
        # Inactive selection colors (when widget loses focus) - dimmed version
        # This is the KEY fix - without this, Qt uses system default (white background)
        app_palette.setColor(QPalette.Inactive, QPalette.Highlight, QColor(58, 58, 58))  # Dark gray (RGB ~0.3 like VS Code)
        app_palette.setColor(QPalette.Inactive, QPalette.HighlightedText, QColor(212, 212, 212))  # Same light gray text
        
        # Disabled state (for completeness)
        app_palette.setColor(QPalette.Disabled, QPalette.Highlight, QColor(45, 45, 45))
        app_palette.setColor(QPalette.Disabled, QPalette.HighlightedText, QColor(128, 128, 128))
        
        app.setPalette(app_palette)
    except Exception as e:
        print(f"Warning: Could not set application palette: {e}")
    
    # Ensure app-level icon is set for taskbar/title even when running from Python
    try:
        app.setWindowIcon(QIcon("img/icon.ico"))
    except Exception:
        pass
    window = MainWindow()
    window.show()
    # Auto-open a .mndoc passed on the command line (for file association / double-click)
    try:
        mndoc_arg = next((a for a in sys.argv[1:] if a.lower().endswith('.mndoc')), None)
        if mndoc_arg and os.path.exists(mndoc_arg):
            window.open_mndoc(mndoc_arg)
    except Exception:
        pass
    # Handle files/folders passed on the command line (drag-drop onto EXE or file association)
    try:
        other_args = [a for a in sys.argv[1:] if not a.lower().endswith('.mndoc')]
        if other_args:
            first_folder_set = False
            # Prefer folder root if provided
            for a in other_args:
                if os.path.isdir(a):
                    window.file_ops.open_folder_from_path(a)
                    try:
                        window.settings['last_folder'] = os.path.abspath(a)
                        window.save_settings()
                    except Exception:
                        pass
                    first_folder_set = True
                    break
            # Open any files and ensure their folder is set as root if no folder argument
            for a in other_args:
                if os.path.isfile(a):
                    if not first_folder_set:
                        folder = os.path.dirname(os.path.abspath(a))
                        # Prefer the Cargo project root if this file is inside a Cargo project
                        try:
                            cargo_root = window.rust_runner.find_cargo_root(folder)
                        except Exception:
                            cargo_root = None
                        root_to_open = cargo_root or folder
                        window.file_ops.open_folder_from_path(root_to_open)
                        try:
                            window.settings['last_folder'] = root_to_open
                            window.save_settings()
                        except Exception:
                            pass
                        first_folder_set = True
                    window.file_ops.open_file_for_editing(a)
    except Exception:
        pass
    sys.exit(app.exec())