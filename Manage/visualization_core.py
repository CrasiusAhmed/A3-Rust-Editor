"""
Visualization Core Module
Contains the main canvas and visualization logic
"""

import math
from typing import Dict, List, Optional, Any

from PySide6.QtCore import (
    Qt, QTimer, QPropertyAnimation, QEasingCurve, QParallelAnimationGroup,
    QRectF, QPointF, Signal, Property, QElapsedTimer
)
from PySide6.QtGui import (
    QPainter, QPen, QBrush, QColor, QFont, QFontMetrics, QPainterPath,
    QLinearGradient, QRadialGradient, QPixmap, QWheelEvent, QMouseEvent, 
    QPaintEvent, QKeyEvent, QResizeEvent
)
from PySide6.QtWidgets import QWidget, QMenu, QMessageBox, QFileDialog, QLineEdit
# Apply app-wide context menu styling to Manage menus
try:
    from Main.menu_style_right_click import apply_default_menu_style
except Exception:
    apply_default_menu_style = None

# Runtime tracing support
import socket
import threading
import json
import time
import os

# Document save/load
try:
    from .document_io import SaveLoadManager
except Exception:
    SaveLoadManager = None

# Debug logging helper (writes to file and prints)
ENABLE_TRACE_SERVER = False
TRACE_DEBUG = False

def _trace_log(msg: str):
    if not TRACE_DEBUG:
        return
    try:
        path = os.path.join(os.path.dirname(__file__), 'trace_debug.log')
        with open(path, 'a', encoding='utf-8') as f:
            f.write(str(msg) + '\n')
    except Exception:
        pass
    try:
        print(f"[canvas] {msg}")
    except Exception:
        pass

from .data_analysis import DARK_THEME, FunctionNode, Connection, FunctionAnalyzer
from .ui_components import ResizablePanel, ResizableCodeViewer
from .annotation_tools import AnnotationTools

