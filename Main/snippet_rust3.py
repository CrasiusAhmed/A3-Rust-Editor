"""
Additional Rust Snippet Expansion Methods - Part 3
This module contains loop, match, and trait snippets for the RustSnippetManager class.
These methods are imported and added to the main snippet manager to keep the codebase modular.
"""

from PySide6.QtGui import QTextCursor


def _expand_for_snippet(self, start_pos, length):
    """
    Expand 'for' into a for loop with 3 phases.
    
    Phase 0: for item in collection { }
    - Cursor at 'item' (highlighted)
    - Tab → Phase 1 (move to collection)
    - Escape → Delete entire snippet
    
    Phase 1: for item in collection { }
    - Cursor at 'collection' (highlighted)
    - Tab → Phase 2 (move to body)
    - Escape → Finish
    
    Phase 2: for item in collection { [body] }
    - Cursor inside body
    - Tab → Finish
    - Escape → Finish
    """
    cursor = QTextCursor(self.editor.document())
    cursor.setPosition(start_pos)
    cursor.movePosition(QTextCursor.Right, QTextCursor.KeepAnchor, length)
    cursor.removeSelectedText()
    
    # Get the current indentation level
    current_text = self.editor.toPlainText()
    line_start = start_pos
    while line_start > 0 and current_text[line_start - 1] not in '\n':
        line_start -= 1
    indent = ''
    pos = line_start
    while pos < start_pos and current_text[pos] in ' \t':
        indent += current_text[pos]
        pos += 1
    
    # Create template with proper indentation
    template = f"for item in collection {{\n{indent}    \n{indent}}}"
    cursor.insertText(template)
    
    # Store only the start position - we'll calculate everything else dynamically
    self.snippet_positions = {
        'start': start_pos  # Store where "for" starts
    }
    self.snippet_active = True
    self.snippet_stage = 0
    self.snippet_trigger = 'for'
    
    # Get current text to find actual positions
    current_text = self.editor.toPlainText()
    
    # Find "for " starting from start_pos
    search_start = max(0, start_pos - 10)
    search_text = current_text[search_start:]
    
    for_pos = search_text.find('for ')
    if for_pos != -1:
        actual_start = search_start + for_pos
        item_start = actual_start + 4  # After "for "
        
        # Find " in " to get item end
        in_pos = search_text.find(' in ', for_pos)
        if in_pos != -1:
            item_end = search_start + in_pos
            
            # Select the item
            cursor.setPosition(item_start)
            cursor.setPosition(item_end, QTextCursor.KeepAnchor)
            self.editor.setTextCursor(cursor)
            self._highlight_snippet_stage()


def _next_stage_for(self):
    """Handle Tab progression for 'for' snippet."""
    cursor = self.editor.textCursor()
    current_text = self.editor.toPlainText()
    start_pos = self.snippet_positions.get('start', 0)
    
    if self.snippet_stage >= 3:
        self.finish()
        return
    
    # Stage 1: Move to collection
    if self.snippet_stage == 1:
        search_start = max(0, start_pos - 10)
        search_text = current_text[search_start:]
        
        # Find " in " and then get collection
        for_pos = search_text.find('for ')
        if for_pos != -1:
            in_pos = search_text.find(' in ', for_pos)
            if in_pos != -1:
                collection_start = search_start + in_pos + 4  # After " in "
                
                # Find the opening brace to get collection end
                brace_pos = search_text.find('{', in_pos)
                if brace_pos != -1:
                    collection_end = search_start + brace_pos
                    # Trim whitespace before {
                    while collection_end > collection_start and current_text[collection_end - 1] in ' \t':
                        collection_end -= 1
                    
                    cursor.setPosition(collection_start)
                    cursor.setPosition(collection_end, QTextCursor.KeepAnchor)
                    self.editor.setTextCursor(cursor)
                    self._highlight_snippet_stage()
        return
    
    # Stage 2: Move to body
    elif self.snippet_stage == 2:
        search_start = max(0, start_pos - 10)
        search_text = current_text[search_start:]
        
        for_pos = search_text.find('for ')
        if for_pos != -1:
            brace_pos = search_text.find('{', for_pos)
            if brace_pos != -1:
                body_start = search_start + brace_pos + 1
                # Skip newline and indentation
                if body_start < len(current_text) and current_text[body_start] == '\n':
                    body_start += 1
                while body_start < len(current_text) and current_text[body_start] in ' \t':
                    body_start += 1
                
                cursor.setPosition(body_start)
                self.editor.setTextCursor(cursor)
                self._highlight_snippet_stage()
        return


