"""
Smart Auto-Correction System for Rust Code
Like Microsoft Word's spell-check, but for Rust syntax!

Features:
- Fixes typos in keywords (ftn -> fn, eni -> enum, wqs -> fn in context)
- Only corrects when you press Space, punctuation, or other word separators
- Respects case sensitivity (sted won't become Self)
- If you delete a correction, it won't autocorrect that typo again

Code Folding Features:
- Collapse/expand functions, structs, impl blocks, enums, traits
- Fold long comments and documentation blocks
- Visual indicators (▶/▼) in the margin
- Click to toggle fold/unfold
"""

import re
from PySide6.QtCore import Qt, QObject, QEvent, QRect, QSize
from PySide6.QtGui import QTextCursor, QTextCharFormat, QColor, QFont, QPainter, QTextBlock
from PySide6.QtWidgets import QApplication, QWidget, QTextEdit
from Main.snippet_rust import RustSnippetManager


class CodeFoldingWidget(QWidget):
    """
    Widget that displays fold/unfold indicators in the editor margin.
    Shows ▶ for collapsed blocks and ▼ for expanded blocks.
    """
    
    def __init__(self, editor):
        super().__init__(editor)
        self.editor = editor
        self.folded_blocks = set()  # Set of block numbers that are folded
        self.foldable_blocks = {}  # {block_number: (start_line, end_line, block_type)}
        
    def sizeHint(self):
        """Return the width of the folding area."""
        return QSize(20, 0)
    
    def paintEvent(self, event):
        """Draw fold indicators (▶/▼) in the margin."""
        painter = QPainter(self)
        painter.fillRect(event.rect(), QColor(30, 30, 30))  # Dark background
        
        # Get the visible blocks
        block = self.editor.firstVisibleBlock()
        block_number = block.blockNumber()
        top = int(self.editor.blockBoundingGeometry(block).translated(self.editor.contentOffset()).top())
        bottom = top + int(self.editor.blockBoundingRect(block).height())
        
        # Draw fold indicators for each visible block
        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                if block_number in self.foldable_blocks:
                    if block_number in self.folded_blocks:
                        # Collapsed - show RIGHT arrow ▶ (BIGGER)
                        arrow_font = painter.font()
                        arrow_font.setPointSize(14)  # Bigger size
                        arrow_font.setBold(True)
                        painter.setFont(arrow_font)
                        painter.setPen(QColor(180, 180, 180))
                        painter.drawText(2, top, self.width() - 4, 
                                       self.editor.fontMetrics().height(),
                                       Qt.AlignCenter, "▶")
                    else:
                        # Expanded - show DOWN arrow ▼ (normal size)
                        arrow_font = painter.font()
                        arrow_font.setPointSize(10)
                        arrow_font.setBold(False)
                        painter.setFont(arrow_font)
                        painter.setPen(QColor(150, 150, 150))
                        painter.drawText(2, top, self.width() - 4,
                                       self.editor.fontMetrics().height(),
                                       Qt.AlignCenter, "▼")
            
            block = block.next()
            top = bottom
            bottom = top + int(self.editor.blockBoundingRect(block).height())
            block_number += 1
    
    def mousePressEvent(self, event):
        """Handle clicks on fold indicators."""
        if event.button() == Qt.LeftButton:
            # Calculate which line was clicked
            block = self.editor.firstVisibleBlock()
            top = int(self.editor.blockBoundingGeometry(block).translated(self.editor.contentOffset()).top())
            block_number = block.blockNumber()
            
            while block.isValid():
                bottom = top + int(self.editor.blockBoundingRect(block).height())
                
                if top <= event.pos().y() < bottom:
                    # Check if this block is foldable
                    if block_number in self.foldable_blocks:
                        self.toggle_fold(block_number)
                        break
                
                block = block.next()
                top = bottom
                block_number += 1
    
    def toggle_fold(self, block_number):
        """Toggle fold state for a block."""
        if block_number in self.folded_blocks:
            # Unfold
            self.unfold_block(block_number)
        else:
            # Fold
            self.fold_block(block_number)
        
        self.update()
        self.editor.viewport().update()
    
    def fold_block(self, block_number):
        """Fold (collapse) a code block."""
        if block_number not in self.foldable_blocks:
            return
        
        start_line, end_line, block_type = self.foldable_blocks[block_number]
        
        # Hide all blocks between start and end
        block = self.editor.document().findBlockByNumber(start_line + 1)
        while block.isValid() and block.blockNumber() <= end_line:
            block.setVisible(False)
            block = block.next()
        
        self.folded_blocks.add(block_number)
        self.editor.document().markContentsDirty(0, self.editor.document().characterCount())
    
    def unfold_block(self, block_number):
        """Unfold (expand) a code block."""
        if block_number not in self.foldable_blocks:
            return
        
        start_line, end_line, block_type = self.foldable_blocks[block_number]
        
        # Show all blocks between start and end
        block = self.editor.document().findBlockByNumber(start_line + 1)
        while block.isValid() and block.blockNumber() <= end_line:
            block.setVisible(True)
            block = block.next()
        
        self.folded_blocks.discard(block_number)
        self.editor.document().markContentsDirty(0, self.editor.document().characterCount())
    
    def update_foldable_blocks(self):
        """Scan the document and identify foldable blocks with proper brace matching."""
        self.foldable_blocks.clear()
        
        text = self.editor.toPlainText()
        lines = text.split('\n')
        
        # Track all opening braces with their context
        brace_stack = []  # Stack of (line_number, block_type, brace_count)
        
        for i, line in enumerate(lines):
            stripped = line.strip()
            
            # Count braces in this line (excluding those in strings/comments)
            line_for_counting = self._remove_strings_and_comments(line)
            open_braces = line_for_counting.count('{')
            close_braces = line_for_counting.count('}')
            
            # Detect block start patterns
            block_type = None
            
            # Functions: fn name(...) {
            if re.match(r'^\s*(pub\s+)?(async\s+)?(unsafe\s+)?fn\s+\w+', stripped):
                if '{' in line:
                    block_type = 'function'
            
            # Structs: struct Name {
            elif re.match(r'^\s*(pub\s+)?struct\s+\w+', stripped):
                if '{' in line:
                    block_type = 'struct'
            
            # Enums: enum Name {
            elif re.match(r'^\s*(pub\s+)?enum\s+\w+', stripped):
                if '{' in line:
                    block_type = 'enum'
            
            # Impl blocks: impl Name { or impl<T> Name {
            elif re.match(r'^\s*impl\b', stripped):
                if '{' in line:
                    block_type = 'impl'
            
            # Traits: trait Name {
            elif re.match(r'^\s*(pub\s+)?trait\s+\w+', stripped):
                if '{' in line:
                    block_type = 'trait'
            
            # Modules: mod name {
            elif re.match(r'^\s*(pub\s+)?mod\s+\w+', stripped):
                if '{' in line:
                    block_type = 'mod'
            
            # Match blocks: match expr {
            elif re.match(r'^\s*match\s+', stripped):
                if '{' in line:
                    block_type = 'match'
            
            # If/else blocks
            elif re.match(r'^\s*if\s+', stripped) or re.match(r'^\s*else\s*\{', stripped):
                if '{' in line:
                    block_type = 'if'
            
            # For/while loops
            elif re.match(r'^\s*(for|while)\s+', stripped):
                if '{' in line:
                    block_type = 'loop'
            
            # Comment blocks (3+ lines of comments)
            elif stripped.startswith('//'):
                if i > 0 and not lines[i-1].strip().startswith('//'):
                    comment_count = 0
                    j = i
                    while j < len(lines) and lines[j].strip().startswith('//'):
                        comment_count += 1
                        j += 1
                    
                    if comment_count >= 3:
                        self.foldable_blocks[i] = (i, j - 1, 'comment')
            
            # If this line starts a new block, push it to stack
            if block_type and open_braces > 0:
                brace_stack.append([i, block_type, 1])  # Start with 1 open brace
                
                # Handle additional braces on the same line
                for _ in range(open_braces - 1):
                    if brace_stack:
                        brace_stack[-1][2] += 1
                
                # Handle closing braces on the same line
                for _ in range(close_braces):
                    if brace_stack:
                        brace_stack[-1][2] -= 1
                        if brace_stack[-1][2] == 0:
                            start_line, btype, _ = brace_stack.pop()
                            if i - start_line >= 1:
                                self.foldable_blocks[start_line] = (start_line, i, btype)
            
            # If no new block started, just update brace counts
            elif brace_stack:
                # Add opening braces to the most recent block
                for _ in range(open_braces):
                    brace_stack[-1][2] += 1
                
                # Subtract closing braces
                for _ in range(close_braces):
                    if brace_stack:
                        brace_stack[-1][2] -= 1
                        if brace_stack[-1][2] == 0:
                            start_line, btype, _ = brace_stack.pop()
                            if i - start_line >= 1:
                                self.foldable_blocks[start_line] = (start_line, i, btype)
        
        self.update()
    
    def _remove_strings_and_comments(self, line):
        """Remove string literals and comments from a line for accurate brace counting."""
        # Remove string literals (simple approach - doesn't handle escaped quotes perfectly)
        result = re.sub(r'"[^"]*"', '', line)
        result = re.sub(r"'[^']*'", '', result)
        
        # Remove line comments
        if '//' in result:
            result = result[:result.index('//')]
        
        return result


