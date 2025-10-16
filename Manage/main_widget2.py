





"""
Main Widget 2 Module
Contains additional methods for ManageWidget
"""

import os
import sys
from typing import Optional
from PySide6.QtWidgets import QMessageBox, QFrame, QWidget, QLabel, QPushButton, QHBoxLayout, QVBoxLayout
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon


def load_file(self, file_path: str):
    """Load and analyze a Python file"""
    try:
        # Capture current file's layout into the session cache before switching
        try:
            self._capture_session_for_current()
        except Exception:
            pass
        # --- FIX: Ensure the file path is absolute ---
        file_path = os.path.abspath(file_path)
        # Keep existing file browser root; only select the opened file in the tree
        try:
            self._select_in_file_tree(file_path)
        except Exception:
            pass
        
        # ✅ CLEAR THE CANVAS BEFORE LOADING NEW FILE
        # This ensures old file's nodes don't remain visible
        try:
            self.canvas.clear()
        except Exception:
            pass
        
        with open(file_path, 'r', encoding='utf-8') as f:
            code = f.read()
        
        # Find main script that might use this file
        main_script_name = self.find_main_script(file_path)
        
        # Preserve current view to avoid zoom-out on reload
        prev_view = None
        try:
            prev_view = (self.canvas.camera_x, self.canvas.camera_y, self.canvas.camera_zoom)
        except Exception:
            prev_view = None
        # --- FIX: Pass the full path to analyze_code ---
        self.analyze_code(code, file_path, main_script_name)
        # Restore previous view if available
        if prev_view is not None:
            try:
                self.canvas.camera_x, self.canvas.camera_y, self.canvas.camera_zoom = prev_view
                self.canvas.update()
            except Exception:
                pass
        
    except Exception as e:
        QMessageBox.critical(self, "File Error", f"Failed to load file: {str(e)}")

def find_main_script(self, file_path: str) -> Optional[str]:
    """Find the main script that uses functions from the current file"""
    directory = os.path.dirname(file_path)
    current_filename = os.path.basename(file_path)
    current_module_name = os.path.splitext(current_filename)[0]
    
    # First, check standard main script names in the same directory
    main_script_candidates = ['safe.py', 'main.py', 'app.py', '__main__.py', 'run.py', 'start.py']
    
    for candidate in main_script_candidates:
        candidate_path = os.path.join(directory, candidate)
        if os.path.exists(candidate_path) and candidate_path != file_path:
            # Check if this main script actually uses the current file
            if self.file_imports_module(candidate_path, current_module_name, current_filename):
                return candidate
    
    # If no standard main script found in same directory, look for any Python file that imports this one
    try:
        for filename in os.listdir(directory):
            if filename.endswith('.py') and filename != current_filename:
                potential_main = os.path.join(directory, filename)
                if self.file_imports_module(potential_main, current_module_name, current_filename):
                    return filename
    except OSError:
        pass
    
    # NEW: If no main script found in same directory, check the project root directory
    # This handles cases where files are in different folders
    project_root = self.get_project_root_directory()
    if project_root and project_root != directory:
        for candidate in main_script_candidates:
            candidate_path = os.path.join(project_root, candidate)
            if os.path.exists(candidate_path):
                # For cross-directory imports, we need to check more flexible patterns
                if self.file_imports_module_flexible(candidate_path, current_module_name, current_filename, file_path):
                    return f"../{candidate}"  # Indicate it's in parent directory
    
    return None

def get_project_root_directory(self) -> Optional[str]:
    """Get the project root directory (where the main application files are)"""
    # Prefer an override set when loading a file
    try:
        if getattr(self, '_project_root_override', None):
            return self._project_root_override
    except Exception:
        pass
    # Fallback to the original behavior
    try:
        return os.path.dirname(os.path.abspath(__file__)).replace('\\Manage', '')
    except Exception:
        return None

def file_imports_module_flexible(self, file_path: str, module_name: str, module_filename: str, target_file_path: str) -> bool:
    """Check if a file imports or uses the specified module with flexible path handling"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        import re
        
        # Get relative path information
        file_dir = os.path.dirname(file_path)
        target_dir = os.path.dirname(target_file_path)
        
        # Check for various import patterns including relative paths
        patterns = [
            rf'from\s+{re.escape(module_name)}\s+import',  # from module import
            rf'import\s+{re.escape(module_name)}',         # import module
            rf'from\s+\.?\s*{re.escape(module_name)}\s+import',  # from .module import
            rf'import\s+\.?\s*{re.escape(module_name)}',   # import .module
            rf'{re.escape(module_filename)}',              # direct filename reference
            # Add patterns for subdirectory imports
            rf'from\s+\w+\.{re.escape(module_name)}\s+import',  # from subdir.module import
            rf'import\s+\w+\.{re.escape(module_name)}',         # import subdir.module
        ]
        
        for pattern in patterns:
            if re.search(pattern, content, re.MULTILINE):
                return True
        
        return False
        
    except Exception:
        return False

def file_imports_module(self, file_path: str, module_name: str, module_filename: str) -> bool:
    """Check if a file imports or uses the specified module"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        import re
        
        # Check for various import patterns
        patterns = [
            rf'from\s+{re.escape(module_name)}\s+import',  # from module import
            rf'import\s+{re.escape(module_name)}',         # import module
            rf'from\s+\.?\s*{re.escape(module_name)}\s+import',  # from .module import
            rf'import\s+\.?\s*{re.escape(module_name)}',   # import .module
            rf'{re.escape(module_filename)}',              # direct filename reference
        ]
        
        for pattern in patterns:
            if re.search(pattern, content, re.MULTILINE):
                return True
        
        return False
        
    except Exception:
        return False