def _cancel_for(self):
    """
    Handle Escape key for 'for' snippet.
    - Stage 0: Delete entire snippet
    - Stage 1+: Finish (keep the for loop)
    """
    cursor = self.editor.textCursor()
    current_text = self.editor.toPlainText()
    
    if self.snippet_stage == 0:
        # Stage 0: Delete entire snippet
        start = self.snippet_positions.get('start')
        if start is not None:
            # Find the end of the snippet
            search_start = max(0, start - 10)
            search_text = current_text[search_start:]
            for_pos = search_text.find('for ')
            if for_pos != -1:
                brace_pos = search_text.find('{', for_pos)
                if brace_pos != -1:
                    brace_start = search_start + brace_pos
                    brace_end = self._find_matching_brace(current_text, brace_start)
                    if brace_end != -1:
                        cursor.setPosition(start)
                        cursor.setPosition(brace_end + 1, QTextCursor.KeepAnchor)
                        cursor.removeSelectedText()
                        self.editor.setTextCursor(cursor)
        self.finish()
        return
    else:
        # Stage 1+: Just finish, keep the for loop
        self.finish()
        return


def _expand_while_snippet(self, start_pos, length):
    """
    Expand 'while' into a while loop with 2 phases.
    
    Phase 0: while condition { }
    - Cursor at 'condition' (highlighted)
    - Tab → Phase 1 (move to body)
    - Escape → Delete entire snippet
    
    Phase 1: while condition { [body] }
    - Cursor inside body
    - Tab → Finish
    - Escape → Finish
    """
    cursor = QTextCursor(self.editor.document())
    cursor.setPosition(start_pos)
    cursor.movePosition(QTextCursor.Right, QTextCursor.KeepAnchor, length)
    cursor.removeSelectedText()
    
    # Get the current indentation level
    current_text = self.editor.toPlainText()
    line_start = start_pos
    while line_start > 0 and current_text[line_start - 1] not in '\n':
        line_start -= 1
    indent = ''
    pos = line_start
    while pos < start_pos and current_text[pos] in ' \t':
        indent += current_text[pos]
        pos += 1
    
    # Create template with proper indentation
    template = f"while condition {{\n{indent}    \n{indent}}}"
    cursor.insertText(template)
    
    # Store only the start position
    self.snippet_positions = {
        'start': start_pos
    }
    self.snippet_active = True
    self.snippet_stage = 0
    self.snippet_trigger = 'while'
    
    # Get current text to find actual positions
    current_text = self.editor.toPlainText()
    
    # Find "while " starting from start_pos
    search_start = max(0, start_pos - 10)
    search_text = current_text[search_start:]
    
    while_pos = search_text.find('while ')
    if while_pos != -1:
        actual_start = search_start + while_pos
        condition_start = actual_start + 6  # After "while "
        
        # Find " {" to get condition end
        brace_pos = search_text.find('{', while_pos)
        if brace_pos != -1:
            condition_end = search_start + brace_pos
            # Trim whitespace before {
            while condition_end > condition_start and current_text[condition_end - 1] in ' \t':
                condition_end -= 1
            
            cursor.setPosition(condition_start)
            cursor.setPosition(condition_end, QTextCursor.KeepAnchor)
            self.editor.setTextCursor(cursor)
            self._highlight_snippet_stage()


