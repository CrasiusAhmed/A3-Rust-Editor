"""
Rust Error Checker Module
Checks Rust code for compilation errors using rustc and highlights error lines with red background.
Also includes CargoCheckManager for fast error checking with cargo check.
"""

import os
import subprocess
import tempfile
import re
from PySide6.QtCore import QObject, Signal, QTimer, Slot, QProcess
from PySide6.QtGui import QTextCharFormat, QColor, QTextFormat, QTextCursor
from PySide6.QtWidgets import QTextEdit


class RustErrorChecker(QObject):
    """
    Checks Rust code for compilation errors and highlights error lines.
    """
    errors_found = Signal(list)  # Emits list of error dictionaries
    
    def __init__(self, editor):
        super().__init__()
        self.editor = editor
        self.check_timer = QTimer(self)
        self.check_timer.setSingleShot(True)
        self.check_timer.setInterval(1000)  # 1 second delay after typing stops
        self.check_timer.timeout.connect(self.perform_check)
        
        # Don't auto-clear error highlights - keep them visible until fixed or manually cleared
        # This way users can see errors while they work on fixing them
        
        # Don't auto-check on text changes - only check when explicitly called
        # This way errors only show after user tries to run the code
    
    def schedule_check(self):
        """Schedule an error check after a delay."""
        self.check_timer.stop()
        self.check_timer.start()
    
    def perform_check(self):
        """Perform the actual Rust error checking."""
        try:
            code = self.editor.toPlainText()
            if not code.strip():
                self.clear_errors()
                return
            
            errors = self.check_rust_code(code)
            self.highlight_errors(errors)
            self.errors_found.emit(errors)
        except Exception as e:
            print(f"Error checking Rust code: {e}")
            import traceback
            traceback.print_exc()
    
    def check_rust_code(self, code):
        """
        Check Rust code for compilation errors using rustc or cargo check.
        Returns a list of error dictionaries with line numbers and messages.
        """
        errors = []
        
        try:
            # Check if we're in a Cargo project by looking for the editor's file path
            file_path = None
            try:
                # Try to get the file path from the main window
                main_window = self.editor.window()
                if hasattr(main_window, 'current_file_path'):
                    file_path = main_window.current_file_path
            except Exception:
                pass
            
            # If in a Cargo project, use cargo check
            if file_path:
                cargo_root = self._find_cargo_root(os.path.dirname(file_path))
                if cargo_root:
                    # Use cargo check for Cargo projects
                    result = subprocess.run(
                        ['cargo', 'check', '--message-format=short'],
                        capture_output=True,
                        text=True,
                        timeout=10,
                        cwd=cargo_root,
                        creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
                    )
                    errors = self.parse_rustc_output(result.stderr, file_path)
                    return errors
            
            # Fallback: Create a temporary file for standalone checking
            with tempfile.NamedTemporaryFile(mode='w', suffix='.rs', delete=False, encoding='utf-8') as tmp_file:
                tmp_file.write(code)
                tmp_path = tmp_file.name
            
            try:
                # Detect if code has main function to determine crate type
                crate_type = 'bin' if 'fn main()' in code else 'lib'
                
                # Run rustc to check for errors
                result = subprocess.run(
                    ['rustc', '--error-format=short', '--crate-type', crate_type, tmp_path],
                    capture_output=True,
                    text=True,
                    timeout=5,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
                )
                
                # Parse rustc output for errors
                errors = self.parse_rustc_output(result.stderr, tmp_path)
                
            finally:
                # Clean up temporary file
                try:
                    os.unlink(tmp_path)
                except Exception:
                    pass
                    
        except FileNotFoundError:
            # rustc not found - silently ignore
            pass
        except subprocess.TimeoutExpired:
            # Compilation took too long - ignore
            pass
        except Exception as e:
            print(f"Error running rustc: {e}")
        
        return errors
    
    def parse_rustc_output(self, output, tmp_path):
        """
        Parse rustc error output and extract line numbers and messages.
        Handles multiple formats from rustc and cargo check.
        Detects both errors and warnings.
        """
        errors = []
        
        if not output:
            return errors
        
        # Pattern 1: cargo check default format (multi-line)
        # Format:
        #   error[E0308]: mismatched types
        #   --> src\main.rs:110:12
        # OR
        #   warning: unused import: `std::collections::HashMap`
        #   --> src\main.rs:6:5
        lines = output.split('\n')
        current_error = None
        
        for i, line in enumerate(lines):
            # Check if this line starts an error or warning
            error_match = re.match(r'^(error|warning)(?:\[E\d+\])?\s*:\s*(.+)', line.strip())
            if error_match:
                msg_type = error_match.group(1)  # 'error' or 'warning'
                message = error_match.group(2).strip()
                current_error = {
                    'type': msg_type,
                    'message': message,
                    'line': None,
                    'column': None
                }
                continue
            
            # Check if this line has the file location (follows error/warning)
            if current_error and line.strip().startswith('-->'):
                # Extract file:line:column from "--> src\main.rs:110:12"
                location_match = re.search(r'-->\s+[^:]+:(\d+):(\d+)', line)
                if location_match:
                    current_error['line'] = int(location_match.group(1))
                    current_error['column'] = int(location_match.group(2)) - 1
                    errors.append(current_error)
                    current_error = None
        
        # Pattern 2: cargo check --message-format=short (single line)
        # Format: src\main.rs:9:34: error[E0425]: cannot find value `z` in this scope
        # Format: src\main.rs:6:9: warning: unused variable: `y`
        pattern_short = re.compile(r'^[^:]+:(\d+):(\d+):\s*(error|warning)(?:\[E\d+\])?:\s*(.+?)(?::|$)', re.MULTILINE)
        for match in pattern_short.finditer(output):
            line_num = int(match.group(1))
            col_num = int(match.group(2))
            msg_type = match.group(3)  # 'error' or 'warning'
            message = match.group(4).strip()
            
            # Avoid duplicates (if already parsed in multi-line format)
            duplicate = False
            for err in errors:
                if err['line'] == line_num and err['type'] == msg_type:
                    duplicate = True
                    break
            
            if not duplicate:
                errors.append({
                    'line': line_num,
                    'column': col_num - 1,
                    'type': msg_type,
                    'message': message
                })
        
        return errors
    
    def highlight_errors(self, errors):
        """
        Highlight error and warning lines in the editor.
        Errors: red background
        Warnings: yellow/orange background
        Also updates scrollbar markers for VS Code-like error indicators.
        Highlights remain visible until code is fixed or manually cleared.
        """
        if not hasattr(self.editor, 'runtime_error_selections'):
            return
        
        # Clear previous error highlights
        self.editor.runtime_error_selections = []
        
        # Separate errors and warnings for scrollbar markers
        error_lines = []
        warning_lines = []
        
        if not errors:
            self.editor.highlightCurrentLine()
            # Clear scrollbar markers
            if hasattr(self.editor, 'minimap_scrollbar'):
                self.editor.minimap_scrollbar.set_syntax_markers(yellow=[], red=[], warning=[])
            return
        
        # Create selections for each error/warning line
        for error in errors:
            line_num = error.get('line', 0)
            if line_num <= 0:
                continue
            
            selection = QTextEdit.ExtraSelection()
            
            # Choose color based on type
            error_type = error.get('type', 'error')
            if error_type == 'warning':
                # Yellow/orange background for warnings
                selection.format.setBackground(QColor(180, 140, 50, 80))  # Semi-transparent orange
                warning_lines.append(line_num)
            else:
                # Red background for errors
                selection.format.setBackground(QColor(139, 69, 69, 100))  # Semi-transparent red
                error_lines.append(line_num)
            
            selection.format.setProperty(QTextFormat.FullWidthSelection, True)
            
            # Find the block for this line
            block = self.editor.document().firstBlock()
            for _ in range(line_num - 1):
                if not block.isValid():
                    block = None
                    break
                block = block.next()
            
            if block and block.isValid():
                cursor = QTextCursor(block)
                cursor.clearSelection()
                selection.cursor = cursor
                self.editor.runtime_error_selections.append(selection)
        
        # Update scrollbar markers (VS Code-style indicators)
        if hasattr(self.editor, 'minimap_scrollbar'):
            self.editor.minimap_scrollbar.set_syntax_markers(
                yellow=[],  # Not used for Rust errors
                red=error_lines,  # Red markers for errors
                warning=warning_lines  # Orange markers for warnings
            )
        
        # Update the editor to show highlights
        self.editor.highlightCurrentLine()
    
    def clear_errors(self):
        """Clear all error highlights and scrollbar markers."""
        if hasattr(self.editor, 'runtime_error_selections'):
            self.editor.runtime_error_selections = []
            self.editor.highlightCurrentLine()
        
        # Clear scrollbar markers
        if hasattr(self.editor, 'minimap_scrollbar'):
            self.editor.minimap_scrollbar.set_syntax_markers(yellow=[], red=[], warning=[])
    
    def _find_cargo_root(self, start_dir: str):
        """Find the Cargo.toml root directory."""
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
    
    def get_error_at_line(self, line_num):
        """Get the error message for a specific line number."""
        # This would be used for tooltips or status bar messages
        pass


