"""
Additional Rust Snippet Expansion Methods
This module contains extra snippet expansion methods for the RustSnippetManager class.
These methods are imported and added to the main snippet manager to keep the codebase modular.
"""

from PySide6.QtGui import QTextCursor


def _expand_let_snippet(self, start_pos, length):
    """
    Expand 'let' into a variable declaration with 2 phases.
    
    Phase 0: let name = ;
    - Cursor at 'name' (highlighted)
    - Tab → Phase 1 (move to value after =)
    - Escape → Delete entire statement
    
    Phase 1: let varname = ;
    - Cursor after = (for value)
    - Tab → Finish
    - Escape → Finish
    """
    cursor = QTextCursor(self.editor.document())
    cursor.setPosition(start_pos)
    cursor.movePosition(QTextCursor.Right, QTextCursor.KeepAnchor, length)
    cursor.removeSelectedText()
    
    template = "let name = ;"
    cursor.insertText(template)
    
    # Store only the start position - we'll calculate everything else dynamically
    self.snippet_positions = {
        'start': start_pos  # Store where "let" starts
    }
    self.snippet_active = True
    self.snippet_stage = 0
    self.snippet_trigger = 'let'
    
    # Get current text to find actual positions
    current_text = self.editor.toPlainText()
    
    # Find "let " starting from start_pos
    search_start = max(0, start_pos - 10)
    search_text = current_text[search_start:]
    
    let_pos = search_text.find('let ')
    if let_pos != -1:
        actual_start = search_start + let_pos
        name_start = actual_start + 4  # After "let "
        
        # Find the = sign
        equals_pos = search_text.find('=', let_pos)
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