def toggle_panel_visibility(self):
    """Toggle visibility of panels based on button state (multiple panels allowed)."""
    sender = self.sender()
    
    # Map buttons to panels
    panel_map = {
        self.files_btn: self.file_panel,
        self.python_btn: self.Rust_panel
    }
    
    if sender not in panel_map:
        return
        
    target_panel = panel_map[sender]
    
    if sender.isChecked():
        # Show the selected panel without hiding others
        target_panel.show()
        target_panel.raise_()
        # Only set initial position if panel has never been shown before
        if target_panel.pos().x() == 0 and target_panel.pos().y() == 0:
            target_panel.move(100, 50)
        if hasattr(target_panel, 'minimized') and not target_panel.minimized:
            # Only resize if it's at default size
            if target_panel.width() < 100:
                target_panel.resize(400, 350)
    else:
        # Hide the panel if button is unchecked
        target_panel.hide()

def on_node_selected(self, node):
    """Handle node selection (details panel removed)"""
    pass

def on_node_double_clicked(self, node):
    """Handle node double click - open error location if present, else code/usage viewer"""
    # FIRST: Check if this is a custom content node (text/image/video)
    try:
        if hasattr(node, 'data') and isinstance(node.data, dict):
            content_type = node.data.get('content_type')
            if content_type in ('text', 'image', 'video'):
                # Handle custom content nodes
                if content_type == 'text':
                    # Open text editor for text content
                    text_content = node.data.get('text_content', '')
                    self.text_editor.set_text_content("Text Content", text_content, node)
                    
                    # Try to restore saved position first
                    try:
                        from .document_io import SaveLoadManager
                        mgr = SaveLoadManager()
                        state = self._session_layouts.get(os.path.abspath(self.analyzer.current_file_path)) if hasattr(self, '_session_layouts') else None
                        if state:
                            mgr.apply_panel_positions(self, state)
                    except Exception:
                        pass
                    
                    # If no saved position, use default position
                    if self.text_editor.pos().x() == 0 and self.text_editor.pos().y() == 0:
                        viewer_width = 500
                        viewer_height = 400
                        margin = 30
                        x = self.canvas.width() - viewer_width - margin
                        y = margin
                        self.text_editor.move(x, y + 50)
                        self.text_editor.resize(viewer_width, viewer_height)
                    
                    self.text_editor.show()
                    self.text_editor.raise_()
                    return
                elif content_type == 'image':
                    # Open image editor for image content
                    image_path = node.data.get('image_path', '')
                    self.image_editor.set_image_content("Image Content", image_path, node)
                    
                    # Try to restore saved position first
                    try:
                        from .document_io import SaveLoadManager
                        mgr = SaveLoadManager()
                        state = self._session_layouts.get(os.path.abspath(self.analyzer.current_file_path)) if hasattr(self, '_session_layouts') else None
                        if state:
                            mgr.apply_panel_positions(self, state)
                    except Exception:
                        pass
                    
                    # If no saved position, use default position
                    if self.image_editor.pos().x() == 0 and self.image_editor.pos().y() == 0:
                        viewer_width = 500
                        viewer_height = 450
                        margin = 30
                        x = self.canvas.width() - viewer_width - margin
                        y = margin
                        self.image_editor.move(x, y + 50)
                        self.image_editor.resize(viewer_width, viewer_height)
                    
                    self.image_editor.show()
                    self.image_editor.raise_()
                    return
                elif content_type == 'video':
                    # Open video editor for video content
                    video_path = node.data.get('video_path', '')
                    self.video_editor.set_video_content("Video Content", video_path, node)
                    
                    # Try to restore saved position first
                    try:
                        from .document_io import SaveLoadManager
                        mgr = SaveLoadManager()
                        state = self._session_layouts.get(os.path.abspath(self.analyzer.current_file_path)) if hasattr(self, '_session_layouts') else None
                        if state:
                            mgr.apply_panel_positions(self, state)
                    except Exception:
                        pass
                    
                    # If no saved position, use default position
                    if self.video_editor.pos().x() == 0 and self.video_editor.pos().y() == 0:
                        viewer_width = 600
                        viewer_height = 500
                        margin = 30
                        x = self.canvas.width() - viewer_width - margin
                        y = margin
                        self.video_editor.move(x, y + 50)
                        self.video_editor.resize(viewer_width, viewer_height)
                    
                    self.video_editor.show()
                    self.video_editor.raise_()
                    return
    except Exception:
        pass
    
    try:
        data = getattr(node, 'data', {}) or {}
        fp = data.get('file_path') or ''
        err_line = int(data.get('error_line') or 0)
        # If this node carries an error marker, jump to that file/line in the editor
        if fp and err_line > 0:
            self.on_canvas_request_open_editor(node, fp)
            return
    except Exception:
        pass
    # Check if this is a main script node (has python icon)
    if hasattr(node, 'icon_path') and node.icon_path and 'python' in node.icon_path:
        # This is a main script node - show function usage
        self.show_function_usage_viewer(node)
    else:
        # Regular function node - show function code
        self.show_function_code_viewer(node)

