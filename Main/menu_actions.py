"""
Menu actions and UI interaction methods.
"""
import sys
import subprocess
from PySide6.QtCore import QUrl, QSize, QTimer
from PySide6.QtGui import QDesktopServices, QTextCursor, QIcon, QPixmap, QPainter, QColor, QFont, QStandardItemModel, QStandardItem
from PySide6.QtWidgets import QCompleter
from Details.dialogs import CustomMessageBox, KeyboardShortcutsDialog, LicenseDialog
from file_showen import apply_modern_scrollbar_style


class MenuActionsManager:
    """Manages menu actions and UI interactions."""
    
    def __init__(self, main_window):
        self.main_window = main_window

    # ++++++++++++++++++++++++++ Edit and Selection Menu Methods ++++++++++++++++++++++++++
    def undo(self):
        """Perform Undo.
        - When Manage view is active, delegate to its canvas (undo Delete/Remove Connection).
        - Otherwise, call the editor's undo if available.
        """
        # Prefer Manage canvas when Manage view is visible
        try:
            stack = getattr(self.main_window, 'main_content_stack', None)
            if stack and stack.currentIndex() == 1 and hasattr(self.main_window, 'manage_widget'):
                canvas = getattr(self.main_window.manage_widget, 'canvas', None)
                if canvas and hasattr(canvas, 'undo'):
                    canvas.undo()
                    return
        except Exception:
            pass
        # Fallback to current editor if it supports undo
        editor = self.main_window.get_current_editor()
        if editor and hasattr(editor, 'undo'):
            editor.undo()

    def redo(self):
        """Perform Redo.
        - When Manage view is active, delegate to its canvas (redo Delete/Remove Connection).
        - Otherwise, call the editor's redo if available.
        """
        # Prefer Manage canvas when Manage view is visible
        try:
            stack = getattr(self.main_window, 'main_content_stack', None)
            if stack and stack.currentIndex() == 1 and hasattr(self.main_window, 'manage_widget'):
                canvas = getattr(self.main_window.manage_widget, 'canvas', None)
                if canvas and hasattr(canvas, 'redo'):
                    canvas.redo()
                    return
        except Exception:
            pass
        # Fallback to current editor if it supports redo
        editor = self.main_window.get_current_editor()
        if editor and hasattr(editor, 'redo'):
            editor.redo()

    def cut(self):
        editor = self.main_window.get_current_editor()
        if editor:
            editor.cut()

    def copy(self):
        editor = self.main_window.get_current_editor()
        if editor:
            editor.copy()

    def paste(self):
        editor = self.main_window.get_current_editor()
        if editor:
            editor.paste()

    def find_text(self):
        editor = self.main_window.get_current_editor()
        if editor:
            cursor = editor.textCursor()
            selected_text = cursor.selectedText()
            
            # Show the search/replace widget
            editor.search_replace_widget.show()
            
            # If there is selected text, put it in the search input and trigger a search
            if selected_text:
                editor.search_replace_widget.search_input.setText(selected_text)
                editor.search_replace_widget.find_next()  # Or whatever the search function is called
            
            # Always set focus to the search input
            editor.search_replace_widget.search_input.setFocus()

    def replace_text(self):
        editor = self.main_window.get_current_editor()
        if editor:
            editor.search_replace_widget.show()
            editor.search_replace_widget.replace_input.setFocus()

    def select_all(self):
        editor = self.main_window.get_current_editor()
        if editor:
            editor.selectAll()

    def expand_selection(self):
        editor = self.main_window.get_current_editor()
        if editor and hasattr(editor, 'expandSelectionVSCodeLike'):
            editor.expandSelectionVSCodeLike()

    def shrink_selection(self):
        editor = self.main_window.get_current_editor()
        if editor and hasattr(editor, 'shrinkSelectionVSCodeLike'):
            editor.shrinkSelectionVSCodeLike()

    def add_cursor_above(self):
        editor = self.main_window.get_current_editor()
        if editor and hasattr(editor, 'multi') and editor.multi:
            editor.multi.add_caret_above()
            editor.highlightCurrentLine()
            editor.setFocus()

    def add_cursor_below(self):
        editor = self.main_window.get_current_editor()
        if editor and hasattr(editor, 'multi') and editor.multi:
            editor.multi.add_caret_below()
            editor.highlightCurrentLine()
            editor.setFocus()

    def copy_line_up(self):
        editor = self.main_window.get_current_editor()
        if editor:
            cursor = editor.textCursor()
            cursor.beginEditBlock()
            # Capture current line and caret column
            block = cursor.block()
            line_text = block.text()
            insert_pos = block.position()
            rel_col = cursor.position() - insert_pos
            # Insert duplicate line above using a temp cursor (so we can reposition main cursor afterwards)
            tmp = QTextCursor(editor.document())
            tmp.setPosition(insert_pos)
            tmp.insertText(line_text + '\n')
            # Place caret on the new (inserted) line at the same column (clamped to line length)
            new_col = min(max(rel_col, 0), len(line_text))
            cursor.setPosition(insert_pos + new_col)
            cursor.endEditBlock()
            editor.setTextCursor(cursor)

    def copy_line_down(self):
        editor = self.main_window.get_current_editor()
        if editor:
            cursor = editor.textCursor()
            cursor.beginEditBlock()
            cursor.movePosition(QTextCursor.EndOfLine)
            cursor.movePosition(QTextCursor.StartOfLine, QTextCursor.KeepAnchor)
            line_text = cursor.selectedText()
            cursor.clearSelection()
            cursor.movePosition(QTextCursor.EndOfLine)
            cursor.insertText('\n' + line_text)
            cursor.endEditBlock()

    def move_line_up(self):
        editor = self.main_window.get_current_editor()
        if editor:
            cursor = editor.textCursor()
            cursor.beginEditBlock()
            block = cursor.block()
            prev_block = block.previous()
            if not prev_block.isValid():
                cursor.endEditBlock()
                return
            # Capture texts and positions
            curr_start = block.position()
            prev_start = prev_block.position()
            curr_text = block.text()
            prev_text = prev_block.text()
            rel_col = max(0, cursor.position() - curr_start)
            # Preserve exact separators as present in the document
            s_prev = '\n' if prev_block.length() > len(prev_text) else ''
            s_curr = '\n' if block.length() > len(curr_text) else ''
            # Select the exact region covering previous and current blocks
            region_start = prev_start
            region_end = prev_start + prev_block.length() + block.length()
            cursor.setPosition(region_start)
            cursor.setPosition(region_end, QTextCursor.KeepAnchor)
            # Replace with swapped lines, preserving separators
            cursor.insertText(f"{curr_text}{s_prev}{prev_text}{s_curr}")
            # Place caret on the moved line (now at region_start) at the same column
            new_col = min(rel_col, len(curr_text))
            cursor.setPosition(region_start + new_col)
            cursor.endEditBlock()
            editor.setTextCursor(cursor)

    def move_line_down(self):
        editor = self.main_window.get_current_editor()
        if editor:
            cursor = editor.textCursor()
            cursor.beginEditBlock()
            block = cursor.block()
            next_block = block.next()
            if not next_block.isValid():
                cursor.endEditBlock()
                return
            # Capture texts and positions
            curr_start = block.position()
            curr_text = block.text()
            next_text = next_block.text()
            rel_col = max(0, cursor.position() - curr_start)
            # Preserve exact separators as present in the document
            s_curr = '\n' if block.length() > len(curr_text) else ''
            s_next = '\n' if next_block.length() > len(next_text) else ''
            # Select the exact region covering current and next blocks
            region_start = curr_start
            region_end = block.position() + block.length() + next_block.length()
            cursor.setPosition(region_start)
            cursor.setPosition(region_end, QTextCursor.KeepAnchor)
            # Replace with swapped lines, preserving separators
            cursor.insertText(f"{next_text}{s_curr}{curr_text}{s_next}")
            # Place caret on the moved line (now second in region)
            new_block_start = region_start + len(next_text) + len(s_curr)
            new_col = min(rel_col, len(curr_text))
            cursor.setPosition(new_block_start + new_col)
            cursor.endEditBlock()
            editor.setTextCursor(cursor)

    def toggle_line_comment(self):
        """Toggle line comments for Rust code using // syntax."""
        editor = self.main_window.get_current_editor()
        if not editor:
            return

        cursor = editor.textCursor()
        cursor.beginEditBlock()

        start_pos = cursor.selectionStart()
        end_pos = cursor.selectionEnd()

        start_block = editor.document().findBlock(start_pos)
        end_block = editor.document().findBlock(end_pos)

        # If selection ends at the start of a line, don't include that line
        if cursor.hasSelection() and end_block.position() == end_pos and start_block != end_block:
            end_block = end_block.previous()

        # Collect all lines to process and check if all are commented
        lines_to_process = []
        is_uncommenting = True
        block = start_block
        while block.isValid() and block.position() <= end_block.position():
            text = block.text()
            lines_to_process.append(block)
            # Check if this line is NOT commented (including empty lines)
            if not text.lstrip().startswith('//'):
                is_uncommenting = False
            block = block.next()

        # Process each line
        for block in lines_to_process:
            line_cursor = QTextCursor(block)
            text = block.text()
            
            if is_uncommenting:
                # Remove comment
                stripped = text.lstrip()
                if stripped.startswith('// '):
                    # Find the position of '//' in the original text
                    index = text.find('//')
                    line_cursor.setPosition(block.position() + index)
                    # Delete '// ' (3 characters)
                    for _ in range(3):
                        line_cursor.deleteChar()
                elif stripped.startswith('//'):
                    # Find the position of '//' in the original text
                    index = text.find('//')
                    line_cursor.setPosition(block.position() + index)
                    # Delete '//' (2 characters)
                    for _ in range(2):
                        line_cursor.deleteChar()
            else:
                # Add comment (including to empty lines)
                indentation = len(text) - len(text.lstrip())
                line_cursor.setPosition(block.position() + indentation)
                line_cursor.insertText('// ')

        cursor.endEditBlock()
        editor.setTextCursor(cursor)
        
        # Refresh syntax highlighting
        if hasattr(editor, 'highlighter') and editor.highlighter:
            editor.highlighter.rehighlight()

    def toggle_block_comment(self):
        """Toggle block comments for Rust code using /* */ syntax."""
        editor = self.main_window.get_current_editor()
        if not editor:
            return
            
        cursor = editor.textCursor()
        cursor.beginEditBlock()
        
        if not cursor.hasSelection():
            # Insert the block comment markers and move cursor to the middle
            start_pos = cursor.position()
            cursor.insertText('/*  */')
            # Move cursor to the center (between the two spaces)
            cursor.setPosition(start_pos + 3)
            editor.setTextCursor(cursor)
        else:
            selected_text = cursor.selectedText()
            
            # Check if the selection is already a block comment
            if selected_text.startswith('/*') and selected_text.endswith('*/'):
                # Remove block comment - strip the /* and */ markers
                text = selected_text[2:-2]
                # Also remove leading/trailing space if present
                if text.startswith(' '):
                    text = text[1:]
                if text.endswith(' '):
                    text = text[:-1]
                cursor.insertText(text)
            else:
                # Add block comment
                cursor.insertText(f'/* {selected_text} */')

        cursor.endEditBlock()
        editor.setTextCursor(cursor)
        
        # Refresh syntax highlighting
        if hasattr(editor, 'highlighter') and editor.highlighter:
            editor.highlighter.rehighlight()

    # ++++++++++++++++++++++++++ Help Menu Methods ++++++++++++++++++++++++++
    def show_about_dialog(self):
        CustomMessageBox.about(self.main_window, "About A³ Rust Editor",
                          "<b>A³ Rust Editor</b><br>"
                          "Version 1.0<br>"
                          "A modern Rust development environment built with PySide6.<br><br>"
                          "Made with ❤️ by Ahmed Rabiee")

    def open_documentation(self):
        QDesktopServices.openUrl(QUrl("https://doc.rust-lang.org/"))

    def show_welcome_message(self):
        CustomMessageBox.information(self.main_window, "Welcome", "Welcome to A³ Rust Editor! Discover its features and enjoy coding.")

    def show_keyboard_shortcuts(self):
        dialog = KeyboardShortcutsDialog(self.main_window)
        dialog.exec()

    def open_video_tutorials(self):
        QDesktopServices.openUrl(QUrl("https://www.youtube.com/@Crasius-madman"))

    def show_tips_and_tricks(self):
        CustomMessageBox.information(self.main_window, "Tips and Tricks", "- Use Ctrl+F to search for text.\n- Use Ctrl+H to replace text.\n- Use Ctrl+/ to toggle line comments.")

    def join_youtube(self):
        QDesktopServices.openUrl(QUrl("https://www.youtube.com/@Crasius-madman"))

    def report_issue(self):
        QDesktopServices.openUrl(QUrl("https://github.com/CrasiusAhmed"))

    def view_license(self):
        dialog = LicenseDialog(self.main_window)
        dialog.exec()

    def check_for_updates(self):
        CustomMessageBox.information(self.main_window, "Check for Updates", "You are using the latest version of A³ Rust Editor.")

    def new_window(self):
        subprocess.Popen([sys.executable] + sys.argv)

    def setup_completer_for_editor(self, editor):
        """Sets up smart auto-correction for Rust code.
        - Automatically fixes typos in keywords (ftn -> fn, eni -> enum, wqs -> fn)
        - Adds missing brackets, braces, quotes, semicolons
        - Context-aware corrections based on Rust syntax
        """
        # Import the new smart auto-correction system
        from Main.smart_autocorrect import RustSmartAutoCorrect
        
        # Initialize and attach to editor
        autocorrect = RustSmartAutoCorrect(editor)
        editor.rust_autocorrect = autocorrect
