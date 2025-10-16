
import re
from PySide6.QtCore import Qt, QRect, QTimer, QEvent, QPoint
from PySide6.QtGui import QGuiApplication, QPainter, QTextCursor, QTextFormat, QColor, QPen, QFont
from PySide6.QtWidgets import QPlainTextEdit, QTextEdit
from Main.menu_style_right_click import build_editor_context_menu
from Details.multi_cursor import MultiCursorManager
from coding_phcjp import MinimapScrollbar, LineNumberArea, InlineColorPickerPopup, SearchReplaceWidget, RustSyntaxHighlighter




class CodeEditor(QPlainTextEdit):
    """
    A custom QPlainTextEdit with line numbers and current line highlighting.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        # Keep a base font to reset zoom
        try:
            self._base_font = QFont(self.font())
        except Exception:
            self._base_font = None
        # Ensure undo/redo is enabled for the editor
        try:
            self.setUndoRedoEnabled(True)
        except Exception:
            pass
        self.lineNumberArea = LineNumberArea(self)
        self.error_selections = []
        self.success_selection = None
        self.inspect_selection = None
        self.search_selections = []
        self.syntax_error_selections = []  # For wavy underlines
        self.runtime_error_selections = []  # For runtime error line highlight
        self.last_error_line = -1 # To track the line for the success highlight
        # Matching bracket highlight selections (init early to avoid AttributeError)
        self.bracket_match_selections = []
        
        # Enable horizontal scrolling by disabling word wrap
        self.setLineWrapMode(QPlainTextEdit.NoWrap)
        
        # Connect signals to update line number area
        self.blockCountChanged.connect(self.updateLineNumberAreaWidth)
        self.updateRequest.connect(self.updateLineNumberArea)
        self.cursorPositionChanged.connect(self.highlightCurrentLine)
        self.horizontalScrollBar().valueChanged.connect(self.lineNumberArea.update)
        
        # Connect text change to syntax checking
        self.textChanged.connect(self.check_syntax_errors)
        # Connect text change to update Cargo.toml highlights (keep them persistent)
        self.textChanged.connect(self._update_cargo_toml_highlights_on_edit)
        
        # Also connect to cursor position changes for immediate feedback
        self.cursorPositionChanged.connect(self.on_cursor_position_changed)
        
        # Initial setup
        self.updateLineNumberAreaWidth(0)
        self.highlightCurrentLine()
        
        # Apply modern scrollbar styling with animations
        self.apply_animated_scrollbar_style()

        self.search_replace_widget = SearchReplaceWidget(self)
        self.highlighter = RustSyntaxHighlighter(self.document())
        self.multi = MultiCursorManager(self)
        self.semantic_checks_enabled = True
        # Ensure we can intercept clicks on both viewport and gutter to reset multi-caret state
        try:
            self.lineNumberArea.installEventFilter(self)
        except Exception:
            pass

        # Matching bracket highlight selections
        self.bracket_match_selections = []
        self.cursorPositionChanged.connect(self.update_bracket_match)
        self.textChanged.connect(self.update_bracket_match)

        # Replace the default scrollbar with our custom one
        self.minimap_scrollbar = MinimapScrollbar(self)
        self.setVerticalScrollBar(self.minimap_scrollbar)

        # Inline color swatch overlay setup (disabled by default to avoid covering code text)
        self.enable_inline_color_overlay = False
        self.enable_change_color_click = False
        try:
            if self.enable_inline_color_overlay:
                self._color_overlay = ColorOverlay(self)
                self._color_overlay.setGeometry(self.viewport().rect())
                # Keep overlay refreshed on text/scroll/cursor changes
                self.textChanged.connect(self._color_overlay.update)
                self.cursorPositionChanged.connect(self._color_overlay.update)
                self.blockCountChanged.connect(self._color_overlay.update)
                self.updateRequest.connect(lambda *_: (self._color_overlay.setGeometry(self.viewport().rect()), self._color_overlay.raise_(), self._color_overlay.update()))
                self.verticalScrollBar().valueChanged.connect(lambda *_: (self._color_overlay.setGeometry(self.viewport().rect()), self._color_overlay.raise_(), self._color_overlay.update()))
                self.horizontalScrollBar().valueChanged.connect(lambda *_: (self._color_overlay.setGeometry(self.viewport().rect()), self._color_overlay.raise_(), self._color_overlay.update()))
                QTimer.singleShot(0, self._color_overlay.update)
            else:
                self._color_overlay = None
        except Exception:
            self._color_overlay = None
        
        # Timer for delayed syntax checking
        self.syntax_check_timer = QTimer(self)
        self.syntax_check_timer.setSingleShot(True)
        self.syntax_check_timer.setInterval(300)  # Reduced to 300ms delay for faster response
        self.syntax_check_timer.timeout.connect(self.perform_syntax_check)

        # Cached indentation guide lines (VS Code style)
        # list of tuples: (indent_level, start_line, end_line)
        self._indent_guides_cache = []
        self._indent_guides_dirty = True
        # Mark cache dirty when text changes
        self.textChanged.connect(self._invalidate_indent_guides)

        # Track when the user is dragging to select text to throttle expensive updates
        self._drag_selecting = False

        # Inline color swatch feature: compiled regex and cache
        try:
            # Prioritize 8-digit hex so alpha channels are recognized before 6-digit
            self._color_swatch_regex = re.compile(r'#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})\b')
        except Exception:
            self._color_swatch_regex = None
        self._color_swatch_entries = []
        # Inline color swatch tuning (you can change these at runtime)
        self._color_swatch_size = 15  # square size in px (controls height/width)
        self._color_swatch_x_offset = 6  # horizontal offset in px relative to the anchor
        self._color_swatch_click_pad = 10  # expands clickable hit area around the square (increase if clicks are hard)
        # Anchor mode: 'hash' anchors at '#', 'after' anchors just after the hex literal
        self._color_swatch_anchor = 'after'

    def changeEvent(self, event):
        try:
            if event.type() == QEvent.FontChange:
                # Invalidate caches and adjust gutter when font changes (zoom)
                try:
                    self._invalidate_scope_cache()
                    self._invalidate_brace_cache()
                except Exception:
                    pass
                try:
                    self.lineNumberArea.setFont(self.font())
                    self.updateLineNumberAreaWidth(0)
                except Exception:
                    pass
                try:
                    self.viewport().update()
                    self.lineNumberArea.update()
                except Exception:
                    pass
        except Exception:
            pass
        super().changeEvent(event)

    # + change space line with number from back not between
    def lineNumberAreaWidth(self):
        """
        **LINE NUMBER SPACING FEATURE**
        Calculates the required width for the line number area based on the number of lines.
        Added extra space between line numbers and code for better readability.
        """
        digits = len(str(max(1, self.blockCount())))
        # Space for digits plus MORE margin for better spacing (increased from 3 to 15)
        space = 35 + self.fontMetrics().horizontalAdvance('1') * digits
        return space

    def updateLineNumberAreaWidth(self, _):
        """
        Updates the viewport margins to accommodate the line number area.
        """
        self.setViewportMargins(self.lineNumberAreaWidth(), 0, 0, 0)

    def updateLineNumberArea(self, rect, dy):
        """
        Updates or scrolls the line number area when the editor content changes.
        """
        if dy:
            self.lineNumberArea.scroll(0, dy)
        else:
            self.lineNumberArea.update(0, rect.y(), self.lineNumberArea.width(), rect.height())
        if rect.contains(self.viewport().rect()):
            self.updateLineNumberAreaWidth(0)

    def resizeEvent(self, event):
        """
        Resizes the line number area when the editor is resized.
        """
        super().resizeEvent(event)
        cr = self.contentsRect()
        self.lineNumberArea.setGeometry(
            QRect(cr.left(), cr.top(), self.lineNumberAreaWidth(), cr.height())
        )
        self.search_replace_widget.update_position()
        try:
            if hasattr(self, '_color_overlay') and self._color_overlay:
                self._color_overlay.setGeometry(self.viewport().rect())
                self._color_overlay.raise_()
                self._color_overlay.update()
        except Exception:
            pass

    def paintEvent(self, event):
        super().paintEvent(event)
        try:
            if hasattr(self, '_color_overlay') and self._color_overlay:
                self._color_overlay.raise_()
                self._color_overlay.update()
        except Exception:
            pass

    def _draw_color_swatches(self, painter):
        """Scan visible text for hex color literals and draw small clickable swatches."""
        try:
            self._color_swatch_entries = []
            if not getattr(self, '_color_swatch_regex', None):
                return

            viewport_rect = self.viewport().rect()

            block = self.firstVisibleBlock()
            fm = self.fontMetrics()
            while block.isValid():
                top = self.blockBoundingGeometry(block).translated(self.contentOffset()).top()
                block_rect_h = self.blockBoundingRect(block).height()
                bottom = top + block_rect_h
                if top > viewport_rect.bottom():
                    break
                if block.isVisible() and bottom >= viewport_rect.top():
                    text = block.text()
                    for m in self._color_swatch_regex.finditer(text):
                        start_in_block = m.start()
                        length = m.end() - m.start()
                        abs_start = block.position() + start_in_block

                        # Get caret rect at the start of the literal (this aligns with the '#' left edge)
                        cur = QTextCursor(self.document())
                        cur.setPosition(abs_start)
                        caret_rect = self.cursorRect(cur)

                        # Determine color from the match
                        literal = m.group(0)
                        col = self._color_from_hex_literal(literal)
                        if not col.isValid():
                            continue

                        # Swatch rectangle: fixed size centered vertically, anchor selection
                        # Determine anchor X: at '#' or after the literal
                        anchor_mode = getattr(self, '_color_swatch_anchor', 'hash')
                        if anchor_mode == 'after':
                            cur_end = QTextCursor(self.document())
                            cur_end.setPosition(abs_start + length)
                            end_rect = self.cursorRect(cur_end)
                            anchor_x = end_rect.left()
                        else:
                            anchor_x = caret_rect.left()
                        
                        line_h = caret_rect.height()
                        size = max(8, min(int(getattr(self, '_color_swatch_size', 12)), int(line_h) - 2))
                        x = int(anchor_x + int(getattr(self, '_color_swatch_x_offset', -20)))
                        y = int(caret_rect.top() + (line_h - size) / 2)
                        sw_rect = QRect(x, y, int(size), int(size))
                        # Expand hit rect to make clicking easier
                        pad = int(getattr(self, '_color_swatch_click_pad', 3))
                        hit_rect = sw_rect.adjusted(-pad, -pad, pad, pad)
                        # Hit area for the literal text itself so clicking on '#RRGGBB' works
                        try:
                            text_rect = QRect(caret_rect.left(), caret_rect.top(), max(1, (end_rect.left() - caret_rect.left())), caret_rect.height())
                            text_hit_rect = text_rect.adjusted(-2, -2, 2, 2)
                        except Exception:
                            text_hit_rect = None

                        # Border with contrasting color
                        r, g, b, _ = col.getRgb()
                        luminance = 0.299 * r + 0.587 * g + 0.114 * b
                        border = QColor(25, 25, 25) if luminance > 186 else QColor(230, 230, 230)

                        # Only draw visible swatches when overlay feature is enabled
                        if painter is not None and getattr(self, 'enable_inline_color_overlay', False):
                            try:
                                tile = 4
                                for yy in range(sw_rect.top(), sw_rect.bottom(), tile):
                                    for xx in range(sw_rect.left(), sw_rect.right(), tile):
                                        c2 = QColor(200, 200, 200) if ((xx//tile + yy//tile) % 2 == 0) else QColor(240, 240, 240)
                                        painter.fillRect(QRect(xx, yy, tile, tile), c2)
                            except Exception:
                                pass
                            # Overlay actual color (with alpha)
                            painter.setPen(Qt.NoPen)
                            painter.setBrush(col)
                            painter.drawRoundedRect(sw_rect, 2, 2)
                            # Border on top
                            painter.setPen(QPen(border, 1))
                            painter.setBrush(Qt.NoBrush)
                            painter.drawRoundedRect(sw_rect, 2, 2)

                        # Keep for click handling
                        self._color_swatch_entries.append({
                            'rect': sw_rect,
                            'hit_rect': hit_rect,
                            'text_hit_rect': text_hit_rect,
                            'start': abs_start,
                            'length': length,
                            'literal': literal,  # preserve exact matched text (including alpha)
                            'color': col,
                        })
                block = block.next()
        except Exception:
            # Fail-safe: never break painting
            pass

    def _color_from_hex_literal(self, literal: str) -> QColor:
        try:
            s = literal.strip()
            if not s.startswith('#'):
                return QColor()
            hexpart = s[1:]
            a = 255
            if len(hexpart) == 3:
                # Expand #RGB to #RRGGBB
                hexpart = ''.join([ch * 2 for ch in hexpart])
            elif len(hexpart) == 8:
                # Parse #RRGGBBAA preserving alpha
                a = int(hexpart[6:8], 16)
                hexpart = hexpart[:6]
            elif len(hexpart) != 6:
                # Normalize unusual lengths (4,5,7) by trimming/padding to 6
                if len(hexpart) > 6:
                    hexpart = hexpart[:6]
                else:
                    hexpart = (hexpart + '0' * 6)[:6]
                a = 255
            r = int(hexpart[0:2], 16)
            g = int(hexpart[2:4], 16)
            b = int(hexpart[4:6], 16)
            c = QColor(r, g, b)
            c.setAlpha(a)
            return c
        except Exception:
            return QColor()

    def _handle_color_swatch_click(self, e) -> bool:
        """If clicking a swatch, open a color picker and replace the hex literal. Returns True if handled."""
        try:
            # Only active when Change Color mode is enabled by the main window
            if not getattr(self, 'enable_change_color_click', False):
                return False
            # Always rebuild swatch hit areas based on current viewport and text state
            try:
                self._draw_color_swatches(None)
            except Exception:
                pass
            if not self._color_swatch_entries:
                return False
            # Map the event position to viewport coordinates to match swatch rects
            # Prefer widget-relative coordinates; fall back to global mapping
            pos = None
            try:
                if hasattr(e, "position"):
                    widget_pos = e.position().toPoint()
                else:
                    widget_pos = e.pos()
            except Exception:
                widget_pos = None
            if widget_pos is not None:
                # QAbstractScrollArea delivers mouse events in viewport coords; but map just in case
                pos_candidate = widget_pos
                if not self.viewport().rect().contains(pos_candidate):
                    pos_candidate = self.viewport().mapFrom(self, widget_pos)
                if self.viewport().rect().contains(pos_candidate):
                    pos = pos_candidate
            if pos is None:
                try:
                    gp = e.globalPosition().toPoint()
                except Exception:
                    try:
                        gp = e.globalPos()
                    except Exception:
                        return False
                pos = self.viewport().mapFromGlobal(gp)
            for entry in reversed(self._color_swatch_entries):
                hit = entry.get('hit_rect', entry.get('rect'))
                text_hit = entry.get('text_hit_rect')
                if (hit and hit.contains(pos)) or (text_hit and text_hit.contains(pos)):
                    # Show lightweight inline color picker popup near the swatch
                    try:
                        # Read original literal including potential alpha
                        start = entry['start']
                        length = entry['length']
                        # Prefer the exact matched literal captured during scanning
                        original = entry.get('literal') if isinstance(entry, dict) else None
                        if not original:
                            doc_text = self.document().toPlainText()
                            original = doc_text[start:start+length]
                        # Validate initial literal; if invalid, fall back to swatch color
                        init_text = original
                        try:
                            import re as _re
                            if not _re.fullmatch(r"#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})", init_text or ""):
                                col = entry.get('color')
                                if col and hasattr(col, 'red'):
                                    init_text = f"#{col.red():02X}{col.green():02X}{col.blue():02X}"
                        except Exception:
                            pass
                        # Update toolbar color icon immediately when clicking a hex
                        try:
                            win = self.window()
                            if hasattr(win, 'set_color_icon'):
                                win.current_color_hex = (init_text or original).upper()
                                win.set_color_icon(win.current_color_hex)
                        except Exception:
                            pass
                        # Anchor to bottom-right of the swatch with a small offset
                        anchor_global = self.viewport().mapToGlobal(entry['rect'].bottomRight()) + QPoint(8, 8)
                        # Close any existing active color picker for this editor before opening a new one
                        try:
                            existing = getattr(self, '_active_color_picker', None)
                            if existing is not None:
                                try:
                                    existing.close()
                                except Exception:
                                    pass
                        except Exception:
                            pass
                        popup = InlineColorPickerPopup(self, anchor_global, start, length, init_text)
                        self._active_color_picker = popup
                        popup.show()
                        popup.raise_()
                        popup.activateWindow()
                        return True
                    except Exception:
                        return False
            return False
        except Exception:
            return False

    
    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            # Handle clicks on inline color swatches to open color picker
            try:
                if self._handle_color_swatch_click(e):
                    return
            except Exception:
                pass
            self._drag_selecting = True
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e):
        # Keep drag flag while left button is held down
        super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e):
        super().mouseReleaseEvent(e)
        if e.button() == Qt.LeftButton:
            self._drag_selecting = False
            # After drag selection finishes, update bracket match once
            QTimer.singleShot(0, self.update_bracket_match)

    # + adding space between line code and number code in -15
    def lineNumberAreaPaintEvent(self, event):
        """
        Paints the line numbers for visible blocks.
        Only shows line numbers for blocks that are actually visible (not folded).
        """
        painter = QPainter(self.lineNumberArea)
        try:
            painter.setFont(self.font())
            # Background color for the line number area
            painter.fillRect(event.rect(), QColor("#1E1E1E"))

            block = self.firstVisibleBlock()
            blockNumber = block.blockNumber()
            top = self.blockBoundingGeometry(block).translated(self.contentOffset()).top()
            bottom = top + self.blockBoundingRect(block).height()
            height = self.fontMetrics().height()

            while block.isValid() and top <= event.rect().bottom():
                # Only paint line numbers for visible blocks (not folded)
                if block.isVisible() and bottom >= event.rect().top():
                    number = str(blockNumber + 1)
                    painter.setPen(QColor("#7F8C8D")) # Color for line numbers
                    painter.drawText(
                        0, top, self.lineNumberArea.width()-15, height,
                        Qt.AlignRight, number
                    )
                block = block.next()
                top = bottom
                bottom = top + self.blockBoundingRect(block).height()
                blockNumber += 1
        finally:
            try:
                painter.end()
            except Exception:
                pass

    
    def keyPressEvent(self, e):
        # Send key press to keyboard display widget
        try:
            main_window = self.window()
            if hasattr(main_window, 'keyboard_display') and main_window.keyboard_display:
                key_text = self._get_key_display_text(e)
                if key_text:
                    main_window.keyboard_display.show_key(key_text)
        except Exception:
            pass

        # VS Code-like zoom: Ctrl + / Ctrl - / Ctrl 0
        try:
            if e.modifiers() & Qt.ControlModifier:
                if e.key() in (Qt.Key_Plus, Qt.Key_Equal):
                    try:
                        self.zoomIn(1)
                    except Exception:
                        f = self.font()
                        f.setPointSizeF(f.pointSizeF() + 1)
                        self.setFont(f)
                    try:
                        self.setTabStopDistance(self.fontMetrics().horizontalAdvance(' ') * 4)
                    except Exception:
                        pass
                    try:
                        self._invalidate_scope_cache()
                        self.updateLineNumberAreaWidth(0)
                        self.viewport().update()
                        self.lineNumberArea.update()
                    except Exception:
                        pass
                    return
                if e.key() == Qt.Key_Minus:
                    try:
                        self.zoomOut(1)
                    except Exception:
                        f = self.font()
                        f.setPointSizeF(max(1, f.pointSizeF() - 1))
                        self.setFont(f)
                    try:
                        self.setTabStopDistance(self.fontMetrics().horizontalAdvance(' ') * 4)
                    except Exception:
                        pass
                    try:
                        self._invalidate_scope_cache()
                        self.updateLineNumberAreaWidth(0)
                        self.viewport().update()
                        self.lineNumberArea.update()
                    except Exception:
                        pass
                    return
                if e.key() == Qt.Key_0:
                    try:
                        if getattr(self, '_base_font', None):
                            self.setFont(self._base_font)
                        self.setTabStopDistance(self.fontMetrics().horizontalAdvance(' ') * 4)
                    except Exception:
                        pass
                    try:
                        self._invalidate_scope_cache()
                        self.updateLineNumberAreaWidth(0)
                        self.viewport().update()
                        self.lineNumberArea.update()
                    except Exception:
                        pass
                    return
        except Exception:
            pass
        # Intercept standard clipboard shortcuts to ensure multi-selection support
        if e.modifiers() & Qt.ControlModifier:
            if e.key() == Qt.Key_C:
                self.copy()
                return
            if e.key() == Qt.Key_X:
                self.cut()
                return
            if e.key() == Qt.Key_V:
                self.paste()
                return
            # Handle Ctrl+/ for toggle line comment - delegate to main window
            if e.key() == Qt.Key_Slash:
                try:
                    main_window = self.window()
                    if hasattr(main_window, 'toggle_line_comment'):
                        main_window.toggle_line_comment()
                        return
                except Exception:
                    pass
        # Multi-caret hotkeys and replication
        if hasattr(self, 'multi') and self.multi and self.multi.handle_key_press(e):
            return
        # Store whether we need to trigger syntax checking after this key event
        should_trigger_syntax_check = False

        # **CTRL+ENTER FEATURE** - Insert new line below without splitting current line (VS Code behavior)
        if (e.modifiers() & Qt.ControlModifier) and e.key() in (Qt.Key_Enter, Qt.Key_Return):
            self.handle_ctrl_enter()
            should_trigger_syntax_check = True
            if should_trigger_syntax_check:
                self.check_syntax_errors()
            return

        # **AUTO INDENTATION FEATURE** - Handle Enter key for VS Code-like auto indentation
        if e.key() in (Qt.Key_Enter, Qt.Key_Return):
            if hasattr(self, 'multi') and self.multi and self.multi.has_multi():
                self.multi._apply_enter_all()
            else:
                self.handle_enter_key()
            # Trigger syntax check after enter
            should_trigger_syntax_check = True
            if should_trigger_syntax_check:
                self.check_syntax_errors()
            return

        # **TAB KEY FEATURE** - Handle Tab key for VS Code-like indentation (4 spaces)
        if e.key() == Qt.Key_Tab:
            if hasattr(self, 'multi') and self.multi and self.multi.has_multi():
                self.multi._apply_text_all('    ')
            else:
                self.handle_tab_key()
            # Trigger syntax check after tab
            should_trigger_syntax_check = True
            if should_trigger_syntax_check:
                self.check_syntax_errors()
            return

        if (e.modifiers() & Qt.ControlModifier) and e.key() == Qt.Key_F:
            cursor = self.textCursor()
            selected_text = cursor.selectedText()
            
            self.search_replace_widget.show()
            self.search_replace_widget.raise_()

            if selected_text:
                # Block signals to prevent find_all from running on setText
                self.search_replace_widget.search_input.blockSignals(True)
                self.search_replace_widget.search_input.setText(selected_text)
                self.search_replace_widget.search_input.blockSignals(False)
                
                # Call find_all and pass the current cursor to start search from there
                self.search_replace_widget.find_all(start_from_cursor=cursor)
                self.search_replace_widget.search_input.selectAll()
            else:
                self.search_replace_widget.search_input.setFocus()
                self.search_replace_widget.search_input.selectAll()
                # Call find_all without a cursor to search from the beginning
                self.search_replace_widget.find_all()
            return

        # VS Code-like auto-pairing for brackets and quotes, plus skip-over and smart backspace
        # Only when no Ctrl/Alt/Meta modifiers are pressed
        if not (e.modifiers() & (Qt.ControlModifier | Qt.AltModifier | Qt.MetaModifier)):
            # Smart backspace: delete paired brackets/quotes when empty between them
            if e.key() == Qt.Key_Backspace:
                cur = self.textCursor()
                if not cur.hasSelection():
                    open_to_close = {'(': ')', '[': ']', '{': '}', '<': '>', '"': '"', "'": "'"}
                    prev_ch = self._char_at(cur.position() - 1)
                    next_ch = self._char_at(cur.position())
                    if prev_ch in open_to_close and open_to_close.get(prev_ch) == next_ch:
                        cur.beginEditBlock()
                        cur.movePosition(QTextCursor.Left, QTextCursor.MoveAnchor, 1)
                        cur.movePosition(QTextCursor.Right, QTextCursor.KeepAnchor, 2)
                        cur.removeSelectedText()
                        cur.endEditBlock()
                        self.setTextCursor(cur)
                        e.accept()
                        self.check_syntax_errors()
                        return
            txt = e.text()
            if txt:
                open_to_close = {'(': ')', '[': ']', '{': '}', '<': '>', '"': '"', "'": "'"}
                closers = {')', ']', '}', '>', '"', "'"}
                # Skip-over: if typing a closer and next char is same closer, just move over it
                if txt in closers:
                    cur = self.textCursor()
                    if not cur.hasSelection():
                        if self._char_at(cur.position()) == txt:
                            cur.movePosition(QTextCursor.Right)
                            self.setTextCursor(cur)
                            e.accept()
                            self.check_syntax_errors()
                            return
                    # otherwise fall through to default insertion
                # Auto-pair for openers and quotes
                if txt in open_to_close:
                    cur = self.textCursor()
                    # Selection wrapping
                    if cur.hasSelection():
                        selected = cur.selectedText().replace('\u2029', '\n')
                        cur.beginEditBlock()
                        cur.removeSelectedText()
                        cur.insertText(txt + selected + open_to_close[txt])
                        cur.movePosition(QTextCursor.Left)  # place before closing
                        cur.endEditBlock()
                        self.setTextCursor(cur)
                        e.accept()
                        self.check_syntax_errors()
                        return
                    else:
                        # Quotes: handle skip-over and escape context
                        if txt in ('"', "'"):
                            next_ch = self._char_at(cur.position())
                            prev_ch = self._char_at(cur.position() - 1)
                            if next_ch == txt:
                                cur.movePosition(QTextCursor.Right)
                                self.setTextCursor(cur)
                                e.accept()
                                self.check_syntax_errors()
                                return
                            if prev_ch == '\\':
                                # likely an escaped quote, let default behavior insert a single quote
                                pass
                            else:
                                cur.beginEditBlock()
                                cur.insertText(txt + open_to_close[txt])
                                cur.movePosition(QTextCursor.Left)
                                cur.endEditBlock()
                                self.setTextCursor(cur)
                                e.accept()
                                self.check_syntax_errors()
                                return
                        # Brackets: insert pair always
                        cur.beginEditBlock()
                        cur.insertText(txt + open_to_close[txt])
                        cur.movePosition(QTextCursor.Left)
                        cur.endEditBlock()
                        self.setTextCursor(cur)
                        e.accept()
                        self.check_syntax_errors()
                        return

        # Default key handling
        super().keyPressEvent(e)
        
        # Trigger syntax check for printable characters
        if should_trigger_syntax_check:
            self.check_syntax_errors()
    
    def keyReleaseEvent(self, e):
        """Handle key release - keyboard display uses timer instead of release events"""
        # Don't call release_key here - let the timer handle it automatically
        # This ensures keys stay visible for the full duration (3 seconds)
        super().keyReleaseEvent(e)
    
    def _get_key_display_text(self, event):
        """Convert a key event to display text for the keyboard widget"""
        try:
            key = event.key()
            
            # Check if this is a modifier key being pressed alone
            is_modifier_key = key in (Qt.Key_Control, Qt.Key_Shift, Qt.Key_Alt, Qt.Key_Meta)
            
            # Build modifier list (but only if this isn't a modifier key press itself)
            modifiers = []
            if not is_modifier_key:
                if event.modifiers() & Qt.ControlModifier:
                    modifiers.append("Ctrl")
                if event.modifiers() & Qt.ShiftModifier:
                    modifiers.append("Shift")
                if event.modifiers() & Qt.AltModifier:
                    modifiers.append("Alt")
                if event.modifiers() & Qt.MetaModifier:
                    modifiers.append("Win")
            
            # Handle modifier keys being pressed (show combinations like "Ctrl + Shift")
            if is_modifier_key:
                # Build list of all active modifiers
                active_modifiers = []
                if event.modifiers() & Qt.ControlModifier:
                    active_modifiers.append("Ctrl")
                if event.modifiers() & Qt.ShiftModifier:
                    active_modifiers.append("Shift")
                if event.modifiers() & Qt.AltModifier:
                    active_modifiers.append("Alt")
                if event.modifiers() & Qt.MetaModifier:
                    active_modifiers.append("Win")
                
                # Show the combination of modifiers
                if len(active_modifiers) > 0:
                    return " + ".join(active_modifiers)
                return None
            
            # Map special keys to readable names
            key_map = {
                Qt.Key_Return: "Enter",
                Qt.Key_Enter: "Enter",
                Qt.Key_Backspace: "Backspace",
                Qt.Key_Tab: "Tab",
                Qt.Key_Escape: "Esc",
                Qt.Key_Space: "Space",
                Qt.Key_Delete: "Delete",
                Qt.Key_Home: "Home",
                Qt.Key_End: "End",
                Qt.Key_PageUp: "PgUp",
                Qt.Key_PageDown: "PgDn",
                Qt.Key_Left: "←",
                Qt.Key_Right: "→",
                Qt.Key_Up: "↑",
                Qt.Key_Down: "↓",
                Qt.Key_F1: "F1",
                Qt.Key_F2: "F2",
                Qt.Key_F3: "F3",
                Qt.Key_F4: "F4",
                Qt.Key_F5: "F5",
                Qt.Key_F6: "F6",
                Qt.Key_F7: "F7",
                Qt.Key_F8: "F8",
                Qt.Key_F9: "F9",
                Qt.Key_F10: "F10",
                Qt.Key_F11: "F11",
                Qt.Key_F12: "F12",
                Qt.Key_Insert: "Insert",
                Qt.Key_CapsLock: "CapsLock",
                Qt.Key_Plus: "+",
                Qt.Key_Minus: "-",
                Qt.Key_Equal: "=",
                Qt.Key_Slash: "/",
                Qt.Key_Backslash: "\\",
            }
            
            # Get key text
            if key in key_map:
                key_text = key_map[key]
            else:
                key_text = event.text()
                if not key_text or key_text.isprintable() == False:
                    key_text = chr(key) if 32 <= key <= 126 else None
                if key_text:
                    key_text = key_text.upper()
            
            if not key_text:
                return None
            
            # Combine modifiers with key
            if modifiers:
                return " + ".join(modifiers + [key_text])
            return key_text
        except Exception:
            return None

    def handle_enter_key(self):
        """
        **AUTO INDENTATION FEATURE**
        Handle Enter key press with VS Code-like auto indentation for Rust
        - Handles {}, (), [] brackets with proper spacing
        - Maintains current indentation level for regular lines
        """
        cursor = self.textCursor()
        current_block = cursor.block()
        current_line = current_block.text()
        cursor_pos_in_line = cursor.position() - current_block.position()
        
        # Get the indentation of the current line
        indent = ""
        for char in current_line:
            if char in [' ', '\t']:
                indent += char
            else:
                break
        
        # Check if cursor is between matching brackets (VS Code behavior)
        char_before = current_line[cursor_pos_in_line - 1] if cursor_pos_in_line > 0 else ''
        char_after = current_line[cursor_pos_in_line] if cursor_pos_in_line < len(current_line) else ''
        
        # Handle all bracket pairs: {}, (), []
        bracket_pairs = {'{': '}', '(': ')', '[': ']'}
        if char_before in bracket_pairs and bracket_pairs[char_before] == char_after:
            # VS Code-style: cursor between matching brackets
            # Insert newline, indented line, newline, and closing bracket
            cursor.beginEditBlock()
            cursor.insertText('\n' + indent + '    ')  # New line with extra indent
            cursor.insertText('\n' + indent)  # Line for closing bracket
            cursor.endEditBlock()
            # Move cursor back up to the indented line
            cursor.movePosition(QTextCursor.Up)
            cursor.movePosition(QTextCursor.EndOfLine)
            self.setTextCursor(cursor)
            return
        
        # Check if current line ends with opening brace (Rust style)
        stripped_line = current_line.strip()
        should_increase_indent = (
            stripped_line.endswith('{') or
            stripped_line.endswith(':') or
            stripped_line.startswith('fn ') or
            stripped_line.startswith('impl ') or
            stripped_line.startswith('struct ') or
            stripped_line.startswith('enum ') or
            stripped_line.startswith('if ') or
            stripped_line.startswith('else') or
            stripped_line.startswith('for ') or
            stripped_line.startswith('while ') or
            stripped_line.startswith('loop') or
            stripped_line.startswith('match ')
        )
        
        # Insert new line
        cursor.insertText('\n')
        
        # Add appropriate indentation
        if should_increase_indent:
            # Add current indentation plus 4 spaces (standard indentation)
            cursor.insertText(indent + '    ')
        else:
            # Just add current indentation
            cursor.insertText(indent)
        
        # Set the cursor position
        self.setTextCursor(cursor)

    def handle_tab_key(self):
        """
        **TAB KEY FEATURE**
        Handle Tab key press like VS Code - always insert exactly 4 spaces
        This ensures consistent indentation and matches VS Code behavior
        """
        cursor = self.textCursor()
        # Insert exactly 4 spaces (VS Code standard)
        cursor.insertText('    ')
        self.setTextCursor(cursor)

    def handle_ctrl_enter(self):
        """
        **CTRL+ENTER FEATURE**
        Handle Ctrl+Enter key press like VS Code - insert new line below current line
        without splitting it, maintaining the same indentation level.
        This allows you to quickly add a new line below while keeping the cursor
        in the middle of the current line.
        """
        cursor = self.textCursor()
        current_block = cursor.block()
        current_line = current_block.text()
        
        # Get the indentation of the current line
        indent = ""
        for char in current_line:
            if char in [' ', '\t']:
                indent += char
            else:
                break
        
        # Use edit block to make undo work properly
        cursor.beginEditBlock()
        
        # Move cursor to end of current line
        cursor.movePosition(QTextCursor.EndOfBlock)
        
        # Insert new line with same indentation
        cursor.insertText('\n' + indent)
        
        cursor.endEditBlock()
        
        # Set the cursor position
        self.setTextCursor(cursor)

    def _char_at(self, pos: int) -> str:
        """Return the character at absolute document position pos or empty string if out of range."""
        try:
            if pos < 0:
                return ''
            doc_text = self.document().toPlainText()
            if pos >= len(doc_text):
                return ''
            return doc_text[pos]
        except Exception:
            return ''

    def setSearchSelections(self, selections):
        self.search_selections = selections
        self.highlightCurrentLine()

    def set_linter_error_markers(self, lines):
        """Set linter error marker lines on the minimap scrollbar (1-based)."""
        if hasattr(self, 'minimap_scrollbar') and hasattr(self.minimap_scrollbar, 'set_linter_error_markers'):
            self.minimap_scrollbar.set_linter_error_markers(lines or [])

    def set_runtime_error_markers(self, lines):
        """Set runtime error marker lines on the minimap scrollbar (1-based)."""
        if hasattr(self, 'minimap_scrollbar') and hasattr(self.minimap_scrollbar, 'set_runtime_error_markers'):
            self.minimap_scrollbar.set_runtime_error_markers(lines or [])

    def highlightCurrentLine(self):
        """
        Highlights the current line in the editor.
        """
        extraSelections = []
        if not self.isReadOnly():
            selection = QTextEdit.ExtraSelection()
            lineColor = QColor("#282A2E") # Background color for the current line
            selection.format.setBackground(lineColor)
            selection.format.setProperty(QTextFormat.FullWidthSelection, True)
            selection.cursor = self.textCursor()
            selection.cursor.clearSelection()
            extraSelections.append(selection)

        extraSelections.extend(self.error_selections)
        
        if self.success_selection:
            extraSelections.append(self.success_selection)
        # Ensure inspect highlight overlays on top of current-line and other selections
        if getattr(self, 'inspect_selection', None):
            extraSelections.append(self.inspect_selection)

        extraSelections.extend(self.search_selections)
        extraSelections.extend(self.syntax_error_selections)  # Add syntax error wavy underlines
        # Ensure runtime error highlight stays visible and is not cleared by linter updates
        extraSelections.extend(self.runtime_error_selections)
        # Add Cargo.toml error highlights (subtle red background for dependency errors)
        if hasattr(self, 'cargo_toml_error_selections'):
            extraSelections.extend(self.cargo_toml_error_selections)
        # Matching bracket pair selections
        extraSelections.extend(self.bracket_match_selections)
        if hasattr(self, 'multi') and self.multi:
            extraSelections.extend(self.multi.get_extra_selections())
        self.setExtraSelections(extraSelections)
        # Force viewport update to redraw indentation guide lines
        self.viewport().update()

    def update_bracket_match(self):
        """Highlight the matching bracket for the bracket under/adjacent to the cursor."""
        return
        # Skip heavy matching while drag-selecting to avoid UI freezes
        if getattr(self, "_drag_selecting", False) or bool(QGuiApplication.mouseButtons() & Qt.LeftButton):
            return
        self.bracket_match_selections = []
        try:
            text = self.toPlainText()
            if not text:
                self.highlightCurrentLine()
                return
            pos = self.textCursor().position()
            idx = None
            if pos < len(text) and text[pos] in '()[]{}':
                idx = pos
            elif pos > 0 and text[pos - 1] in '()[]{}':
                idx = pos - 1
            if idx is None:
                self.highlightCurrentLine()
                return

            match_pos = self._find_matching_bracket(text, idx)
            if match_pos is None:
                self.highlightCurrentLine()
                return

            # Create subtle highlight selections on both brackets
            for p in (idx, match_pos):
                sel = QTextEdit.ExtraSelection()
                cur = self.textCursor()
                cur.setPosition(p)
                cur.movePosition(QTextCursor.NextCharacter, QTextCursor.KeepAnchor)
                sel.cursor = cur
                fmt = QTextCharFormat()
                fmt.setBackground(QColor(255, 215, 0, 70))  # Light gold highlight
                sel.format = fmt
                self.bracket_match_selections.append(sel)
        except Exception:
            pass
        self.highlightCurrentLine()

    def _find_matching_bracket(self, text: str, idx: int) -> int | None:
        """Find the matching bracket index for the bracket at idx, skipping strings and comments."""
        open_to_close = {'(' : ')', '[' : ']', '{' : '}'}
        close_to_open = {')':'(', ']':'[', '}':'{'}
        if idx < 0 or idx >= len(text):
            return None
        ch = text[idx]
        if ch in open_to_close:
            open_ch = ch
            close_ch = open_to_close[ch]
            step = 1
            i = idx + 1
        elif ch in close_to_open:
            open_ch = close_to_open[ch]
            close_ch = ch
            step = -1
            i = idx - 1
        else:
            return None

        # Determine initial in-string state by scanning up to idx
        in_string = False
        str_type = None  # '"', "'", '"""', or "'''"
        escape = False
        try:
            j = 0
            while j < idx:
                c = text[j]
                if in_string:
                    if escape:
                        escape = False
                    elif c == '\\':
                        escape = True
                    elif str_type in ('"', "'"):
                        if c == str_type:
                            in_string = False
                            str_type = None
                    else:
                        if j + 2 < len(text) and text[j:j+3] == str_type:
                            in_string = False
                            str_type = None
                            j += 2
                else:
                    if c == '#':
                        # Skip to end of line
                        while j < len(text) and text[j] != '\n':
                            j += 1
                    elif c in ('"', "'"):
                        if j + 2 < len(text) and text[j:j+3] in ('"""', "'''"):
                            in_string = True
                            str_type = text[j:j+3]
                            j += 2
                        else:
                            in_string = True
                            str_type = c
                j += 1
        except Exception:
            pass

        depth = 0
        n = len(text)
        while 0 <= i < n:
            c = text[i]
            if in_string:
                if escape:
                    escape = False
                elif c == '\\':
                    escape = True
                elif str_type in ('"', "'"):
                    if c == str_type:
                        in_string = False
                        str_type = None
                else:
                    if i + 2 < n and text[i:i+3] == str_type:
                        in_string = False
                        str_type = None
                        i += 2
            else:
                if c == '#':
                    # Skip to end of line
                    while i < n and text[i] != '\n':
                        i += 1
                    i += step
                    continue
                if c in ('"', "'"):
                    if i + 2 < n and text[i:i+3] in ('"""', "'''"):
                        in_string = True
                        str_type = text[i:i+3]
                        i += 3
                        continue
                    else:
                        in_string = True
                        str_type = c
                        i += 1
                        continue
                if step == 1:
                    if c == open_ch:
                        depth += 1
                    elif c == close_ch:
                        if depth == 0:
                            return i
                        depth -= 1
                else:
                    if c == close_ch:
                        depth += 1
                    elif c == open_ch:
                        if depth == 0:
                            return i
                        depth -= 1
            i += step
        return None

    def highlight_error_line(self, line_num):
        """ Highlights a single line with a red background. """
        # Only clear previous runtime selections; keep linter selections intact
        self.runtime_error_selections = []
        if line_num > 0:
            selection = QTextEdit.ExtraSelection()
            # Use red background instead of underline
            selection.format.setBackground(QColor(139, 69, 69, 100))  # Semi-transparent red background
            selection.format.setProperty(QTextFormat.FullWidthSelection, True)

            block = self.document().firstBlock()
            for _ in range(line_num - 1):
                if not block.isValid():
                    block = None
                    break
                block = block.next()

            if block and block.isValid():
                selection.cursor = QTextCursor(block)
                selection.cursor.clearSelection()
                self.runtime_error_selections.append(selection)
        self.highlightCurrentLine()

    def highlight_errors(self, errors):
        """ Highlights the first error found and updates linter minimap markers. """
        self.error_selections = []
        marker_lines = []
        if errors:
            for err in errors:
                try:
                    ln = int(err.get('line')) if isinstance(err, dict) else None
                    if ln and ln > 0:
                        marker_lines.append(ln)
                except Exception:
                    continue

            first_error = errors[0]
            line = first_error['line']
            self.last_error_line = line

            selection = QTextEdit.ExtraSelection()
            selection.format.setBackground(QColor(139, 69, 69, 100))  # Semi-transparent red background
            selection.format.setProperty(QTextFormat.FullWidthSelection, True)

            if line > 0:
                block = self.document().firstBlock()
                for _ in range(line - 1):
                    if not block.isValid():
                        block = None
                        break
                    block = block.next()

                if block and block.isValid():
                    cursor = QTextCursor(block)
                    cursor.clearSelection()
                    selection.cursor = cursor
                    self.error_selections.append(selection)
        else:
            self.last_error_line = -1
            marker_lines = []
        
        # Update only linter minimap markers (preserve runtime markers)
        self.set_linter_error_markers(sorted(set(marker_lines)))
        self.highlightCurrentLine()

    def clear_error_highlight(self):
        """ Clears runtime error highlights. """
        self.runtime_error_selections = []
        self.last_error_line = -1
        self.set_runtime_error_markers([])
        self.highlightCurrentLine()

    def show_success_highlight(self, line):
        """ Highlights a line with a success color for a short duration. """
        self.success_selection = QTextEdit.ExtraSelection()
        lineColor = QColor(69, 139, 69, 120) # Semi-transparent green background
        self.success_selection.format.setBackground(lineColor)
        self.success_selection.format.setProperty(QTextFormat.FullWidthSelection, True)
        if line > 0 and line <= self.blockCount():
            self.success_selection.cursor = QTextCursor(self.document().findBlockByLineNumber(line - 1))
            self.success_selection.cursor.clearSelection()
        self.highlightCurrentLine() # Apply the highlight
        QTimer.singleShot(1000, self.clear_success_highlight) # Set timer to clear it

    def clear_success_highlight(self):
        """ Clears the success highlight. """
        self.success_selection = None
        self.highlightCurrentLine() # Re-apply highlights to remove the green one

    # Inspect-mode highlight that coexists with editor highlights and auto-clears
    def show_inspect_highlight(self, line, duration_ms=5000):
        try:
            sel = QTextEdit.ExtraSelection()
            lineColor = QColor(69, 139, 69, 180)  # stronger semi-transparent green
            sel.format.setBackground(lineColor)
            sel.format.setProperty(QTextFormat.FullWidthSelection, True)
            if line > 0 and line <= self.blockCount():
                sel.cursor = QTextCursor(self.document().findBlockByLineNumber(line - 1))
                sel.cursor.clearSelection()
            self.inspect_selection = sel
            self.highlightCurrentLine()
            try:
                QTimer.singleShot(int(duration_ms or 5000), self.clear_inspect_highlight)
            except Exception:
                pass
        except Exception:
            pass

    def clear_inspect_highlight(self):
        try:
            self.inspect_selection = None
            self.highlightCurrentLine()
        except Exception:
            pass

    def on_cursor_position_changed(self):
        """Handle cursor position changes (disabled syntax checks in Rust mode)."""
        return

    def check_syntax_errors(self):
        """Syntax checking disabled in Rust mode."""
        return

    def perform_syntax_check(self):
        """Syntax checking disabled in Rust mode."""
        self.syntax_error_selections = []
        if hasattr(self.minimap_scrollbar, 'set_syntax_markers'):
            self.minimap_scrollbar.set_syntax_markers([], [], [])
        self.highlightCurrentLine()

    def apply_animated_scrollbar_style(self):
        """
        Apply modern animated scrollbar styling with opacity transitions
        """
        self.setStyleSheet("""
            QPlainTextEdit {
                background: #1E1E1E; 
                border: none; 
                padding: 10px;
                color: #D4D4D4;
            }
            QScrollBar:vertical {
                background: #232323;
                width: 20px;
                border-radius: 0px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: #4A4D51;
                border-radius: 0px;
                min-height: 20px;
                margin: 2px;
            }
            QScrollBar::handle:vertical:hover {
                background: #5A5D61;
            }
            QScrollBar::handle:vertical:pressed {
                background: #6A6D71;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: transparent;
            }
            QScrollBar:horizontal {
                background: #232323;
                height: 12px;
                border-radius: 0px;
                margin: 0px;
            }
            QScrollBar::handle:horizontal {
                background: #4A4D51;
                border-radius: 0px;
                min-width: 20px;
                margin: 2px;
            }
            QScrollBar::handle:horizontal:hover {
                background: #5A5D61;
            }
            QScrollBar::handle:horizontal:pressed {
                background: #6A6D71;
            }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                width: 0px;
            }
            QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
                background: transparent;
            }
        """)

    def _invalidate_indent_guides(self):
        """Mark indentation guides cache as dirty."""
        self._indent_guides_dirty = True

    def _compute_indent_guides(self):
        """
        Compute indentation guides using a robust scope-based approach.
        This method analyzes the actual code structure to draw guides accurately.
        """
        try:
            doc = self.document()
            self._indent_guides_cache = []
            
            if doc.blockCount() == 0:
                self._indent_guides_dirty = False
                return
            
            # Build line data with indent levels
            lines = []
            block = doc.firstBlock()
            while block.isValid():
                text = block.text()
                stripped = text.lstrip()
                
                if stripped:  # Non-empty line
                    indent = len(text) - len(stripped)
                    indent_level = indent // 4  # 4 spaces per indent
                    lines.append({
                        'line_num': block.blockNumber(),
                        'indent': indent_level,
                        'text': stripped,
                        'full_text': text
                    })
                else:  # Empty line
                    lines.append({
                        'line_num': block.blockNumber(),
                        'indent': -1,
                        'text': '',
                        'full_text': text
                    })
                block = block.next()
            
            if not lines:
                self._indent_guides_dirty = False
                return
            
            # Find maximum indent level
            max_indent = max((line['indent'] for line in lines if line['indent'] >= 0), default=0)
            
            # For each indent level, find continuous regions
            for level in range(max_indent + 1):
                i = 0
                while i < len(lines):
                    line = lines[i]
                    
                    # Look for lines with indent greater than current level
                    if line['indent'] > level:
                        start_line = line['line_num']
                        end_line = line['line_num']
                        
                        # Scan forward to find the extent of this indented region
                        j = i + 1
                        while j < len(lines):
                            next_line = lines[j]
                            
                            # Empty lines continue the guide
                            if next_line['indent'] == -1:
                                end_line = next_line['line_num']
                                j += 1
                                continue
                            
                            # Lines with greater indent continue the guide
                            if next_line['indent'] > level:
                                end_line = next_line['line_num']
                                j += 1
                                continue
                            
                            # Lines with equal or less indent end the guide
                            # But we need to check if it's a continuation of the same block
                            if next_line['indent'] <= level:
                                # Stop here
                                break
                            
                            j += 1
                        
                        # Add guide if it spans multiple lines
                        if end_line > start_line:
                            self._indent_guides_cache.append((level, start_line, end_line))
                        
                        i = j
                    else:
                        i += 1
            
            self._indent_guides_dirty = False
        except Exception:
            self._indent_guides_cache = []
            self._indent_guides_dirty = False

    def contextMenuEvent(self, event):
        """Show a styled context menu with standard editor actions."""
        menu = build_editor_context_menu(self)
        menu.exec(event.globalPos())

    def eventFilter(self, obj, event):
        # Clear multi-caret/selections on any non-Alt left click (press or double-click) in viewport or gutter
        if event.type() in (QEvent.MouseButtonPress, QEvent.MouseButtonDblClick):
            try:
                if event.button() == Qt.LeftButton and (event.modifiers() & Qt.AltModifier) == 0:
                    if hasattr(self, 'multi') and self.multi:
                        self.multi.clear()
                        self.viewport().update()
            except Exception:
                pass
        return super().eventFilter(obj, event)

    def mousePressEvent(self, e):
        # Handle clicks on inline color swatches to open color picker before any selection logic
        if e.button() == Qt.LeftButton:
            try:
                if self._handle_color_swatch_click(e):
                    return
            except Exception:
                pass
        # If user clicks without holding Alt, reset multi-cursor state first (so Qt selection replaces old state)
        if e.button() == Qt.LeftButton and not (e.modifiers() & Qt.AltModifier):
            if hasattr(self, 'multi') and self.multi.has_multi():
                self.multi.clear()
                # We need to let the editor process the click to move the primary cursor
                # so we don't return here. We just cleared the extras.

        # Then handle Alt-based multi-cursor
        if hasattr(self, 'multi') and self.multi.handle_mouse_press(e):
            return # The event was handled by the multi-cursor manager

        # Fallback to default behavior if not handled by multi-cursor
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e):
        if hasattr(self, 'multi') and self.multi and self.multi.handle_mouse_move(e):
            return
        super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e):
        # Safety: clear on release of a non-Alt left click as well
        try:
            if e.button() == Qt.LeftButton and (e.modifiers() & Qt.AltModifier) == 0:
                if hasattr(self, 'multi') and self.multi:
                    self.multi.clear()
                    self.viewport().update()
        except Exception:
            pass
        if hasattr(self, 'multi') and self.multi and self.multi.handle_mouse_release(e):
            return
        super().mouseReleaseEvent(e)

    def insertFromMimeData(self, source):
        if hasattr(self, 'multi') and self.multi and self.multi.handle_paste(source):
            return
        super().insertFromMimeData(source)

    # Override copy to support multi-selections (Alt-based)
    def copy(self):
        try:
            if hasattr(self, 'multi') and self.multi and self.multi.has_multi():
                cursors = self.multi.get_all_cursors()
                # Gather only selections
                selected = [c for c in cursors if c.hasSelection()]
                if selected:
                    # Order by position for line-based consistency
                    selected.sort(key=lambda c: (c.selectionStart(), c.selectionEnd()))
                    parts = []
                    for c in selected:
                        txt = c.selectedText()
                        if txt:
                            parts.append(txt.replace('\u2029', '\n'))
                    if parts:
                        QGuiApplication.clipboard().setText('\n'.join(parts))
                        return
        except Exception:
            pass
        # Fallback to default behavior
        try:
            super().copy()
        except Exception:
            pass

    # Override cut to support multi-selections (Alt-based)
    def cut(self):
        try:
            if hasattr(self, 'multi') and self.multi and self.multi.has_multi():
                cursors = self.multi.get_all_cursors()
                selected = [c for c in cursors if c.hasSelection()]
                if selected:
                    # Perform a multi-selection aware copy first
                    try:
                        selected.sort(key=lambda c: (c.selectionStart(), c.selectionEnd()))
                        parts = []
                        for c in selected:
                            txt = c.selectedText()
                            if txt:
                                parts.append(txt.replace('\u2029', '\n'))
                        if parts:
                            QGuiApplication.clipboard().setText('\n'.join(parts))
                    except Exception:
                        pass
                    # Now remove the selected texts from bottom to top
                    selected.sort(key=lambda c: c.selectionStart(), reverse=True)
                    self.blockSignals(True)
                    try:
                        for c in selected:
                            c.removeSelectedText()
                    finally:
                        self.blockSignals(False)
                    self.highlightCurrentLine()
                    return
        except Exception:
            pass
        # Fallback to default behavior
        try:
            super().cut()
        except Exception:
            pass

    def _update_cargo_toml_highlights_on_edit(self):
        """Keep Cargo.toml error highlights persistent when editing the file."""
        try:
            # Only process if we have Cargo.toml error highlights
            if not hasattr(self, 'cargo_toml_error_selections') or not self.cargo_toml_error_selections:
                return
            
            # Re-scan and re-apply highlights to the [dependencies] section
            # This ensures highlights persist even when text is added/removed
            text = self.toPlainText()
            lines = text.split('\n')
            
            in_dependencies = False
            dependencies_start_line = -1
            dependencies_end_line = -1
            
            for i, line in enumerate(lines):
                stripped = line.strip()
                
                if stripped == '[dependencies]':
                    in_dependencies = True
                    dependencies_start_line = i
                    continue
                
                if in_dependencies:
                    if stripped.startswith('[') and stripped.endswith(']'):
                        dependencies_end_line = i - 1
                        break
                    if i == len(lines) - 1:
                        dependencies_end_line = i
            
            # Rebuild the highlights - only for non-empty lines
            if dependencies_start_line >= 0:
                if dependencies_end_line < dependencies_start_line:
                    dependencies_end_line = len(lines) - 1
                
                self.cargo_toml_error_selections = []
                
                current_line = dependencies_start_line
                while current_line <= dependencies_end_line:
                    # Only highlight lines that have content (not empty lines)
                    if current_line < len(lines) and lines[current_line].strip():
                        block = self.document().findBlockByLineNumber(current_line)
                        if block.isValid():
                            selection = QTextEdit.ExtraSelection()
                            selection.format.setBackground(QColor(139, 69, 69, 40))
                            selection.format.setProperty(QTextFormat.FullWidthSelection, True)
                            cursor = QTextCursor(block)
                            cursor.clearSelection()
                            selection.cursor = cursor
                            self.cargo_toml_error_selections.append(selection)
                    current_line += 1
        except Exception:
            pass

    def expandSelectionVSCodeLike(self):
        if hasattr(self, 'multi') and self.multi:
            self.multi.expand_selection()

    def shrinkSelectionVSCodeLike(self):
        if hasattr(self, 'multi') and self.multi:
            self.multi.shrink_selection()

    def paintEvent(self, event):
        """
        **SIMPLE INDENTATION GUIDE LINES**
        Draws indentation guide lines for every visible line based on its indentation.
        Empty lines inherit indentation from surrounding context.
        """
        # Paint text and selections FIRST
        super().paintEvent(event)
        
        # Draw indentation guide lines
        try:
            painter = QPainter(self.viewport())
            painter.setRenderHint(QPainter.Antialiasing, False)  # Crisp lines
            
            # Get viewport info
            viewport_rect = self.viewport().rect()
            char_width = self.fontMetrics().horizontalAdvance(' ')
            horizontal_offset = self.horizontalScrollBar().value()
            
            # Guide line color (brighter gray for better visibility)
            line_color = QColor("#666666")
            painter.setPen(QPen(line_color, 1))  # 2px width for better visibility
            
            # Track the last non-empty line's indent to continue guides through empty lines
            last_indent_levels = 0
            
            # Iterate through visible blocks
            block = self.firstVisibleBlock()
            while block.isValid():
                block_geom = self.blockBoundingGeometry(block).translated(self.contentOffset())
                
                # Stop if we're past the visible area
                if block_geom.top() > viewport_rect.bottom():
                    break
                
                # Only process visible blocks
                if block.isVisible() and block_geom.bottom() >= viewport_rect.top():
                    text = block.text()
                    
                    # Determine indentation level for this line
                    if text and not text.isspace():
                        # Non-empty line: calculate actual indentation
                        stripped = text.lstrip()
                        indent = len(text) - len(stripped)
                        indent_levels = indent // 4
                        last_indent_levels = indent_levels
                    else:
                        # Empty line: use the last non-empty line's indentation
                        indent_levels = last_indent_levels
                    
                    # Draw a guide line for each indentation level
                    for level in range(indent_levels):
                        x_pos = (level * 4 * char_width) + 6 - horizontal_offset
                        
                        # Draw line for this block's height
                        y_top = max(block_geom.top(), viewport_rect.top())
                        y_bottom = min(block_geom.bottom(), viewport_rect.bottom())
                        
                        if y_bottom > y_top:
                            painter.drawLine(
                                int(x_pos), int(y_top),
                                int(x_pos), int(y_bottom)
                            )
                
                block = block.next()
            
            # Draw multi-cursor carets
            if hasattr(self, 'multi') and self.multi:
                self.multi.paint_additional_carets(painter)
            
            painter.end()
        except Exception:
            pass