def show_function_code_viewer(self, node):
    """Show the code for a specific function"""
    # Ensure code viewer exists
    if not hasattr(self, 'code_viewer') or self.code_viewer is None:
        return
    
    # Check if this is a custom Rust node with source_code
    if hasattr(node, 'data') and isinstance(node.data, dict):
        source_code = node.data.get('source_code')
        file_path = node.data.get('file_path')
        item_type = node.data.get('type', 'Function')  # Get the type (Function, Struct, Implementation)
        
        if source_code:
            # This is a custom Rust function/struct/impl node - show its actual code
            title = f"{item_type}: {node.name}"
            self.code_viewer.set_code(title, source_code, highlight_line=0)
            
            # Only set default position if panel has never been positioned (at 0,0)
            if self.code_viewer.pos().x() == 0 and self.code_viewer.pos().y() == 0:
                viewer_width = 500
                viewer_height = 400
                margin = 30
                x = self.canvas.width() - viewer_width - margin
                y = margin
                self.code_viewer.move(x, y + 50)
                self.code_viewer.resize(viewer_width, viewer_height)
            
            self.code_viewer.show()
            self.code_viewer.raise_()
            return
    
    # Original Python code handling
    if not self.analyzer.current_code:
        return

    # --- Function body extraction robust to missing end_lineno ---
    lines = self.analyzer.current_code.split('\n')
    start_line = max(0, int(node.data.get('lineno', 1)) - 1)
    end_line = node.data.get('end_lineno')
    if not end_line:
        # Fallback: find next top-level def/class or end of file
        end = start_line + 1
        import re
        def_or_class = re.compile(r'^\s*(def|class)\s+')
        base_indent = len(lines[start_line]) - len(lines[start_line].lstrip(' '))
        while end < len(lines):
            line = lines[end]
            # New top-level def/class or lower/equal indentation than function start
            if def_or_class.match(line) and (len(line) - len(line.lstrip(' '))) <= base_indent:
                break
            end += 1
        end_line = end
    # Extract the function code
    function_lines = lines[start_line:end_line]
    function_code = '\n'.join(function_lines)

    # Compute base indentation for re-inserting snippet on save
    try:
        base_indent = len(lines[start_line]) - len(lines[start_line].lstrip(' '))
        base_indent = max(0, base_indent)
    except Exception:
        base_indent = 0
    # Provide source context so the viewer can save back to disk on Ctrl+S
    try:
        if hasattr(self.code_viewer, 'set_source_context'):
            self.code_viewer.set_source_context(self.analyzer.current_file_path, start_line, end_line, base_indent)
    except Exception:
        pass
    
    # Compute highlight position relative to function code if there's an error
    hl_rel = 0
    try:
        err_line_abs = int(node.data.get('error_line') or 0)
        if err_line_abs > 0:
            # Map absolute to relative (1-based)
            hl_rel = max(1, err_line_abs - start_line)
    except Exception:
        hl_rel = 0
    
    # Show in code viewer and highlight error line if available
    self.code_viewer.set_code(f"Function: {node.name}", function_code, highlight_line=hl_rel)
    
    # Try to restore saved position first
    position_restored = False
    try:
        from .document_io import SaveLoadManager
        mgr = SaveLoadManager()
        state = self._session_layouts.get(os.path.abspath(self.analyzer.current_file_path)) if hasattr(self, '_session_layouts') and self._session_layouts else None
        if state and state.get('panels', {}).get('code_viewer'):
            mgr.apply_panel_positions(self, state)
            position_restored = True
    except Exception:
        pass
    
    # If no saved position or session cache is empty, use default position
    if not position_restored:
        viewer_width = 500
        viewer_height = 400
        margin = 30
        x = self.canvas.width() - viewer_width - margin
        y = margin
        self.code_viewer.move(x, y + 50)
        self.code_viewer.resize(viewer_width, viewer_height)
    
    self.code_viewer.show()
    self.code_viewer.raise_()

