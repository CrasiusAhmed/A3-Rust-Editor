"""
UI Components Module
Contains all UI panels, widgets, and resizable components
"""

import os
from PySide6.QtCore import Qt, Signal, QSize, QEvent, QRectF
from PySide6.QtGui import (
    QPainter, QPen, QBrush, QColor, QFont, QFontMetrics, 
    QLinearGradient, QIcon, QMouseEvent, QResizeEvent, QPaintEvent, QPixmap, QStandardItemModel, QStandardItem,
    QShortcut, QKeySequence
)
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QPushButton, QLabel, 
    QTextEdit, QScrollArea, QFrame, QSizeGrip, QTreeView, QHeaderView, QSizePolicy, QPlainTextEdit
)

from coding_phcjp import RustSyntaxHighlighter
from Details.Main_Code_Editor import CodeEditor
from file_showen import CustomFileSystemModel, FileSorterProxyModel, FileTreeDelegate, apply_modern_scrollbar_style
from .data_analysis import DARK_THEME, FunctionNode
from PySide6.QtCore import QDir

# Import custom content editors from ui_components2
from .ui_components2 import (
    ResizableTextEditor,
    ResizableImageEditor,
    ResizableVideoEditor
)


class ResizableCodeViewer(QFrame):
    """ A movable, resizable frame to display source code. """
    closed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(300, 200)
        self.setWindowFlags(Qt.SubWindow | Qt.FramelessWindowHint)
        self.setFrameShape(QFrame.StyledPanel)
        
        # --- Custom Styling ---
        self.setStyleSheet(f"""
            ResizableCodeViewer {{
                background-color: {DARK_THEME['bg_primary']};
                border: 1px solid {DARK_THEME['border']};
                border-radius: 15px;
            }}
        """)

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(1, 1, 1, 1)
        self.main_layout.setSpacing(0)

        # --- Title Bar ---
        self.title_bar = QWidget()
        self.title_bar.setFixedHeight(35)
        self.title_bar.setStyleSheet(f"""
            QWidget {{
                background-color: {DARK_THEME['bg_secondary']};
                border-top-left-radius: 14px;
                border-top-right-radius: 14px;
                border-bottom: 1px solid {DARK_THEME['border']};
            }}
        """)
        title_layout = QHBoxLayout(self.title_bar)
        title_layout.setContentsMargins(15, 0, 5, 0)

        self.title_label = QLabel("Function Code")
        self.title_label.setStyleSheet(f"color: {DARK_THEME['text_primary']}; font-weight: bold; border: none;")
        
        self.close_button = QPushButton("✕")
        self.close_button.setFixedSize(25, 25)
        self.close_button.setStyleSheet("""
            QPushButton { background: transparent; color: #BDC1C6; border: none; font-size: 16px; }
            QPushButton:hover { color: #E81123; }
        """)
        self.close_button.clicked.connect(self.hide)
        self.close_button.clicked.connect(self.closed.emit)

        title_layout.addWidget(self.title_label)
        title_layout.addStretch()
        title_layout.addWidget(self.close_button)

        # --- Code Editor ---
        self.editor = CodeEditor()
        # Disable semantic checks for snippet view: function bodies may reference names imported at module scope
        try:
            self.editor.semantic_checks_enabled = False
        except Exception:
            pass
        self.editor.setReadOnly(False) # Allow editing
        RustSyntaxHighlighter(self.editor.document())
        # Ensure monospaced font and correct tab width for proper Python indentation rendering
        try:
            font = QFont("Consolas", 10)
            self.editor.setFont(font)
            self._base_font = QFont(font)
            try:
                self.editor.installEventFilter(self)
            except Exception:
                pass
            try:
                self.editor.setTabStopDistance(self.editor.fontMetrics().horizontalAdvance(' ') * 4)
            except Exception:
                pass
        except Exception:
            pass
        # Attach styled Python autocompletion using the project engine (VS Code-like)
        try:
            from PySide6.QtWidgets import QCompleter
            from PySide6.QtCore import QTimer
            from Main.python_recommendation import PythonRecommendationEngine

            eng = PythonRecommendationEngine()
            model = QStandardItemModel()
            comp = QCompleter(model, self)
            comp.setCaseSensitivity(Qt.CaseInsensitive)
            comp.setMaxVisibleItems(12)
            self.editor.setCompleter(comp)

            popup = comp.popup()
            popup_style = """
                QListView {
                    background-color: #282A2E;
                    color: #E8EAED;
                    border: 1px solid #4A4D51;
                    font-size: 11pt;
                }
                QListView::item:selected {
                    background-color: #4A4D51;
                }
            """ + apply_modern_scrollbar_style()
            popup.setStyleSheet(popup_style)
            popup.setIconSize(QSize(16, 16))
            popup.setMinimumWidth(320)

            def _line_before_cursor():
                cur = self.editor.textCursor()
                block = cur.block()
                rel = cur.position() - block.position()
                return block.text()[:max(0, rel)]

            # Build small colored circle icons with a letter
            def _make_icon(bg: QColor, letter: str) -> QIcon:
                pm = QPixmap(16, 16)
                pm.fill(Qt.transparent)
                p = QPainter(pm)
                p.setRenderHint(QPainter.Antialiasing)
                p.setBrush(bg)
                p.setPen(Qt.NoPen)
                p.drawEllipse(0, 0, 16, 16)
                p.setPen(QColor('#ffffff'))
                f = QFont()
                f.setPointSize(8)
                f.setBold(True)
                p.setFont(f)
                p.drawText(pm.rect(), Qt.AlignCenter, letter)
                p.end()
                return QIcon(pm)

            # Precompute sets
            kw_set = set(eng._keywords)
            bi_set = set(eng._builtins)
            sn_set = set(eng._snippets)
            mod_set = set(eng._top_level_modules)

            icon_map = {
                'keyword': _make_icon(QColor(197, 134, 192), 'K'),
                'builtin': _make_icon(QColor(78, 201, 176), 'B'),
                'snippet': _make_icon(QColor(220, 220, 170), 'S'),
                'module': _make_icon(QColor(86, 156, 214), 'M'),
                'member': _make_icon(QColor(156, 220, 254), 'A'),
                'symbol': _make_icon(QColor(180, 180, 180), '·'),
            }

            def _classify(s: str, line_before: str) -> str:
                if s in kw_set:
                    return 'keyword'
                if s in bi_set:
                    return 'builtin'
                if s in sn_set:
                    return 'snippet'
                if s in mod_set and (line_before.strip().startswith('import') or line_before.strip().startswith('from') or line_before.endswith('.')):
                    return 'module'
                if '.' in line_before:
                    return 'member'
                return 'symbol'

            def _populate_model(suggestions, line_before):
                model.clear()
                limit = 200
                for s in suggestions[:limit]:
                    kind = _classify(s, line_before)
                    item = QStandardItem(s)
                    item.setIcon(icon_map.get(kind, icon_map['symbol']))
                    model.appendRow(item)

            # Optional: multi-line from-import context for module members
            import re as _re
            def _find_from_import_module():
                try:
                    cur = self.editor.textCursor()
                    doc = self.editor.document()
                    base_block = cur.block()
                    found_from = None
                    for _ in range(80):
                        txt = base_block.text()
                        if 'from ' in txt and ' import' in txt:
                            found_from = base_block
                            break
                        if not base_block.previous().isValid():
                            break
                        base_block = base_block.previous()
                    if not found_from:
                        return None
                    m = _re.search(r'^\s*from\s+([A-Za-z_][\w\.]*)\s+import\b', found_from.text())
                    if not m:
                        return None
                    mod_name = m.group(1)
                    start_pos = found_from.position()
                    end_pos = cur.position()
                    segment = doc.toPlainText()[start_pos:end_pos]
                    depth = segment.count('(') - segment.count(')')
                    return mod_name if depth > 0 else None
                except Exception:
                    return None

            def _update():
                try:
                    prefix = self.editor.textUnderCursor()
                    line_before = _line_before_cursor()
                    txt = self.editor.toPlainText()
                    mod_in_from = _find_from_import_module()
                    if mod_in_from:
                        suggestions = eng._module_members(mod_in_from, prefix)
                    else:
                        suggestions = eng.suggest(prefix, line_before, txt)
                    _populate_model(suggestions, line_before)
                    comp.setCompletionPrefix(prefix)
                    if model.rowCount() > 0:
                        popup.setCurrentIndex(comp.completionModel().index(0, 0))
                except Exception:
                    pass

            timer = QTimer(self)
            timer.setSingleShot(True)
            timer.setInterval(150)
            def _schedule():
                timer.stop()
                timer.start()
            timer.timeout.connect(_update)
            self.editor.textChanged.connect(_schedule)
            self.editor.cursorPositionChanged.connect(_schedule)
            _schedule()
        except Exception:
            pass
        self.editor.setStyleSheet(f"""
            CodeEditor {{ 
                border: none; 
                border-bottom-left-radius: 14px; 
                border-bottom-right-radius: 14px;
                padding: 5px;
            }}
            QScrollBar:vertical {{
                background: #1E1F22;
                width: 12px;
                border: none;
                border-radius: 0px;
                margin: 0px;
            }}
            QScrollBar::handle:vertical {{
                background: rgba(85, 85, 85, 0.6);
                border-radius: 0px;
                min-height: 20px;
                margin: 2px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: rgba(102, 102, 102, 0.9);
            }}
            QScrollBar::handle:vertical:pressed {{
                background: rgba(119, 119, 119, 1.0);
            }}
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {{
                height: 0px;
                background: none;
            }}
            QScrollBar::add-page:vertical,
            QScrollBar::sub-page:vertical {{
                background: none;
            }}
            QScrollBar:horizontal {{
                background: #1E1F22;
                height: 12px;
                border: none;
                border-radius: 0px;
                margin: 0px;
            }}
            QScrollBar::handle:horizontal {{
                background: rgba(85, 85, 85, 0.6);
                border-radius: 0px;
                min-width: 20px;
                margin: 2px;
            }}
            QScrollBar::handle:horizontal:hover {{
                background: rgba(102, 102, 102, 0.9);
            }}
            QScrollBar::handle:horizontal:pressed {{
                background: rgba(119, 119, 119, 1.0);
            }}
            QScrollBar::add-line:horizontal,
            QScrollBar::sub-line:horizontal {{
                width: 0px;
                background: none;
            }}
            QScrollBar::add-page:horizontal,
            QScrollBar::sub-page:horizontal {{
                background: none;
            }}
        """)

        self.main_layout.addWidget(self.title_bar)
        self.main_layout.addWidget(self.editor)

        # --- Resizing Grip ---
        self.grip = QSizeGrip(self)
        self.grip.setFixedSize(16, 16)
        
        self._drag_start_position = None

        # --- Editing context and dirty tracking ---
        self._source_path = None
        self._abs_start = 0   # 0-based absolute start line in file
        self._abs_end = 0     # 0-based absolute end line (exclusive) in file
        self._base_indent = 0
        self._dirty = False
        self._suppress_dirty = False
        try:
            self.editor.textChanged.connect(self._on_text_changed)
        except Exception:
            pass
        # Reliable Ctrl+S binding (widget-local), independent of other shortcut handlers
        try:
            self._save_sc = QShortcut(QKeySequence.Save, self.editor)
            self._save_sc.setContext(Qt.WidgetWithChildrenShortcut)
            # Ensure it works when focus is inside the editor or its children
            self._save_sc.activated.connect(self._save_changes)
        except Exception:
            pass

    def set_source_context(self, file_path: str, abs_start_line: int, abs_end_line: int, base_indent: int = 0):
        """Provide the file and line-range context for saving edited snippet back to disk.
        Lines are 0-based and abs_end_line is exclusive.
        """
        self._source_path = file_path
        self._abs_start = max(0, int(abs_start_line or 0))
        self._abs_end = max(self._abs_start, int(abs_end_line or self._abs_start))
        self._base_indent = max(0, int(base_indent or 0))

    def set_code(self, title: str, code: str, highlight_line: int = 0):
        """ Sets the content of the code viewer.
        highlight_line is a 1-based line number within 'code' to highlight in red.
        """
        self.title_label.setText(title)
        try:
            import textwrap
            normalized = textwrap.dedent(code or "").lstrip('\n')
        except Exception:
            normalized = code or ""
        # Replace editor content without triggering dirty flag
        try:
            self._suppress_dirty = True
            self.editor.setPlainText(normalized)
        finally:
            self._suppress_dirty = False
        # Apply optional highlight and move cursor to the line
        try:
            hl = int(highlight_line or 0)
            if hl > 0:
                self._apply_line_highlight(hl)
            else:
                self._clear_line_highlight()
        except Exception:
            pass
        # Reset dirty indicator for fresh view
        self._set_dirty_indicator(False)

    def _clear_line_highlight(self):
        try:
            self.editor.setExtraSelections([])
        except Exception:
            pass

    def _apply_line_highlight(self, line_1_based: int):
        """Highlight a given 1-based line in the editor with a translucent red background."""
        try:
            from PySide6.QtGui import QTextCharFormat, QTextCursor
            selections = []
            sel = QPlainTextEdit.ExtraSelection()
            fmt = QTextCharFormat()
            fmt.setBackground(QColor(194, 58, 58, 110))  # semi-transparent red
            fmt.setProperty(QTextCharFormat.FullWidthSelection, True)
            sel.format = fmt
            cursor = self.editor.textCursor()
            cursor.movePosition(QTextCursor.Start)
            if line_1_based > 1:
                cursor.movePosition(QTextCursor.Down, QTextCursor.MoveAnchor, max(0, line_1_based - 1))
            cursor.select(QTextCursor.LineUnderCursor)
            sel.cursor = cursor
            selections.append(sel)
            self.editor.setExtraSelections(selections)
            # Move caret and center on the highlighted line for visibility
            try:
                self.editor.setTextCursor(cursor)
                self.editor.centerCursor()
            except Exception:
                pass
        except Exception:
            pass

    def resizeEvent(self, event: QResizeEvent):
        """ Places the grip in the bottom-right corner. """
        super().resizeEvent(event)
        self.grip.move(self.width() - self.grip.width(), self.height() - self.grip.height())

    def mousePressEvent(self, event: QMouseEvent):
        """ Captures mouse press for dragging the window. """
        if event.button() == Qt.LeftButton and self.title_bar.geometry().contains(event.pos()):
            self._drag_start_position = event.globalPosition().toPoint() - self.pos()
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent):
        """ Moves the window if dragging. """
        if self._drag_start_position:
            self.move(event.globalPosition().toPoint() - self._drag_start_position)
            event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent):
        """ Resets the drag position. """
        self._drag_start_position = None
        event.accept()

    def _on_text_changed(self):
        if not self._suppress_dirty:
            self._set_dirty_indicator(True)

    def _set_dirty_indicator(self, dirty: bool):
        try:
            self._dirty = bool(dirty)
            # Replace close button text with a filled circle when dirty; restore 'X' when clean
            if self._dirty:
                self.close_button.setText("●")
                self.close_button.setToolTip("Unsaved changes — Ctrl+S to save")
            else:
                self.close_button.setText("✕")
                self.close_button.setToolTip("Close")
        except Exception:
            pass

    def _save_changes(self):
        """Save the current snippet back into the source file (range replacement) and reload host."""
        try:
            if not self._source_path or self._abs_end < self._abs_start:
                return
            # Read current file content from disk
            try:
                with open(self._source_path, 'r', encoding='utf-8') as f:
                    full = f.read()
            except Exception:
                return
            lines = full.split('\n')
            # Build re-indented snippet
            raw = self.editor.toPlainText()
            snippet_lines = raw.split('\n')
            indent = ' ' * int(self._base_indent or 0)
            reindented = [(indent + s if s.strip() != '' else s) for s in snippet_lines]
            # Replace the slice
            start = int(self._abs_start)
            end = int(self._abs_end)
            new_lines = lines[:start] + reindented + lines[end:]
            new_content = '\n'.join(new_lines)
            # Write back to disk
            try:
                with open(self._source_path, 'w', encoding='utf-8') as f:
                    f.write(new_content)
            except Exception:
                return
            # Update our context's end to reflect new length
            self._abs_end = start + len(reindented)
            # Clear dirty indicator
            self._set_dirty_indicator(False)
            # Ask host to reload the file to refresh visualization without resetting view
            try:
                canvas = self.parent()  # VisualizationCanvas
                host = canvas.parent() if canvas else None  # ManageWidget
                # Set one-time skip flag to avoid reset_view inside set_data
                try:
                    if canvas is not None:
                        setattr(canvas, '_skip_reset_view_once', True)
                except Exception:
                    pass
                if host and hasattr(host, 'load_file'):
                    host.load_file(self._source_path)
            except Exception:
                pass
        except Exception:
            pass

    def eventFilter(self, obj, event):
        try:
            # Swallow Ctrl+S at ShortcutOverride on the editor to avoid ambiguous global actions
            if obj is self.editor and event.type() == QEvent.ShortcutOverride:
                try:
                    if (event.modifiers() & Qt.ControlModifier) and event.key() == Qt.Key_S:
                        # Handle save here to avoid global shortcuts stealing it
                        try:
                            self._save_changes()
                        except Exception:
                            pass
                        event.accept()
                        return True
                except Exception:
                    pass
            if obj is self.editor and event.type() == QEvent.KeyPress and (event.modifiers() & Qt.ControlModifier):
                if event.key() in (Qt.Key_Plus, Qt.Key_Equal):
                    try:
                        self.editor.zoomIn(1)
                    except Exception:
                        f = self.editor.font()
                        f.setPointSizeF(f.pointSizeF() + 1)
                        self.editor.setFont(f)
                    try:
                        self.editor.setTabStopDistance(self.editor.fontMetrics().horizontalAdvance(' ') * 4)
                    except Exception:
                        pass
                    return True
                if event.key() == Qt.Key_Minus:
                    try:
                        self.editor.zoomOut(1)
                    except Exception:
                        f = self.editor.font()
                        f.setPointSizeF(max(1, f.pointSizeF() - 1))
                        self.editor.setFont(f)
                    try:
                        self.editor.setTabStopDistance(self.editor.fontMetrics().horizontalAdvance(' ') * 4)
                    except Exception:
                        pass
                    return True
                if event.key() == Qt.Key_0:
                    try:
                        if getattr(self, '_base_font', None):
                            self.editor.setFont(self._base_font)
                        self.editor.setTabStopDistance(self.editor.fontMetrics().horizontalAdvance(' ') * 4)
                    except Exception:
                        pass
                    return True
        except Exception:
            pass
        return super().eventFilter(obj, event)