def _next_stage_while(self):
    """Handle Tab progression for 'while' snippet."""
    cursor = self.editor.textCursor()
    current_text = self.editor.toPlainText()
    start_pos = self.snippet_positions.get('start', 0)
    
    if self.snippet_stage >= 2:
        self.finish()
        return
    
    # Stage 1: Move to body
    if self.snippet_stage == 1:
        search_start = max(0, start_pos - 10)
        search_text = current_text[search_start:]
        
        while_pos = search_text.find('while ')
        if while_pos != -1:
            brace_pos = search_text.find('{', while_pos)
            if brace_pos != -1:
                body_start = search_start + brace_pos + 1
                # Skip newline and indentation
                if body_start < len(current_text) and current_text[body_start] == '\n':
                    body_start += 1
                while body_start < len(current_text) and current_text[body_start] in ' \t':
                    body_start += 1
                
                cursor.setPosition(body_start)
                self.editor.setTextCursor(cursor)
                self._highlight_snippet_stage()
        return


def _cancel_while(self):
    """
    Handle Escape key for 'while' snippet.
    - Stage 0: Delete entire snippet
    - Stage 1+: Finish (keep the while loop)
    """
    cursor = self.editor.textCursor()
    current_text = self.editor.toPlainText()
    
    if self.snippet_stage == 0:
        # Stage 0: Delete entire snippet
        start = self.snippet_positions.get('start')
        if start is not None:
            search_start = max(0, start - 10)
            search_text = current_text[search_start:]
            while_pos = search_text.find('while ')
            if while_pos != -1:
                brace_pos = search_text.find('{', while_pos)
                if brace_pos != -1:
                    brace_start = search_start + brace_pos
                    brace_end = self._find_matching_brace(current_text, brace_start)
                    if brace_end != -1:
                        cursor.setPosition(start)
                        cursor.setPosition(brace_end + 1, QTextCursor.KeepAnchor)
                        cursor.removeSelectedText()
                        self.editor.setTextCursor(cursor)
        self.finish()
        return
    else:
        # Stage 1+: Just finish
        self.finish()
        return


def _expand_loop_snippet(self, start_pos, length):
    """
    Expand 'loop' into an infinite loop with 1 phase.
    
    Phase 0: loop { [body] }
    - Cursor inside body
    - Tab → Finish
    - Escape → Delete entire snippet
    """
    cursor = QTextCursor(self.editor.document())
    cursor.setPosition(start_pos)
    cursor.movePosition(QTextCursor.Right, QTextCursor.KeepAnchor, length)
    cursor.removeSelectedText()
    
    # Get the current indentation level
    current_text = self.editor.toPlainText()
    line_start = start_pos
    while line_start > 0 and current_text[line_start - 1] not in '\n':
        line_start -= 1
    indent = ''
    pos = line_start
    while pos < start_pos and current_text[pos] in ' \t':
        indent += current_text[pos]
        pos += 1
    
    # Create template with proper indentation
    template = f"loop {{\n{indent}    \n{indent}}}"
    cursor.insertText(template)
    
    # Store only the start position
    self.snippet_positions = {
        'start': start_pos
    }
    self.snippet_active = True
    self.snippet_stage = 0
    self.snippet_trigger = 'loop'
    
    # Get current text to find actual positions
    current_text = self.editor.toPlainText()
    
    # Find "loop {" starting from start_pos
    search_start = max(0, start_pos - 10)
    search_text = current_text[search_start:]
    
    loop_pos = search_text.find('loop ')
    if loop_pos != -1:
        brace_pos = search_text.find('{', loop_pos)
        if brace_pos != -1:
            body_start = search_start + brace_pos + 1
            # Skip newline and indentation
            if body_start < len(current_text) and current_text[body_start] == '\n':
                body_start += 1
            while body_start < len(current_text) and current_text[body_start] in ' \t':
                body_start += 1
            
            cursor.setPosition(body_start)
            self.editor.setTextCursor(cursor)
            self._highlight_snippet_stage()