def show_function_usage_viewer(self, node):
    """Show where functions from current file are used in the main script"""
    if not hasattr(self.canvas, 'main_script_name') or not self.canvas.main_script_name or not self.current_data:
        return
    
    # --- FIX: Use the absolute path from the analyzer result ---
    current_file_path = self.analyzer.current_file_path
    if not current_file_path:
        QMessageBox.warning(self, "Error", "Could not determine the path of the analyzed file.")
        return

    current_dir = os.path.dirname(current_file_path)
    
    # Handle cross-directory main scripts (indicated by ../ prefix)
    if self.canvas.main_script_name.startswith('../'):
        # Main script is in parent directory
        main_script_name = self.canvas.main_script_name[3:]  # Remove '../'
        project_root = self.get_project_root_directory()
        if project_root:
            main_script_path = os.path.join(project_root, main_script_name)
        else:
            main_script_path = os.path.join(os.path.dirname(current_dir), main_script_name)
    else:
        # Main script is in same directory
        main_script_path = os.path.join(current_dir, self.canvas.main_script_name)
    
    if not os.path.exists(main_script_path):
        debug_msg = f"Main script '{self.canvas.main_script_name}' not found!\n\n"
        debug_msg += f"Looking for: {main_script_path}\n"
        debug_msg += f"Current file: {current_file_path}\n"
        debug_msg += f"Directory: {current_dir}\n"
        
        # If it's a cross-directory reference, show additional info
        if self.canvas.main_script_name.startswith('../'):
            debug_msg += f"Project root: {self.get_project_root_directory()}\n"
        
        debug_msg += "\n"
        
        # List files in directory for debugging
        try:
            files_in_dir = [f for f in os.listdir(current_dir) if f.endswith('.py')]
            debug_msg += f"Python files in current directory: {', '.join(files_in_dir)}\n"
            
            # Also list files in project root if different
            project_root = self.get_project_root_directory()
            if project_root and project_root != current_dir:
                try:
                    root_files = [f for f in os.listdir(project_root) if f.endswith('.py')]
                    debug_msg += f"Python files in project root: {', '.join(root_files)}"
                except:
                    debug_msg += "Could not list project root files"
                    
        except Exception as e:
            debug_msg += f"Could not list directory contents: {e}"
            
        QMessageBox.warning(self, "Debug Info", debug_msg)
        return
    
    try:
        # Read the main script file
        with open(main_script_path, 'r', encoding='utf-8') as f:
            main_script_content = f.read()
        
        # Find usage of functions from current file
        usage_info = self.find_function_usage(main_script_content, self.current_data['functions'])
        
        if not usage_info:
            # Get the current module name and class name for debugging
            current_module_name = os.path.splitext(os.path.basename(current_file_path))[0]
            current_class_name = self.find_class_name_in_module()
            
            # Create user-friendly header
            debug_info = f"Analysis Results for {os.path.basename(current_file_path)} in {self.canvas.main_script_name}\n"
            debug_info += "=" * 70 + "\n\n"
            
            if current_class_name:
                debug_info += f"📋 CLASS INFORMATION:\n"
                debug_info += f"   Class Name: {current_class_name}\n"
                debug_info += f"   Module: {current_module_name}\n"
                debug_info += f"   Functions in this class: {', '.join([f for f in self.current_data['functions'].keys() if not f.startswith('__')])}\n\n"
            
            # Show class usage
            debug_info += f"🔍 CLASS USAGE FOUND:\n"
            found_lines = 0
            class_usage_lines = []
            for line_num, line in enumerate(main_script_content.split('\n'), 1):
                if (current_module_name.lower() in line.lower() or 
                    (current_class_name and current_class_name in line) or 
                    'ai_chat' in line.lower()):
                    class_usage_lines.append(f"   Line {line_num:3d}: {line.strip()}")
                    found_lines += 1
                    if found_lines >= 10:
                        class_usage_lines.append("   ... (showing first 10 matches)")
                        break
            
            if found_lines > 0:
                debug_info += f"   Found {found_lines} references to this class/module:\n"
                debug_info += "\n".join(class_usage_lines) + "\n\n"
            else:
                debug_info += "   No class references found\n\n"
            
            # --- NEW: Enhanced, beginner-friendly explanation ---
            debug_info += f"💡 How It Works (An Explanation):\n"
            if current_class_name and found_lines > 0:
                debug_info += f"   The class '{current_class_name}' is being used in '{self.canvas.main_script_name}', but its functions (like '{next((f for f in self.current_data['functions'].keys() if not f.startswith('__')), 'method')}') are not called directly. Why?\n\n"
                debug_info += f"   This is because this is an **event-driven** class, which is very common in UI applications!\n\n"
                debug_info += f"   Think of it like a doorbell:\n"
                debug_info += f"   1. **Setup:** You connect the button to the chime (`__init__`).\n"
                debug_info += f"   2. **Event:** Someone presses the button (a user clicks a UI element).\n"
                debug_info += f"   3. **Action:** The chime rings automatically (a function like `send_message` is called by the framework).\n\n"
                debug_info += f"   Your code doesn't call the function directly; the application framework (PySide6) does when the user interacts with the UI. This report correctly shows that the class blueprint is used, which is the key connection here! ✅\n"
            else:
                debug_info += f"   No direct function calls were found. This could mean:\n"
                debug_info += f"   • The functions are called indirectly by the application framework (e.g., connected to button clicks).\n"
                debug_info += f"   • The functions are utility methods that are not used by this particular main script.\n"
                debug_info += f"   • The class is imported but has not been used yet.\n"
            
            debug_info += f"\n" + "=" * 70 + "\n"
            debug_info += f"TECHNICAL DETAILS (for debugging):\n\n"
            debug_info += f"Functions analyzed: {list(self.current_data['functions'].keys())}\n\n"
            debug_info += "Search patterns tested:\n"
            
            # Show what patterns we're looking for
            for func_name in list(self.current_data['functions'].keys())[:3]:  # Show first 3 functions
                if not func_name.startswith('__'):
                    debug_info += f"- {func_name}()\n"
                    debug_info += f"- .{func_name}()\n"
                    debug_info += f"- object.{func_name}()\n"
            
            debug_info += "\nSearch results:\n"
            for func_name in self.current_data['functions'].keys():
                if not func_name.startswith('__'):
                    # Count actual matches found
                    import re
                    pattern1 = rf'\b{re.escape(func_name)}\s*\('
                    pattern2 = rf'\.{re.escape(func_name)}\s*\('
                    pattern3 = rf'\b\w+\.{re.escape(func_name)}\s*\('
                    
                    matches1 = len(re.findall(pattern1, main_script_content))
                    matches2 = len(re.findall(pattern2, main_script_content))
                    matches3 = len(re.findall(pattern3, main_script_content))
                    
                    debug_info += f"- {func_name}: direct={matches1}, method={matches2}, object={matches3}\n"
            
            usage_content = debug_info
        else:
            usage_content = self.format_usage_info(usage_info, self.canvas.main_script_name)
        
        # Show in code viewer with custom size for main script
        self.code_viewer.set_code(f"Usage in {self.canvas.main_script_name}", usage_content)
        self.code_viewer.show()
        self.code_viewer.raise_()
        
        # Position the code viewer at center-right (not too far right)
        viewer_width = 600
        viewer_height = 400
        margin = 100  # More margin from right edge
        
        x = self.canvas.width() - viewer_width - margin
        y = (self.canvas.height() - viewer_height) // 2
        
        self.code_viewer.move(x, y)
        self.code_viewer.resize(viewer_width, viewer_height)
        
    except Exception as e:
        error_msg = f"Failed to analyze main script '{self.canvas.main_script_name}':\n\n"
        error_msg += f"Error: {str(e)}\n\n"
        error_msg += f"Main script path: {main_script_path}\n"
        error_msg += f"File exists: {os.path.exists(main_script_path)}\n"
        error_msg += f"Current data file: {self.current_data.get('file_path', 'Unknown')}"
        QMessageBox.critical(self, "Error", error_msg)

