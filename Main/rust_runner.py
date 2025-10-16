import os
import sys
import shutil
import re
from PySide6.QtCore import QProcess, Slot


class RustRunnerManager:
    """
    Encapsulates running Rust code via cargo or rustc, capturing output and
    relaying it to the main window's Output tab. This removes bulky logic from Rust.py.
    """

    def __init__(self, window):
        self.w = window  # MainWindow instance
        self.process: QProcess | None = None
        self.mode: str | None = None  # 'cargo' | 'rustc_compile' | 'exe'
        self.pending_exe: str | None = None

    def ensure_dependency(self, cargo_root: str, crate: str, version: str) -> bool:
        """
        Ensure 'crate = "version"' exists in Cargo.toml [dependencies].
        Returns True if the file was modified.
        """
        try:
            cargo_toml = os.path.join(cargo_root, 'Cargo.toml')
            if not os.path.isfile(cargo_toml):
                return False
            with open(cargo_toml, 'r', encoding='utf-8') as f:
                content = f.read()
            dep_re = re.compile(rf'^\s*{re.escape(crate)}\s*=\s*', re.MULTILINE)
            if dep_re.search(content):
                out = getattr(self.w, 'python_console_output', None)
                if out:
                    out.appendPlainText(f"Dependency {crate} already present in Cargo.toml")
                return False
            if '[dependencies]' not in content:
                content = content.rstrip() + f'\n\n[dependencies]\n{crate} = "{version}"\n'
            else:
                lines = content.splitlines()
                out_lines = []
                i = 0
                inserted = False
                while i < len(lines):
                    out_lines.append(lines[i])
                    if lines[i].strip() == '[dependencies]' and not inserted:
                        j = i + 1
                        while j < len(lines) and not lines[j].startswith('['):
                            j += 1
                        block = '\n'.join(lines[i+1:j])
                        if not dep_re.search(block):
                            out_lines.append(f'{crate} = "{version}"')
                        out_lines.extend(lines[i+1:j])
                        i = j
                        inserted = True
                        continue
                    i += 1
                content = '\n'.join(out_lines)
                if not content.endswith('\n'):
                    content += '\n'
            with open(cargo_toml, 'w', encoding='utf-8') as f:
                f.write(content)
            out = getattr(self.w, 'python_console_output', None)
            if out:
                out.appendPlainText(f'Auto-added dependency: {crate} = "{version}" in {cargo_toml}')
            return True
        except Exception as e:
            out = getattr(self.w, 'python_console_output', None)
            if out:
                out.appendPlainText(f'Failed to ensure dependency {crate}: {e}')
            return False

    def run_for_current_file(self, file_path: str):
        try:
            out = getattr(self.w, 'python_console_output', None)
            if out:
                out.clear()
                out.appendPlainText(f"Running Rust for: {os.path.basename(file_path)}\n")
            
            # Check for errors first before running
            editor = self.w.get_editor_for_path(file_path)
            if editor and hasattr(editor, 'rust_error_checker'):
                out.appendPlainText("Checking for compilation errors...\n")
                
                # Save the file first if it has unsaved changes
                if editor.document().isModified():
                    out.appendPlainText("Saving file before checking...\n")
                    try:
                        with open(file_path, 'w', encoding='utf-8') as f:
                            f.write(editor.toPlainText())
                        editor.document().setModified(False)
                    except Exception as e:
                        out.appendPlainText(f"Error saving file: {e}\n")
                
                error_checker = editor.rust_error_checker
                error_checker.perform_check()
                
                # Wait a moment for the check to complete
                from PySide6.QtCore import QEventLoop, QTimer
                loop = QEventLoop()
                QTimer.singleShot(500, loop.quit)
                loop.exec()
                
                # Check if there are errors
                if editor.runtime_error_selections:
                    # Count errors vs warnings
                    error_count = 0
                    warning_count = 0
                    
                    # Get the actual errors/warnings from the error checker
                    try:
                        all_issues = error_checker.check_rust_code(editor.toPlainText())
                        for issue in all_issues:
                            if issue.get('type') == 'warning':
                                warning_count += 1
                            else:
                                error_count += 1
                    except Exception:
                        error_count = len(editor.runtime_error_selections)
                    
                    file_name = os.path.basename(file_path)
                    
                    # If there are actual errors (not just warnings), prevent running
                    if error_count > 0:
                        out.appendPlainText(f"❌ Found {error_count} compilation error(s) in {file_name}!\n")
                        out.appendPlainText("Lines with errors are highlighted in RED.\n")
                        out.appendPlainText("Fix all errors before running.\n")
                        
                        # Show error details with line numbers and messages
                        try:
                            if all_issues:
                                out.appendPlainText("\nError details:")
                                for issue in all_issues:
                                    if issue.get('type') == 'warning':
                                        continue
                                    ln = issue.get('line')
                                    col = issue.get('column')
                                    msg = issue.get('message') or 'Compilation error'
                                    # Colored, readable line
                                    self._append_colored_line(out, f"  • Line {ln}:{(col or 0)+1} - {msg}", '#FF6B6B')
                        except Exception:
                            pass
                        
                        if warning_count > 0:
                            out.appendPlainText(f"\n⚠️  Also found {warning_count} warning(s) highlighted in YELLOW/ORANGE.")
                            out.appendPlainText("Warnings are suggestions for improvement but won't prevent running.")
                        return
                    elif warning_count > 0:
                        # Only warnings, allow running but inform user
                        out.appendPlainText(f"⚠️  Found {warning_count} warning(s) in {file_name}.\n")
                        out.appendPlainText("Lines with warnings are highlighted in YELLOW/ORANGE.\n")
                        out.appendPlainText("Warnings are suggestions for code improvement.\n")
                        out.appendPlainText("Your code will still compile and run.\n\n")
                        out.appendPlainText("✓ No compilation errors found. Running...\n")
                else:
                    out.appendPlainText("✓ No compilation errors or warnings found. Running...\n")
            
            # Stop previous process if running
            if self.process and self.process.state() == QProcess.Running:
                self.process.kill()
                self.process.waitForFinished(1000)

            self.process = QProcess(self.w)
            self.process.readyReadStandardOutput.connect(self._handle_stdout)
            self.process.readyReadStandardError.connect(self._handle_stderr)
            self.process.finished.connect(self._process_finished)
            self.process.errorOccurred.connect(self._process_error)

            folder = os.path.dirname(os.path.abspath(file_path))
            cargo_root = self.find_cargo_root(folder)
            
            if cargo_root:
                # Guard: cargo must be available
                if shutil.which('cargo') is None:
                    if out:
                        out.appendPlainText("Rust toolchain not detected. Install Rust and cargo from https://rustup.rs and try again.")
                    return
                if out:
                    out.appendPlainText(f"Using Cargo project: {cargo_root}")
                self.mode = 'cargo'
                self.pending_exe = None
                self.process.setWorkingDirectory(cargo_root)
                # Auto-ensure common GUI crate deps when referenced in code
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        code = f.read()
                    if 'eframe' in code:
                        if out:
                            out.appendPlainText('Detected eframe usage in source; ensuring dependency in Cargo.toml')
                        added = self.ensure_dependency(cargo_root, 'eframe', '0.27')
                        if not added and out:
                            out.appendPlainText('Dependency eframe already present or could not be added')
                except Exception as ex:
                    if out:
                        out.appendPlainText(f'Auto-dependency check failed: {ex}')
                self.process.start('cargo', ['run'])
            else:
                # Guard: rustc must be available
                if shutil.which('rustc') is None:
                    if out:
                        out.appendPlainText("Rust compiler (rustc) not found. Install Rust from https://rustup.rs and try again.")
                    return
                base = os.path.splitext(os.path.basename(file_path))[0]
                exe = os.path.join(folder, base + ('.exe' if sys.platform == 'win32' else ''))
                try:
                    if os.path.exists(exe):
                        try:
                            os.remove(exe)
                        except Exception:
                            pass
                except Exception:
                    pass
                self.mode = 'rustc_compile'
                self.pending_exe = exe
                self.process.setWorkingDirectory(folder)
                self.process.start('rustc', [file_path, '-o', exe])
        except Exception as e:
            out = getattr(self.w, 'python_console_output', None)
            if out:
                out.appendPlainText(f"Error starting Rust process: {e}")

    def _append_output(self, text: str):
        out = getattr(self.w, 'python_console_output', None)
        if out:
            out.appendPlainText(text.rstrip('\n'))

    def _handle_stdout(self):
        try:
            if not self.process:
                return
            data = self.process.readAllStandardOutput().data()
            text = data.decode('utf-8', errors='replace')
            self._append_output(text)
        except Exception:
            pass

    def _handle_stderr(self):
        try:
            if not self.process:
                return
            data = self.process.readAllStandardError().data()
            text = data.decode('utf-8', errors='replace')
            # Parse and highlight error files in the tree
            self._parse_and_highlight_error_files(text)
            # Colorize the output
            self._append_colored_output(text)
        except Exception:
            pass
    
    def _append_colored_output(self, text: str):
        """Append output with color formatting and clear error separation."""
        out = getattr(self.w, 'python_console_output', None)
        if not out:
            return
        
        lines = text.split('\n')
        error_count = 0
        in_error_block = False
        
        for i, line in enumerate(lines):
            if not line.strip():
                out.appendPlainText(line)
                continue
            
            # Detect start of new error/warning
            is_error_start = 'error[E' in line or (line.strip().startswith('error:') and '-->' not in line)
            is_warning_start = 'warning[' in line or (line.strip().startswith('warning:') and '-->' not in line)
            
            # Add separator before each new error (except the first one)
            if (is_error_start or is_warning_start) and error_count > 0:
                out.appendHtml('<span style="color: #555555;">━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━</span>')
                out.appendPlainText('')
            
            if is_error_start or is_warning_start:
                error_count += 1
                in_error_block = True
                # Add error number header
                error_type = 'ERROR' if is_error_start else 'WARNING'
                color = '#FF6B6B' if is_error_start else '#FFB84D'
                out.appendHtml(f'<span style="color: {color}; font-weight: bold;">╔═ {error_type} #{error_count} ═══════════════════════════════════════════════════</span>')
            
            # Color coding based on content
            if 'error[E' in line or 'error:' in line.lower():
                # Red for errors with bold
                self._append_colored_line(out, '║ ' + line, '#FF6B6B', bold=True)
            elif 'warning:' in line.lower() or 'warning[' in line:
                # Yellow/Orange for warnings with bold
                self._append_colored_line(out, '║ ' + line, '#FFB84D', bold=True)
            elif line.strip().startswith('-->'):
                # Cyan for file location with icon
                self._append_colored_line(out, '║ 📍 ' + line.strip(), '#4ECDC4', bold=True)
            elif line.strip().startswith('|'):
                # Light gray for code context with proper indentation
                self._append_colored_line(out, '║   ' + line, '#95A5A6')
            elif 'help:' in line.lower():
                # Green for help suggestions with icon
                self._append_colored_line(out, '║ 💡 ' + line.strip(), '#6BCF7F')
            elif 'note:' in line.lower():
                # Light blue for notes with icon
                self._append_colored_line(out, '║ ℹ️  ' + line.strip(), '#85C1E9')
            elif 'Compiling' in line or 'Finished' in line or 'Running' in line:
                # Blue for build status
                self._append_colored_line(out, line, '#5DADE2')
                in_error_block = False
            elif line.strip().startswith('='):
                # Separator lines
                self._append_colored_line(out, '║ ' + line, '#555555')
            else:
                # Regular text - add prefix if in error block
                if in_error_block and line.strip():
                    out.appendPlainText('║ ' + line)
                else:
                    out.appendPlainText(line)
        
        # Add final separator if there were errors
        if error_count > 0:
            out.appendHtml('<span style="color: #555555;">╚═══════════════════════════════════════════════════════════════════════</span>')
            out.appendPlainText('')
    
    def _append_colored_line(self, output_widget, text: str, color: str, bold: bool = False):
        """Append a line with HTML color formatting."""
        try:
            # Use HTML to add color and optional bold
            style = f'color: {color};'
            if bold:
                style += ' font-weight: bold;'
            output_widget.appendHtml(f'<span style="{style}">{text}</span>')
        except Exception:
            output_widget.appendPlainText(text)

    @Slot(int, QProcess.ExitStatus)
    def _process_finished(self, exit_code, exit_status):
        try:
            if self.mode == 'rustc_compile' and exit_status == QProcess.NormalExit and exit_code == 0 and self.pending_exe:
                folder = os.path.dirname(self.pending_exe)
                
                # Run the compiled executable
                self.mode = 'exe'
                self.process = QProcess(self.w)
                self.process.readyReadStandardOutput.connect(self._handle_stdout)
                self.process.readyReadStandardError.connect(self._handle_stderr)
                self.process.finished.connect(self._process_finished)
                self.process.errorOccurred.connect(self._process_error)
                self.process.setWorkingDirectory(folder)
                program = self.pending_exe
                self.pending_exe = None
                self.process.start(program, [])
                return
            
            # If compilation succeeded (exit code 0), clear Cargo.toml error highlights
            if exit_code == 0 and self.mode == 'cargo':
                self._clear_cargo_toml_error_highlights()
            
            self._append_output(f"\n--- Finished (exit code {exit_code}) ---")
        except Exception:
            pass

    @Slot(QProcess.ProcessError)
    def _process_error(self, error):
        try:
            self._append_output(f"Process error: {error}")
        except Exception:
            pass

    def _parse_and_highlight_error_files(self, error_text: str):
        """
        Parse error output to find which files have errors and highlight them in the file tree.
        Handles both local project files and external dependency errors.
        """
        try:
            # Pattern to match file paths in error messages
            # Examples:
            # --> src/main.rs:9:34
            # --> Cargo.toml:12:1
            # --> C:\Users\PC\.cargo\registry\...\eframe-0.24.1\src\native\app_icon.rs:83:9
            file_pattern = re.compile(r'-->\s+([^:]+):(\d+):(\d+)')
            
            error_files = set()
            has_dependency_error = False
            failed_crate = None
            
            # Check if error is in external dependency
            if '.cargo' in error_text and 'registry' in error_text:
                has_dependency_error = True
                # Try to extract the crate name
                crate_match = re.search(r'\\([a-z_\-]+)-\d+\.\d+\.\d+\\', error_text)
                if crate_match:
                    failed_crate = crate_match.group(1)
            
            for match in file_pattern.finditer(error_text):
                file_path = match.group(1).strip()
                line_num = match.group(2)
                col_num = match.group(3)
                
                # Normalize path separators
                file_path = file_path.replace('\\', os.sep).replace('/', os.sep)
                
                # Check if it's a local project file (not in .cargo registry)
                if '.cargo' not in file_path and 'registry' not in file_path:
                    # Try to resolve relative paths
                    if not os.path.isabs(file_path):
                        # Get the working directory of the process
                        if self.process and hasattr(self.process, 'workingDirectory'):
                            working_dir = self.process.workingDirectory()
                            full_path = os.path.join(working_dir, file_path)
                            if os.path.exists(full_path):
                                file_path = os.path.abspath(full_path)
                                error_files.add(file_path)
                    else:
                        if os.path.exists(file_path):
                            error_files.add(file_path)
            
            # If it's a dependency error, highlight Cargo.toml instead
            if has_dependency_error and self.process:
                working_dir = self.process.workingDirectory()
                cargo_toml = os.path.join(working_dir, 'Cargo.toml')
                if os.path.exists(cargo_toml):
                    error_files.add(cargo_toml)
                    # Show helpful message in output
                    out = getattr(self.w, 'python_console_output', None)
                    if out and failed_crate:
                        out.appendHtml(f'<br><span style="color: #FF6B6B;">⚠️  Dependency Error Detected!</span>')
                        out.appendHtml(f'<span style="color: #FFB84D;">The <b>{failed_crate}</b> crate has configuration issues.</span>')
                        out.appendHtml(f'<span style="color: #4ECDC4;">⚙️  Check your <b>Cargo.toml</b> file (highlighted in red in file tree)</span>')
                        out.appendPlainText('')
                        
                        # Provide specific solution for common issues
                        if 'winapi' in error_text and 'feature' in error_text:
                            out.appendHtml('<span style="color: #6BCF7F;">🔧 <b>Solution:</b> Add winapi features to Cargo.toml:</span>')
                            out.appendPlainText('[dependencies]')
                            out.appendPlainText('winapi = { version = "0.3", features = ["winuser", "windef"] }')
                            out.appendPlainText('')
                        elif failed_crate == 'eframe':
                            out.appendHtml('<span style="color: #6BCF7F;">🔧 <b>Solution:</b> Try updating eframe version in Cargo.toml:</span>')
                            out.appendPlainText('[dependencies]')
                            out.appendPlainText('eframe = "0.27"  # or latest version')
                            out.appendPlainText('')
            
            # Highlight all error files in the tree
            for error_file in error_files:
                self._highlight_error_file(error_file)
                
        except Exception as e:
            # Silently fail - highlighting is not critical
            pass
    
    def _highlight_error_file(self, file_path: str):
        """Highlight the file with errors in the tree view with red background and in editor if open."""
        try:
            if hasattr(self.w, 'highlight_main_python_file'):
                self.w.highlight_main_python_file(file_path)
                # Also refresh the tree view to show the highlight
                if hasattr(self.w, 'tree_view'):
                    self.w.tree_view.viewport().update()
            
            # If the file is currently open in an editor, add red background to all lines
            if file_path.lower().endswith('cargo.toml'):
                editor = self.w.get_editor_for_path(file_path)
                if editor:
                    self._add_cargo_toml_error_highlight(editor)
        except Exception:
            pass
    
    def _add_cargo_toml_error_highlight(self, editor):
        """Add subtle red background to [dependencies] section in Cargo.toml when it has dependency errors."""
        try:
            from PySide6.QtWidgets import QTextEdit
            from PySide6.QtGui import QColor, QTextFormat, QTextCursor
            
            # Clear any existing Cargo.toml error highlights
            if not hasattr(editor, 'cargo_toml_error_selections'):
                editor.cargo_toml_error_selections = []
            
            editor.cargo_toml_error_selections = []
            
            # Find the [dependencies] section and highlight only that section
            text = editor.toPlainText()
            lines = text.split('\n')
            
            in_dependencies = False
            dependencies_start_line = -1
            dependencies_end_line = -1
            
            for i, line in enumerate(lines):
                stripped = line.strip()
                
                # Found [dependencies] section
                if stripped == '[dependencies]':
                    in_dependencies = True
                    dependencies_start_line = i
                    continue
                
                # If we're in dependencies section
                if in_dependencies:
                    # Check if we hit another section (starts with [)
                    if stripped.startswith('[') and stripped.endswith(']'):
                        dependencies_end_line = i - 1
                        break
                    # If we reach end of file
                    if i == len(lines) - 1:
                        dependencies_end_line = i
            
            # If [dependencies] section was found, highlight it
            if dependencies_start_line >= 0:
                if dependencies_end_line < dependencies_start_line:
                    dependencies_end_line = len(lines) - 1
                
                # Highlight from [dependencies] line to the end of the section
                block = editor.document().findBlockByLineNumber(dependencies_start_line)
                end_block_num = dependencies_end_line
                
                current_line = dependencies_start_line
                while block.isValid() and current_line <= end_block_num:
                    selection = QTextEdit.ExtraSelection()
                    selection.format.setBackground(QColor(139, 69, 69, 40))  # Subtle red for dependencies section
                    selection.format.setProperty(QTextFormat.FullWidthSelection, True)
                    cursor = QTextCursor(block)
                    cursor.clearSelection()
                    selection.cursor = cursor
                    editor.cargo_toml_error_selections.append(selection)
                    block = block.next()
                    current_line += 1
            
            # Update the editor to show highlights
            editor.highlightCurrentLine()
        except Exception:
            pass

    def _clear_cargo_toml_error_highlights(self):
        """Clear red background from Cargo.toml when compilation succeeds."""
        try:
            # Find Cargo.toml in the project
            if self.process and hasattr(self.process, 'workingDirectory'):
                working_dir = self.process.workingDirectory()
                cargo_toml = os.path.join(working_dir, 'Cargo.toml')
                
                # Check if Cargo.toml is open in an editor
                if os.path.exists(cargo_toml):
                    editor = self.w.get_editor_for_path(cargo_toml)
                    if editor and hasattr(editor, 'cargo_toml_error_selections'):
                        # Clear the error highlights
                        editor.cargo_toml_error_selections = []
                        editor.highlightCurrentLine()
                    
                    # Also clear the file tree highlight
                    if hasattr(self.w, 'highlighted_file'):
                        if self.w.highlighted_file and self.w.highlighted_file.lower() == cargo_toml.lower():
                            self.w.highlighted_file = None
                            if hasattr(self.w, 'tree_view'):
                                self.w.tree_view.viewport().update()
        except Exception:
            pass

    def find_cargo_root(self, start_dir: str):
        try:
            d = os.path.abspath(start_dir)
            while True:
                if os.path.isfile(os.path.join(d, 'Cargo.toml')):
                    return d
                parent = os.path.dirname(d)
                if not parent or parent == d:
                    break
                d = parent
        except Exception:
            pass
        return None