class RustSmartAutoCorrect(QObject):
    """
    Smart auto-correction system that fixes Rust code typos and adds missing syntax.
    Works like Microsoft Word's autocorrect but understands Rust context.
    Also provides code folding functionality.
    
    NEW: Snippet expansion system - type 'fn' and press Tab to create function template!
    """
    
    def __init__(self, editor):
        super().__init__(editor)  # Initialize QObject with parent
        self.editor = editor
        self.enabled = True
        self.correction_in_progress = False
        self.last_corrected_word = None  # Track the last word we corrected (original, corrected, position)
        self.rejected_typos_at_position = {}  # Track typos rejected at specific positions: {(typo, position): True}
        
        # Snippet expansion system - delegate to RustSnippetManager
        self.snippet_manager = RustSnippetManager(editor)
        
        # Code folding widget
        self.folding_widget = None
        self.setup_code_folding()
        
        # Rust keyword typo mappings (common typos -> correct keyword)
        self.keyword_typos = {
            # fn variations
            'ftn': 'fn', 'fnn': 'fn', 'fn.': 'fn', 'fn,': 'fn',
            'fnt': 'fn', 'fnc': 'fn', 'func': 'fn', 'function': 'fn',
            
            # let variations
            'lte': 'let', 'lett': 'let', 'elt': 'let',
            
            # enum variations
            'eni': 'enum', 'enm': 'enum', 'enu': 'enum', 'enym': 'enum',
            
            # struct variations
            'strct': 'struct', 'stuct': 'struct', 'struc': 'struct',
            'stru': 'struct', 'strcuct': 'struct',
            
            # impl variations
            'implt': 'impl', 'imple': 'impl', 'implm': 'impl',
            'imp': 'impl',
            
            # self variations
            'slf': 'self', 'slef': 'self', 'sself': 'self',
            'sefl': 'self', 'sef': 'self',
            
            # Self variations (uppercase)
            'Slf': 'Self', 'Slef': 'Self', 'SElf': 'Self',
            
            # pub variations
            'pbu': 'pub', 'publ': 'pub', 'publi': 'pub',
            
            # mut variations
            'mtu': 'mut', 'mutt': 'mut',
            
            # match variations
            'mtch': 'match', 'mach': 'match', 'matc': 'match',
            
            # return variations
            'retrun': 'return', 'retrn': 'return', 'retur': 'return',
            'ret': 'return', 'rtn': 'return',
            
            # use variations
            'ues': 'use', 'usr': 'use', 'usee': 'use',
            
            # mod variations
            'mdo': 'mod', 'modd': 'mod', 'modl': 'mod',
            
            # trait variations
            'trat': 'trait', 'trai': 'trait', 'triat': 'trait',
            
            # type variations
            'tpe': 'type', 'typ': 'type', 'tpye': 'type',
            
            # const variations
            'cnst': 'const', 'cosnt': 'const', 'conts': 'const',
            
            # static variations
            'statc': 'static', 'stati': 'static', 'statci': 'static',
            
            # if/else variations
            'fi': 'if', 'iff': 'if', 'esle': 'else', 'els': 'else',
            
            # for/while variations
            'ofr': 'for', 'forr': 'for', 'whle': 'while', 'wile': 'while',
            
            # loop variations
            'lop': 'loop', 'looop': 'loop', 'loo': 'loop',
            
            # break/continue variations
            'brak': 'break', 'brk': 'break', 'contiue': 'continue',
            'contine': 'continue', 'contin': 'continue',
            
            # as variations
            'ass': 'as',
            
            # ref variations
            'rfe': 'ref', 'refr': 'ref',
            
            # move variations
            'mvoe': 'move', 'moev': 'move', 'mov': 'move',
            
            # unsafe variations
            'unsaf': 'unsafe', 'unsfe': 'unsafe', 'unsaef': 'unsafe',
            
            # async/await variations
            'asyncc': 'async', 'asyn': 'async', 'awiat': 'await',
            'awit': 'await', 'awai': 'await',
            
            # where variations
            'whre': 'where', 'wher': 'where', 'wehre': 'where',
            
            # crate variations
            'crat': 'crate', 'crae': 'crate', 'craet': 'crate',
            
            # super variations
            'supr': 'super', 'suepr': 'super', 'sper': 'super',
            
            # extern variations
            'extrn': 'extern', 'exten': 'extern', 'externl': 'extern',
            
            # dyn variations
            'dny': 'dyn', 'dyyn': 'dyn',
        }
        
        # Context-aware typo detection (for cases like "wqs" in function context)
        # These need context to determine the correct keyword
        self.context_typos = {
            'wqs': ['fn', 'let', 'const'],  # Could be fn, let, or const depending on context
            'qws': ['fn', 'let', 'const'],
            'was': ['fn', 'let', 'const'],
            'asd': ['fn', 'let', 'const'],
            'sdf': ['fn', 'let', 'const'],
            'dfg': ['fn', 'let', 'const'],
        }
        
        # Rust keywords for validation
        self.rust_keywords = {
            'as', 'break', 'const', 'continue', 'crate', 'else', 'enum', 'extern',
            'false', 'fn', 'for', 'if', 'impl', 'in', 'let', 'loop', 'match',
            'mod', 'move', 'mut', 'pub', 'ref', 'return', 'self', 'Self',
            'static', 'struct', 'super', 'trait', 'true', 'type', 'unsafe',
            'use', 'usec', 'uses', 'where', 'while', 'async', 'await', 'dyn'
        }
        
        # Install event filter to catch special keys
        self.editor.installEventFilter(self)
        
        # Go to Definition feature
        self.ctrl_pressed = False
        self.hover_cursor_position = None
        
        # Enable mouse tracking for hover effects
        self.editor.setMouseTracking(True)
        self.editor.viewport().installEventFilter(self)
        
        # Connect to document changes to update foldable blocks
        self.editor.document().contentsChanged.connect(self.update_folding)
    
    def setup_code_folding(self):
        """Set up the code folding widget in the editor margin."""
        try:
            # Create folding widget
            self.folding_widget = CodeFoldingWidget(self.editor)
            
            # Set up the editor's viewport margins to make room for folding widget
            self.editor.setViewportMargins(20, 0, 0, 0)
            
            # Position the folding widget
            self.update_folding_widget_geometry()
            
            # Connect to editor resize events
            self.editor.updateRequest.connect(self.update_folding_widget_position)
            
            # Show the widget
            self.folding_widget.show()
            
            # Initial scan for foldable blocks
            self.update_folding()
        except Exception as e:
            print(f"Error setting up code folding: {e}")
    
    def update_folding_widget_geometry(self):
        """Update the geometry of the folding widget."""
        if self.folding_widget:
            rect = self.editor.contentsRect()
            self.folding_widget.setGeometry(QRect(rect.left(), rect.top(), 20, rect.height()))
    
    def update_folding_widget_position(self, rect, dy):
        """Update folding widget position when editor scrolls."""
        if self.folding_widget:
            if dy:
                self.folding_widget.scroll(0, dy)
            else:
                self.update_folding_widget_geometry()
            
            self.folding_widget.update()
    
    def update_folding(self):
        """Update the list of foldable blocks."""
        if self.folding_widget:
            self.folding_widget.update_foldable_blocks()
    
    def eventFilter(self, obj, event):
        """Catch special keys to trigger corrections and handle Ctrl+Click for Go to Definition."""
        
        # Handle Ctrl key press/release for Go to Definition
        if event.type() == QEvent.KeyPress:
            if event.key() == Qt.Key_Control:
                self.ctrl_pressed = True
                self.editor.viewport().setCursor(Qt.PointingHandCursor)
        elif event.type() == QEvent.KeyRelease:
            if event.key() == Qt.Key_Control:
                self.ctrl_pressed = False
                self.editor.viewport().setCursor(Qt.IBeamCursor)
                self._clear_hover_highlight()
        
        # Handle mouse move for hover effect when Ctrl is pressed
        if obj == self.editor.viewport() and event.type() == QEvent.MouseMove:
            if self.ctrl_pressed:
                self._handle_ctrl_hover(event)
        
        # Handle Ctrl+Click for Go to Definition
        if obj == self.editor.viewport() and event.type() == QEvent.MouseButtonPress:
            if self.ctrl_pressed and event.button() == Qt.LeftButton:
                self._go_to_definition(event)
                return True  # Consume the event
        
        if obj == self.editor and event.type() == QEvent.KeyPress:
            key = event.key()
            
            # Track backspace key - if user deletes a correction, don't re-correct it
            if key == Qt.Key_Backspace or key == Qt.Key_Delete:
                self._handle_deletion()
            
            # Handle Tab key - snippet expansion or navigation
            if key == Qt.Key_Tab:
                if self.snippet_manager.is_active():
                    # Special handling for derive snippet - try autocomplete first
                    if self.snippet_manager.snippet_trigger == 'derive':
                        # Try to autocomplete inside derive()
                        if self.snippet_manager._try_derive_autocomplete():
                            return True  # Consume the Tab key, autocomplete succeeded
                        # If no autocomplete, check if we should finish
                        cursor = self.editor.textCursor()
                        current_text = self.editor.toPlainText()
                        current_pos = cursor.position()
                        
                        # Check if cursor is still inside derive()
                        search_start = max(0, current_pos - 100)
                        search_text = current_text[search_start:current_pos + 50]
                        derive_start = search_text.rfind('#[derive(')
                        
                        if derive_start != -1:
                            derive_close = search_text.find(')', derive_start)
                            abs_derive_start = search_start + derive_start + 9
                            abs_derive_close = search_start + derive_close
                            
                            # If cursor is inside and no word to autocomplete, just stay active
                            if abs_derive_start <= current_pos <= abs_derive_close:
                                return True  # Consume Tab but don't finish
                        
                        # Otherwise finish the snippet
                        self.snippet_manager.finish()
                        return True
                    else:
                        # For other snippets, navigate to next stage
                        self.snippet_manager.next_stage()
                        return True  # Consume the Tab key
                else:
                    # Check if we should trigger snippet expansion
                    cursor = self.editor.textCursor()
                    word_start, word = self._get_word_before_cursor(cursor)
                    if self.snippet_manager.try_trigger_snippet(word_start, word):
                        return True  # Consume the Tab key
            
            # Handle Escape key - cancel snippet
            elif key == Qt.Key_Escape:
                if self.snippet_manager.is_active():
                    self.snippet_manager.cancel()
                    return True  # Consume the Escape key
            
            # Handle Enter key - confirm snippet stage or add semicolon
            elif key == Qt.Key_Return or key == Qt.Key_Enter:
                if self.snippet_manager.is_active():
                    # For use snippets (use, usec, uses)
                    if self.snippet_manager.snippet_trigger in ['use_std', 'use_crate', 'use_super']:
                        # Always finish and allow normal Enter
                        self.snippet_manager.finish()
                        return False  # Don't consume - let normal Enter work
                    
                    # For simple 2-stage snippets (struct, impl, enum)
                    elif self.snippet_manager.snippet_trigger in ['struct', 'impl', 'enum']:
                        if self.snippet_manager.snippet_stage == 0:
                            # At name stage - move to body (stage 1)
                            self.snippet_manager.confirm_stage()
                            return True  # Consume the Enter key
                        elif self.snippet_manager.snippet_stage >= 1:
                            # At body stage - allow normal Enter (don't advance)
                            return False  # Don't consume - let normal Enter work
                    
                    # For attribute snippets (derive, allow, cfg, test)
                    elif self.snippet_manager.snippet_trigger in ['derive', 'allow', 'cfg', 'test']:
                        # Always finish and allow normal Enter
                        self.snippet_manager.finish()
                        return False  # Don't consume - let normal Enter work
                    
                    # For if and ifl snippets
                    elif self.snippet_manager.snippet_trigger in ['if', 'ifl']:
                        if self.snippet_manager.snippet_stage == 0:
                            # At condition/pattern stage - advance to next stage
                            self.snippet_manager.confirm_stage()
                            return True  # Consume the Enter key
                        else:
                            # At body or value stage - allow normal Enter (don't advance)
                            # User must press Tab to add else-if or else
                            return False  # Don't consume - let normal Enter work
                    
                    # For let snippet
                    elif self.snippet_manager.snippet_trigger == 'let':
                        if self.snippet_manager.snippet_stage == 0:
                            # At name stage - advance to value stage
                            self.snippet_manager.confirm_stage()
                            return True  # Consume the Enter key
                        else:
                            # At value stage - allow normal Enter
                            return False  # Don't consume - let normal Enter work
                    
                    # For fn and async snippets (multi-stage)
                    elif self.snippet_manager.snippet_trigger in ['fn', 'async']:
                        if self.snippet_manager.snippet_stage == 3:
                            # At body stage - allow normal Enter (don't advance)
                            return False  # Don't consume - let normal Enter work
                        else:
                            # Not at body stage - advance to next stage
                            self.snippet_manager.confirm_stage()
                            return True  # Consume the Enter key
                    
                    # Default: allow normal Enter
                    else:
                        return False  # Don't consume - let normal Enter work
                else:
                    self._handle_enter_key()
            
            # Trigger correction on word separators (Space, punctuation, etc.)
            # This is like Microsoft Word - correct when you finish typing a word
            elif key in [Qt.Key_Space, Qt.Key_Period, Qt.Key_Colon, Qt.Key_Semicolon, 
                      Qt.Key_Comma, Qt.Key_ParenLeft, Qt.Key_ParenRight,
                      Qt.Key_BraceLeft, Qt.Key_BraceRight, Qt.Key_BracketLeft, 
                      Qt.Key_BracketRight, Qt.Key_Equal, Qt.Key_Plus, Qt.Key_Minus,
                      Qt.Key_Asterisk, Qt.Key_Slash, Qt.Key_Ampersand, Qt.Key_Bar,
                      Qt.Key_Less, Qt.Key_Greater, Qt.Key_Exclam, Qt.Key_Question]:
                # Check if we're inside attribute block - try attribute autocomplete first
                if self.snippet_manager.is_active() and self.snippet_manager.snippet_trigger in ['derive', 'allow', 'cfg', 'test']:
                    cursor = self.editor.textCursor()
                    if self._is_inside_attribute_block(cursor, self.snippet_manager.snippet_trigger):
                        # Try attribute autocomplete before the key is inserted
                        autocomplete_method = getattr(self.snippet_manager, f'_try_{self.snippet_manager.snippet_trigger}_autocomplete', None)
                        if autocomplete_method and autocomplete_method():
                            # Autocomplete succeeded, now insert the separator key
                            pass  # Let the key be inserted normally
                        # Don't perform regular corrections
                        return False
                
                # Regular corrections for non-derive contexts
                self._perform_corrections()
            
            # Handle opening brace { - check if we need to add ()
            elif key == Qt.Key_BraceLeft:  # {
                self._handle_opening_brace()
        
        return False  # Don't block the event
    
    def _perform_corrections(self):
        """Perform all auto-corrections."""
        if not self.enabled or self.correction_in_progress:
            return
        
        try:
            self.correction_in_progress = True
            
            # Get current cursor position
            cursor = self.editor.textCursor()
            
            # Perform corrections in order of priority
            self._fix_keyword_typos(cursor)
            self._add_missing_brackets(cursor)
            
        finally:
            self.correction_in_progress = False
    
    def _fix_keyword_typos(self, cursor):
        """Fix typos in Rust keywords - like Microsoft Word autocorrect."""
        # Get the word before cursor
        word_start, word = self._get_word_before_cursor(cursor)
        
        if not word or len(word) < 2:
            return
        
        # IMPORTANT: Skip if word contains numbers - it's likely a Rust type (u8, i32, u64, etc.)
        if any(char.isdigit() for char in word):
            return
        
        # Skip if we're inside an attribute block - let attribute autocomplete handle it
        if self._is_inside_attribute_block(cursor, 'derive') or \
           self._is_inside_attribute_block(cursor, 'allow') or \
           self._is_inside_attribute_block(cursor, 'cfg') or \
           self._is_inside_attribute_block(cursor, 'test'):
            return
        
        # Skip if user has rejected this specific typo at this exact position
        if (word, word_start) in self.rejected_typos_at_position:
            return
        
        # Check for direct typo match
        if word in self.keyword_typos:
            correct_word = self.keyword_typos[word]
            
            # IMPORTANT: Match case! If user typed lowercase, don't suggest uppercase
            # If user typed "sted", don't suggest "Self" (uppercase)
            if word[0].isupper() != correct_word[0].isupper():
                return  # Case doesn't match, skip
            
            # First letter must match (case-insensitive for the match itself)
            if word[0].lower() == correct_word[0].lower():
                self._replace_word(word_start, len(word), correct_word)
                self.last_corrected_word = (word, correct_word, word_start)
            return
        
        # Check for context-aware typos (like "wqs" -> "fn" in function context)
        if word in self.context_typos:
            correct_word = self._determine_context_correction(word, cursor)
            if correct_word:
                # First letter must match
                if word[0].lower() == correct_word[0].lower():
                    self._replace_word(word_start, len(word), correct_word)
                    self.last_corrected_word = (word, correct_word, word_start)
            return
        
        # Check for fuzzy matches (Levenshtein distance) with FIRST LETTER PRIORITY
        if word not in self.rust_keywords:
            best_match = self._find_closest_keyword(word)
            if best_match:
                # IMPORTANT: Match case! 
                if word[0].isupper() != best_match[0].isupper():
                    return  # Case doesn't match, skip
                
                # First letter MUST match!
                if word[0].lower() == best_match[0].lower():
                    self._replace_word(word_start, len(word), best_match)
                    self.last_corrected_word = (word, best_match, word_start)
    
    def _determine_context_correction(self, typo, cursor):
        """Determine the correct keyword based on context.
        PRIORITY: First letter MUST match!
        """
        # Get the line text
        block = cursor.block()
        line = block.text()
        
        # Get position of typo in line
        pos_in_block = cursor.position() - block.position()
        
        # Look for context clues
        # If followed by identifier and parentheses, it's likely "fn"
        after_typo = line[pos_in_block:].strip()
        
        first_letter = typo[0].lower()
        
        # Only suggest keywords that start with the same letter
        if re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*\s*\(', after_typo):
            # Function context
            if first_letter == 'f':
                return 'fn'
            return None
        
        # If followed by identifier and equals, it's likely "let"
        if re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*\s*=', after_typo):
            if first_letter == 'l':
                return 'let'
            elif first_letter == 'c':
                return 'const'
            return None
        
        # If inside impl block and followed by identifier with params, it's "fn"
        text_before = self.editor.toPlainText()[:cursor.position()]
        if 'impl' in text_before[-200:]:  # Check last 200 chars
            if re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*\s*\(', after_typo):
                if first_letter == 'f':
                    return 'fn'
        
        return None  # Don't guess if first letter doesn't match
    
    def _find_closest_keyword(self, word):
        """Find the closest Rust keyword using Levenshtein distance.
        PRIORITY: First letter MUST match and case must match!
        IMPORTANT: Don't correct common valid identifiers!
        """
        if len(word) < 2:
            return None
        
        # CRITICAL: Skip common valid identifiers that should NEVER be corrected
        common_identifiers = {
            'ui', 'ctx', 'app', 'egui', 'eframe', 'std', 'io', 'fs', 'env',
            'vec', 'str', 'ok', 'err', 'some', 'none', 'result', 'option',
            'iter', 'into', 'from', 'try', 'box', 'rc', 'arc', 'cell',
            'ref', 'mut', 'ptr', 'mem', 'ops', 'fmt', 'cmp', 'hash',
            'sync', 'thread', 'time', 'path', 'net', 'tcp', 'udp',
            'buf', 'read', 'write', 'seek', 'file', 'dir', 'entry',
            'args', 'vars', 'var', 'key', 'val', 'item', 'elem',
            'idx', 'len', 'cap', 'size', 'count', 'num', 'id',
            'msg', 'req', 'res', 'resp', 'data', 'info', 'config',
            'state', 'status', 'code', 'name', 'value', 'field',
            'method', 'func', 'param', 'arg', 'ret', 'temp', 'tmp',
            'src', 'dst', 'dest', 'source', 'target', 'input', 'output',
            'start', 'end', 'begin', 'finish', 'init', 'done',
            'prev', 'next', 'curr', 'current', 'last', 'first',
            'min', 'max', 'sum', 'avg', 'total', 'delta', 'diff',
            'old', 'new', 'orig', 'copy', 'clone', 'dup',
            'left', 'right', 'top', 'bottom', 'width', 'height',
            'x', 'y', 'z', 'i', 'j', 'k', 'n', 'm', 'c', 'ch',
            'a', 'b', 'e', 'f', 'g', 'h', 'l', 'p', 'q', 'r', 's', 't', 'u', 'v', 'w',
        }
        
        # If word is a common identifier, DON'T correct it
        if word.lower() in common_identifiers:
            return None
        
        # ADDITIONAL CHECK: If word looks like a crate/module name (lowercase, no underscores at start)
        # and is 3+ characters, it's probably intentional
        if len(word) >= 3 and word.islower() and not word.startswith('_'):
            # Check if it's NOT a typo of a keyword by checking distance
            # Only correct if it's VERY close to a keyword (distance 1-2)
            closest_keyword = None
            min_dist = float('inf')
            
            for kw in self.rust_keywords:
                if kw[0].lower() == word[0].lower():
                    dist = self._levenshtein_distance(word, kw)
                    if dist < min_dist:
                        min_dist = dist
                        closest_keyword = kw
            
            # Only correct if distance is 1-2 (very close typo)
            if min_dist > 2:
                return None
        
        first_letter = word[0].lower()
        is_uppercase = word[0].isupper()
        min_distance = float('inf')
        best_match = None
        
        # STEP 1: Only consider keywords that start with the SAME letter AND same case
        matching_keywords = [kw for kw in self.rust_keywords 
                           if kw[0].lower() == first_letter and kw[0].isupper() == is_uppercase]
        
        if not matching_keywords:
            return None  # No keywords start with this letter and case
        
        # STEP 2: Find closest match among keywords with same first letter
        for keyword in matching_keywords:
            # Only consider keywords of similar length (stricter now)
            if abs(len(keyword) - len(word)) > 2:
                continue
            
            distance = self._levenshtein_distance(word.lower(), keyword.lower())
            
            # Only suggest if distance is VERY small (1-2 characters different)
            # This prevents "egui" -> "enum" (distance 3)
            if distance < min_distance and distance <= 2:
                min_distance = distance
                best_match = keyword
        
        # STEP 3: Extra scoring - prioritize if more letters match in order
        if best_match:
            # Count matching letters in sequence
            matches = sum(1 for i, (a, b) in enumerate(zip(word.lower(), best_match.lower())) if a == b)
            # If less than 50% of letters match, don't suggest (stricter now)
            if matches < len(word) * 0.5:
                return None
            
            # STEP 4: Check second-to-last letter (before last letter)
            # This prevents "enso" -> "enum", "enom" -> "enum", etc.
            # Only applies to words with 3+ characters
            if len(word) >= 3 and len(best_match) >= 3:
                word_second_last = word[-2].lower()
                match_second_last = best_match[-2].lower()
                
                # If second-to-last letters don't match, don't suggest
                if word_second_last != match_second_last:
                    return None
        
        return best_match
    
    def _levenshtein_distance(self, s1, s2):
        """Calculate Levenshtein distance between two strings."""
        if len(s1) < len(s2):
            return self._levenshtein_distance(s2, s1)
        
        if len(s2) == 0:
            return len(s1)
        
        previous_row = range(len(s2) + 1)
        for i, c1 in enumerate(s1):
            current_row = [i + 1]
            for j, c2 in enumerate(s2):
                insertions = previous_row[j + 1] + 1
                deletions = current_row[j] + 1
                substitutions = previous_row[j] + (c1 != c2)
                current_row.append(min(insertions, deletions, substitutions))
            previous_row = current_row
        
        return previous_row[-1]
    
    def _handle_deletion(self):
        """Handle backspace/delete key - track if user is deleting a correction (like MS Word)."""
        try:
            # Check if we just corrected something recently
            if self.last_corrected_word:
                cursor = self.editor.textCursor()
                current_pos = cursor.position()
                
                original_word, corrected_word, correction_pos = self.last_corrected_word
                
                # Calculate the end position of the corrected word
                correction_end_pos = correction_pos + len(corrected_word)
                
                # Check if cursor is within or right after the corrected word
                # This means user is deleting the correction
                if correction_pos <= current_pos <= correction_end_pos + 2:
                    # User is deleting the correction at THIS position - reject it here only
                    self.rejected_typos_at_position[(original_word, correction_pos)] = True
                    self.last_corrected_word = None
                elif current_pos > correction_end_pos + 10:
                    # User moved far away, clear the last correction tracking
                    self.last_corrected_word = None
        except Exception:
            pass
    
    def _handle_enter_key(self):
        """Handle Enter key - add semicolon or comma if needed at end of line (SMART)."""
        try:
            cursor = self.editor.textCursor()
            block = cursor.block()
            line = block.text().rstrip()
            
            # Skip if line is empty
            if not line:
                return
            
            # Skip if line already ends with proper punctuation
            if line.endswith(';') or line.endswith('{') or line.endswith('}') or line.endswith(','):
                return
            
            stripped = line.strip()
            
            # Skip comments
            if stripped.startswith('//'):
                return
            
            # Check if we need a COMMA (match arms, enum variants, struct fields, etc.)
            needs_comma = self._check_needs_comma(line, stripped)
            if needs_comma:
                cursor.movePosition(QTextCursor.EndOfLine)
                self.editor.blockSignals(True)
                cursor.insertText(',')
                self.editor.blockSignals(False)
                self.editor.setTextCursor(cursor)
                return
            
            # Check if we need a SEMICOLON (statements, not expressions)
            needs_semicolon = self._check_needs_semicolon(line, stripped)
            if needs_semicolon:
                cursor.movePosition(QTextCursor.EndOfLine)
                self.editor.blockSignals(True)
                cursor.insertText(';')
                self.editor.blockSignals(False)
                self.editor.setTextCursor(cursor)
        except Exception:
            pass
    
    def _check_needs_comma(self, line, stripped):
        """Check if the line needs a comma (match arms, enum variants, struct fields)."""
        try:
            # 1. Match arms with =>
            if '=>' in line:
                if self._is_inside_block_type('match'):
                    return True
            
            # 2. Enum variants (inside enum definition)
            if self._is_inside_block_type('enum'):
                # Skip the enum declaration line itself
                if not (stripped.startswith('enum ') or stripped.startswith('pub enum ')):
                    # Enum variants start with uppercase or are identifiers
                    if stripped and stripped[0].isupper():
                        return True
            
            # 3. Struct fields (inside struct definition with named fields)
            if self._is_inside_block_type('struct'):
                # Skip the struct declaration line itself
                if not (stripped.startswith('struct ') or stripped.startswith('pub struct ')):
                    # Struct fields: "field: Type" or "pub field: Type"
                    if ':' in stripped and not stripped.startswith('//'):
                        return True
            
            return False
        except Exception:
            return False
    
    def _check_needs_semicolon(self, line, stripped):
        """Check if the line needs a semicolon (statements, not expressions)."""
        try:
            # IMPORTANT: Check if this is the last expression before closing brace
            # In Rust, the last expression in a block is implicitly returned (no semicolon)
            if self._is_last_expression_in_block():
                # Check if we're in a function with return type
                if self._is_in_function_with_return_type():
                    # This might be an implicit return - DON'T add semicolon
                    return False
            
            # CRITICAL: Check for method chaining pattern
            # If line ends with ) and might continue with .method() on next line, DON'T add semicolon
            if self._might_be_method_chaining(stripped):
                return False
            
            # Statements that ALWAYS need semicolons:
            
            # 1. let statements (variable declarations)
            if stripped.startswith('let '):
                return True
            
            # 2. return statements (explicit returns)
            if stripped.startswith('return '):
                return True
            
            # 3. break/continue statements
            if stripped in ['break', 'continue'] or stripped.startswith('break ') or stripped.startswith('continue '):
                return True
            
            # 4. use statements (imports)
            if stripped.startswith('use '):
                return True
            
            # 5. Expression statements (function calls, method calls)
            # But NOT if it's a control flow expression (if, match, loop, etc.)
            if not self._is_control_flow_expression(stripped):
                # Check if it looks like a function call or method call
                if '(' in line and ')' in line:
                    # Make sure it's not a function definition
                    if not stripped.startswith('fn ') and not stripped.startswith('async fn '):
                        return True
                
                # Assignment statements (but not in struct/enum definitions)
                if '=' in line and not self._is_inside_block_type('struct') and not self._is_inside_block_type('enum'):
                    # Make sure it's not a function definition or control flow
                    if not stripped.startswith('fn ') and not stripped.startswith('if ') and \
                       not stripped.startswith('while ') and not stripped.startswith('for ') and \
                       not stripped.startswith('match '):
                        return True
            
            return False
        except Exception:
            return False
    
    def _might_be_method_chaining(self, stripped):
        """Check if the line might be part of method chaining (ends with ) and could continue with .)"""
        try:
            # If line ends with closing parenthesis, it might be method chaining
            if stripped.endswith(')'):
                # Check if there's an opening parenthesis (function/method call)
                if '(' in stripped:
                    # This could be method chaining - DON'T add semicolon yet
                    # User will add it manually when they're done chaining
                    return True
            return False
        except Exception:
            return False
    
    def _is_control_flow_expression(self, stripped):
        """Check if the line is a control flow expression (if, match, loop, etc.)."""
        control_flow_keywords = ['if ', 'match ', 'loop', 'while ', 'for ']
        return any(stripped.startswith(kw) for kw in control_flow_keywords)
    
    def _is_last_expression_in_block(self):
        """Check if the current line is the last expression before a closing brace."""
        try:
            cursor = self.editor.textCursor()
            current_pos = cursor.position()
            text = self.editor.toPlainText()
            
            # Look ahead to see if the next non-empty line is a closing brace
            lines = text[current_pos:].split('\n')
            for line in lines[1:]:  # Skip current line
                stripped = line.strip()
                if stripped:
                    # If next non-empty line is }, this is the last expression
                    if stripped.startswith('}'):
                        return True
                    # If it's anything else, it's not the last expression
                    return False
            
            return False
        except Exception:
            return False
    
    def _is_in_function_with_return_type(self):
        """Check if we're inside a function that has a return type (-> Type)."""
        try:
            cursor = self.editor.textCursor()
            current_pos = cursor.position()
            text = self.editor.toPlainText()[:current_pos]
            
            # Look backwards for function definition
            lines = text.split('\n')
            brace_depth = 0
            
            for line in reversed(lines):
                # Count braces
                brace_depth += line.count('}') - line.count('{')
                
                # If we've exited the function, stop
                if brace_depth > 0:
                    break
                
                # Check if this is a function definition with return type
                stripped = line.strip()
                if stripped.startswith('fn ') or stripped.startswith('pub fn ') or \
                   stripped.startswith('async fn ') or stripped.startswith('pub async fn '):
                    # Check if it has a return type (->)
                    if '->' in line:
                        return True
                    # If it has { but no ->, it returns ()
                    if '{' in line:
                        return False
            
            return False
        except Exception:
            return False
    
    def _is_inside_block_type(self, block_type):
        """Check if cursor is inside a specific block type (match, enum, struct, impl, mod, etc.)."""
        try:
            cursor = self.editor.textCursor()
            current_pos = cursor.position()
            text = self.editor.toPlainText()[:current_pos]
            
            lines = text.split('\n')
            brace_depth = 0
            found_block = False
            
            # Scan backwards through lines
            for line in reversed(lines):
                # Count braces on this line
                brace_depth += line.count('}') - line.count('{')
                
                # If we're at depth 0 or positive, we've exited the block
                if brace_depth > 0:
                    break
                
                # Check for the specific block type
                stripped = line.strip()
                
                if block_type == 'match':
                    if stripped.startswith('match ') or ' match ' in line:
                        found_block = True
                        break
                
                elif block_type == 'enum':
                    if stripped.startswith('enum ') or stripped.startswith('pub enum '):
                        found_block = True
                        break
                
                elif block_type == 'struct':
                    if stripped.startswith('struct ') or stripped.startswith('pub struct '):
                        # Make sure it's not a tuple struct (ends with ;)
                        if '{' in line:
                            found_block = True
                            break
                
                elif block_type == 'impl':
                    if stripped.startswith('impl ') or stripped.startswith('pub impl '):
                        found_block = True
                        break
                
                elif block_type == 'mod':
                    if stripped.startswith('mod ') or stripped.startswith('pub mod '):
                        if '{' in line:
                            found_block = True
                            break
                
                elif block_type == 'trait':
                    if stripped.startswith('trait ') or stripped.startswith('pub trait '):
                        found_block = True
                        break
                
                # If we hit another block type, we're not in the target block
                if block_type != 'match' and (stripped.startswith('fn ') or stripped.startswith('match ')):
                    break
            
            return found_block
        except Exception:
            return False
    
    def _is_inside_match_or_enum(self):
        """Check if cursor is inside a match block or enum definition."""
        try:
            cursor = self.editor.textCursor()
            current_pos = cursor.position()
            text = self.editor.toPlainText()[:current_pos]
            
            # Count braces to determine if we're inside a block
            # Look backwards for 'match' or 'enum' keyword
            lines = text.split('\n')
            
            brace_depth = 0
            found_match = False
            found_enum = False
            
            # Scan backwards through lines
            for line in reversed(lines):
                # Count braces on this line
                brace_depth += line.count('}') - line.count('{')
                
                # If we're at depth 0 or positive, we've exited the block
                if brace_depth > 0:
                    break
                
                # Check for match or enum keyword
                stripped = line.strip()
                if stripped.startswith('match ') or ' match ' in line:
                    found_match = True
                    break
                elif stripped.startswith('enum ') or stripped.startswith('pub enum '):
                    found_enum = True
                    break
            
            return found_match or found_enum
        except Exception:
            return False
    
    def _is_inside_enum_definition(self):
        """Check if cursor is specifically inside an enum definition block."""
        try:
            cursor = self.editor.textCursor()
            current_pos = cursor.position()
            text = self.editor.toPlainText()[:current_pos]
            
            # Look backwards for 'enum' keyword
            lines = text.split('\n')
            
            brace_depth = 0
            found_enum = False
            
            # Scan backwards through lines
            for line in reversed(lines):
                # Count braces on this line
                brace_depth += line.count('}') - line.count('{')
                
                # If we're at depth 0 or positive, we've exited the block
                if brace_depth > 0:
                    break
                
                # Check for enum keyword
                stripped = line.strip()
                if stripped.startswith('enum ') or stripped.startswith('pub enum '):
                    found_enum = True
                    break
                
                # If we hit another block type, we're not in an enum
                if stripped.startswith('struct ') or stripped.startswith('impl ') or \
                   stripped.startswith('fn ') or stripped.startswith('match '):
                    break
            
            return found_enum
        except Exception:
            return False
    
    def _handle_opening_brace(self):
        """Handle { key press - add () if missing before function braces."""
        try:
            cursor = self.editor.textCursor()
            block = cursor.block()
            line = block.text()
            pos_in_block = cursor.position() - block.position()
            
            # Get text before cursor
            text_before = line[:pos_in_block].strip()
            
            # Check if this looks like a function without ()
            # Pattern: "fn name" or "fn name<T>" without ()
            if 'fn ' in text_before and '(' not in text_before:
                # Add () before the { is typed
                cursor.insertText('() ')
                self.editor.setTextCursor(cursor)
        except Exception:
            pass
    
    def _add_missing_brackets(self, cursor):
        """Add missing closing brackets ) ] automatically."""
        # Get the line before cursor
        block = cursor.block()
        line = block.text()
        pos_in_block = cursor.position() - block.position()
        
        if pos_in_block <= 0:
            return
        
        # Count unmatched brackets in the line
        open_parens = line[:pos_in_block].count('(') - line[:pos_in_block].count(')')
        open_brackets = line[:pos_in_block].count('[') - line[:pos_in_block].count(']')
        
        # If there are unmatched opening brackets at end of line, close them
        if pos_in_block == len(line) or line[pos_in_block:].strip() == '':
            if open_parens > 0:
                # Check if this looks like a function signature
                if 'fn ' in line or 'impl ' in line:
                    self._insert_at_cursor(')' * open_parens)
            
            if open_brackets > 0:
                self._insert_at_cursor(']' * open_brackets)
    
    def _get_word_before_cursor(self, cursor):
        """Get the word before the cursor position."""
        block = cursor.block()
        text = block.text()
        pos_in_block = cursor.position() - block.position()
        
        if pos_in_block <= 0:
            return None, ""
        
        # Find word boundary (include # for attributes like #derive)
        word_start = pos_in_block
        while word_start > 0 and (text[word_start - 1].isalnum() or text[word_start - 1] in ('_', '#')):
            word_start -= 1
        
        word = text[word_start:pos_in_block]
        absolute_start = block.position() + word_start
        
        return absolute_start, word
    
    def _is_inside_attribute_block(self, cursor, attr_type):
        """Check if the cursor is currently inside an attribute block."""
        current_text = self.editor.toPlainText()
        current_pos = cursor.position()
        
        # Search backwards for the attribute
        search_start = max(0, current_pos - 200)
        search_text = current_text[search_start:current_pos + 50]
        
        if attr_type == 'derive':
            # Find the last #[derive( before cursor
            attr_start = search_text.rfind('#[derive(')
            if attr_start == -1:
                return False
            
            # Find the closing parenthesis
            attr_close = search_text.find(')', attr_start)
            if attr_close == -1:
                return True
            
            # Calculate absolute positions
            abs_attr_start = search_start + attr_start + 9  # After "#[derive("
            abs_attr_close = search_start + attr_close
            
            return abs_attr_start <= current_pos <= abs_attr_close
        
        elif attr_type == 'allow':
            # Find the last #[allow( before cursor
            attr_start = search_text.rfind('#[allow(')
            if attr_start == -1:
                return False
            
            # Find the closing parenthesis
            attr_close = search_text.find(')', attr_start)
            if attr_close == -1:
                return True
            
            # Calculate absolute positions
            abs_attr_start = search_start + attr_start + 8  # After "#[allow("
            abs_attr_close = search_start + attr_close
            
            return abs_attr_start <= current_pos <= abs_attr_close
        
        elif attr_type == 'cfg':
            # Find the last #[cfg( before cursor
            attr_start = search_text.rfind('#[cfg(')
            if attr_start == -1:
                return False
            
            # Find the closing parenthesis
            attr_close = search_text.find(')', attr_start)
            if attr_close == -1:
                return True
            
            # Calculate absolute positions
            abs_attr_start = search_start + attr_start + 6  # After "#[cfg("
            abs_attr_close = search_start + attr_close
            
            return abs_attr_start <= current_pos <= abs_attr_close
        
        elif attr_type == 'test':
            # Find the last #[test before cursor
            attr_start = search_text.rfind('#[test')
            if attr_start == -1:
                return False
            
            # Find the closing bracket
            attr_close = search_text.find(']', attr_start)
            if attr_close == -1:
                return True
            
            # Calculate absolute positions
            abs_attr_start = search_start + attr_start + 6  # After "#[test"
            abs_attr_close = search_start + attr_close
            
            return abs_attr_start <= current_pos <= abs_attr_close
        
        return False
    
    def _replace_word(self, start_pos, length, new_word):
        """Replace a word at the given position."""
        cursor = QTextCursor(self.editor.document())
        cursor.setPosition(start_pos)
        cursor.movePosition(QTextCursor.Right, QTextCursor.KeepAnchor, length)
        
        # Block signals to avoid triggering corrections again
        self.editor.blockSignals(True)
        cursor.insertText(new_word)
        self.editor.blockSignals(False)
        
        # Update cursor position
        self.editor.setTextCursor(cursor)
    
    def _insert_at_cursor(self, text):
        """Insert text at current cursor position."""
        cursor = self.editor.textCursor()
        self.editor.blockSignals(True)
        cursor.insertText(text)
        self.editor.blockSignals(False)
        self.editor.setTextCursor(cursor)
    
    def enable(self):
        """Enable auto-correction."""
        self.enabled = True
    
    def disable(self):
        """Disable auto-correction."""
        self.enabled = False
    
    def toggle(self):
        """Toggle auto-correction on/off."""
        self.enabled = not self.enabled
        return self.enabled
    
    def clear_correction_history(self):
        """Clear the history of rejected typos (for testing)."""
        self.rejected_typos_at_position = {}
        self.last_corrected_word = None
    
    def _handle_ctrl_hover(self, event):
        """Handle mouse hover when Ctrl is pressed - highlight only the word under cursor."""
        cursor = self.editor.cursorForPosition(event.pos())
        cursor.select(QTextCursor.WordUnderCursor)
        word = cursor.selectedText()
        
        # Check if this is an identifier (function or struct name)
        if word and word.strip() and (word[0].isalpha() or word[0] == '_'):
            # Only update if we're hovering over a different word
            if self.hover_cursor_position is None or \
               self.hover_cursor_position.position() != cursor.position():
                self.hover_cursor_position = cursor
                self._apply_hover_highlight()
        else:
            self._clear_hover_highlight()
    
    def _apply_hover_highlight(self):
        """Apply hover highlight using ExtraSelections (doesn't modify document)."""
        if not self.hover_cursor_position:
            return
        
        from PySide6.QtWidgets import QTextEdit
        
        # Create extra selection for hover effect
        extra_selections = []
        selection = QTextEdit.ExtraSelection()
        
        # Set the format (underline only, keep original text color)
        selection.format.setFontUnderline(True)
        selection.cursor = self.hover_cursor_position
        
        extra_selections.append(selection)
        self.editor.setExtraSelections(extra_selections)
    
    def _clear_hover_highlight(self):
        """Clear the hover highlight."""
        self.hover_cursor_position = None
        self.editor.setExtraSelections([])
    
    def _go_to_definition(self, event):
        """Go to the definition of the identifier under the cursor (Ctrl+Click)."""
        cursor = self.editor.cursorForPosition(event.pos())
        cursor.select(QTextCursor.WordUnderCursor)
        word = cursor.selectedText()
        
        if not word or not (word[0].isalpha() or word[0] == '_'):
            return
        
        # Get the full text of the document
        full_text = self.editor.toPlainText()
        
        # Search for function definition: fn word(
        fn_pattern = rf'\bfn\s+{re.escape(word)}\s*[<(]'
        fn_match = re.search(fn_pattern, full_text)
        
        if fn_match:
            self._jump_to_position(fn_match.start())
            return
        
        # Search for struct definition: struct word
        struct_pattern = rf'\bstruct\s+{re.escape(word)}\b'
        struct_match = re.search(struct_pattern, full_text)
        
        if struct_match:
            self._jump_to_position(struct_match.start())
            return
        
        # Search for enum definition: enum word
        enum_pattern = rf'\benum\s+{re.escape(word)}\b'
        enum_match = re.search(enum_pattern, full_text)
        
        if enum_match:
            self._jump_to_position(enum_match.start())
            return
        
        # Search for trait definition: trait word
        trait_pattern = rf'\btrait\s+{re.escape(word)}\b'
        trait_match = re.search(trait_pattern, full_text)
        
        if trait_match:
            self._jump_to_position(trait_match.start())
            return
        
        # Search for type alias: type word
        type_pattern = rf'\btype\s+{re.escape(word)}\b'
        type_match = re.search(type_pattern, full_text)
        
        if type_match:
            self._jump_to_position(type_match.start())
            return
        
        # Search for const definition: const word
        const_pattern = rf'\bconst\s+{re.escape(word)}\b'
        const_match = re.search(const_pattern, full_text)
        
        if const_match:
            self._jump_to_position(const_match.start())
            return
        
        # Search for static definition: static word
        static_pattern = rf'\bstatic\s+{re.escape(word)}\b'
        static_match = re.search(static_pattern, full_text)
        
        if static_match:
            self._jump_to_position(static_match.start())
            return
        
        # Search for impl block: impl word or impl<T> word
        impl_pattern = rf'\bimpl\b[^{{]*\b{re.escape(word)}\b'
        impl_match = re.search(impl_pattern, full_text)
        
        if impl_match:
            self._jump_to_position(impl_match.start())
            return
    
    def _jump_to_position(self, position):
        """Jump to a specific position in the document."""
        cursor = QTextCursor(self.editor.document())
        cursor.setPosition(position)
        
        # Move to the beginning of the line
        cursor.movePosition(QTextCursor.StartOfLine)
        
        # Set the cursor and ensure it's visible
        self.editor.setTextCursor(cursor)
        self.editor.ensureCursorVisible()
        
        # Highlight the line briefly with subtle white background
        self._highlight_current_line()
    
    def _highlight_current_line(self):
        """Briefly highlight the current line with subtle white background."""
        cursor = self.editor.textCursor()
        cursor.select(QTextCursor.LineUnderCursor)
        
        # Create a selection with subtle white highlight (30% opacity)
        from PySide6.QtWidgets import QTextEdit
        extra_selections = []
        selection = QTextEdit.ExtraSelection()
        
        # Subtle white background with 30% opacity (rgba: 255, 255, 255, 77)
        highlight_color = QColor(255, 255, 255, 30)
        selection.format.setBackground(highlight_color)
        selection.format.setProperty(QTextCharFormat.FullWidthSelection, True)
        selection.cursor = cursor
        extra_selections.append(selection)
        
        self.editor.setExtraSelections(extra_selections)
        
        # Clear the highlight after a short delay
        from PySide6.QtCore import QTimer
        QTimer.singleShot(800, self._clear_hover_highlight)
    
    def _try_trigger_snippet(self):
        cursor = self.editor.textCursor()
        word_start, word = self._get_word_before_cursor(cursor)
        if not word:
            return False
        
        # Check if word starts with # for attributes
        if word.startswith('#'):
            # Remove the # to get the actual word
            actual_word = word[1:]
            if actual_word == 'derive':
                self._expand_derive_snippet(word_start, len(word))
                return True
        
        if word == 'fn':
            self._expand_fn_snippet(word_start, len(word))
            return True
        elif word == 'async':
            self._expand_async_snippet(word_start, len(word))
            return True
        elif word == 'struct':
            self._expand_struct_snippet(word_start, len(word))
            return True
        elif word == 'impl':
            self._expand_impl_snippet(word_start, len(word))
            return True
        elif word == 'enum':
            self._expand_enum_snippet(word_start, len(word))
            return True
        return False
    
    def _expand_fn_snippet(self, start_pos, length):
        cursor = QTextCursor(self.editor.document())
        cursor.setPosition(start_pos)
        cursor.movePosition(QTextCursor.Right, QTextCursor.KeepAnchor, length)
        cursor.removeSelectedText()
        template = "fn name() {\n    \n}"
        cursor.insertText(template)
        name_start = start_pos + 3
        name_end = name_start + 4
        self.snippet_positions = {0: (name_start, name_end), 1: (name_end + 1, name_end + 1), 2: (start_pos + len("fn name() {\n    "), start_pos + len("fn name() {\n    "))}
        self.snippet_active = True
        self.snippet_stage = 0
        self.snippet_trigger = 'fn'
        cursor.setPosition(name_start)
        cursor.setPosition(name_end, QTextCursor.KeepAnchor)
        self.editor.setTextCursor(cursor)
        self._highlight_snippet_stage()
    
    def _expand_async_snippet(self, start_pos, length):
        """Expand 'async' into an async function template with tab stops."""
        cursor = QTextCursor(self.editor.document())
        cursor.setPosition(start_pos)
        cursor.movePosition(QTextCursor.Right, QTextCursor.KeepAnchor, length)
        cursor.removeSelectedText()
        template = "async fn name() {\n    \n}"
        cursor.insertText(template)
        # Position after "async fn " (9 characters)
        name_start = start_pos + 9
        name_end = name_start + 4  # "name"
        self.snippet_positions = {0: (name_start, name_end), 1: (name_end + 1, name_end + 1), 2: (start_pos + len("async fn name() {\n    "), start_pos + len("async fn name() {\n    "))}
        self.snippet_active = True
        self.snippet_stage = 0
        self.snippet_trigger = 'async'
        cursor.setPosition(name_start)
        cursor.setPosition(name_end, QTextCursor.KeepAnchor)
        self.editor.setTextCursor(cursor)
        self._highlight_snippet_stage()