def find_function_usage(self, main_script_content, functions):
    """Find where functions are used in the main script"""
    import re
    usage_info = []
    lines = main_script_content.split('\n')
    
    # First, find class names from the current module
    current_module_name = os.path.splitext(os.path.basename(self.current_data.get('file_path', '')))[0]
    
    # Find the class name from the current module (e.g., AIChatWidget)
    current_class_name = self.find_class_name_in_module()
    
    for func_name, func_data in functions.items():
        usages = []
        
        # Skip __init__ and other special methods as they're too common
        if func_name.startswith('__') and func_name.endswith('__'):
            continue
        
        # Search for function calls
        for line_num, line in enumerate(lines, 1):
            # --- FIX: Use a set to track added line numbers to avoid duplicates ---
            added_lines = set()

            # Pattern 1: Direct function calls (function_name followed by parentheses)
            pattern1 = rf'\b{re.escape(func_name)}\s*\('
            matches1 = re.finditer(pattern1, line)
            
            # Pattern 2: Method calls on class instances (instance.method_name())
            pattern2 = rf'\.{re.escape(func_name)}\s*\('
            matches2 = re.finditer(pattern2, line)
            
            # Pattern 3: Class instantiation or method calls through imported classes
            pattern3 = rf'\b\w+\.{re.escape(func_name)}\s*\('
            matches3 = re.finditer(pattern3, line)
            
            # Pattern 4: Signal connections (connect(self.method_name))
            pattern4 = rf'connect\s*\(\s*[^.]*\.{re.escape(func_name)}\s*\)'
            matches4 = re.finditer(pattern4, line)
            
            # Pattern 5: Lambda or partial connections
            pattern5 = rf'lambda.*{re.escape(func_name)}'
            matches5 = re.finditer(pattern5, line)
            
            # Pattern 6: Class instantiation (for __init__ methods)
            if func_name == '__init__' and current_class_name:
                pattern6 = rf'{re.escape(current_class_name)}\s*\('
                matches6 = re.finditer(pattern6, line)
            else:
                matches6 = []
            
            all_matches = list(matches1) + list(matches2) + list(matches3) + list(matches4) + list(matches5) + list(matches6)
            
            for match in all_matches:
                if line_num in added_lines:
                    continue # Already added a usage for this line

                # Try to find which function this usage is inside
                containing_function = self.find_containing_function(lines, line_num)
                
                # Get context lines (before and after)
                context_before = []
                context_after = []
                
                # Get 2 lines before
                for i in range(max(0, line_num - 3), line_num - 1):
                    if i < len(lines):
                        context_before.append(f"   {i+1:3d} | {lines[i]}")
                
                # Get 2 lines after
                for i in range(line_num, min(len(lines), line_num + 2)):
                    if i < len(lines):
                        context_after.append(f"   {i+1:3d} | {lines[i]}")
                
                usages.append({
                    'line': line_num,
                    'content': line.strip(),
                    'containing_function': containing_function,
                    'column': match.start(),
                    'context_before': context_before,
                    'context_after': context_after
                })
                added_lines.add(line_num) # Mark line as added
        
        if usages:
            usage_info.append({
                'function_name': func_name,
                'usages': usages,
                'docstring': func_data.get('docstring', ''),
                'args': func_data.get('args', [])
            })
    
    return usage_info

