"""
Top Right Toolbar Module
Adds vertical toolbar in top right corner with full-height panel (Zapier/n8n style)
"""

from PySide6.QtCore import Qt, QSize, Signal
from PySide6.QtGui import QIcon, QPainter, QPen, QBrush, QColor, QLinearGradient
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QPushButton, QMenu, 
    QVBoxLayout, QLabel, QFrame, QScrollArea, QMessageBox
)

from Manage2.project_state import ProjectStateManager


class ToolbarIconButton(QPushButton):
    """Custom toolbar button matching the left toolbar style"""
    def __init__(self, icon_path: str, tooltip: str, parent=None):
        super().__init__(parent)
        self.setToolTip(tooltip)
        self.setIcon(QIcon(icon_path))
        self.setFixedSize(50, 50)
        self.setIconSize(QSize(32, 32))  # Bigger icon size
        self.setCheckable(True)
        self.setStyleSheet("background-color: transparent; border: none;")

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        rect = self.rect().adjusted(2, 2, -2, -2)
        border_radius = 5.0

        # Base shadow
        shadow_rect = rect.translated(1, 2)
        painter.setBrush(QBrush(QColor(0, 0, 0, 70)))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(shadow_rect, border_radius, border_radius)

        # Main gradient
        gradient = QLinearGradient(rect.topLeft(), rect.bottomLeft())
        if self.isChecked():
            gradient.setColorAt(0, QColor('#6A6D71').lighter(150))
            gradient.setColorAt(1, QColor('#6A6D71'))
        elif self.underMouse():
            gradient.setColorAt(0, QColor('#1E1E1E'))
            gradient.setColorAt(1, QColor('#232323'))
        else:
            gradient.setColorAt(0, QColor("#161616"))
            gradient.setColorAt(1, QColor('#202124'))
        
        painter.setBrush(QBrush(gradient))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(rect, border_radius, border_radius)

        # Inner highlight
        highlight_gradient = QLinearGradient(rect.topLeft(), rect.bottomRight())
        highlight_gradient.setColorAt(0, QColor(255, 255, 255, 25))
        highlight_gradient.setColorAt(1, QColor(255, 255, 255, 0))
        painter.setBrush(QBrush(highlight_gradient))
        painter.drawRoundedRect(rect, border_radius, border_radius)

        # Border
        border_color = QColor('#4A4D51')
        if self.isChecked():
            border_color = QColor('#6A6D71').lighter(150)
        elif self.underMouse():
             border_color = QColor('#6A6D71')
        painter.setPen(QPen(border_color, 1.5))
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(rect, border_radius, border_radius)

        # Icon
        icon_rect = rect.adjusted(9, 9, -9, -9)
        self.icon().paint(painter, icon_rect, Qt.AlignCenter)


