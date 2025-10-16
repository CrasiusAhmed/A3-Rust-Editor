from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QTextCursor, QColor, QPainter, QPalette, QGuiApplication
from PySide6.QtWidgets import QTextEdit

class MultiCursorManager:
    """
    Provides VS Code-like multi-cursor and multi-selection behaviors for a QPlainTextEdit-based editor.
    Features:
    - Alt+Click to add additional carets
    - Alt+Drag for column selection (adds a caret per line at the same column)
    - Ctrl+Alt+Up/Down to add caret above/below at the same column
    - Ctrl+D add selection to next match; Ctrl+F2 select all occurrences
    - Alt+Shift+I insert cursors at end of each selected line
    - Alt+Shift+Right expand selection, Alt+Shift+Left shrink selection
    - Replicates text insertions/deletions/Enter/Tab across all active carets
    """
    def __init__(self, editor):
        self.editor = editor
        # Secondary carets as list of QTextCursor (primary caret is editor.textCursor())
        self.extra_carets = []
        # Column selection (Alt+Drag) state
        self._dragging_column_select = False
        self._drag_anchor_block = None
        self._drag_anchor_column = 0
        self._blink_visible = True
        self._blink_timer = QTimer(editor)
        self._blink_timer.timeout.connect(self._toggle_blink)
        try:
            ft = QGuiApplication.cursorFlashTime()
            interval = max(200, int(ft / 2)) if ft and ft > 0 else 500
        except Exception:
            interval = 500
        self._blink_timer.start(interval)
        # Free-form Alt+drag range selection state (when an initial selection exists)
        self._range_select_active = False
        self._range_select_anchor_pos = None
        self._range_select_index = -1

    # ---------------------- Public API ----------------------
    def clear(self):
        self.extra_carets = []
        self._dragging_column_select = False
        self._drag_anchor_block = None
        self._drag_anchor_column = 0
        self._range_select_active = False
        self._range_select_anchor_pos = None
        self._range_select_index = -1
        # Restore the primary cursor when clearing multi-cursors
        self.editor.setCursorWidth(2)
        self.editor.highlightCurrentLine()

    def has_multi(self):
        return len(self.extra_carets) > 0

    def get_all_cursors(self):
        cursors = [self.editor.textCursor()]
        cursors.extend(self._clone_cursors(self.extra_carets))
        # Deduplicate by range/position, preserving order
        unique = []
        seen = set()
        for c in cursors:
            key = (c.selectionStart(), c.selectionEnd()) if c.hasSelection() else (c.position(), c.position())
            if key in seen:
                continue
            seen.add(key)
            unique.append(c)
        return unique

    def _toggle_caret_at_position(self, pos):
        found_index = -1
        for i, c in enumerate(self.extra_carets):
            if c.position() == pos:
                found_index = i
                break
        if found_index != -1:
            del self.extra_carets[found_index]
        else:
            c = QTextCursor(self.editor.document())
            c.setPosition(pos)
            self._append_or_merge(c)
            self._reset_blink()

    def add_caret_at(self, pos_cursor: QTextCursor, select_word=False, selection=None):
        c = QTextCursor(pos_cursor)
        if selection and isinstance(selection, tuple) and len(selection) == 2:
            c.setPosition(selection[0])
            c.setPosition(selection[1], QTextCursor.KeepAnchor)
        elif select_word:
            c.select(QTextCursor.WordUnderCursor)
        self._append_or_merge(c)
        self._reset_blink()
        self.editor.highlightCurrentLine()

    def add_caret_above(self):
        # Add caret above for each caret (primary + extra)
        # Use the primary caret's column as the persistent target to preserve alignment across empty lines
        base = self.editor.textCursor()
        base_block = base.block()
        base_col = base.position() - base_block.position()
        new_carets = []
        for cur in self.get_all_cursors():
            block = cur.block()
            if not block.previous().isValid():
                continue
            prev_block = block.previous()
            text = prev_block.text()
            target_col = min(base_col, len(text))
            nc = QTextCursor(prev_block)
            nc.setPosition(prev_block.position() + target_col)
            new_carets.append(nc)
        for nc in new_carets:
            self._append_or_merge(nc)
        if new_carets:
            self._reset_blink()
        self.editor.highlightCurrentLine()

    def add_caret_below(self):
        # Use the primary caret's column as the persistent target to preserve alignment across empty lines
        base = self.editor.textCursor()
        base_block = base.block()
        base_col = base.position() - base_block.position()
        new_carets = []
        for cur in self.get_all_cursors():
            block = cur.block()
            if not block.next().isValid():
                continue
            next_block = block.next()
            text = next_block.text()
            target_col = min(base_col, len(text))
            nc = QTextCursor(next_block)
            nc.setPosition(next_block.position() + target_col)
            new_carets.append(nc)
        for nc in new_carets:
            self._append_or_merge(nc)
        if new_carets:
            self._reset_blink()
        self.editor.highlightCurrentLine()

    def add_carets_at_line_ends(self):
        # Alt+Shift+I: add a cursor to end of each selected line
        cur = self.editor.textCursor()
        start_block = cur.selectionStart()
        end_block = cur.selectionEnd()
        sblock = self.editor.document().findBlock(start_block)
        eblock = self.editor.document().findBlock(end_block)
        # Ensure inclusive of line containing end
        block = sblock
        positions = []
        while block.isValid():
            text = block.text()
            pos = block.position() + len(text)
            positions.append(pos)
            if block == eblock:
                break
            block = block.next()
        for p in positions:
            c = QTextCursor(self.editor.document())
            c.setPosition(p)
            self._append_or_merge(c)
        if positions:
            self._reset_blink()
        self.editor.highlightCurrentLine()

    def select_next_occurrence(self):
        cur = self.editor.textCursor()
        if not cur.hasSelection():
            cur.select(QTextCursor.WordUnderCursor)
            self.editor.setTextCursor(cur)
        if not cur.hasSelection():
            return
        sel_text = cur.selectedText()
        # Find from end of last selection
        search_start = cur.selectionEnd()
        doc = self.editor.document()
        nxt = doc.find(sel_text, search_start)
        if nxt.isNull():
            # Wrap
            nxt = doc.find(sel_text, 0)
        # Avoid adding a selection that overlaps existing ones
        if not nxt.isNull():
            self._append_or_merge(nxt)
            self._reset_blink()
        self.editor.highlightCurrentLine()

    def select_all_occurrences(self):
        cur = self.editor.textCursor()
        if not cur.hasSelection():
            cur.select(QTextCursor.WordUnderCursor)
            self.editor.setTextCursor(cur)
        if not cur.hasSelection():
            return
        sel_text = cur.selectedText()
        # Clear extras first and rebuild from scratch
        self.extra_carets = []
        c = self.editor.document().find(sel_text, 0)
        # Keep the first match as primary selection if it matches current primary
        current_range = (cur.selectionStart(), cur.selectionEnd())
        primary_set = False
        while not c.isNull():
            rng = (c.selectionStart(), c.selectionEnd())
            if not primary_set and rng == current_range:
                primary_set = True
            else:
                self._append_or_merge(QTextCursor(c))
            c = self.editor.document().find(sel_text, c)
        if self.extra_carets:
            self._reset_blink()
        self.editor.highlightCurrentLine()

    def expand_selection(self):
        # VS Code-like expansion per caret; write results back to editor and extras
        cursors = self.get_all_cursors()
        new_primary = None
        new_extras = []
        for idx, cur in enumerate(cursors):
            c = QTextCursor(cur)
            if not c.hasSelection():
                # Prefer intuitive cases first: word under caret, then structures
                blk = c.block()
                rel = c.position() - blk.position()
                line = blk.text()
                ch_here = line[rel] if 0 <= rel < len(line) else ''
                ch_left = line[rel-1] if 0 < rel <= len(line) else ''
                # If caret is on a colon or the line ends with a colon, expand to the Python block first
                if ch_here == ':' or line.strip().endswith(':'):
                    if not self._expand_python_block(c):
                        c.select(QTextCursor.WordUnderCursor)
                # If caret is on a comma inside brackets, expand to the entire bracketed scope (include parentheses)
                elif ch_here == ',' and self._is_inside_bracket_scope(c.position()):
                    if not self._expand_to_enclosing_scope(c, include_delims=True):
                        if not self._expand_to_enclosing(c):
                            c.select(QTextCursor.WordUnderCursor)
                # If caret is exactly on a bracket and immediately after an identifier, prefer selecting the word first
                elif ch_here in '()[]{}':
                    if (ch_left.isalnum() or ch_left == '_'):
                        c.select(QTextCursor.WordUnderCursor)
                    else:
                        if not self._expand_to_enclosing(c):
                            c.select(QTextCursor.WordUnderCursor)
                # If caret is on/next-to an identifier, select the word first (prevent over-expansion)
                elif (ch_here.isalnum() or ch_here == '_' or ch_left.isalnum() or ch_left == '_'):
                    c.select(QTextCursor.WordUnderCursor)
                else:
                    # Try nearest encloser (quotes/brackets)
                    if not self._expand_to_enclosing(c):
                        c.select(QTextCursor.WordUnderCursor)
            else:
                # Try to expand bracketed selection (inside -> outside)
                if not self._expand_to_enclosing(c):
                    # Try to expand to Python indentation block
                    if not self._expand_python_block(c):
                        # Fallback: expand to full lines covering selection
                        start = c.selectionStart()
                        end = c.selectionEnd()
                        bs = self.editor.document().findBlock(start)
                        be = self.editor.document().findBlock(end)
                        new_start = bs.position()
                        new_end = be.position() + be.length() - 1
                        c.setPosition(new_start)
                        c.setPosition(new_end, QTextCursor.KeepAnchor)
            if idx == 0:
                new_primary = c
            else:
                new_extras.append(c)
        if new_primary is not None:
            self.editor.setTextCursor(new_primary)
        self.extra_carets = new_extras
        self.editor.highlightCurrentLine()

    def shrink_selection(self):
        # Shrink selection per caret; write results back
        cursors = self.get_all_cursors()
        new_primary = None
        new_extras = []
        for idx, cur in enumerate(cursors):
            c = QTextCursor(cur)
            if c.hasSelection():
                # Keep existing shrink behavior when there's a selection: reduce to word at start
                pos = c.selectionStart()
                c.setPosition(pos)
                c.select(QTextCursor.WordUnderCursor)
            else:
                # No selection: select the entire current line (without the newline)
                block = c.block()
                line_text = block.text()
                start = block.position()
                end = start + len(line_text)
                c.setPosition(start)
                c.setPosition(end, QTextCursor.KeepAnchor)
            if idx == 0:
                new_primary = c
            else:
                new_extras.append(c)
        if new_primary is not None:
            self.editor.setTextCursor(new_primary)
        self.extra_carets = new_extras
        self.editor.highlightCurrentLine()

    def get_extra_selections(self):
        """Return QTextEdit.ExtraSelection list representing extra selections for painting."""
        sels = []
        # Selection highlight color: use the editor's selection highlight color at 80% opacity
        pal = self.editor.palette()
        base_col = pal.color(QPalette.Highlight)
        bg_sel = QColor(base_col)
        try:
            bg_sel.setAlphaF(0.8)
        except Exception:
            bg_sel.setAlpha(204)
        for c in self.extra_carets:
            sel = QTextEdit.ExtraSelection()
            sel.cursor = c
            if c.hasSelection():
                sel.format.setBackground(bg_sel)
            else:
                # Non-selected caret will be drawn as a blinking line in paint_additional_carets
                pass
            sels.append(sel)
        return sels

    def paint_additional_carets(self, painter: QPainter):
        if not self._blink_visible:
            return
        painter.save()
        # Match the editor's caret color and width for consistency
        color = self.editor.palette().color(QPalette.Text)
        
        # When we have multi-cursors, also draw the primary cursor ourselves
        # so it blinks in sync with the extra cursors
        if self.has_multi():
            primary = self.editor.textCursor()
            if not primary.hasSelection():
                r = self.editor.cursorRect(primary)
                x = r.left()
                width = max(1, self.editor.cursorWidth())
                painter.fillRect(x, r.top(), width, r.height(), color)
        
        for c in self.extra_carets:
            if c.hasSelection():
                continue
            r = self.editor.cursorRect(c)
            x = r.left()
            width = max(1, self.editor.cursorWidth())
            painter.fillRect(x, r.top(), width, r.height(), color)
        painter.restore()

    # ---------------------- Event handlers ----------------------
    def handle_mouse_press(self, e):
        # If it's a regular left click (no Alt), clear all extra cursors
        if e.button() == Qt.LeftButton and not (e.modifiers() & Qt.AltModifier):
            self.clear()
            return False  # Let Qt handle the normal behavior

        if e.button() == Qt.LeftButton and (e.modifiers() & Qt.AltModifier):
            tc = self.editor.cursorForPosition(e.position().toPoint())
            has_primary_selection = self.editor.textCursor().hasSelection()
            
            # If there is already a primary selection and user Alt+drags, create a new free-form selection
            # rather than column selection. Shift still forces word selection on click.
            if has_primary_selection and not (e.modifiers() & Qt.ShiftModifier):
                # Convert primary selection to extra caret first (avoid duplicates)
                primary_cursor = self.editor.textCursor()
                self._append_or_merge(QTextCursor(primary_cursor))
                
                # Start a word selection at click, and enable range adjust if the user drags
                c = QTextCursor(tc)
                c.select(QTextCursor.WordUnderCursor)
                self._append_or_merge(c)
                self._reset_blink()
                self._range_select_active = True
                self._range_select_anchor_pos = tc.position()
                self._range_select_index = len(self.extra_carets) - 1
                
                # Clear primary selection
                new_cursor = QTextCursor(self.editor.document())
                new_cursor.setPosition(tc.position())
                self.editor.setTextCursor(new_cursor)
                
                self.editor.highlightCurrentLine()
                return True
            else:
                # Default Alt+Click behavior: toggle caret or select word when Shift held or primary has selection
                select_word = bool(e.modifiers() & Qt.ShiftModifier) or has_primary_selection
                if select_word:
                    c = QTextCursor(tc)
                    c.select(QTextCursor.WordUnderCursor)
                    self._append_or_merge(c)
                    self._reset_blink()
                else:
                    self._toggle_caret_at_position(tc.position())
                self._start_column_drag(tc)
                self.editor.highlightCurrentLine()
                return True
        return False

    def handle_mouse_move(self, e):
        if self._range_select_active and (e.buttons() & Qt.LeftButton) and (e.modifiers() & Qt.AltModifier):
            pos_cur = self.editor.cursorForPosition(e.position().toPoint())
            try:
                idx = self._range_select_index
                if 0 <= idx < len(self.extra_carets):
                    c = self.extra_carets[idx]
                    c.setPosition(self._range_select_anchor_pos)
                    c.setPosition(pos_cur.position(), QTextCursor.KeepAnchor)
                    self.editor.viewport().update()
            except Exception:
                pass
            return True
        if self._dragging_column_select and (e.buttons() & Qt.LeftButton) and (e.modifiers() & Qt.AltModifier):
            pos_cur = self.editor.cursorForPosition(e.position().toPoint())
            self._update_column_drag(pos_cur)
            return True
        return False

    def handle_mouse_release(self, e):
        if self._range_select_active:
            self._range_select_active = False
            return True
        if self._dragging_column_select:
            self._dragging_column_select = False
            return True
        return False

    def handle_key_press(self, e):
        # Navigation that modifies multi-caret sets
        if (e.modifiers() & Qt.ControlModifier) and (e.modifiers() & Qt.AltModifier) and e.key() == Qt.Key_Up:
            self.add_caret_above()
            return True
        if (e.modifiers() & Qt.ControlModifier) and (e.modifiers() & Qt.AltModifier) and e.key() == Qt.Key_Down:
            self.add_caret_below()
            return True
        if (e.modifiers() & Qt.ControlModifier) and e.key() == Qt.Key_D:
            self.select_next_occurrence()
            return True
        if (e.modifiers() & Qt.ControlModifier) and e.key() == Qt.Key_F2:
            self.select_all_occurrences()
            return True
        if (e.modifiers() & Qt.AltModifier) and (e.modifiers() & Qt.ShiftModifier) and e.key() == Qt.Key_I:
            self.add_carets_at_line_ends()
            return True
        if (e.modifiers() & Qt.AltModifier) and (e.modifiers() & Qt.ShiftModifier) and e.key() == Qt.Key_Right:
            self.expand_selection()
            return True
        if (e.modifiers() & Qt.AltModifier) and (e.modifiers() & Qt.ShiftModifier) and e.key() == Qt.Key_Left:
            self.shrink_selection()
            return True

        # If we have multi-caret state, replicate edits
        if self.has_multi():
            if e.key() in (Qt.Key_Return, Qt.Key_Enter):
                self._apply_enter_all()
                return True
            if e.key() == Qt.Key_Tab:
                self._apply_text_all('    ')
                return True
            if e.key() == Qt.Key_Backspace:
                self._apply_backspace_all()
                return True
            if e.key() == Qt.Key_Delete:
                self._apply_delete_all()
                return True
            # Printable text
            if e.text() and e.text().isprintable():
                self._apply_text_all(e.text())
                return True
        return False

    def handle_paste(self, mime):
        if not self.has_multi():
            return False
        text = mime.text()
        if not text:
            return False
        cursors = self.get_all_cursors()
        parts = text.splitlines()
        # Prefer mapping to selections only; ignore plain carets for line-wise paste
        selected = [c for c in cursors if c.hasSelection()]
        if selected and len(parts) == len(selected):
            # Map top-to-bottom selections to lines, but apply edits bottom-to-top
            ordered_asc = sorted(selected, key=lambda c: c.selectionStart())
            pairs = list(zip(ordered_asc, parts))
            mc = QTextCursor(self.editor.textCursor())
            mc.beginEditBlock()
            try:
                self.editor.blockSignals(True)
                for c, part in reversed(pairs):
                    c.insertText(part)
            finally:
                self.editor.blockSignals(False)
                mc.endEditBlock()
            self.editor.highlightCurrentLine()
        elif not selected and len(parts) == len(cursors):
            ordered_asc = sorted(cursors, key=lambda c: c.selectionStart() if c.hasSelection() else c.position())
            pairs = list(zip(ordered_asc, parts))
            mc = QTextCursor(self.editor.textCursor())
            mc.beginEditBlock()
            try:
                self.editor.blockSignals(True)
                for c, part in reversed(pairs):
                    c.insertText(part)
            finally:
                self.editor.blockSignals(False)
                mc.endEditBlock()
            self.editor.highlightCurrentLine()
        else:
            # Broadcast same text to all carets/selections
            self._apply_text_all(text)
        return True

    # ---------------------- Internal helpers ----------------------
    def _clone_cursors(self, cursors):
        return [QTextCursor(c) for c in cursors]

    def _append_or_merge(self, cursor: QTextCursor):
        # Avoid duplicates or overlapping ranges
        rng = (cursor.selectionStart(), cursor.selectionEnd()) if cursor.hasSelection() else (cursor.position(), cursor.position())
        for i, c in enumerate(self.extra_carets):
            rr = (c.selectionStart(), c.selectionEnd()) if c.hasSelection() else (c.position(), c.position())
            if rr == rng:
                return
        self.extra_carets.append(cursor)

    def _toggle_blink(self):
        self._blink_visible = not self._blink_visible
        self.editor.viewport().update()

    def _reset_blink(self):
        """Reset the blink animation to visible state and restart the timer.
        This ensures all cursors blink in sync when a new cursor is added."""
        self._blink_visible = True
        self._blink_timer.stop()
        self._blink_timer.start()
        
        # Hide the Qt-managed primary cursor when we have multi-cursors
        # We'll draw it ourselves in paint_additional_carets so it blinks in sync
        if self.has_multi():
            self.editor.setCursorWidth(0)
        
        self.editor.viewport().update()

    def _start_column_drag(self, anchor_cursor: QTextCursor):
        self._dragging_column_select = True
        self._drag_anchor_block = anchor_cursor.block()
        self._drag_anchor_column = anchor_cursor.position() - anchor_cursor.block().position()

    def _update_column_drag(self, pos_cursor: QTextCursor):
        if not self._dragging_column_select or not self._drag_anchor_block:
            return
        # Create a caret per line between anchor block and current block at the anchor column
        start_block = self._drag_anchor_block
        end_block = pos_cursor.block()
        # Clear extras for live preview based on drag
        self.extra_carets = []
        doc = self.editor.document()
        b = start_block
        step_forward = start_block.position() <= end_block.position()
        def _iter_blocks(a, b):
            blk = a
            while True:
                yield blk
                if blk == b:
                    break
                blk = blk.next() if step_forward else blk.previous()
        for blk in _iter_blocks(start_block, end_block):
            text = blk.text()
            col = min(self._drag_anchor_column, len(text))
            c = QTextCursor(blk)
            c.setPosition(blk.position() + col)
            self.extra_carets.append(c)
        self.editor.viewport().update()

    def _apply_text_all(self, text: str):
        cursors = self.get_all_cursors()
        # Sort by position descending to avoid shifting ranges during edits
        cursors.sort(key=lambda c: c.selectionStart() if c.hasSelection() else c.position(), reverse=True)
        mc = QTextCursor(self.editor.textCursor())
        mc.beginEditBlock()
        try:
            self.editor.blockSignals(True)
            for c in cursors:
                c.insertText(text)
        finally:
            self.editor.blockSignals(False)
            mc.endEditBlock()
        self.editor.highlightCurrentLine()

    def _apply_backspace_all(self):
        cursors = self.get_all_cursors()
        cursors.sort(key=lambda c: c.selectionStart() if c.hasSelection() else c.position(), reverse=True)
        mc = QTextCursor(self.editor.textCursor())
        mc.beginEditBlock()
        try:
            self.editor.blockSignals(True)
            for c in cursors:
                if c.hasSelection():
                    c.removeSelectedText()
                else:
                    # Delete previous character if possible
                    pos = c.position()
                    if pos > c.block().position():
                        c.setPosition(pos - 1, QTextCursor.KeepAnchor)
                        c.removeSelectedText()
        finally:
            self.editor.blockSignals(False)
            mc.endEditBlock()
        self.editor.highlightCurrentLine()

    def _apply_delete_all(self):
        cursors = self.get_all_cursors()
        cursors.sort(key=lambda c: c.selectionStart() if c.hasSelection() else c.position(), reverse=True)
        mc = QTextCursor(self.editor.textCursor())
        mc.beginEditBlock()
        try:
            self.editor.blockSignals(True)
            for c in cursors:
                if c.hasSelection():
                    c.removeSelectedText()
                else:
                    # Delete next character if exists
                    block_end = c.block().position() + c.block().length() - 1
                    if c.position() < block_end:
                        c.setPosition(c.position() + 1, QTextCursor.KeepAnchor)
                        c.removeSelectedText()
        finally:
            self.editor.blockSignals(False)
            mc.endEditBlock()
        self.editor.highlightCurrentLine()

    def _apply_enter_all(self):
        # Apply VS Code-like enter behavior per caret
        cursors = self.get_all_cursors()
        cursors.sort(key=lambda c: c.selectionStart() if c.hasSelection() else c.position(), reverse=True)
        mc = QTextCursor(self.editor.textCursor())
        mc.beginEditBlock()
        try:
            self.editor.blockSignals(True)
            for c in cursors:
                # Determine indentation for the line where caret is
                block = c.block()
                line = block.text()
                indent = ''
                for ch in line:
                    if ch in (' ', '\t'):
                        indent += ch
                    else:
                        break
                stripped = line.strip()
                increase = (
                    stripped.endswith(':') or
                    stripped.startswith('class ') or
                    stripped.startswith('def ') or
                    stripped.startswith('if ') or
                    stripped.startswith('elif ') or
                    stripped.startswith('else:') or
                    stripped.startswith('for ') or
                    stripped.startswith('while ') or
                    stripped.startswith('try:') or
                    stripped.startswith('except') or
                    stripped.startswith('finally:') or
                    stripped.startswith('with ')
                )
                c.insertText('\n')
                c.insertText(indent + ('    ' if increase else ''))
        finally:
            self.editor.blockSignals(False)
            mc.endEditBlock()
        self.editor.highlightCurrentLine()

    def _expand_to_enclosing(self, c: QTextCursor) -> bool:
        """Expand selection around brackets or quotes.
        Behavior: if current selection equals the inner content, expand to include the delimiters next.
        Applies to (), [], {}, ' ', " ".
        """
        text = self.editor.toPlainText()
        # Determine base position
        if c.hasSelection():
            pos = c.selectionStart()
            cur_start = c.selectionStart()
            cur_end = c.selectionEnd()
        else:
            pos = c.position()
            cur_start = cur_end = pos
        pairs = { '(': ')', '[': ']', '{': '}', '"': '"', "'": "'" }
        open_set = set(pairs.keys())
        close_to_open = {v: k for k, v in pairs.items()}
        # Search backwards for nearest opener or quote
        left = pos
        open_ch = None
        while left >= 0:
            ch = text[left]
            if ch in open_set:
                open_ch = ch
                break
            if ch in close_to_open:
                # skip over a closed region by scanning to its opener
                target_open = close_to_open[ch]
                depth = 1
                i = left - 1
                while i >= 0:
                    ch2 = text[i]
                    if ch2 == ch:
                        depth += 1
                    elif ch2 == target_open:
                        depth -= 1
                        if depth == 0:
                            left = i
                            break
                    i -= 1
                # continue searching outside that region
            left -= 1
        if open_ch is None:
            return False
        # Find the matching closer
        close_ch = pairs[open_ch]
        depth = 0
        right = left
        L = len(text)
        while right < L:
            ch = text[right]
            if ch == open_ch:
                depth += 1
            elif ch == close_ch:
                depth -= 1
                if depth == 0:
                    inner_start = left + 1
                    inner_end = right
                    outer_start = left
                    outer_end = right + 1
                    # Decide target: outer or inner
                    choose_outer = (cur_start == cur_end and (cur_start == left or cur_start == right))
                    # If current selection equals inner, expand to outer
                    if not choose_outer and (cur_start == inner_start and cur_end == inner_end):
                        choose_outer = True
                    # Compute default target
                    t_start = outer_start if choose_outer else inner_start
                    t_end = outer_end if choose_outer else inner_end
                    if open_ch == '(':
                        # Detect call expression: include preceding dotted identifier
                        k = left - 1
                        name_start = left
                        while k >= 0 and (text[k].isalnum() or text[k] in '._'):
                            name_start = k
                            k -= 1
                        # If there is a name immediately before '('
                        if name_start < left and (text[left-1].isalnum() or text[left-1] in '._'):
                            if cur_start == cur_end and (cur_start == right or cur_start == left):
                                t_start = min(t_start, name_start)
                                t_end = max(t_end, outer_end)
                            elif cur_start == inner_start and cur_end == inner_end:
                                t_start = min(t_start, name_start)
                                t_end = max(t_end, outer_end)
                        # Special case: from ... import ( ... ) -> extend start to 'from '
                        doc = self.editor.document()
                        blk = doc.findBlock(left)
                        if blk.isValid():
                            line_start = blk.position()
                            prefix = text[line_start:outer_start]
                            import re as _re
                            m = _re.search(r'\bfrom\s+\S+\s+import\b', prefix)
                            if m:
                                t_start = min(t_start, line_start + m.start())
                    c.setPosition(t_start)
                    c.setPosition(t_end, QTextCursor.KeepAnchor)
                    return True
            right += 1
        return False

    def _nearest_enclosing_bracket_scope(self, pos: int, text: str):
        """Return (open_index, close_index) for the nearest enclosing (), [], {} around pos, or None."""
        pairs = {'(': ')', '[': ']', '{': '}'}
        openers = set(pairs.keys())
        # Find the nearest opener to the left that actually balances to the right
        i = pos
        while i >= 0:
            ch = text[i]
            if ch in openers:
                # Try to find its matching closer
                target = pairs[ch]
                depth = 1
                j = i + 1
                L = len(text)
                while j < L:
                    ch2 = text[j]
                    if ch2 == ch:
                        depth += 1
                    elif ch2 == target:
                        depth -= 1
                        if depth == 0:
                            # Ensure pos lies between opener and closer
                            if i < pos <= j:
                                return (i, j)
                            else:
                                break
                    j += 1
            i -= 1
        return None

    def _is_inside_bracket_scope(self, pos: int) -> bool:
        return self._nearest_enclosing_bracket_scope(pos, self.editor.toPlainText()) is not None

    def _expand_to_enclosing_scope(self, c: QTextCursor, include_delims: bool = True) -> bool:
        """Select the nearest enclosing bracket scope. If include_delims is True, include the brackets.
        Otherwise select only the inner content."""
        text = self.editor.toPlainText()
        pos = c.selectionStart() if c.hasSelection() else c.position()
        scope = self._nearest_enclosing_bracket_scope(pos, text)
        if not scope:
            return False
        open_i, close_i = scope
        start = open_i if include_delims else open_i + 1
        end = close_i + 1 if include_delims else close_i
        c.setPosition(start)
        c.setPosition(end, QTextCursor.KeepAnchor)
        return True

    def _expand_to_argument(self, c: QTextCursor) -> bool:
        """Expand selection to the argument under the cursor within a comma-separated list
        inside (), [], {} possibly spanning multiple lines. Returns True if expanded.
        """
        text = self.editor.toPlainText()
        pos = c.selectionStart() if c.hasSelection() else c.position()
        scope = self._nearest_enclosing_bracket_scope(pos, text)
        if not scope:
            return False
        open_i, close_i = scope
        # Backward scan within scope
        depth = 0
        i = pos - 1
        left_bound = open_i + 1
        while i >= open_i + 1:
            ch = text[i]
            if ch in ')]}':
                depth += 1
            elif ch in '([{':
                if depth == 0:
                    break
                depth -= 1
            elif ch == ',' and depth == 0:
                left_bound = i + 1
                break
            i -= 1
        # Forward scan within scope
        depth = 0
        i = pos
        right_bound = close_i
        while i < close_i:
            ch = text[i]
            if ch in '([{':
                depth += 1
            elif ch in ')]}':
                if depth == 0:
                    break
                depth -= 1
            elif ch == ',' and depth == 0:
                right_bound = i
                break
            i += 1
        # Normalize whitespace
        ls = left_bound
        while ls < right_bound and text[ls].isspace():
            ls += 1
        rs = right_bound
        while rs > ls and text[rs - 1].isspace():
            rs -= 1
        if rs <= ls:
            return False
        c.setPosition(ls)
        c.setPosition(rs, QTextCursor.KeepAnchor)
        return True

    def _expand_python_block(self, c: QTextCursor) -> bool:
        """Expand selection to a Python indentation block.
        If cursor is on a line ending with ':', select the block starting at this line.
        If cursor is within an indented suite, climb to its header line.
        """
        doc = self.editor.document()
        block = c.block()
        line = block.text()
        rel = c.position() - block.position()
        ch_here = line[rel] if 0 <= rel < len(line) else ''
        # Determine header candidate
        header_block = None
        if line.strip().endswith(':') or ch_here == ':':
            header_block = block
        else:
            # If inside indented code, climb up to nearest header line ending with ':' with smaller indent
            cur_indent = len(line) - len(line.lstrip())
            b = block.previous()
            tries = 0
            while b.isValid() and tries < 200:
                txt = b.text()
                if txt.strip() and txt.strip().endswith(':'):
                    ind = len(txt) - len(txt.lstrip())
                    if ind < cur_indent:
                        header_block = b
                        break
                tries += 1
                b = b.previous()
        if not header_block:
            return False
        header_text = header_block.text()
        header_indent = len(header_text) - len(header_text.lstrip())
        # Find end of block: subsequent lines with indent strictly greater than header_indent
        end_block = header_block
        b = header_block.next()
        while b.isValid():
            txt = b.text()
            # Stop at blank line that dedents or any line with indent <= header
            if txt.strip():
                ind = len(txt) - len(txt.lstrip())
                if ind <= header_indent:
                    break
            end_block = b
            b = b.next()
        start_pos = header_block.position()
        end_pos = end_block.position() + end_block.length() - 1
        c.setPosition(start_pos)
        c.setPosition(end_pos, QTextCursor.KeepAnchor)
        return True