def find_class_name_in_module(self):
    """Find the main class name in the current module"""
    if not self.analyzer.current_code:
        return None
    
    import re
    lines = self.analyzer.current_code.split('\n')
    
    for line in lines:
        # Look for class definitions
        class_match = re.match(r'class\s+(\w+)', line.strip())
        if class_match:
            return class_match.group(1)
    
    return None








# --------------------- Canvas context menu handlers ---------------------
def on_canvas_request_open_file(self, file_path: str):
    """Open the given file in the host window's file tree/editor if available; else fallback to Manage's own loader."""
    try:
        if not file_path:
            return
        fp = os.path.abspath(file_path)
        host = self.parent()
        # Prefer opening in the host application's custom editor (safe.py)
        if host and hasattr(host, 'open_file_for_editing'):
            try:
                host.open_file_for_editing(fp)
            except Exception:
                pass
            # Reveal/highlight in the host file tree if supported
            try:
                if hasattr(host, 'highlight_main_python_file'):
                    host.highlight_main_python_file(fp)
            except Exception:
                pass
            return
        # Fallback: open within Manage's own file panel
        self.load_file(fp)
        try:
            self.files_btn.setChecked(True)
            self.toggle_panel_visibility()
        except Exception:
            pass
    except Exception:
        pass

def on_canvas_request_open_editor(self, node, file_path: str):
    """Open the custom editor for the target file and optionally jump to the node's line.
    Prefers error_line if present on the node's data.
    """
    try:
        target = file_path or getattr(self.analyzer, 'current_file_path', None)
        target = os.path.abspath(target) if target else None
        host = self.parent()
        if target and host and hasattr(host, 'open_file_for_editing'):
            # Open file in the main editor (custom CodeEditor)
            try:
                host.open_file_for_editing(target)
            except Exception:
                pass
            # Jump to error line first if available, else function start line
            try:
                data = (getattr(node, 'data', {}) or {})
                ln = 0
                try:
                    ln = int(data.get('error_line') or 0)
                except Exception:
                    ln = 0
                if ln <= 0:
                    try:
                        ln = int(data.get('lineno') or 0)
                    except Exception:
                        ln = 0
                if ln > 0 and hasattr(host, 'get_editor_for_path'):
                    ed = host.get_editor_for_path(target)
                    if ed:
                        from PySide6.QtGui import QTextCursor as _QTextCursor
                        block = ed.document().findBlockByLineNumber(max(0, ln - 1))
                        cur = _QTextCursor(block) if block.isValid() else ed.textCursor()
                        ed.setTextCursor(cur)
                        try:
                            ed.centerCursor()
                        except Exception:
                            pass
            except Exception:
                pass
            return
        # Fallback: show the function code in Manage's code viewer
        if node:
            self.show_function_code_viewer(node)
    except Exception:
        pass

