
import os
import re
from PySide6.QtCore import Qt, QRect, QPoint
from PySide6.QtWidgets import QMessageBox, QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QWidget
from PySide6.QtGui import QTextCursor

class CustomTitleBar(QWidget):
    """Custom title bar for replace confirmation dialog"""
    def __init__(self, title, parent):
        super().__init__(parent)
        self.parent_dialog = parent
        self.setFixedHeight(35)
        self.m_old_pos = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 0, 5, 0)
        layout.setSpacing(10)

        self.title_label = QLabel(title, self)
        self.title_label.setStyleSheet("color: #BDC1C6; font-size: 14px; font-weight: bold; border: none;")
        layout.addWidget(self.title_label)

        layout.addStretch()

        self.close_button = QPushButton("✕", self)
        self.close_button.setFixedSize(30, 30)
        self.close_button.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #BDC1C6;
                border: none;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #E81123;
                color: white;
            }
        """)
        self.close_button.clicked.connect(self.parent_dialog.reject)
        layout.addWidget(self.close_button)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.m_old_pos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event):
        if self.m_old_pos is not None:
            delta = event.globalPosition().toPoint() - self.m_old_pos
            self.parent_dialog.move(self.parent_dialog.x() + delta.x(), self.parent_dialog.y() + delta.y())
            self.m_old_pos = event.globalPosition().toPoint()

    def mouseReleaseEvent(self, event):
        self.m_old_pos = None

class ReplaceConfirmDialog(QDialog):
    """Custom confirmation dialog for replace operations"""
    def __init__(self, title, text, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setStyleSheet("background-color: transparent;")
        self.setFixedWidth(450)

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)

        self.container = QWidget()
        self.container.setStyleSheet("""
            QWidget {
                background-color: #1E1E1E;
                border: 1px solid #4A4D51;
                border-radius: 8px;
            }
        """)
        self.main_layout.addWidget(self.container)
        
        container_layout = QVBoxLayout(self.container)
        container_layout.setContentsMargins(1, 1, 1, 1)
        container_layout.setSpacing(0)

        # Custom Title Bar
        self.title_bar = CustomTitleBar(title, self)
        container_layout.addWidget(self.title_bar)

        # Content
        content_layout = QVBoxLayout()
        content_layout.setContentsMargins(20, 20, 20, 20)
        content_layout.setSpacing(15)
        container_layout.addLayout(content_layout)

        # Message text
        self.label = QLabel(text, self)
        self.label.setStyleSheet("color: #E0E2E6; font-size: 14px; border: none;")
        self.label.setWordWrap(True)
        content_layout.addWidget(self.label)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.setContentsMargins(0, 10, 0, 0)
        button_layout.addStretch()
        content_layout.addLayout(button_layout)

        self.yes_button = QPushButton("Yes", self)
        self.no_button = QPushButton("No", self)
        
        for btn in [self.yes_button, self.no_button]:
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #3C4043;
                    color: #E0E2E6;
                    border: 1px solid #4A4D51;
                    border-radius: 4px;
                    padding: 8px 20px;
                    min-width: 60px;
                }
                QPushButton:hover {
                    background-color: #4A4D51;
                }
                QPushButton:pressed {
                    background-color: #5A5D61;
                }
            """)
            button_layout.addWidget(btn)

        self.yes_button.clicked.connect(self.accept)
        self.no_button.clicked.connect(self.reject)

    @staticmethod
    def question(parent, title, text):
        dialog = ReplaceConfirmDialog(title, text, parent)
        if dialog.exec() == QDialog.Accepted:
            return QMessageBox.Yes
        return QMessageBox.No