class TopRightToolbar(QWidget):
    """
    Top right toolbar with vertical icon layout:
    - First icon opens full-height right panel (Zapier/n8n style)
    - Second icon for additional options
    """
    
    # Signals for actions
    menu_action_triggered = Signal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.selected_menu_item = None  # Track selected item for border highlight
        self.panel = None  # Reference to the side panel
        self.project_state = ProjectStateManager()  # Project state manager
        self.setup_ui()
        
    def setup_ui(self):
        """Setup the toolbar UI with vertical layout"""
        # Make the toolbar float on top
        self.setStyleSheet("background-color: transparent;")
        
        # VERTICAL layout for the icons (stacked)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        layout.setAlignment(Qt.AlignTop)
        
        # First icon - Project Settings panel (using ToolbarButton style)
        self.workflow_btn = ToolbarIconButton("img/Add.png", "Project Settings")
        self.workflow_btn.setCheckable(True)
        self.workflow_btn.clicked.connect(self.toggle_workflow_panel)
        layout.addWidget(self.workflow_btn)
        
        # Second icon - Manage Text Brush (using ToolbarButton style)
        self.text_brush_btn = ToolbarIconButton("img/Manage_Text_Brush.png", "Annotate / Draw")
        self.text_brush_btn.setCheckable(True)
        self.text_brush_btn.clicked.connect(self.toggle_text_brush)
        layout.addWidget(self.text_brush_btn)
        
        # Create the side panel (hidden initially)
        self._create_side_panel()
        
    def _create_side_panel(self):
        """Create the full-height right side panel (Zapier/n8n style)"""
        if not self.parent():
            return
            
        self.panel = QFrame(self.parent())
        self.panel.setStyleSheet("""
            QFrame {
                background-color: #1C1C1C;
            }
        """)
        
        layout = QVBoxLayout(self.panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Header with title and navigation buttons
        back_container = QWidget()
        back_container.setFixedHeight(60)
        back_container.setStyleSheet("background-color: #1C1C1C; border-bottom: 1px solid #4A4D51;")
        back_layout = QHBoxLayout(back_container)
        back_layout.setContentsMargins(20, 15, 15, 15)
        
        # Title on the left
        title_label = QLabel("Manage Native")
        title_label.setStyleSheet("""
            QLabel {
                color: #E8EAED;
                font-size: 15px;
                font-weight: bold;
                background: transparent;
                border: none;
            }
        """)
        back_layout.addWidget(title_label)
        back_layout.addStretch()
        
        # Project toggle button (Layer.png) - before back button
        self.project_btn = QPushButton()
        self.project_btn.setIcon(QIcon("img/Layer.png"))
        self.project_btn.setToolTip("Projects")
        self.project_btn.setFixedSize(35, 35)
        self.project_btn.setIconSize(QSize(28, 28))
        self.project_btn.setCheckable(True)
        self.project_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #3C4043;
            }
            QPushButton:checked {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(106, 109, 113, 225),
                    stop:1 rgba(106, 109, 113, 150));
                border: 1px solid rgba(106, 109, 113, 225);
            }
        """)
        self.project_btn.clicked.connect(self.toggle_projects_view)
        back_layout.addWidget(self.project_btn)
        
        # Add spacing between Layer button and back button
        back_layout.addSpacing(10)
        
        # Back button on the right (arrow-right)
        self.back_btn = QPushButton()
        self.back_btn.setIcon(QIcon("img/arrow-right.svg"))
        self.back_btn.setToolTip("Close Panel")
        self.back_btn.setFixedSize(35, 35)
        self.back_btn.setIconSize(QSize(23, 23))
        self.back_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #3C4043;
            }
        """)
        self.back_btn.clicked.connect(self.hide_panel)
        back_layout.addWidget(self.back_btn)
        
        layout.addWidget(back_container)
        
        # Menu items container
        self.menu_container = QWidget()
        self.menu_container.setStyleSheet("background-color: #1C1C1C; border: none;")
        menu_layout = QVBoxLayout(self.menu_container)
        menu_layout.setContentsMargins(0, 10, 0, 10)
        menu_layout.setSpacing(2)
        
        # Create menu items with icons and right border on hover/select
        self.menu_items = []
        
        items = [
            ("Add Project", "img/Add.png"),
            ("Select Box", "img/Manage_Select.png"),
            ("Search", "img/Manage_Search.png"),
            ("Save A3 Project", "img/Error_Rust.png"),
            ("Load A3 Project", "img/Error_Rust.png"),
        ]
        
        for text, icon_path in items:
            item_btn = self._create_menu_item(text, icon_path)
            menu_layout.addWidget(item_btn)
            self.menu_items.append(item_btn)
        
        menu_layout.addStretch()
        layout.addWidget(self.menu_container)
        
        # Projects view container (hidden by default)
        self.projects_container = QWidget()
        self.projects_container.setStyleSheet("background-color: #1C1C1C; border: none;")
        projects_layout = QVBoxLayout(self.projects_container)
        projects_layout.setContentsMargins(0, 0, 0, 0)
        projects_layout.setSpacing(0)
        
        # Scroll area for projects list
        self.projects_scroll_area = QScrollArea()
        self.projects_scroll_area.setWidgetResizable(True)
        self.projects_scroll_area.setStyleSheet("""
            QScrollArea {
                background-color: #1C1C1C;
                border: none;
            }
            QScrollBar:vertical {
                background-color: #1C1C1C;
                width: 12px;
                border-radius: 6px;
            }
            QScrollBar::handle:vertical {
                background-color: #4A4D51;
                border-radius: 6px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #60A5FA;
            }
        """)
        
        # Projects list widget
        self.projects_list_widget = QWidget()
        self.projects_list_widget.setStyleSheet("background-color: #1C1C1C; border: none;")
        self.projects_list_layout = QVBoxLayout(self.projects_list_widget)
        self.projects_list_layout.setContentsMargins(0, 10, 0, 10)
        self.projects_list_layout.setSpacing(2)
        self.projects_list_layout.setAlignment(Qt.AlignTop)
        
        self.projects_scroll_area.setWidget(self.projects_list_widget)
        projects_layout.addWidget(self.projects_scroll_area)
        
        # Install event filter on scroll area to handle keyboard shortcuts
        self.projects_scroll_area.installEventFilter(self)
        self.projects_scroll_area.setFocusPolicy(Qt.StrongFocus)
        
        layout.addWidget(self.projects_container)
        self.projects_container.hide()
        
        self.panel.hide()
    
    def _create_menu_item(self, text, icon_path):
        """Create a menu item button with icon and text"""
        btn = QPushButton()
        btn.setText(f"  {text}")  # Add spacing for icon
        btn.setIcon(QIcon(icon_path))
        btn.setIconSize(QSize(35, 35))  # Even bigger icon size
        btn.setFixedHeight(56)  # Taller height
        btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #E8EAED;
                text-align: left;
                padding-left: 20px;
                border: none;
                border-left: 3px solid transparent;
                font-size: 16px;
            }
            QPushButton:hover {
                background-color: #2C2E33;
                border-left: 3px solid #60A5FA;
            }
            QPushButton:pressed {
                background-color: #3C4043;
            }
        """)
        btn.clicked.connect(lambda: self.on_menu_item_clicked(text, btn))
        return btn
    
    def on_menu_item_clicked(self, action_name, btn):
        """Handle menu item click"""
        self.selected_menu_item = action_name
        
        # Update all buttons to show selected state
        for item in self.menu_items:
            if item == btn:
                item.setStyleSheet("""
                    QPushButton {
                        background-color: #2C2E33;
                        color: #E8EAED;
                        text-align: left;
                        padding-left: 20px;
                        border: none;
                        border-left: 3px solid #60A5FA;
                        font-size: 16px;
                    }
                    QPushButton:hover {
                        background-color: #2C2E33;
                        border-left: 3px solid #60A5FA;
                    }
                """)
            else:
                item.setStyleSheet("""
                    QPushButton {
                        background-color: transparent;
                        color: #E8EAED;
                        text-align: left;
                        padding-left: 20px;
                        border: none;
                        border-left: 3px solid transparent;
                        font-size: 16px;
                    }
                    QPushButton:hover {
                        background-color: #2C2E33;
                        border-left: 3px solid #60A5FA;
                    }
                    QPushButton:pressed {
                        background-color: #3C4043;
                    }
                """)
        
        # Emit the action signal
        self.menu_action_triggered.emit(action_name)
        
        # Close the panel after clicking any menu item
        self.hide_panel()
    
    def toggle_workflow_panel(self):
        """Toggle the side panel visibility"""
        if self.panel and self.panel.isVisible():
            self.hide_panel()
        else:
            self.show_panel()
    
    def show_panel(self):
        """Show the side panel"""
        if not self.panel:
            return
            
        # Position panel on right side, full height (wider panel)
        panel_width = 450
        parent = self.parent()
        if parent:
            self.panel.setGeometry(
                parent.width() - panel_width,
                0,
                panel_width,
                parent.height()
            )
        
        self.panel.show()
        self.panel.raise_()
        self.workflow_btn.setChecked(True)
    
    def hide_panel(self):
        """Hide the side panel"""
        if self.panel:
            self.panel.hide()
        self.workflow_btn.setChecked(False)
        # Reset to menu view when closing
        if hasattr(self, 'project_btn'):
            self.project_btn.setChecked(False)
            self.menu_container.show()
            self.projects_container.hide()
    
    def toggle_projects_view(self):
        """Toggle between menu view and projects view"""
        if self.project_btn.isChecked():
            # Show projects view
            self.refresh_projects_list()
            self.menu_container.hide()
            self.projects_container.show()
            # Set focus on scroll area to enable keyboard shortcuts
            if hasattr(self, 'projects_scroll_area'):
                self.projects_scroll_area.setFocus()
        else:
            # Show menu view
            self.menu_container.show()
            self.projects_container.hide()
    
    def refresh_projects_list(self):
        """Refresh the projects list display"""
        # Clear existing items
        while self.projects_list_layout.count():
            item = self.projects_list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        # Get all projects
        projects = self.project_state.get_all_projects()
        
        if not projects:
            # Show empty state
            empty_state = QWidget()
            empty_state.setStyleSheet("background-color: #1C1C1C; border: none;")
            empty_layout = QVBoxLayout(empty_state)
            empty_layout.setAlignment(Qt.AlignCenter)
            
            empty_icon = QLabel()
            empty_icon.setPixmap(QIcon("img/Layer.png").pixmap(64, 64))
            empty_icon.setAlignment(Qt.AlignCenter)
            empty_layout.addWidget(empty_icon)
            
            empty_text = QLabel("No projects yet")
            empty_text.setAlignment(Qt.AlignCenter)
            empty_text.setStyleSheet("""
                QLabel {
                    color: #9AA0A6;
                    font-size: 16px;
                    font-weight: bold;
                    margin-top: 20px;
                }
            """)
            empty_layout.addWidget(empty_text)
            
            empty_subtext = QLabel("Create your first project to get started")
            empty_subtext.setAlignment(Qt.AlignCenter)
            empty_subtext.setStyleSheet("""
                QLabel {
                    color: #5F6368;
                    font-size: 13px;
                    margin-top: 10px;
                }
            """)
            empty_layout.addWidget(empty_subtext)
            
            self.projects_list_layout.addWidget(empty_state)
        else:
            # Show project items
            active_project = self.project_state.get_active_project()
            active_id = active_project.id if active_project else None
            
            for project in projects:
                project_item = self._create_project_item(project, project.id == active_id)
                self.projects_list_layout.addWidget(project_item)
    
    def _create_project_item(self, project, is_active=False):
        """Create a project list item widget"""
        item = QPushButton()
        
        # Prevent button from taking focus - keep focus on scroll area for shortcuts
        item.setFocusPolicy(Qt.NoFocus)
        
        # Show modified indicator
        modified_indicator = " •" if project.is_modified else ""
        item.setText(f"  {project.name}{modified_indicator}")
        
        item.setIcon(QIcon("img/Layer.png"))
        item.setIconSize(QSize(32, 32))
        item.setFixedHeight(56)
        
        # Style based on active state
        if is_active:
            item.setStyleSheet("""
                QPushButton {
                    background-color: #2C2E33;
                    color: #E8EAED;
                    text-align: left;
                    padding-left: 20px;
                    border: none;
                    border-left: 3px solid #60A5FA;
                    font-size: 16px;
                }
                QPushButton:hover {
                    background-color: #2C2E33;
                    border-left: 3px solid #60A5FA;
                }
            """)
        else:
            item.setStyleSheet("""
                QPushButton {
                    background-color: transparent;
                    color: #E8EAED;
                    text-align: left;
                    padding-left: 20px;
                    border: none;
                    border-left: 3px solid transparent;
                    font-size: 16px;
                }
                QPushButton:hover {
                    background-color: #2C2E33;
                    border-left: 3px solid #60A5FA;
                }
                QPushButton:pressed {
                    background-color: #3C4043;
                }
            """)
        
        # Connect click to switch project
        item.clicked.connect(lambda: self.on_project_selected(project.id))
        
        # Enable context menu
        item.setContextMenuPolicy(Qt.CustomContextMenu)
        item.customContextMenuRequested.connect(lambda pos: self.show_project_context_menu(item, project))
        
        return item
    
    def on_project_selected(self, project_id: int):
        """Handle project selection"""
        # Just switch to the project without asking
        self._switch_to_project(project_id)
    
    def _switch_to_project(self, project_id: int):
        """Switch to a different project"""
        # CRITICAL: Save current project's canvas state before switching
        # BUT DO NOT save to database - only update in-memory state
        current_project = self.project_state.get_active_project()
        if current_project:
            try:
                # Get manage widget from parent window
                parent_window = self.parent()
                while parent_window and not hasattr(parent_window, 'manage_widget'):
                    parent_window = parent_window.parent()
                
                if parent_window and hasattr(parent_window, 'manage_widget'):
                    manage_widget = parent_window.manage_widget
                    
                    # Collect and save current canvas state
                    from Manage.document_io import SaveLoadManager
                    save_manager = SaveLoadManager()
                    canvas_state = save_manager.collect_state(manage_widget)
                    
                    # Update project with current canvas state (in-memory only)
                    self.project_state.update_project_canvas(current_project.id, canvas_state)
            except Exception as e:
                import traceback
                traceback.print_exc()
        
        # Now switch to the new project
        if self.project_state.set_active_project(project_id):
            project = self.project_state.get_project(project_id)
            
            # Refresh the list to update active indicator
            self.refresh_projects_list()
            
            # Emit signal to load project canvas
            self.menu_action_triggered.emit(f"_load_project_{project_id}")
    
    def show_project_context_menu(self, button, project):
        """Show context menu for project item"""
        from PySide6.QtGui import QCursor, QKeySequence
        
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #1E1F22;
                border: 1px solid #4A4D51;
                border-radius: 8px;
                padding: 4px;
                color: #E8EAED;
            }
            QMenu::item {
                background-color: transparent;
                padding: 8px 12px;
                border-radius: 4px;
                margin: 0px;
            }
            QMenu::item:selected {
                background-color: #2C2E33;
            }
            QMenu::item:pressed {
                background-color: #3C4043;
            }
            QMenu::separator {
                height: 1px;
                background-color: #4A4D51;
                margin: 4px 0px;
            }
        """)
        
        # Rename action (no icon, no shortcut)
        rename_action = menu.addAction("Rename")
        rename_action.triggered.connect(lambda: self.rename_project(project))
        
        # Delete action (no icon, no shortcut)
        delete_action = menu.addAction("Delete")
        delete_action.triggered.connect(lambda: self.delete_project(project))
        
        menu.addSeparator()
        
        # Move up action (no icon, with Up arrow shortcut)
        projects = self.project_state.get_all_projects()
        project_index = next((i for i, p in enumerate(projects) if p.id == project.id), -1)
        
        move_up_action = menu.addAction("Move Up")
        move_up_action.setShortcut(QKeySequence(Qt.Key_Up))
        move_up_action.setEnabled(project_index > 0)
        move_up_action.triggered.connect(lambda: self.move_project_up(project))
        
        # Move down action (no icon, with Down arrow shortcut)
        move_down_action = menu.addAction("Move Down")
        move_down_action.setShortcut(QKeySequence(Qt.Key_Down))
        move_down_action.setEnabled(project_index < len(projects) - 1 and project_index != -1)
        move_down_action.triggered.connect(lambda: self.move_project_down(project))
        
        # Show menu at cursor position
        menu.exec(QCursor.pos())
    
    def rename_project(self, project):
        """Rename a project"""
        from Manage2.project_dialogs import RenameProjectDialog
        
        dialog = RenameProjectDialog(project.name, self)
        if dialog.exec() == RenameProjectDialog.Accepted and dialog.new_name:
            # Update project name
            project.name = dialog.new_name
            project.is_modified = True
            
            # Save to database
            self.project_state.save_projects()
            
            # Refresh the list
            self.refresh_projects_list()
    
    def delete_project(self, project):
        """Delete a project with confirmation"""
        from Manage2.project_dialogs import DeleteProjectDialog
        
        # Show custom delete confirmation dialog
        dialog = DeleteProjectDialog(project.name, self)
        if dialog.exec() == DeleteProjectDialog.Accepted and dialog.confirmed:
            # Delete the project
            success = self.project_state.delete_project(project.id, save=True)
            
            if success:
                # If deleted project was active, clear canvas
                if self.project_state.get_active_project() is None:
                    # Clear canvas
                    try:
                        parent_window = self.parent()
                        while parent_window and not hasattr(parent_window, 'manage_widget'):
                            parent_window = parent_window.parent()
                        
                        if parent_window and hasattr(parent_window, 'manage_widget'):
                            manage_widget = parent_window.manage_widget
                            if hasattr(manage_widget, 'canvas'):
                                manage_widget.canvas.clear()
                    except Exception as e:
                        print(f"[TopRightToolbar] Error clearing canvas: {e}")
                
                # Refresh the list
                self.refresh_projects_list()
            else:
                QMessageBox.warning(
                    self,
                    "Delete Failed",
                    f"Failed to delete project '{project.name}'."
                )
    
    def move_project_up(self, project):
        """Move project up in the list"""
        projects = self.project_state.get_all_projects()
        project_index = next((i for i, p in enumerate(projects) if p.id == project.id), -1)
        
        if project_index <= 0:
            return  # Already at top or not found
        
        # Swap IDs to change order
        # We swap the IDs of the two projects to maintain database integrity
        prev_project = projects[project_index - 1]
        
        # Swap IDs
        temp_id = project.id
        project.id = prev_project.id
        prev_project.id = temp_id
        
        # Update the projects dict
        self.project_state.projects[project.id] = project
        self.project_state.projects[prev_project.id] = prev_project
        
        # Update active project ID if needed
        if self.project_state.active_project_id == temp_id:
            self.project_state.active_project_id = project.id
        elif self.project_state.active_project_id == prev_project.id:
            self.project_state.active_project_id = prev_project.id
        
        # Save to database
        self.project_state.save_projects()
        
        # Refresh the list
        self.refresh_projects_list()
        
        print(f"[TopRightToolbar] Moved project '{project.name}' up")
    
    def move_project_down(self, project):
        """Move project down in the list"""
        projects = self.project_state.get_all_projects()
        project_index = next((i for i, p in enumerate(projects) if p.id == project.id), -1)
        
        if project_index == -1 or project_index >= len(projects) - 1:
            return  # Already at bottom or not found
        
        # Swap IDs to change order
        next_project = projects[project_index + 1]
        
        # Swap IDs
        temp_id = project.id
        project.id = next_project.id
        next_project.id = temp_id
        
        # Update the projects dict
        self.project_state.projects[project.id] = project
        self.project_state.projects[next_project.id] = next_project
        
        # Update active project ID if needed
        if self.project_state.active_project_id == temp_id:
            self.project_state.active_project_id = project.id
        elif self.project_state.active_project_id == next_project.id:
            self.project_state.active_project_id = next_project.id
        
        # Save to database
        self.project_state.save_projects()
        
        # Refresh the list
        self.refresh_projects_list()
        
        print(f"[TopRightToolbar] Moved project '{project.name}' down")
    
    def eventFilter(self, obj, event):
        """Handle keyboard shortcuts for moving projects"""
        from PySide6.QtCore import QEvent
        from PySide6.QtGui import QKeyEvent
        
        if event.type() == QEvent.KeyPress and isinstance(event, QKeyEvent):
            # Only handle if projects view is visible
            if self.projects_container and self.projects_container.isVisible():
                active_project = self.project_state.get_active_project()
                
                if active_project:
                    if event.key() == Qt.Key_Up:
                        # Move active project up
                        self.move_project_up(active_project)
                        return True
                    elif event.key() == Qt.Key_Down:
                        # Move active project down
                        self.move_project_down(active_project)
                        return True
        
        return super().eventFilter(obj, event)
    
    def toggle_text_brush(self):
        """Toggle the text brush/annotation toolbar"""
        # This will be connected to the ManageWidget's annotation toolbar
        # The connection is made in manage_native.py or main_widget.py
        pass
        
    def position_toolbar(self, parent_width, parent_height):
        """Position the toolbar in the top right corner"""
        toolbar_width = self.sizeHint().width()
        x = parent_width - toolbar_width - 20
        y = 20
        self.move(x, y)
        
        # Also reposition panel if visible
        if self.panel and self.panel.isVisible():
            panel_width = 400
            self.panel.setGeometry(
                parent_width - panel_width,
                0,
                panel_width,
                parent_height
            )