class FunctionInfoPanel(QWidget):
    """Panel showing detailed information about selected function"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        
    def setup_ui(self):
        """Setup the UI components"""
        layout = QVBoxLayout(self)
        
        # Header
        header = QLabel("Function Details")
        header.setStyleSheet(f"""
            QLabel {{
                font-size: 16px;
                font-weight: bold;
                color: {DARK_THEME['accent']};
                padding: 10px;
                border-bottom: 1px solid {DARK_THEME['border']};
            }}
        """)
        layout.addWidget(header)
        
        # Scroll area for details
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        self.details_widget = QWidget()
        self.details_layout = QVBoxLayout(self.details_widget)
        
        scroll.setWidget(self.details_widget)
        layout.addWidget(scroll)
        
        # No selection message
        self.no_selection_label = QLabel("No function selected")
        self.no_selection_label.setAlignment(Qt.AlignCenter)
        self.no_selection_label.setStyleSheet(f"""
            QLabel {{
                color: {DARK_THEME['text_secondary']};
                font-style: italic;
                padding: 20px;
            }}
        """)
        self.details_layout.addWidget(self.no_selection_label)
        
        # Style
        self.setStyleSheet(f"""
            QWidget {{
                background-color: {DARK_THEME['bg_secondary']};
                border: 1px solid {DARK_THEME['border']};
                border-radius: 8px;
            }}
            QScrollArea {{
                border: none;
                background-color: transparent;
            }}
            QScrollBar:vertical {{
                background: #1E1F22;
                width: 12px;
                border: none;
                border-radius: 0px;
                margin: 0px;
            }}
            QScrollBar::handle:vertical {{
                background: rgba(85, 85, 85, 0.6);
                border-radius: 0px;
                min-height: 20px;
                margin: 2px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: rgba(102, 102, 102, 0.9);
            }}
            QScrollBar::handle:vertical:pressed {{
                background: rgba(119, 119, 119, 1.0);
            }}
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {{
                height: 0px;
                background: none;
            }}
            QScrollBar::add-page:vertical,
            QScrollBar::sub-page:vertical {{
                background: none;
            }}
        """)
        
    def show_function_info(self, node: FunctionNode):
        """Show information for the selected function"""
        # Clear existing details by removing the label and deleting the rest
        self.no_selection_label.setParent(None)
        while self.details_layout.count():
            item = self.details_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        # Add function details
        details = [
            ("Name", node.name),
            ("Line", str(node.data.get('lineno', 'Unknown'))),
            ("Arguments", ', '.join(node.data.get('args', [])) or 'none'),
            ("Complexity", f"{node.data.get('complexity', 1)} ({'Simple' if node.data.get('complexity', 1) <= 3 else 'Complex'})"),
            ("Calls", f"{len(node.calls)} function(s)"),
            ("Called by", f"{len(node.called_by)} function(s)")
        ]
        
        for label, value in details:
            detail_widget = self._create_detail_item(label, value)
            self.details_layout.addWidget(detail_widget)
            
        # Add docstring if available
        docstring = node.data.get('docstring', '').strip()
        if docstring:
            doc_widget = self._create_detail_item("Description", docstring, multiline=True)
            self.details_layout.addWidget(doc_widget)
            
        self.details_layout.addStretch()
        
    def hide_function_info(self):
        """Hide function information"""
        # Safely remove the label before clearing the layout
        self.no_selection_label.setParent(None)

        # Clear existing details
        while self.details_layout.count():
            item = self.details_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        # Show no selection message
        self.details_layout.addWidget(self.no_selection_label)
        
    def _create_detail_item(self, label: str, value: str, multiline: bool = False) -> QWidget:
        """Create a detail item widget"""
        widget = QFrame()
        widget.setFrameStyle(QFrame.Box)
        widget.setStyleSheet(f"""
            QFrame {{
                background-color: {DARK_THEME['bg_primary']};
                border: 1px solid {DARK_THEME['border']};
                border-radius: 6px;
                margin: 2px;
                padding: 8px;
            }}
        """)
        
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(8, 8, 8, 8)
        
        # Label
        label_widget = QLabel(label.upper())
        label_widget.setStyleSheet(f"""
            QLabel {{
                color: {DARK_THEME['accent']};
                font-weight: bold;
                font-size: 12px;
                margin-bottom: 4px;
            }}
        """)
        layout.addWidget(label_widget)
        
        # Value
        if multiline:
            value_widget = QTextEdit()
            value_widget.setPlainText(value)
            value_widget.setReadOnly(True)
            value_widget.setMaximumHeight(100)
        else:
            value_widget = QLabel(value)
            value_widget.setWordWrap(True)
            
        value_widget.setStyleSheet(f"""
            QLabel, QTextEdit {{
                color: {DARK_THEME['text_primary']};
                background-color: transparent;
                border: none;
                font-size: 14px;
            }}
        """)
        layout.addWidget(value_widget)
        
        return widget

class ResizablePanel(QFrame):
    """ A generic movable, resizable panel for holding other widgets. """
    closed = Signal()

    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.setMinimumSize(350, 250)
        self.setWindowFlags(Qt.SubWindow | Qt.FramelessWindowHint)
        self.setFrameShape(QFrame.StyledPanel)
        
        self.setStyleSheet(f"""
            ResizablePanel {{
                background-color: {DARK_THEME['bg_secondary']};
                border: 1px solid {DARK_THEME['border']};
                border-radius: 15px;
            }}
        """)

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(1, 1, 1, 1)
        self.main_layout.setSpacing(0)

        # Title Bar
        self.title_bar = QWidget()
        self.title_bar.setFixedHeight(40)
        self.title_bar.setStyleSheet(f"""
            QWidget {{
                background-color: {DARK_THEME['bg_tertiary']};
                border-top-left-radius: 14px;
                border-top-right-radius: 14px;
                border-bottom: 1px solid {DARK_THEME['border']};
            }}
        """)
        self.title_layout = QHBoxLayout(self.title_bar)
        self.title_layout.setContentsMargins(15, 0, 5, 0)

        self.title_label = QLabel(title)
        self.title_label.setStyleSheet(f"color: {DARK_THEME['text_primary']}; font-weight: bold; border: none;")
        
        # Minimize button
        self.minimize_button = QPushButton("–")
        self.minimize_button.setFixedSize(30, 30)
        self.minimize_button.setToolTip("Minimize")
        self.minimize_button.setStyleSheet("""
            QPushButton { background: transparent; color: #BDC1C6; border: none; font-size: 16px; }
            QPushButton:hover { color: #FFFFFF; }
        """)
        
        self.close_button = QPushButton("✕")
        self.close_button.setFixedSize(30, 30)
        self.close_button.setStyleSheet("""
            QPushButton { background: transparent; color: #BDC1C6; border: none; font-size: 16px; }
            QPushButton:hover { color: #E81123; }
        """)
        self.close_button.clicked.connect(self.hide)
        self.close_button.clicked.connect(self.closed.emit)

        self.title_layout.addWidget(self.title_label)
        self.title_layout.addStretch()
        self.title_layout.addWidget(self.minimize_button)
        self.title_layout.addWidget(self.close_button)
        self.main_layout.addWidget(self.title_bar)

        # Content Area
        self.content_area = QWidget()
        self.content_layout = QVBoxLayout(self.content_area)
        self.content_layout.setContentsMargins(5, 5, 5, 5)
        self.main_layout.addWidget(self.content_area)

        # Resizing Grip
        self.grip = QSizeGrip(self)
        self.grip.setFixedSize(16, 16)
        
        # Minimize state
        self.minimized = False
        self._saved_size = None
        
        # Wire minimize toggle
        self.minimize_button.clicked.connect(self.toggle_minimize)
        
        self._drag_start_position = None

    def set_widget(self, widget: QWidget):
        """ Sets the main content widget of the panel. """
        # Clear old content
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            if item.widget():
                item.widget().setParent(None)
        self.content_layout.addWidget(widget)

    def add_title_widget(self, widget: QWidget):
        """Add a widget to the title bar, just left of the close button."""
        try:
            idx = self.title_layout.indexOf(self.close_button)
            if idx == -1:
                self.title_layout.addWidget(widget)
            else:
                self.title_layout.insertWidget(max(0, idx), widget)
        except Exception:
            # Fallback: append to the end
            self.title_layout.addWidget(widget)

    def toggle_minimize(self):
        """Toggle minimized state: collapse to title bar or restore content."""
        try:
            if not self.minimized:
                # Save current size and collapse
                self._saved_size = self.size()
                self.content_area.setVisible(False)
                self.grip.setVisible(False)
                self.setMinimumHeight(self.title_bar.height() + 9)
                self.setMaximumHeight(self.title_bar.height() + 9)
                self.minimize_button.setText("▢")  # restore icon
                self.minimized = True
            else:
                # Restore
                self.content_area.setVisible(True)
                self.grip.setVisible(True)
                self.setMaximumHeight(16777215)  # reset constraint
                self.setMinimumHeight(0)
                if self._saved_size:
                    self.resize(self._saved_size)
                self.minimize_button.setText("–")
                self.minimized = False
        except Exception:
            # Fallback simple toggle
            self.content_area.setVisible(not self.content_area.isVisible())

    def resizeEvent(self, event: QResizeEvent):
        super().resizeEvent(event)
        self.grip.move(self.width() - self.grip.width(), self.height() - self.grip.height())

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton and self.title_bar.geometry().contains(event.pos()):
            self._drag_start_position = event.globalPosition().toPoint() - self.pos()
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent):
        if self._drag_start_position:
            self.move(event.globalPosition().toPoint() - self._drag_start_position)
            event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent):
        self._drag_start_position = None
        event.accept()

class ToolbarButton(QPushButton):
    """ A custom circular button for the toolbar with a 3D style. """
    def __init__(self, icon_path: str, tooltip: str, parent=None):
        super().__init__(parent)
        self.setToolTip(tooltip)
        self.setIcon(QIcon(icon_path))
        self.setFixedSize(50, 50)
        self.setIconSize(QSize(28, 28))
        self.setCheckable(True)
        self.setStyleSheet("background-color: transparent; border: none;")
        # Optional small badge text (e.g., numeric shortcut) drawn on top-left
        self._shortcut_label = None

    def paintEvent(self, event: QPaintEvent):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        rect = self.rect().adjusted(2, 2, -2, -2)
        border_radius = 5.0

        # Base shadow
        shadow_rect = rect.translated(1, 2)
        painter.setBrush(QBrush(QColor(0, 0, 0, 70)))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(shadow_rect, border_radius, border_radius)

        # Main gradient
        gradient = QLinearGradient(rect.topLeft(), rect.bottomLeft())
        if self.isChecked():
            gradient.setColorAt(0, QColor(DARK_THEME['text_secondary']).lighter(150))
            gradient.setColorAt(1, QColor(DARK_THEME['text_secondary']))
        elif self.underMouse():
            gradient.setColorAt(0, QColor('#1E1E1E'))
            gradient.setColorAt(1, QColor('#232323'))
        else:
            gradient.setColorAt(0, QColor("#161616"))
            gradient.setColorAt(1, QColor('#202124'))
        
        painter.setBrush(QBrush(gradient))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(rect, border_radius, border_radius)

        # Inner highlight
        highlight_gradient = QLinearGradient(rect.topLeft(), rect.bottomRight())
        highlight_gradient.setColorAt(0, QColor(255, 255, 255, 25))
        highlight_gradient.setColorAt(1, QColor(255, 255, 255, 0))
        painter.setBrush(QBrush(highlight_gradient))
        painter.drawRoundedRect(rect, border_radius, border_radius)

        # Border
        border_color = QColor(DARK_THEME['border'])
        if self.isChecked():
            border_color = QColor(DARK_THEME['text_secondary']).lighter(150)
        elif self.underMouse():
             border_color = QColor('#6A6D71')
        painter.setPen(QPen(border_color, 1.5))
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(rect, border_radius, border_radius)

        # Icon
        icon_rect = rect.adjusted(11, 11, -11, -11)
        self.icon().paint(painter, icon_rect, Qt.AlignCenter)

        # Shortcut label (top-left, plain text)
        label = getattr(self, '_shortcut_label', None)
        if label:
            f = QFont('Segoe UI', 9)
            f.setBold(True)
            painter.setFont(f)
            tx = rect.left() + 8
            ty = rect.top() + 16
            # simple shadow for contrast
            painter.setPen(QPen(QColor(0, 0, 0, 180)))
            painter.drawText(tx + 1, ty + 1, str(label))
            painter.setPen(QPen(QColor('#E8EAED')))
            painter.drawText(tx, ty, str(label))

    def set_shortcut_label(self, text: str):
        try:
            self._shortcut_label = str(text)
            self.update()
        except Exception:
            pass

class StatsPanel(QWidget):
    """Panel showing visualization statistics"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        
    def setup_ui(self):
        """Setup the UI components"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)
        
        # Header
        header = QLabel("📊 Statistics")
        header.setStyleSheet(f"""
            QLabel {{
                font-size: 16px;
                font-weight: bold;
                color: {DARK_THEME['accent']};
                padding: 10px;
                border-bottom: 1px solid {DARK_THEME['border']};
            }}
        """)
        layout.addWidget(header)
        
        # Stats grid inside a scroll area to prevent clipping on small sizes
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }" + apply_modern_scrollbar_style())

        stats_widget = QWidget()
        stats_layout = QGridLayout(stats_widget)
        stats_layout.setContentsMargins(4, 4, 4, 4)
        stats_layout.setHorizontalSpacing(6)
        stats_layout.setVerticalSpacing(6)

        # Create stat items
        self.function_count_label = self._create_stat_item("Functions", "0")
        self.connection_count_label = self._create_stat_item("Connections", "0")
        self.file_name_label = self._create_stat_item("File", "None")
        self.avg_complexity_label = self._create_stat_item("Avg Complexity", "0")

        # Enable wrapping for long file names
        try:
            self.file_name_label.value_widget.setWordWrap(True)
        except Exception:
            pass
        
        stats_layout.addWidget(self.function_count_label, 0, 0)
        stats_layout.addWidget(self.connection_count_label, 0, 1)
        stats_layout.addWidget(self.file_name_label, 1, 0)
        stats_layout.addWidget(self.avg_complexity_label, 1, 1)

        scroll.setWidget(stats_widget)
        layout.addWidget(scroll)
        
        # Style
        self.setStyleSheet(f"""
            QWidget {{
                background-color: {DARK_THEME['bg_secondary']};
                border: 1px solid {DARK_THEME['border']};
                border-radius: 8px;
            }}
        """)
        
    def _create_stat_item(self, label: str, value: str) -> QWidget:
        """Create a statistics item widget"""
        widget = QFrame()
        widget.setFrameStyle(QFrame.Box)
        widget.setStyleSheet(f"""
            QFrame {{
                background-color: {DARK_THEME['bg_primary']};
                border: 1px solid {DARK_THEME['border']};
                border-radius: 6px;
                margin: 4px;
                padding: 8px;
            }}
        """)
        
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(8, 8, 8, 8)
        
        # Label
        label_widget = QLabel(label)
        label_widget.setStyleSheet(f"""
            QLabel {{
                color: {DARK_THEME['text_secondary']};
                font-size: 12px;
                margin-bottom: 4px;
            }}
        """)
        layout.addWidget(label_widget)
        
        # Value
        value_widget = QLabel(value)
        value_widget.setStyleSheet(f"""
            QLabel {{
                color: {DARK_THEME['accent']};
                font-weight: bold;
                font-size: 14px;
            }}
        """)
        value_widget.setWordWrap(True)
        value_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        layout.addWidget(value_widget)
        
        # Store value widget for updates
        widget.value_widget = value_widget
        
        return widget
        
    def update_stats(self, function_count: int, connection_count: int, 
                    file_name: str = "Unknown", avg_complexity: float = 0.0):
        """Update the statistics display"""
        self.function_count_label.value_widget.setText(str(function_count))
        self.connection_count_label.value_widget.setText(str(connection_count))
        self.file_name_label.value_widget.setText(file_name)
        self.avg_complexity_label.value_widget.setText(f"{avg_complexity:.1f}")

def setup_file_browser_widget(parent_widget):
    """Setup file browser tree view"""
    container = QWidget()
    container_layout = QVBoxLayout(container)
    container_layout.setContentsMargins(0,0,0,0)

    file_model = CustomFileSystemModel()
    file_model.setRootPath(QDir.rootPath())

    proxy_model = FileSorterProxyModel(parent_widget)
    proxy_model.setSourceModel(file_model)

    file_tree = QTreeView()
    file_tree.setModel(proxy_model)
    
    # Get initial root path: prefer last_folder from settings (VS Code-like behavior)
    initial_root = QDir.currentPath()  # fallback
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
                    initial_root = last_folder
    except Exception:
        pass
    
    file_tree.setRootIndex(proxy_model.mapFromSource(file_model.index(initial_root)))
    file_tree.setSortingEnabled(True)
    file_tree.sortByColumn(0, Qt.AscendingOrder)
    file_tree.setItemDelegate(FileTreeDelegate(file_tree))

    # Styling
    hdr = file_tree.header()
    hdr.setSectionResizeMode(0, QHeaderView.Interactive)
    hdr.setStyleSheet(f"""QHeaderView::section {{ background-color: {DARK_THEME['bg_tertiary']}; color: {DARK_THEME['text_secondary']}; padding: 4px; border: none; }}""")
    file_tree.setStyleSheet(f"""
        QTreeView {{ 
            background: transparent; 
            color: {DARK_THEME['text_primary']}; 
            border: none;
        }}
        QTreeView::item:selected {{ background-color: {DARK_THEME['accent']}; }}
        QTreeView::branch:closed:has-children {{ image: url(img/branch-closed.svg); }}
        QTreeView::branch:open:has-children {{ image: url(img/branch-open.svg); }}
        QScrollBar:vertical {{
            background: #1E1F22;
            width: 12px;
            border: none;
            border-radius: 0px;
            margin: 0px;
        }}
        QScrollBar::handle:vertical {{
            background: rgba(85, 85, 85, 0.6);
            border-radius: 0px;
            min-height: 20px;
            margin: 2px;
        }}
        QScrollBar::handle:vertical:hover {{
            background: rgba(102, 102, 102, 0.9);
        }}
        QScrollBar::handle:vertical:pressed {{
            background: rgba(119, 119, 119, 1.0);
        }}
        QScrollBar::add-line:vertical,
        QScrollBar::sub-line:vertical {{
            height: 0px;
            background: none;
        }}
        QScrollBar::add-page:vertical,
        QScrollBar::sub-page:vertical {{
            background: none;
        }}
        QScrollBar:horizontal {{
            background: #1E1F22;
            height: 12px;
            border: none;
            border-radius: 0px;
            margin: 0px;
        }}
        QScrollBar::handle:horizontal {{
            background: rgba(85, 85, 85, 0.6);
            border-radius: 0px;
            min-width: 20px;
            margin: 2px;
        }}
        QScrollBar::handle:horizontal:hover {{
            background: rgba(102, 102, 102, 0.9);
        }}
        QScrollBar::handle:horizontal:pressed {{
            background: rgba(119, 119, 119, 1.0);
        }}
        QScrollBar::add-line:horizontal,
        QScrollBar::sub-line:horizontal {{
            width: 0px;
            background: none;
        }}
        QScrollBar::add-page:horizontal,
        QScrollBar::sub-page:horizontal {{
            background: none;
        }}
    """)

    # Zoom shortcuts scoped to the file tree (focus-based like VS Code)
    try:
        file_tree._base_font = QFont(file_tree.font())
    except Exception:
        file_tree._base_font = None

    def _apply_tree_font(f: QFont):
        try:
            file_tree.setFont(f)
            # Scale header font too
            try:
                hdr_font = QFont(f)
                file_tree.header().setFont(hdr_font)
            except Exception:
                pass
            # Adjust icon size relative to font height
            try:
                h = file_tree.fontMetrics().height()
                file_tree.setIconSize(QSize(max(16, h + 4), max(16, h + 4)))
            except Exception:
                pass
            file_tree.viewport().update()
        except Exception:
            pass

    try:
        from PySide6.QtGui import QKeySequence, QShortcut
        sc_in = QShortcut(QKeySequence("Ctrl++"), file_tree)
        sc_in.setContext(Qt.WidgetWithChildrenShortcut)
        def _zoom_in_tree():
            f = QFont(file_tree.font())
            f.setPointSizeF(f.pointSizeF() + 1)
            _apply_tree_font(f)
        sc_in.activated.connect(_zoom_in_tree)
    except Exception:
        pass
    try:
        sc_in_eq = QShortcut(QKeySequence("Ctrl+="), file_tree)
        sc_in_eq.setContext(Qt.WidgetWithChildrenShortcut)
        sc_in_eq.activated.connect(_zoom_in_tree)
    except Exception:
        pass
    try:
        sc_out = QShortcut(QKeySequence("Ctrl+-"), file_tree)
        sc_out.setContext(Qt.WidgetWithChildrenShortcut)
        def _zoom_out_tree():
            f = QFont(file_tree.font())
            f.setPointSizeF(max(1, f.pointSizeF() - 1))
            _apply_tree_font(f)
        sc_out.activated.connect(_zoom_out_tree)
    except Exception:
        pass
    try:
        sc_reset = QShortcut(QKeySequence("Ctrl+0"), file_tree)
        sc_reset.setContext(Qt.WidgetWithChildrenShortcut)
        def _reset_tree():
            bf = getattr(file_tree, '_base_font', None)
            if bf:
                _apply_tree_font(bf)
        sc_reset.activated.connect(_reset_tree)
    except Exception:
        pass

    container_layout.addWidget(file_tree)
    return container, file_tree, file_model, proxy_model