def show_replace_preview(self):
    """Show replace preview for current selection"""
    # Auto-select first result if nothing is selected
    if not self.current_preview_item or self.current_preview_item.kind != 'match' or not self.current_preview_item.line_num:
        if not self._select_first_result():
            return
        
    replace_text = self.replace_input.text()
    search_text = self.search_input.text()
    
    self.replace_preview.show_preview(
        self.current_preview_item.file_path,
        self.current_preview_item.line_num,
        self.current_preview_item.line_text or "",
        search_text,
        replace_text
    )
    
    self.replace_preview.setVisible(True)
    self.splitter.setSizes([self.height() // 2, self.height() // 2])
    
def hide_replace_preview(self):
    """Hide replace preview"""
    self.replace_preview.setVisible(False)
    
def replace_current(self):
    """Replace the current selected match"""
    if not self.current_preview_item or self.current_preview_item.kind != 'match' or not self.current_preview_item.line_num:
        return
        
    try:
        file_path = self.current_preview_item.file_path
        line_num = self.current_preview_item.line_num
        search_text = self.search_input.text()
        replace_text = self.replace_input.text()
        
        if not search_text:
            QMessageBox.information(self, "Replace", "No search text specified")
            return
        
        # Read file
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        # Replace in the specific line (first occurrence only)
        if 0 <= line_num - 1 < len(lines):
            original_line = lines[line_num - 1]
            # Use regex pattern for replacement to match search behavior
            pattern = self._compile_replace_pattern()
            if pattern:
                lines[line_num - 1] = pattern.sub(replace_text, original_line, count=1)
            else:
                lines[line_num - 1] = original_line.replace(search_text, replace_text, 1)
            
            # Write back
            with open(file_path, 'w', encoding='utf-8') as f:
                f.writelines(lines)
            
            # Reload the file in the editor if it's open, keeping the replaced line visible
            self._reload_file_in_editor(file_path, keep_line_visible=line_num)
            
            self.status_label.setText(f"Replaced in {os.path.basename(file_path)}")
            
            # Remove this result from tree
            parent = self.current_preview_item.parent()
            if parent:
                parent.removeChild(self.current_preview_item)
                # Update per-file count
                self.per_file_counts[file_path] = max(0, self.per_file_counts.get(file_path, 1) - 1)
                if isinstance(parent, SearchResultItem) and parent.kind == 'file':
                    self._update_file_item_text(parent)
            
            self.hide_replace_preview()
            
    except Exception as e:
        QMessageBox.critical(self, "Replace Error", f"Failed to replace: {e}")
        import traceback
        traceback.print_exc()

def _compile_replace_pattern(self):
    """Compile the search pattern for replacement"""
    text = self.search_input.text()
    if not text:
        return None
    try:
        if self.regex_cb.isChecked():
            flags = 0 if self.case_sensitive_cb.isChecked() else re.IGNORECASE
            return re.compile(text, flags)
        else:
            escaped = re.escape(text)
            if self.whole_word_cb.isChecked():
                escaped = r'\b' + escaped + r'\b'
            flags = 0 if self.case_sensitive_cb.isChecked() else re.IGNORECASE
            return re.compile(escaped, flags)
    except re.error:
        return None

def _reload_file_in_editor(self, file_path, keep_line_visible=None):
    """Reload a file in the editor if it's currently open
    
    Args:
        file_path: Path to the file to reload
        keep_line_visible: Line number to keep visible after reload (1-based)
    """
    try:
        # Normalize the file path for comparison
        file_path = os.path.abspath(file_path)
        
        # Get the main window through parent chain
        main_window = None
        parent = self.parent()
        while parent:
            if hasattr(parent, 'open_files') and hasattr(parent, 'editor_tabs'):
                main_window = parent
                break
            parent = parent.parent()
        
        if not main_window:
            return
        
        # Check if file is open (normalize paths for comparison)
        editor = None
        for open_path, open_editor in main_window.open_files.items():
            if os.path.abspath(open_path) == file_path:
                editor = open_editor
                break
        
        if not editor:
            return
        
        # Save scroll position and cursor
        scrollbar = editor.verticalScrollBar()
        scroll_value = scrollbar.value()
        cursor = editor.textCursor()
        position = cursor.position()
        
        # Reload file content
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            new_content = f.read()
        
        # Block signals to prevent triggering modification events
        editor.blockSignals(True)
        
        # Update editor content
        editor.setPlainText(new_content)
        
        # Restore cursor position and scroll
        if keep_line_visible is not None:
            # Move to the specific line and center it
            block = editor.document().findBlockByLineNumber(keep_line_visible - 1)
            if block.isValid():
                cursor = QTextCursor(block)
                cursor.movePosition(QTextCursor.StartOfBlock)
                editor.setTextCursor(cursor)
                editor.centerCursor()
        else:
            # Restore original position
            if position <= len(new_content):
                cursor.setPosition(min(position, len(new_content)))
                editor.setTextCursor(cursor)
            # Restore scroll position
            scrollbar.setValue(scroll_value)
        
        # Mark as unmodified since we just loaded from disk
        editor.document().setModified(False)
        
        # Re-enable signals
        editor.blockSignals(False)
        
        # Force a repaint
        editor.viewport().update()
        
    except Exception as e:
        # Print error for debugging
        import traceback
        print(f"Error reloading file in editor: {e}")
        traceback.print_exc()
        
def replace_all(self):
    """Replace all matches"""
    total_to_replace = sum(self.per_file_counts.values())
    if total_to_replace <= 0:
        QMessageBox.information(self, "Replace All", "No matches to replace")
        return
    
    # Use custom confirmation dialog
    reply = ReplaceConfirmDialog.question(
        self,
        "Replace All",
        f"Replace all {total_to_replace} occurrences?"
    )
    
    if reply != QMessageBox.Yes:
        return
        
    try:
        search_text = self.search_input.text()
        replace_text = self.replace_input.text()
        replaced_count = 0
        
        # Compile the pattern once for all files
        pattern = self._compile_replace_pattern()
        
        modified_files = []
        for file_path in list(self.search_results.keys()):
            # Read file
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Replace all occurrences using regex pattern (respects search options)
            if pattern:
                new_content = pattern.sub(replace_text, content)
            else:
                # Fallback to literal replace
                new_content = content.replace(search_text, replace_text)
            
            # Write back if changed
            if new_content != content:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                replaced_count += self.per_file_counts.get(file_path, 0)
                modified_files.append(file_path)
        
        # Reload all modified files in the editor
        for file_path in modified_files:
            self._reload_file_in_editor(file_path)
        
        self.status_label.setText(f"Replaced {replaced_count} occurrences in {len(modified_files)} file(s)")
        
        # Clear results
        self._reset_results_view()
        self.hide_replace_preview()
        
    except Exception as e:
        QMessageBox.critical(self, "Replace All Error", f"Failed to replace: {e}")
        import traceback
        traceback.print_exc()

def replace_all_in_file(self, file_path):
    """Replace all matches in a specific file"""
    if not file_path or file_path not in self.search_results:
        return
    
    count_in_file = self.per_file_counts.get(file_path, 0)
    if count_in_file <= 0:
        return
    
    # Use custom confirmation dialog
    reply = ReplaceConfirmDialog.question(
        self,
        "Replace All in File",
        f"Replace all {count_in_file} occurrences in {os.path.basename(file_path)}?"
    )
    
    if reply != QMessageBox.Yes:
        return
    
    try:
        search_text = self.search_input.text()
        replace_text = self.replace_input.text()
        
        # Compile the pattern
        pattern = self._compile_replace_pattern()
        
        # Read file
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Replace all occurrences
        if pattern:
            new_content = pattern.sub(replace_text, content)
        else:
            new_content = content.replace(search_text, replace_text)
        
        # Write back if changed
        if new_content != content:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            
            # Reload file in editor
            self._reload_file_in_editor(file_path)
            
            self.status_label.setText(f"Replaced {count_in_file} occurrences in {os.path.basename(file_path)}")
            
            # Remove all results for this file from tree
            for i in range(self.results_tree.topLevelItemCount()):
                item = self.results_tree.topLevelItem(i)
                if hasattr(item, 'file_path') and item.file_path == file_path:
                    self.results_tree.takeTopLevelItem(i)
                    break
            
            # Update counts
            if file_path in self.per_file_counts:
                del self.per_file_counts[file_path]
            if file_path in self.search_results:
                del self.search_results[file_path]
            
            # Update summary
            total_matches = sum(self.per_file_counts.values())
            file_count = len(self.per_file_counts)
            if total_matches > 0:
                self.summary_label.setText(f"{total_matches} result{'s' if total_matches != 1 else ''} in {file_count} file{'s' if file_count != 1 else ''}")
            else:
                self.summary_label.setVisible(False)
                self.status_label.setText("No results")
        
    except Exception as e:
        QMessageBox.critical(self, "Replace Error", f"Failed to replace: {e}")
        import traceback
        traceback.print_exc()

def replace_single_match(self, item):
    """Replace a single match item instantly (like VS Code)"""
    if not item or not hasattr(item, 'kind') or item.kind != 'match':
        return
    
    if not item.line_num or not item.file_path:
        return
    
    try:
        file_path = item.file_path
        line_num = item.line_num
        search_text = self.search_input.text()
        replace_text = self.replace_input.text()
        
        if not search_text:
            return
        
        # Read file
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        # Replace in the specific line (first occurrence only)
        if 0 <= line_num - 1 < len(lines):
            original_line = lines[line_num - 1]
            # Use regex pattern for replacement to match search behavior
            pattern = self._compile_replace_pattern()
            if pattern:
                lines[line_num - 1] = pattern.sub(replace_text, original_line, count=1)
            else:
                lines[line_num - 1] = original_line.replace(search_text, replace_text, 1)
            
            # Write back
            with open(file_path, 'w', encoding='utf-8') as f:
                f.writelines(lines)
            
            # Reload the file in the editor if it's open, keeping the replaced line visible
            self._reload_file_in_editor(file_path, keep_line_visible=line_num)
            
            self.status_label.setText(f"Replaced in {os.path.basename(file_path)}")
            
            # Remove this result from tree
            parent = item.parent()
            if parent:
                parent.removeChild(item)
                # Update per-file count
                self.per_file_counts[file_path] = max(0, self.per_file_counts.get(file_path, 1) - 1)
                
                # If no more results for this file, remove the file item
                if self.per_file_counts[file_path] == 0:
                    index = self.results_tree.indexOfTopLevelItem(parent)
                    if index >= 0:
                        self.results_tree.takeTopLevelItem(index)
                    del self.per_file_counts[file_path]
                    if file_path in self.search_results:
                        del self.search_results[file_path]
                else:
                    # Update file item text
                    if hasattr(parent, 'kind') and parent.kind == 'file':
                        self._update_file_item_text(parent)
                
                # Update summary
                total_matches = sum(self.per_file_counts.values())
                file_count = len(self.per_file_counts)
                if total_matches > 0:
                    self.summary_label.setText(f"{total_matches} result{'s' if total_matches != 1 else ''} in {file_count} file{'s' if file_count != 1 else ''}")
                else:
                    self.summary_label.setVisible(False)
                    self.status_label.setText("No results")
            
    except Exception as e:
        QMessageBox.critical(self, "Replace Error", f"Failed to replace: {e}")
        import traceback
        traceback.print_exc()