def _expand_if_snippet(self, start_pos, length):
    """
    Expand 'if' into an if statement with multiple phases.
    
    Phase 0: if condition { }
    - Cursor at 'condition' (highlighted)
    - Tab → Phase 1 (move to body)
    - Escape → Delete entire snippet
    
    Phase 1: if condition { [body] }
    - Cursor inside body
    - Tab → Phase 2 (add else if)
    - Escape → Finish (keep just the if)
    
    Phase 2+: if condition { body } else if conditionN { }
    - Cursor at conditionN
    - Tab → Phase N+1 (move to else-if body)
    - Escape → Skip to final else phase
    
    Phase N+1: if condition { body } else if conditionN { [body] }
    - Cursor inside else-if body
    - Tab → Phase 2 again (add another else if - loop)
    - Escape → Skip to final else phase
    
    Final Phase: if condition { body } [else if blocks] else { [body] }
    - Cursor inside else body
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
    template = f"if condition {{\n{indent}    \n{indent}}}"
    cursor.insertText(template)
    
    # Get current text to find actual positions
    current_text = self.editor.toPlainText()
    
    # Find "if " starting from start_pos
    search_start = max(0, start_pos - 10)
    search_text = current_text[search_start:]
    
    if_pos = search_text.find('if ')
    if if_pos != -1:
        actual_start = search_start + if_pos
        condition_start = actual_start + 3  # After "if "
        
        # Find the opening brace
        brace_pos = search_text.find('{', if_pos)
        if brace_pos != -1:
            # Find the matching closing brace
            close_brace_pos = search_text.find('}', brace_pos)
            if close_brace_pos != -1:
                snippet_end = search_start + close_brace_pos + 1
                
                # Store positions
                self.snippet_positions = {
                    'start': actual_start,  # Store where "if" starts
                    'end': snippet_end,  # Store where the snippet ends (after })
                    'else_if_count': 0,  # Track number of else-if blocks
                    'in_else_if_body': False  # Track if we're in else-if body
                }
                self.snippet_active = True
                self.snippet_stage = 0
                self.snippet_trigger = 'if'
                
                # Find condition end (before {)
                condition_end = search_start + brace_pos
                # Trim whitespace before {
                while condition_end > condition_start and current_text[condition_end - 1] in ' \t':
                    condition_end -= 1
                
                # Select the condition
                cursor.setPosition(condition_start)
                cursor.setPosition(condition_end, QTextCursor.KeepAnchor)
                self.editor.setTextCursor(cursor)
                self._highlight_snippet_stage()


def _expand_ifl_snippet(self, start_pos, length):
    """
    Expand 'ifl' into an if-let statement with multiple phases.
    
    Phase 0: if let pattern = value { }
    - Cursor at 'pattern' (highlighted)
    - Tab → Phase 1 (move to value)
    - Escape → Delete entire snippet
    
    Phase 1: if let pattern = value { }
    - Cursor at 'value' (highlighted)
    - Tab → Phase 2 (move to body)
    - Escape → Finish
    
    Phase 2: if let pattern = value { [body] }
    - Cursor inside body
    - Tab → Phase 3 (add else if let)
    - Escape → Finish (keep just the if let)
    
    Phase 3+: if let pattern = value { body } else if let pattern2 = value2 { }
    - Cursor at pattern2
    - Tab → Phase N+1 (move to value2)
    - Escape → Skip to final else phase
    
    Phase N+1: if let pattern = value { body } else if let pattern2 = value2 { }
    - Cursor at value2
    - Tab → Phase N+2 (move to else-if-let body)
    - Escape → Skip to final else phase
    
    Phase N+2: if let pattern = value { body } else if let pattern2 = value2 { [body] }
    - Cursor inside else-if-let body
    - Tab → Phase 3 again (add another else if let - loop)
    - Escape → Skip to final else phase
    
    Final Phase: if let pattern = value { body } [else if let blocks] else { [body] }
    - Cursor inside else body
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
    template = f"if let pattern = value {{\n{indent}    \n{indent}}}"
    cursor.insertText(template)
    
    # Get current text to find actual positions
    current_text = self.editor.toPlainText()
    
    # Find "if let " starting from start_pos
    search_start = max(0, start_pos - 10)
    search_text = current_text[search_start:]
    
    ifl_pos = search_text.find('if let ')
    if ifl_pos != -1:
        actual_start = search_start + ifl_pos
        pattern_start = actual_start + 7  # After "if let "
        
        # Find the = sign
        equals_pos = search_text.find('=', ifl_pos)
        if equals_pos != -1:
            # Find the opening brace
            brace_pos = search_text.find('{', equals_pos)
            if brace_pos != -1:
                # Find the matching closing brace
                close_brace_pos = search_text.find('}', brace_pos)
                if close_brace_pos != -1:
                    snippet_end = search_start + close_brace_pos + 1
                    
                    # Store positions
                    self.snippet_positions = {
                        'start': actual_start,  # Store where "if let" starts
                        'end': snippet_end,  # Store where the snippet ends (after })
                        'else_if_let_count': 0,  # Track number of else-if-let blocks
                        'in_else_if_let_stage': 0  # Track which part of else-if-let we're in (0=pattern, 1=value, 2=body)
                    }
                    self.snippet_active = True
                    self.snippet_stage = 0
                    self.snippet_trigger = 'ifl'
                    
                    # Find pattern end (before =)
                    pattern_end = search_start + equals_pos
                    # Trim whitespace before =
                    while pattern_end > pattern_start and current_text[pattern_end - 1] in ' \t':
                        pattern_end -= 1
                    
                    # Select the pattern
                    cursor.setPosition(pattern_start)
                    cursor.setPosition(pattern_end, QTextCursor.KeepAnchor)
                    self.editor.setTextCursor(cursor)
                    self._highlight_snippet_stage()


# Delegated next_stage handlers moved from snippet_rust.py

def _next_stage_let(self):
    """Handle Tab progression for 'let' snippet."""
    if self.snippet_stage >= 2:
        self.finish()
        return
    # Stage 1: Move to value (after =)
    if self.snippet_stage == 1:
        # Dynamically recalculate position
        cursor = self.editor.textCursor()
        current_text = self.editor.toPlainText()

        # Find the let statement from the start position
        start_pos = self.snippet_positions.get('start', 0)
        search_start = max(0, start_pos - 10)
        search_text = current_text[search_start:]

        # Find "let " and then the = sign
        let_pos = search_text.find('let ')
        if let_pos != -1:
            equals_pos = search_text.find('=', let_pos)
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


