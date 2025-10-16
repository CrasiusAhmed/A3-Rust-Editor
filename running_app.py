import os
import sys
import subprocess
from functools import partial

from PySide6.QtCore import (
    Qt, QDir, QFileInfo, QUrl, QRegularExpression, QCoreApplication, QRect, QSize, QProcess, Slot, QTimer, QRunnable, QThreadPool, QObject, Signal
)

from PySide6.QtGui import (
    QFont, QSyntaxHighlighter, QTextCharFormat, QColor, QPalette, QPainter, QTextFormat, QTextCursor
)
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QSplitter, QTreeView, QTextEdit,
    QVBoxLayout, QWidget, QFileDialog, QTabWidget, QPlainTextEdit,
    QMessageBox, QFileSystemModel, QMenuBar, QHeaderView,
    QHBoxLayout, QPushButton, QCompleter,
    QDialog, QDialogButtonBox, QFontComboBox, QSpinBox, QFormLayout,
    QMenu, QInputDialog, QLineEdit,
    QStackedWidget, QLabel, QTabBar, QStyledItemDelegate, QStyle
)

try:
    from PySide6.QtWebEngineWidgets import QWebEngineView
    WEB_ENGINE_AVAILABLE = True
except ImportError:
    WEB_ENGINE_AVAILABLE = False
    QWebEngineView = None
# Force-disable WebEngine in frozen executables to avoid recursive subprocess spawning
if getattr(sys, "frozen", False):
    WEB_ENGINE_AVAILABLE = False
    QWebEngineView = None