class WorkflowMenu(QMenu):
    """
    Custom menu for project settings
    Styled like Zapier or n8n with icons on the left and colored border for selection
    """
    
    action_triggered = Signal(str)
    
    def __init__(self, parent=None, selected_item=None):
        super().__init__(parent)
        self.selected_item = selected_item
        self.setup_menu()
        
    def setup_menu(self):
        """Setup the menu with project settings options"""
        # Set minimum width for the menu
        self.setMinimumWidth(250)
        
        # Apply dark theme styling with left border for selection (Zapier/n8n style)
        self.setStyleSheet("""
            QMenu {
                background-color: #1E1F22;
                border: 1px solid #4A4D51;
                border-radius: 8px;
                padding: 8px;
                color: #E8EAED;
            }
            QMenu::item {
                background-color: transparent;
                padding: 10px 12px 10px 12px;
                border-radius: 6px;
                margin: 2px 4px;
                border-left: 3px solid transparent;
            }
            QMenu::item:selected {
                background-color: #2C2E33;
                border-left: 3px solid #60A5FA;
            }
            QMenu::item:pressed {
                background-color: #3C4043;
            }
            QMenu::separator {
                height: 1px;
                background-color: #4A4D51;
                margin: 6px 8px;
            }
            QMenu::icon {
                padding-left: 8px;
            }
        """)
        
        # Create menu items with icons on the left
        add_project = self.addAction(QIcon("img/Add.png"), "  Add Project")
        add_project.triggered.connect(lambda: self.on_action_triggered("Add Project"))
        if self.selected_item == "Add Project":
            add_project.setIconVisibleInMenu(True)
        
        select_box = self.addAction(QIcon("img/Manage_Select.png"), "  Select Box")
        select_box.triggered.connect(lambda: self.on_action_triggered("Select Box"))
        if self.selected_item == "Select Box":
            select_box.setIconVisibleInMenu(True)
        
        search = self.addAction(QIcon("img/Manage_Search.png"), "  Search")
        search.triggered.connect(lambda: self.on_action_triggered("Search"))
        if self.selected_item == "Search":
            search.setIconVisibleInMenu(True)
        
        self.addSeparator()
        
        save_project = self.addAction(QIcon("img/Error_Rust.png"), "  Save A3 Project")
        save_project.triggered.connect(lambda: self.on_action_triggered("Save A3 Project"))
        if self.selected_item == "Save A3 Project":
            save_project.setIconVisibleInMenu(True)
        
        load_project = self.addAction(QIcon("img/Error_Rust.png"), "  Load A3 Project")
        load_project.triggered.connect(lambda: self.on_action_triggered("Load A3 Project"))
        if self.selected_item == "Load A3 Project":
            load_project.setIconVisibleInMenu(True)
    
    def on_action_triggered(self, action_name):
        """Emit signal when action is triggered"""
        self.action_triggered.emit(action_name)


