from PySide6.QtWidgets import QMenu, QApplication
from PySide6.QtGui import QKeySequence, QTextCursor
from Details.dialogs import CustomMessageBox


def default_menu_stylesheet() -> str:
    """Return the default stylesheet for context menus to match app theme."""
    return (
        """
        QMenu {
            background: #282A2E;
            color: #FFFFFF;
            font-size: 13px;
            border: 1px solid #4A4D51;
            border-radius: 4px;
            min-width: 260px;
        }
        QMenu::item { padding: 8px 24px; }
        /* Ensure the hover/selected background stretches the full menu width */
        QMenu::item:selected {
            background-color: #4A4D51;
            color: #FFFFFF;
            margin-left: 0px;
            margin-right: 0px;
        }
        QMenu::separator { height: 1px; background-color: #4A4D51; margin: 6px 1px; }
        """
    )


essential_menu_stylesheet = default_menu_stylesheet


def apply_default_menu_style(menu: QMenu) -> None:
    """Apply the default stylesheet to a given QMenu."""
    menu.setStyleSheet(default_menu_stylesheet())


def build_editor_context_menu(editor) -> QMenu:
    """Create a standard editor context menu with consistent styling.
    Includes Undo, Redo, Cut, Copy, Paste, Delete, and Select All.
    """
    menu = QMenu(editor)
    apply_default_menu_style(menu)

    # Undo / Redo
    act_undo = menu.addAction("Undo")
    act_undo.setShortcut(QKeySequence.Undo)
    act_undo.triggered.connect(editor.undo)
    try:
        act_undo.setEnabled(editor.canUndo())
    except Exception:
        pass

    act_redo = menu.addAction("Redo")
    act_redo.setShortcut(QKeySequence.Redo)
    act_redo.triggered.connect(editor.redo)
    try:
        act_redo.setEnabled(editor.canRedo())
    except Exception:
        pass

    menu.addSeparator()

    # Cut / Copy / Paste
    act_cut = menu.addAction("Cut")
    act_cut.setShortcut(QKeySequence.Cut)
    act_cut.triggered.connect(editor.cut)

    act_copy = menu.addAction("Copy")
    act_copy.setShortcut(QKeySequence.Copy)
    act_copy.triggered.connect(editor.copy)

    act_paste = menu.addAction("Paste")
    act_paste.setShortcut(QKeySequence.Paste)
    act_paste.triggered.connect(editor.paste)

    selection = editor.textCursor().hasSelection()
    read_only = editor.isReadOnly()

    act_cut.setEnabled(selection and not read_only)
    act_copy.setEnabled(selection)

    try:
        can_paste = (not read_only) and bool(QApplication.clipboard().text())
        act_paste.setEnabled(can_paste)
    except Exception:
        pass

    # Delete
    act_delete = menu.addAction("Delete")
    act_delete.setShortcut(QKeySequence.Delete)

    def do_delete():
        cur = editor.textCursor()
        if cur.hasSelection():
            cur.removeSelectedText()
        else:
            cur.movePosition(QTextCursor.Right, QTextCursor.KeepAnchor, 1)
            if cur.hasSelection():
                cur.removeSelectedText()
        editor.setTextCursor(cur)

    act_delete.triggered.connect(do_delete)
    act_delete.setEnabled(not read_only)

    menu.addSeparator()

    # Select All
    act_select_all = menu.addAction("Select All")
    act_select_all.setShortcut(QKeySequence.SelectAll)
    act_select_all.triggered.connect(editor.selectAll)

    menu.addSeparator()

    # Format with rustfmt
    act_format = menu.addAction("Format")
    act_format.setShortcut("Shift+Alt+F")
    
    def format_code():
        """Format the current Rust file using rustfmt."""
        try:
            # Get the main window to access current file path
            main_window = editor.window()
            if not hasattr(main_window, 'current_file_path') or not main_window.current_file_path:
                CustomMessageBox.information(
                    editor, 
                    "Format", 
                    "No file is currently open.<br><br>Save the file first to format it."
                )
                return
            
            import os
            file_path = main_window.current_file_path
            
            # Check if it's a Rust file
            if not file_path.lower().endswith('.rs'):
                CustomMessageBox.information(
                    editor, 
                    "Format", 
                    "Format is only available for Rust files (.rs)"
                )
                return
            
            # Save the file first
            if editor.document().isModified():
                main_window.save_file()
            
            # Run rustfmt
            import subprocess
            try:
                result = subprocess.run(
                    ['rustfmt', file_path],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                
                if result.returncode == 0:
                    # Reload the formatted file
                    with open(file_path, 'r', encoding='utf-8') as f:
                        formatted_content = f.read()
                    
                    # Save cursor position
                    cursor = editor.textCursor()
                    position = cursor.position()
                    
                    # Update editor content
                    editor.blockSignals(True)
                    editor.setPlainText(formatted_content)
                    editor.document().setModified(False)
                    editor.blockSignals(False)
                    
                    # Restore cursor position (or close to it)
                    cursor.setPosition(min(position, len(formatted_content)))
                    editor.setTextCursor(cursor)
                    
                    # Invalidate caches to force redraw of indentation guide lines
                    try:
                        if hasattr(editor, '_invalidate_scope_cache'):
                            editor._invalidate_scope_cache()
                        if hasattr(editor, '_invalidate_brace_cache'):
                            editor._invalidate_brace_cache()
                    except Exception as e:
                        print(f"Error invalidating caches: {e}")
                    
                    # Update code folding after formatting
                    try:
                        if hasattr(editor, 'rust_autocorrect'):
                            autocorrect = editor.rust_autocorrect
                            if hasattr(autocorrect, 'update_folding'):
                                autocorrect.update_folding()
                    except Exception as e:
                        print(f"Error updating folding: {e}")
                    
                    # Force viewport update to redraw guide lines
                    try:
                        editor.viewport().update()
                    except Exception:
                        pass
                    
                    # Show success message
                    main_window.statusBar().showMessage("File formatted successfully with rustfmt", 3000)
                else:
                    error_msg = result.stderr if result.stderr else "Unknown error"
                    # Parse error message to extract line number and details
                    error_lines = error_msg.strip().split('\n')
                    
                    # Try to find the main error line (usually starts with "error:")
                    main_error = ""
                    error_location = ""
                    error_details = []
                    
                    for line in error_lines:
                        if line.strip().startswith('error:'):
                            main_error = line.strip()
                        elif '-->' in line:
                            # This is the location line (e.g., "--> src/main.rs:5:10")
                            error_location = line.strip()
                        elif line.strip() and not line.startswith('error:') and not line.startswith('warning:'):
                            error_details.append(line)
                    
                    # Build formatted message
                    if main_error:
                        error_html = f"<p style='font-size: 13px; text-align: left;'><b style='color: #FF6B6B;'>Format Error:</b></p>"
                        error_html += f"<p style='font-size: 12px; color: #E0E2E6; text-align: left; margin-top: 10px;'>{main_error}</p>"
                        
                        if error_location:
                            # Highlight the file location
                            error_html += f"<p style='font-family: Consolas, monospace; font-size: 12px; color: #4EC9B0; text-align: left; margin-top: 5px;'>{error_location}</p>"
                        
                        if error_details:
                            details_text = '<br>'.join(error_details[:5])  # Show first 5 detail lines
                            error_html += f"<p style='font-family: Consolas, monospace; font-size: 11px; color: #BDC1C6; background-color: #1E1F22; padding: 10px; border-radius: 4px; margin-top: 10px; text-align: left; white-space: pre-wrap;'>{details_text}</p>"
                    else:
                        # Fallback: show raw error
                        formatted_error = '<br>'.join(error_lines[:10])
                        error_html = f"<p style='font-size: 13px; text-align: left;'><b style='color: #FF6B6B;'>rustfmt failed:</b></p>"
                        error_html += f"<p style='font-family: Consolas, monospace; font-size: 11px; color: #BDC1C6; background-color: #1E1F22; padding: 10px; border-radius: 4px; margin-top: 10px; text-align: left; white-space: pre-wrap;'>{formatted_error}</p>"
                    
                    CustomMessageBox.information(editor, "Format Error", error_html)
            
            except FileNotFoundError:
                CustomMessageBox.information(
                    editor, 
                    "rustfmt Not Found", 
                    "<p style='font-size: 13px;'><b style='color: #FFA500;'>rustfmt is not installed</b></p>"
                    "<p style='font-size: 13px; margin-top: 10px;'>rustfmt is not found in your system PATH.</p>"
                    "<p style='font-size: 13px; margin-top: 15px;'><b>To install rustfmt:</b></p>"
                    "<p style='font-family: Consolas, monospace; font-size: 12px; color: #4EC9B0; "
                    "background-color: #1E1F22; padding: 10px; border-radius: 4px; margin-top: 5px;'>"
                    "rustup component add rustfmt</p>"
                )
            except subprocess.TimeoutExpired:
                CustomMessageBox.information(
                    editor, 
                    "Format Timeout", 
                    "<p style='font-size: 13px;'><b style='color: #FFA500;'>Format operation timed out</b></p>"
                    "<p style='font-size: 13px; margin-top: 10px;'>rustfmt took too long to complete (>10 seconds).</p>"
                    "<p style='font-size: 13px; margin-top: 10px;'>This might happen with very large files.</p>"
                )
            except Exception as e:
                error_text = str(e).replace('\n', '<br>')
                CustomMessageBox.information(
                    editor, 
                    "Format Error", 
                    f"<p style='font-size: 13px;'><b style='color: #FF6B6B;'>Error formatting file</b></p>"
                    f"<p style='font-family: Consolas, monospace; font-size: 12px; color: #BDC1C6; "
                    f"background-color: #1E1F22; padding: 10px; border-radius: 4px; margin-top: 10px;'>"
                    f"{error_text}</p>"
                )
        
        except Exception as e:
            error_text = str(e).replace('\n', '<br>')
            CustomMessageBox.information(
                editor, 
                "Format Error", 
                f"<p style='font-size: 13px;'><b style='color: #FF6B6B;'>Unexpected error occurred</b></p>"
                f"<p style='font-family: Consolas, monospace; font-size: 12px; color: #BDC1C6; "
                f"background-color: #1E1F22; padding: 10px; border-radius: 4px; margin-top: 10px;'>"
                f"{error_text}</p>"
            )
    
    act_format.triggered.connect(format_code)
    act_format.setEnabled(not read_only)

    return menu


def show_file_tree_context_menu(main_window, position):
    """Build and handle the file tree context menu, centralized here.
    This mirrors VS Code-like actions and uses main_window's managers.
    """
    import os
    import shutil
    import subprocess
    from PySide6.QtCore import QProcess
    from PySide6.QtWidgets import QMessageBox, QMenu
    from Details.dialogs import CustomInputDialog, CustomMessageBox

    tree_view = main_window.tree_view
    file_model = main_window.file_model
    proxy_model = main_window.proxy_model

    # Resolve clicked index and path
    view_index = tree_view.indexAt(position)
    if view_index.isValid():
        source_index = proxy_model.mapToSource(view_index)
    else:
        # Use current root when clicking on empty area
        source_index = proxy_model.mapToSource(tree_view.rootIndex())
    path = file_model.filePath(source_index)
    is_dir = True if not view_index.isValid() else file_model.isDir(source_index)

    # Helpers
    def target_dir_for(p, is_directory):
        return p if is_directory else os.path.dirname(p)

    def unique_name(p):
        directory = os.path.dirname(p)
        base = os.path.basename(p)
        name, ext = os.path.splitext(base)
        counter = 1
        while True:
            candidate = os.path.join(directory, f"{name} - Copy{'' if counter == 1 else f' ({counter})'}{ext}")
            if not os.path.exists(candidate):
                return candidate
            counter += 1

    # Build context menu with styling consistent with header menus
    menu = QMenu(main_window)
    apply_default_menu_style(menu)

    # Action group: creation/open
    act_new_file = menu.addAction("New File")
    act_new_folder = menu.addAction("New Folder")
    act_open = menu.addAction("Open")
    act_reveal = menu.addAction("Reveal in File Explorer")
    act_open_default = menu.addAction("Open with Default App")
    act_open_terminal = menu.addAction("Open in Integrated Terminal")

    menu.addSeparator()

    # Action group: clipboard
    act_copy = menu.addAction("Copy")
    act_cut = menu.addAction("Cut")
    act_paste = menu.addAction("Paste")
    act_copy_path = menu.addAction("Copy Path")
    act_copy_rel = menu.addAction("Copy Relative Path")
    act_duplicate = menu.addAction("Duplicate")

    menu.addSeparator()

    # Action group: edit
    act_rename = menu.addAction("Rename")
    act_delete = menu.addAction("Delete")

    # Python run actions removed for Rust-focused editor

    # Disable context-sensitive actions when clicking empty space
    if not view_index.isValid():
        act_open.setEnabled(False)
        act_open_default.setEnabled(False)
        act_duplicate.setEnabled(False)
        act_rename.setEnabled(False)
        act_delete.setEnabled(False)

    # Init clipboard storage if needed
    if not hasattr(main_window, 'file_clipboard'):
        main_window.file_clipboard = {'action': None, 'paths': []}

    # Disable paste when clipboard empty
    if not main_window.file_clipboard['paths']:
        act_paste.setEnabled(False)

    # Execute
    global_pos = tree_view.viewport().mapToGlobal(position)
    chosen = menu.exec(global_pos)
    if not chosen:
        return

    # Target directory for operations
    target_dir = target_dir_for(path, is_dir)

    try:
        if chosen == act_new_file:
            # Reuse existing manager (handles base_path dir/file smartly)
            main_window.create_new_file(base_path=target_dir)

        elif chosen == act_new_folder:
            folder_name, ok = CustomInputDialog.getText(main_window, "New Folder", "Enter folder name")
            if ok and folder_name:
                new_dir = os.path.abspath(os.path.join(target_dir, folder_name))
                if not os.path.exists(new_dir):
                    os.makedirs(new_dir, exist_ok=True)
                else:
                    QMessageBox.warning(main_window, "Warning", "Folder already exists.")

        elif chosen == act_open:
            if os.path.isdir(path):
                tree_view.setRootIndex(proxy_model.mapFromSource(file_model.index(path)))
            else:
                main_window.file_ops.open_file_for_editing(path)

        elif chosen == act_reveal:
            if os.path.exists(path):
                # On Windows, reliably reveal the item in Explorer
                try:
                    norm = os.path.normpath(path)
                    if os.path.isdir(norm):
                        # Open the folder directly
                        os.startfile(norm)
                    else:
                        # Select the file in its folder
                        subprocess.run(["explorer", "/select,", norm], check=False)
                except Exception:
                    try:
                        os.startfile(target_dir)
                    except Exception:
                        QMessageBox.warning(main_window, "Reveal", f"Could not open Explorer for:\n{path}")

        elif chosen == act_open_default:
            if os.path.exists(path) and os.path.isfile(path):
                os.startfile(path)

        elif chosen == act_open_terminal:
            # Open integrated terminal at this directory
            main_window.terminal_manager.add_new_terminal()
            term = main_window.terminal_tabs.currentWidget()
            if hasattr(term, 'process'):
                cmd = f'cd "{target_dir}"\n'
                term.process.write(cmd.encode('utf-8'))

        elif chosen == act_copy:
            main_window.file_clipboard = {'action': 'copy', 'paths': [path]}

        elif chosen == act_cut:
            main_window.file_clipboard = {'action': 'cut', 'paths': [path]}

        elif chosen == act_paste:
            if not main_window.file_clipboard['paths']:
                return
            action = main_window.file_clipboard['action']
            for src in main_window.file_clipboard['paths']:
                base_name = os.path.basename(src)
                dest_path = os.path.join(target_dir, base_name)
                if os.path.exists(dest_path):
                    dest_path = unique_name(dest_path)
                if action == 'copy':
                    if os.path.isdir(src):
                        shutil.copytree(src, dest_path)
                    else:
                        shutil.copy2(src, dest_path)
                elif action == 'cut':
                    shutil.move(src, dest_path)
            if action == 'cut':
                # Clear clipboard after move
                main_window.file_clipboard = {'action': None, 'paths': []}

        elif chosen == act_copy_path:
            QApplication.clipboard().setText(path)

        elif chosen == act_copy_rel:
            try:
                root_src_index = proxy_model.mapToSource(tree_view.rootIndex())
                root_path = file_model.filePath(root_src_index)
                rel = os.path.relpath(path, root_path)
                QApplication.clipboard().setText(rel)
            except Exception:
                QApplication.clipboard().setText(path)

        elif chosen == act_duplicate:
            if os.path.isfile(path):
                dest_path = unique_name(path)
                shutil.copy2(path, dest_path)
            elif os.path.isdir(path):
                dest_path = unique_name(path)
                shutil.copytree(path, dest_path)

        elif chosen == act_rename:
            new_name, ok = CustomInputDialog.getText(main_window, "Rename", f"Enter new name for '{os.path.basename(path)}'")
            if ok and new_name:
                new_path = os.path.join(os.path.dirname(path), new_name)
                if os.path.exists(new_path):
                    QMessageBox.warning(main_window, "Warning", "A file or folder with that name already exists.")
                else:
                    os.rename(path, new_path)

        elif chosen == act_delete:
            confirm = CustomMessageBox.question(main_window, "Confirm Delete", f"Are you sure you want to delete '{os.path.basename(path)}'?")
            if confirm == QMessageBox.Yes:
                # Normalize path for comparison
                norm_path = os.path.abspath(path)
                is_directory = os.path.isdir(path)
                
                # Create backup for undo (use tree_view's operation history)
                backup_dir = tree_view.operation_history.get_backup_dir()
                backup_name = f"backup_{os.path.basename(path)}_ctx"
                backup_path = os.path.join(backup_dir, backup_name)
                
                # Backup before delete
                if is_directory:
                    shutil.copytree(path, backup_path)
                else:
                    shutil.copy2(path, backup_path)
                
                # Close editor tabs for deleted files (VS Code behavior)
                if is_directory:
                    # Close all tabs for files inside this directory
                    tabs_to_close = []
                    for file_path, editor in list(main_window.open_files.items()):
                        norm_file_path = os.path.abspath(file_path)
                        # Check if file is inside the deleted directory
                        if norm_file_path.startswith(norm_path + os.sep) or norm_file_path == norm_path:
                            tabs_to_close.append(editor)
                    
                    # Close the tabs
                    for editor in tabs_to_close:
                        main_window.close_editor_by_widget(editor)
                    
                    # Delete the directory
                    shutil.rmtree(path)
                else:
                    # Close tab for this specific file
                    editor = main_window.open_files.get(norm_path)
                    if editor:
                        main_window.close_editor_by_widget(editor)
                    
                    # Delete the file
                    os.remove(path)
                
                # Add to undo history (import FileOperation from the tree view module)
                from Details.file_tree_with_shortcuts import FileOperation
                op = FileOperation('delete', {
                    'original_path': path,
                    'backup_path': backup_path,
                    'was_dir': is_directory
                })
                tree_view.operation_history.add_operation(op)
                
                # Show status message
                main_window.statusBar().showMessage(f"Deleted '{os.path.basename(path)}' (Ctrl+Z to undo)", 3000)

        # Python run actions removed
    except Exception as e:
        QMessageBox.critical(main_window, "Error", str(e))

    # Ensure view refresh
    tree_view.viewport().update()