def _next_stage_if(self):
    """Handle Tab progression for 'if' snippet, including else-if loop and else stages."""
    cursor = self.editor.textCursor()
    current_text = self.editor.toPlainText()
    start_pos = self.snippet_positions.get('start', 0)
    
    # Helper function to find the current end of the snippet
    def find_snippet_end():
        # Start from the beginning and find all closing braces
        search_start = max(0, start_pos - 10)
        search_text = current_text[search_start:]
        
        # Find the initial "if "
        if_pos = search_text.find('if ')
        if if_pos == -1:
            return None
            
        # Find the first opening brace
        first_brace = search_text.find('{', if_pos)
        if first_brace == -1:
            return None
        
        # Track brace depth to find the end of the entire if-else chain
        pos = search_start + first_brace
        brace_count = 0
        in_if_chain = True
        last_close = pos
        
        i = pos
        while i < len(current_text):
            if current_text[i] == '{':
                brace_count += 1
            elif current_text[i] == '}':
                brace_count -= 1
                if brace_count == 0:
                    last_close = i
                    # Check if there's an else/else if after this
                    j = i + 1
                    while j < len(current_text) and current_text[j] in ' \t\n':
                        j += 1
                    if j < len(current_text) - 4 and current_text[j:j+4] == 'else':
                        # Continue to include the else/else if
                        i = j + 3
                    else:
                        # No more else, we're done
                        return last_close + 1
            i += 1
        
        return last_close + 1 if brace_count == 0 else None

    # Stage 1: Move to if body
    if self.snippet_stage == 1:
        search_start = max(0, start_pos - 10)
        search_text = current_text[search_start:]
        if_pos = search_text.find('if ')
        if if_pos != -1:
            brace_pos = search_text.find('{', if_pos)
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

    # Stage 2+: Handle else-if loop (even stages) and else-if body (odd stages)
    # Stage 2, 4, 6, ... : Add else if (or final else if we're done with else-ifs)
    # Stage 3, 5, 7, ... : Move to else-if body
    elif self.snippet_stage >= 2:
        in_else_if_body = self.snippet_positions.get('in_else_if_body', False)
        
        # If we're in an else-if body stage (odd stage >= 3), move to the body
        if self.snippet_stage >= 3 and self.snippet_stage % 2 == 1:
            # Move to the last else-if body
            search_start = max(0, start_pos - 10)
            search_text = current_text[search_start:]
            else_if_pos = search_text.rfind('else if ')
            if else_if_pos != -1:
                brace_pos = search_text.find('{', else_if_pos)
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
                    self.snippet_positions['in_else_if_body'] = True
            return
        
        # If we're at an even stage >= 2, add another else-if
        elif self.snippet_stage % 2 == 0:
            # Find current end of snippet
            snippet_end = find_snippet_end()
            if snippet_end is not None:
                # Increment else-if counter
                else_if_count = self.snippet_positions.get('else_if_count', 0)
                else_if_count += 1
                self.snippet_positions['else_if_count'] = else_if_count
                
                # Get the current indentation level
                line_start = snippet_end - 1
                while line_start > 0 and current_text[line_start - 1] not in '\n':
                    line_start -= 1
                indent = ''
                pos = line_start
                while pos < snippet_end and current_text[pos] in ' \t':
                    indent += current_text[pos]
                    pos += 1
                
                # Insert new else-if at the end
                insert_position = snippet_end
                cursor.setPosition(insert_position)
                condition_name = f"condition{else_if_count + 1}"
                cursor.insertText(f' else if {condition_name} {{\n{indent}    \n{indent}}}')
                
                # Update snippet end
                current_text = self.editor.toPlainText()
                snippet_end = find_snippet_end()
                if snippet_end:
                    self.snippet_positions['end'] = snippet_end
                
                # Find and select the new condition we just inserted
                # Search forward from where we inserted, not backward from the end
                search_text = current_text[insert_position:]
                else_if_pos = search_text.find('else if ')
                if else_if_pos != -1:
                    condition_start = insert_position + else_if_pos + 8  # After "else if "
                    brace_pos = search_text.find('{', else_if_pos)
                    if brace_pos != -1:
                        condition_end = insert_position + brace_pos
                        # Trim whitespace
                        while condition_end > condition_start and current_text[condition_end - 1] in ' \t':
                            condition_end -= 1

                        cursor.setPosition(condition_start)
                        cursor.setPosition(condition_end, QTextCursor.KeepAnchor)
                        self.editor.setTextCursor(cursor)
                        self._highlight_snippet_stage()
                        self.snippet_positions['in_else_if_body'] = False
            return

    # Should not reach here
    self.finish()
    return


