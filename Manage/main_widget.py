"""
Main Widget Module
Contains the main ManageWidget that integrates all components
"""

import os
import sys
from typing import Optional, List
from PySide6.QtCore import Qt, QSize, QEvent
from PySide6.QtGui import QResizeEvent, QIcon, QTextCursor, QPixmap
from PySide6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QMessageBox, QPushButton, QFrame, QLabel, QTextEdit, QLineEdit, QColorDialog

from .data_analysis import FunctionAnalyzer, DARK_THEME
from .visualization_core import VisualizationCanvas
from .document_io import SaveLoadManager
from .ui_components import (
    ResizablePanel, ResizableCodeViewer, ResizableTextEditor,
    ResizableImageEditor, ResizableVideoEditor,
    ToolbarButton, setup_file_browser_widget
)

# Import functions from main_widget2
from . import main_widget2

class ManageWidget(QWidget):
    """Main widget for the native function dependency visualizer"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.analyzer = FunctionAnalyzer()
        self.current_data = None
        self.setup_ui()
        self.connect_signals()
        # Internal guide overlay box (created on demand)
        self._warning_box = None
        # Activity tracking disabled by default
        self.activity_enabled = False
        # Search state
        self._search_matches = []
        self._search_index = -1
        # Active project (.mndoc) state for multi-file layouts
        self._project_doc = None
        self._project_path = None
        # In-memory session layouts (per-file) to prevent resets when switching files
        self._session_layouts = {}
        # Track preferred project root based on the last loaded file
        self._project_root_override = None
        # Default annotation color: white for text and brush
        try:
            if hasattr(self.canvas, 'set_current_color'):
                from PySide6.QtGui import QColor as _QColor
                self.canvas.set_current_color(_QColor('#FFFFFF'), apply_to_selection=False)
        except Exception:
            pass
        
        # Add top right toolbar with two icons
        self._setup_top_right_toolbar()

    # --------------------- Session cache helpers ---------------------
    def _capture_session_for_current(self):
        """Capture current canvas layout (including annotations) into the in-memory session cache for the current file."""
        try:
            cur = getattr(self.analyzer, 'current_file_path', None)
            if not cur:
                return
            mgr = SaveLoadManager()
            state = mgr.collect_state(self)
            self._session_layouts[os.path.abspath(cur)] = state
        except Exception:
            pass

    def _apply_session_for(self, file_path: str):
        """Apply a previously captured layout (including annotations) for file_path if present."""
        try:
            if not file_path:
                return
            key = os.path.abspath(file_path)
            state = self._session_layouts.get(key)
            if not state:
                return
            mgr = SaveLoadManager()
            mgr.apply_to_canvas(self.canvas, state)
        except Exception:
            pass

    def _merge_all_sessions_into_project(self, project_doc: dict) -> dict:
        """Merge current canvas and all session-cached per-file states into the given project document."""
        try:
            mgr = SaveLoadManager()
            proj = project_doc or {}
            # Ensure project has files map
            if not isinstance(proj.get('files'), dict):
                proj['files'] = {}
            # Merge the current canvas first
            try:
                proj, _ = mgr.merge_current_file_into_project(self, proj)
            except Exception:
                pass
            # Merge all cached sessions
            for abs_path, state in (self._session_layouts or {}).items():
                try:
                    per_file_state = {
                        'viewport': state.get('viewport') or {},
                        'nodes': state.get('nodes') or [],
                        'hidden_nodes': state.get('hidden_nodes') or [],
                        'panels': state.get('panels') or {},
                        'annotations': state.get('annotations') or {},
                        'modified_at': state.get('modified_at') or '',
                    }
                    proj['files'][abs_path] = per_file_state
                except Exception:
                    pass
            return proj
        except Exception:
            return project_doc

    def setup_ui(self):
        """Setup the main UI layout"""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Main visualization canvas is the base layer
        self.canvas = VisualizationCanvas(self)
        layout.addWidget(self.canvas)

        
        # Left Toolbar floats on top of the canvas (horizontal layout)
        self.toolbar = QWidget(self.canvas)
        self.toolbar.setStyleSheet("background-color: transparent;")
        toolbar_layout = QHBoxLayout(self.toolbar)
        toolbar_layout.setContentsMargins(10, 10, 10, 10)
        toolbar_layout.setSpacing(15)
        toolbar_layout.setAlignment(Qt.AlignLeft | Qt.AlignBottom)

        self.files_btn = ToolbarButton("img/folder.png", "Open File Browser")
        self.python_btn = ToolbarButton("img/Rust.png", "Show Rust Panel")

        toolbar_layout.addWidget(self.files_btn)
        toolbar_layout.addWidget(self.python_btn)
        
        # Bottom-centered mini-toolbar for annotation tools (hidden by default)
        self.annotation_toolbar = QWidget(self.canvas)
        self.annotation_toolbar.setVisible(False)
        ann_layout = QHBoxLayout(self.annotation_toolbar)
        ann_layout.setContentsMargins(12, 8, 12, 8)
        ann_layout.setSpacing(14)
        ann_layout.setAlignment(Qt.AlignCenter)
        self.annotation_toolbar.setStyleSheet(
            f"""
            QWidget {{
                background-color: {DARK_THEME['bg_secondary']};
                border: 1px solid {DARK_THEME['border']};
                border-radius: 18px;
            }}
            """
        )
        # Five center icons: Cursor, Brush, Text, Erase, Color
        self.cursor_tool_btn = ToolbarButton("img/Cursor.png", "Cursor / Select")
        self.brush_tool_btn = ToolbarButton("img/Brush.png", "Brush / Paint")
        self.text_tool_btn = ToolbarButton("img/Text.png", "Add Text")
        self.erase_tool_btn = ToolbarButton("img/Eraser.png", "Erase Brush")
        self.color_tool_btn = ToolbarButton("img/RGB.png", "Pick Color (RGB)")
        # Radio behavior for cursor/brush/text/erase
        self.cursor_tool_btn.setCheckable(True)
        self.brush_tool_btn.setCheckable(True)
        self.text_tool_btn.setCheckable(True)
        self.erase_tool_btn.setCheckable(True)
        self.cursor_tool_btn.setChecked(False)
        self.brush_tool_btn.setChecked(True)
        self.text_tool_btn.setChecked(False)
        self.erase_tool_btn.setChecked(False)
        for b in (self.cursor_tool_btn, self.brush_tool_btn, self.text_tool_btn, self.erase_tool_btn, self.color_tool_btn):
            b.setFixedSize(44, 44)
            b.setIconSize(QSize(24, 24))
        ann_layout.addWidget(self.cursor_tool_btn)
        ann_layout.addWidget(self.brush_tool_btn)
        ann_layout.addWidget(self.text_tool_btn)
        ann_layout.addWidget(self.erase_tool_btn)
        ann_layout.addWidget(self.color_tool_btn)
        # Show numeric shortcut badges on tool buttons
        try:
            self.cursor_tool_btn.set_shortcut_label('1')
            self.brush_tool_btn.set_shortcut_label('2')
            self.text_tool_btn.set_shortcut_label('3')
            self.erase_tool_btn.set_shortcut_label('4')
            self.color_tool_btn.set_shortcut_label('5')
        except Exception:
            pass

        # --- Floating Panels (initially hidden) ---
        self.setup_floating_panels()

        # --- Code Viewer (initially hidden) ---
        self.code_viewer = ResizableCodeViewer(self.canvas)
        self.code_viewer.setVisible(False)
        self.code_viewer.closed.connect(self.on_code_viewer_closed)
        
        # --- Text Editor for custom text content (initially hidden) ---
        self.text_editor = ResizableTextEditor(self.canvas)
        self.text_editor.setVisible(False)
        self.text_editor.closed.connect(self.on_text_editor_closed)
        
        # --- Image Editor for custom image content (initially hidden) ---
        self.image_editor = ResizableImageEditor(self.canvas)
        self.image_editor.setVisible(False)
        self.image_editor.closed.connect(self.on_image_editor_closed)
        
        # --- Video Editor for custom video content (initially hidden) ---
        self.video_editor = ResizableVideoEditor(self.canvas)
        self.video_editor.setVisible(False)
        self.video_editor.closed.connect(self.on_video_editor_closed)

                
        # Style
        self.setStyleSheet(f"""
            QWidget {{
                background-color: {DARK_THEME['bg_primary']};
                color: {DARK_THEME['text_primary']};
            }}
            QToolTip {{
                background-color: #2C2E33;
                color: #E8EAED;
                border: 1px solid #4A4D51;
                padding: 6px 8px;
                border-radius: 6px;
            }}
        """)

        # Install event filters to capture Ctrl+F/F3 before global QActions
        try:
            self.installEventFilter(self)
            self.canvas.installEventFilter(self)
        except Exception:
            pass
    
    def _setup_top_right_toolbar(self):
        """Create top right toolbar using Manage2 module"""
        try:
            # Import the TopRightToolbar from Manage2
            import sys
            import os
            # Add parent directory to path if needed
            parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            if parent_dir not in sys.path:
                sys.path.insert(0, parent_dir)
            
            from Manage2.top_right_toolbar import TopRightToolbar
            
            # Create the toolbar
            self.top_toolbar = TopRightToolbar(self.canvas)
            
            # Connect to menu action signal
            self.top_toolbar.menu_action_triggered.connect(self._on_toolbar_menu_action)
            
            # Connect text brush button to annotation toolbar toggle
            self.top_toolbar.text_brush_btn.clicked.connect(self._on_top_toolbar_text_brush_clicked)
            
            # Position the toolbar
            self.top_toolbar.position_toolbar(
                self.canvas.width(),
                self.canvas.height()
            )
            
            # Show the toolbar
            self.top_toolbar.show()
            self.top_toolbar.raise_()
            
        except Exception as e:
            import traceback
            traceback.print_exc()
    
    def _on_toolbar_menu_action(self, action_name: str):
        """Handle menu action from top right toolbar"""
        print(f"[ManageWidget] Toolbar menu action: {action_name}")
        
        # Emit signal to parent window if it exists (for manage_native.py to handle)
        try:
            parent_window = self.window()
            print(f"[ManageWidget] Parent window: {parent_window}")
            print(f"[ManageWidget] Has _on_menu_action: {hasattr(parent_window, '_on_menu_action')}")
            
            if parent_window and parent_window != self and hasattr(parent_window, '_on_menu_action'):
                print(f"[ManageWidget] Forwarding to parent window")
                parent_window._on_menu_action(action_name)
                return
            else:
                print(f"[ManageWidget] No valid parent window found, using fallback")
        except Exception as e:
            print(f"[ManageWidget] Error checking parent: {e}")
            import traceback
            traceback.print_exc()
        
        # Fallback handlers if no parent window
        if action_name == "Add Project":
            QMessageBox.information(self, "Add Project", "Add Project functionality - please run through manage_native.py")
        elif action_name == "Select Box":
            # Toggle selection box mode on the canvas
            if hasattr(self, 'canvas'):
                current_mode = getattr(self.canvas, '_selection_box_mode', False)
                self.canvas.toggle_selection_box_mode(not current_mode)
        elif action_name == "Search":
            # Trigger the search box
            try:
                self.trigger_search()
            except Exception:
                QMessageBox.information(self, "Search", "Search functionality")
        elif action_name == "Save A3 Project":
            QMessageBox.information(self, "Save A3 Project", "Save A3 Project functionality will be implemented here.")
        elif action_name == "Load A3 Project":
            QMessageBox.information(self, "Load A3 Project", "Load A3 Project functionality will be implemented here.")
    
    def _on_top_toolbar_text_brush_clicked(self, checked: bool):
        """Handle text brush button click from top right toolbar"""
        try:
            # Toggle the annotation toolbar
            self.toggle_annotation_toolbar(checked)
        except Exception as e:
            print(f"[ManageWidget] Error toggling text brush: {e}")

    def _position_top_toolbar(self):
        """Position top right toolbar"""
        if hasattr(self, 'top_toolbar') and hasattr(self.top_toolbar, 'position_toolbar'):
            try:
                self.top_toolbar.position_toolbar(
                    self.canvas.width(),
                    self.canvas.height()
                )
            except Exception as e:
                print(f"[ManageWidget] Error positioning toolbar: {e}")

    def resizeEvent(self, event: QResizeEvent):
        """Ensure all floating UI elements are repositioned correctly on resize."""
        super().resizeEvent(event)
        if hasattr(self, 'toolbar'):
            self.toolbar.move(0, 0)
            self.toolbar.setFixedHeight(self.canvas.height())
                
        # --- FIX: Reposition all floating panels when the window is resized ---
        self.update_panel_positions()
        
        # Reposition top right toolbar
        if hasattr(self, 'top_toolbar'):
            self._position_top_toolbar()

    def update_panel_positions(self):
        """ Recalculates and sets the position of all visible floating panels. """
        # DON'T reposition file_panel and Rust_panel - let them keep user's position
        # Only reposition panels that need dynamic positioning
        
        # Reposition the code viewer panel (right side)
        if self.code_viewer.isVisible():
            viewer_width = self.code_viewer.width()
            margin = 50
            x = self.canvas.width() - viewer_width - margin
            y = margin
            self.code_viewer.move(x, y + 50)
        
        # Reposition bottom annotation toolbar (center bottom)
        try:
            if hasattr(self, 'annotation_toolbar') and self.annotation_toolbar.isVisible():
                self._position_annotation_toolbar()
        except Exception:
            pass

    def setup_floating_panels(self):
        """ Creates and configures all the floating panels. """
        # File Browser Panel
        self.file_panel = ResizablePanel("File Browser", self.canvas)
        self.setup_file_browser()
        self.file_panel.setVisible(False)
        self.file_panel.closed.connect(lambda: self.files_btn.setChecked(False))
        # Set initial size and position
        self.file_panel.resize(400, 350)
        self.file_panel.move(100, 50)

        
        
        # Rust Panel
        self.Rust_panel = ResizablePanel("Rust Panel", self.canvas)
        try:
            from running_app import InteractiveTerminal
            self.python_preview_widget = InteractiveTerminal()
            # Match running_app.py console background styling on the container
            try:
                self.python_preview_widget.setStyleSheet("""
                    QWidget { background-color: #121214; }
                """)
            except Exception:
                pass
            # Always connect terminal stdout; console visibility is controlled separately
            try:
                self.python_preview_widget.outputReceived.connect(self.on_terminal_output)
            except Exception:
                pass
            self.Rust_panel.set_widget(self.python_preview_widget)
        except ImportError:
            # Fallback if running_app is not available
            from PySide6.QtWidgets import QLabel
            fallback_label = QLabel("Python Preview not available")
            fallback_label.setAlignment(Qt.AlignCenter)
            self.Rust_panel.set_widget(fallback_label)

        # Add a Rust run icon next to the close button
        try:
            self.run_python_btn = QPushButton()
            self.run_python_btn.setToolTip("Run Rust file")
            self.run_python_btn.setIcon(QIcon("img/Rust_R.png"))
            self.run_python_btn.setFixedSize(28, 28)
            self.run_python_btn.setIconSize(QSize(20, 20))
            self.run_python_btn.setStyleSheet("background: transparent; border: none;")
            self.run_python_btn.clicked.connect(self.run_python_script)
            if hasattr(self.Rust_panel, 'add_title_widget'):
                self.Rust_panel.add_title_widget(self.run_python_btn)
        except Exception:
            pass
        # Activity toggle icon in Python Preview title bar
        try:
            self.activity_panel_title_btn = QPushButton()
            self.activity_panel_title_btn.setToolTip("Show Activity")
            self.activity_panel_title_btn.setCheckable(True)
            self.activity_panel_title_btn.setIcon(QIcon("img/Manage_Static.png"))
            self.activity_panel_title_btn.setFixedSize(28, 28)
            self.activity_panel_title_btn.setIconSize(QSize(20, 20))
            self.activity_panel_title_btn.setStyleSheet("background: transparent; border: none;")
            self.activity_panel_title_btn.toggled.connect(self._toggle_activity_panel_from_title)
            if hasattr(self.Rust_panel, 'add_title_widget'):
                self.Rust_panel.add_title_widget(self.activity_panel_title_btn)
        except Exception:
            pass

        self.Rust_panel.setVisible(False)
        self.Rust_panel.closed.connect(lambda: self.python_btn.setChecked(False))
        # Set initial size and position
        self.Rust_panel.resize(400, 350)
        self.Rust_panel.move(100, 50)

        # Activity Panel for live function calls (no socket)
        self.activity_panel = ResizablePanel("Activity", self.canvas)
        self.activity_text = QTextEdit()
        self.activity_text.setReadOnly(True)
        self.activity_text.setStyleSheet("QTextEdit { background: #121214; color: #E0E2E6; border: none; }")
        self.activity_panel.set_widget(self.activity_text)
        self.activity_panel.setVisible(False)
        self.activity_panel.closed.connect(lambda: None)
        try:
            self.activity_panel.closed.connect(lambda: self._sync_activity_title_btn(False))
        except Exception:
            pass

        # Activity toggle button in Activity panel (controls only console logging)
        try:
            self.activity_toggle_btn = QPushButton()
            self.activity_toggle_btn.setToolTip("Enable Console")
            self.activity_toggle_btn.setCheckable(True)
            self.activity_toggle_btn.setIcon(QIcon("img/Manage_Static.png"))
            self.activity_toggle_btn.setFixedSize(28, 28)
            self.activity_toggle_btn.setIconSize(QSize(20, 20))
            self.activity_toggle_btn.setStyleSheet("background: transparent; border: none;")
            self.activity_toggle_btn.toggled.connect(self.set_activity_enabled)
            if hasattr(self.activity_panel, 'add_title_widget'):
                self.activity_panel.add_title_widget(self.activity_toggle_btn)
        except Exception:
            pass

    def connect_signals(self):
        """Connect all signals"""
        # Toolbar button signals
        self.files_btn.clicked.connect(self.toggle_panel_visibility)
        self.python_btn.clicked.connect(self.toggle_panel_visibility)
        # Annotation toolbar tools
        self.cursor_tool_btn.clicked.connect(lambda: self._set_annotation_tool('cursor'))
        self.brush_tool_btn.clicked.connect(lambda: self._set_annotation_tool('brush'))
        self.text_tool_btn.clicked.connect(lambda: self._set_annotation_tool('text'))
        self.erase_tool_btn.clicked.connect(lambda: self._set_annotation_tool('erase'))
        self.color_tool_btn.clicked.connect(self.on_pick_annotation_color)

        # Canvas signals
        self.canvas.node_selected.connect(self.on_node_selected)
        self.canvas.node_double_clicked.connect(self.on_node_double_clicked)
        # Context menu requests from canvas
        try:
            self.canvas.request_open_file.connect(self.on_canvas_request_open_file)
            self.canvas.request_open_editor.connect(self.on_canvas_request_open_editor)
            self.canvas.request_stop_python.connect(self.on_canvas_request_stop_python)
            self.canvas.request_toggle_activity.connect(self.on_canvas_request_toggle_activity)
        except Exception:
            pass
        # Connection drag signal (for adding functions via drag-and-drop)
        try:
            self.canvas.connection_drag_completed.connect(self.on_connection_drag_completed)
        except Exception:
            pass
        self.file_tree.doubleClicked.connect(self.on_file_tree_double_clicked)

    def setup_file_browser(self):
        """ Sets up the file browser tree view inside the file panel. """
        container, self.file_tree, self.file_model, self.proxy_model = setup_file_browser_widget(self)
        self.file_panel.set_widget(container)

    def on_file_tree_double_clicked(self, index):
        """ Loads and analyzes a file when double-clicked in the tree. """
        source_index = self.proxy_model.mapToSource(index)
        path = self.file_model.filePath(source_index)
        if not self.file_model.isDir(source_index) and (path.endswith('.py') or path.endswith('.rs')):
            self.load_file(path)

    def set_root_path(self, path: str):
        """ Sets the root path for the file browser tree. """
        if hasattr(self, 'file_tree'):
            self.file_tree.setRootIndex(self.proxy_model.mapFromSource(self.file_model.index(path)))

    def _select_in_file_tree(self, file_path: str):
        """Expand ancestors and select the given file in the file tree without changing the root."""
        try:
            if not hasattr(self, 'file_tree') or not hasattr(self, 'file_model') or not hasattr(self, 'proxy_model'):
                return
            src_index = self.file_model.index(file_path)
            if not src_index.isValid():
                return
            # Expand ancestors so the file is visible
            parent = src_index.parent()
            while parent.isValid():
                try:
                    self.file_tree.expand(self.proxy_model.mapFromSource(parent))
                except Exception:
                    pass
                parent = parent.parent()
            # Select and scroll to the file
            proxy_index = self.proxy_model.mapFromSource(src_index)
            try:
                self.file_tree.setCurrentIndex(proxy_index)
                self.file_tree.scrollTo(proxy_index)
            except Exception:
                pass
        except Exception:
            pass

    def load_sample_data(self):
        """Load sample Python code for demonstration"""
        sample_code = '''
def calculate_total(items):
    """Calculate total price of items with tax"""
    if not validate_items(items):
        return 0
    
    subtotal = sum(get_price(item) for item in items)
    tax = subtotal * get_tax_rate()
    return subtotal + tax

def get_price(item):
    """Get price of a single item"""
    base_price = item.get('price', 0)
    if has_discount(item):
        return apply_item_discount(base_price, item)
    return base_price

def get_tax_rate():
    """Get current tax rate"""
    return 0.08  # 8% tax

def has_discount(item):
    """Check if item has discount"""
    return item.get('discount', 0) > 0

def apply_item_discount(price, item):
    """Apply discount to item price"""
    discount = item.get('discount', 0)
    return price * (1 - discount / 100)

def validate_items(items):
    """Validate items before processing"""
    if not items:
        return False
    return all(item.get('price') is not None for item in items)

def process_order(items, customer_discount=0):
    """Process a complete order with customer discount"""
    if not validate_items(items):
        return create_error_response("Invalid items")
    
    total = calculate_total(items)
    final_total = apply_customer_discount(total, customer_discount)
    return create_receipt(items, final_total)

def apply_customer_discount(total, discount_percent):
    """Apply customer-level discount to total"""
    if discount_percent <= 0:
        return total
    return total * (1 - discount_percent / 100)

def create_receipt(items, total):
    """Create receipt for the order"""
    return {
        'items': format_items(items),
        'total': round(total, 2),
        'timestamp': get_timestamp(),
        'processed': True
    }

def create_error_response(message):
    """Create error response"""
    return {
        'error': message,
        'processed': False,
        'timestamp': get_timestamp()
    }

def format_items(items):
    """Format items for receipt"""
    return [
        {
            'name': item.get('name', 'Unknown'),
            'price': get_price(item),
            'quantity': item.get('quantity', 1)
        }
        for item in items
    ]

def get_timestamp():
    """Get current timestamp"""
    import datetime
    return datetime.datetime.now().isoformat()
'''
        self.analyze_code(sample_code, "sample_order_system.py")
        
    def analyze_code(self, code: str, file_path: str, main_script_name: Optional[str] = None):
        """Analyze Python code and visualize dependencies"""
        try:
            # --- FIX: Use the full file_path for analysis ---
            result = self.analyzer.analyze_code(code, file_path)
            
            # If parsing failed, we still proceed to visualize stubs and mark error if available
            had_error = 'error' in result
            self.current_data = result
            
            # Update visualization
            # Provide current file context for runtime flashing
            try:
                self.canvas.current_file_path = file_path
                self.canvas.current_module_base = os.path.splitext(os.path.basename(file_path))[0].lower()
            except Exception:
                pass
            # Capture one-shot skip flag BEFORE set_data resets it, so we can later skip project layout apply
            _skip_proj_apply_once = bool(getattr(self.canvas, '_skip_reset_view_once', False))
            self.canvas.set_data(result['functions'], result['dependencies'], result.get('total_classes', 0), main_script_name)
            # If there was an error, mark the offending function/node in red for immediate visibility
            if had_error:
                try:
                    err_line = int(result.get('error_line') or 0)
                except Exception:
                    err_line = 0
                err_func = (result.get('error_func') or '').strip()
                err_msg = str(result.get('error') or '')
                try:
                    if hasattr(self.canvas, 'mark_error_for_file'):
                        # Mark by file and function, so the function box becomes red
                        self.canvas.mark_error_for_file(file_path, err_func, err_line, err_msg)
                except Exception:
                    pass
            
                        
            # If a project is active, auto-apply any saved layout for this file
            # Skip when reload was triggered by inline editor save (Ctrl+S),
            # which sets a one-shot skip flag on the canvas to avoid overriding positions.
            try:
                if (self._project_doc and file_path) and not _skip_proj_apply_once and not str(file_path).lower().endswith('.rs'):
                    mgr = SaveLoadManager()
                    mgr.apply_project_file_to_canvas(self.canvas, self._project_doc, file_path)
            except Exception:
                pass
            # Apply session-cached layout (takes precedence over project)
            # Skip when inline editor save requested targeted reload to keep current positions
            try:
                if not _skip_proj_apply_once and not str(file_path).lower().endswith('.rs'):
                    self._apply_session_for(file_path)
            except Exception:
                pass
            
            if had_error:
                # Show a non-blocking info about error but keep the visualization visible
                try:
                    QMessageBox.information(self, "Analysis Error", f"Parsed with errors at line {result.get('error_line', 0)}:\n{result.get('error', '')}\n\nYou can fix it now; the offending function is marked in red.")
                except Exception:
                    pass
            else:
                # Clear any lingering error markers so nodes return to default styling
                try:
                    if hasattr(self.canvas, 'clear_error_for_file'):
                        self.canvas.clear_error_for_file(file_path)
                except Exception:
                    pass
                
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to analyze code: {str(e)}")

    def find_containing_function(self, lines, target_line):
        """Find which function contains the given line number"""
        import re
        # Look backwards from target line to find the function definition
        for i in range(target_line - 1, -1, -1):
            line = lines[i].strip()
            if line.startswith('def ') and ':' in line:
                # Extract function name
                func_match = re.match(r'def\s+(\w+)\s*\(', line)
                if func_match:
                    return func_match.group(1)
            elif line.startswith('class ') and ':' in line:
                # If we hit a class definition, we're in a class method
                class_match = re.match(r'class\s+(\w+)', line)
                if class_match:
                    # Look for the method within this class
                    for j in range(i + 1, target_line):
                        method_line = lines[j].strip()
                        if method_line.startswith('def ') and ':' in method_line:
                            method_match = re.match(r'def\s+(\w+)\s*\(', method_line)
                            if method_match:
                                return f"{class_match.group(1)}.{method_match.group(1)}"
        
        return "global scope"
    
    def format_usage_info(self, usage_info, main_script_name):
        """ Formats the usage information into a user-friendly, readable report. """
        # --- Main Header ---
        content = f"✨ Function Connection Report ✨\n"
        content += f"Analyzing how functions from this file are used in '{main_script_name}'\n"
        content += "=" * 70 + "\n\n"

        if not usage_info:
            content += "No direct function usages were found. This is common for UI files where functions are connected to signals or events."
            return content

        # --- Loop through each function that has usages ---
        for func_info in usage_info:
            func_name = func_info['function_name']
            usages = func_info['usages']
            docstring = func_info.get('docstring', 'No description available.').strip()
            args = func_info.get('args', [])

            # --- Function Header ---
            content += f"🔵 Function: {func_name}\n"
            content += "-" * 50 + "\n"
            content += f"   📝 Description: {docstring}\n"
            if args:
                content += f"   📥 Arguments: ({', '.join(args)})\n"
            content += f"   🔗 Found {len(usages)} connection(s) in '{main_script_name}'\n\n"

            # --- Usage Details ---
            for i, usage in enumerate(usages):
                containing_function = usage['containing_function']
                line_num = usage['line']

                # --- Usage Context Header ---
                content += f"   ➡️ Connection #{i+1}: Used in '{containing_function}()' at line {line_num}\n"
                
                # --- Code Snippet ---
                content += "      " + "-" * 40 + "\n"
                # Context before
                for context_line in usage['context_before']:
                    content += f"      {context_line}\n"
                # The actual line, highlighted
                content += f"      >>> {usage['content']}   <-- 🎯 HERE\n"
                # Context after
                for context_line in usage['context_after']:
                    content += f"      {context_line}\n"
                content += "      " + "-" * 40 + "\n\n"

            content += "=" * 70 + "\n\n"

        return content

    def show_activity_panel(self):
        try:
            self.activity_panel.show()
            self.activity_panel.raise_()
            self.activity_panel.move(100, 420)
            self.activity_panel.resize(600, 200)
            try:
                self._sync_activity_title_btn(True)
            except Exception:
                pass
        except Exception:
            pass

    def _toggle_activity_panel_from_title(self, checked: bool):
        try:
            if checked:
                self.show_activity_panel()
            else:
                self.activity_panel.hide()
            try:
                self._sync_activity_title_btn(bool(checked))
            except Exception:
                pass
        except Exception:
            pass

    def _sync_activity_title_btn(self, visible: bool):
        try:
            btn = getattr(self, 'activity_panel_title_btn', None)
            if btn:
                btn.blockSignals(True)
                btn.setChecked(bool(visible))
                btn.blockSignals(False)
                btn.setToolTip("Hide Activity" if visible else "Show Activity")
        except Exception:
            pass

    def set_activity_enabled(self, enabled: bool):
        self.activity_enabled = bool(enabled)
        # Update tooltip to reflect state
        try:
            if hasattr(self, 'activity_toggle_btn'):
                self.activity_toggle_btn.setToolTip("Disable Console" if self.activity_enabled else "Enable Console")
        except Exception:
            pass
        # Keep tracer connected always; only control console spam
        if self.activity_enabled:
            self.show_activity_panel()
        else:
            # Optional: clear previous logs when disabling to reduce clutter
            try:
                self.activity_text.clear()
            except Exception:
                pass

    def _attach_activity_signal(self, attach: bool):
        try:
            terminal = getattr(self, 'python_preview_widget', None)
            if not terminal:
                return
            if attach:
                try:
                    terminal.outputReceived.connect(self.on_terminal_output)
                except Exception:
                    pass
            else:
                try:
                    terminal.outputReceived.disconnect(self.on_terminal_output)
                except Exception:
                    pass
        except Exception:
            pass

    def on_terminal_output(self, text: str):
        # Parse tracer stdout lines to drive highlight without sockets
        try:
            import re
            # Only append concise tracer call lines to reduce UI overhead
            for line in text.splitlines():
                line_s = line.strip()
                if not line_s.startswith("[tracer]"):
                    # Also detect tracer target announcement to clear previous error state for the script
                    try:
                        if line_s.startswith("[tracer] target="):
                            fp = line_s.split("=", 1)[1].strip()
                            if fp and hasattr(self.canvas, 'clear_error_for_file'):
                                self.canvas.clear_error_for_file(fp)
                    except Exception:
                        pass
                    continue
                # Match runtime call events
                m_call = re.search(r"\[tracer\]\s+call:\s+func=([^\s]+)\s+module=([^\s]*)\s+file=(.+)$", line_s)
                # Match error events (emitted by runtime_tracer on exception)
                m_err = re.search(r"\[tracer\]\s+error:\s+file=(.+?)\s+func=([^\s]*)\s+line=(\d+)\s+msg=(.+)$", line_s)
                if m_call:
                    func = m_call.group(1)
                    module = m_call.group(2)
                    file_path = m_call.group(3)
                    # Append compact entry to Activity (only if console enabled)
                    if getattr(self, 'activity_enabled', False):
                        try:
                            self.activity_text.moveCursor(QTextCursor.End)
                            self.activity_text.insertPlainText(f"{func}  <- {os.path.basename(file_path)}\n")
                            self.activity_text.moveCursor(QTextCursor.End)
                        except Exception:
                            pass
                    # Clear any lingering error markers for this file now that a successful call occurred
                    try:
                        if hasattr(self.canvas, 'clear_error_for_file'):
                            self.canvas.clear_error_for_file(file_path)
                    except Exception:
                        pass
                    # Drive canvas directly (creates dynamic node and lights border)
                    try:
                        self.canvas._on_trace_call(func.lower(), module, file_path)
                    except Exception:
                        pass
                elif m_err:
                    file_path = m_err.group(1)
                    func = (m_err.group(2) or '').strip()
                    try:
                        line_no = int(m_err.group(3))
                    except Exception:
                        line_no = 0
                    msg = m_err.group(4)
                    # Log concise error to activity console
                    try:
                        self.activity_text.moveCursor(QTextCursor.End)
                        base = os.path.basename(file_path) if file_path else ''
                        self.activity_text.insertPlainText(f"ERROR in {base}:{line_no} -> {msg}\n")
                        self.activity_text.moveCursor(QTextCursor.End)
                    except Exception:
                        pass
                    # Mark error on canvas (turn module box red, store metadata, and prepare jump)
                    try:
                        if hasattr(self.canvas, 'mark_error_for_file'):
                            self.canvas.mark_error_for_file(file_path, func, line_no, msg)
                    except Exception:
                        pass
        except Exception:
            pass

    def on_code_viewer_closed(self):
        """Handle code viewer being closed"""
        pass  # Nothing special needed for now
    
    def on_text_editor_closed(self):
        """Handle text editor being closed"""
        pass  # Nothing special needed for now
    
    def on_image_editor_closed(self):
        """Handle image editor being closed"""
        pass  # Nothing special needed for now
    
    def on_video_editor_closed(self):
        """Handle video editor being closed"""
        pass  # Nothing special needed for now

    # --------------------- Search overlay ---------------------
    def _build_search_box(self) -> QFrame:
        box = QFrame(self.canvas)
        try:
            box.setWindowFlags(Qt.SubWindow | Qt.FramelessWindowHint)
        except Exception:
            pass
        box.setStyleSheet(
            """
            QFrame {
                background-color: #2C2E33;
                border: 1px solid #4A4D51;
                border-radius: 8px;
                margin: 0px;
            }
            QLabel { color: #E8EAED; background-color: transparent; border: none; }
            QLineEdit {
                background-color: #1E1F22;
                color: #E8EAED;
                border: 1px solid #4A4D51;
                border-radius: 6px;
                padding: 6px 10px;
                min-width: 180px;
            }
            QPushButton { background: transparent; color: #E8EAED; border: none; font-size: 16px; }
            QPushButton:hover { color: #FFFFFF; }
            """
        )
        h = QHBoxLayout(box)
        h.setContentsMargins(8, 8, 8, 8)
        h.setSpacing(5)

        # Left header area with icon above label
        left_container = QWidget()
        # Ensure no background behind the icon area
        try:
            left_container.setAttribute(Qt.WA_TranslucentBackground, True)
        except Exception:
            pass
        left_container.setStyleSheet("background: transparent; border: none;")
        vl = QVBoxLayout(left_container)
        vl.setContentsMargins(2, 2, 2, 2)
        vl.setSpacing(2)
        icon_lbl = QLabel()
        # Make sure the image label itself has no background
        icon_lbl.setStyleSheet("background: transparent; border: none;")
        try:
            icon_lbl.setAttribute(Qt.WA_TranslucentBackground, True)
        except Exception:
            pass
        try:
            pix = QPixmap("img/Manage_Search.png")
            icon_w, icon_h = 60, 60  # Example: set to 50, 50 to make the icon 50x50
            if not pix.isNull():
                pix = pix.scaled(icon_w, icon_h, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                icon_lbl.setPixmap(pix)
                icon_lbl.setFixedSize(pix.size())
        except Exception:
            pass
        vl.addWidget(icon_lbl, 0, Qt.AlignCenter)
        lbl = QLabel("Search")
        lbl.setStyleSheet("color: #60A5FA; font-weight: bold; font-size: 14px; background-color: #2C2E33;")
        vl.addWidget(lbl, 0, Qt.AlignCenter)
        h.addWidget(left_container)

        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("Search function…")
        self._search_input.returnPressed.connect(self._on_search_activate)
        self._search_input.textChanged.connect(self._on_search_text)
        try:
            self._search_input.installEventFilter(self)
        except Exception:
            pass
        h.addWidget(self._search_input, 1)

        # Result counter and navigation
        self._search_count = QLabel("0 to 0")
        self._search_count.setStyleSheet("color: #AAB2BC;")
        h.addWidget(self._search_count)

        self._search_prev_btn = QPushButton("▲")
        self._search_prev_btn.setFixedSize(22, 22)
        self._search_prev_btn.setToolTip("Previous result (Up)")
        self._search_prev_btn.clicked.connect(lambda: self._navigate_search(-1))
        h.addWidget(self._search_prev_btn)

        self._search_next_btn = QPushButton("▼")
        self._search_next_btn.setFixedSize(22, 22)
        self._search_next_btn.setToolTip("Next result (Down)")
        self._search_next_btn.clicked.connect(lambda: self._navigate_search(1))
        h.addWidget(self._search_next_btn)

        close_btn = QPushButton("✕")
        close_btn.clicked.connect(self._hide_search_box)
        h.addWidget(close_btn)

        box.setFixedWidth(420)
        box.adjustSize()
        # Initial position; will be repositioned on show
        box.move(120, 60)
        box.hide()
        return box

    def show_search_box(self):
        if not hasattr(self, '_search_box') or self._search_box is None:
            self._search_box = self._build_search_box()
        # Position top-right similar to guide overlay
        try:
            # Ensure height adapts to content each time it's shown
            self._search_box.adjustSize()
            margin = 30
            x = max(10, self.canvas.width() - self._search_box.width() - margin)
            y = 60
            self._search_box.move(x, y)
        except Exception:
            pass
        self._search_box.show()
        self._search_box.raise_()
        try:
            self._search_input.setFocus()
            self._search_input.selectAll()
        except Exception:
            pass

    # Public entry points for external shortcuts
    def trigger_search(self):
        self.show_search_box()

    def search_next(self):
        self._navigate_search(1)

    def search_prev(self):
        self._navigate_search(-1)

    def _hide_search_box(self):
        try:
            if getattr(self, '_search_box', None) and self._search_box.isVisible():
                self._search_box.hide()
        except Exception:
            pass

    def _on_search_text(self, text: str):
        # If cleared, reset selection and zoom out
        t = (text or "").strip()
        if t == "":
            self._search_matches = []
            self._search_index = -1
            self._update_search_ui()
            try:
                self.canvas.select_node(None)
                self.canvas.reset_view()
            except Exception:
                pass
            return
        # Update matches and live-preview first result
        self._update_search_matches(t)
        self._search_index = 0 if self._search_matches else -1
        self._update_search_ui()
        self._select_current_match(preview=True)

    def _on_search_activate(self):
        # Enter moves to next result; if no query/matches, just recompute
        text = self._search_input.text() if hasattr(self, '_search_input') and self._search_input else ""
        if not text:
            return
        if not self._search_matches:
            self._update_search_matches(text)
            self._search_index = 0 if self._search_matches else -1
            self._update_search_ui()
            self._select_current_match(preview=False)
        else:
            self._navigate_search(1)

    def _focus_node_by_query(self, query: str):
        if not query or not hasattr(self.canvas, 'nodes'):
            return
        q = query.strip().lower()
        if not q:
            return
        nodes = getattr(self.canvas, 'nodes', []) or []
        # Exact match
        match = next((n for n in nodes if (getattr(n, 'name', '') or '').lower() == q), None)
        # Prefix match
        if not match:
            match = next((n for n in nodes if (getattr(n, 'name', '') or '').lower().startswith(q)), None)
        # Substring match
        if not match:
            match = next((n for n in nodes if q in (getattr(n, 'name', '') or '').lower()), None)
        if match:
            try:
                self.canvas.select_node(match)
                self.canvas.focus_on_node(match)
            except Exception:
                pass

    def _update_search_matches(self, query: str):
        """Compute all matching nodes ordered like VS Code: exact, prefix, then substring."""
        try:
            q = (query or '').strip().lower()
            nodes = getattr(self.canvas, 'nodes', []) or []
            matches = []
            if q:
                for n in nodes:
                    name = (getattr(n, 'name', '') or '')
                    nl = name.lower()
                    if nl == q:
                        score = 0
                    elif nl.startswith(q):
                        score = 1
                    elif q in nl:
                        score = 2
                    else:
                        continue
                    matches.append((score, nl, n))
            matches.sort(key=lambda t: (t[0], t[1]))
            self._search_matches = [t[2] for t in matches]
        except Exception:
            self._search_matches = []

    def _select_current_match(self, preview: bool = False):
        """Select and focus the current match index."""
        try:
            if not self._search_matches or self._search_index < 0 or self._search_index >= len(self._search_matches):
                return
            node = self._search_matches[self._search_index]
            self.canvas.select_node(node)
            self.canvas.focus_on_node(node)
        except Exception:
            pass

    def _navigate_search(self, step: int):
        """Move selection up/down within current matches (wrap-around)."""
        try:
            if not self._search_matches:
                text = self._search_input.text() if hasattr(self, '_search_input') and self._search_input else ''
                self._update_search_matches(text)
                if not self._search_matches:
                    self._search_index = -1
                    self._update_search_ui()
                    return
                self._search_index = 0
            else:
                n = len(self._search_matches)
                self._search_index = (self._search_index + (step or 0)) % n
            self._update_search_ui()
            self._select_current_match(preview=False)
        except Exception:
            pass

    def _update_search_ui(self):
        try:
            total = len(self._search_matches) if hasattr(self, '_search_matches') and self._search_matches is not None else 0
            idx = (self._search_index + 1) if (hasattr(self, '_search_index') and self._search_index >= 0 and total > 0) else 0
            if hasattr(self, '_search_count') and self._search_count:
                self._search_count.setText(f"{idx} to {total}")
            # Enable/disable nav buttons
            enable = total > 1
            for btn in (getattr(self, '_search_prev_btn', None), getattr(self, '_search_next_btn', None)):
                if btn:
                    btn.setEnabled(enable)
        except Exception:
            pass

    def eventFilter(self, obj, event):
        try:
            # Pre-empt global QAction conflicts by handling shortcut override first
            if event.type() == QEvent.ShortcutOverride:
                if (event.modifiers() & Qt.ControlModifier) and event.key() == Qt.Key_F:
                    self.trigger_search()
                    event.accept()
                    return True
                if event.key() == Qt.Key_F3:
                    if event.modifiers() & Qt.ShiftModifier:
                        self.search_prev()
                    else:
                        self.search_next()
                    event.accept()
                    return True
            if event.type() == QEvent.KeyPress:
                if event.key() == Qt.Key_Escape:
                    self._hide_search_box()
                    return True
                # Global handling when Manage widget or children have focus
                if (event.modifiers() & Qt.ControlModifier) and event.key() == Qt.Key_F:
                    self.trigger_search()
                    return True
                if event.key() == Qt.Key_F3:
                    if event.modifiers() & Qt.ShiftModifier:
                        self.search_prev()
                    else:
                        self.search_next()
                    return True
                # Search input specific navigation
                if obj is getattr(self, '_search_input', None):
                    if event.key() in (Qt.Key_Down,):
                        self._navigate_search(1)
                        return True
                    if event.key() in (Qt.Key_Up,):
                        self._navigate_search(-1)
                        return True
        except Exception:
            pass
        return super().eventFilter(obj, event)

    def keyPressEvent(self, event):
        """Number row 1-5 switches annotation tools and color picker."""
        try:
            key = event.key()
            if key in (Qt.Key_1, Qt.Key_2, Qt.Key_3, Qt.Key_4, Qt.Key_5):
                # Do not consume number shortcuts while inline text editor is open
                try:
                    te = getattr(self.canvas, '_text_editor', None)
                    if te is not None and te.isVisible():
                        # Let the line edit handle typing; do not consume
                        super().keyPressEvent(event)
                        return
                except Exception:
                    pass
                try:
                    if not self.annotation_toolbar.isVisible():
                        # Show annotation toolbar via top right button
                        if hasattr(self, 'top_toolbar') and hasattr(self.top_toolbar, 'text_brush_btn'):
                            self.top_toolbar.text_brush_btn.setChecked(True)
                except Exception:
                    pass
                if key == Qt.Key_1:
                    self._set_annotation_tool('cursor')
                elif key == Qt.Key_2:
                    self._set_annotation_tool('brush')
                elif key == Qt.Key_3:
                    self._set_annotation_tool('text')
                elif key == Qt.Key_4:
                    self._set_annotation_tool('erase')
                elif key == Qt.Key_5:
                    self.on_pick_annotation_color()
                event.accept()
                return
        except Exception:
            pass
        super().keyPressEvent(event)

    # --------------------- Annotation helpers ---------------------
    def _position_annotation_toolbar(self):
        try:
            w = self.annotation_toolbar.sizeHint().width()
            h = self.annotation_toolbar.sizeHint().height()
            x = max(10, (self.canvas.width() - w) // 2)
            y = max(10, self.canvas.height() - h - 20)
            self.annotation_toolbar.setFixedSize(w, h)
            self.annotation_toolbar.move(x, y)
        except Exception:
            pass

    def toggle_annotation_toolbar(self, checked: bool):
        try:
            self.annotation_toolbar.setVisible(bool(checked))
            if checked:
                self.brush_tool_btn.setChecked(True)
                self.text_tool_btn.setChecked(False)
                self._set_annotation_tool('brush')
                self._position_annotation_toolbar()
            else:
                if hasattr(self.canvas, 'set_tool_mode'):
                    self.canvas.set_tool_mode(None)
            # Sync the top right toolbar button state
            try:
                if hasattr(self, 'top_toolbar') and hasattr(self.top_toolbar, 'text_brush_btn'):
                    self.top_toolbar.text_brush_btn.blockSignals(True)
                    self.top_toolbar.text_brush_btn.setChecked(checked)
                    self.top_toolbar.text_brush_btn.blockSignals(False)
            except Exception:
                pass
        except Exception:
            pass

    def _set_annotation_tool(self, mode: str):
        try:
            if mode == 'cursor':
                self.brush_tool_btn.setChecked(False)
                self.text_tool_btn.setChecked(False)
                self.erase_tool_btn.setChecked(False)
                self.cursor_tool_btn.setChecked(True)
            elif mode == 'brush':
                self.cursor_tool_btn.setChecked(False)
                self.text_tool_btn.setChecked(False)
                self.erase_tool_btn.setChecked(False)
                self.brush_tool_btn.setChecked(True)
            elif mode == 'text':
                self.cursor_tool_btn.setChecked(False)
                self.brush_tool_btn.setChecked(False)
                self.erase_tool_btn.setChecked(False)
                self.text_tool_btn.setChecked(True)
            elif mode == 'erase':
                self.cursor_tool_btn.setChecked(False)
                self.brush_tool_btn.setChecked(False)
                self.text_tool_btn.setChecked(False)
                self.erase_tool_btn.setChecked(True)
            if hasattr(self.canvas, 'set_tool_mode'):
                self.canvas.set_tool_mode(mode)
        except Exception:
            pass

    def on_pick_annotation_color(self):
        try:
            from PySide6.QtGui import QColor as _QColor
            init = getattr(self.canvas, 'draw_color', _QColor('#FFFFFF')) if hasattr(self.canvas, 'draw_color') else _QColor('#FFFFFF')
            color = QColorDialog.getColor(init, self, 'Pick Annotation Color')
            if color and color.isValid():
                if hasattr(self.canvas, 'set_current_color'):
                    self.canvas.set_current_color(color, apply_to_selection=True)
        except Exception:
            pass

    # ------------ Canvas -> Manage host handlers for menu actions ------------
    def on_canvas_request_stop_python(self):
        """Stop the running tracer/python process in the embedded Python Preview terminal."""
        try:
            terminal = getattr(self, 'python_preview_widget', None)
            proc = getattr(terminal, 'process', None) if terminal else None
            if proc and proc.state() != 0:
                try:
                    proc.kill()
                    proc.waitForFinished(1000)
                except Exception:
                    pass
            # Also clear Activity focus state promptly
            try:
                self.canvas.runtime_focus_mode = False
                self.canvas._ever_active_nodes = set()
            except Exception:
                pass
        except Exception:
            pass

    def on_canvas_request_toggle_activity(self, desired_enabled: bool):
        """Toggle Activity console parsing on/off when requested from canvas menu."""
        try:
            self.set_activity_enabled(bool(desired_enabled))
        except Exception:
            pass
    
    # --------------------- Connection Drag Workflow (100% same as Manage2) ---------------------
    def on_connection_drag_completed(self, source_node, world_x, world_y):
        """
        Handle connection drag completion - show choice dialog first
        
        This is STEP 1 of the connection drag workflow:
        1. User drags from node border to empty space
        2. Show choice dialog (Rust or Custom)
        3a. If Rust: Show file selection dialog → function selection dialog
        3b. If Custom: Show custom content dialog (TODO)
        4. Create new node at drop location
        5. Create UI connection between source and new node
        
        Args:
            source_node: The node where the drag started
            world_x: World X coordinate where drag ended
            world_y: World Y coordinate where drag ended
        """
        try:
            # Store drag context for later steps
            self._connection_drag_source = source_node
            self._connection_drag_position = (world_x, world_y)
            self._connection_drag_files = []
            
            # Import choice dialog from visualization_core3
            from .visualization_core3 import ConnectionTypeChoiceDialog
            
            # Show choice dialog
            self.choice_dialog = ConnectionTypeChoiceDialog(self)
            self.choice_dialog.choice_made.connect(self.on_connection_type_chosen)
            self.choice_dialog.exec()
            
        except Exception as e:
            print(f"[ManageWidget] Error in connection drag: {e}")
            import traceback
            traceback.print_exc()
    
    def on_connection_type_chosen(self, choice_type):
        """
        STEP 2: Handle choice selection (Rust or Custom)
        
        Args:
            choice_type: "rust" or "custom"
        """
        try:
            # Close the first dialog explicitly
            if hasattr(self, 'choice_dialog') and self.choice_dialog:
                self.choice_dialog.close()
                self.choice_dialog = None
            
            if choice_type == "rust":
                # Continue with Rust workflow
                self._show_rust_file_selection()
            elif choice_type == "custom":
                # Show custom content type dialog
                self._show_custom_content_selection()
        except Exception as e:
            print(f"[ManageWidget] Error in choice selection: {e}")
            import traceback
            traceback.print_exc()
    
    def _show_rust_file_selection(self):
        """Show Rust file selection dialog"""
        try:
            # Get current root path dynamically from file browser
            root_path = self._get_current_file_browser_root()
            print(f"[ManageWidget] Opening Rust file dialog with root: {root_path}")
            
            # Import dialog from visualization_core3
            from .visualization_core3 import ConnectionFileSelectionDialog
            
            # Show file selection dialog
            file_dialog = ConnectionFileSelectionDialog(root_path, self)
            file_dialog.files_selected.connect(self.on_connection_files_selected)
            file_dialog.exec()
            
        except Exception as e:
            print(f"[ManageWidget] Error showing file selection: {e}")
            import traceback
            traceback.print_exc()
    
    def _get_current_file_browser_root(self):
        """
        Get the current root path from the file browser dynamically.
        This ensures dialogs open in the currently browsed folder.
        
        Priority order:
        1. Last opened folder from settings (VS Code-like behavior)
        2. Current file browser root
        3. Parent window file browser root
        4. Project root directory
        5. Current working directory
        
        Returns:
            str: Current root path from file browser, or fallback
        """
        try:
            # Priority 1: Try to get last opened folder from settings (VS Code-like)
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
                            print(f"[ManageWidget] Got root from settings (last_folder): {last_folder}")
                            return last_folder
            except Exception as e:
                print(f"[ManageWidget] Error getting last_folder from settings: {e}")
            
            # Priority 2: Try to get current root from file browser
            if hasattr(self, 'file_tree') and hasattr(self, 'file_model') and hasattr(self, 'proxy_model'):
                try:
                    src_idx = self.proxy_model.mapToSource(self.file_tree.rootIndex())
                    root_path = self.file_model.filePath(src_idx)
                    if root_path and os.path.isdir(root_path):
                        print(f"[ManageWidget] Got root from file browser: {root_path}")
                        return root_path
                except Exception as e:
                    print(f"[ManageWidget] Error getting root from file browser: {e}")
            
            # Priority 3: Try parent window (for manage_native.py wrapper)
            try:
                parent_window = self.window()
                if parent_window and parent_window != self:
                    if hasattr(parent_window, 'tree_view') and hasattr(parent_window, 'file_model'):
                        proxy_model = getattr(parent_window, 'proxy_model', None)
                        if proxy_model:
                            src_idx = proxy_model.mapToSource(parent_window.tree_view.rootIndex())
                            root_path = parent_window.file_model.filePath(src_idx)
                            if root_path and os.path.isdir(root_path):
                                print(f"[ManageWidget] Got root from parent window: {root_path}")
                                return root_path
            except Exception as e:
                print(f"[ManageWidget] Error getting root from parent: {e}")
            
            # Priority 4: Use get_project_root_directory
            root_path = self.get_project_root_directory()
            if root_path and os.path.exists(root_path):
                print(f"[ManageWidget] Got root from project directory: {root_path}")
                return root_path
                
        except Exception as e:
            print(f"[ManageWidget] Error in _get_current_file_browser_root: {e}")
            import traceback
            traceback.print_exc()
        
        # Final fallback: current working directory
        fallback = os.getcwd()
        print(f"[ManageWidget] Using fallback root: {fallback}")
        return fallback
    
    def _show_custom_content_selection(self):
        """Show custom content type selection dialog"""
        try:
            print("[ManageWidget] Showing custom content selection dialog...")
            
            # Import dialog from visualization_core3
            from .visualization_core3 import CustomContentTypeDialog
            
            # Show custom content type dialog
            content_dialog = CustomContentTypeDialog(self)
            print(f"[ManageWidget] Dialog created: {content_dialog}")
            
            content_dialog.content_type_selected.connect(self.on_custom_content_type_selected)
            
            # Make sure dialog is visible and on top
            content_dialog.show()
            content_dialog.raise_()
            content_dialog.activateWindow()
            
            result = content_dialog.exec()
            print(f"[ManageWidget] Dialog result: {result}")
            
        except Exception as e:
            print(f"[ManageWidget] Error showing custom content selection: {e}")
            import traceback
            traceback.print_exc()
    
    def on_custom_content_type_selected(self, content_type):
        """
        Handle custom content type selection (text, image, video)
        Create a custom content node at the drag position
        
        Args:
            content_type: "text", "image", or "video"
        """
        try:
            print(f"[ManageWidget] Custom content type selected: {content_type}")
            
            # Get stored context
            source_node = getattr(self, '_connection_drag_source', None)
            position = getattr(self, '_connection_drag_position', (0, 0))
            
            if not source_node:
                print("[ManageWidget] No source node found")
                return
            
            world_x, world_y = position
            
            # Create custom content node data
            from .data_analysis import FunctionNode, Connection
            import random
            
            # Generate color based on content type
            if content_type == "text":
                node_color = '#4FC3F7'  # Cyan/Blue for text
                node_title = "Text Content"
            elif content_type == "image":
                node_color = '#1c087a'  # Deep purple for image
                node_title = "Image Content"
            elif content_type == "video":
                node_color = '#541a4c'  # Dark magenta for video
                node_title = "Video Content"
            else:
                node_color = '#9AA0A6'  # Gray default
                node_title = "Custom Content"
            
            # Create node data (same structure as Rust function nodes)
            data = {
                'name': node_title,
                'lineno': 0,
                'args': [],
                'docstring': f'{content_type.capitalize()} content node',
                'returns': '',
                'complexity': 1,
                'type': content_type,
                'content_type': content_type,  # Mark as custom content
                'file_path': None,
                'source_code': ''
            }
            
            # Create the node at drop position
            node = FunctionNode(data, world_x, world_y)
            node.color = node_color
            
            # Add to canvas
            self.canvas.nodes.append(node)
            
            # Index the node
            if hasattr(self.canvas, '_index_node'):
                self.canvas._index_node(node)
            
            # Create UI-only connection from source to new node
            connection = Connection(source_node, node)
            self.canvas.connections.append(connection)
            
            # Push undo action for adding the node and connection
            try:
                if hasattr(self.canvas, '_push_undo'):
                    self.canvas._push_undo({
                        'type': 'add_connection_node',
                        'node': node,
                        'connection': connection
                    })
            except Exception as e:
                print(f"[ManageWidget] Error pushing undo: {e}")
            
            # Clear drag context
            self._connection_drag_source = None
            self._connection_drag_position = None
            self._connection_drag_files = []
            
            # Update canvas
            self.canvas.update()
            
            print(f"[ManageWidget] Created {content_type} content node at ({world_x}, {world_y})")
            
        except Exception as e:
            print(f"[ManageWidget] Error in custom content type selection: {e}")
            import traceback
            traceback.print_exc()
    
    def on_connection_files_selected(self, file_paths):
        """
        STEP 2: Handle files selected from connection drag dialog
        
        Args:
            file_paths: List of selected .rs file paths
        """
        try:
            # Store selected files
            self._connection_drag_files = file_paths
            
            # Import dialog from visualization_core3
            from .visualization_core3 import ConnectionFunctionSelectionDialog
            
            # Get existing node names from canvas to prevent duplicates
            existing_nodes = [node.name for node in self.canvas.nodes if not getattr(node, 'is_add_tool', False)]
            
            # Show function selection dialog with existing nodes filter
            func_dialog = ConnectionFunctionSelectionDialog(file_paths, self, existing_nodes)
            func_dialog.function_selected.connect(self.on_connection_function_selected)
            func_dialog.exec()
            
        except Exception as e:
            print(f"[ManageWidget] Error in file selection: {e}")
            import traceback
            traceback.print_exc()
    
    def on_connection_function_selected(self, name, func_type):
        """
        STEP 3: Handle function selected - create node and connection
        
        Args:
            name: Function/struct/impl name
            func_type: Type of item ("Function", "Struct", "Implementation")
        """
        try:
            # Get stored context
            source_node = getattr(self, '_connection_drag_source', None)
            position = getattr(self, '_connection_drag_position', (0, 0))
            file_paths = getattr(self, '_connection_drag_files', [])
            
            if not source_node or not file_paths:
                return
            
            world_x, world_y = position
            
            # Find source file and extract code
            source_file = None
            source_code = None
            try:
                for file_path in file_paths:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        lines = content.split('\n')
                        
                        # Build search pattern based on type
                        if func_type == "Function":
                            # For functions, look for "fn name(" or "pub fn name("
                            search_patterns = [
                                f'fn {name}(',
                                f'pub fn {name}(',
                            ]
                        elif func_type == "Struct":
                            # For structs, look for "struct name" or "pub struct name"
                            search_patterns = [
                                f'struct {name}',
                                f'pub struct {name}',
                            ]
                        elif func_type == "Implementation":
                            # For impl blocks, the name includes "impl " prefix
                            # Remove "impl " prefix if present in name
                            impl_name = name.replace('impl ', '').strip()
                            search_patterns = [
                                f'impl {impl_name}',
                                f'pub impl {impl_name}',
                            ]
                        else:
                            search_patterns = [name]
                        
                        # Search for the exact pattern
                        found = False
                        for i, line in enumerate(lines):
                            # Check if any search pattern matches this line
                            if any(pattern in line for pattern in search_patterns):
                                source_file = file_path
                                # Extract the code block
                                start = i
                                brace_count = 0
                                found_start = False
                                end = start
                                
                                for j in range(start, len(lines)):
                                    if '{' in lines[j]:
                                        brace_count += lines[j].count('{')
                                        found_start = True
                                    if '}' in lines[j]:
                                        brace_count -= lines[j].count('}')
                                    if found_start and brace_count == 0:
                                        end = j
                                        break
                                
                                source_code = '\n'.join(lines[start:end+1])
                                found = True
                                break
                        
                        if found:
                            break
            except Exception as e:
                print(f"[ManageWidget] Error extracting code: {e}")
            
            # Create function node data
            from .data_analysis import FunctionNode, Connection
            import random
            
            # Generate random color for the node
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
            random_color = random.choice(colors)
            
            data = {
                'name': name,
                'lineno': 0,
                'args': [],
                'docstring': f'{func_type} from Rust file',
                'returns': '',
                'complexity': 1,
                'type': func_type,
                'file_path': source_file,
                'source_code': source_code
            }
            
            # Create the function node at drop position
            node = FunctionNode(data, world_x, world_y)
            node.color = random_color  # Random color for variety
            
            # Add to canvas
            self.canvas.nodes.append(node)
            
            # Index the node
            if hasattr(self.canvas, '_index_node'):
                self.canvas._index_node(node)
            
            # Create UI-only connection from source to new node
            connection = Connection(source_node, node)
            self.canvas.connections.append(connection)
            
            # Push undo action for adding the node and connection
            try:
                if hasattr(self.canvas, '_push_undo'):
                    self.canvas._push_undo({
                        'type': 'add_connection_node',
                        'node': node,
                        'connection': connection
                    })
            except Exception as e:
                print(f"[ManageWidget] Error pushing undo: {e}")
            
            # Clear drag context
            self._connection_drag_source = None
            self._connection_drag_position = None
            self._connection_drag_files = []
            
            # Update canvas
            self.canvas.update()
            
            print(f"[ManageWidget] Created connection from {source_node.name} to {name}")
            
        except Exception as e:
            print(f"[ManageWidget] Error creating connection node: {e}")
            import traceback
            traceback.print_exc()

    # --------------------- Session cache helpers ---------------------
    def _capture_session_for_current(self):
        """Capture current canvas layout into the in-memory session cache for the current file."""
        try:
            cur = getattr(self.analyzer, 'current_file_path', None)
            if not cur:
                return
            # Only capture if we have nodes
            if not getattr(self.canvas, 'nodes', None):
                return
            mgr = SaveLoadManager()
            state = mgr.collect_state(self)
            # Also persist hidden connections by name pairs
            state['hidden_connections'] = self._collect_hidden_connections()
            self._session_layouts[os.path.abspath(cur)] = state
        except Exception:
            pass

    def _collect_hidden_connections(self):
        hidden = []
        try:
            for c in getattr(self.canvas, 'connections', []) or []:
                if getattr(c, 'hidden', False):
                    fn = (getattr(c.from_node, 'name', '') or '')
                    tn = (getattr(c.to_node, 'name', '') or '')
                    if fn and tn:
                        hidden.append({'from': fn, 'to': tn})
        except Exception:
            pass
        return hidden

    def _apply_session_for(self, file_path: str):
        try:
            key = os.path.abspath(file_path) if file_path else None
            if not key:
                return
            state = self._session_layouts.get(key)
            if not state:
                return
            mgr = SaveLoadManager()
            mgr.apply_to_canvas(self.canvas, state)
            mgr.apply_panel_positions(self, state)
            self._apply_hidden_connections(state)
        except Exception:
            pass

    def _apply_hidden_connections(self, state: dict):
        try:
            hidden = state.get('hidden_connections') or []
            hidden_set = set()
            for item in hidden:
                fn = (item.get('from', '') or '').lower()
                tn = (item.get('to', '') or '').lower()
                if fn and tn:
                    hidden_set.add((fn, tn))
            for c in getattr(self.canvas, 'connections', []) or []:
                fn = (getattr(c.from_node, 'name', '') or '').lower()
                tn = (getattr(c.to_node, 'name', '') or '').lower()
                if (fn, tn) in hidden_set:
                    setattr(c, 'hidden', True)
            try:
                self.canvas.update()
            except Exception:
                pass
        except Exception:
            pass

    # Import methods from main_widget2
    load_file = main_widget2.load_file
    find_main_script = main_widget2.find_main_script
    get_project_root_directory = main_widget2.get_project_root_directory
    file_imports_module_flexible = main_widget2.file_imports_module_flexible
    file_imports_module = main_widget2.file_imports_module
    toggle_panel_visibility = main_widget2.toggle_panel_visibility
    on_node_selected = main_widget2.on_node_selected
    on_node_double_clicked = main_widget2.on_node_double_clicked
    show_function_code_viewer = main_widget2.show_function_code_viewer
    show_function_usage_viewer = main_widget2.show_function_usage_viewer
    find_function_usage = main_widget2.find_function_usage
    find_class_name_in_module = main_widget2.find_class_name_in_module
    on_canvas_request_open_file = main_widget2.on_canvas_request_open_file
    on_canvas_request_open_editor = main_widget2.on_canvas_request_open_editor
    _resolve_main_script_path = main_widget2._resolve_main_script_path
    _is_standalone_script = main_widget2._is_standalone_script
    run_python_script = main_widget2.run_python_script
    _build_warning_box = main_widget2._build_warning_box
    _show_main_warning_box = main_widget2._show_main_warning_box
    _highlight_main_node_red = main_widget2._highlight_main_node_red
    _maybe_show_main_warning_for = main_widget2._maybe_show_main_warning_for
    get_function_code = main_widget2.get_function_code


