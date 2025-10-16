"""
Project Manager - Add Project Feature
======================================

This module orchestrates the "Add Project" workflow:
1. User clicks "Add Project" → start_add_project()
2. File selection dialog → on_files_selected()
3. Add Tool node created → create_add_node()
4. User double-clicks Add Tool → on_add_function_requested()
5. Function selection dialog → on_function_selected()
6. Function node created, Add Tool removed

Key Concepts:
- Add Tool Node: Special node with border + icon only (no 3D background)
- Marked by: node.is_add_tool = True
- Double-click triggers function selection dialog
- After selection, Add Tool is replaced with actual function node

See: Manage2/README_ADD_PROJECT.md for full documentation
"""

import os
from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QWidget

from Manage2.project_dialogs import FileSelectionDialog, FunctionSelectionDialog
from Manage.data_analysis import FunctionNode


class ProjectManager(QObject):
    """
    Manages the Add Project workflow for adding custom Rust functions to the canvas.
    
    Attributes:
        parent_window: Main window reference (for dialog parent)
        canvas: VisualizationCanvas instance where nodes are displayed
        root_path: Root directory for file browsing
        selected_files: List of .rs file paths selected by user
        add_node: Reference to the current Add Tool node (if any)
    """
    
    def __init__(self, parent_window, canvas, root_path=None):
        super().__init__()
        self.parent_window = parent_window
        self.canvas = canvas  # VisualizationCanvas from visualization_core.py
        self.initial_root_path = root_path  # Store initial path as fallback
        self.selected_files = []  # Stores selected .rs files
        self.add_node = None  # Reference to Add Tool node
        self._dialog_open = False  # Prevent double-opening dialogs
    
    def get_current_root_path(self):
        """
        Get the current root path from the file browser dynamically.
        This ensures the file selection dialog opens in the currently browsed folder.
        
        Returns:
            str: Current root path from file browser, or initial_root_path as fallback
        """
        try:
            # Try multiple paths to find the file browser
            # Path 1: Direct access (for Rust.py main window)
            if hasattr(self.parent_window, 'tree_view') and hasattr(self.parent_window, 'file_model'):
                proxy_model = getattr(self.parent_window, 'proxy_model', None)
                if proxy_model:
                    src_idx = proxy_model.mapToSource(self.parent_window.tree_view.rootIndex())
                    root_path = self.parent_window.file_model.filePath(src_idx)
                    if root_path and os.path.isdir(root_path):
                        print(f"[ProjectManager] Got root from parent_window: {root_path}")
                        return root_path
            
            # Path 2: Via manage widget (for manage_native.py wrapper)
            if hasattr(self.parent_window, 'manage'):
                manage = self.parent_window.manage
                if hasattr(manage, 'file_model') and hasattr(manage, 'tree_view'):
                    try:
                        proxy_model = getattr(manage, 'proxy_model', None)
                        if proxy_model:
                            src_idx = proxy_model.mapToSource(manage.tree_view.rootIndex())
                            root_path = manage.file_model.filePath(src_idx)
                            if root_path and os.path.isdir(root_path):
                                print(f"[ProjectManager] Got root from manage widget: {root_path}")
                                return root_path
                    except Exception as e:
                        print(f"[ProjectManager] Error getting root from manage: {e}")
            
            # Path 3: Check if parent_window has a method to get root path
            if hasattr(self.parent_window, 'get_current_root_path'):
                root_path = self.parent_window.get_current_root_path()
                if root_path and os.path.isdir(root_path):
                    print(f"[ProjectManager] Got root from method: {root_path}")
                    return root_path
                    
        except Exception as e:
            print(f"[ProjectManager] Error getting current root path: {e}")
            import traceback
            traceback.print_exc()
        
        # Final fallback: use initial root path
        fallback = self.initial_root_path or os.getcwd()
        print(f"[ProjectManager] Using fallback root: {fallback}")
        return fallback
        
    def start_add_project(self):
        """
        STEP 1: Start the Add Project workflow
        
        Opens a file selection dialog for the user to choose Rust files (.rs).
        When files are selected, triggers on_files_selected() via signal.
        
        Called by: Main window's _on_menu_action() when "Add Project" is clicked
        Next step: on_files_selected() when user selects files
        """
        # Prevent double-opening
        if self._dialog_open:
            return
        
        try:
            self._dialog_open = True
            
            # Get current root path dynamically from file browser
            current_root = self.get_current_root_path()
            print(f"[ProjectManager] Opening file dialog with root: {current_root}")
            
            # Create and show file selection dialog with current root
            file_dialog = FileSelectionDialog(current_root, self.parent_window)
            
            # Connect signal: when files are selected, call on_files_selected()
            file_dialog.files_selected.connect(self.on_files_selected)
            
            # Show dialog (blocks until user clicks OK or Cancel)
            file_dialog.exec()
        except Exception as e:
            print(f"[ProjectManager] Error in start_add_project: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self._dialog_open = False
    
    def on_files_selected(self, file_paths):
        """
        STEP 2: Handle files selected from dialog
        
        Stores selected files and creates the Add Tool node in the center of canvas.
        The Add Tool is a special node that shows only border + icon (no 3D background).
        
        Args:
            file_paths: List of absolute paths to selected .rs files
            
        Called by: FileSelectionDialog via files_selected signal
        Next step: User double-clicks Add Tool → on_add_function_requested()
        """
        # Store selected files for later use in function selection
        self.selected_files = file_paths
        
        # IMPORTANT: Save current project state before clearing canvas
        # This ensures we don't lose the current project's nodes
        if hasattr(self.parent_window, 'top_toolbar'):
            try:
                project_state = self.parent_window.top_toolbar.project_state
                active_project = project_state.get_active_project()
                
                # Only save if there's an active project with nodes (excluding Add Tool)
                real_nodes = [n for n in self.canvas.nodes if not getattr(n, 'is_add_tool', False)]
                
                if active_project and len(real_nodes) > 0:
                    from Manage.document_io import SaveLoadManager
                    save_manager = SaveLoadManager()
                    manage_widget = getattr(self.parent_window, 'manage_widget', None)
                    if manage_widget:
                        canvas_state = save_manager.collect_state(manage_widget)
                        project_state.update_project_canvas(active_project.id, canvas_state)
                        
                        # Clear active project so a new one will be created
                        project_state.active_project_id = None
            except Exception:
                pass
        
        # Clear canvas to show only the Add Tool
        self.canvas.clear()
        
        # Create the Add Tool node (border + icon only)
        self.create_add_node()
    
    def create_add_node(self):
        """
        Create the Add Tool node in the center of the canvas
        
        The Add Tool is a special node that:
        - Shows only border + Add.png icon (no 3D background)
        - Is marked with is_add_tool = True flag
        - When double-clicked, opens function selection dialog
        - Gets replaced by actual function node after selection
        
        Rendering: See _draw_node() in visualization_core2.py
        """
        # Create node data (standard FunctionNode format)
        data = {
            'name': 'Add Function',
            'lineno': 0,
            'args': [],
            'docstring': 'Double-click to add a custom Rust function',
            'returns': '',
            'complexity': 1
        }
        
        # Position at world origin (center of canvas)
        x = 0.0
        y = 0.0
        
        # Create FunctionNode instance
        node = FunctionNode(data, x, y)
        node.icon_path = 'img/Add.png'  # Path to Add icon
        node.color = '#60A5FA'  # Blue color for border
        
        # IMPORTANT: Mark as Add Tool (enables special rendering)
        node.is_add_tool = True
        
        # Add to canvas nodes list
        self.canvas.nodes.append(node)
        self.add_node = node  # Keep reference for later removal
        
        # Index the node for lookups
        if hasattr(self.canvas, '_index_node'):
            self.canvas._index_node(node)
        
        # Center camera on the Add Tool
        self.canvas.reset_view()
        self.canvas.update()  # Trigger repaint
    
    def on_add_function_requested(self):
        """
        STEP 3: Handle Add Tool double-click
        
        Opens function selection dialog showing all functions/structs/impls
        from the previously selected Rust files.
        
        Called by: Main window's _on_node_double_clicked() when Add Tool is double-clicked
        Next step: on_function_selected() when user selects a function
        """
        # Prevent double-opening
        if self._dialog_open:
            return
        
        # Validate that files were selected in step 1
        if not self.selected_files:
            return
        
        try:
            self._dialog_open = True
            
            # Get existing node names from canvas to prevent duplicates
            existing_nodes = [node.name for node in self.canvas.nodes if not getattr(node, 'is_add_tool', False)]
            
            # Create function selection dialog with existing nodes filter
            func_dialog = FunctionSelectionDialog(self.selected_files, self.parent_window, existing_nodes)
            
            # Connect signal: when function is selected, call on_function_selected()
            func_dialog.function_selected.connect(self.on_function_selected)
            
            # Show dialog (blocks until user selects or cancels)
            func_dialog.exec()
        except Exception:
            pass
        finally:
            self._dialog_open = False
    
    def on_function_selected(self, name, func_type):
        """
        STEP 4: Handle function selection - create actual function node
        
        Removes the Add Tool node and creates a proper function node with:
        - 3D gradient background (unlike Add Tool which has no background)
        - Function name displayed
        - Cyan color (#4FC3F7) for Rust functions
        
        Args:
            name: Function/struct/impl name selected by user
            func_type: Type of item ("Function", "Struct", "Implementation")
            
        Called by: FunctionSelectionDialog via function_selected signal
        Result: Add Tool disappears, function node appears in same position
        """
        # STEP 4A: Auto-create Project 1 if no projects exist (delayed to ensure toolbar is ready)
        from PySide6.QtCore import QTimer
        QTimer.singleShot(300, lambda: self._create_project_if_needed())
        
        # STEP 4B: Remove the Add Tool node
        if self.add_node and self.add_node in self.canvas.nodes:
            try:
                # Remove from nodes list
                self.canvas.nodes.remove(self.add_node)
                
                # Remove from name index
                if hasattr(self.canvas, '_node_by_name'):
                    self.canvas._node_by_name.pop(self.add_node.name.lower(), None)
            except Exception:
                pass
        
        # STEP 4B: Find the source file for this function
        source_file = None
        source_code = None
        try:
            import re
            # Search through selected files to find the function
            for file_path in self.selected_files:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                    # Handle "impl Name" format (remove "impl " prefix for matching)
                    search_name = name
                    if name.startswith('impl '):
                        search_name = name[5:].strip()  # Remove "impl " prefix
                    
                    # Use regex for more precise matching
                    # Match: fn, struct, enum, trait, impl, type, const, mod
                    patterns = [
                        rf'\bfn\s+{re.escape(search_name)}\b',
                        rf'\bstruct\s+{re.escape(search_name)}\b',
                        rf'\benum\s+{re.escape(search_name)}\b',
                        rf'\btrait\s+{re.escape(search_name)}\b',
                        rf'\bimpl\s+{re.escape(search_name)}\b',
                        rf'\bimpl\s+\w+\s+for\s+{re.escape(search_name)}\b',  # impl Trait for Type
                        rf'\btype\s+{re.escape(search_name)}\b',
                        rf'\bconst\s+{re.escape(search_name)}\b',
                        rf'\bmod\s+{re.escape(search_name)}\b'
                    ]
                    
                    found = False
                    for pattern in patterns:
                        if re.search(pattern, content):
                            found = True
                            break
                    
                    if found:
                        source_file = file_path
                        
                        # Extract the function/struct/impl code
                        lines = content.split('\n')
                        for i, line in enumerate(lines):
                            # Check if this line contains the declaration
                            match_found = False
                            for pattern in patterns:
                                if re.search(pattern, line):
                                    match_found = True
                                    break
                            
                            if match_found:
                                # Find the end of the function/struct/impl
                                start = i
                                brace_count = 0
                                found_start = False
                                end = start
                                
                                # Look for opening brace
                                for j in range(start, len(lines)):
                                    if '{' in lines[j]:
                                        brace_count += lines[j].count('{')
                                        found_start = True
                                    if '}' in lines[j]:
                                        brace_count -= lines[j].count('}')
                                    
                                    # Stop when we've closed all braces
                                    if found_start and brace_count == 0:
                                        end = j
                                        break
                                    
                                    # Safety: don't go beyond 1000 lines
                                    if j - start > 1000:
                                        end = j
                                        break
                                
                                source_code = '\n'.join(lines[start:end+1])
                                break
                        break
        except Exception as e:
            print(f"[ProjectManager] Error extracting source code: {e}")
        
        # STEP 4C: Create function node data
        data = {
            'name': name,
            'lineno': 0,
            'args': [],
            'docstring': f'{func_type} from Rust file',
            'returns': '',
            'complexity': 1,
            'type': func_type,
            'file_path': source_file,  # Store file path for code viewer
            'source_code': source_code  # Store extracted code
        }
        
        # STEP 4D: Position at same location as Add Tool
        x = self.add_node.x if self.add_node else 0.0
        y = self.add_node.y if self.add_node else 0.0
        
        # STEP 4E: Create the function node with random color
        # NOTE: This node does NOT have is_add_tool flag, so it renders with 3D background
        node = FunctionNode(data, x, y)
        
        # Generate random color for the node border
        import random
        colors = [
            '#4FC3F7',  # Cyan
            '#66BB6A',  # Green
            '#FFA726',  # Orange
            '#AB47BC',  # Purple
            '#EF5350',  # Red
            '#42A5F5',  # Blue
            '#FFCA28',  # Yellow
            '#26A69A',  # Teal
            '#EC407A',  # Pink
            '#7E57C2',  # Deep Purple
        ]
        node.color = random.choice(colors)
        
        # STEP 4F: Add to canvas
        self.canvas.nodes.append(node)
        
        # STEP 4G: Index the node for lookups
        if hasattr(self.canvas, '_index_node'):
            self.canvas._index_node(node)
        
        # STEP 4H: Clear Add Tool reference
        self.add_node = None
        
                
        # STEP 4J: Trigger canvas repaint
        self.canvas.update()
    
    def _create_project_if_needed(self):
        """Helper method to create project if needed (called with delay to ensure toolbar is ready)"""
        try:
            if not hasattr(self.parent_window, 'top_toolbar'):
                return
            
            project_state = self.parent_window.top_toolbar.project_state
            all_projects = project_state.get_all_projects()
            active_project = project_state.get_active_project()
            
            # Simplified logic:
            # 1. If no projects exist, create Project 1
            # 2. If no active project, create a new project
            # 3. If active project exists, use it (it was already saved in on_files_selected)
            
            should_create_new = False
            project_name = None
            
            if len(all_projects) == 0:
                # No projects exist - create Project 1
                should_create_new = True
                project_name = "Project 1"
            elif active_project is None:
                # No active project - create a new one
                # Find the next available project number
                existing_numbers = []
                for p in all_projects:
                    if p.name.startswith("Project "):
                        try:
                            num = int(p.name.replace("Project ", ""))
                            existing_numbers.append(num)
                        except:
                            pass
                
                next_num = max(existing_numbers) + 1 if existing_numbers else 1
                project_name = f"Project {next_num}"
                should_create_new = True
            
            if should_create_new:
                # Create new project
                project = project_state.create_project(project_name)
                
                # Set as active
                project_state.set_active_project(project.id)
                
                # Refresh projects list
                self.parent_window.top_toolbar.refresh_projects_list()
            
            # Always save the current canvas state to the active project
            active_project = project_state.get_active_project()
            if active_project:
                from Manage.document_io import SaveLoadManager
                save_manager = SaveLoadManager()
                # Try both 'manage' and 'manage_widget' attribute names
                manage_widget = getattr(self.parent_window, 'manage', None) or getattr(self.parent_window, 'manage_widget', None)
                if manage_widget:
                    canvas_state = save_manager.collect_state(manage_widget)
                    project_state.update_project_canvas(active_project.id, canvas_state)
                    self.parent_window.top_toolbar.refresh_projects_list()
                
        except Exception:
            pass
