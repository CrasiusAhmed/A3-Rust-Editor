"""
Terminal management functionality.
"""
import os
from running_app import InteractiveTerminal


class TerminalManager:
    """Manages terminal operations and interactions."""
    
    def __init__(self, main_window):
        self.main_window = main_window

    def toggle_terminal_panel(self):
        """Toggles the visibility of the terminal panel."""
        sizes = self.main_window.editor_terminal_splitter.sizes()
        if sizes[1] == 0:  # If hidden, show it
            total = max(100, sum(sizes)) or max(100, self.main_window.editor_terminal_splitter.height())
            self.main_window.editor_terminal_splitter.setSizes([int(total * 0.6), int(total * 0.4)])
            if self.main_window.terminal_tabs.count() == 0:
                self.add_new_terminal()
        else:  # If visible, hide it
            self.hide_terminal_panel()

    def add_new_terminal(self):
        """Adds a new terminal tab, configures its environment, and ensures the panel is visible."""
        if self.main_window.editor_terminal_splitter.sizes()[1] == 0:
            sizes = self.main_window.editor_terminal_splitter.sizes()
            total = max(100, sum(sizes)) or max(100, self.main_window.editor_terminal_splitter.height())
            self.main_window.editor_terminal_splitter.setSizes([int(total * 0.6), int(total * 0.4)])

        # --- FIX: Start terminal in the current project directory ---
        source_root_index = self.main_window.proxy_model.mapToSource(self.main_window.tree_view.rootIndex())
        working_directory = self.main_window.file_model.filePath(source_root_index)

        # --- NEW: Configure terminal environment ---
        python_executable = self.main_window.settings.get('python_interpreter_path') or 'python'
        startup_command = None
        # Use platform from stdlib, not from main_window
        import sys as _sys
        if python_executable and _sys.platform == "win32":
            # For PowerShell, prepend the interpreter's directory to the PATH
            interpreter_dir = os.path.dirname(python_executable)
            startup_command = f"$env:Path = '{interpreter_dir}' + ';' + $env:Path"

        terminal = InteractiveTerminal(startup_command=startup_command, working_directory=working_directory)
        index = self.main_window.terminal_tabs.addTab(terminal, "powershell")
        self.main_window.terminal_tabs.setCurrentIndex(index)

    def close_terminal_tab(self, index):
        """Closes the terminal tab at the given index."""
        if 0 <= index < self.main_window.terminal_tabs.count():
            terminal_to_remove = self.main_window.terminal_tabs.widget(index)
            if terminal_to_remove:
                terminal_to_remove.kill_process()
            self.main_window.terminal_tabs.removeTab(index)
            if self.main_window.terminal_tabs.count() == 0:
                self.hide_terminal_panel()

    def kill_current_terminal(self):
        """Kills the currently active terminal."""
        index = self.main_window.terminal_tabs.currentIndex()
        if index != -1:
            self.close_terminal_tab(index)

    def hide_terminal_panel(self):
        """Hides the terminal panel."""
        total = max(100, sum(self.main_window.editor_terminal_splitter.sizes())) or max(100, self.main_window.editor_terminal_splitter.height())
        self.main_window.editor_terminal_splitter.setSizes([total, 0])