"""
Search Panel for A³ Rust Editor
VS Code-like search functionality with live find and replace across all files
"""

import os
import re
from typing import List, Dict, Tuple, Optional
from PySide6.QtCore import (
    Qt, QThread, Signal, QObject, QTimer, QSize, QRect
)
from PySide6.QtGui import (
    QFont, QColor, QIcon, QPixmap, QPainter, QPen, QTextCursor, QTextCharFormat, QPalette
)
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton,
    QTreeWidget, QTreeWidgetItem, QLabel, QCheckBox, QSplitter,
    QTextEdit, QFrame, QScrollArea, QApplication, QMessageBox,
    QStyledItemDelegate, QStyle, QStyleOptionViewItem
)

# Import additional methods from Search2.py
from Search2 import (
    show_replace_preview, hide_replace_preview, replace_current,
    _compile_replace_pattern, _reload_file_in_editor, replace_all,
    replace_all_in_file, replace_single_match
)


class SearchWorker(QThread):
    """Background thread for searching files"""
    result_found = Signal(str, int, str)  # file_path, line_num, line_text
    search_finished = Signal(int)  # total_matches
    
    def __init__(self, root_path: str, search_text: str, case_sensitive: bool, 
                 whole_word: bool, use_regex: bool, file_pattern: str = "*"):
        super().__init__()
        self.root_path = root_path
        self.search_text = search_text
        self.case_sensitive = case_sensitive
        self.whole_word = whole_word
        self.use_regex = use_regex
        self.file_pattern = file_pattern
        self._stop = False
        
    def stop(self):
        self._stop = True
        
    def _compile_pattern(self):
        if self.use_regex:
            flags = 0 if self.case_sensitive else re.IGNORECASE
            return re.compile(self.search_text, flags)
        else:
            escaped = re.escape(self.search_text)
            if self.whole_word:
                escaped = r'\b' + escaped + r'\b'
            flags = 0 if self.case_sensitive else re.IGNORECASE
            return re.compile(escaped, flags)
        
    def run(self):
        """Execute the search"""
        if not self.search_text or not self.root_path:
            self.search_finished.emit(0)
            return
            
        total_matches = 0

        # Prepare search pattern
        try:
            pattern = self._compile_pattern()
        except re.error:
            self.search_finished.emit(0)
            return
        
        # Search through files
        for root, dirs, files in os.walk(self.root_path):
            if self._stop:
                break
                
            # Skip common ignore directories
            dirs[:] = [d for d in dirs if d not in ['.git', '__pycache__', 'node_modules', 
                                                     'target', '.vscode', '.idea', 'venv', 'env']]
            
            for file in files:
                if self._stop:
                    break
                    
                # Filter by file extension (support Rust and Python primarily)
                if not (file.endswith('.rs') or file.endswith('.py') or 
                       file.endswith('.toml') or file.endswith('.txt') or
                       file.endswith('.md') or file.endswith('.json')):
                    continue
                
                file_path = os.path.join(root, file)
                
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        for line_num, line in enumerate(f, 1):
                            if self._stop:
                                break
                            
                            # Find all matches on this line
                            matches = list(pattern.finditer(line))
                            if matches:
                                # Count all matches for total
                                total_matches += len(matches)
                                # But only emit the signal ONCE per line (VS Code behavior)
                                self.result_found.emit(
                                    file_path,
                                    line_num,
                                    line.rstrip('\n').rstrip('\r')
                                )
                except Exception:
                    # Skip files that can't be read
                    continue
        
        self.search_finished.emit(total_matches)


class SearchResultItem(QTreeWidgetItem):
    """Custom tree item for search results"""
    def __init__(self, parent, *, kind: str, file_path: str, 
                 line_num: Optional[int] = None, 
                 line_text: Optional[str] = None,
                 occurrence_index: Optional[int] = None):
        super().__init__(parent)
        self.kind = kind  # 'file' or 'match'
        self.file_path = file_path
        self.line_num = line_num
        self.line_text = line_text
        self.occurrence_index = occurrence_index

        if kind == 'file':
            # File header
            base = os.path.basename(file_path)
            self.setText(0, base)
            self.setToolTip(0, file_path)
            self.setForeground(0, QColor("#E8EAED"))
            font = self.font(0)
            font.setBold(True)
            self.setFont(0, font)
            # Mark as branch by ensuring it can have children
            self.setChildIndicatorPolicy(QTreeWidgetItem.ShowIndicator)
            # Tag data for delegate
            self.setData(0, Qt.UserRole, {
                'type': 'file',
                'file_path': file_path,
            })
        else:
            # Match line item
            display = f"{line_num}: {line_text if line_text is not None else ''}"
            self.setText(0, display)
            self.setForeground(0, QColor("#BDC1C6"))
            self.setToolTip(0, f"Line {line_num}")
            # Tag data for delegate
            self.setData(0, Qt.UserRole, {
                'type': 'match',
                'file_path': file_path,
                'line_num': line_num,
                'line_text': line_text,
                'occurrence_index': occurrence_index,
            })