def _next_stage_loop(self):
    """Handle Tab progression for 'loop' snippet."""
    # Loop only has 1 stage (body), so Tab finishes it
    if self.snippet_stage >= 1:
        self.finish()
        return


def _cancel_loop(self):
    """
    Handle Escape key for 'loop' snippet.
    - Stage 0: Delete entire snippet
    """
    cursor = self.editor.textCursor()
    current_text = self.editor.toPlainText()
    
    if self.snippet_stage == 0:
        # Stage 0: Delete entire snippet
        start = self.snippet_positions.get('start')
        if start is not None:
            search_start = max(0, start - 10)
            search_text = current_text[search_start:]
            loop_pos = search_text.find('loop ')
            if loop_pos != -1:
                brace_pos = search_text.find('{', loop_pos)
                if brace_pos != -1:
                    brace_start = search_start + brace_pos
                    brace_end = self._find_matching_brace(current_text, brace_start)
                    if brace_end != -1:
                        cursor.setPosition(start)
                        cursor.setPosition(brace_end + 1, QTextCursor.KeepAnchor)
                        cursor.removeSelectedText()
                        self.editor.setTextCursor(cursor)
        self.finish()
        return
    else:
        # Stage 1+: Just finish
        self.finish()
        return


def _expand_match_snippet(self, start_pos, length):
    """
    Expand 'match' into a match expression with multiple phases.
    
    Phase 0: match value { }
    - Cursor at 'value' (highlighted)
    - Tab → Phase 1 (add first arm)
    - Escape → Delete entire snippet
    
    Phase 1+: match value { pattern => result, }
    - Cursor at 'pattern' (highlighted)
    - Tab → Move to result
    - Escape → Remove last arm and finish
    
    Loops: Keep adding arms with Tab
    """
    cursor = QTextCursor(self.editor.document())
    cursor.setPosition(start_pos)
    cursor.movePosition(QTextCursor.Right, QTextCursor.KeepAnchor, length)
    cursor.removeSelectedText()
    
    # Get the current indentation level
    current_text = self.editor.toPlainText()
    line_start = start_pos
    while line_start > 0 and current_text[line_start - 1] not in '\n':
        line_start -= 1
    indent = ''
    pos = line_start
    while pos < start_pos and current_text[pos] in ' \t':
        indent += current_text[pos]
        pos += 1
    
    # Create template with proper indentation
    template = f"match value {{\n{indent}    \n{indent}}}"
    cursor.insertText(template)
    
    # Store only the start position
    self.snippet_positions = {
        'start': start_pos
    }
    self.snippet_active = True
    self.snippet_stage = 0
    self.snippet_trigger = 'match'
    self.match_arm_count = 0  # Track number of arms added
    
    # Get current text to find actual positions
    current_text = self.editor.toPlainText()
    
    # Find "match " starting from start_pos
    search_start = max(0, start_pos - 10)
    search_text = current_text[search_start:]
    
    match_pos = search_text.find('match ')
    if match_pos != -1:
        actual_start = search_start + match_pos
        value_start = actual_start + 6  # After "match "
        
        # Find " {" to get value end
        brace_pos = search_text.find('{', match_pos)
        if brace_pos != -1:
            value_end = search_start + brace_pos
            # Trim whitespace before {
            while value_end > value_start and current_text[value_end - 1] in ' \t':
                value_end -= 1
            
            cursor.setPosition(value_start)
            cursor.setPosition(value_end, QTextCursor.KeepAnchor)
            self.editor.setTextCursor(cursor)
            self._highlight_snippet_stage()


