"""
Enhanced File Tree with keyboard shortcuts and undo/redo support.
Provides VS Code-like file operations with Ctrl+C, Ctrl+V, Delete, Ctrl+Z, Ctrl+Y.
"""

import os
import shutil
from PySide6.QtWidgets import QTreeView, QApplication, QMessageBox
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeySequence
from Details.dialogs import CustomMessageBox


class FileOperation:
    """Represents a file operation that can be undone/redone."""
    
    def __init__(self, op_type, data):
        """
        op_type: 'delete', 'rename', 'create', 'move', 'copy'
        data: dict with operation-specific info
        """
        self.op_type = op_type
        self.data = data
    
    def undo(self):
        """Undo this operation."""
        try:
            if self.op_type == 'delete':
                # Restore from backup
                if self.data.get('was_dir'):
                    shutil.copytree(self.data['backup_path'], self.data['original_path'])
                else:
                    shutil.copy2(self.data['backup_path'], self.data['original_path'])
                    
            elif self.op_type == 'rename':
                # Rename back
                os.rename(self.data['new_path'], self.data['old_path'])
                
            elif self.op_type == 'create':
                # Delete created item
                if os.path.isdir(self.data['path']):
                    shutil.rmtree(self.data['path'])
                else:
                    os.remove(self.data['path'])
                    
            elif self.op_type == 'move':
                # Move back
                shutil.move(self.data['dest_path'], self.data['src_path'])
                
            elif self.op_type == 'copy':
                # Delete the copy
                if os.path.isdir(self.data['dest_path']):
                    shutil.rmtree(self.data['dest_path'])
                else:
                    os.remove(self.data['dest_path'])
            
            return True
        except Exception as e:
            print(f"Undo failed: {e}")
            return False
    
    def redo(self):
        """Redo this operation."""
        try:
            if self.op_type == 'delete':
                # Delete again
                if os.path.isdir(self.data['original_path']):
                    shutil.rmtree(self.data['original_path'])
                else:
                    os.remove(self.data['original_path'])
                    
            elif self.op_type == 'rename':
                # Rename forward
                os.rename(self.data['old_path'], self.data['new_path'])
                
            elif self.op_type == 'create':
                # Create again
                if self.data.get('is_dir'):
                    os.makedirs(self.data['path'], exist_ok=True)
                else:
                    with open(self.data['path'], 'w') as f:
                        f.write(self.data.get('content', ''))
                        
            elif self.op_type == 'move':
                # Move forward
                shutil.move(self.data['src_path'], self.data['dest_path'])
                
            elif self.op_type == 'copy':
                # Copy again
                if self.data.get('is_dir'):
                    shutil.copytree(self.data['src_path'], self.data['dest_path'])
                else:
                    shutil.copy2(self.data['src_path'], self.data['dest_path'])
            
            return True
        except Exception as e:
            print(f"Redo failed: {e}")
            return False


class FileOperationHistory:
    """Manages undo/redo history for file operations."""
    
    def __init__(self, max_history=50):
        self.undo_stack = []
        self.redo_stack = []
        self.max_history = max_history
        self.temp_backup_dir = None
    
    def get_backup_dir(self):
        """Get or create temporary backup directory."""
        if not self.temp_backup_dir:
            import tempfile
            self.temp_backup_dir = tempfile.mkdtemp(prefix='file_tree_backup_')
        return self.temp_backup_dir
    
    def add_operation(self, operation):
        """Add an operation to the undo stack."""
        self.undo_stack.append(operation)
        # Clear redo stack when new operation is added
        self.redo_stack.clear()
        # Limit history size
        if len(self.undo_stack) > self.max_history:
            self.undo_stack.pop(0)
    
    def can_undo(self):
        """Check if undo is available."""
        return len(self.undo_stack) > 0
    
    def can_redo(self):
        """Check if redo is available."""
        return len(self.redo_stack) > 0
    
    def undo(self):
        """Undo the last operation."""
        if not self.can_undo():
            return False
        
        operation = self.undo_stack.pop()
        if operation.undo():
            self.redo_stack.append(operation)
            return True
        else:
            # If undo failed, put it back
            self.undo_stack.append(operation)
            return False
    
    def redo(self):
        """Redo the last undone operation."""
        if not self.can_redo():
            return False
        
        operation = self.redo_stack.pop()
        if operation.redo():
            self.undo_stack.append(operation)
            return True
        else:
            # If redo failed, put it back
            self.redo_stack.append(operation)
            return False
    
    def cleanup(self):
        """Clean up temporary backup directory."""
        if self.temp_backup_dir and os.path.exists(self.temp_backup_dir):
            try:
                shutil.rmtree(self.temp_backup_dir)
            except Exception:
                pass