class ReplacePreviewWidget(QWidget):
    """Widget to preview replace operations"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Header
        header = QLabel("Replace Preview")
        header.setStyleSheet("""
            QLabel {
                background-color: #2C2E33;
                color: #E8EAED;
                padding: 8px;
                font-weight: bold;
                border-bottom: 1px solid #4A4D51;
            }
        """)
        layout.addWidget(header)
        
        # Preview text area
        self.preview_text = QTextEdit()
        self.preview_text.setReadOnly(True)
        self.preview_text.setStyleSheet("""
            QTextEdit {
                background-color: #1E1E1E;
                color: #E8EAED;
                border: none;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 11pt;
            }
            QScrollBar:vertical {
                background: #232323;
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
                background: #232323;
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
        layout.addWidget(self.preview_text)
        
        # Action buttons
        button_layout = QHBoxLayout()
        button_layout.setContentsMargins(8, 8, 8, 8)
        
        self.replace_btn = QPushButton("Replace")
        self.replace_btn.setStyleSheet("""
            QPushButton {
                background-color: #0E639C;
                color: white;
                border: none;
                padding: 6px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1177BB;
            }
            QPushButton:pressed {
                background-color: #0D5A8F;
            }
        """)
        
        self.replace_all_btn = QPushButton("Replace All")
        self.replace_all_btn.setStyleSheet(self.replace_btn.styleSheet())
        
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #3C3C3C;
                color: #E8EAED;
                border: none;
                padding: 6px 16px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #4A4D51;
            }
        """)
        
        button_layout.addWidget(self.replace_btn)
        button_layout.addWidget(self.replace_all_btn)
        button_layout.addStretch()
        button_layout.addWidget(self.cancel_btn)
        
        layout.addLayout(button_layout)
        
    def show_preview(self, file_path: str, line_num: int, original: str, 
                     search_text: str, replace_text: str):
        """Show preview of replacement"""
        # Read context around the line
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                
            start = max(0, line_num - 3)
            end = min(len(lines), line_num + 2)
            
            preview = []
            preview.append(f"File: {file_path}\n")
            preview.append(f"Line {line_num}:\n\n")
            
            for i in range(start, end):
                line = lines[i].rstrip('\n').rstrip('\r')
                if i == line_num - 1:
                    # Show before
                    preview.append(f"- {i+1}: {line}\n")
                    # Show after
                    replaced = line.replace(search_text, replace_text)
                    preview.append(f"+ {i+1}: {replaced}\n")
                else:
                    preview.append(f"  {i+1}: {line}\n")
            
            self.preview_text.setPlainText(''.join(preview))
            
        except Exception as e:
            self.preview_text.setPlainText(f"Error loading preview: {e}")


class SearchResultDelegate(QStyledItemDelegate):
    """Custom delegate to draw highlighted matches in the results tree like VS Code"""
    def __init__(self, panel: 'SearchPanel', parent=None):
        super().__init__(parent)
        self.panel = panel
        # VS Code-like find match highlight color (orange/brown with transparency)
        self.highlight_color = QColor(234, 92, 0, 110)  # ~#EA5C00 with alpha
        # VS Code-like replace colors
        self.remove_color = QColor(255, 0, 0, 80)  # Red with transparency for removed text
        self.add_color = QColor(0, 255, 0, 80)  # Green with transparency for added text
        # Track hovered item for buttons
        self.hovered_item = None
        self.close_button_rect = QRect()
        self.close_button_hovered = False
        self.replace_button_rect = QRect()
        self.replace_button_hovered = False
        
        # Enable mouse tracking on the tree widget
        if parent:
            parent.setMouseTracking(True)
            parent.viewport().setMouseTracking(True)
            parent.viewport().installEventFilter(self)

    def _compile_pattern(self):
        text = self.panel.search_input.text()
        if not text:
            return None
        try:
            if self.panel.regex_cb.isChecked():
                flags = 0 if self.panel.case_sensitive_cb.isChecked() else re.IGNORECASE
                return re.compile(text, flags)
            else:
                escaped = re.escape(text)
                if self.panel.whole_word_cb.isChecked():
                    escaped = r'\b' + escaped + r'\b'
                flags = 0 if self.panel.case_sensitive_cb.isChecked() else re.IGNORECASE
                return re.compile(escaped, flags)
        except re.error:
            return None

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index):
        data = index.data(Qt.UserRole)
        # Fallback to default for safety
        if not isinstance(data, dict):
            return super().paint(painter, option, index)

        # Prepare style option
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        style = opt.widget.style() if opt.widget else QApplication.style()

        # Draw background/selection/etc. without text
        text_backup = opt.text
        opt.text = ""
        style.drawControl(QStyle.CE_ItemViewItem, opt, painter, opt.widget)

        # Determine text to draw and any highlight ranges
        painter.save()
        painter.setRenderHint(QPainter.TextAntialiasing)

        # Use semi-transparent white for selected items (even when not focused)
        if option.state & QStyle.State_Selected:
            text_color = QColor(255, 255, 255, 128)  # White with 50% opacity (0.5 * 255 = 128)
        else:
            text_color = opt.palette.color(QPalette.Text)
        painter.setPen(text_color)

        font = opt.font
        painter.setFont(font)
        fm = painter.fontMetrics()

        if data.get('type') == 'file':
            # File item - adjust for icon space
            icon_size = 20
            icon_padding = 4
            rect = opt.rect.adjusted(icon_size + icon_padding + 6, 0, -6, 0)
            # Show filename only (icon is already shown by Qt)
            base = os.path.basename(data.get('file_path', ''))
            painter.drawText(rect, Qt.AlignVCenter | Qt.TextSingleLine, base)
            
            # Draw buttons for file items when hovered or selected (like VS Code)
            tree = self.parent()
            if tree:
                item = tree.itemFromIndex(index)
                show_buttons = False
                
                # Show buttons if item is hovered or selected
                if item == self.hovered_item:
                    show_buttons = True
                elif option.state & QStyle.State_Selected:
                    show_buttons = True
                
                # Always show replace and close buttons for files (like VS Code)
                if show_buttons:
                    button_size = 16
                    button_spacing = 4
                    
                    # Calculate button positions from right to left
                    # Close button is always rightmost
                    close_x = opt.rect.right() - button_size - 4
                    close_y = opt.rect.y() + (opt.rect.height() - button_size) // 2
                    close_rect = QRect(close_x, close_y, button_size, button_size)
                    
                    # Replace All button is to the left of close button
                    replace_x = close_x - button_size - button_spacing
                    replace_y = close_y
                    replace_rect = QRect(replace_x, replace_y, button_size, button_size)
                    
                    # Draw replace button background when hovered
                    if self.replace_button_hovered and item == self.hovered_item:
                        painter.setBrush(QColor(14, 99, 156))  # Blue when hovered
                        painter.setPen(Qt.NoPen)
                        painter.drawRoundedRect(replace_rect, 3, 3)
                    
                    # Draw replace icon (R letter for Replace All)
                    painter.setPen(QPen(QColor(204, 204, 204), 1.5))
                    painter.setFont(QFont("Arial", 9, QFont.Bold))
                    painter.drawText(replace_rect, Qt.AlignCenter, "R")
                    
                    # Draw close button background when hovered
                    if self.close_button_hovered and item == self.hovered_item:
                        painter.setBrush(QColor(90, 93, 94))  # Darker gray when hovered
                        painter.setPen(Qt.NoPen)
                        painter.drawEllipse(close_rect)
                    
                    # Draw X icon for close button
                    painter.setPen(QPen(QColor(204, 204, 204), 1.5))  # Light gray X
                    padding = 4
                    x1 = close_rect.left() + padding
                    y1 = close_rect.top() + padding
                    x2 = close_rect.right() - padding
                    y2 = close_rect.bottom() - padding
                    
                    # Draw X
                    painter.drawLine(x1, y1, x2, y2)
                    painter.drawLine(x2, y1, x1, y2)
        else:
            # Match item - compensate for tree indentation to align with file name
            # Tree indentation is 20px, so we need to move left by that amount
            icon_size = 20
            icon_padding = 4
            tree_indent = 20
            rect = opt.rect.adjusted(icon_size + icon_padding + 6 - tree_indent, 0, -6, 0)
            line_num = data.get('line_num')
            line_text = data.get('line_text') or ""
            occurrence_index = data.get('occurrence_index', 0)
            prefix = f"{line_num}: "
            display = prefix + line_text

            # Check if we should show replace preview
            replace_text = self.panel.replace_input.text()
            show_replace = bool(replace_text)
            
            # Compute highlight range for the match
            pattern = self._compile_pattern()
            
            if pattern is not None and not show_replace:
                # Normal search mode - just highlight the match
                painter.drawText(rect, Qt.AlignVCenter | Qt.TextSingleLine, display)
                
                # Find the first match in the displayed (possibly truncated) line
                match_spans = []
                try:
                    for m in pattern.finditer(line_text):
                        match_spans.append((m.start(), m.end()))
                except re.error:
                    match_spans = []
                
                # For truncated text, we only highlight the first match shown
                if match_spans:
                    start, end = match_spans[0]
                    # Compute pixel x positions
                    prefix_width = fm.horizontalAdvance(prefix)
                    left_text = line_text[:start]
                    match_text = line_text[start:end]
                    left_w = fm.horizontalAdvance(left_text)
                    match_w = fm.horizontalAdvance(match_text)

                    x = rect.x() + prefix_width + left_w
                    y = rect.y()
                    h = rect.height()
                    # Slight vertical padding inside line rect
                    pad = max(0, (h - fm.height()) // 2)
                    highlight_rect = QRect(int(x), int(y + pad), int(match_w), int(fm.height()))

                    # Draw highlight underlay
                    painter.fillRect(highlight_rect, self.highlight_color)

                # Redraw text on top to keep crisp glyphs over highlight
                painter.setPen(text_color)
                painter.drawText(rect, Qt.AlignVCenter | Qt.TextSingleLine, display)
                
            elif pattern is not None and show_replace:
                # Replace preview mode - show old text with red bg and new text with green bg
                match_spans = []
                try:
                    for m in pattern.finditer(line_text):
                        match_spans.append((m.start(), m.end()))
                except re.error:
                    match_spans = []
                
                if match_spans:
                    start, end = match_spans[0]
                    match_text = line_text[start:end]
                    
                    # Split the line into: before_match | match | after_match
                    before_match = line_text[:start]
                    after_match = line_text[end:]
                    
                    # Build the display with replacement
                    prefix_width = fm.horizontalAdvance(prefix)
                    before_w = fm.horizontalAdvance(before_match)
                    match_w = fm.horizontalAdvance(match_text)
                    replace_w = fm.horizontalAdvance(replace_text)
                    
                    x_start = rect.x() + prefix_width
                    y = rect.y()
                    h = rect.height()
                    pad = max(0, (h - fm.height()) // 2)
                    
                    # Draw prefix (line number)
                    painter.setPen(text_color)
                    painter.drawText(rect.x(), y, prefix_width, h, Qt.AlignVCenter, prefix)
                    
                    # Draw text before match
                    painter.drawText(x_start, y, before_w, h, Qt.AlignVCenter, before_match)
                    
                    # Draw old text with red background (strikethrough)
                    old_x = x_start + before_w
                    old_rect = QRect(int(old_x), int(y + pad), int(match_w), int(fm.height()))
                    painter.fillRect(old_rect, self.remove_color)
                    
                    # Draw strikethrough line (white)
                    painter.setPen(QPen(QColor(255, 255, 255), 1))
                    mid_y = int(y + h / 2)
                    painter.drawLine(int(old_x), mid_y, int(old_x + match_w), mid_y)
                    
                    # Draw old text
                    painter.setPen(text_color)
                    painter.drawText(int(old_x), y, int(match_w), h, Qt.AlignVCenter, match_text)
                    
                    # Draw arrow/separator
                    arrow_x = old_x + match_w + 4
                    arrow_text = " → "
                    arrow_w = fm.horizontalAdvance(arrow_text)
                    painter.setPen(QColor("#BDC1C6"))
                    painter.drawText(int(arrow_x), y, int(arrow_w), h, Qt.AlignVCenter, arrow_text)
                    
                    # Draw new text with green background
                    new_x = arrow_x + arrow_w
                    new_rect = QRect(int(new_x), int(y + pad), int(replace_w), int(fm.height()))
                    painter.fillRect(new_rect, self.add_color)
                    painter.setPen(text_color)
                    painter.drawText(int(new_x), y, int(replace_w), h, Qt.AlignVCenter, replace_text)
                    
                    # Draw text after match
                    after_x = new_x + replace_w + 4
                    painter.drawText(int(after_x), y, rect.width() - int(after_x - rect.x()), h, 
                                   Qt.AlignVCenter | Qt.TextSingleLine, after_match)
                else:
                    # No match found, just draw normally
                    painter.drawText(rect, Qt.AlignVCenter | Qt.TextSingleLine, display)
            else:
                # No pattern, just draw text
                painter.drawText(rect, Qt.AlignVCenter | Qt.TextSingleLine, display)
            
            # Draw buttons for match items when hovered or selected
            tree = self.parent()
            if tree:
                item = tree.itemFromIndex(index)
                show_buttons = False
                
                # Show buttons if item is hovered or selected
                if item == self.hovered_item:
                    show_buttons = True
                elif option.state & QStyle.State_Selected:
                    show_buttons = True
                
                # Always show replace button (even if replace text is empty, like VS Code)
                if show_buttons:
                    button_size = 16
                    button_spacing = 4
                    
                    # Calculate button positions from right to left
                    # Close button is always rightmost
                    close_x = opt.rect.right() - button_size - 4
                    close_y = opt.rect.y() + (opt.rect.height() - button_size) // 2
                    close_rect = QRect(close_x, close_y, button_size, button_size)
                    
                    # Replace button is to the left of close button (always show like VS Code)
                    replace_x = close_x - button_size - button_spacing
                    replace_y = close_y
                    replace_rect = QRect(replace_x, replace_y, button_size, button_size)
                    
                    # Draw replace button background when hovered
                    if self.replace_button_hovered and item == self.hovered_item:
                        painter.setBrush(QColor(14, 99, 156))  # Blue when hovered
                        painter.setPen(Qt.NoPen)
                        painter.drawRoundedRect(replace_rect, 3, 3)
                    
                    # Draw replace icon (R letter)
                    painter.setPen(QPen(QColor(204, 204, 204), 1.5))
                    painter.setFont(QFont("Arial", 9, QFont.Bold))
                    painter.drawText(replace_rect, Qt.AlignCenter, "R")
                    
                    # Draw close button background when hovered
                    if self.close_button_hovered and item == self.hovered_item:
                        painter.setBrush(QColor(90, 93, 94))  # Darker gray when hovered
                        painter.setPen(Qt.NoPen)
                        painter.drawEllipse(close_rect)
                    
                    # Draw X icon for close button
                    painter.setPen(QPen(QColor(204, 204, 204), 1.5))  # Light gray X
                    padding = 4
                    x1 = close_rect.left() + padding
                    y1 = close_rect.top() + padding
                    x2 = close_rect.right() - padding
                    y2 = close_rect.bottom() - padding
                    
                    # Draw X
                    painter.drawLine(x1, y1, x2, y2)
                    painter.drawLine(x2, y1, x1, y2)

        painter.restore()

    def sizeHint(self, option, index):
        # Use default size hint
        return super().sizeHint(option, index)
    
    def eventFilter(self, obj, event):
        """Handle mouse events for buttons"""
        from PySide6.QtCore import QEvent
        from PySide6.QtGui import QMouseEvent
        
        if event.type() == QEvent.MouseMove:
            if isinstance(event, QMouseEvent):
                tree = self.parent()
                if tree:
                    # Get item at mouse position
                    pos = event.pos()
                    item = tree.itemAt(pos)
                    
                    # Update hovered item
                    old_hovered = self.hovered_item
                    self.hovered_item = item
                    
                    # Check if mouse is over buttons (both match and file items)
                    if item and isinstance(item, SearchResultItem):
                        index = tree.indexFromItem(item)
                        rect = tree.visualRect(index)
                        
                        button_size = 16
                        button_spacing = 4
                        
                        # Close button is on the right side
                        close_x = rect.right() - button_size - 4
                        close_y = rect.y() + (rect.height() - button_size) // 2
                        self.close_button_rect = QRect(close_x, close_y, button_size, button_size)
                        
                        # Replace button is to the left of close button (always show like VS Code)
                        replace_x = close_x - button_size - button_spacing
                        replace_y = close_y
                        self.replace_button_rect = QRect(replace_x, replace_y, button_size, button_size)
                        
                        # Check if mouse is over buttons
                        old_close_hovered = self.close_button_hovered
                        old_replace_hovered = self.replace_button_hovered
                        
                        self.close_button_hovered = self.close_button_rect.contains(pos)
                        self.replace_button_hovered = self.replace_button_rect.contains(pos)
                        
                        # Repaint if hover state changed
                        if (old_close_hovered != self.close_button_hovered or 
                            old_replace_hovered != self.replace_button_hovered or 
                            old_hovered != self.hovered_item):
                            tree.viewport().update(rect)
                    else:
                        self.close_button_hovered = False
                        self.replace_button_hovered = False
                        self.close_button_rect = QRect()
                        self.replace_button_rect = QRect()
                        
                        # Repaint old hovered item if changed
                        if old_hovered and old_hovered != item:
                            old_index = tree.indexFromItem(old_hovered)
                            tree.viewport().update(tree.visualRect(old_index))
        
        elif event.type() == QEvent.MouseButtonPress:
            if isinstance(event, QMouseEvent):
                tree = self.parent()
                if tree and self.hovered_item and isinstance(self.hovered_item, SearchResultItem):
                    # Check which button was clicked
                    if self.replace_button_hovered:
                        # Replace button clicked
                        if self.hovered_item.kind == 'file':
                            # For file items: Replace All in this file
                            self.panel.replace_all_in_file(self.hovered_item.file_path)
                        else:
                            # For match items: Replace single match
                            self.panel.replace_single_match(self.hovered_item)
                        self.hovered_item = None
                        self.replace_button_hovered = False
                        self.replace_button_rect = QRect()
                        return True  # Consume the event
                    elif self.close_button_hovered:
                        # Close button clicked
                        if self.hovered_item.kind == 'file':
                            # For file items: Remove entire file from results
                            index = tree.indexOfTopLevelItem(self.hovered_item)
                            if index >= 0:
                                tree.takeTopLevelItem(index)
                                # Update counts
                                file_path = self.hovered_item.file_path
                                if file_path in self.panel.per_file_counts:
                                    del self.panel.per_file_counts[file_path]
                                if file_path in self.panel.search_results:
                                    del self.panel.search_results[file_path]
                                # Update summary
                                total_matches = sum(self.panel.per_file_counts.values())
                                file_count = len(self.panel.per_file_counts)
                                if total_matches > 0:
                                    self.panel.summary_label.setText(f"{total_matches} result{'s' if total_matches != 1 else ''} in {file_count} file{'s' if file_count != 1 else ''}")
                                    self.panel.status_label.setText(f"Found {total_matches} match{'es' if total_matches != 1 else ''} in {file_count} file{'s' if file_count != 1 else ''}")
                                else:
                                    self.panel.summary_label.setVisible(False)
                                    self.panel.status_label.setText("No results")
                        else:
                            # For match items: Remove single result
                            self.panel._remove_search_result(self.hovered_item)
                        self.hovered_item = None
                        self.close_button_hovered = False
                        self.close_button_rect = QRect()
                        return True  # Consume the event
        
        elif event.type() == QEvent.Leave:
            # Mouse left the widget
            tree = self.parent()
            if tree and self.hovered_item:
                old_item = self.hovered_item
                self.hovered_item = None
                self.close_button_hovered = False
                self.replace_button_hovered = False
                self.close_button_rect = QRect()
                self.replace_button_rect = QRect()
                if old_item:
                    old_index = tree.indexFromItem(old_item)
                    tree.viewport().update(tree.visualRect(old_index))
        
        return super().eventFilter(obj, event)


class SearchPanel(QWidget):
    """Main search panel widget"""
    
    # Signals
    file_selected = Signal(str, int)  # file_path, line_number
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.root_path = ""
        self.search_worker: Optional[SearchWorker] = None
        self.search_results: Dict[str, List[Tuple[int, str]]] = {}  # file_path -> [(line_num, line_text), ...]
        self.per_file_counts: Dict[str, int] = {}
        self.line_occurrence_next: Dict[Tuple[str, int], int] = {}
        self.current_preview_item: Optional[SearchResultItem] = None

        # Live search debounce timer
        self.live_timer = QTimer(self)
        self.live_timer.setSingleShot(True)
        self.live_timer.setInterval(300)  # ms
        self.live_timer.timeout.connect(self.start_search)

        self.setup_ui()
        
    def setup_ui(self):
        """Setup the user interface"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Search input section
        search_section = QFrame()
        search_section.setStyleSheet("""
            QFrame {
                background-color: #1E1E1E;
                border-bottom: 1px solid #3C3C3C;
            }
        """)
        search_layout = QVBoxLayout(search_section)
        search_layout.setContentsMargins(12, 12, 12, 12)
        search_layout.setSpacing(8)
        
        # Search input
        search_input_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search (live)")
        self.search_input.setStyleSheet("""
            QLineEdit {
                background-color: #3C3C3C;
                color: #E8EAED;
                border: 1px solid #4A4D51;
                border-radius: 4px;
                padding: 6px 8px;
                font-size: 13px;
            }
            QLineEdit:focus {
                border: 1px solid #007ACC;
            }
        """)
        # Live search as you type (debounced)
        self.search_input.textChanged.connect(self._on_search_text_changed)
        self.search_input.returnPressed.connect(self.start_search)
        search_input_layout.addWidget(self.search_input)
        
        # Search button
        self.search_btn = QPushButton()
        self.search_btn.setIcon(self.create_search_icon())
        self.search_btn.setFixedSize(32, 32)
        self.search_btn.setStyleSheet("""
            QPushButton {
                background-color: #0E639C;
                border: none;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #1177BB;
            }
            QPushButton:pressed {
                background-color: #0D5A8F;
            }
        """)
        self.search_btn.clicked.connect(self.start_search)
        search_input_layout.addWidget(self.search_btn)
        
        search_layout.addLayout(search_input_layout)
        
        # Replace input
        replace_input_layout = QHBoxLayout()
        self.replace_input = QLineEdit()
        self.replace_input.setPlaceholderText("Replace")
        self.replace_input.setStyleSheet(self.search_input.styleSheet())
        # Trigger repaint when replace text changes to show inline preview
        self.replace_input.textChanged.connect(lambda: self.results_tree.viewport().update())
        replace_input_layout.addWidget(self.replace_input)
        
        # Replace button
        self.replace_btn = QPushButton()
        self.replace_btn.setIcon(self.create_replace_icon())
        self.replace_btn.setFixedSize(32, 32)
        self.replace_btn.setStyleSheet(self.search_btn.styleSheet())
        self.replace_btn.clicked.connect(self.show_replace_preview)
        replace_input_layout.addWidget(self.replace_btn)
        
        search_layout.addLayout(replace_input_layout)
        
        # Search options
        options_layout = QHBoxLayout()
        options_layout.setSpacing(12)
        
        self.case_sensitive_cb = QCheckBox("Aa")
        self.case_sensitive_cb.setToolTip("Match Case")
        self.case_sensitive_cb.setStyleSheet("""
            QCheckBox {
                color: #BDC1C6;
                spacing: 4px;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border: 1px solid #4A4D51;
                border-radius: 3px;
                background-color: #3C3C3C;
            }
            QCheckBox::indicator:checked {
                background-color: #007ACC;
                border-color: #007ACC;
            }
        """)
        
        self.whole_word_cb = QCheckBox("Ab")
        self.whole_word_cb.setToolTip("Match Whole Word")
        self.whole_word_cb.setStyleSheet(self.case_sensitive_cb.styleSheet())
        
        self.regex_cb = QCheckBox(".*")
        self.regex_cb.setToolTip("Use Regular Expression")
        self.regex_cb.setStyleSheet(self.case_sensitive_cb.styleSheet())
        
        # Changing options should trigger live search/delegate repaint
        self.case_sensitive_cb.toggled.connect(self._on_search_option_changed)
        self.whole_word_cb.toggled.connect(self._on_search_option_changed)
        self.regex_cb.toggled.connect(self._on_search_option_changed)
        
        options_layout.addWidget(self.case_sensitive_cb)
        options_layout.addWidget(self.whole_word_cb)
        options_layout.addWidget(self.regex_cb)
        options_layout.addStretch()
        
        search_layout.addLayout(options_layout)
        
        main_layout.addWidget(search_section)
        
        # Summary label (shows "X results in Y files")
        self.summary_label = QLabel("")
        self.summary_label.setStyleSheet("""
            QLabel {
                background-color: #1E1E1E;
                color: #BDC1C6;
                padding: 6px 12px;
                font-size: 11px;
            }
        """)
        self.summary_label.setVisible(False)
        main_layout.addWidget(self.summary_label)
        
        # Splitter for results and preview
        self.splitter = QSplitter(Qt.Vertical)
        
        # Results tree
        self.results_tree = QTreeWidget()
        self.results_tree.setHeaderHidden(True)
        self.results_tree.setIndentation(20)  # Minimal indentation for expand/collapse arrows
        self.results_tree.setStyleSheet("""
            QTreeWidget {
                background-color: #1E1E1E;
                color: #E8EAED;
                border: none;
                outline: none;
                font-family: 'Consolas', monospace;
                font-size: 10pt;
            }
            QTreeWidget::item {
                padding: 4px;
                border: none;
            }
            QTreeWidget::item:hover {
                background-color: #2C2E33;
            }
            QTreeWidget::item:selected {
                background-color: #094771;
                color: #FFFFFF;
            }
            QTreeWidget::branch {
                background-color: #1E1E1E;
            }
            QTreeWidget::branch:has-children:closed {
                image: url(img/arrow-right.svg);
            }
            QTreeWidget::branch:has-children:open {
                image: url(img/arrow-down.svg);
            }
            QScrollBar:vertical {
                background: #232323;
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
                background: #232323;
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
        self.results_tree.itemClicked.connect(self.on_result_clicked)
        self.results_tree.itemDoubleClicked.connect(self.on_result_double_clicked)
        # Attach custom delegate for VS Code-like highlight
        self.results_tree.setItemDelegate(SearchResultDelegate(self, self.results_tree))

        self.splitter.addWidget(self.results_tree)
        
        # Replace preview (initially hidden)
        self.replace_preview = ReplacePreviewWidget()
        self.replace_preview.setVisible(False)
        self.replace_preview.replace_btn.clicked.connect(self.replace_current)
        self.replace_preview.replace_all_btn.clicked.connect(self.replace_all)
        self.replace_preview.cancel_btn.clicked.connect(self.hide_replace_preview)
        self.splitter.addWidget(self.replace_preview)
        
        main_layout.addWidget(self.splitter)
        
        # Status footer (better styled)
        self.status_label = QLabel("Type to search across files")
        self.status_label.setStyleSheet("""
            QLabel {
                background-color: #252526;
                color: #BDC1C6;
                padding: 8px 12px;
                font-size: 11px;
                border-top: 1px solid #3C3C3C;
            }
        """)
        main_layout.addWidget(self.status_label)
        
    def _on_search_text_changed(self, _):
        # Debounce live search; also cancel any running worker quickly
        if self.search_worker and self.search_worker.isRunning():
            self.search_worker.stop()
        self.live_timer.start()

    def _on_search_option_changed(self, _):
        # Re-run search with new options (debounced)
        if self.search_worker and self.search_worker.isRunning():
            self.search_worker.stop()
        self.live_timer.start()
        # Also repaint results to update highlight behavior immediately
        self.results_tree.viewport().update()
        
    def create_search_icon(self) -> QIcon:
        """Create a search icon"""
        pixmap = QPixmap(24, 24)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Draw magnifying glass
        painter.setPen(QPen(QColor("#FFFFFF"), 2))
        painter.drawEllipse(4, 4, 12, 12)
        painter.drawLine(14, 14, 20, 20)
        
        painter.end()
        return QIcon(pixmap)
        
    def create_replace_icon(self) -> QIcon:
        """Create a replace icon"""
        pixmap = QPixmap(24, 24)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Draw replace arrows
        painter.setPen(QPen(QColor("#FFFFFF"), 2))
        painter.drawLine(4, 8, 20, 8)
        painter.drawLine(16, 4, 20, 8)
        painter.drawLine(16, 12, 20, 8)
        
        painter.drawLine(20, 16, 4, 16)
        painter.drawLine(8, 12, 4, 16)
        painter.drawLine(8, 20, 4, 16)
        
        painter.end()
        return QIcon(pixmap)
        
    def set_root_path(self, path: str):
        """Set the root path for searching"""
        self.root_path = path
        
    def _reset_results_view(self):
        self.results_tree.clear()
        self.search_results.clear()
        self.per_file_counts.clear()
        self.line_occurrence_next.clear()
        self.current_preview_item = None

    def start_search(self):
        """Start a new search (live or manual)"""
        search_text = self.search_input.text()
        # Stop any existing search
        if self.search_worker and self.search_worker.isRunning():
            self.search_worker.stop()
            self.search_worker.wait()

        if not search_text:
            self._reset_results_view()
            self.status_label.setText("Type to search across files")
            self.summary_label.setVisible(False)
            return
            
        if not self.root_path or not os.path.isdir(self.root_path):
            self.status_label.setText("No folder opened. Please open a folder first.")
            return
        
        # Clear previous results
        self._reset_results_view()
        self.status_label.setText("Searching…")
        
        # Start new search
        self.search_worker = SearchWorker(
            self.root_path,
            search_text,
            self.case_sensitive_cb.isChecked(),
            self.whole_word_cb.isChecked(),
            self.regex_cb.isChecked()
        )
        self.search_worker.result_found.connect(self.add_search_result)
        self.search_worker.search_finished.connect(self.search_completed)
        self.search_worker.start()
        
    def _get_file_icon(self, file_path: str) -> QIcon:
        """Get appropriate icon for file type"""
        name_lower = os.path.basename(file_path).lower()
        ext = os.path.splitext(file_path)[1].lower()
        
        # Specific file name matches
        if name_lower == "cargo.toml":
            return QIcon("img/Setting.png")
        if name_lower == "cargo.lock":
            return self._create_lock_icon()
        
        # Extension-based icons
        if ext == ".rs":
            return self._create_rust_icon()
        elif ext == ".py":
            return QIcon("img/python.png")
        elif ext == ".json":
            return self._create_json_icon()
        elif ext == ".toml":
            return QIcon("img/Setting.png")
        elif ext == ".md":
            return self._create_md_icon()
        elif ext == ".txt":
            return self._create_txt_icon()
        else:
            return self._create_generic_icon()
    
    def _create_rust_icon(self) -> QIcon:
        """Create Rust icon with 'R' letter"""
        pixmap = QPixmap(24, 24)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QPen(QColor("#2C2E33"), 0))
        painter.setBrush(QColor("#1E1F22"))
        painter.drawEllipse(1, 1, 22, 22)
        painter.setPen(QPen(QColor("#DEA584"), 2))
        font = QFont()
        font.setBold(True)
        font.setPointSize(14)
        painter.setFont(font)
        painter.drawText(QRect(0, 0, 24, 24), Qt.AlignCenter, "R")
        painter.end()
        return QIcon(pixmap)
    
    def _create_json_icon(self) -> QIcon:
        """Create JSON icon"""
        pixmap = QPixmap(24, 24)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QPen(QColor("#FFF172"), 2))
        font = QFont()
        font.setPointSize(16)
        painter.setFont(font)
        painter.drawText(QRect(0, 0, 24, 24), Qt.AlignCenter, "{ }")
        painter.end()
        return QIcon(pixmap)
    
    def _create_lock_icon(self) -> QIcon:
        """Create lock icon for .lock files"""
        pixmap = QPixmap(24, 24)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QPen(QColor("#9AA0A6"), 2))
        painter.setBrush(Qt.NoBrush)
        painter.drawArc(QRect(7, 5, 10, 8), 0, 180 * 16)
        painter.setPen(QPen(QColor("#9AA0A6"), 1))
        painter.setBrush(QColor("#F1C40F"))
        painter.drawRoundedRect(6, 10, 12, 10, 3, 3)
        painter.setPen(QPen(QColor("#5D4037"), 2))
        painter.drawPoint(12, 15)
        painter.end()
        return QIcon(pixmap)
    
    def _create_md_icon(self) -> QIcon:
        """Create Markdown icon"""
        pixmap = QPixmap(24, 24)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QPen(QColor("#519ABA"), 2))
        font = QFont()
        font.setBold(True)
        font.setPointSize(14)
        painter.setFont(font)
        painter.drawText(QRect(0, 0, 24, 24), Qt.AlignCenter, "M")
        painter.end()
        return QIcon(pixmap)
    
    def _create_txt_icon(self) -> QIcon:
        """Create text file icon"""
        pixmap = QPixmap(24, 24)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QPen(QColor("#BDC1C6"), 2))
        font = QFont()
        font.setPointSize(14)
        painter.setFont(font)
        painter.drawText(QRect(0, 0, 24, 24), Qt.AlignCenter, "T")
        painter.end()
        return QIcon(pixmap)
    
    def _create_generic_icon(self) -> QIcon:
        """Create generic file icon"""
        pixmap = QPixmap(24, 24)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QPen(QColor("#9AA0A6"), 1))
        painter.setBrush(QColor("#3C3C3C"))
        painter.drawRoundedRect(4, 2, 16, 20, 2, 2)
        painter.drawLine(7, 7, 17, 7)
        painter.drawLine(7, 11, 17, 11)
        painter.drawLine(7, 15, 14, 15)
        painter.end()
        return QIcon(pixmap)
    
    def _get_or_create_file_item(self, file_path: str) -> SearchResultItem:
        # Check existing top-level items
        for i in range(self.results_tree.topLevelItemCount()):
            item = self.results_tree.topLevelItem(i)
            if isinstance(item, SearchResultItem) and item.kind == 'file' and item.file_path == file_path:
                return item
        # Create new
        file_item = SearchResultItem(self.results_tree, kind='file', file_path=file_path)
        file_item.setExpanded(True)
        # Set file icon
        file_item.setIcon(0, self._get_file_icon(file_path))
        return file_item

    def _update_file_item_text(self, file_item: SearchResultItem):
        base = os.path.basename(file_item.file_path)
        file_item.setText(0, base)

    def _get_truncated_line_text(self, line_text: str, search_text: str, occurrence_index: int, max_length: int = 120) -> tuple:
        """
        Truncate line text to show the match with context, like VS Code.
        Returns (truncated_text, adjusted_match_start, show_ellipsis_start)
        """
        # Strip leading/trailing whitespace for display
        line_text = line_text.strip()
        
        if len(line_text) <= max_length:
            return line_text, None, False
        
        # Find the match position
        try:
            if self.regex_cb.isChecked():
                flags = 0 if self.case_sensitive_cb.isChecked() else re.IGNORECASE
                pattern = re.compile(search_text, flags)
            else:
                escaped = re.escape(search_text)
                if self.whole_word_cb.isChecked():
                    escaped = r'\b' + escaped + r'\b'
                flags = 0 if self.case_sensitive_cb.isChecked() else re.IGNORECASE
                pattern = re.compile(escaped, flags)
            
            matches = list(pattern.finditer(line_text))
            if not matches or occurrence_index >= len(matches):
                # Fallback: just truncate from start with ellipsis at end
                return line_text[:max_length] + "...", None, False
            
            match = matches[occurrence_index]
            match_start = match.start()
            match_end = match.end()
            match_length = match_end - match_start
            
            # Calculate how much we can show
            # Reserve 3 chars for "..." at start if needed
            context_before = 15  # characters before match
            
            # Determine start position
            start_pos = max(0, match_start - context_before)
            
            # Check if we need ellipsis at start
            show_ellipsis_start = start_pos > 0
            
            if show_ellipsis_start:
                # We're truncating from start, so reserve space for "..."
                # Show: "..." + context_before + match + rest (up to max_length total)
                available_for_content = max_length - 3  # -3 for "..."
                end_pos = min(len(line_text), start_pos + available_for_content)
                truncated = "..." + line_text[start_pos:end_pos]
            else:
                # Starting from beginning
                end_pos = min(len(line_text), max_length)
                truncated = line_text[start_pos:end_pos]
            
            # Check if we need ellipsis at end
            show_ellipsis_end = end_pos < len(line_text)
            if show_ellipsis_end:
                # Trim a bit to add "..." at end
                if len(truncated) > max_length - 3:
                    truncated = truncated[:max_length - 3]
                truncated = truncated + "..."
            
            return truncated, None, show_ellipsis_start
            
        except Exception as e:
            # Fallback on error
            return line_text[:max_length] + "...", None, False
    
    def add_search_result(self, file_path: str, line_num: int, line_text: str):
        """Add a search result to the tree"""
        # Track per-file count and results
        self.search_results.setdefault(file_path, [])
        self.search_results[file_path].append((line_num, line_text))
        self.per_file_counts[file_path] = self.per_file_counts.get(file_path, 0) + 1
        
        # Get/create file item
        file_item = self._get_or_create_file_item(file_path)
        self._update_file_item_text(file_item)

        # Determine occurrence index for this line within this file
        key = (file_path, line_num)
        occ_index = self.line_occurrence_next.get(key, 0)
        self.line_occurrence_next[key] = occ_index + 1
        
        # Truncate long lines to show match with context
        search_text = self.search_input.text()
        truncated_text, adjusted_start, has_ellipsis = self._get_truncated_line_text(
            line_text, search_text, occ_index
        )
        
        # Add match item
        match_item = SearchResultItem(
            file_item,
            kind='match',
            file_path=file_path,
            line_num=line_num,
            line_text=truncated_text,  # Use truncated text for display
            occurrence_index=occ_index,
        )
        # Store original line text in data for reference
        match_item.setData(0, Qt.UserRole + 1, {
            'original_text': line_text,
            'truncated_text': truncated_text,
            'adjusted_start': adjusted_start,
            'has_ellipsis': has_ellipsis
        })
        
        # Ensure delegate has latest data: update viewport
        # (painting will use UserRole data and current search options)
    
    def _remove_search_result(self, item: SearchResultItem):
        """Remove a single search result from the tree"""
        if not isinstance(item, SearchResultItem) or item.kind != 'match':
            return
        
        try:
            file_path = item.file_path
            parent = item.parent()
            
            if parent:
                # Remove from tree
                parent.removeChild(item)
                
                # Update per-file count
                if file_path in self.per_file_counts:
                    self.per_file_counts[file_path] = max(0, self.per_file_counts[file_path] - 1)
                    
                    # If no more results for this file, remove the file item
                    if self.per_file_counts[file_path] == 0:
                        index = self.results_tree.indexOfTopLevelItem(parent)
                        if index >= 0:
                            self.results_tree.takeTopLevelItem(index)
                        del self.per_file_counts[file_path]
                        if file_path in self.search_results:
                            del self.search_results[file_path]
                    else:
                        # Update file item text to show new count
                        if isinstance(parent, SearchResultItem) and parent.kind == 'file':
                            self._update_file_item_text(parent)
                
                # Update summary
                total_matches = sum(self.per_file_counts.values())
                file_count = len(self.per_file_counts)
                if total_matches > 0:
                    self.summary_label.setText(f"{total_matches} result{'s' if total_matches != 1 else ''} in {file_count} file{'s' if file_count != 1 else ''}")
                    self.status_label.setText(f"Found {total_matches} match{'es' if total_matches != 1 else ''} in {file_count} file{'s' if file_count != 1 else ''}")
                else:
                    self.summary_label.setVisible(False)
                    self.status_label.setText("No results")
                    
        except Exception as e:
            print(f"Error removing search result: {e}")
        
    def search_completed(self, total_matches: int):
        """Handle search completion"""
        if total_matches == 0:
            self.status_label.setText("No results found")
            self.summary_label.setVisible(False)
        else:
            file_count = len(self.per_file_counts)
            # Update summary at top
            self.summary_label.setText(f"{total_matches} result{'s' if total_matches != 1 else ''} in {file_count} file{'s' if file_count != 1 else ''}")
            self.summary_label.setVisible(True)
            # Update footer
            self.status_label.setText(f"Found {total_matches} match{'es' if total_matches != 1 else ''} in {file_count} file{'s' if file_count != 1 else ''}")
            # Expand all file items by default
            for i in range(self.results_tree.topLevelItemCount()):
                item = self.results_tree.topLevelItem(i)
                item.setExpanded(True)
        # Repaint to ensure highlight draws with final state
        self.results_tree.viewport().update()
            
    def on_result_clicked(self, item: QTreeWidgetItem, column: int):
        """Handle result item click"""
        if isinstance(item, SearchResultItem) and item.kind == 'match' and item.line_num:
            # This is a match line - show preview reference
            self.current_preview_item = item
            
    def on_result_double_clicked(self, item: QTreeWidgetItem, column: int):
        """Handle result item double-click - open file"""
        if isinstance(item, SearchResultItem) and item.kind == 'match' and item.line_num and item.file_path:
            self.file_selected.emit(item.file_path, item.line_num)
            
    def _select_first_result(self):
        """Auto-select the first search result"""
        if self.results_tree.topLevelItemCount() > 0:
            # Get first file item
            file_item = self.results_tree.topLevelItem(0)
            if file_item and file_item.childCount() > 0:
                # Get first match under first file
                first_match = file_item.child(0)
                if isinstance(first_match, SearchResultItem) and first_match.kind == 'match':
                    self.results_tree.setCurrentItem(first_match)
                    self.current_preview_item = first_match
                    return True
        return False
    
    # Import methods from Search2.py to keep code modular
    show_replace_preview = show_replace_preview
    hide_replace_preview = hide_replace_preview
    replace_current = replace_current
    _compile_replace_pattern = _compile_replace_pattern
    _reload_file_in_editor = _reload_file_in_editor
    replace_all = replace_all
    replace_all_in_file = replace_all_in_file
    replace_single_match = replace_single_match


        