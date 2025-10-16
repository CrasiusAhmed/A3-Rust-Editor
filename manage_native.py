"""
Native Python Function Dependency Visualizer (Beginner-Friendly Launcher)
Pure PySide6 implementation - No HTTP server needed!
Wraps Manage.ManageWidget with a ready-to-use window, tips, and sensible defaults.

What this provides:
- Starts a window hosting the ManageWidget
- Sets the file browser root to the project directory
- Automatically loads a target Python file (prefers ai_chat.py if present)
- If a main script (e.g., safe.py) is detected, opens a beginner-friendly usage view
- Opens helpful panels (Details/Stats) by default to guide users
- Optional CLI: python manage_native.py <file_to_analyze.py>

This file does NOT modify any Manage or simple_manage.py internals; it configures behavior for beginners.
"""

from __future__ import annotations

import os
import sys
from typing import Optional

from PySide6.QtCore import Qt, QTimer, QEvent, QSize
from PySide6.QtGui import QIcon, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QFileDialog,
    QMessageBox,
    QLabel,
    QFrame,
    QPushButton,
    QHBoxLayout,
    QVBoxLayout,
    QWidget,
    QMenu,
)

# Import the main widget from the modular structure
from Manage.main_widget import ManageWidget
# Import the top right toolbar from Manage2
from Manage2.top_right_toolbar import TopRightToolbar
# Import project manager
from Manage2.project_manager import ProjectManager

__all__ = ["ManageWidget"]


