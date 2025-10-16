"""
File operations and management functionality.
"""
import os
import json
from functools import partial
from PySide6.QtCore import QFileInfo, QDir
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QFileDialog, QMessageBox, QTabBar, QPushButton
from Details.Main_Code_Editor import CodeEditor
from Details.dialogs import CustomInputDialog
from coding_phcjp import RustSyntaxHighlighter
from Main.rust_error_checker import RustErrorChecker


class FileOperationsManager:
    """Manages file operations like open, save, create, etc."""
    
    def __init__(self, main_window):
        self.main_window = main_window

    def create_new_file(self, base_path=None):
        """ Creates a new file using a custom dialog. """
        if base_path and not QFileInfo(base_path).isDir():
            base_path = QFileInfo(base_path).dir().path()
        elif not base_path:
            source_root_index = self.main_window.proxy_model.mapToSource(self.main_window.tree_view.rootIndex())
            base_path = self.main_window.file_model.filePath(source_root_index)

        # Auto-close welcome tab when creating a new file (VS Code-like behavior)
        if self.main_window.welcome_tab_index != -1:
            self.main_window.close_welcome_tab()

        file_name, ok = CustomInputDialog.getText(self.main_window, "New File", "Enter file name (e.g., new_file.txt)")
        if ok and file_name:
            # --- FIX: Ensure the path is absolute ---
            new_path = os.path.abspath(os.path.join(base_path, file_name))
            if not os.path.exists(new_path):
                with open(new_path, 'w') as f:
                    f.write("")  # Create an empty file
                self.main_window.statusBar().showMessage(f"File created: {file_name}", 2000)
                self.open_file_for_editing(new_path)
            else:
                QMessageBox.warning(self.main_window, "Warning", "File already exists.")

    def open_file(self):
        path, _ = QFileDialog.getOpenFileName(self.main_window, "Open File")
        if path:
            self.open_file_for_editing(path)

    def open_folder(self):
        """
        Opens a folder and sets it as the root for the file tree in both the main view and the manage view.
        Also syncs the Inspect panel's file tree root.
        """
        path = QFileDialog.getExistingDirectory(self.main_window, "Open Folder")
        if path:
            # --- FIX: Ensure the path is absolute ---
            path = os.path.abspath(path)
            
            # --- NEW: Close all open editor tabs (VS Code-like behavior) ---
            # Close all tabs from right to left to avoid index shifting issues
            while self.main_window.editor_tabs.count() > 0:
                self.main_window.close_editor_tab(self.main_window.editor_tabs.count() - 1)
            
            # Update the main file tree
            self.main_window.tree_view.setRootIndex(self.main_window.proxy_model.mapFromSource(self.main_window.file_model.index(path)))
            self.main_window.statusBar().showMessage(f"Opened folder: {path}", 3000)

            # --- NEW: Update the manage widget's file tree as well ---
            if hasattr(self.main_window.manage_widget, 'set_root_path'):
                self.main_window.manage_widget.set_root_path(path)
            # --- NEW: Sync Inspect file tree root ---
            try:
                if hasattr(self.main_window, 'inspect_widget') and hasattr(self.main_window.inspect_widget, 'set_root_path'):
                    self.main_window.inspect_widget.set_root_path(path)
            except Exception:
                pass

            # --- FIX: Update all open terminals to the new directory ---
            self.update_all_terminals_directory(path)
            
            # --- FIX: Save the last opened folder to settings ---
            try:
                self.main_window.settings['last_folder'] = path
                self.main_window.save_settings()
            except Exception:
                pass

    def open_folder_from_path(self, path):
        """
        Opens the provided folder path and sets it as the root for the file tree
        in both the main view and the manage view, without showing a dialog.
        Also syncs the Inspect panel's file tree root.
        """
        if not path:
            return
        path = os.path.abspath(path)
        if not os.path.isdir(path):
            return
        
        # --- NEW: Close all open editor tabs (VS Code-like behavior) ---
        # Close all tabs from right to left to avoid index shifting issues
        while self.main_window.editor_tabs.count() > 0:
            self.main_window.close_editor_tab(self.main_window.editor_tabs.count() - 1)
        
        # Update the main file tree
        self.main_window.tree_view.setRootIndex(self.main_window.proxy_model.mapFromSource(self.main_window.file_model.index(path)))
        self.main_window.statusBar().showMessage(f"Opened folder: {path}", 3000)

        # Update the manage widget's file tree as well
        if hasattr(self.main_window.manage_widget, 'set_root_path'):
            self.main_window.manage_widget.set_root_path(path)
        # Sync Inspect file tree root
        try:
            if hasattr(self.main_window, 'inspect_widget') and hasattr(self.main_window.inspect_widget, 'set_root_path'):
                self.main_window.inspect_widget.set_root_path(path)
        except Exception:
            pass

        # Update all open terminals to the new directory
        self.update_all_terminals_directory(path)
        
        # --- FIX: Save the last opened folder to settings ---
        try:
            self.main_window.settings['last_folder'] = path
            self.main_window.save_settings()
        except Exception:
            pass

    def update_all_terminals_directory(self, path):
        """ Sends a 'cd' command to all open terminal instances. """
        for i in range(self.main_window.terminal_tabs.count()):
            terminal = self.main_window.terminal_tabs.widget(i)
            if hasattr(terminal, 'process'):  # Check if it's an InteractiveTerminal
                # Use f-string for cleaner formatting
                command = f'cd "{path}"\n'
                terminal.process.write(command.encode('utf-8'))

    def open_file_for_editing(self, path, line_number=None):
        # --- FIX: Convert to absolute path to handle files from different drives/locations ---
        path = os.path.abspath(path)
        self.main_window.current_file_path = path  # Keep track of last clicked file
        # --- NEW: Persist last opened file for restore on next launch ---
        try:
            self.main_window.settings['last_open_file'] = path
            self.save_settings()
        except Exception:
            pass

        # Auto-close welcome tab when opening a file (VS Code-like behavior)
        if self.main_window.welcome_tab_index != -1:
            self.main_window.close_welcome_tab()

        if path in self.main_window.open_files:
            ed = self.main_window.open_files[path]
            # Ensure Rust highlighter is applied for .rs files
            try:
                if path.lower().endswith('.rs'):
                    try:
                        if getattr(ed, 'highlighter', None):
                            ed.highlighter.setDocument(None)
                    except Exception:
                        pass
                    try:
                        ed.highlighter = RustSyntaxHighlighter(ed.document())
                        ed.highlighter.rehighlight()
                    except Exception:
                        pass
            except Exception:
                pass
            self.main_window.editor_tabs.setCurrentWidget(ed)
            
            # If line number is provided, scroll to and highlight that line
            if line_number is not None and line_number > 0:
                self._scroll_to_and_highlight_line(ed, line_number)
            return

        try:
            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                data = f.read()
        except Exception as e:
            QMessageBox.warning(self.main_window, "Error", f"Could not open file: {e}")
            return
        
        editor = CodeEditor(self.main_window)
        # Set the font from settings
        settings_font = QFont(self.main_window.settings['font_family'], self.main_window.settings['font_size'])
        editor.setFont(settings_font)
        # Update the base font for Ctrl+0 reset to use the settings font, not the default Qt font
        try:
            editor._base_font = QFont(settings_font)
        except Exception:
            pass
        
        # Configure Rust syntax highlighting for .rs files
        try:
            if path.lower().endswith('.rs'):
                try:
                    if getattr(editor, 'highlighter', None):
                        editor.highlighter.setDocument(None)
                except Exception:
                    pass
                try:
                    editor.highlighter = RustSyntaxHighlighter(editor.document())
                except Exception:
                    pass
        except Exception:
            pass
        
        self.main_window.setup_completer_for_editor(editor)  # Setup autocompletion for new editor
        
        editor.setPlainText(data)
        
        # Force line number area to update and show immediately
        try:
            editor.updateLineNumberAreaWidth(0)
            editor.lineNumberArea.update()
            editor.viewport().update()
        except Exception:
            pass
        # Force rehighlight after text is set
        try:
            if getattr(editor, 'highlighter', None):
                editor.highlighter.rehighlight()
        except Exception:
            pass
        editor.document().modificationChanged.connect(
            partial(self.main_window.on_modification_changed, editor)
        )
        # Apply any cached runtime error markers for this file to the editor's minimap
        try:
            markers = self.main_window.runtime_error_markers.get(path, []) if hasattr(self.main_window, 'runtime_error_markers') else []
            if hasattr(editor, 'set_runtime_error_markers'):
                editor.set_runtime_error_markers(markers)
            # Also highlight the first runtime error line for visibility
            if markers and hasattr(editor, 'highlight_error_line'):
                editor.highlight_error_line(int(markers[0]))
        except Exception:
            pass
        
        tab_index = self.main_window.editor_tabs.addTab(editor, QFileInfo(path).fileName())
        self.main_window.editor_tabs.setCurrentWidget(editor)
        self.main_window.open_files[path] = editor

        # Add custom close button and keep it behind the scroller arrows
        close_button = QPushButton("X")
        close_button.setStyleSheet("border:none; background:transparent; color: #BDC1C6; font-weight: bold; font-size: 14px; padding: 2px 6px;")
        close_button.clicked.connect(lambda checked=False, ed=editor: self.main_window.close_editor_by_widget(ed))
        self.main_window.editor_tabs.tabBar().setTabButton(tab_index, QTabBar.RightSide, close_button)
        close_button.lower()  # ensure it stays behind the left/right scroller arrows
        self.main_window.closable_tabs_with_buttons[editor] = close_button

        if hasattr(self.main_window, 'run_linter'):
            self.main_window.run_linter(path)
        self.add_to_recent_files(path)
        # --- NEW: Mirror the opened file into Inspect editor ---
        try:
            if hasattr(self.main_window, 'inspect_widget') and hasattr(self.main_window.inspect_widget, 'set_current_file_from_external'):
                self.main_window.inspect_widget.set_current_file_from_external(path)
        except Exception:
            pass

        file_info = QFileInfo(path)
        suffix = file_info.suffix().lower()
        
        # Clear previous previews
        self.main_window.python_console_output.clear()  # Clear the dedicated Rust output
        if self.main_window.web_preview:
            self.main_window.web_preview.setHtml("")

        if suffix in ['html', 'htm'] and getattr(self.main_window, 'web_preview', None):
            self.main_window.web_preview.setHtml(data)
            self.main_window.preview_tabs.setCurrentWidget(self.main_window.web_preview)
        else:
            # Default: keep current preview tab; do not auto-run Rust on file open
            pass
        
        self.main_window.python_console_output.appendPlainText(f"File opened: {os.path.basename(path)}")
        
        # Attach Rust error checker for .rs files (but don't auto-check)
        if suffix == 'rs':
            try:
                error_checker = RustErrorChecker(editor)
                # Store the error checker on the editor so it persists
                editor.rust_error_checker = error_checker
                # Don't schedule check - only check when user tries to run
            except Exception as e:
                print(f"Error attaching Rust error checker: {e}")
        
        # Update toolbar visibility
        self.main_window.update_editor_toolbar_visibility()
        
        # If line number is provided, scroll to and highlight that line
        if line_number is not None and line_number > 0:
            self._scroll_to_and_highlight_line(editor, line_number)

    def _scroll_to_and_highlight_line(self, editor, line_number):
        """
        Scrolls to the specified line and highlights it with a VS Code-like background.
        The line number is 1-based.
        """
        try:
            from PySide6.QtGui import QTextCursor, QTextCharFormat, QColor, QTextFormat
            from PySide6.QtWidgets import QTextEdit
            from PySide6.QtCore import QTimer
            
            # Convert to 0-based line number
            line_index = line_number - 1
            
            # Get the block (line) at the specified line number
            block = editor.document().findBlockByLineNumber(line_index)
            if not block.isValid():
                return
            
            # Create a cursor at the beginning of the line
            cursor = QTextCursor(block)
            
            # Move cursor to the beginning of the line
            cursor.movePosition(QTextCursor.StartOfBlock)
            
            # Set the cursor in the editor (this will scroll to it)
            editor.setTextCursor(cursor)
            
            # Ensure the line is visible and centered
            editor.centerCursor()
            
            # Create a highlight selection for the line with VS Code-like color
            selection = QTextEdit.ExtraSelection()
            
            # Use a semi-transparent orange/yellow background like VS Code search results
            lineColor = QColor(234, 92, 0, 76)  # Orange with 30% opacity (0.3 * 255 ≈ 76)
            selection.format.setBackground(lineColor)
            selection.format.setProperty(QTextFormat.FullWidthSelection, True)
            
            selection.cursor = cursor
            selection.cursor.clearSelection()
            
            # Store the search highlight selection
            if not hasattr(editor, 'search_highlight_selection'):
                editor.search_highlight_selection = None
            
            editor.search_highlight_selection = selection
            
            # Apply the highlight immediately
            self._apply_search_highlight(editor)
            
            # Force a repaint
            editor.viewport().update()
            
            # Auto-clear the highlight after 3 seconds
            QTimer.singleShot(3000, lambda: self._clear_search_highlight(editor))
            
        except Exception as e:
            print(f"Error scrolling to line: {e}")
            import traceback
            traceback.print_exc()
    
    def _apply_search_highlight(self, editor):
        """Apply the search highlight to the editor"""
        try:
            extraSelections = []
            
            # Add current line highlight
            if not editor.isReadOnly():
                selection = QTextEdit.ExtraSelection()
                from PySide6.QtGui import QColor, QTextFormat
                lineColor = QColor("#282A2E")
                selection.format.setBackground(lineColor)
                selection.format.setProperty(QTextFormat.FullWidthSelection, True)
                selection.cursor = editor.textCursor()
                selection.cursor.clearSelection()
                extraSelections.append(selection)
            
            # Add all existing selections
            if hasattr(editor, 'error_selections'):
                extraSelections.extend(editor.error_selections)
            
            if hasattr(editor, 'success_selection') and editor.success_selection:
                extraSelections.append(editor.success_selection)
            
            if hasattr(editor, 'inspect_selection') and editor.inspect_selection:
                extraSelections.append(editor.inspect_selection)
            
            if hasattr(editor, 'search_selections'):
                extraSelections.extend(editor.search_selections)
            
            if hasattr(editor, 'syntax_error_selections'):
                extraSelections.extend(editor.syntax_error_selections)
            
            if hasattr(editor, 'runtime_error_selections'):
                extraSelections.extend(editor.runtime_error_selections)
            
            if hasattr(editor, 'cargo_toml_error_selections'):
                extraSelections.extend(editor.cargo_toml_error_selections)
            
            if hasattr(editor, 'bracket_match_selections'):
                extraSelections.extend(editor.bracket_match_selections)
            
            # Add the search highlight (should be on top)
            if hasattr(editor, 'search_highlight_selection') and editor.search_highlight_selection:
                extraSelections.append(editor.search_highlight_selection)
            
            # Add multi-cursor selections
            if hasattr(editor, 'multi') and editor.multi:
                extraSelections.extend(editor.multi.get_extra_selections())
            
            editor.setExtraSelections(extraSelections)
        except Exception as e:
            print(f"Error applying search highlight: {e}")
    
    def _clear_search_highlight(self, editor):
        """Clear the search highlight from the editor"""
        try:
            if hasattr(editor, 'search_highlight_selection'):
                editor.search_highlight_selection = None
            # Reapply all highlights without the search highlight
            if hasattr(editor, 'highlightCurrentLine'):
                editor.highlightCurrentLine()
        except Exception:
            pass

    def save_file(self):
        """
        Saves the current content of the active editor tab to its file.
        """
        editor = self.main_window.get_current_editor()
        if not editor:
            QMessageBox.information(self.main_window, "Info", "No file open to save.")
            return
        
        # Find the path associated with the current editor
        path_to_save = None
        for path, e in self.main_window.open_files.items():
            if e == editor:
                path_to_save = path
                break
        
        if not path_to_save:
            self.save_as_file()
            return

        try:
            with open(path_to_save, 'w', encoding='utf-8') as f:
                f.write(editor.toPlainText())

            editor.document().setModified(False)

            self.main_window.statusBar().showMessage(f"Saved: {os.path.basename(path_to_save)}", 2000)
            self.main_window.python_console_output.appendPlainText(f"Saved: {os.path.basename(path_to_save)}")

            # Clear any cached runtime error markers on save (they may be stale now)
            try:
                if hasattr(self.main_window, 'runtime_error_markers') and path_to_save in self.main_window.runtime_error_markers:
                    del self.main_window.runtime_error_markers[path_to_save]
                if hasattr(editor, 'set_runtime_error_markers'):
                    editor.set_runtime_error_markers([])
            except Exception:
                pass

            # --- NEW: Run linter on save ---
            if hasattr(self.main_window, 'run_linter'):
                self.main_window.run_linter(path_to_save)

        except Exception as e:
            QMessageBox.critical(self.main_window, "Error", f"Could not save file: {e}")
            self.main_window.python_console_output.appendPlainText(f"Error saving file: {e}")

    def save_as_file(self):
        editor = self.main_window.get_current_editor()
        if not editor:
            QMessageBox.information(self.main_window, "Info", "No file open to save.")
            return

        path_to_save, _ = QFileDialog.getSaveFileName(self.main_window, "Save File As")
        if not path_to_save:
            return

        try:
            with open(path_to_save, 'w', encoding='utf-8') as f:
                f.write(editor.toPlainText())

            editor.document().setModified(False)
            
            # Update open_files dictionary with the new path
            old_path = None
            for path, e in self.main_window.open_files.items():
                if e == editor:
                    old_path = path
                    break
            if old_path:
                del self.main_window.open_files[old_path]
            self.main_window.open_files[path_to_save] = editor
            
            # Update tab text
            index = self.main_window.editor_tabs.indexOf(editor)
            self.main_window.editor_tabs.setTabText(index, QFileInfo(path_to_save).fileName())

            self.main_window.statusBar().showMessage(f"Saved: {os.path.basename(path_to_save)}", 2000)
            self.main_window.python_console_output.appendPlainText(f"Saved: {os.path.basename(path_to_save)}")

            self.main_window.run_linter(path_to_save)
        except Exception as e:
            QMessageBox.critical(self.main_window, "Error", f"Could not save file: {e}")

    def save_all_files(self):
        for editor in self.main_window.open_files.values():
            if editor.document().isModified():
                path_to_save = None
                for path, e in self.main_window.open_files.items():
                    if e == editor:
                        path_to_save = path
                        break
                if path_to_save:
                    try:
                        with open(path_to_save, 'w', encoding='utf-8') as f:
                            f.write(editor.toPlainText())
                        editor.document().setModified(False)
                    except Exception as e:
                        QMessageBox.critical(self.main_window, "Error", f"Could not save file {path_to_save}: {e}")

    def close_current_editor(self):
        index = self.main_window.editor_tabs.currentIndex()
        if index != -1:
            self.main_window.close_editor_tab(index)

    def close_folder(self):
        self.main_window.tree_view.setRootIndex(self.main_window.proxy_model.mapFromSource(self.main_window.file_model.index(QDir.rootPath())))
        # Close all editor tabs
        for i in range(self.main_window.editor_tabs.count()):
            self.main_window.close_editor_tab(0)

    def add_to_recent_files(self, path):
        if path in self.main_window.recent_files:
            self.main_window.recent_files.remove(path)
        self.main_window.recent_files.insert(0, path)
        self.main_window.recent_files = self.main_window.recent_files[:15]  # Limit to 15 recent files
        self.save_settings()

    def save_settings(self):
        try:
            with open(self.main_window.settings_file, 'w') as f:
                settings_to_save = self.main_window.settings.copy()
                settings_to_save['recent_files'] = self.main_window.recent_files
                json.dump(settings_to_save, f, indent=4)
        except Exception as e:
            print(f"Error saving settings: {e}")