def _next_stage_match(self):
    """Handle Tab progression for 'match' snippet."""
    cursor = self.editor.textCursor()
    current_text = self.editor.toPlainText()
    start_pos = self.snippet_positions.get('start', 0)
    
    if self.snippet_stage >= 100:  # Arbitrary high limit
        self.finish()
        return
    
    # Stage 1: User finished typing value, add first arm and select pattern
    if self.snippet_stage == 1:
        # Find the match block
        search_start = max(0, start_pos - 10)
        search_text = current_text[search_start:]
        
        match_pos = search_text.find('match ')
        if match_pos != -1:
            brace_pos = search_text.find('{', match_pos)
            if brace_pos != -1:
                # Find position after opening brace
                insert_pos = search_start + brace_pos + 1
                
                # Skip newline and indentation
                if insert_pos < len(current_text) and current_text[insert_pos] == '\n':
                    insert_pos += 1
                while insert_pos < len(current_text) and current_text[insert_pos] in ' \t':
                    insert_pos += 1
                
                # Insert first arm
                cursor.setPosition(insert_pos)
                cursor.insertText("pattern => result,\n    ")
                
                # Update text after insertion
                current_text = self.editor.toPlainText()
                
                # Select 'pattern'
                pattern_start = insert_pos
                pattern_end = pattern_start + 7  # "pattern"
                cursor.setPosition(pattern_start)
                cursor.setPosition(pattern_end, QTextCursor.KeepAnchor)
                self.editor.setTextCursor(cursor)
                self._highlight_snippet_stage()
                
                self.match_arm_count = 1
        return
    
    # Even stages (2, 4, 6...): Move from pattern to result
    elif self.snippet_stage >= 2 and self.snippet_stage % 2 == 0:
        # Find the current arm's "=>" and select "result"
        cursor_pos = cursor.position()
        
        # Search backward to find the start of current line/arm
        line_start = cursor_pos
        while line_start > 0 and current_text[line_start - 1] not in '\n':
            line_start -= 1
        
        # Search forward from line start for "=>" on this line
        line_end = cursor_pos
        while line_end < len(current_text) and current_text[line_end] not in '\n':
            line_end += 1
        
        line_text = current_text[line_start:line_end]
        arrow_pos_in_line = line_text.find('=>')
        
        if arrow_pos_in_line != -1:
            arrow_pos = line_start + arrow_pos_in_line
            result_start = arrow_pos + 2  # After "=>"
            # Skip whitespace after =>
            while result_start < len(current_text) and current_text[result_start] in ' \t':
                result_start += 1
            
            # Find comma on this line
            comma_pos = current_text.find(',', result_start)
            if comma_pos != -1 and comma_pos <= line_end:
                result_end = comma_pos
                # Trim whitespace
                while result_end > result_start and current_text[result_end - 1] in ' \t':
                    result_end -= 1
                
                cursor.setPosition(result_start)
                cursor.setPosition(result_end, QTextCursor.KeepAnchor)
                self.editor.setTextCursor(cursor)
                self._highlight_snippet_stage()
        return
    
    # Odd stages (3, 5, 7...): Add new arm
    elif self.snippet_stage >= 3 and self.snippet_stage % 2 == 1:
        # Find the last comma in the match block
        search_start = max(0, start_pos - 10)
        search_text = current_text[search_start:]
        
        match_pos = search_text.find('match ')
        if match_pos != -1:
            brace_pos = search_text.find('{', match_pos)
            if brace_pos != -1:
                # Find the closing brace
                brace_start = search_start + brace_pos
                brace_end = self._find_matching_brace(current_text, brace_start)
                
                if brace_end != -1:
                    # Find last comma before closing brace
                    match_content = current_text[brace_start:brace_end]
                    last_comma = match_content.rfind(',')
                    
                    if last_comma != -1:
                        insert_pos = brace_start + last_comma + 1
                        
                        # Get the indentation of the first arm to match it
                        # Find the first arm's indentation
                        first_newline = match_content.find('\n')
                        if first_newline != -1:
                            # Get indentation after first newline
                            indent_start = first_newline + 1
                            indent = ''
                            while indent_start < len(match_content) and match_content[indent_start] in ' \t':
                                indent += match_content[indent_start]
                                indent_start += 1
                        else:
                            indent = '    '  # Default to 4 spaces
                        
                        # Insert new arm
                        cursor.setPosition(insert_pos)
                        self.match_arm_count += 1
                        cursor.insertText(f"\n{indent}pattern{self.match_arm_count} => result{self.match_arm_count},")
                        
                        # Update text after insertion
                        current_text = self.editor.toPlainText()
                        
                        # Select the new pattern
                        pattern_start = insert_pos + 1 + len(indent)  # After "\n" + indent
                        pattern_end = pattern_start + 7 + len(str(self.match_arm_count))  # "patternN"
                        cursor.setPosition(pattern_start)
                        cursor.setPosition(pattern_end, QTextCursor.KeepAnchor)
                        self.editor.setTextCursor(cursor)
                        self._highlight_snippet_stage()
        return