class ManageNativeWindow(QMainWindow):
    """Top-level window that hosts ManageWidget and configures a guided UX."""

    def __init__(self, initial_file: Optional[str] = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Manage Native - Beginner Mode")
        try:
            self.setWindowIcon(QIcon("img/Manage_Python.png"))
        except Exception:
            pass

        # Central widget: the core manage UI
        self.manage = ManageWidget(self)
        self.setCentralWidget(self.manage)

        # Intercept shortcut overrides at window level to avoid QAction conflicts
        try:
            self.installEventFilter(self)
        except Exception:
            pass

        
        # Fix dark tooltip styling for toolbar icons
        try:
            self.setStyleSheet(self.styleSheet() + """
                QToolTip {
                    background-color: #2C2E33;
                    color: #E8EAED;
                    border: 1px solid #4A4D51;
                    padding: 6px 8px;
                    border-radius: 6px;
                }
            """)
        except Exception:
            pass

        # Configure file browser root to the last opened folder (or project directory as fallback)
        project_root = self._get_project_root()
        last_folder = self._get_last_folder_from_settings()
        root_to_use = last_folder if last_folder and os.path.isdir(last_folder) else project_root
        self.manage.set_root_path(root_to_use)

        # Hook ManageWidget loads to always update the main warning/highlight
        # AND to save current project state before loading
        try:
            self._orig_manage_load_file = self.manage.load_file
            def _wrapped_load_file(fp):
                # Save current project state before loading a file
                try:
                    if hasattr(self, 'top_toolbar') and self.top_toolbar:
                        project_state = self.top_toolbar.project_state
                        active_project = project_state.get_active_project()
                        
                        if active_project:
                            # Save current canvas state to the active project
                            from Manage.document_io import SaveLoadManager
                            save_manager = SaveLoadManager()
                            canvas_state = save_manager.collect_state(self.manage)
                            project_state.update_project_canvas(active_project.id, canvas_state)
                            print(f"[ManageNative] Saved Project {active_project.id} state before loading file")
                except Exception as e:
                    print(f"[ManageNative] Error saving project before load: {e}")
                
                # Now load the file
                self._orig_manage_load_file(fp)
                
                # After loading, create/switch to a project named after the file
                # Use a longer delay to ensure top_toolbar is initialized
                QTimer.singleShot(300, lambda: self._create_file_project(fp))
                
                QTimer.singleShot(350, self._try_open_usage_viewer)
                QTimer.singleShot(450, self._maybe_show_main_warning)
            self.manage.load_file = _wrapped_load_file
        except Exception:
            pass

        # Subtle tips overlay for beginners
        self.tips_label = QLabel(self.manage.canvas)
        self.tips_label.setText(
            "\n".join(
                [
                    "Tips:",
                    "• Double-click a function bubble to view its code.",
                    "• Double-click the Python icon bubble to see where these functions are used in the main script (e.g., safe.py).",
                    "• Use the left toolbar: File Browser and Python Preview.",
                ]
            )
        )
        self.tips_label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.tips_label.setStyleSheet(
            """
            QLabel {
                color: #D4D4D4;
                background-color: rgba(0, 0, 0, 80);
                border: 1px solid #4A4D51;
                border-radius: 8px;
                padding: 10px;
                font-size: 12px;
            }
            """
        )
        self.tips_label.resize(520, 100)
        self.tips_label.move(120, 60)
        self.tips_label.show()

        # Helper panels disabled (Details/Statistics removed)

        # Placeholder for warning overlay
        self._warning_box = None

        # Initialize project manager
        self.project_manager = None
        
        # Load initial file (auto or from CLI)
        QTimer.singleShot(0, lambda: self._auto_load(initial_file))
        
        # Add top right toolbar with two icons (after a delay to ensure canvas is ready)
        QTimer.singleShot(100, self._setup_top_right_toolbar)
        
        # Initialize project manager after canvas is ready
        QTimer.singleShot(200, self._setup_project_manager)

    # ----------------------- Top Right Toolbar -----------------------
    def _setup_top_right_toolbar(self):
        """Create and position the top right toolbar using Manage2 module"""
        try:
            self.top_toolbar = TopRightToolbar(self.manage.canvas)
            self.top_toolbar.menu_action_triggered.connect(self._on_menu_action)
            self.top_toolbar.position_toolbar(
                self.manage.canvas.width(),
                self.manage.canvas.height()
            )
            self.top_toolbar.show()
            self.top_toolbar.raise_()
        except Exception as e:
            print(f"Error setting up toolbar: {e}")
    
    def _setup_project_manager(self):
        """Initialize the project manager"""
        try:
            project_root = self._get_project_root()
            self.project_manager = ProjectManager(self, self.manage.canvas, project_root)
            self.manage.canvas.node_double_clicked.connect(self._on_node_double_clicked)
        except Exception as e:
            print(f"Error setting up project manager: {e}")
    
    def _on_node_double_clicked(self, node):
        """Handle node double-click - check if it's the Add node or show code editor"""
        try:
            is_add_tool = getattr(node, 'is_add_tool', False)
            has_add_icon = hasattr(node, 'icon_path') and node.icon_path and 'Add.png' in str(node.icon_path)
            
            if is_add_tool or has_add_icon:
                if self.project_manager:
                    self.project_manager.on_add_function_requested()
                return
            
            if hasattr(self.manage, 'show_function_code_viewer'):
                self.manage.show_function_code_viewer(node)
            elif hasattr(self.manage, 'on_node_double_clicked'):
                self.manage.on_node_double_clicked(node)
        except Exception as e:
            print(f"Error in node double-click: {e}")
    
    def _create_file_project(self, fp: str):
        """Create or update a project for the loaded file"""
        try:
            if not hasattr(self, 'top_toolbar') or not self.top_toolbar or not fp:
                return
            
            filename = os.path.basename(fp)
            project_state = self.top_toolbar.project_state
            
            existing_project = None
            for project in project_state.get_all_projects():
                if project.name == filename:
                    existing_project = project
                    break
            
            if existing_project:
                self._update_file_project(existing_project.id, filename)
            else:
                new_project = project_state.create_project(name=filename)
                QTimer.singleShot(200, lambda: self._update_file_project(new_project.id, filename))
        except Exception as e:
            print(f"Error in _create_file_project: {e}")
    
    def _update_file_project(self, project_id: int, filename: str):
        """Update a file-based project with current canvas state and set as active"""
        try:
            project_state = self.top_toolbar.project_state
            from Manage.document_io import SaveLoadManager
            save_manager = SaveLoadManager()
            canvas_state = save_manager.collect_state(self.manage)
            project_state.update_project_canvas(project_id, canvas_state)
            project_state.set_active_project(project_id)
            self.top_toolbar.refresh_projects_list()
        except Exception as e:
            print(f"Error updating file project: {e}")
    
    def _on_menu_action(self, action_name: str):
        """Handle menu action selection"""
        if action_name.startswith("_load_project_"):
            project_id = int(action_name.replace("_load_project_", ""))
            self._save_current_project_state()
            self._load_project_canvas(project_id)
            return
        
        if action_name == "Add Project":
            # Start the Add Project workflow (file selection)
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
            QMessageBox.information(self, "Search", "Search functionality will be implemented here.")
        elif action_name == "Save A3 Project":
            self._save_layout_to_file()
        elif action_name == "Load A3 Project":
            self._open_layout_from_file()
    
    def _create_new_project(self):
        """Create a new project"""
        try:
            project_state = self.top_toolbar.project_state
            project = project_state.create_project()
            project_state.set_active_project(project.id)
            self.manage.canvas.clear()
            self.top_toolbar.refresh_projects_list()
            QMessageBox.information(self, "Project Created", f"Created new project: {project.name}")
        except Exception as e:
            print(f"Error creating project: {e}")
            QMessageBox.critical(self, "Error", f"Failed to create project:\n{e}")
    
    def _save_layout_to_file(self):
        """Save current canvas layout AND all Layer menu projects to a .mndoc file"""
        try:
            from Manage.document_io import SaveLoadManager
            
            # Ask user if they want to save current canvas as "whole file" default view
            save_as_whole_file = False
            if len(self.manage.canvas.nodes) > 0:
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
            save_manager = SaveLoadManager()
            state = save_manager.collect_state(
                self.manage, 
                include_projects=True,
                save_as_whole_file=save_as_whole_file
            )
            
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
                project_state = self.top_toolbar.project_state
                for project in project_state.get_all_projects():
                    project_state.mark_project_saved(project.id)
                
                # Show custom success dialog
                from Manage2.project_dialogs import SaveSuccessDialog
                success_dialog = SaveSuccessDialog(
                    file_path,
                    len(state.get('projects', {})),
                    save_as_whole_file,
                    self
                )
                success_dialog.exec()
                
                print(f"[ManageNative] Saved layout to: {file_path}")
                print(f"[ManageNative] Saved {len(state.get('projects', {}))} Layer menu projects")
                if save_as_whole_file:
                    print(f"[ManageNative] Saved 'whole file' view as default")
        except Exception as e:
            print(f"[ManageNative] Error saving layout: {e}")
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
            
            # Load the document
            doc = save_manager.load_from_file(file_path)
            
            # Restore Layer menu projects if present
            projects_data = doc.get('projects', {})
            if projects_data:
                print(f"[ManageNative] Restoring {len(projects_data)} Layer menu projects")
                
                # Get project state manager
                project_state = self.top_toolbar.project_state
                
                # Clear existing projects
                project_state.projects = {}
                
                # Restore each project
                from Manage2.project_state import ProjectData
                for project_id_str, project_dict in projects_data.items():
                    try:
                        project = ProjectData.from_dict(project_dict)
                        project_state.projects[project.id] = project
                        print(f"[ManageNative] ✓ Restored project: {project.name} (ID: {project.id})")
                    except Exception as e:
                        print(f"[ManageNative] ERROR restoring project {project_id_str}: {e}")
                
                # Restore next_project_id and active_project_id
                if 'next_project_id' in doc:
                    project_state.next_project_id = doc['next_project_id']
                if 'active_project_id' in doc:
                    project_state.active_project_id = doc['active_project_id']
                
                # Refresh Layer menu
                self.top_toolbar.refresh_projects_list()
                
                print(f"[ManageNative] ✓ Restored {len(project_state.projects)} projects to Layer menu")
            
            # Clear canvas first
            self.manage.canvas.clear()
            
            # Check if there's a "whole_file" view saved (new format)
            whole_file_data = doc.get('whole_file')
            if whole_file_data:
                print(f"[ManageNative] Found 'whole_file' view, loading as default")
                nodes_data = whole_file_data.get('nodes', [])
            else:
                # Fall back to old format (nodes at root level)
                nodes_data = doc.get('nodes', [])
                if nodes_data:
                    print(f"[ManageNative] No 'whole_file' view found, loading root nodes")
                else:
                    print(f"[ManageNative] No 'whole_file' view and no root nodes - canvas will be empty")
            
            if nodes_data:
                print(f"[ManageNative] Loading {len(nodes_data)} nodes from file")
                
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
                        self.manage.canvas.nodes.append(node)
                        
                        # Index the node
                        if hasattr(self.manage.canvas, '_index_node'):
                            self.manage.canvas._index_node(node)
                        
                        print(f"[ManageNative] ✓ Loaded node: {node.name}")
                    except Exception as e:
                        print(f"[ManageNative] ERROR loading node: {e}")
                        import traceback
                        traceback.print_exc()
                
                # Apply viewport and other settings
                # Use whole_file data if available, otherwise use root doc
                canvas_data = whole_file_data if whole_file_data else doc
                save_manager.apply_to_canvas(self.manage.canvas, canvas_data)
                
                # Update canvas
                self.manage.canvas.update()
                
                print(f"[ManageNative] ✓ Loaded {len(self.manage.canvas.nodes)} nodes from: {file_path}")
            
            # Show success message
            num_projects = len(projects_data)
            num_nodes = len(nodes_data)
            has_whole_file = whole_file_data is not None
            
            # Show custom success dialog
            from Manage2.project_dialogs import LoadSuccessDialog
            success_dialog = LoadSuccessDialog(
                num_projects,
                num_nodes,
                has_whole_file,
                self
            )
            success_dialog.exec()
            
        except Exception as e:
            print(f"[ManageNative] Error loading layout: {e}")
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "Error", f"Failed to load project:\n{e}")
    
    def _save_current_project_state(self):
        """Save current project state without showing dialog"""
        try:
            project_state = self.top_toolbar.project_state
            active_project = project_state.get_active_project()
            
            if active_project:
                from Manage.document_io import SaveLoadManager
                save_manager = SaveLoadManager()
                canvas_state = save_manager.collect_state(self.manage)
                project_state.update_project_canvas(active_project.id, canvas_state)
                print(f"[ManageNative] Saved state for project: {active_project.name}")
        except Exception as e:
            print(f"[ManageNative] Error saving project state: {e}")
    
    def _load_project_canvas(self, project_id: int):
        """Load canvas state for a project"""
        try:
            print(f"\n{'='*80}")
            print(f"[ManageNative] _load_project_canvas called for project ID: {project_id}")
            
            # Get project state manager from toolbar
            project_state = self.top_toolbar.project_state
            
            # Set as active
            project_state.set_active_project(project_id)
            
            # Get project
            project = project_state.get_project(project_id)
            if not project:
                print(f"[ManageNative] ERROR: Project {project_id} not found")
                return
            
            print(f"[ManageNative] Loading project: {project.name} (ID: {project.id})")
            print(f"[ManageNative] Project canvas_state exists: {project.canvas_state is not None}")
            if project.canvas_state:
                print(f"[ManageNative] Project has {len(project.canvas_state.get('nodes', []))} saved nodes")
            
            # Clear current canvas
            print(f"[ManageNative] Clearing canvas...")
            self.manage.canvas.clear()
            
            # Load canvas state if available
            if project.canvas_state and project.canvas_state.get('nodes'):
                nodes_to_load = project.canvas_state.get('nodes', [])
                print(f"[ManageNative] Loading {len(nodes_to_load)} nodes for project: {project.name}")
                
                # Recreate nodes from saved state
                from Manage.data_analysis import FunctionNode
                for idx, node_data in enumerate(nodes_to_load):
                    try:
                        node_name = node_data.get('name', '')
                        node_x = node_data.get('x', 0.0)
                        node_y = node_data.get('y', 0.0)
                        print(f"[ManageNative] Node {idx+1}: {node_name} at ({node_x}, {node_y})")
                        
                        # Create node from saved data with all fields
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
                        
                        # Add to canvas
                        self.manage.canvas.nodes.append(node)
                        
                        # Index the node
                        if hasattr(self.manage.canvas, '_index_node'):
                            self.manage.canvas._index_node(node)
                        
                        print(f"[ManageNative] ✓ Recreated node: {node.name}")
                    except Exception as e:
                        print(f"[ManageNative] ERROR recreating node: {e}")
                        import traceback
                        traceback.print_exc()
                
                print(f"[ManageNative] Total nodes in canvas after loading: {len(self.manage.canvas.nodes)}")
                
                # Apply viewport settings
                from Manage.document_io import SaveLoadManager
                save_manager = SaveLoadManager()
                save_manager.apply_to_canvas(self.manage.canvas, project.canvas_state)
                
                # Update canvas
                self.manage.canvas.update()
                print(f"[ManageNative] ✓ Canvas updated")
            else:
                print(f"[ManageNative] No nodes to load for project: {project.name}")
            
            # Refresh projects list
            self.top_toolbar.refresh_projects_list()
            
            print(f"[ManageNative] ✓ Loaded canvas for project: {project.name}")
            print(f"{'='*80}\n")
        except Exception as e:
            print(f"[ManageNative] ERROR loading project canvas: {e}")
            import traceback
            traceback.print_exc()

    # ----------------------- Setup helpers -----------------------
    def _get_project_root(self) -> str:
        try:
            # Use where this file lives as project root
            return os.path.dirname(os.path.abspath(__file__))
        except Exception:
            return os.getcwd()
    
    def _get_last_folder_from_settings(self) -> Optional[str]:
        """Load the last opened folder from settings file"""
        try:
            import json
            settings_dir = os.path.join(
                os.environ.get('LOCALAPPDATA') or os.environ.get('APPDATA') or os.path.expanduser("~"),
                "A3PyEditor"
            )
            settings_file = os.path.join(settings_dir, "settings.json")
            
            if os.path.exists(settings_file):
                with open(settings_file, 'r') as f:
                    settings = json.load(f)
                    last_folder = settings.get('last_folder', '').strip()
                    if last_folder and os.path.isdir(last_folder):
                        return last_folder
        except Exception:
            pass
        return None

    def _open_helper_panels(self):
        # Toggle Details panel on
        try:
            self.manage.details_btn.setChecked(True)
            self.manage.toggle_panel_visibility()
        except Exception:
            pass
        # Toggle Stats panel on (only one panel visible at a time, so flip after a short delay)
        QTimer.singleShot(150, self._show_stats_panel)

    def _show_stats_panel(self):
        try:
            self.manage.stats_btn.setChecked(True)
            self.manage.toggle_panel_visibility()
        except Exception:
            pass

    # ----------------------- Loading logic -----------------------
    def _auto_load(self, initial_file: Optional[str]):
        """Attempt to load a sensible default target file.
        Preference:
          1) CLI-provided file path
          2) ./ai_chat.py if present
          3) Ask user to select a .py file
          4) Load sample data
        """
        project_root = self._get_project_root()

        def is_python_file(path: str) -> bool:
            return path.lower().endswith(".py") and os.path.exists(path)

        candidate = None
        if initial_file and is_python_file(os.path.abspath(initial_file)):
            candidate = os.path.abspath(initial_file)
        else:
            ai_chat_path = os.path.join(project_root, "ai_chat.py")
            if os.path.exists(ai_chat_path):
                candidate = ai_chat_path

        if candidate and os.path.exists(candidate):
            self._load_and_prepare(candidate)
            return

        # Let user choose a file
        chosen, _ = QFileDialog.getOpenFileName(
            self,
            "Select Python file to analyze",
            project_root,
            "Python Files (*.py)"
        )
        if chosen and os.path.exists(chosen):
            self._load_and_prepare(chosen)
            return

        # As a last resort, load sample data
        self.manage.load_sample_data()
        QMessageBox.information(
            self,
            "Sample Loaded",
            "No Python file selected. Loaded sample code for demonstration."
        )

    def _load_and_prepare(self, file_path: str):
        """Load target file in ManageWidget, then try to open the usage viewer if a main script is detected."""
        try:
            self.manage.load_file(file_path)
        except Exception as e:
            QMessageBox.critical(self, "Load Error", f"Failed to load file:\n{file_path}\n\n{e}")
            return

        # If a main script (like safe.py) is detected, open the usage viewer automatically
        QTimer.singleShot(350, self._try_open_usage_viewer)

        # After the canvas is populated, check and show main-script warning and highlight
        QTimer.singleShot(450, self._maybe_show_main_warning)

    def _try_open_usage_viewer(self):
        """If the visualization created a main script node (python icon), open its usage view."""
        try:
            canvas = self.manage.canvas
            if not hasattr(canvas, "nodes") or not canvas.nodes:
                return

            main_node = next((n for n in canvas.nodes if getattr(n, "icon_path", None) and "python" in str(n.icon_path).lower()), None)
            if main_node is None:
                # No main script detected; offer a short hint
                if getattr(self.manage, "current_data", None):
                    QMessageBox.information(
                        self,
                        "Analysis Complete",
                        "No main script (e.g., safe.py) was detected using this module.\n"
                        "You can still explore connections by double-clicking function bubbles."
                    )
                return

            # Show how functions from this file are used in the detected main script
            self.manage.show_function_usage_viewer(main_node)
        except Exception:
            # Fail silently to keep UX clean; users can still double-click manually
            pass

    def _maybe_show_main_warning(self):
        """Show a red warning box and highlight the main script node if current file isn't the main script."""
        try:
            current_path = getattr(self.manage.analyzer, 'current_file_path', None)
            resolve = getattr(self.manage, '_resolve_main_script_path', None)
            main_path = resolve() if callable(resolve) else None
            print(f"[ManageNative] _maybe_show_main_warning: current={current_path} main={main_path}")

            # Fallback: if we couldn't resolve, try common main script names in current dir and project root
            if not main_path and current_path:
                candidates = ['safe.py', 'main.py', 'app.py', '__main__.py', 'run.py', 'start.py']
                cur_dir = os.path.dirname(current_path)
                for c in candidates:
                    p = os.path.join(cur_dir, c)
                    if os.path.exists(p):
                        main_path = p
                        break
                if not main_path:
                    try:
                        root = self._get_project_root()
                        for c in candidates:
                            p = os.path.join(root, c)
                            if os.path.exists(p):
                                main_path = p
                                break
                    except Exception:
                        pass

            if not current_path or not main_path:
                self._hide_main_warning()
                return

            # If we are analyzing the main script itself, no warning
            if os.path.abspath(current_path) == os.path.abspath(main_path):
                self._hide_main_warning()
                return

            # Otherwise, show warning and highlight the main node
            self._highlight_main_node_red()
            self._show_main_warning_box(os.path.basename(main_path))
        except Exception:
            # Keep UX clean if any error occurs
            self._hide_main_warning()
            return

    def _highlight_main_node_red(self):
        """Change the main script node color to a red tone as a visual cue."""
        try:
            canvas = self.manage.canvas
            if not hasattr(canvas, 'nodes'):
                return
            main_node = next((n for n in canvas.nodes if getattr(n, 'icon_path', None) and 'python' in str(n.icon_path).lower()), None)
            if main_node:
                main_node.color = '#D16969'  # Red (matches DARK_THEME['error'])
                canvas.update()
        except Exception:
            pass

    def _maybe_show_main_warning_for(self, current_path: Optional[str]):
        """Same as _maybe_show_main_warning, but for an explicit current_path (used when running a file)."""
        try:
            print(f"[ManageNative] _maybe_show_main_warning_for: current={current_path}")
            resolve = getattr(self.manage, '_resolve_main_script_path', None)
            main_path = resolve() if callable(resolve) else None

            # Fallback: if we couldn't resolve, try common main script names in current dir and project root
            if not main_path and current_path:
                candidates = ['safe.py', 'main.py', 'app.py', '__main__.py', 'run.py', 'start.py']
                cur_dir = os.path.dirname(current_path)
                for c in candidates:
                    p = os.path.join(cur_dir, c)
                    if os.path.exists(p):
                        main_path = p
                        break
                if not main_path:
                    try:
                        root = self._get_project_root()
                        for c in candidates:
                            p = os.path.join(root, c)
                            if os.path.exists(p):
                                main_path = p
                                break
                    except Exception:
                        pass

            if not current_path or not main_path:
                self._hide_main_warning()
                return

            # If we are analyzing the main script itself, no warning
            if os.path.abspath(current_path) == os.path.abspath(main_path):
                self._hide_main_warning()
                return

            # Otherwise, show warning and highlight the main node
            self._highlight_main_node_red()
            self._show_main_warning_box(os.path.basename(main_path))
        except Exception:
            # Keep UX clean if any error occurs
            self._hide_main_warning()
            return

    def _build_warning_box(self):
        """Create the warning overlay box widget."""
        box = QFrame(self.manage.canvas)
        # Make overlay float above other panels (which use Qt.SubWindow)
        try:
            box.setWindowFlags(Qt.SubWindow | Qt.FramelessWindowHint)
        except Exception:
            pass
        box.setStyleSheet("""
            QFrame { 
                background-color: #A12126; /* solid red tint */
                border: 1px solid #D16969; 
                border-radius: 10px; 
            }
            QLabel { color: #F5F5F5; background-color: transparent; }
            QPushButton { background: transparent; color: #F5F5F5; border: none; font-size: 16px; }
            QPushButton:hover { color: #FFFFFF; }
        """)
        layout = QHBoxLayout(box)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(8)

        # Icon
        icon_label = QLabel()
        try:
            icon = QIcon("img/Manage_Python.png")
            pix = icon.pixmap(48, 48)
            icon_label.setPixmap(pix)
        except Exception:
            pass
        layout.addWidget(icon_label)

        # Texts
        text_container = QWidget()
        v = QVBoxLayout(text_container)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(3)

        self._warning_title = QLabel("Module loaded")
        self._warning_title.setStyleSheet("font-weight: bold; font-size: 14px;")
        self._warning_body = QLabel("")
        self._warning_body.setWordWrap(True)

        v.addWidget(self._warning_title)
        v.addWidget(self._warning_body)
        layout.addWidget(text_container, 1)

        # Close button
        close_btn = QPushButton("✕")
        close_btn.clicked.connect(self._hide_main_warning)
        layout.addWidget(close_btn)

        # Position and size
        box.resize(420, 90)
        box.move(120, 120)
        box.hide()
        return box

    def _show_main_warning_box(self, main_script_basename: str):
        """Populate and show the warning overlay."""
        if self._warning_box is None:
            self._warning_box = self._build_warning_box()
        self._warning_title.setText("Run the main script")
        self._warning_body.setText(
            f"This file is a module of the application. To start the app, run {main_script_basename}."
        )
        # Position top-right to avoid overlapping the Python Preview panel
        try:
            margin = 30
            x = max(10, self.manage.canvas.width() - self._warning_box.width() - margin)
            y = 60
            print(f"[ManageNative] _show_main_warning_box: pos=({x},{y}) canvas=({self.manage.canvas.width()}x{self.manage.canvas.height()}) box=({self._warning_box.width()}x{self._warning_box.height()})")
            self._warning_box.move(x, y)
        except Exception:
            pass
        self._warning_box.show()
        self._warning_box.raise_()

    def _hide_main_warning(self):
        if self._warning_box and self._warning_box.isVisible():
            self._warning_box.hide()

    def eventFilter(self, obj, event):
        try:
            if event.type() == QEvent.ShortcutOverride:
                # Ctrl+F opens Manage search box
                if (event.modifiers() & Qt.ControlModifier) and event.key() == Qt.Key_F:
                    try:
                        if hasattr(self.manage, 'trigger_search'):
                            self.manage.trigger_search()
                        else:
                            self.manage.show_search_box()
                    except Exception:
                        pass
                    event.accept()
                    return True
                # F3 / Shift+F3 navigate
                if event.key() == Qt.Key_F3:
                    try:
                        if event.modifiers() & Qt.ShiftModifier:
                            if hasattr(self.manage, 'search_prev'):
                                self.manage.search_prev()
                        else:
                            if hasattr(self.manage, 'search_next'):
                                self.manage.search_next()
                    except Exception:
                        pass
                    event.accept()
                    return True
        except Exception:
            pass
        return super().eventFilter(obj, event)
    
    def resizeEvent(self, event):
        """Reposition toolbar on window resize"""
        super().resizeEvent(event)
        if hasattr(self, 'top_toolbar'):
            self.top_toolbar.position_toolbar(
                self.manage.canvas.width(),
                self.manage.canvas.height()
            )
    
    def closeEvent(self, event):
        """Handle window close - no unsaved changes check since we use file-based save/load"""
        # Since Save A3 Project and Load A3 Project now work like Save Layout and Open Layout
        # (file-based operations), we don't need to check for unsaved changes in projects.json
        event.accept()


def main():
    # Build QApplication once
    app = QApplication.instance() or QApplication(sys.argv)

    # Optional CLI parameter: file to analyze
    initial_file = None
    if len(sys.argv) > 1:
        potential = sys.argv[1]
        if os.path.exists(potential) and potential.lower().endswith(".py"):
            initial_file = potential

    window = ManageNativeWindow(initial_file=initial_file)
    window.resize(1200, 800)
    window.show()

    # Start event loop
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