def _resolve_main_script_path(self) -> Optional[str]:
    """Resolve absolute path to main script if detected, else None."""
    if not hasattr(self.canvas, 'main_script_name') or not self.canvas.main_script_name:
        return None

    current_file_path = getattr(self.analyzer, 'current_file_path', None)
    current_dir = os.path.dirname(current_file_path) if current_file_path else None

    # Handle cross-directory main scripts (indicated by ../ prefix)
    if self.canvas.main_script_name.startswith('../'):
        main_script_name = self.canvas.main_script_name[3:]
        project_root = self.get_project_root_directory()
        if project_root:
            main_script_path = os.path.join(project_root, main_script_name)
        elif current_dir:
            main_script_path = os.path.join(os.path.dirname(current_dir), main_script_name)
        else:
            main_script_path = None
    else:
        if current_dir:
            main_script_path = os.path.join(current_dir, self.canvas.main_script_name)
        else:
            main_script_path = None

    if main_script_path and os.path.exists(main_script_path):
        return os.path.abspath(main_script_path)
    return None

def _is_standalone_script(self, path: Optional[str]) -> bool:
    """Return True if the file can act as an entry script (standalone)."""
    try:
        if not path or not os.path.exists(path):
            return False
        base = os.path.basename(path).lower()
        # Common entry script names including this tool's launcher
        standalone_names = {'safe.py', 'main.py', 'app.py', 'run.py', 'start.py', 'manage_native.py'}
        if base in standalone_names:
            return True
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        return "if __name__ == '__main__'" in content
    except Exception:
        return False

def run_python_script(self):
    """Run Rust file using cargo run or rustc."""
    # Ensure rust console is visible
    self.Rust_panel.show()
    self.Rust_panel.raise_()
    self.python_btn.setChecked(True)

    terminal = getattr(self, 'python_preview_widget', None)
    process = getattr(terminal, 'process', None) if terminal else None
    if not process:
        QMessageBox.warning(self, "Rust Console", "Interactive terminal is not available.")
        return

    # Determine which file to run: prefer current analyzed file
    target_path = getattr(self.analyzer, 'current_file_path', None)
    if not target_path or not os.path.exists(target_path):
        QMessageBox.warning(self, "Run Rust", "No Rust file to run. Load a .rs file first.")
        return

    # Check if it's a Rust file
    if not target_path.lower().endswith('.rs'):
        QMessageBox.warning(self, "Run Rust", "Please select a Rust file (.rs) to run.")
        return

    work_dir = os.path.dirname(target_path)
    
    # Try to find Cargo.toml in parent directories
    cargo_root = None
    current_dir = work_dir
    for _ in range(10):  # Check up to 10 levels up
        cargo_toml = os.path.join(current_dir, 'Cargo.toml')
        if os.path.exists(cargo_toml):
            cargo_root = current_dir
            break
        parent = os.path.dirname(current_dir)
        if parent == current_dir:  # Reached root
            break
        current_dir = parent

    # Build the command
    if cargo_root:
        # Use cargo run if in a Cargo project
        if os.name == 'nt':
            command = f'cd "{cargo_root}" ; cargo run'
        else:
            command = f'cd "{cargo_root}" && cargo run'
    else:
        # Use rustc for standalone files
        file_name = os.path.basename(target_path)
        exe_name = os.path.splitext(file_name)[0]
        if os.name == 'nt':
            exe_name += '.exe'
            command = f'cd "{work_dir}" ; rustc "{file_name}" && .\\{exe_name}'
        else:
            command = f'cd "{work_dir}" && rustc "{file_name}" && ./{exe_name}'

    try:
        # Write command to the running shell
        process.write((command + "\n").encode())
    except Exception as e:
        QMessageBox.critical(self, "Run Rust Error", f"Failed to run Rust file:\n{e}")

def _build_warning_box(self) -> QFrame:
    box = QFrame(self.canvas)
    try:
        box.setWindowFlags(Qt.SubWindow | Qt.FramelessWindowHint)
    except Exception:
        pass
    box.setStyleSheet("""
        QFrame {
            background-color: #2C2E33; /* solid background */
            border: 1px solid #4A4D51;
            border-radius: 8px;
            margin: 0px;
        }
        /* Ensure inner text and icon have no borders/radius and no background */
        QLabel { 
            color: #E8EAED; 
            background-color: transparent; 
            border: none; 
            border-radius: 0;
        }
        #warningTextContainer {
            background: transparent;
            border: none;
            border-radius: 0;
        }
        #warningIcon {
            background: transparent;
            border: none;
            border-radius: 0;
        }
        QPushButton { background: transparent; color: #E8EAED; border: none; font-size: 16px; }
        QPushButton:hover { color: #FFFFFF; }
    """)
    layout = QHBoxLayout(box)
    layout.setContentsMargins(10, 8, 10, 8)
    layout.setSpacing(8)

    icon_label = QLabel()
    icon_label.setObjectName("warningIcon")
    try:
        icon = QIcon("img/Simple_manage.png")
        pix = icon.pixmap(60, 60)
        icon_label.setPixmap(pix)
    except Exception:
        pass
    layout.addWidget(icon_label)

    text_container = QWidget()
    text_container.setObjectName("warningTextContainer")
    v = QVBoxLayout(text_container)
    v.setContentsMargins(0, 0, 0, 0)
    v.setSpacing(0)

    self._warning_title = QLabel("Guide")
    self._warning_title.setStyleSheet("color: #60A5FA; font-weight: bold; font-size: 16px; margin: 0px; margin-bottom: 10px;")
    self._warning_title.setContentsMargins(0, 0, 0, 0)
    self._warning_body = QLabel("")
    self._warning_body.setWordWrap(True)
    self._warning_body.setStyleSheet("color: #E8EAED; font-size: 13px; margin: 0px;")
    self._warning_body.setContentsMargins(6, 0, 0, 0)

    v.addWidget(self._warning_title)
    v.addWidget(self._warning_body)
    layout.addWidget(text_container, 1)

    close_btn = QPushButton("✕")
    close_btn.clicked.connect(lambda: self._warning_box and self._warning_box.hide())
    layout.addWidget(close_btn)

    box.resize(420, 90)
    box.move(120, 120)
    box.hide()
    return box