def _cancel_match(self):
    """
    Handle Escape key for 'match' snippet.
    - Stage 0: Delete entire snippet
    - Stage 1+: Remove last arm and finish
    """
    cursor = self.editor.textCursor()
    current_text = self.editor.toPlainText()
    
    if self.snippet_stage == 0:
        # Stage 0: Delete entire snippet
        start = self.snippet_positions.get('start')
        if start is not None:
            search_start = max(0, start - 10)
            search_text = current_text[search_start:]
            match_pos = search_text.find('match ')
            if match_pos != -1:
                brace_pos = search_text.find('{', match_pos)
                if brace_pos != -1:
                    brace_start = search_start + brace_pos
                    brace_end = self._find_matching_brace(current_text, brace_start)
                    if brace_end != -1:
                        cursor.setPosition(start)
                        cursor.setPosition(brace_end + 1, QTextCursor.KeepAnchor)
                        cursor.removeSelectedText()
                        self.editor.setTextCursor(cursor)
        self.finish()
        return
    else:
        # Stage 1+: Remove the last arm and finish
        start = self.snippet_positions.get('start')
        if start is not None and hasattr(self, 'match_arm_count') and self.match_arm_count > 0:
            search_start = max(0, start - 10)
            search_text = current_text[search_start:]
            
            match_pos = search_text.find('match ')
            if match_pos != -1:
                brace_pos = search_text.find('{', match_pos)
                if brace_pos != -1:
                    brace_start = search_start + brace_pos
                    brace_end = self._find_matching_brace(current_text, brace_start)
                    
                    if brace_end != -1:
                        # Find the last arm (last occurrence of "=>")
                        match_content = current_text[brace_start:brace_end]
                        last_arrow = match_content.rfind('=>')
                        
                        if last_arrow != -1:
                            # Find the start of this arm (previous newline or opening brace)
                            arm_content_before = match_content[:last_arrow]
                            last_newline = arm_content_before.rfind('\n')
                            
                            if last_newline != -1:
                                arm_start = brace_start + last_newline
                            else:
                                arm_start = brace_start + 1
                            
                            # Find the comma after this arm
                            arm_content_after = match_content[last_arrow:]
                            comma_pos = arm_content_after.find(',')
                            
                            if comma_pos != -1:
                                arm_end = brace_start + last_arrow + comma_pos + 1
                                
                                # Also delete the trailing newline and indentation if present
                                if arm_end < len(current_text):
                                    # Check if there's a newline after the comma
                                    if current_text[arm_end] == '\n':
                                        arm_end += 1
                                        # Skip indentation after newline
                                        while arm_end < len(current_text) and current_text[arm_end] in ' \t':
                                            arm_end += 1
                                
                                # Delete the arm
                                cursor.setPosition(arm_start)
                                cursor.setPosition(arm_end, QTextCursor.KeepAnchor)
                                cursor.removeSelectedText()
                                self.editor.setTextCursor(cursor)
        
        self.finish()
        return