class EnhancedFileTreeView(QTreeView):
    """
    Enhanced QTreeView with keyboard shortcuts for file operations.
    Supports: Ctrl+C (copy), Ctrl+V (paste), Delete, Ctrl+Z (undo), Ctrl+Y (redo)
    """
    
    # Signal emitted when tree needs refresh
    refresh_needed = Signal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.main_window = None
        self.file_model = None
        self.proxy_model = None
        
        # File operation history for undo/redo
        self.operation_history = FileOperationHistory()
        
        # Clipboard for copy/cut/paste
        self.file_clipboard = {'action': None, 'paths': []}
        
        # Set focus policy to ensure tree can receive keyboard input
        self.setFocusPolicy(Qt.StrongFocus)
        
        # Track if we have focus to show border like VS Code
        self._has_focus = False
    
    def set_models(self, main_window, file_model, proxy_model):
        """Set references to main window and models."""
        self.main_window = main_window
        self.file_model = file_model
        self.proxy_model = proxy_model
    
    def event(self, event):
        """Override event to intercept shortcuts before they reach parent widgets."""
        # Intercept ShortcutOverride events to claim shortcuts when tree has focus
        if event.type() == event.Type.ShortcutOverride:
            # Claim shortcuts when tree has focus (even without selection for undo/redo/paste)
            if self.hasFocus():
                if (event.matches(QKeySequence.Copy) or 
                    event.matches(QKeySequence.Cut) or 
                    event.matches(QKeySequence.Paste) or
                    event.matches(QKeySequence.Undo) or
                    event.matches(QKeySequence.Redo) or
                    event.matches(QKeySequence.Delete) or
                    event.key() == Qt.Key_Delete):
                    event.accept()
                    return True
        
        return super().event(event)
    
    def focusInEvent(self, event):
        """Handle focus in - show VS Code style border."""
        self._has_focus = True
        self.viewport().update()
        super().focusInEvent(event)
    
    def focusOutEvent(self, event):
        """Handle focus out - hide border."""
        self._has_focus = False
        self.viewport().update()
        super().focusOutEvent(event)
    
    def mousePressEvent(self, event):
        """Handle mouse press - ensure focus when clicking anywhere in tree."""
        # Set focus when clicking anywhere in the tree view
        if not self.hasFocus():
            self.setFocus(Qt.MouseFocusReason)
        super().mousePressEvent(event)
    
    def keyPressEvent(self, event):
        """Handle keyboard shortcuts for file operations."""
        # Handle undo/redo even without selection
        if event.matches(QKeySequence.Undo):  # Ctrl+Z
            event.accept()
            self.undo_operation()
            return
            
        elif event.matches(QKeySequence.Redo):  # Ctrl+Y or Ctrl+Shift+Z
            event.accept()
            self.redo_operation()
            return
        
        # Get selected items for other operations
        selected_indexes = self.selectedIndexes()
        
        # Handle paste even without selection (paste to root)
        if event.matches(QKeySequence.Paste):  # Ctrl+V
            event.accept()
            if selected_indexes:
                # Get first selected item
                selected_paths = []
                for idx in selected_indexes:
                    if idx.column() == 0:
                        source_idx = self.proxy_model.mapToSource(idx)
                        path = self.file_model.filePath(source_idx)
                        if path and path not in selected_paths:
                            selected_paths.append(path)
                if selected_paths:
                    self.paste_files(selected_paths[0])
            else:
                # Paste to root directory
                root_idx = self.rootIndex()
                if root_idx.isValid():
                    source_idx = self.proxy_model.mapToSource(root_idx)
                    root_path = self.file_model.filePath(source_idx)
                    if root_path:
                        self.paste_files(root_path)
            return
        
        # For copy/cut/delete, we need selection
        if not selected_indexes:
            super().keyPressEvent(event)
            return
        
        # Get first selected item (column 0 only)
        selected_paths = []
        for idx in selected_indexes:
            if idx.column() == 0:  # Only process first column
                source_idx = self.proxy_model.mapToSource(idx)
                path = self.file_model.filePath(source_idx)
                if path and path not in selected_paths:
                    selected_paths.append(path)
        
        if not selected_paths:
            super().keyPressEvent(event)
            return
        
        # Handle keyboard shortcuts - accept and stop propagation
        if event.matches(QKeySequence.Copy):  # Ctrl+C
            event.accept()
            self.copy_files(selected_paths)
            return
            
        elif event.matches(QKeySequence.Cut):  # Ctrl+X
            event.accept()
            self.cut_files(selected_paths)
            return
            
        elif event.matches(QKeySequence.Delete) or event.key() == Qt.Key_Delete:  # Delete
            event.accept()
            self.delete_files(selected_paths)
            return
        
        # Pass other keys to parent
        super().keyPressEvent(event)
    
    def copy_files(self, paths):
        """Copy files to clipboard."""
        self.file_clipboard = {'action': 'copy', 'paths': paths}
        count = len(paths)
        if self.main_window:
            self.main_window.statusBar().showMessage(f"Copied {count} item{'s' if count > 1 else ''}", 2000)
    
    def cut_files(self, paths):
        """Cut files to clipboard."""
        self.file_clipboard = {'action': 'cut', 'paths': paths}
        count = len(paths)
        if self.main_window:
            self.main_window.statusBar().showMessage(f"Cut {count} item{'s' if count > 1 else ''}", 2000)
    
    def paste_files(self, target_path):
        """Paste files from clipboard."""
        if not self.file_clipboard['paths']:
            return
        
        # Determine target directory
        if os.path.isdir(target_path):
            target_dir = target_path
        else:
            target_dir = os.path.dirname(target_path)
        
        action = self.file_clipboard['action']
        pasted_count = 0
        
        for src_path in self.file_clipboard['paths']:
            if not os.path.exists(src_path):
                continue
            
            base_name = os.path.basename(src_path)
            dest_path = os.path.join(target_dir, base_name)
            
            # Handle name conflicts
            if os.path.exists(dest_path):
                dest_path = self.get_unique_name(dest_path)
            
            try:
                if action == 'copy':
                    # Copy operation
                    if os.path.isdir(src_path):
                        shutil.copytree(src_path, dest_path)
                    else:
                        shutil.copy2(src_path, dest_path)
                    
                    # Add to undo history
                    op = FileOperation('copy', {
                        'src_path': src_path,
                        'dest_path': dest_path,
                        'is_dir': os.path.isdir(dest_path)
                    })
                    self.operation_history.add_operation(op)
                    pasted_count += 1
                    
                elif action == 'cut':
                    # Move operation
                    shutil.move(src_path, dest_path)
                    
                    # Add to undo history
                    op = FileOperation('move', {
                        'src_path': src_path,
                        'dest_path': dest_path
                    })
                    self.operation_history.add_operation(op)
                    pasted_count += 1
                    
            except Exception as e:
                if self.main_window:
                    QMessageBox.warning(self.main_window, "Paste Error", f"Failed to paste '{base_name}':\n{str(e)}")
        
        # Clear clipboard after cut operation
        if action == 'cut':
            self.file_clipboard = {'action': None, 'paths': []}
        
        if self.main_window and pasted_count > 0:
            self.main_window.statusBar().showMessage(f"Pasted {pasted_count} item{'s' if pasted_count > 1 else ''}", 2000)
        
        # Refresh view
        self.refresh_needed.emit()
        self.viewport().update()
    
    def delete_files(self, paths):
        """Delete files with confirmation dialog."""
        if not paths:
            return
        
        # Show custom confirmation dialog
        count = len(paths)
        if count == 1:
            item_name = os.path.basename(paths[0])
            message = f"Are you sure you want to delete '<b>{item_name}</b>'?<br><br>This action cannot be undone."
        else:
            message = f"Are you sure you want to delete <b>{count} items</b>?<br><br>This action cannot be undone."
        
        confirm = CustomMessageBox.question(
            self.main_window,
            "Confirm Delete",
            message
        )
        
        if confirm != QMessageBox.Yes:
            return
        
        deleted_count = 0
        backup_dir = self.operation_history.get_backup_dir()
        
        for path in paths:
            if not os.path.exists(path):
                continue
            
            try:
                # Create backup for undo
                backup_name = f"backup_{os.path.basename(path)}_{deleted_count}"
                backup_path = os.path.join(backup_dir, backup_name)
                
                is_dir = os.path.isdir(path)
                
                # Backup before delete
                if is_dir:
                    shutil.copytree(path, backup_path)
                else:
                    shutil.copy2(path, backup_path)
                
                # Close editor tabs for deleted files (VS Code behavior)
                if self.main_window:
                    # Normalize paths for comparison
                    norm_path = os.path.abspath(path)
                    
                    if is_dir:
                        # Close all tabs for files inside this directory
                        tabs_to_close = []
                        for file_path, editor in list(self.main_window.open_files.items()):
                            norm_file_path = os.path.abspath(file_path)
                            # Check if file is inside the deleted directory
                            if norm_file_path.startswith(norm_path + os.sep) or norm_file_path == norm_path:
                                tabs_to_close.append(editor)
                        
                        # Close the tabs
                        for editor in tabs_to_close:
                            self.main_window.close_editor_by_widget(editor)
                    else:
                        # Close tab for this specific file
                        editor = self.main_window.open_files.get(norm_path)
                        if editor:
                            self.main_window.close_editor_by_widget(editor)
                
                # Delete
                if is_dir:
                    shutil.rmtree(path)
                else:
                    os.remove(path)
                
                # Add to undo history
                op = FileOperation('delete', {
                    'original_path': path,
                    'backup_path': backup_path,
                    'was_dir': is_dir
                })
                self.operation_history.add_operation(op)
                deleted_count += 1
                
            except Exception as e:
                if self.main_window:
                    QMessageBox.warning(self.main_window, "Delete Error", f"Failed to delete '{os.path.basename(path)}':\n{str(e)}")
        
        if self.main_window and deleted_count > 0:
            self.main_window.statusBar().showMessage(f"Deleted {deleted_count} item{'s' if deleted_count > 1 else ''}", 2000)
        
        # Refresh view
        self.refresh_needed.emit()
        self.viewport().update()
    
    def undo_operation(self):
        """Undo the last file operation."""
        if not self.operation_history.can_undo():
            if self.main_window:
                self.main_window.statusBar().showMessage("Nothing to undo", 2000)
            return
        
        if self.operation_history.undo():
            if self.main_window:
                self.main_window.statusBar().showMessage("Undo successful", 2000)
            self.refresh_needed.emit()
            self.viewport().update()
        else:
            if self.main_window:
                QMessageBox.warning(self.main_window, "Undo Failed", "Could not undo the last operation.")
    
    def redo_operation(self):
        """Redo the last undone file operation."""
        if not self.operation_history.can_redo():
            if self.main_window:
                self.main_window.statusBar().showMessage("Nothing to redo", 2000)
            return
        
        if self.operation_history.redo():
            if self.main_window:
                self.main_window.statusBar().showMessage("Redo successful", 2000)
            self.refresh_needed.emit()
            self.viewport().update()
        else:
            if self.main_window:
                QMessageBox.warning(self.main_window, "Redo Failed", "Could not redo the operation.")
    
    def get_unique_name(self, path):
        """Generate a unique name for a file/folder to avoid conflicts."""
        directory = os.path.dirname(path)
        base = os.path.basename(path)
        name, ext = os.path.splitext(base)
        counter = 1
        
        while True:
            if counter == 1:
                candidate = os.path.join(directory, f"{name} - Copy{ext}")
            else:
                candidate = os.path.join(directory, f"{name} - Copy ({counter}){ext}")
            
            if not os.path.exists(candidate):
                return candidate
            counter += 1
    
    def cleanup(self):
        """Clean up resources (call on app exit)."""
        self.operation_history.cleanup()