def _show_main_warning_box(self, main_script_basename: str):
    if self._warning_box is None:
        self._warning_box = self._build_warning_box()
    self._warning_title.setText("Guide")
    self._warning_body.setText(f"You must run {main_script_basename} :)")
    try:
        margin = 30
        x = max(10, self.canvas.width() - self._warning_box.width() - margin)
        y = 60
        self._warning_box.move(x, y)
    except Exception:
        pass
    self._warning_box.show()
    self._warning_box.raise_()

def _highlight_main_node_red(self):
    try:
        if not hasattr(self, 'canvas') or not hasattr(self.canvas, 'nodes'):
            return
        main_node = next((n for n in self.canvas.nodes if getattr(n, 'icon_path', None) and 'python' in str(n.icon_path).lower()), None)
        if main_node:
            main_node.color = '#D16969'
            self.canvas.update()
    except Exception:
        pass

def _maybe_show_main_warning_for(self, current_path: Optional[str]):
    try:
        # Prefer Manage’s own resolver
        main_path = self._resolve_main_script_path()

        # Fallback search
        if (not main_path) and current_path:
            candidates = ['safe.py', 'main.py', 'app.py', '__main__.py', 'run.py', 'start.py']
            cur_dir = os.path.dirname(current_path)
            for c in candidates:
                p = os.path.join(cur_dir, c)
                if os.path.exists(p):
                    main_path = p
                    break
            if not main_path:
                try:
                    root = self.get_project_root_directory()
                    for c in candidates:
                        p = os.path.join(root or '', c)
                        if p and os.path.exists(p):
                            main_path = p
                            break
                except Exception:
                    pass

        # Suppress if the current file is a standalone/entry script
        if current_path and self._is_standalone_script(current_path):
            return

        if not current_path or not main_path:
            return

        # Suppress the guide if the host application is already the main script (e.g., safe.py)
        try:
            host_main = os.path.abspath(sys.argv[0]) if sys.argv else None
        except Exception:
            host_main = None
        if host_main and os.path.exists(host_main):
            try:
                if os.path.abspath(host_main) == os.path.abspath(main_path):
                    return
            except Exception:
                pass

        # If we are analyzing/running the main script itself, no warning
        if os.path.abspath(current_path) == os.path.abspath(main_path):
            return

        # Highlight and blink the main python node for ~3 seconds
        self._highlight_main_node_red()
        try:
            if hasattr(self, 'canvas') and hasattr(self.canvas, 'nodes'):
                main_node = next((n for n in self.canvas.nodes if getattr(n, 'icon_path', None) and 'python' in str(n.icon_path).lower()), None)
                if main_node:
                    main_node.blink_time = 3.0
                    main_node.blink_phase = 0.0
        except Exception:
            pass
        self._show_main_warning_box(os.path.basename(main_path))
    except Exception:
        pass

def get_function_code(self, func_name: str) -> Optional[str]:
    """Extract function code from current source"""
    if not self.analyzer.current_code:
        return None
        
    lines = self.analyzer.current_code.split('\n')
    
    # Find function start
    start_line = None
    for i, line in enumerate(lines):
        if line.strip().startswith(f'def {func_name}('):
            start_line = i
            break
            
    if start_line is None:
        return None
        
    # Find function end
    end_line = len(lines)
    indent_level = None
    
    for i in range(start_line + 1, len(lines)):
        line = lines[i]
        if line.strip():  # Non-empty line
            current_indent = len(line) - len(line.lstrip())
            if indent_level is None:
                indent_level = current_indent
            elif current_indent <= indent_level and not line.lstrip().startswith(('"""', "'''", '#')):
                end_line = i
                break
    
    return '\n'.join(lines[start_line:end_line])
