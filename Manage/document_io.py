"""
Manage Document I/O
Provides a SaveLoadManager to persist and restore Manage Native state.

Now supports:
- Single-file layout documents (.mndoc) containing one file's viewport/nodes.
- Project documents (.mndoc) containing multiple files' layouts in a "files" map.

MVP features:
- Collect per-file state from Manage widget and canvas.
- Save/Load single-file docs as before.
- Normalize any loaded doc to a project form (schema_version >= 2) with a files map.
- Merge current file state into a project doc and save back (for multi-file accumulation).
- Apply a per-file state (from either single-file doc or project doc) to a canvas.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional, Tuple

try:
    from PySide6.QtGui import QColor
except Exception:
    QColor = None

SCHEMA_VERSION = 3  # Updated to support multi-project storage
DEFAULT_EXTENSION = ".mndoc"

# ----- Annotation color helpers -----

def _color_to_json(c):
    try:
        if c is None:
            return None
        if QColor and isinstance(c, QColor):
            return c.name()
        if isinstance(c, str):
            return c
        if isinstance(c, (tuple, list)):
            if len(c) >= 3:
                r = int(c[0]); g = int(c[1]); b = int(c[2])
                return f"#{r:02X}{g:02X}{b:02X}"
        # Fallback: try attr access
        name = getattr(c, 'name', None)
        if callable(name):
            return name()
    except Exception:
        pass
    return None


def _color_from_json(v):
    try:
        if QColor:
            if isinstance(v, str):
                return QColor(v)
            if isinstance(v, (tuple, list)):
                if len(v) >= 3:
                    return QColor(int(v[0]), int(v[1]), int(v[2]))
        return v
    except Exception:
        return v


def _now_iso() -> str:
    try:
        import datetime
        return datetime.datetime.now().isoformat()
    except Exception:
        return ""


def _norm_path(p: Optional[str]) -> Optional[str]:
    if not p:
        return None
    try:
        return os.path.abspath(p)
    except Exception:
        return p


def _is_project_doc(data: Dict[str, Any]) -> bool:
    return isinstance(data, dict) and isinstance(data.get("files"), dict)


def _make_empty_project(project_root: Optional[str] = None) -> Dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "app_version": "1.0.0",
        "created_at": _now_iso(),
        "modified_at": _now_iso(),
        "project_root": _norm_path(project_root),
        "files": {},
        "projects": {},  # Store multiple projects (Project 1, Project 2, etc.)
        "next_project_id": 1,
        "active_project_id": None,
    }


def _single_to_project(single: Dict[str, Any]) -> Tuple[Dict[str, Any], Optional[str]]:
    """Wrap a single-file doc into a project doc; return (project_doc, file_path_key).
    The single-file doc is expected to contain viewport/nodes for one analyzed_file_path.
    """
    if not isinstance(single, dict):
        return _make_empty_project(None), None
    analyzed = _norm_path(single.get("analyzed_file_path")) or _norm_path(single.get("file_path"))
    proj = _make_empty_project(single.get("project_root"))
    # Minimal per-file state we care about
    per_file_state = {
        "viewport": single.get("viewport") or {},
        "nodes": single.get("nodes") or [],
        "hidden_nodes": single.get("hidden_nodes") or [],
        "panels": single.get("panels") or {},
        "annotations": single.get("annotations") or {},
        "modified_at": single.get("modified_at") or _now_iso(),
    }
    if analyzed:
        proj["files"][analyzed] = per_file_state
    return proj, analyzed


def _normalize_project(data: Dict[str, Any]) -> Dict[str, Any]:
    """Return a project-shaped document. Converts single-file docs to project form."""
    if _is_project_doc(data):
        # ensure schema_version
        data["schema_version"] = max(int(data.get("schema_version", 1) or 1), SCHEMA_VERSION)
        return data
    proj, _ = _single_to_project(data or {})
    return proj


def _ensure_files_map(project_doc: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(project_doc.get("files"), dict):
        project_doc["files"] = {}
    return project_doc


@dataclass
class NodeState:
    id: str
    name: str
    file_path: Optional[str]
    lineno: Optional[int]
    end_lineno: Optional[int]
    x: float
    y: float
    color: Optional[str] = None
    icon_path: Optional[str] = None


class SaveLoadManager:
    """Serialize and restore Manage canvas/document state."""

    def __init__(self) -> None:
        # optional runtime cache for active project
        self.active_project_path: Optional[str] = None
        self.active_project_doc: Optional[Dict[str, Any]] = None

    # --------------------------- ID strategy ---------------------------
    @staticmethod
    def compute_node_id(node: Any, fallback_file: Optional[str] = None) -> str:
        """Stable node identity for layout persistence.
        Prefers qual_name when present, falls back to name.
        Does NOT include end_lineno and ignores line number if qual_name available,
        so IDs survive code edits and error states that shift lines.
        """
        try:
            data = getattr(node, 'data', {}) or {}
        except Exception:
            data = {}
        try:
            name = str(getattr(node, 'name', '') or '')
        except Exception:
            name = ''
        qn = ''
        try:
            qn = str((data.get('qual_name') or '').strip())
        except Exception:
            qn = ''
        path = data.get('file_path') or fallback_file or ''
        try:
            path = _norm_path(path) or ''
        except Exception:
            pass
        # If we have a qual_name, ignore lineno entirely for stability
        if qn:
            return f"{path}::{qn}".lower()
        # Otherwise use name only; avoid lineno to prevent jumps on edits
        return f"{path}::{name}".lower()

    # --------------------------- Collect per-file ---------------------------
    def collect_state(self, manage_widget: Any, include_projects: bool = False, save_as_whole_file: bool = False) -> Dict[str, Any]:
        """
        Collect current canvas state.
        
        Args:
            manage_widget: The ManageWidget instance
            include_projects: If True, include all Layer menu projects in the state
            save_as_whole_file: If True, save current canvas as the "whole file" default view
            
        Returns:
            Dictionary containing canvas state and optionally all projects
        """
        canvas = getattr(manage_widget, 'canvas', None)
        analyzer = getattr(manage_widget, 'analyzer', None)
        analyzed_file = _norm_path(getattr(analyzer, 'current_file_path', None))
        project_root = None
        try:
            project_root = manage_widget.get_project_root_directory()
        except Exception:
            pass

        viewport = {
            'camera_x': float(getattr(canvas, 'camera_x', 0.0) or 0.0),
            'camera_y': float(getattr(canvas, 'camera_y', 0.0) or 0.0),
            'camera_zoom': float(getattr(canvas, 'camera_zoom', 1.0) or 1.0),
        }

        nodes = []
        try:
            for n in getattr(canvas, 'nodes', []) or []:
                fid = self.compute_node_id(n, fallback_file=analyzed_file)
                data = getattr(n, 'data', {}) or {}
                
                # Build node state dict with all necessary fields
                node_dict = {
                    'id': fid,
                    'name': str(getattr(n, 'name', '') or ''),
                    'file_path': _norm_path(data.get('file_path') or analyzed_file),
                    'lineno': int(data.get('lineno') or 0) if data else None,
                    'end_lineno': int(data.get('end_lineno') or 0) if data else None,
                    'x': float(getattr(n, 'x', 0.0) or 0.0),
                    'y': float(getattr(n, 'y', 0.0) or 0.0),
                    'color': str(getattr(n, 'color', '') or '') or None,
                    'icon_path': str(getattr(n, 'icon_path', '') or '') or None,
                }
                
                # Save custom content type for text/image/video nodes
                content_type = data.get('content_type')
                if content_type in ('text', 'image', 'video'):
                    node_dict['content_type'] = content_type
                    # Save additional custom content data
                    node_dict['type'] = data.get('type', content_type)
                    node_dict['docstring'] = data.get('docstring', '')
                
                # Save source_code and type for Rust function nodes
                source_code = data.get('source_code')
                if source_code:
                    node_dict['source_code'] = str(source_code)
                
                # Save type field for all nodes (Function, Struct, Implementation, etc.)
                node_type = data.get('type')
                if node_type and content_type not in ('text', 'image', 'video'):
                    node_dict['type'] = str(node_type)
                
                # Save is_add_tool flag for Add nodes
                if getattr(n, 'is_add_tool', False):
                    node_dict['is_add_tool'] = True
                
                nodes.append(node_dict)
        except Exception:
            pass

        # Collect connections
        connections = []
        try:
            for conn in getattr(canvas, 'connections', []) or []:
                try:
                    from_node = getattr(conn, 'from_node', None)
                    to_node = getattr(conn, 'to_node', None)
                    if from_node and to_node:
                        from_name = str(getattr(from_node, 'name', '') or '')
                        to_name = str(getattr(to_node, 'name', '') or '')
                        if from_name and to_name:
                            connections.append({
                                'from': from_name,
                                'to': to_name,
                                'hidden': bool(getattr(conn, 'hidden', False))
                            })
                except Exception:
                    pass
        except Exception:
            pass

        def _panel_state(panel: Any) -> Optional[Dict[str, Any]]:
            if not panel:
                return None
            try:
                g = panel.geometry()
                return {
                    'visible': bool(panel.isVisible()),
                    'rect': [g.x(), g.y(), g.width(), g.height()],
                }
            except Exception:
                return None

        panels = {
            'file_panel': _panel_state(getattr(manage_widget, 'file_panel', None)),
            'details_panel': _panel_state(getattr(manage_widget, 'details_panel', None)),
            'stats_panel': _panel_state(getattr(manage_widget, 'stats_panel', None)),
            'Rust_panel': _panel_state(getattr(manage_widget, 'Rust_panel', None)),
            'activity_panel': _panel_state(getattr(manage_widget, 'activity_panel', None)),
            'code_viewer': _panel_state(getattr(manage_widget, 'code_viewer', None)),
            'text_editor': _panel_state(getattr(manage_widget, 'text_editor', None)),
            'image_editor': _panel_state(getattr(manage_widget, 'image_editor', None)),
            'video_editor': _panel_state(getattr(manage_widget, 'video_editor', None)),
        }

        # Collect annotations (strokes + texts)
        ann_strokes = []
        try:
            for s in (getattr(canvas, '_strokes', []) or []):
                pts = [(float(px), float(py)) for (px, py) in (s.get('points') or [])]
                ann_strokes.append({
                    'points': pts,
                    'color': _color_to_json(s.get('color')),
                    'width': float(s.get('width', 2.5) or 2.5),
                })
        except Exception:
            pass
        ann_texts = []
        try:
            for t in (getattr(canvas, '_texts', []) or []):
                ann_texts.append({
                    'x': float(t.get('x', 0.0) or 0.0),
                    'y': float(t.get('y', 0.0) or 0.0),
                    'text': str(t.get('text', '') or ''),
                    'size': float(t.get('size', 14) or 14),
                    'color': _color_to_json(t.get('color')),
                })
        except Exception:
            pass
        
        # Build base state
        single = {
            'schema_version': SCHEMA_VERSION,
            'app_version': '1.0.0',
            'created_at': _now_iso(),
            'modified_at': _now_iso(),
            'project_root': _norm_path(project_root),
            'analyzed_file_path': _norm_path(analyzed_file),
            'viewport': viewport,
            'nodes': nodes,
            'hidden_nodes': [],
            'connections': connections,
            'edges': [],
            'annotations': {
                'strokes': ann_strokes,
                'texts': ann_texts,
            },
            'panels': panels,
        }
        
        # Include Layer menu projects if requested
        if include_projects:
            try:
                # Get project state from toolbar
                if hasattr(manage_widget, 'top_toolbar'):
                    project_state = manage_widget.top_toolbar.project_state
                    
                    # Collect all projects
                    projects_dict = {}
                    for project in project_state.get_all_projects():
                        projects_dict[str(project.id)] = {
                            'name': project.name,
                            'id': project.id,
                            'created_at': project.created_at,
                            'modified_at': project.modified_at,
                            'is_modified': project.is_modified,
                            'selected_files': project.selected_files,
                            'canvas_state': project.canvas_state,
                        }
                    
                    single['projects'] = projects_dict
                    single['next_project_id'] = project_state.next_project_id
                    single['active_project_id'] = project_state.active_project_id
                    
                    # If save_as_whole_file is True, save current canvas as the default "whole file" view
                    if save_as_whole_file:
                        single['whole_file'] = {
                            'analyzed_file_path': _norm_path(analyzed_file),
                            'viewport': viewport,
                            'nodes': nodes,
                            'connections': connections,
                            'annotations': {
                                'strokes': ann_strokes,
                                'texts': ann_texts,
                            },
                            'panels': panels,
                        }
                        print(f"[SaveLoadManager] Saved 'whole file' view with {len(nodes)} nodes")
            except Exception as e:
                print(f"[SaveLoadManager] Error collecting projects: {e}")
                import traceback
                traceback.print_exc()
        
        return single

    # --------------------------- Single-file Save/Load ---------------------------
    def save_to_file(self, path: str, state: Dict[str, Any]) -> None:
        if not path:
            raise ValueError("save_to_file: path is required")
        root, ext = os.path.splitext(path)
        if not ext:
            path = root + DEFAULT_EXTENSION
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(state, f, indent=2)
        except Exception as e:
            raise IOError(f"Failed to save document: {e}")

    def load_from_file(self, path: str) -> Dict[str, Any]:
        if not path or not os.path.exists(path):
            raise FileNotFoundError(path)
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            raise IOError(f"Failed to load document: {e}")
        if not isinstance(data, dict):
            raise ValueError("Invalid .mndoc file: not a dict")
        # Pass through for backward compatibility
        return data

    # --------------------------- Project Save/Load ---------------------------
    def load_project(self, path: str) -> Dict[str, Any]:
        """Load a .mndoc and normalize to project form."""
        data = self.load_from_file(path)
        proj = _normalize_project(data)
        self.active_project_path = path
        self.active_project_doc = proj
        return proj

    def save_project(self, path: str, project_doc: Dict[str, Any]) -> None:
        if not path:
            raise ValueError("save_project: path is required")
        _ensure_files_map(project_doc)
        project_doc['schema_version'] = SCHEMA_VERSION
        project_doc['modified_at'] = _now_iso()
        root, ext = os.path.splitext(path)
        if not ext:
            path = root + DEFAULT_EXTENSION
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(project_doc, f, indent=2)
        except Exception as e:
            raise IOError(f"Failed to save project: {e}")
        self.active_project_path = path
        self.active_project_doc = project_doc

    def merge_current_file_into_project(self, manage_widget: Any, project_doc: Dict[str, Any]) -> Tuple[Dict[str, Any], Optional[str]]:
        """Collect current canvas state and merge into project_doc under its absolute file path."""
        single = self.collect_state(manage_widget)
        proj = _normalize_project(project_doc or {})
        files = _ensure_files_map(proj)["files"]
        file_key = _norm_path(single.get("analyzed_file_path"))
        per_file_state = {
            'viewport': single.get('viewport') or {},
            'nodes': single.get('nodes') or [],
            'hidden_nodes': single.get('hidden_nodes') or [],
            'connections': single.get('connections') or [],
            'panels': single.get('panels') or {},
            'annotations': single.get('annotations') or {},
            'modified_at': _now_iso(),
        }
        if file_key:
            files[file_key] = per_file_state
        proj['modified_at'] = _now_iso()
        return proj, file_key

    # --------------------------- Apply ---------------------------
    def apply_to_canvas(self, canvas: Any, state_or_perfile: Dict[str, Any]) -> None:
        """Apply viewport and node positions to a canvas from a single-file or per-file state."""
        if not canvas or not state_or_perfile or not isinstance(state_or_perfile, dict):
            return
        # Accept either full single-file doc or per-file dict
        if 'viewport' in state_or_perfile and 'nodes' in state_or_perfile and 'files' not in state_or_perfile:
            per = state_or_perfile
        elif _is_project_doc(state_or_perfile):
            # No target specified; nothing to do here.
            return
        else:
            per = state_or_perfile
        # Viewport
        try:
            vp = per.get('viewport') or {}
            cx = float(vp.get('camera_x', canvas.camera_x))
            cy = float(vp.get('camera_y', canvas.camera_y))
            cz = float(vp.get('camera_zoom', canvas.camera_zoom))
            canvas.camera_x = cx
            canvas.camera_y = cy
            canvas.camera_zoom = cz
        except Exception:
            pass
        # Apply positions by node id
        try:
            analyzer = getattr(getattr(canvas, 'parent', lambda: None)(), 'analyzer', None)
            fallback_file = getattr(analyzer, 'current_file_path', None)
        except Exception:
            fallback_file = None
        saved_nodes = per.get('nodes') or []
        by_id = {str(n.get('id', '')).lower(): n for n in saved_nodes if isinstance(n, dict)}
        for n in getattr(canvas, 'nodes', []) or []:
            try:
                nid = self.compute_node_id(n, fallback_file=fallback_file)
                saved = by_id.get(nid)
                if saved:
                    x = float(saved.get('x', n.x))
                    y = float(saved.get('y', n.y))
                    n.x = x
                    n.y = y
                    n.original_x = x
                    n.original_y = y
            except Exception:
                pass
        # Apply connections
        try:
            saved_connections = per.get('connections') or []
            # Build node lookup by name (case-insensitive)
            node_by_name = {}
            for n in getattr(canvas, 'nodes', []) or []:
                name = str(getattr(n, 'name', '') or '').lower()
                if name:
                    node_by_name[name] = n
            
            # Restore connections from saved state
            from .data_analysis import Connection
            restored_connections = []
            for conn_data in saved_connections:
                try:
                    from_name = str(conn_data.get('from', '') or '').lower()
                    to_name = str(conn_data.get('to', '') or '').lower()
                    hidden = bool(conn_data.get('hidden', False))
                    
                    # Find nodes by name
                    from_node = node_by_name.get(from_name)
                    to_node = node_by_name.get(to_name)
                    
                    if from_node and to_node:
                        conn = Connection(from_node, to_node)
                        conn.hidden = hidden
                        restored_connections.append(conn)
                except Exception:
                    pass
            
            # Replace canvas connections with restored ones
            # This ensures we only have the connections from the saved state
            try:
                canvas.connections = restored_connections
            except Exception:
                pass
        except Exception:
            pass
        # Apply annotations
        try:
            ann = per.get('annotations') or {}
            strokes_in = ann.get('strokes') if isinstance(ann, dict) else None
            texts_in = ann.get('texts') if isinstance(ann, dict) else None
            if strokes_in is not None:
                new_strokes = []
                for s in strokes_in or []:
                    try:
                        pts = [(float(px), float(py)) for (px, py) in (s.get('points') or [])]
                    except Exception:
                        pts = []
                    col = _color_from_json(s.get('color'))
                    w = float(s.get('width', 2.5) or 2.5)
                    new_strokes.append({'points': pts, 'color': col, 'width': w})
                try:
                    canvas._strokes = new_strokes
                except Exception:
                    pass
            if texts_in is not None:
                new_texts = []
                for t in texts_in or []:
                    col = _color_from_json(t.get('color'))
                    new_texts.append({
                        'x': float(t.get('x', 0.0) or 0.0),
                        'y': float(t.get('y', 0.0) or 0.0),
                        'text': str(t.get('text', '') or ''),
                        'size': float(t.get('size', 14) or 14),
                        'color': col,
                    })
                try:
                    canvas._texts = new_texts
                except Exception:
                    pass
        except Exception:
            pass
        try:
            canvas.update()
        except Exception:
            pass

    def apply_project_file_to_canvas(self, canvas: Any, project_doc: Dict[str, Any], file_path: str) -> bool:
        """Apply layout for a specific file from a project_doc. Returns True if applied."""
        if not _is_project_doc(project_doc):
            return False
        key = _norm_path(file_path)
        per = (project_doc.get('files') or {}).get(key)
        if not per:
            return False
        self.apply_to_canvas(canvas, per)
        return True

    def apply_panel_positions(self, manage_widget: Any, state_or_perfile: Dict[str, Any]) -> None:
        """Apply saved panel positions from state to manage widget panels."""
        if not manage_widget or not state_or_perfile or not isinstance(state_or_perfile, dict):
            return
        
        # Get panels dict from state
        panels = state_or_perfile.get('panels') or {}
        if not isinstance(panels, dict):
            return
        
        # Helper to restore a single panel
        def _restore_panel(panel: Any, panel_state: Optional[Dict[str, Any]]) -> None:
            if not panel or not panel_state or not isinstance(panel_state, dict):
                return
            try:
                rect = panel_state.get('rect')
                if rect and isinstance(rect, (list, tuple)) and len(rect) >= 4:
                    x, y, w, h = int(rect[0]), int(rect[1]), int(rect[2]), int(rect[3])
                    panel.move(x, y)
                    panel.resize(w, h)
            except Exception:
                pass
        
        # Restore each panel
        _restore_panel(getattr(manage_widget, 'file_panel', None), panels.get('file_panel'))
        _restore_panel(getattr(manage_widget, 'details_panel', None), panels.get('details_panel'))
        _restore_panel(getattr(manage_widget, 'stats_panel', None), panels.get('stats_panel'))
        _restore_panel(getattr(manage_widget, 'Rust_panel', None), panels.get('Rust_panel'))
        _restore_panel(getattr(manage_widget, 'activity_panel', None), panels.get('activity_panel'))
        _restore_panel(getattr(manage_widget, 'code_viewer', None), panels.get('code_viewer'))
        _restore_panel(getattr(manage_widget, 'text_editor', None), panels.get('text_editor'))
        _restore_panel(getattr(manage_widget, 'image_editor', None), panels.get('image_editor'))
        _restore_panel(getattr(manage_widget, 'video_editor', None), panels.get('video_editor'))

    # --------------------------- Helpers ---------------------------
    @staticmethod
    def suggested_filter() -> str:
        return "Manage Documents (*.mndoc);;All Files (*)"

    @staticmethod
    def ensure_extension(path: str) -> str:
        if not path:
            return path
        root, ext = os.path.splitext(path)
        return path if ext else root + DEFAULT_EXTENSION

