class WorkflowPanel(QFrame):
    """
    Alternative: A floating panel instead of a menu
    This provides more space for complex UI elements
    """
    
    closed = Signal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        
    def setup_ui(self):
        """Setup the panel UI"""
        self.setWindowFlags(Qt.Tool | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        # Set fixed size for the panel
        self.setFixedSize(400, 500)
        
        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # Container frame for styling
        container = QFrame()
        container.setStyleSheet("""
            QFrame {
                background-color: #1E1F22;
                border: 1px solid #4A4D51;
                border-radius: 12px;
            }
            QLabel {
                color: #E8EAED;
            }
            QPushButton {
                background-color: #2C2E33;
                border: 1px solid #4A4D51;
                border-radius: 6px;
                padding: 8px 16px;
                color: #E8EAED;
            }
            QPushButton:hover {
                background-color: #3C4043;
                border: 1px solid #60A5FA;
            }
        """)
        
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(15, 15, 15, 15)
        container_layout.setSpacing(10)
        
        # Title bar
        title_layout = QHBoxLayout()
        title_label = QLabel("⚡ Workflow & Automation")
        title_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #60A5FA;")
        title_layout.addWidget(title_label)
        
        title_layout.addStretch()
        
        close_btn = QPushButton("✕")
        close_btn.setFixedSize(24, 24)
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
                color: #BDC1C6;
                font-size: 16px;
                padding: 0px;
            }
            QPushButton:hover {
                color: #FFFFFF;
                background-color: #3C4043;
            }
        """)
        close_btn.clicked.connect(self.close)
        title_layout.addWidget(close_btn)
        
        container_layout.addLayout(title_layout)
        
        # Add separator
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setStyleSheet("background-color: #4A4D51;")
        separator.setFixedHeight(1)
        container_layout.addWidget(separator)
        
        # Content area - placeholder
        content_label = QLabel("Workflow content will be added here.\n\nThis panel provides space for:\n• Workflow builder\n• Automation rules\n• Trigger configuration\n• Action settings\n• And more...")
        content_label.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        content_label.setWordWrap(True)
        content_label.setStyleSheet("color: #BDC1C6; padding: 10px;")
        container_layout.addWidget(content_label)
        
        container_layout.addStretch()
        
        main_layout.addWidget(container)
        
    def closeEvent(self, event):
        """Emit closed signal when panel is closed"""
        self.closed.emit()
        super().closeEvent(event)