def _next_stage_ifl(self):
    """Handle Tab progression for 'ifl' (if let) snippet, including else-if-let loop and else stages."""
    cursor = self.editor.textCursor()
    current_text = self.editor.toPlainText()
    start_pos = self.snippet_positions.get('start', 0)
    
    # Helper function to find the current end of the snippet
    def find_snippet_end():
        search_start = max(0, start_pos - 10)
        search_text = current_text[search_start:]
        
        # Find the initial "if let "
        ifl_pos = search_text.find('if let ')
        if ifl_pos == -1:
            return None
            
        # Find the first opening brace
        first_brace = search_text.find('{', ifl_pos)
        if first_brace == -1:
            return None
        
        # Track brace depth to find the end of the entire if-else chain
        pos = search_start + first_brace
        brace_count = 0
        last_close = pos
        
        i = pos
        while i < len(current_text):
            if current_text[i] == '{':
                brace_count += 1
            elif current_text[i] == '}':
                brace_count -= 1
                if brace_count == 0:
                    last_close = i
                    # Check if there's an else/else if after this
                    j = i + 1
                    while j < len(current_text) and current_text[j] in ' \t\n':
                        j += 1
                    if j < len(current_text) - 4 and current_text[j:j+4] == 'else':
                        # Continue to include the else/else if
                        i = j + 3
                    else:
                        # No more else, we're done
                        return last_close + 1
            i += 1
        
        return last_close + 1 if brace_count == 0 else None

    # Stage 1: Move to value (first if let)
    if self.snippet_stage == 1:
        search_start = max(0, start_pos - 10)
        search_text = current_text[search_start:]
        ifl_pos = search_text.find('if let ')
        if ifl_pos != -1:
            equals_pos = search_text.find('=', ifl_pos)
            if equals_pos != -1:
                value_pos = search_start + equals_pos + 1
                # Skip whitespace after =
                while value_pos < len(current_text) and current_text[value_pos] in ' \t':
                    value_pos += 1

                # Find the opening brace to get value end
                brace_pos = search_text.find('{', equals_pos)
                if brace_pos != -1:
                    value_end = search_start + brace_pos
                    # Trim whitespace before {
                    while value_end > value_pos and current_text[value_end - 1] in ' \t':
                        value_end -= 1

                    cursor.setPosition(value_pos)
                    cursor.setPosition(value_end, QTextCursor.KeepAnchor)
                    self.editor.setTextCursor(cursor)
                    self._highlight_snippet_stage()
        return

    # Stage 2: Move to body (first if let)
    elif self.snippet_stage == 2:
        search_start = max(0, start_pos - 10)
        search_text = current_text[search_start:]
        ifl_pos = search_text.find('if let ')
        if ifl_pos != -1:
            brace_pos = search_text.find('{', ifl_pos)
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

    # Stage 3+: Handle else-if-let loop
    # Stages cycle through: pattern -> value -> body -> pattern -> value -> body...
    elif self.snippet_stage >= 3:
        in_else_if_let_stage = self.snippet_positions.get('in_else_if_let_stage', 0)
        
        # Stage pattern: 3, 6, 9, 12... ((stage - 3) % 3 == 0) - Add new else if let and select pattern
        if (self.snippet_stage - 3) % 3 == 0:
            # Add new else if let
            snippet_end = find_snippet_end()
            if snippet_end is not None:
                # Increment else-if-let counter
                else_if_let_count = self.snippet_positions.get('else_if_let_count', 0)
                else_if_let_count += 1
                self.snippet_positions['else_if_let_count'] = else_if_let_count
                
                # Get the current indentation level
                line_start = snippet_end - 1
                while line_start > 0 and current_text[line_start - 1] not in '\n':
                    line_start -= 1
                indent = ''
                pos = line_start
                while pos < snippet_end and current_text[pos] in ' \t':
                    indent += current_text[pos]
                    pos += 1
                
                # Insert new else if let at the end
                insert_position = snippet_end
                cursor.setPosition(insert_position)
                pattern_name = f"pattern{else_if_let_count + 1}"
                value_name = f"value{else_if_let_count + 1}"
                cursor.insertText(f' else if let {pattern_name} = {value_name} {{\n{indent}    \n{indent}}}')
                
                # Update snippet end
                current_text = self.editor.toPlainText()
                snippet_end = find_snippet_end()
                if snippet_end:
                    self.snippet_positions['end'] = snippet_end
                
                # Find and select the new pattern we just inserted
                # Search forward from where we inserted, not backward from the end
                search_text = current_text[insert_position:]
                else_if_let_pos = search_text.find('else if let ')
                if else_if_let_pos != -1:
                    pattern_start = insert_position + else_if_let_pos + 12  # After "else if let "
                    # Find the = sign
                    equals_pos = search_text.find('=', else_if_let_pos)
                    if equals_pos != -1:
                        pattern_end = insert_position + equals_pos
                        # Trim whitespace
                        while pattern_end > pattern_start and current_text[pattern_end - 1] in ' \t':
                            pattern_end -= 1

                        cursor.setPosition(pattern_start)
                        cursor.setPosition(pattern_end, QTextCursor.KeepAnchor)
                        self.editor.setTextCursor(cursor)
                        self._highlight_snippet_stage()
                        self.snippet_positions['in_else_if_let_stage'] = 0
            return
        
        # Stage value: 4, 7, 10, 13... ((stage - 4) % 3 == 0) - Move to value
        elif (self.snippet_stage - 4) % 3 == 0:
            # Move to the last else if let value
            search_start = max(0, start_pos - 10)
            search_text = current_text[search_start:]
            else_if_let_pos = search_text.rfind('else if let ')
            if else_if_let_pos != -1:
                equals_pos = search_text.find('=', else_if_let_pos)
                if equals_pos != -1:
                    value_pos = search_start + equals_pos + 1
                    # Skip whitespace after =
                    while value_pos < len(current_text) and current_text[value_pos] in ' \t':
                        value_pos += 1
                    
                    # Find the opening brace to get value end
                    brace_pos = search_text.find('{', equals_pos)
                    if brace_pos != -1:
                        value_end = search_start + brace_pos
                        # Trim whitespace before {
                        while value_end > value_pos and current_text[value_end - 1] in ' \t':
                            value_end -= 1

                        cursor.setPosition(value_pos)
                        cursor.setPosition(value_end, QTextCursor.KeepAnchor)
                        self.editor.setTextCursor(cursor)
                        self._highlight_snippet_stage()
                        self.snippet_positions['in_else_if_let_stage'] = 1
            return
        
        # Stage body: 5, 8, 11, 14... ((stage - 5) % 3 == 0) - Move to body
        elif (self.snippet_stage - 5) % 3 == 0:
            # Move to the last else if let body
            search_start = max(0, start_pos - 10)
            search_text = current_text[search_start:]
            else_if_let_pos = search_text.rfind('else if let ')
            if else_if_let_pos != -1:
                brace_pos = search_text.find('{', else_if_let_pos)
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
                    self.snippet_positions['in_else_if_let_stage'] = 2
            return

    # Should not reach here
    self.finish()
    return