class InteractiveTerminal(QWidget):
    """
    An interactive terminal widget that runs a shell process.
    Can be initialized with a startup command to configure the environment.
    """
    outputReceived = Signal(str)
    def __init__(self, startup_command=None, working_directory=None, parent=None):
        super().__init__(parent)
        self.process = QProcess(self)

        self.output_view = QPlainTextEdit(self)
        self.output_view.setFont(QFont("Consolas", 10))
        self.output_view.setStyleSheet("""
            QPlainTextEdit {
                background-color: #121214; 
                color: #E0E2E6; 
                padding: 5px; 
                border: none;
            }
            QScrollBar:vertical {
                background: #1E1F22;
                width: 12px;
                border: none;
                border-radius: 0px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: rgba(85, 85, 85, 0.6);
                border-radius: 0px;
                min-height: 20px;
                margin: 2px;
            }
            QScrollBar::handle:vertical:hover {
                background: rgba(102, 102, 102, 0.9);
            }
            QScrollBar::handle:vertical:pressed {
                background: rgba(119, 119, 119, 1.0);
            }
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {
                height: 0px;
                background: none;
            }
            QScrollBar::add-page:vertical,
            QScrollBar::sub-page:vertical {
                background: none;
            }
            QScrollBar:horizontal {
                background: #1E1F22;
                height: 12px;
                border: none;
                border-radius: 0px;
                margin: 0px;
            }
            QScrollBar::handle:horizontal {
                background: rgba(85, 85, 85, 0.6);
                border-radius: 0px;
                min-width: 20px;
                margin: 2px;
            }
            QScrollBar::handle:horizontal:hover {
                background: rgba(102, 102, 102, 0.9);
            }
            QScrollBar::handle:horizontal:pressed {
                background: rgba(119, 119, 119, 1.0);
            }
            QScrollBar::add-line:horizontal,
            QScrollBar::sub-line:horizontal {
                width: 0px;
                background: none;
            }
            QScrollBar::add-page:horizontal,
            QScrollBar::sub-page:horizontal {
                background: none;
            }
        """)
        self.output_view.setReadOnly(False)
        # Store base font to support Ctrl+0 reset for zoom
        try:
            self._base_font = QFont(self.output_view.font())
        except Exception:
            self._base_font = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.output_view)

        self.process.readyReadStandardOutput.connect(self.handle_stdout)
        self.process.readyReadStandardError.connect(self.handle_stderr)

        self.output_view.keyPressEvent = self.terminal_key_press

        # --- FIX: Set working directory before starting the process ---
        if working_directory and os.path.isdir(working_directory):
            self.process.setWorkingDirectory(working_directory)

        shell_program = "powershell.exe" if sys.platform == "win32" else "bash"
        self.process.start(shell_program)

        # --- NEW: Run startup command if provided ---
        if startup_command:
            self.process.waitForStarted()
            self.process.write((startup_command + "\n").encode())

    def terminal_key_press(self, event):
        """ Handles key presses to send commands to the shell. """
        # VS Code-like zoom shortcuts for terminal: Ctrl + / Ctrl - / Ctrl 0
        try:
            if event.modifiers() & Qt.ControlModifier:
                if event.key() in (Qt.Key_Plus, Qt.Key_Equal):
                    f = self.output_view.font()
                    f.setPointSizeF(f.pointSizeF() + 1)
                    self.output_view.setFont(f)
                    event.accept()
                    return
                if event.key() == Qt.Key_Minus:
                    f = self.output_view.font()
                    f.setPointSizeF(max(1, f.pointSizeF() - 1))
                    self.output_view.setFont(f)
                    event.accept()
                    return
                if event.key() == Qt.Key_0:
                    if getattr(self, '_base_font', None):
                        self.output_view.setFont(self._base_font)
                    event.accept()
                    return
        except Exception:
            pass
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            # On Enter, get the full text and find the last line entered
            full_text = self.output_view.toPlainText()
            last_line = full_text.strip().split('\n')[-1]

            # A simple way to find the actual command after the prompt (e.g., after '>')
            prompt_marker = ">"
            prompt_end_index = last_line.rfind(prompt_marker)
            command = last_line[prompt_end_index + 1:].strip() if prompt_end_index != -1 else last_line

            # Let the text edit handle the newline first
            QPlainTextEdit.keyPressEvent(self.output_view, event)
            # Then write the captured command to the process
            if command:
                self.process.write((command + "\n").encode())
        else:
            # For all other keys, just let the text edit do its normal job
            QPlainTextEdit.keyPressEvent(self.output_view, event)


    def handle_stdout(self):
        data = self.process.readAllStandardOutput().data()
        try:
            import locale as _locale
            enc = (getattr(sys.stdout, 'encoding', None) or _locale.getpreferredencoding(False) or 'utf-8')
        except Exception:
            enc = 'utf-8'
        text = data.decode(enc, errors='replace')
        # Emit full text for internal listeners (e.g., Manage activity parser)
        try:
            self.outputReceived.emit(text)
        except Exception:
            pass
        # Filter [tracer] lines and blank-only lines from the visible console output
        try:
            filtered_lines = [ln for ln in text.splitlines(True) if (not ln.lstrip().startswith('[tracer]') and ln.strip() != '')]
            filtered_text = ''.join(filtered_lines)
            if filtered_text:
                self.output_view.moveCursor(QTextCursor.End)
                self.output_view.insertPlainText(filtered_text)
                self.output_view.moveCursor(QTextCursor.End)
        except Exception:
            # Fallback to raw output if filtering fails
            self.output_view.moveCursor(QTextCursor.End)
            self.output_view.insertPlainText(text)
            self.output_view.moveCursor(QTextCursor.End)

    def handle_stderr(self):
        data = self.process.readAllStandardError().data()
        try:
            import locale as _locale
            enc = (getattr(sys.stderr, 'encoding', None) or _locale.getpreferredencoding(False) or 'utf-8')
        except Exception:
            enc = 'utf-8'
        text = data.decode(enc, errors='replace')
        # Emit full text for internal listeners
        try:
            self.outputReceived.emit(text)
        except Exception:
            pass
        # Filter [tracer] lines and blank-only lines from visible console output
        try:
            filtered_lines = [ln for ln in text.splitlines(True) if (not ln.lstrip().startswith('[tracer]') and ln.strip() != '')]
            filtered_text = ''.join(filtered_lines)
            if filtered_text:
                self.output_view.moveCursor(QTextCursor.End)
                self.output_view.insertPlainText(filtered_text)
                self.output_view.moveCursor(QTextCursor.End)
        except Exception:
            # Fallback
            self.output_view.moveCursor(QTextCursor.End)
            self.output_view.insertPlainText(text)
            self.output_view.moveCursor(QTextCursor.End)

    def kill_process(self):
        """ Kills the terminal's shell process. """
        self.process.kill()
        self.process.waitForFinished()