class CargoCheckManager(QObject):
    """
    Manages cargo check operations for fast error checking without compilation.
    Provides instant feedback (1-2 seconds) compared to full cargo run (5-10 seconds).
    """
    
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.process = None
    
    def run_cargo_check(self):
        """Run cargo check for fast error checking without running the program."""
        try:
            # Focus the output tab
            try:
                self.main_window.preview_tabs.setCurrentWidget(self.main_window.python_console_output)
            except Exception:
                pass
            
            # Check if a file is selected
            if not self.main_window.current_file_path or not os.path.isfile(self.main_window.current_file_path):
                try:
                    self.main_window.python_console_output.appendPlainText("No file selected. Open a Rust file and try again.")
                except Exception:
                    pass
                return
            
            # Find cargo root
            folder = os.path.dirname(os.path.abspath(self.main_window.current_file_path))
            cargo_root = self._find_cargo_root(folder)
            
            if not cargo_root:
                self.main_window.python_console_output.appendPlainText("Not in a Cargo project. Cargo check requires a Cargo.toml file.")
                return
            
            # Clear output and show status with colors
            self.main_window.python_console_output.clear()
            self.main_window.python_console_output.appendHtml(f'<span style="color: #5DADE2; font-weight: bold;">Running cargo check in: {cargo_root}</span>')
            self.main_window.python_console_output.appendPlainText('')
            self.main_window.python_console_output.appendHtml('<span style="color: #6BCF7F; font-weight: bold;">⚡ Fast error checking (no compilation)...</span>')
            self.main_window.python_console_output.appendPlainText('')
            
            # Stop any running process
            if self.process and self.process.state() == QProcess.Running:
                self.process.kill()
                self.process.waitForFinished(1000)
            
            # Initialize stderr collection
            self._collected_stderr = ""
            
            # Find cargo executable
            cargo_cmd = self._find_cargo_executable()
            
            # Create new process for cargo check
            self.process = QProcess(self.main_window)
            self.process.readyReadStandardOutput.connect(self._handle_stdout)
            self.process.readyReadStandardError.connect(self._handle_stderr)
            self.process.finished.connect(self._cargo_check_finished)
            self.process.errorOccurred.connect(self._cargo_check_error)
            self.process.setWorkingDirectory(cargo_root)
            
            # Run cargo check
            self.process.start(cargo_cmd, ['check'])
            
        except Exception as e:
            try:
                self.main_window.python_console_output.appendPlainText(f"Error running cargo check: {e}")
            except Exception:
                pass
    
    def _find_cargo_executable(self):
        """Find the cargo executable in common locations."""
        cargo_cmd = 'cargo'
        try:
            import shutil
            cargo_path = shutil.which('cargo')
            if cargo_path:
                return cargo_path
            
            # Try common Rust installation paths
            home = os.path.expanduser('~')
            possible_paths = [
                os.path.join(home, '.cargo', 'bin', 'cargo.exe'),
                os.path.join(home, '.cargo', 'bin', 'cargo'),
                r'C:\Users\{}\\.cargo\\bin\\cargo.exe'.format(os.environ.get('USERNAME', '')),
            ]
            for p in possible_paths:
                if os.path.exists(p):
                    return p
        except Exception:
            pass
        return cargo_cmd
    
    def _find_cargo_root(self, start_dir: str):
        """Find the Cargo.toml root directory."""
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
    
    def _handle_stdout(self):
        """Handle standard output from cargo check with color formatting."""
        try:
            if self.process:
                data = self.process.readAllStandardOutput()
                text = bytes(data).decode('utf-8', errors='replace')
                if text.strip():
                    out = self.main_window.python_console_output
                    # Color code stdout messages
                    lines = text.split('\n')
                    for line in lines:
                        if not line.strip():
                            out.appendPlainText(line)
                            continue
                        
                        # Color different types of messages
                        if 'Updating' in line and 'index' in line:
                            # Cyan for updating index
                            out.appendHtml(f'<span style="color: #4ECDC4; font-weight: bold;">{line}</span>')
                        elif 'Downloading' in line or 'Downloaded' in line:
                            # Light blue for downloads
                            out.appendHtml(f'<span style="color: #85C1E9;">{line}</span>')
                        elif 'Checking' in line or 'Compiling' in line:
                            # Blue for build status
                            out.appendHtml(f'<span style="color: #5DADE2; font-weight: bold;">{line}</span>')
                        elif 'Finished' in line:
                            # Green for finished
                            out.appendHtml(f'<span style="color: #6BCF7F; font-weight: bold;">{line}</span>')
                        else:
                            out.appendPlainText(line)
        except Exception:
            pass
    
    def _handle_stderr(self):
        """Handle standard error from cargo check."""
        try:
            if self.process:
                data = self.process.readAllStandardError()
                text = bytes(data).decode('utf-8', errors='replace')
                if text.strip():
                    # Collect stderr for later parsing
                    if not hasattr(self, '_collected_stderr'):
                        self._collected_stderr = ""
                    self._collected_stderr += text
                    
                    # Use colored output like RustRunnerManager does
                    self._append_colored_output(text)
        except Exception:
            pass
    
    def _append_colored_output(self, text: str):
        """Append output with color formatting and clear error separation."""
        out = self.main_window.python_console_output
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
                out.appendHtml(f'<span style="color: {color}; font-weight: bold;">╔═ {error_type} #{error_count} ════════════════════════════════════════════════════</span>')
            
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
            elif 'Compiling' in line or 'Finished' in line or 'Running' in line or 'Checking' in line:
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
    def _cargo_check_finished(self, exit_code, exit_status):
        """Handle cargo check completion."""
        try:
            out = self.main_window.python_console_output
            if exit_code == 0:
                out.appendHtml('<br><span style="color: #6BCF7F;">✅ <b>No errors found!</b> Your code is ready to run.</span>')
                # Clear Cargo.toml error highlights if check succeeded
                if hasattr(self.main_window, 'rust_runner') and self.main_window.rust_runner:
                    self.main_window.rust_runner._clear_cargo_toml_error_highlights()
                
                # Clear error highlights in the editor
                editor = self.main_window.get_current_editor()
                if editor and hasattr(editor, 'rust_error_checker'):
                    editor.rust_error_checker.clear_errors()
            else:
                out.appendHtml(f'<br><span style="color: #FF6B6B;">❌ Found errors. Fix them before running.</span>')
                
                # Highlight errors in the editor with red/yellow backgrounds
                self._highlight_errors_in_editor()
            
            out.appendPlainText(f"\n--- Check finished (exit code {exit_code}) ---")
        except Exception as e:
            print(f"Error in _cargo_check_finished: {e}")
            import traceback
            traceback.print_exc()
    
    @Slot(QProcess.ProcessError)
    def _cargo_check_error(self, error):
        """Handle cargo check process errors."""
        try:
            out = self.main_window.python_console_output
            if error == QProcess.FailedToStart:
                out.appendHtml('<br><span style="color: #FF6B6B;">❌ <b>Cargo not found!</b></span>')
                out.appendPlainText("\nMake sure Rust is installed and 'cargo' is in your PATH.")
                out.appendPlainText("Install Rust from: https://rustup.rs/")
            else:
                out.appendPlainText(f"\nProcess error: {error}")
        except Exception:
            pass
    
    def _highlight_errors_in_editor(self):
        """Parse collected stderr output and highlight errors/warnings in the code editor."""
        try:
            # Get the current editor
            editor = self.main_window.get_current_editor()
            if not editor or not hasattr(editor, 'rust_error_checker'):
                return
            
            # Get the collected stderr output
            if not hasattr(self, '_collected_stderr'):
                return
            
            stderr_text = self._collected_stderr
            
            # Get the current file path
            file_path = self.main_window.current_file_path
            if not file_path:
                return
            
            # Parse the errors from stderr
            error_checker = editor.rust_error_checker
            errors = error_checker.parse_rustc_output(stderr_text, file_path)
            
            # Highlight the errors in the editor (will auto-clear after 3 seconds)
            if errors:
                error_checker.highlight_errors(errors)
                
        except Exception:
            pass