def _cancel_ifl(self):
    """
    Handle Escape key for 'ifl' (if let) snippet.
    - Stage 0: Delete entire snippet
    - Stage 1: Finish (keep just the if let)
    - Stage 2: Finish (keep just the if let)
    - Stage 3+ (else-if-let stages): Remove last else-if-let and skip to final else phase
    - Final else phase: Finish
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
            ifl_pos = search_text.find('if let ')
            if ifl_pos != -1:
                brace_pos = search_text.find('{', ifl_pos)
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
    
    elif self.snippet_stage == 1 or self.snippet_stage == 2:
        # Stage 1 or 2: Just finish, keep the if let statement
        self.finish()
        return
    
    elif self.snippet_stage >= 3:
        # Stage 3+: Remove the last else-if-let and skip to final else phase
        # Find current end of snippet
        def find_snippet_end():
            search_start = max(0, self.snippet_positions.get('start', 0) - 10)
            search_text = current_text[search_start:]
            ifl_pos = search_text.find('if let ')
            if ifl_pos == -1:
                return None
            first_brace = search_text.find('{', ifl_pos)
            if first_brace == -1:
                return None
            pos = search_start + first_brace
            brace_count = 0
            last_close = pos
            i = pos
            while i < len(current_text):
                if current_text[i] == '{':
                    brace_count += 1
                elif current_text[i] == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        last_close = i
                        j = i + 1
                        while j < len(current_text) and current_text[j] in ' \t\n':
                            j += 1
                        if j < len(current_text) - 4 and current_text[j:j+4] == 'else':
                            i = j + 3
                        else:
                            return last_close + 1
                i += 1
            return last_close + 1 if brace_count == 0 else None
        
        # First, check if we need to remove the last else-if-let
        else_if_let_count = self.snippet_positions.get('else_if_let_count', 0)
        if else_if_let_count > 0:
            # Find and remove the last else-if-let block
            search_start = max(0, self.snippet_positions.get('start', 0) - 10)
            search_text = current_text[search_start:]
            
            # Find the last "else if let"
            last_else_if_let_pos = search_text.rfind('else if let ')
            if last_else_if_let_pos != -1:
                # Find the opening brace of this else-if-let
                brace_pos = search_text.find('{', last_else_if_let_pos)
                if brace_pos != -1:
                    brace_start = search_start + brace_pos
                    brace_end = self._find_matching_brace(current_text, brace_start)
                    if brace_end != -1:
                        # Delete from " else if let" to the closing brace
                        delete_start = search_start + last_else_if_let_pos
                        delete_end = brace_end + 1
                        cursor.setPosition(delete_start)
                        cursor.setPosition(delete_end, QTextCursor.KeepAnchor)
                        cursor.removeSelectedText()
                        
                        # Update current_text after deletion
                        current_text = self.editor.toPlainText()
        
        snippet_end = find_snippet_end()
        if snippet_end is not None:
            # Check if we already have an else block
            search_from = snippet_end - 50 if snippet_end > 50 else 0
            search_text = current_text[search_from:snippet_end]
            
            # Check if there's already a final else (not else if let)
            # Look for "else {" without "if" before it
            else_matches = []
            pos = 0
            while True:
                else_pos = search_text.find('else', pos)
                if else_pos == -1:
                    break
                # Check if it's "else if" or just "else"
                after_else = else_pos + 4
                while after_else < len(search_text) and search_text[after_else] in ' \t':
                    after_else += 1
                if after_else < len(search_text) and search_text[after_else] != 'i':  # Not "if"
                    else_matches.append(else_pos)
                pos = else_pos + 1
            
            has_final_else = len(else_matches) > 0
            
            if has_final_else:
                # Already have final else, just finish
                # Move cursor to inside the else body
                last_else_pos = search_from + else_matches[-1]
                brace_pos = current_text.find('{', last_else_pos)
                if brace_pos != -1:
                    body_start = brace_pos + 1
                    if body_start < len(current_text) and current_text[body_start] == '\n':
                        body_start += 1
                    while body_start < len(current_text) and current_text[body_start] in ' \t':
                        body_start += 1
                    cursor.setPosition(body_start)
                    self.editor.setTextCursor(cursor)
                self.finish()
            else:
                # Get the current indentation level
                line_start = snippet_end - 1
                while line_start > 0 and current_text[line_start - 1] not in '\n':
                    line_start -= 1
                indent = ''
                pos = line_start
                while pos < snippet_end and current_text[pos] in ' \t':
                    indent += current_text[pos]
                    pos += 1
                
                # Add final else block at snippet_end position
                insert_position = snippet_end
                cursor.setPosition(insert_position)
                cursor.insertText(f' else {{\n{indent}    \n{indent}}}')
                
                # Now find the body position of the else we JUST inserted
                # We know it starts right after insert_position
                current_text = self.editor.toPlainText()
                
                # Search for "else {" starting from insert_position
                search_start = insert_position
                search_text = current_text[search_start:]
                
                # Find the first "else {" after our insert position
                else_pos = search_text.find('else {')
                if else_pos != -1:
                    # Find the opening brace
                    brace_pos = search_text.find('{', else_pos)
                    if brace_pos != -1:
                        # Calculate absolute position of the body
                        body_start = search_start + brace_pos + 1
                        # Skip newline
                        if body_start < len(current_text) and current_text[body_start] == '\n':
                            body_start += 1
                        # Skip indentation
                        while body_start < len(current_text) and current_text[body_start] in ' \t':
                            body_start += 1
                        
                        # Move cursor to the body
                        cursor.setPosition(body_start)
                        self.editor.setTextCursor(cursor)
                
                # Finish the snippet
                self.finish()
        return


def _expand_mod_snippet(self, start_pos, length):
    """
    Expand 'mod' into a module definition with 2 phases.
    
    Phase 0: mod name { }
    - Cursor at 'name' (highlighted)
    - Tab → Phase 1 (move to body)
    - Escape → Delete entire snippet
    
    Phase 1: mod name { [body] }
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
    template = f"mod name {{\n{indent}    \n{indent}}}"
    cursor.insertText(template)
    
    # Store only the start position - we'll calculate everything else dynamically
    self.snippet_positions = {
        'start': start_pos  # Store where "mod" starts
    }
    self.snippet_active = True
    self.snippet_stage = 0
    self.snippet_trigger = 'mod'
    
    # Get current text to find actual positions
    current_text = self.editor.toPlainText()
    
    # Find "mod " starting from start_pos
    search_start = max(0, start_pos - 10)
    search_text = current_text[search_start:]
    
    mod_pos = search_text.find('mod ')
    if mod_pos != -1:
        actual_start = search_start + mod_pos
        name_start = actual_start + 4  # After "mod "
        
        # Find " {" to get name end
        brace_pos = search_text.find('{', mod_pos)
        if brace_pos != -1:
            name_end = search_start + brace_pos
            # Trim whitespace before {
            while name_end > name_start and current_text[name_end - 1] in ' \t':
                name_end -= 1
            
            # Select the name
            cursor.setPosition(name_start)
            cursor.setPosition(name_end, QTextCursor.KeepAnchor)
            self.editor.setTextCursor(cursor)
            self._highlight_snippet_stage()