def _expand_trait_snippet(self, start_pos, length):
    """
    Expand 'trait' into a trait definition template.
    
    Phase 0: trait Name { }
    - Cursor at 'Name' (highlighted)
    - Tab → Phase 1 (move to body)
    - Escape → Delete entire snippet
    
    Phase 1: trait Name { [body] }
    - Cursor inside body
    - Tab → Finish
    - Escape → Finish
    """
    cursor = QTextCursor(self.editor.document())
    cursor.setPosition(start_pos)
    cursor.movePosition(QTextCursor.Right, QTextCursor.KeepAnchor, length)
    cursor.removeSelectedText()
    
    # Get the current indentation level
    current_text = self.editor.toPlainText()
    line_start = start_pos
    while line_start > 0 and current_text[line_start - 1] not in '\n':
        line_start -= 1
    indent = ''
    pos = line_start
    while pos < start_pos and current_text[pos] in ' \t':
        indent += current_text[pos]
        pos += 1
    
    # Create template with proper indentation
    template = f"trait Name {{\n{indent}    \n{indent}}}"
    cursor.insertText(template)
    
    # Store the start position for later reference
    self.snippet_positions = {
        'start': start_pos
    }
    self.snippet_active = True
    self.snippet_stage = 0
    self.snippet_trigger = 'trait'
    
    # Get current text to find actual positions
    current_text = self.editor.toPlainText()
    
    # Find "trait " starting from start_pos
    search_start = max(0, start_pos - 10)
    search_text = current_text[search_start:]
    
    trait_pos = search_text.find('trait ')
    if trait_pos != -1:
        actual_start = search_start + trait_pos
        name_start = actual_start + 6  # After "trait "
        
        # Find the opening brace
        brace_pos = search_text.find('{', trait_pos)
        if brace_pos != -1:
            # Find name end (before {)
            name_end_pos = search_start + brace_pos
            # Trim whitespace before {
            while name_end_pos > name_start and current_text[name_end_pos - 1] in ' \t':
                name_end_pos -= 1
            
            # Select the name
            cursor.setPosition(name_start)
            cursor.setPosition(name_end_pos, QTextCursor.KeepAnchor)
            self.editor.setTextCursor(cursor)
            self._highlight_snippet_stage()


def _next_stage_trait(self):
    """Handle Tab progression for 'trait' snippet."""
    if self.snippet_stage >= 2:
        self.finish()
        return
    
    # Stage 1: Move to body
    if self.snippet_stage == 1:
        # Recalculate body position dynamically
        cursor = self.editor.textCursor()
        current_text = self.editor.toPlainText()
        
        # Find the trait from the start position
        start_pos = self.snippet_positions.get('start', 0)
        search_start = max(0, start_pos - 10)
        search_text = current_text[search_start:]
        
        trait_pos = search_text.find('trait ')
        if trait_pos != -1:
            brace_pos = search_text.find('{', trait_pos)
            if brace_pos != -1:
                body_start = search_start + brace_pos + 1  # After {
                # Skip newline
                if body_start < len(current_text) and current_text[body_start] == '\n':
                    body_start += 1
                # Skip indentation
                while body_start < len(current_text) and current_text[body_start] in ' \t':
                    body_start += 1
                
                cursor.setPosition(body_start)
                self.editor.setTextCursor(cursor)
                self._highlight_snippet_stage()
    return


def _cancel_trait(self):
    """
    Handle Escape key for 'trait' snippet.
    - Stage 0: Delete entire snippet
    - Stage 1: Finish (keep the trait)
    """
    cursor = self.editor.textCursor()
    current_text = self.editor.toPlainText()
    
    if self.snippet_stage == 0:
        # Stage 0: Delete entire snippet
        start = self.snippet_positions.get('start')
        if start is not None:
            search_start = max(0, start - 10)
            search_text = current_text[search_start:]
            trait_pos = search_text.find('trait ')
            if trait_pos != -1:
                brace_pos = search_text.find('{', trait_pos)
                if brace_pos != -1:
                    brace_start = search_start + brace_pos
                    brace_end = self._find_matching_brace(current_text, brace_start)
                    if brace_end != -1:
                        cursor.setPosition(start)
                        cursor.setPosition(brace_end + 1, QTextCursor.KeepAnchor)
                        cursor.removeSelectedText()
                        self.editor.setTextCursor(cursor)
        self.finish()
    else:
        # Stage 1: Just finish, keep the trait
        self.finish()