class VisualizationCanvas(QWidget):
    """Main canvas for function dependency visualization"""
    
    node_selected = Signal(object)  # Emits selected node
    node_double_clicked = Signal(object)  # Emits double-clicked node
    trace_called = Signal(str)  # Emits function name when runtime call received
    connection_drag_completed = Signal(object, float, float)  # Emits (source_node, world_x, world_y) when connection drag completes
    # Context menu actions delegated to host widget
    request_open_file = Signal(str)
    request_open_editor = Signal(object, str)
    request_stop_python = Signal()
    request_remove_file = Signal()
    request_toggle_activity = Signal(bool)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(800, 600)
        self.setFocusPolicy(Qt.StrongFocus)
        
        # Data
        self.nodes: List[FunctionNode] = []
        self.connections: List[Connection] = []
        self.selected_node: Optional[FunctionNode] = None
        self.hovered_node: Optional[FunctionNode] = None
        
        # Camera
        self.camera_x = 0.0
        self.camera_y = 0.0
        self.camera_zoom = 1.0
        self.target_zoom = 1.0
        
        # Mouse interaction
        self.mouse_down = False
        self.last_mouse_x = 0
        self.last_mouse_y = 0
        self.dragging = False
        
        # Animation timer with adaptive frame rate
        self.animation_timer = QTimer()
        self.animation_timer.timeout.connect(self.update_animation)
        self.animation_timer.start(33)  # ~30 FPS to reduce load
        
        # Performance optimization flags
        self._viewport_culling = True  # Only render visible nodes
        self._dirty = True  # Track if redraw is needed
        self._last_camera_state = (0.0, 0.0, 1.0)  # Track camera changes
        self._idle_frames = 0  # Count frames without changes
        self._max_idle_fps = 10  # Reduce to 10 FPS when idle
        
        # Timer for delta-time calculation
        self.elapsed_timer = QElapsedTimer()
        self.elapsed_timer.start()
        
        # Dimension settings
        self.width_multiplier = 2.5
        self.height_multiplier = 1.7
        self.hover_scale = 1.15
        self.main_node_icon_size = 70
        
        # Style with scrollbar styling
        try:
            from file_showen import apply_modern_scrollbar_style
            scrollbar_style = apply_modern_scrollbar_style()
        except Exception:
            scrollbar_style = ""
        
        self.setStyleSheet(f"""
            VisualizationCanvas {{
                background-color: {DARK_THEME['bg_primary']};
                border: 1px solid {DARK_THEME['border']};
                border-radius: 8px;
            }}
            {scrollbar_style}
        """)

        # --- Live tracing server state ---
        self._trace_server_thread: Optional[threading.Thread] = None
        self._trace_server_stop = threading.Event()
        self._trace_server_port: Optional[int] = None
        self._last_flash_time: float = 0.0
        # Duration (seconds) to keep a node in runtime-active state after last call
        self._active_duration: float = 0.45
        # Mapping from absolute file path to aggregated external module nodes
        self._module_nodes = {}
        # Track error states by file (abs path -> {'func','line','msg'})
        self._file_errors = {}
        # When True, dim nodes that have never been used during runtime; default off
        self.runtime_focus_mode = False
        # Track nodes that have been used at least once during current run session
        self._ever_active_nodes = set()
        # Timestamp of last trace activity to auto-exit focus mode when run ends
        self._last_activity_time = 0.0
        # UI undo/redo stacks (UI-only actions)
        self._undo_stack = []
        self._redo_stack = []
        # Drag/move tracking for node position undo/redo
        self._drag_node: Optional[FunctionNode] = None
        self._drag_start_pos: Optional[tuple] = None
        self._node_moved: bool = False

        # Annotation state (delegated)
        try:
            from PySide6.QtGui import QColor as _QColor
            self.draw_color = _QColor('#FFFFFF')
        except Exception:
            self.draw_color = None
        self.tool_mode: Optional[str] = None   # None, 'cursor', 'brush', 'text'
        self._strokes: list = []
        self._current_stroke: Optional[dict] = None
        self._texts: list = []
        self._selected_text = None
        self._text_editor: Optional[QLineEdit] = None
        self._drag_text = None
        self._drag_text_offset = (0.0, 0.0)
        self._resizing_text = None
        self._resize_start = (0, 14.0)
        self._editing_text_ref = None
        self.annotations = AnnotationTools(self)
        # Enable restoring previous positions so manual moves are preserved
        self.restore_previous_positions = True
        
        # Selection box mode state
        self._selection_box_mode = False
        self._selection_box_active = False
        self._selection_box_start = None
        self._selection_box_end = None
        self._selection_box_nodes = []
        
        # Blender-style transform mode (G key for grab/move)
        self._transform_mode = None  # None, 'grab', 'grab_x', 'grab_y'
        self._transform_start_pos = None
        self._transform_start_nodes = []  # List of (node, original_x, original_y)
        self._transform_mouse_start = None

    @Property(float)
    def camera_x_prop(self):
        return self.camera_x

    @camera_x_prop.setter
    def camera_x_prop(self, value):
        self.camera_x = value
        self.update()

    @Property(float)
    def camera_y_prop(self):
        return self.camera_y

    @camera_y_prop.setter
    def camera_y_prop(self, value):
        self.camera_y = value
        self.update()

    @Property(float)
    def camera_zoom_prop(self):
        return self.camera_zoom

    @camera_zoom_prop.setter
    def camera_zoom_prop(self, value):
        self.camera_zoom = value
        self.update()
        
    def set_data(self, functions: Dict[str, Any], dependencies: Dict[str, List[str]], class_count: int, main_script_name: Optional[str]):
        """Set the function data and create visualization"""
        # Capture previous positions AND selection to preserve layout across re-analysis of the same file
        prev_file = getattr(self, 'current_file_path', None)
        _prev_by_id = {}
        _prev_by_name = {}
        _prev_selected_name = None
        try:
            if getattr(self, 'nodes', None):
                import os as _osmod
                _prev_abs = _osmod.path.abspath(prev_file) if prev_file else None
                _mgr = SaveLoadManager() if SaveLoadManager else None
                # Remember which node was selected
                if self.selected_node:
                    _prev_selected_name = self.selected_node.name
                for _n in list(self.nodes):
                    try:
                        if _mgr:
                            _nid = _mgr.compute_node_id(_n, fallback_file=_prev_abs)
                        else:
                            _nid = (str(getattr(_n, 'name', '') or '').lower())
                        _pos = (float(getattr(_n, 'x', 0.0) or 0.0), float(getattr(_n, 'y', 0.0) or 0.0))
                        _prev_by_id[_nid] = _pos
                        _prev_by_name[str(getattr(_n, 'name', '') or '').lower()] = _pos
                    except Exception:
                        pass
        except Exception:
            pass
        self.clear()
        self.main_script_name = main_script_name
        
        if not functions and class_count == 0:
            return

        # Create nodes
        self._layout_nodes(functions, dependencies)

        # Always create normal connections first
        self._create_connections(dependencies)

        # Use square-grid layout only; skip legacy adjustment passes to preserve orthogonality
        
        # Skip creating a central main-script connection to preserve orthogonal layout

        # Re-apply previous positions when reloading the same file (guarded)
        try:
            if getattr(self, 'restore_previous_positions', False):
                import os as _osmod
                _cur_abs = _osmod.path.abspath(getattr(self, 'current_file_path', '') or '')
                _prev_abs = _osmod.path.abspath(prev_file or '') if prev_file else ''
                if _prev_by_id and _prev_abs and _cur_abs and _prev_abs == _cur_abs:
                    _mgr = SaveLoadManager() if SaveLoadManager else None
                    for _n in list(self.nodes):
                        try:
                            # Skip special nodes such as the main script icon node
                            if getattr(_n, 'icon_path', None):
                                continue
                            if _mgr:
                                _nid = _mgr.compute_node_id(_n, fallback_file=_cur_abs)
                            else:
                                _nid = (str(getattr(_n, 'name', '') or '').lower())
                            _pos = _prev_by_id.get(_nid) or _prev_by_name.get(str(getattr(_n, 'name', '') or '').lower())
                            if _pos and isinstance(_pos, tuple) and len(_pos) == 2:
                                _n.x, _n.y = float(_pos[0]), float(_pos[1])
                                _n.original_x, _n.original_y = _n.x, _n.y
                        except Exception:
                            pass
        except Exception:
            pass

        # Apply pending error marker for this file (if any)
        try:
            import os as _os
            cur = getattr(self, 'current_file_path', None)
            if cur and hasattr(self, '_file_errors'):
                err = self._file_errors.get(_os.path.abspath(cur))
                if err:
                    fname = (err.get('func') or '').lower()
                    node = None
                    try:
                        node = getattr(self, '_node_by_name', {}).get(fname)
                    except Exception:
                        node = None
                    if node:
                        try:
                            setattr(node, 'error_state', {'line': int(err.get('line') or 0), 'msg': err.get('msg') or ''})
                            if isinstance(node.data, dict):
                                node.data['error_line'] = int(err.get('line') or 0)
                                node.data['error_msg'] = err.get('msg') or ''
                        except Exception:
                            pass
                else:
                    # No pending error for current file: ensure previous error markers are cleared
                    try:
                        for n in list(getattr(self, 'nodes', []) or []):
                            try:
                                if hasattr(n, 'error_state'):
                                    delattr(n, 'error_state')
                            except Exception:
                                try:
                                    n.error_state = None
                                except Exception:
                                    pass
                            try:
                                if isinstance(getattr(n, 'data', None), dict):
                                    n.data.pop('error_line', None)
                                    n.data.pop('error_msg', None)
                            except Exception:
                                pass
                    except Exception:
                        pass
        except Exception:
            pass

        # Restore previous selection if same file
        try:
            if _prev_selected_name and _prev_abs and _cur_abs and _prev_abs == _cur_abs:
                for _n in self.nodes:
                    if _n.name == _prev_selected_name:
                        self.select_node(_n)
                        break
        except Exception:
            pass

        # Reset view to fit all nodes unless skipped for a targeted reload
        if getattr(self, '_skip_reset_view_once', False):
            try:
                self._skip_reset_view_once = False
            except Exception:
                pass
        else:
            self.reset_view()
        
        self.update()

        # Start trace server when data is set (optional)
        if ENABLE_TRACE_SERVER:
            try:
                self._ensure_trace_server()
            except Exception:
                pass

            
    def clear(self):
        """Clear all nodes, connections, and per-file UI state (including annotations)."""
        self.nodes.clear()
        self.connections.clear()
        self.selected_node = None
        self.hovered_node = None
        # Reset aggregated external module nodes
        try:
            self._module_nodes = {}
        except Exception:
            pass
        # Reset run-session tracking
        try:
            self.runtime_focus_mode = False
            self._ever_active_nodes = set()
        except Exception:
            pass
        # Reset annotations so they don't bleed across files
        try:
            self._strokes = []
            self._current_stroke = None
            self._texts = []
            self._selected_text = None
            # Hide and drop inline text editor if present
            if getattr(self, '_text_editor', None):
                try:
                    self._text_editor.hide()
                except Exception:
                    pass
            self._text_editor = None
            self._drag_text = None
            self._drag_text_offset = (0.0, 0.0)
            self._resizing_text = None
            self._resize_start = (0, 14.0)
            self._editing_text_ref = None
            self._eraser_pos_world = None
            # Leave current color as-is; just reset tool mode
            self.tool_mode = None
        except Exception:
            pass
        # Reset undo/redo stacks (these are UI-only and should not span files)
        try:
            self._undo_stack = []
            self._redo_stack = []
        except Exception:
            pass
        self.update()
        
    def _layout_nodes(self, functions: Dict[str, Any], dependencies: Dict[str, List[str]]):
        """Layout nodes on a square grid to enforce horizontal/vertical connections (no diagonals)."""
        function_names = list(functions.keys())
        node_count = len(function_names)
        
        if node_count == 0:
            return

        # Use square grid layout so edges are horizontal or vertical
        self._layout_square_grid(functions, dependencies)
            
    def _layout_square_grid(self, functions: Dict[str, Any], dependencies: Dict[str, List[str]]):
        """Place nodes on an integer grid so edges align horizontally or vertically.
        Strategy:
        - Start from zero in-degree roots (or earliest by lineno) and BFS.
        - For each parent at (gx, gy), place children around it using cardinal slots:
          up (gx, gy-1), right (gx+1, gy), down (gx, gy+1), then expand further
          along the same axes (gx+2, gy), (gx, gy-2), (gx, gy+2), ...
        - Resolve collisions by extending further along the chosen axis.
        - Map grid (gx, gy) to pixels using bounded spacing so width/height stay compact.
        This keeps either X or Y equal for every parent->child, so the curve function renders straight lines.
        """
        names = list(functions.keys())
        if not names:
            return
        # Build adjacency and in-degree
        out: Dict[str, List[str]] = {}
        in_deg: Dict[str, int] = {n: 0 for n in names}
        for u in names:
            outs = [v for v in (dependencies.get(u) or []) if v in functions]
            out[u] = outs
            for v in outs:
                in_deg[v] = in_deg.get(v, 0) + 1
        def _lineno(n: str) -> int:
            try:
                return int((functions.get(n) or {}).get('lineno') or 0)
            except Exception:
                return 0
        roots = [n for n in names if in_deg.get(n, 0) == 0]
        if not roots:
            roots = [sorted(names, key=_lineno)[0]]
        roots = sorted(roots, key=_lineno)
        # Grid placement
        pos: Dict[str, tuple] = {}
        occupied = set()
        from collections import deque
        # Place each root spaced apart to the right to avoid overlap between components
        root_spacing = 3
        cur_root_base = 0
        for r in roots:
            if r in pos:
                continue
            q = deque()
            pgx, pgy = cur_root_base, 0
            pos[r] = (pgx, pgy)
            occupied.add((pgx, pgy))
            q.append(r)
            cur_root_base += root_spacing
            while q:
                p = q.popleft()
                if p not in pos:
                    # Should not happen, but guard
                    continue
                pgx, pgy = pos[p]
                children = [c for c in out.get(p, []) if c in functions]
                if not children:
                    continue
                # Precompute slot sequence around (pgx, pgy)
                # Cardinal directions including left to avoid one-sided spread
                slots = [(0, -1), (1, 0), (0, 1), (-1, 0)]  # up, right, down, left
                step = 2
                # Expand rings by Manhattan distance to keep placements near before jumping far
                while len(slots) < len(children) + 12:
                    slots.extend([(0, -step), (step, 0), (0, step), (-step, 0)])
                    step += 1
                ci = 0
                for c in children:
                    # If child already placed by another parent, don't move it here
                    if c in pos:
                        continue
                    dx, dy = slots[ci] if ci < len(slots) else (ci - len(slots) + 2, 0)
                    ci += 1
                    tgx, tgy = pgx + dx, pgy + dy
                    # Resolve collisions along axis of motion to keep cardinal alignment
                    if dx == 0:
                        # vertical lane: keep X fixed to parent's X, vary Y near first with symmetric search
                        step_dir = -1 if dy < 0 else 1 if dy > 0 else 1
                        max_span = 30
                        found = False
                        for k in range(0, max_span + 1):
                            if k == 0:
                                cand_ys = [tgy]
                            else:
                                base = (abs(dy) if dy else 1) + k
                                cand_ys = [pgy + step_dir * base, pgy - step_dir * base]
                            for ytest in cand_ys:
                                if (pgx, ytest) not in occupied:
                                    tgx, tgy = pgx, ytest
                                    found = True
                                    break
                            if found:
                                break
                        if not found:
                            tgx, tgy = pgx, tgy
                    else:
                        # horizontal lane: keep Y fixed to parent's Y, vary X near first
                        step_dir = 1 if dx > 0 else -1
                        max_span = 30
                        found = False
                        for k in range(0, max_span + 1):
                            if k == 0:
                                cand_xs = [tgx]
                            else:
                                base = (abs(dx) if dx else 1) + k
                                cand_xs = [pgx + step_dir * base, pgx - step_dir * base]
                            for xtest in cand_xs:
                                if (xtest, pgy) not in occupied:
                                    tgx, tgy = xtest, pgy
                                    found = True
                                    break
                            if found:
                                break
                    pos[c] = (tgx, tgy)
                    occupied.add((tgx, tgy))
                    q.append(c)
        # Post-pass: for multi-parent nodes, snap to share X or Y with the closest parent if free
        try:
            in_from: Dict[str, List[str]] = {}
            for u, outs in out.items():
                for v in outs:
                    in_from.setdefault(v, []).append(u)
            for n, (gx, gy) in list(pos.items()):
                parents = [p for p in in_from.get(n, []) if p in pos]
                if len(parents) < 2:
                    continue
                # choose parent with minimal manhattan distance
                def manhattan(p):
                    px, py = pos[p]
                    return abs(px - gx) + abs(py - gy)
                parents.sort(key=manhattan)
                best = parents[0]
                px, py = pos[best]
                if (px, gy) not in occupied:
                    occupied.discard((gx, gy))
                    gx = px
                    pos[n] = (gx, gy)
                    occupied.add((gx, gy))
                elif (gx, py) not in occupied:
                    occupied.discard((gx, gy))
                    gy = py
                    pos[n] = (gx, gy)
                    occupied.add((gx, gy))
        except Exception:
            pass
        # Reduce overlong edges by clamping grid distance along aligned axis
        try:
            max_dx = 6
            max_dy = 6
            for u, outs in out.items():
                if u not in pos:
                    continue
                ugx, ugy = pos[u]
                for v in outs:
                    if v not in pos:
                        continue
                    vgx, vgy = pos[v]
                    if ugy == vgy:
                        # horizontal edge
                        dx = vgx - ugx
                        if abs(dx) > max_dx:
                            target = ugx + (max_dx if dx > 0 else -max_dx)
                            # find closest free x near target
                            cand = None
                            for k in range(0, max_dx + 1):
                                for off in (target - k, target + k):
                                    if (off, ugy) not in occupied:
                                        cand = off
                                        break
                                if cand is not None:
                                    break
                            if cand is not None:
                                occupied.discard((vgx, vgy))
                                vgx = cand
                                pos[v] = (vgx, vgy)
                                occupied.add((vgx, vgy))
                    elif ugx == vgx:
                        # vertical edge
                        dy = vgy - ugy
                        if abs(dy) > max_dy:
                            target = ugy + (max_dy if dy > 0 else -max_dy)
                            cand = None
                            for k in range(0, max_dy + 1):
                                for off in (target - k, target + k):
                                    if (ugx, off) not in occupied:
                                        cand = off
                                        break
                                if cand is not None:
                                    break
                            if cand is not None:
                                occupied.discard((vgx, vgy))
                                vgy = cand
                                pos[v] = (vgx, vgy)
                                occupied.add((vgx, vgy))
        except Exception:
            pass
        if not pos:
            return
        # Normalize so minimum grid coords start at zero
        min_gx = min(gx for gx, gy in pos.values())
        min_gy = min(gy for gx, gy in pos.values())
        pos = {n: (gx - min_gx, gy - min_gy) for n, (gx, gy) in pos.items()}
        # Determine grid extents
        max_gx = max(gx for gx, gy in pos.values())
        max_gy = max(gy for gx, gy in pos.values())
        # Map grid to pixels using large fixed spacing (approx 400x400 cells)
        margin_x = 110.0
        margin_y = 90.0
        spacing_x = 400.0
        spacing_y = 400.0
        start_x = margin_x
        start_y = margin_y
        # Create nodes with computed positions
        for n in names:
            gx, gy = pos.get(n, (max_gx + 1, max_gy + 1))
            x = start_x + gx * spacing_x
            y = start_y + gy * spacing_y
            node = FunctionNode(functions[n], float(x), float(y))
            self.nodes.append(node)

    
    def _create_connections(self, dependencies: Dict[str, List[str]]):
        """Create connection objects between nodes"""
        self.connections.clear()
        
        for from_name, to_names in dependencies.items():
            from_node = next((n for n in self.nodes if n.name == from_name), None)
            if not from_node:
                continue
                
            for to_name in to_names:
                to_node = next((n for n in self.nodes if n.name == to_name), None)
                if to_node:
                    connection = Connection(from_node, to_node)
                    self.connections.append(connection)
                    
                    # Update node relationships
                    from_node.calls.append(to_name)
                    to_node.called_by.append(from_name)

        # Also build a lookup by lowercase name for fast flash
        self._node_by_name = {}
        for n in self.nodes:
            self._index_node(n)
                    
    def get_node_at_position(self, x: float, y: float) -> Optional[FunctionNode]:
        """Get node at screen position - uses EXACT SAME dimension calculation as _draw_node"""
        world_x = (x - self.camera_x) / self.camera_zoom
        world_y = (y - self.camera_y) / self.camera_zoom
        
        for node in reversed(self.nodes):  # Check from top to bottom
            # Use EXACT SAME calculation as _draw_node for consistency!
            is_add_tool = getattr(node, 'is_add_tool', False)
            
            if is_add_tool:
                # Add tool node dimensions
                icon_size = 80 * node.scale
                border_padding = 20 * node.scale
                node_width = icon_size + border_padding * 2
                node_height = icon_size + border_padding * 2
            else:
                # Check if custom content node (text/image/video)
                is_custom_content = False
                try:
                    if hasattr(node, 'data') and isinstance(node.data, dict):
                        content_type = node.data.get('content_type')
                        if content_type in ('text', 'image', 'video'):
                            is_custom_content = True
                except Exception:
                    pass
                
                if is_custom_content:
                    # Custom content: square box
                    icon_size = 60 * node.scale
                    border_padding = 20 * node.scale
                    node_width = icon_size + border_padding * 2
                    node_height = node_width  # Square
                else:
                    # Normal node: calculate based on text width (SAME AS _draw_node!)
                    font = QFont("Arial", 14)
                    font.setBold(True)
                    fm = QFontMetrics(font)
                    text_width = fm.horizontalAdvance(node.name)
                    
                    node_width = max(100, min(text_width + 40, 300)) * node.scale
                    node_height = (fm.height() + 20) * self.height_multiplier * node.scale
                    
                    # If it's a main script node, adjust height
                    if node.icon_path and not is_add_tool:
                        node_height = max(node_height, (self.main_node_icon_size + fm.height() + 40) * node.scale)
            
            node_x = node.x - node_width / 2
            node_y = node.y - node_height / 2
            
            if (world_x >= node_x and world_x <= node_x + node_width and
                world_y >= node_y and world_y <= node_y + node_height):
                return node
                
        return None
        
    def select_node(self, node: Optional[FunctionNode]):
        """Select a node and highlight its connections"""
        # Deselect previous node
        if self.selected_node:
            self.selected_node.selected = False
            self.selected_node.target_scale = 1.0
            
        self.selected_node = node
        
        if node:
            node.selected = True
            node.target_scale = 1.1
            self._highlight_connections(node)
            self.node_selected.emit(node)
        else:
            self._clear_highlights()
            self.node_selected.emit(None)
            
        self.update()
        
    def _highlight_connections(self, node: FunctionNode):
        """Highlight connections related to the selected node"""
        # Dim all nodes first
        for n in self.nodes:
            n.highlighted = False
            n.target_opacity = 0.5
        
        # Highlight the selected node
        node.highlighted = True
        node.target_opacity = 1.0
        
        # Highlight related connections and nodes
        for connection in self.connections:
            is_related = connection.from_node == node or connection.to_node == node
            connection.highlighted = is_related
            connection.target_opacity = 0.9 if is_related else 0.3

            if is_related:
                # Set connected nodes to highlighted state
                if connection.from_node != node:
                    connection.from_node.highlighted = True
                    connection.from_node.target_opacity = 0.9
                if connection.to_node != node:
                    connection.to_node.highlighted = True
                    connection.to_node.target_opacity = 0.9
                
    def _clear_highlights(self):
        """Clear all highlights"""
        for node in self.nodes:
            node.highlighted = False
            node.target_opacity = 1.0
            
        for connection in self.connections:
            connection.highlighted = False
            connection.target_opacity = 0.6
            
    def focus_on_node(self, node: FunctionNode):
        """Focus camera on a specific node"""
        target_zoom = 1.7
        target_x = (self.width() / 2) - (node.x * target_zoom)
        target_y = (self.height() / 2) - (node.y * target_zoom)
        self._animate_camera(target_x, target_y, target_zoom)
        
    def reset_view(self):
        """Reset camera to show all nodes"""
        if not self.nodes:
            self.camera_x = 0
            self.camera_y = 0
            self.camera_zoom = 1.0
            self.update()
            return
            
        # Calculate bounding box
        min_x = min(node.x - node.radius for node in self.nodes)
        max_x = max(node.x + node.radius for node in self.nodes)
        min_y = min(node.y - node.radius for node in self.nodes)
        max_y = max(node.y + node.radius for node in self.nodes)
        
        width = max_x - min_x
        height = max_y - min_y
        center_x = (min_x + max_x) / 2
        center_y = (min_y + max_y) / 2
        
        # Calculate zoom to fit
        scale_x = (self.width() * 0.8) / width if width > 0 else 1
        scale_y = (self.height() * 0.8) / height if height > 0 else 1
        target_zoom = min(scale_x, scale_y, 1.5)
        
        target_x = self.width() / 2 - center_x * target_zoom
        target_y = self.height() / 2 - center_y * target_zoom
        
        self._animate_camera(target_x, target_y, target_zoom)
        
    def _animate_camera(self, target_x: float, target_y: float, target_zoom: float):
        """Animate camera to target position and zoom"""
        self.zoom_animation = QPropertyAnimation(self, b"camera_zoom_prop")
        self.zoom_animation.setEndValue(target_zoom)
        self.zoom_animation.setDuration(300)
        self.zoom_animation.setEasingCurve(QEasingCurve.InOutSine)

        self.pan_animation_x = QPropertyAnimation(self, b"camera_x_prop")
        self.pan_animation_x.setEndValue(target_x)
        self.pan_animation_x.setDuration(300)
        self.pan_animation_x.setEasingCurve(QEasingCurve.InOutSine)

        self.pan_animation_y = QPropertyAnimation(self, b"camera_y_prop")
        self.pan_animation_y.setEndValue(target_y)
        self.pan_animation_y.setDuration(300)
        self.pan_animation_y.setEasingCurve(QEasingCurve.InOutSine)

        self.animation_group = QParallelAnimationGroup()
        self.animation_group.addAnimation(self.zoom_animation)
        self.animation_group.addAnimation(self.pan_animation_x)
        self.animation_group.addAnimation(self.pan_animation_y)
        self.animation_group.start()
        
    def zoom_in(self):
        """Zoom in towards center"""
        factor = 1.2
        new_zoom = min(self.camera_zoom * factor, 3.0)
        
        center_x = self.width() / 2
        center_y = self.height() / 2
        
        world_x = (center_x - self.camera_x) / self.camera_zoom
        world_y = (center_y - self.camera_y) / self.camera_zoom
        
        target_x = center_x - world_x * new_zoom
        target_y = center_y - world_y * new_zoom
        
        self._animate_camera(target_x, target_y, new_zoom)
        
    def zoom_out(self):
        """Zoom out from center"""
        factor = 0.8
        new_zoom = max(self.camera_zoom * factor, 0.1)
        
        center_x = self.width() / 2
        center_y = self.height() / 2
        
        world_x = (center_x - self.camera_x) / self.camera_zoom
        world_y = (center_y - self.camera_y) / self.camera_zoom
        
        target_x = center_x - world_x * new_zoom
        target_y = center_y - world_y * new_zoom
        
        self._animate_camera(target_x, target_y, new_zoom)
        
    def update_animation(self):
        """Update all animations with performance optimizations"""
        # Calculate delta time for smooth, frame-rate independent animations
        dt = self.elapsed_timer.restart() / 1000.0  # seconds
        dt = min(dt, 0.032)  # Clamp to avoid large jumps (max 2 frames worth)
        
        # Track if anything changed
        changed = False
        
        # Check camera state changes
        current_camera = (self.camera_x, self.camera_y, self.camera_zoom)
        if current_camera != self._last_camera_state:
            changed = True
            self._last_camera_state = current_camera
        
        # Update node animations (only visible nodes for performance)
        now_ts = time.monotonic()
        visible_nodes = self._get_visible_nodes() if self._viewport_culling else self.nodes
        
        for node in visible_nodes:
            if node.update_animation(dt):
                changed = True
            
            # Update hover state
            if node == self.hovered_node and not node.selected:
                if node.target_scale != self.hover_scale:
                    node.target_scale = self.hover_scale
                    changed = True
            elif not node.selected:
                if node.target_scale != 1.0:
                    node.target_scale = 1.0
                    changed = True

            # Expire runtime-active highlight without creating timers
            if getattr(node, '_active_on', False):
                until = float(getattr(node, '_active_until', 0.0) or 0.0)
                if now_ts > until:
                    try:
                        node._active_on = False
                        changed = True
                    except Exception:
                        pass
                
        # Update connection animations (only visible connections)
        visible_connections = self._get_visible_connections() if self._viewport_culling else self.connections
        for connection in visible_connections:
            if connection.update_animation(dt):
                changed = True

        # Dim nodes that have NEVER been used during this run to 0.7 (no animation)
        try:
            # Auto-disable focus mode if no activity for a while
            if getattr(self, 'runtime_focus_mode', False):
                try:
                    idle_secs = max(0.0, time.monotonic() - float(getattr(self, '_last_activity_time', 0.0)))
                    any_active_now = any(bool(getattr(n, '_active_on', False)) for n in visible_nodes)
                    if idle_secs > 1.5 and not any_active_now:
                        self.runtime_focus_mode = False
                        self._ever_active_nodes = set()
                        changed = True
                except Exception:
                    pass

            DIM = 0.5
            if getattr(self, 'runtime_focus_mode', False) and (self.selected_node is None):
                used = getattr(self, '_ever_active_nodes', set())
                for n in visible_nodes:
                    if n.name in used:
                        if n.opacity != 1.0 or n.target_opacity != 1.0:
                            n.opacity = 1.0
                            n.target_opacity = 1.0
                            changed = True
                    else:
                        if n.opacity != DIM or n.target_opacity != DIM:
                            n.opacity = DIM
                            n.target_opacity = DIM
                            changed = True
            elif not getattr(self, 'runtime_focus_mode', False):
                # Only restore when no selection is active; otherwise let selection/dimming logic persist
                if self.selected_node is None:
                    for n in visible_nodes:
                        if not n.selected and not n.highlighted:
                            if n.opacity != 1.0 or n.target_opacity != 1.0:
                                n.opacity = 1.0
                                n.target_opacity = 1.0
                                changed = True
        except Exception:
            pass
        
        # Adaptive frame rate: slow down when idle
        if changed:
            self._idle_frames = 0
            self._dirty = True
            # Ensure we're at full frame rate
            if self.animation_timer.interval() != 33:
                self.animation_timer.setInterval(33)
        else:
            self._idle_frames += 1
            # After 30 idle frames (~1 second), reduce to 10 FPS
            if self._idle_frames > 30 and self.animation_timer.interval() != 100:
                self.animation_timer.setInterval(100)
        
        # Only trigger repaint if something changed
        if changed or self._dirty:
            self.update()
            self._dirty = False

        # Skip server keep-alive if disabled
        if ENABLE_TRACE_SERVER:
            if getattr(self, '_trace_server_thread', None) and not self._trace_server_thread.is_alive():
                try:
                    self._ensure_trace_server()
                except Exception:
                    pass
        
    # Event handlers
    def paintEvent(self, event: QPaintEvent):
        """Paint the visualization with viewport culling"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Draw flowing background matching the original design
        self._draw_flowing_background(painter)
        
        # Apply camera transform
        painter.save()
        try:
            painter.translate(self.camera_x, self.camera_y)
            painter.scale(self.camera_zoom, self.camera_zoom)
            
            # Background dot grid in world coordinates (under connections/nodes)
            try:
                self._draw_background_dots(painter)
            except Exception:
                pass
            
            # Get visible items for culling
            if self._viewport_culling:
                visible_connections = self._get_visible_connections()
                visible_nodes = self._get_visible_nodes()
            else:
                visible_connections = self.connections
                visible_nodes = self.nodes
            
            # Draw connections first (behind nodes) - only visible ones
            for connection in visible_connections:
                self._draw_connection(painter, connection)
            
            # Draw connection drag line if in drag mode (behind nodes like regular connections)
            try:
                self._draw_connection_drag_line(painter)
            except Exception:
                pass
                
            # Draw nodes - only visible ones
            for node in visible_nodes:
                try:
                    self._draw_node(painter, node)
                except AttributeError:
                    # If binding not yet available, skip further node drawing to avoid painter state leaks
                    break
                except Exception:
                    # Skip faulty node to preserve painter state
                    pass

            # Delegate drawing of annotations (strokes + text)
            try:
                self.annotations.paint_annotations(painter)
            except Exception:
                pass
        finally:
            painter.restore()
        
        # Draw selection box (in screen coordinates, after restoring painter)
        try:
            self._draw_selection_box(painter)
        except Exception:
            pass
        
        # Draw selection box mode instructions (in screen coordinates)
        try:
            self._draw_selection_box_instructions(painter)
        except Exception:
            pass

    def _get_visible_nodes(self) -> List[FunctionNode]:
        """Get nodes visible in current viewport for culling"""
        try:
            # Calculate viewport bounds in world coordinates
            margin = 100  # Extra margin to avoid pop-in
            world_left = (-self.camera_x - margin) / self.camera_zoom
            world_top = (-self.camera_y - margin) / self.camera_zoom
            world_right = (self.width() - self.camera_x + margin) / self.camera_zoom
            world_bottom = (self.height() - self.camera_y + margin) / self.camera_zoom
            
            visible = []
            for node in self.nodes:
                # Quick bounds check
                node_radius = node.radius * 2  # Approximate size
                if (node.x + node_radius >= world_left and 
                    node.x - node_radius <= world_right and
                    node.y + node_radius >= world_top and 
                    node.y - node_radius <= world_bottom):
                    visible.append(node)
            
            return visible
        except Exception:
            return self.nodes
    
    def _get_visible_connections(self) -> List[Connection]:
        """Get connections visible in current viewport for culling"""
        try:
            # Calculate viewport bounds in world coordinates
            margin = 100
            world_left = (-self.camera_x - margin) / self.camera_zoom
            world_top = (-self.camera_y - margin) / self.camera_zoom
            world_right = (self.width() - self.camera_x + margin) / self.camera_zoom
            world_bottom = (self.height() - self.camera_y + margin) / self.camera_zoom
            
            visible = []
            for conn in self.connections:
                # Check if either endpoint is visible
                from_node = conn.from_node
                to_node = conn.to_node
                
                from_visible = (world_left <= from_node.x <= world_right and 
                               world_top <= from_node.y <= world_bottom)
                to_visible = (world_left <= to_node.x <= world_right and 
                             world_top <= to_node.y <= world_bottom)
                
                if from_visible or to_visible:
                    visible.append(conn)
            
            return visible
        except Exception:
            return self.connections
    
    # ---------------------- Selection Box Mode ----------------------
    def toggle_selection_box_mode(self, enabled: bool):
        """Toggle selection box mode on/off"""
        self._selection_box_mode = enabled
        self._selection_box_active = False
        self._selection_box_start = None
        self._selection_box_end = None
        self._selection_box_nodes = []
        
        # Change cursor based on mode
        if enabled:
            self.setCursor(Qt.CrossCursor)
        else:
            self.setCursor(Qt.ArrowCursor)
        
        self.update()
    
    def _update_selection_box(self, current_pos):
        """Update selection box end position and find nodes within rectangle"""
        self._selection_box_end = current_pos
        
        # Convert screen coordinates to world coordinates
        start_x = (self._selection_box_start[0] - self.camera_x) / self.camera_zoom
        start_y = (self._selection_box_start[1] - self.camera_y) / self.camera_zoom
        end_x = (current_pos[0] - self.camera_x) / self.camera_zoom
        end_y = (current_pos[1] - self.camera_y) / self.camera_zoom
        
        # Calculate rectangle bounds
        min_x = min(start_x, end_x)
        max_x = max(start_x, end_x)
        min_y = min(start_y, end_y)
        max_y = max(start_y, end_y)
        
        # Find nodes within rectangle
        self._selection_box_nodes = []
        for node in self.nodes:
            if (min_x <= node.x <= max_x and min_y <= node.y <= max_y):
                self._selection_box_nodes.append(node)
        
        self.update()
    
    def _finalize_selection_box(self):
        """Finalize selection box and select all nodes within it"""
        if not self._selection_box_nodes:
            # No nodes selected - clear selection
            self.select_node(None)
        elif len(self._selection_box_nodes) == 1:
            # Single node - select it normally
            self.select_node(self._selection_box_nodes[0])
        else:
            # Multiple nodes - highlight all of them
            # Clear previous selection
            if self.selected_node:
                self.selected_node.selected = False
                self.selected_node.target_scale = 1.0
            
            self.selected_node = None
            
            # Dim all nodes first
            for n in self.nodes:
                n.highlighted = False
                n.target_opacity = 0.5
            
            # Highlight selected nodes
            for node in self._selection_box_nodes:
                node.highlighted = True
                node.target_opacity = 1.0
                node.target_scale = 1.1
            
            # Highlight connections between selected nodes
            for connection in self.connections:
                is_related = (connection.from_node in self._selection_box_nodes or 
                             connection.to_node in self._selection_box_nodes)
                connection.highlighted = is_related
                connection.target_opacity = 0.9 if is_related else 0.3
        
        # Reset selection box state
        self._selection_box_active = False
        self._selection_box_start = None
        self._selection_box_end = None
        self._selection_box_nodes = []
        
        self.update()
    
    def _draw_selection_box(self, painter: QPainter):
        """Draw the Windows-style blue selection rectangle"""
        if not getattr(self, '_selection_box_active', False):
            return
        
        if not self._selection_box_start or not self._selection_box_end:
            return
        
        try:
            # Draw in screen coordinates (not world coordinates)
            painter.save()
            painter.resetTransform()
            
            start_x, start_y = self._selection_box_start
            end_x, end_y = self._selection_box_end
            
            # Calculate rectangle
            x = min(start_x, end_x)
            y = min(start_y, end_y)
            width = abs(end_x - start_x)
            height = abs(end_y - start_y)
            
            # Draw Windows-style selection rectangle
            # Blue fill with transparency
            fill_color = QColor(0, 120, 215, 50)  # Windows blue with alpha
            painter.setBrush(QBrush(fill_color))
            
            # Blue border
            border_color = QColor(0, 120, 215, 180)  # Windows blue
            painter.setPen(QPen(border_color, 1))
            
            painter.drawRect(int(x), int(y), int(width), int(height))
            
            painter.restore()
        except Exception:
            pass
    
    # ---------------------- Blender-style Transform Mode ----------------------
    def _start_transform_mode(self, mode: str):
        """Start Blender-style transform mode (G for grab, X/Y for axis constraint)"""
        # Get currently highlighted nodes (from selection box or single selection)
        nodes_to_transform = []
        
        if self.selected_node:
            # Single node selected
            nodes_to_transform = [self.selected_node]
        else:
            # Multiple nodes highlighted (from selection box)
            nodes_to_transform = [n for n in self.nodes if n.highlighted]
        
        if not nodes_to_transform:
            return
        
        # Store original positions
        self._transform_start_nodes = [(n, n.x, n.y) for n in nodes_to_transform]
        self._transform_mode = mode
        
        # Get current mouse position from the widget
        try:
            cursor_pos = self.mapFromGlobal(self.cursor().pos())
            self._transform_mouse_start = (cursor_pos.x(), cursor_pos.y())
        except Exception:
            self._transform_mouse_start = None  # Will be set on first mouse move
        
        # Change cursor
        self.setCursor(Qt.SizeAllCursor if mode == 'grab' else 
                      Qt.SizeHorCursor if mode == 'grab_x' else 
                      Qt.SizeVerCursor)
        
        self.update()
    
    def _update_transform(self, mouse_x: int, mouse_y: int):
        """Update node positions during transform"""
        if not self._transform_mode or not self._transform_start_nodes:
            return
        
        # Set mouse start on first move
        if self._transform_mouse_start is None:
            self._transform_mouse_start = (mouse_x, mouse_y)
            return
        
        # Calculate delta in world coordinates
        start_mx, start_my = self._transform_mouse_start
        delta_screen_x = mouse_x - start_mx
        delta_screen_y = mouse_y - start_my
        
        # Convert to world coordinates
        delta_world_x = delta_screen_x / self.camera_zoom
        delta_world_y = delta_screen_y / self.camera_zoom
        
        # Apply constraints based on mode
        if self._transform_mode == 'grab_x':
            delta_world_y = 0  # Only move on X axis
        elif self._transform_mode == 'grab_y':
            delta_world_x = 0  # Only move on Y axis
        
        # Update node positions
        for node, orig_x, orig_y in self._transform_start_nodes:
            node.x = orig_x + delta_world_x
            node.y = orig_y + delta_world_y
            node.original_x = node.x
            node.original_y = node.y
        
        self.update()
    
    def _confirm_transform(self):
        """Confirm the transform operation"""
        if not self._transform_mode or not self._transform_start_nodes:
            return
        
        # Push undo for each moved node
        for node, orig_x, orig_y in self._transform_start_nodes:
            if abs(node.x - orig_x) > 0.01 or abs(node.y - orig_y) > 0.01:
                try:
                    if hasattr(self, '_push_undo'):
                        self._push_undo({
                            'type': 'move_node',
                            'node': node,
                            'from': (orig_x, orig_y),
                            'to': (node.x, node.y)
                        })
                except Exception:
                    pass
        
        # Reset transform state
        self._transform_mode = None
        self._transform_start_nodes = []
        self._transform_mouse_start = None
        self.setCursor(Qt.ArrowCursor)
        
        self.update()
    
    def _cancel_transform(self):
        """Cancel the transform operation and restore original positions"""
        if not self._transform_mode or not self._transform_start_nodes:
            return
        
        # Restore original positions
        for node, orig_x, orig_y in self._transform_start_nodes:
            node.x = orig_x
            node.y = orig_y
            node.original_x = orig_x
            node.original_y = orig_y
        
        # Reset transform state
        self._transform_mode = None
        self._transform_start_nodes = []
        self._transform_mouse_start = None
        self.setCursor(Qt.ArrowCursor)
        
        self.update()
    
    def _draw_selection_box_instructions(self, painter: QPainter):
        """Draw helpful instructions in top-left corner when Select Box mode is active"""
        if not getattr(self, '_selection_box_mode', False):
            return
        
        try:
            painter.save()
            painter.resetTransform()
            
            # Semi-transparent dark background
            padding = 12
            margin = 15
            
            # Instructions text (no bullet points)
            instructions = [
                "Select Box Node",
                "Press G to move selected nodes",
            ]
            
            # Calculate text dimensions with larger title font
            title_font = QFont("Segoe UI", 18)  # Larger title
            title_font.setBold(True)
            regular_font = QFont("Segoe UI", 10)
            
            max_width = 0
            total_height = 0
            line_heights = []
            
            for i, line in enumerate(instructions):
                if i == 0:
                    painter.setFont(title_font)
                    fm = QFontMetrics(title_font)
                else:
                    painter.setFont(regular_font)
                    fm = QFontMetrics(regular_font)
                
                width = fm.horizontalAdvance(line)
                height = fm.height()
                max_width = max(max_width, width)
                line_heights.append(height)
                total_height += height
            
            # Add spacing between lines (with extra margin after title)
            line_spacing = 4
            title_margin_bottom = 10  # Extra margin after title
            total_height += line_spacing * (len(instructions) - 1) + title_margin_bottom
            
            # Background rectangle (no border, no rounded corners)
            bg_rect = QRectF(
                margin,
                margin,
                max_width + padding * 2,
                total_height + padding * 2
            )
            
            painter.setPen(Qt.NoPen)  # No border
            painter.drawRect(bg_rect)  # No rounded corners
            
            # Draw text
            y_offset = margin + padding
            
            for i, line in enumerate(instructions):
                if i == 0:
                    # Title - bold and white (larger font)
                    painter.setFont(title_font)
                    painter.setPen(QPen(QColor(255, 255, 255)))  # White
                else:
                    # Regular text - light gray
                    painter.setFont(regular_font)
                    painter.setPen(QPen(QColor(220, 220, 220)))  # Light gray
                
                painter.drawText(
                    int(margin + padding),
                    int(y_offset + line_heights[i]),
                    line
                )
                
                # Add extra margin after title
                if i == 0:
                    y_offset += line_heights[i] + title_margin_bottom
                else:
                    y_offset += line_heights[i] + line_spacing
            
            painter.restore()
        except Exception:
            pass


# --- Bind extended/moved methods from visualization_core2 onto the canvas class ---
try:
    try:
        from . import visualization_core2 as _vc2
    except Exception:
        try:
            import importlib
            _vc2 = importlib.import_module('Manage.visualization_core2')
        except Exception:
            import importlib.util as _imputil, os as _os
            _p = _os.path.join(_os.path.dirname(__file__), 'visualization_core2.py')
            _spec = _imputil.spec_from_file_location('visualization_core2_dynamic', _p)
            _vc2 = _imputil.module_from_spec(_spec)
            assert _spec and _spec.loader
            _spec.loader.exec_module(_vc2)
    _BIND_METHODS = [
        '_push_undo', 'undo', 'redo',
        '_draw_node', '_draw_3d_box', '_draw_3d_circle', '_draw_node_text', '_draw_port_dots',
        'mousePressEvent', 'mouseMoveEvent', 'mouseDoubleClickEvent', 'mouseReleaseEvent', 'wheelEvent', 'keyPressEvent',
        'set_tool_mode', 'set_rgb', 'set_current_color',
        '_ensure_trace_server', '_trace_server_loop', '_handle_trace_line', '_on_trace_call',
        '_soft_clear_selection', '_clear_highlight_if_no_blink', '_deactivate_node', 'get_trace_port', '_ann_legacy_hit_test_text', '_draw_arrowhead',
        '_index_node', '_get_or_create_module_node', '_layout_module_nodes', '_create_dynamic_node', 'flash_node',
        '_is_near_node_border', '_draw_connection_drag_line',
    ]
    for _name in _BIND_METHODS:
        if hasattr(_vc2, _name):
            setattr(VisualizationCanvas, _name, getattr(_vc2, _name))
except Exception as _e:
    try:
        _trace_log(f"binding core2 failed: {_e}")
    except Exception:
        pass

# --- Bind extended/moved methods from visualization_core3 onto the canvas class ---
try:
    try:
        from . import visualization_core3 as _vc3
    except Exception:
        try:
            import importlib
            _vc3 = importlib.import_module('Manage.visualization_core3')
        except Exception:
            import importlib.util as _imputil, os as _os
            _p = _os.path.join(_os.path.dirname(__file__), 'visualization_core3.py')
            _spec = _imputil.spec_from_file_location('visualization_core3_dynamic', _p)
            _vc3 = _imputil.module_from_spec(_spec)
            assert _spec and _spec.loader
            _spec.loader.exec_module(_vc3)
    _BIND_METHODS_VC3 = [
        'contextMenuEvent', '_show_node_context_menu', '_show_background_context_menu',
        '_draw_connection', '_draw_connection_flow',
        '_resolve_main_file_path', 'mark_error_for_file', 'clear_error_for_file',
        '_draw_flowing_background', '_draw_background_dots',
    ]
    for _name in _BIND_METHODS_VC3:
        if hasattr(_vc3, _name):
            setattr(VisualizationCanvas, _name, getattr(_vc3, _name))
except Exception as _e:
    try:
        _trace_log(f"binding core3 failed: {_e}")
    except Exception:
        pass