def _next_stage_mod(self):
    """Handle Tab progression for 'mod' snippet."""
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
        
        mod_pos = search_text.find('mod ')
        if mod_pos != -1:
            brace_pos = search_text.find('{', mod_pos)
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


def _cancel_mod(self):
    """
    Handle Escape key for 'mod' snippet.
    - Stage 0: Delete entire snippet
    - Stage 1+: Finish (keep the mod)
    """
    cursor = self.editor.textCursor()
    current_text = self.editor.toPlainText()
    
    if self.snippet_stage == 0:
        # Stage 0: Delete entire snippet
        start = self.snippet_positions.get('start')
        if start is not None:
            search_start = max(0, start - 10)
            search_text = current_text[search_start:]
            mod_pos = search_text.find('mod ')
            if mod_pos != -1:
                brace_pos = search_text.find('{', mod_pos)
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
        # Stage 1+: Just finish, keep the mod
        self.finish()
        return


def _cancel_if(self):
    """
    Handle Escape key for 'if' snippet.
    - Stage 0: Delete entire snippet
    - Stage 1: Finish (keep just the if)
    - Stage 2+ (else-if stages): Skip to final else phase
    - Final else phase: Finish
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
            if_pos = search_text.find('if ')
            if if_pos != -1:
                brace_pos = search_text.find('{', if_pos)
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
    
    elif self.snippet_stage == 1:
        # Stage 1: Just finish, keep the if statement
        self.finish()
        return
    
    elif self.snippet_stage >= 2:
        # Stage 2+: Remove the last else-if (if we're in else-if stage) and skip to final else phase
        # Find current end of snippet
        def find_snippet_end():
            search_start = max(0, self.snippet_positions.get('start', 0) - 10)
            search_text = current_text[search_start:]
            if_pos = search_text.find('if ')
            if if_pos == -1:
                return None
            first_brace = search_text.find('{', if_pos)
            if first_brace == -1:
                return None
            pos = search_start + first_brace
            brace_count = 0
            last_close = pos
            i = pos
            while i < len(current_text):
                if current_text[i] == '{':
                    brace_count += 1
                elif current_text[i] == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        last_close = i
                        j = i + 1
                        while j < len(current_text) and current_text[j] in ' \t\n':
                            j += 1
                        if j < len(current_text) - 4 and current_text[j:j+4] == 'else':
                            i = j + 3
                        else:
                            return last_close + 1
                i += 1
            return last_close + 1 if brace_count == 0 else None
        
        # First, check if we need to remove the last else-if
        # If we're at an even stage (just added else-if condition) or odd stage (in else-if body)
        # and there are else-if blocks, remove the last one
        else_if_count = self.snippet_positions.get('else_if_count', 0)
        if else_if_count > 0:
            # Find and remove the last else-if block
            search_start = max(0, self.snippet_positions.get('start', 0) - 10)
            search_text = current_text[search_start:]
            
            # Find the last "else if"
            last_else_if_pos = search_text.rfind('else if ')
            if last_else_if_pos != -1:
                # Find the opening brace of this else-if
                brace_pos = search_text.find('{', last_else_if_pos)
                if brace_pos != -1:
                    brace_start = search_start + brace_pos
                    brace_end = self._find_matching_brace(current_text, brace_start)
                    if brace_end != -1:
                        # Delete from " else if" to the closing brace
                        delete_start = search_start + last_else_if_pos
                        delete_end = brace_end + 1
                        cursor.setPosition(delete_start)
                        cursor.setPosition(delete_end, QTextCursor.KeepAnchor)
                        cursor.removeSelectedText()
                        
                        # Update current_text after deletion
                        current_text = self.editor.toPlainText()
        
        snippet_end = find_snippet_end()
        if snippet_end is not None:
            # Check if we already have an else block
            search_from = snippet_end - 50 if snippet_end > 50 else 0
            search_text = current_text[search_from:snippet_end]
            
            # Check if there's already a final else (not else if)
            # Look for "else {" without "if" before it
            else_matches = []
            pos = 0
            while True:
                else_pos = search_text.find('else', pos)
                if else_pos == -1:
                    break
                # Check if it's "else if" or just "else"
                after_else = else_pos + 4
                while after_else < len(search_text) and search_text[after_else] in ' \t':
                    after_else += 1
                if after_else < len(search_text) and search_text[after_else] != 'i':  # Not "if"
                    else_matches.append(else_pos)
                pos = else_pos + 1
            
            has_final_else = len(else_matches) > 0
            
            if has_final_else:
                # Already have final else, just finish
                # Move cursor to inside the else body
                last_else_pos = search_from + else_matches[-1]
                brace_pos = current_text.find('{', last_else_pos)
                if brace_pos != -1:
                    body_start = brace_pos + 1
                    if body_start < len(current_text) and current_text[body_start] == '\n':
                        body_start += 1
                    while body_start < len(current_text) and current_text[body_start] in ' \t':
                        body_start += 1
                    cursor.setPosition(body_start)
                    self.editor.setTextCursor(cursor)
                self.finish()
            else:
                # Get the current indentation level
                line_start = snippet_end - 1
                while line_start > 0 and current_text[line_start - 1] not in '\n':
                    line_start -= 1
                indent = ''
                pos = line_start
                while pos < snippet_end and current_text[pos] in ' \t':
                    indent += current_text[pos]
                    pos += 1
                
                # Add final else block at snippet_end position
                insert_position = snippet_end
                cursor.setPosition(insert_position)
                cursor.insertText(f' else {{\n{indent}    \n{indent}}}')
                
                # Now find the body position of the else we JUST inserted
                # We know it starts right after insert_position
                current_text = self.editor.toPlainText()
                
                # Search for "else {" starting from insert_position
                search_start = insert_position
                search_text = current_text[search_start:]
                
                # Find the first "else {" after our insert position
                else_pos = search_text.find('else {')
                if else_pos != -1:
                    # Find the opening brace
                    brace_pos = search_text.find('{', else_pos)
                    if brace_pos != -1:
                        # Calculate absolute position of the body
                        body_start = search_start + brace_pos + 1
                        # Skip newline
                        if body_start < len(current_text) and current_text[body_start] == '\n':
                            body_start += 1
                        # Skip indentation
                        while body_start < len(current_text) and current_text[body_start] in ' \t':
                            body_start += 1
                        
                        # Move cursor to the body
                        cursor.setPosition(body_start)
                        self.editor.setTextCursor(cursor)
                
                # Finish the snippet
                self.finish()
        return


# You can add more snippet expansion methods here in the future
# For example:
# def _expand_for_snippet(self, start_pos, length):
#     """Expand 'for' into a for loop"""
#     pass
#
# def _expand_while_snippet(self, start_pos, length):
#     """Expand 'while' into a while loop"""
#     pass
#
# def _expand_match_snippet(self, start_pos, length):
#     """Expand 'match' into a match expression"""
#     pass