def _expand_type_snippet(self, start_pos, length):
    """
    Expand 'type' into a type alias definition with 2 phases.
    
    Phase 0: type Name = ;
    - Cursor at 'Name' (highlighted)
    - Tab → Phase 1 (move to type after =)
    - Escape → Delete entire snippet
    
    Phase 1: type Name = ;
    - Cursor after = (for type definition)
    - Tab → Finish
    - Escape → Finish
    """
    cursor = QTextCursor(self.editor.document())
    cursor.setPosition(start_pos)
    cursor.movePosition(QTextCursor.Right, QTextCursor.KeepAnchor, length)
    cursor.removeSelectedText()
    
    # Create template
    template = "type Name = ;"
    cursor.insertText(template)
    
    # Store only the start position - we'll calculate everything else dynamically
    self.snippet_positions = {
        'start': start_pos  # Store where "type" starts
    }
    self.snippet_active = True
    self.snippet_stage = 0
    self.snippet_trigger = 'type'
    
    # Get current text to find actual positions
    current_text = self.editor.toPlainText()
    
    # Find "type " starting from start_pos
    search_start = max(0, start_pos - 10)
    search_text = current_text[search_start:]
    
    type_pos = search_text.find('type ')
    if type_pos != -1:
        actual_start = search_start + type_pos
        name_start = actual_start + 5  # After "type "
        
        # Find the = sign
        equals_pos = search_text.find('=', type_pos)
        if equals_pos != -1:
            # Find name end (before =)
            name_end_pos = search_start + equals_pos
            # Trim whitespace before =
            while name_end_pos > name_start and current_text[name_end_pos - 1] in ' \t':
                name_end_pos -= 1
            
            # Select the name
            cursor.setPosition(name_start)
            cursor.setPosition(name_end_pos, QTextCursor.KeepAnchor)
            self.editor.setTextCursor(cursor)
            self._highlight_snippet_stage()


def _next_stage_type(self):
    """Handle Tab progression for 'type' snippet."""
    cursor = self.editor.textCursor()
    current_text = self.editor.toPlainText()
    start_pos = self.snippet_positions.get('start', 0)
    
    if self.snippet_stage >= 2:
        self.finish()
        return
    
    # Stage 1: Move to type definition (after =)
    if self.snippet_stage == 1:
        search_start = max(0, start_pos - 10)
        search_text = current_text[search_start:]
        
        type_pos = search_text.find('type ')
        if type_pos != -1:
            equals_pos = search_text.find('=', type_pos)
            if equals_pos != -1:
                # Position after "= "
                value_pos = search_start + equals_pos + 1
                # Skip whitespace after =
                while value_pos < len(current_text) and current_text[value_pos] in ' \t':
                    value_pos += 1
                
                cursor.setPosition(value_pos)
                self.editor.setTextCursor(cursor)
                self._highlight_snippet_stage()
        return


def _cancel_type(self):
    """
    Handle Escape key for 'type' snippet.
    - Stage 0: Delete entire snippet
    - Stage 1+: Finish (keep the type alias)
    """
    cursor = self.editor.textCursor()
    current_text = self.editor.toPlainText()
    
    if self.snippet_stage == 0:
        # Stage 0: Delete entire snippet
        start = self.snippet_positions.get('start')
        if start is not None:
            search_start = max(0, start - 10)
            search_text = current_text[search_start:]
            type_pos = search_text.find('type ')
            if type_pos != -1:
                # Find the semicolon
                semicolon_pos = search_text.find(';', type_pos)
                if semicolon_pos != -1:
                    cursor.setPosition(start)
                    cursor.setPosition(search_start + semicolon_pos + 1, QTextCursor.KeepAnchor)
                    cursor.removeSelectedText()
                    self.editor.setTextCursor(cursor)
        self.finish()
        return
    else:
        # Stage 1+: Just finish, keep the type alias
        self.finish()
        return
