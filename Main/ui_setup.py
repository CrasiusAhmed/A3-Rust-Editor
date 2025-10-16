"""
UI Setup Module for A³ Rust Editor
Contains all UI initialization and setup methods extracted from Rust.py
"""

from PySide6.QtCore import Qt, QSize, QTimer
from PySide6.QtGui import QIcon, QFont
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QSplitter,
    QStackedWidget, QTabWidget, QPlainTextEdit, QLabel, QTabBar,
    QTreeView, QHeaderView, QSizePolicy
)

from Details.Main_Code_Editor import CodeEditor
from file_showen import FileTreeDelegate, CustomFileSystemModel, FileSorterProxyModel, KeyboardDisplayWidget
from Details.welcome_page import WelcomePageWidget
from Details.file_tree_with_shortcuts import EnhancedFileTreeView
from manage_native import ManageWidget
from Main.title_bar import CustomTitleBar


class UISetupManager:
    """Manages all UI setup and initialization for the main window."""
    
    def __init__(self, main_window):
        """
        Initialize the UI setup manager.
        
        Args:
            main_window: Reference to the MainWindow instance
        """
        self.window = main_window
    
    def setup_ui(self):
        """Initialize the user interface."""
        # --- Main Layout ---
        main_widget = QWidget()
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.window.title_bar = CustomTitleBar(self.window)
        main_layout.addWidget(self.window.title_bar)

        self.window.content_widget = QWidget()
        main_hbox = QHBoxLayout(self.window.content_widget)
        main_hbox.setContentsMargins(0, 0, 0, 0)
        main_hbox.setSpacing(0)
        main_layout.addWidget(self.window.content_widget)
        self.window.setCentralWidget(main_widget)

        self.setup_icon_bar(main_hbox)
        self.setup_main_content(main_hbox)
        self.setup_status_bar()
        
        # Initialize keyboard display widget (JetBrains PyCharm style)
        self.window.keyboard_display = KeyboardDisplayWidget(self.window)

    def setup_icon_bar(self, main_hbox):
        """Setup the left icon bar."""
        icon_bar = QWidget()
        icon_bar.setStyleSheet("background-color: #1E1E1E; border-right: 1px solid #2C2E33;")
        icon_bar_layout = QVBoxLayout(icon_bar)
        icon_bar_layout.setContentsMargins(5, 5, 5, 5)
        icon_bar_layout.setSpacing(10)
        icon_bar_layout.setAlignment(Qt.AlignTop)

        self.window.files_button = QPushButton()
        self.window.files_button.setIcon(QIcon("img/folder.png"))
        self.window.files_button.setToolTip("Files")
        self.window.search_button = QPushButton()
        self.window.search_button.setIcon(QIcon("img/Search.png"))
        self.window.search_button.setToolTip("Search")
        self.window.manage_button = QPushButton()
        self.window.manage_button.setIcon(QIcon("img/Manage.png"))
        self.window.manage_button.setToolTip("Manage")
        
        for btn in [self.window.files_button, self.window.search_button, self.window.manage_button]:
            btn.setCheckable(True)
            btn.setAutoExclusive(True)
            btn.setStyleSheet("""
                QPushButton {
                    background: transparent;
                    border: none;
                    color: #60A5FA;
                    font-size: 24px;
                    padding: 5px;
                    icon-size: 35px;
                    border-left: 3px solid transparent;
                }
                QPushButton:hover {
                    background-color: #282A2E;
                }
                QPushButton:checked {
                    background: transparent;
                    color: #60A5FA;
                    border-left: 3px solid #007ACC;
                }
            """)
            icon_bar_layout.addWidget(btn)

        icon_bar_layout.addStretch()

        self.window.settings_button = QPushButton()
        self.window.settings_button.setIcon(QIcon("img/Setting.png"))
        self.window.settings_button.setToolTip("Settings")
        self.window.settings_button.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                padding: 5px;
                icon-size: 30px;
            }
            QPushButton:hover {
                background-color: #282A2E;
            }
        """)
        self.window.settings_button.clicked.connect(self.window.show_settings_menu)
        icon_bar_layout.addWidget(self.window.settings_button)
        
        main_hbox.addWidget(icon_bar)

    def setup_main_content(self, main_hbox):
        """Setup the main content area."""
        # Main content stack for switching between editor view and manage view
        self.window.main_content_stack = QStackedWidget()
        main_hbox.addWidget(self.window.main_content_stack)

        # --- Editor View ---
        editor_view_widget = QWidget()
        editor_view_layout = QHBoxLayout(editor_view_widget)
        editor_view_layout.setContentsMargins(0, 0, 0, 0)
        editor_view_layout.setSpacing(0)
        self.window.main_content_stack.addWidget(editor_view_widget)

        self.window.main_splitter = QSplitter(Qt.Horizontal)
        editor_view_layout.addWidget(self.window.main_splitter)

        self.window.right_pane_splitter = QSplitter(Qt.Vertical)
        self.setup_left_pane()
        self.setup_editor_and_terminal()
        self.setup_preview_tabs()

        self.window.main_splitter.addWidget(self.window.right_pane_splitter)
        self.window.main_splitter.addWidget(self.window.editor_terminal_splitter)
        self.window.main_splitter.setSizes([480, 938])

        # --- Manage View (full screen) ---
        self.window.manage_widget = ManageWidget(self.window)
        self.window.manage_widget.setMinimumSize(800, 600)
        self.window.main_content_stack.addWidget(self.window.manage_widget)
        
        # Hook file loading to save current project and create file-based projects
        self._setup_file_loading_hook()

    def setup_left_pane(self):
        """Setup the left pane with file tree and other panels."""
        self.window.left_pane_stack = QStackedWidget()
        
        # File Tree View (INDEX 0 - DEFAULT)
        self.window.file_model = CustomFileSystemModel()
        from PySide6.QtCore import QDir
        self.window.file_model.setRootPath(QDir.rootPath())

        self.window.proxy_model = FileSorterProxyModel(self.window)
        self.window.proxy_model.setSourceModel(self.window.file_model)

        self.window.tree_view = EnhancedFileTreeView()
        self.window.tree_view.set_models(self.window, self.window.file_model, self.window.proxy_model)
        self.window.tree_view.setModel(self.window.proxy_model)
        # Connect refresh signal
        self.window.tree_view.refresh_needed.connect(self.window.refresh_file_tree)
        if getattr(self.window, 'initial_root_path', None):
            idx = self.window.file_model.index(self.window.initial_root_path)
            if idx.isValid():
                self.window.tree_view.setRootIndex(self.window.proxy_model.mapFromSource(idx))
        # else: no root set initially to avoid defaulting to the app's own folder
        self.window.tree_view.clicked.connect(self.window.on_file_clicked)
        self.window.tree_view.setSortingEnabled(True)
        self.window.tree_view.sortByColumn(0, Qt.AscendingOrder)
        self.window.tree_view.setIndentation(15)
        self.window.tree_view.setIconSize(QSize(16, 16))
        self.window.tree_view.setUniformRowHeights(True)
        # Enable multi-selection like VS Code (Ctrl+Click to select multiple)
        self.window.tree_view.setSelectionMode(QTreeView.ExtendedSelection)
        self.window.tree_view.setContextMenuPolicy(Qt.CustomContextMenu)
        self.window.tree_view.customContextMenuRequested.connect(self.window.open_file_context_menu)
        # Allow shrinking in vertical splitter
        self.window.tree_view.setMinimumHeight(0)
        self.window.tree_view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Ignored)
        
        self.setup_tree_view_styling()
        # Add file tree as INDEX 0
        self.window.left_pane_stack.addWidget(self.window.tree_view)
        
        # Search Panel (INDEX 1)
        from Search import SearchPanel
        self.window.search_panel = SearchPanel()
        self.window.search_panel.file_selected.connect(self.window.open_file_for_editing)
        self.window.left_pane_stack.addWidget(self.window.search_panel)
        
        # Connect buttons AFTER widgets are added
        self.window.files_button.clicked.connect(self.window.show_files_panel)
        self.window.search_button.clicked.connect(self.window.show_search_panel)
        self.window.manage_button.clicked.connect(self.window.show_manage_panel)
        
        # Set Files button as checked by default and show file tree
        self.window.files_button.setChecked(True)
        self.window.left_pane_stack.setCurrentIndex(0)  # Ensure file tree is shown

        self.window.right_pane_splitter.addWidget(self.window.left_pane_stack)
        # Ensure the top pane can shrink
        self.window.left_pane_stack.setMinimumHeight(0)
        self.window.left_pane_stack.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Ignored)

    def setup_tree_view_styling(self):
        """Apply styling to the tree view."""
        hdr = self.window.tree_view.header()
        hdr.setSectionResizeMode(0, QHeaderView.Interactive)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.window.tree_view.setColumnWidth(0, 170)
        # Store the highlighted file path
        self.window.highlighted_file = None
        hdr.setStyleSheet(
            "QHeaderView::section { background-color: #2C2E33; color: #BDC1C6; padding: 4px; border: none; }"
            "QHeaderView::section:first { padding-left: 3px; }"
        )
        self.window.tree_view.setStyleSheet("""
            QTreeView {
                background: #1E1E1E;
                color: #BDC1C6;
                font-size: 14px;
                border: 1px solid transparent;
            }
            QTreeView:focus {
                border: 1px solid #007ACC;
            }
            QTreeView::item {
                padding: 2px;
                background-color: transparent;
                border: none;
                color: #E8EAED;  /* Force bright text color */
            }
            QTreeView::item:selected {
                background-color: #3C4043;
                color: #E8EAED;
            }
            QTreeView::branch {
                background: transparent;
            }
            QTreeView::branch:hover {
                background: #282A2E;
            }
            QTreeView::branch:closed:has-children {
                image: url(img/branch-closed.svg);
            }
            QTreeView::branch:open:has-children {
                image: url(img/branch-open.svg);
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
        self.window.tree_view.setItemDelegate(FileTreeDelegate(self.window.tree_view))

    def setup_editor_and_terminal(self):
        """Setup the editor and terminal area."""
        self.window.editor_terminal_splitter = QSplitter(Qt.Vertical)

        # Create editor container with toolbar
        editor_container = QWidget()
        # Allow editor container to shrink in the splitter
        editor_container.setMinimumHeight(0)
        editor_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Ignored)
        editor_layout = QVBoxLayout(editor_container)
        editor_layout.setContentsMargins(0, 0, 0, 0)
        editor_layout.setSpacing(0)

        # Create toolbar for Python run button and split editor
        self.window.editor_toolbar = QWidget()
        self.window.editor_toolbar.setFixedHeight(25)  # Match tab height
        toolbar_layout = QHBoxLayout(self.window.editor_toolbar)
        toolbar_layout.setContentsMargins(5, 0, 5, 0)
        toolbar_layout.setSpacing(3)

        # Python run button with dropdown menu
        self.window.run_python_btn = QPushButton()
        self.window.run_python_btn.setIcon(QIcon("img/Brush.png"))
        self.window.run_python_btn.setToolTip("Toggle Color Mode (F1)")
        self.window.run_python_btn.setFixedSize(28, 28)  # Larger button size
        self.window.run_python_btn.setIconSize(QSize(22, 22))  # Explicit icon size
        self.window.run_python_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                padding: 2px;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #3C4043;
            }
            QPushButton:pressed {
                background-color: #4A4D51;
            }
        """)
        # Default action: Toggle Color Mode
        self.window.run_python_btn.clicked.connect(self.window.toggle_color_change_mode)
        toolbar_layout.addWidget(self.window.run_python_btn)

        # Rust Run button
        self.window.rust_run_btn = QPushButton()
        self.window.rust_run_btn.setIcon(QIcon("img/Rust_R.png"))
        self.window.rust_run_btn.setToolTip("Run Rust (F5)")
        self.window.rust_run_btn.setFixedSize(28, 28)  # Larger button size
        self.window.rust_run_btn.setIconSize(QSize(22, 22))  # Explicit icon size
        self.window.rust_run_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                padding: 2px;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #3C4043;
            }
            QPushButton:pressed {
                background-color: #4A4D51;
            }
        """)
        self.window.rust_run_btn.clicked.connect(self.window.run_current_rust)
        toolbar_layout.addWidget(self.window.rust_run_btn)

        # Cargo Check button (Fast error checking without running)
        self.window.cargo_check_btn = QPushButton()
        self.window.cargo_check_btn.setIcon(QIcon("img/Error_Rust.png"))
        self.window.cargo_check_btn.setToolTip("Cargo Check - Fast error checking (F6)")
        self.window.cargo_check_btn.setFixedSize(28, 28)
        self.window.cargo_check_btn.setIconSize(QSize(22, 22))
        self.window.cargo_check_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                padding: 2px;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #3C4043;
            }
            QPushButton:pressed {
                background-color: #4A4D51;
            }
        """)
        self.window.cargo_check_btn.clicked.connect(self.window.run_cargo_check)
        toolbar_layout.addWidget(self.window.cargo_check_btn)

        # Separator
        separator = QLabel("|")
        separator.setStyleSheet("color: #4A4D51; font-size: 16px;")
        toolbar_layout.addWidget(separator)

        # Split editor right button with icon
        self.window.split_editor_btn = QPushButton("▯▯")  # Two tall rectangles side by side like VS Code
        self.window.split_editor_btn.setToolTip("Split Editor Right (Ctrl+\\)")
        self.window.split_editor_btn.setFixedWidth(50)
        self.window.split_editor_btn.setFixedHeight(25)
        self.window.split_editor_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                color: #BDC1C6;
                padding: 2px;
                border-radius: 3px;
                font-size: 20px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #3C4043;
                color: #E8EAED;
            }
            QPushButton:pressed {
                background-color: #4A4D51;
            }
        """)
        self.window.split_editor_btn.clicked.connect(self.window.split_editor_right)
        toolbar_layout.addWidget(self.window.split_editor_btn)

        # Tabbed Code Editor
        self.window.editor_tabs = QTabWidget()
        self.window.editor_tabs.setTabsClosable(True)
        self.window.editor_tabs.tabCloseRequested.connect(self.window.close_editor_tab)
        self.window.editor_tabs.currentChanged.connect(self.window.on_editor_tab_changed)
        self.window.editor_tabs.setStyleSheet("""
            QTabWidget::pane { border-top: 1px solid #282A2E; }
            QTabBar::tab {
                background: #141414; color: #BDC1C6; padding: 8px 15px;
                border: 1px solid #141414; border-bottom: none;
                border-top-left-radius: 6px; border-top-right-radius: 6px;
            }
            QTabBar::tab:selected {
                background: #222223; color: #E8EAED;
            }
            QTabBar::tab:!selected:hover {
                background: #282A2E;
            }
            /* Force white scroll arrows on the tab bar scroller buttons */
            QTabBar::scroller { width: 36px; }
            QTabBar QToolButton { background: transparent; border: none;  margin-top: 7px;  }
            QTabBar QToolButton::right-arrow { image: url(img/arrow-right.svg); }
            QTabBar QToolButton::left-arrow { image: url(img/arrow-left.svg); }
            QTabBar QToolButton::right-arrow:disabled { image: url(img/arrow-right.svg); }
            QTabBar QToolButton::left-arrow:disabled { image: url(img/arrow-left.svg); }
            QTabBar QToolButton::right-arrow:hover { image: url(img/arrow-right.svg); }
            QTabBar QToolButton::left-arrow:hover { image: url(img/arrow-left.svg); }
            QTabBar QToolButton::right-arrow:pressed { image: url(img/arrow-right.svg); }
            QTabBar QToolButton::left-arrow:pressed { image: url(img/arrow-left.svg); }
        """)

        # Set the toolbar as corner widget on the right side of tab bar (VS Code style)
        self.window.editor_tabs.setCornerWidget(self.window.editor_toolbar, Qt.TopRightCorner)
        
        # Hide toolbar initially
        self.window.editor_toolbar.hide()
        
        # Welcome Page
        self.window.welcome_page = WelcomePageWidget(self.window)
        self.window.welcome_tab_index = self.window.editor_tabs.addTab(self.window.welcome_page, "Welcome")
        welcome_close_button = QPushButton("X")
        welcome_close_button.setStyleSheet("border:none; background:transparent; color: #BDC1C6; font-weight: bold; font-size: 14px; padding: 2px 6px;")
        welcome_close_button.clicked.connect(lambda: self.window.close_welcome_tab())
        self.window.editor_tabs.tabBar().setTabButton(self.window.welcome_tab_index, QTabBar.RightSide, welcome_close_button)
        welcome_close_button.lower()
        
        editor_layout.addWidget(self.window.editor_tabs)
        self.window.editor_terminal_splitter.addWidget(editor_container)
        self.setup_terminal_container()

    def setup_terminal_container(self):
        """Setup the terminal container."""
        terminal_container = QWidget()
        # Allow terminal container to shrink in the splitter
        terminal_container.setMinimumHeight(0)
        terminal_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Ignored)
        terminal_layout = QVBoxLayout(terminal_container)
        terminal_layout.setContentsMargins(0, 0, 0, 0)
        terminal_layout.setSpacing(0)

        self.window.terminal_tabs = QTabWidget()
        # Allow terminal tabs to shrink vertically
        self.window.terminal_tabs.setMinimumHeight(0)
        self.window.terminal_tabs.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Ignored)
        self.window.terminal_tabs.setTabsClosable(True)
        self.window.terminal_tabs.setStyleSheet("""
            QTabWidget::pane { border-top: 1px solid #4A4D51; }
            QTabBar::tab { background: #131314; color: #BDC1C6; padding: 6px 15px; border: none; }
            QTabBar::tab:selected { background: #1E1F22; color: #E8EAED; }
            QTabBar::tab:hover { background: #282A2E; }
        """)
        terminal_layout.addWidget(self.window.terminal_tabs)

        # Terminal toolbar
        terminal_toolbar = QWidget()
        terminal_toolbar_layout = QHBoxLayout(terminal_toolbar)
        terminal_toolbar_layout.setContentsMargins(5, 0, 5, 0)
        terminal_toolbar_layout.setSpacing(4)

        self.window.add_term_btn = QPushButton("➕")
        self.window.trash_term_btn = QPushButton("🗑️")
        self.window.close_panel_btn = QPushButton("❌")

        for btn, tooltip in [(self.window.add_term_btn, "New Terminal"), (self.window.trash_term_btn, "Kill Current Terminal"), (self.window.close_panel_btn, "Close Panel")]:
            btn.setToolTip(tooltip)
            btn.setStyleSheet("QPushButton { background: transparent; border: none; color: #BDC1C6; font-size: 16px; padding: 2px;} QPushButton:hover { color: #FFFFFF; }")
            terminal_toolbar_layout.addWidget(btn)
        
        self.window.terminal_tabs.setCornerWidget(terminal_toolbar, Qt.TopRightCorner)

        self.window.add_term_btn.clicked.connect(self.window.terminal_manager.add_new_terminal)
        self.window.trash_term_btn.clicked.connect(self.window.terminal_manager.kill_current_terminal)
        self.window.close_panel_btn.clicked.connect(self.window.terminal_manager.hide_terminal_panel)
        self.window.terminal_tabs.tabCloseRequested.connect(self.window.terminal_manager.close_terminal_tab)

        self.window.editor_terminal_splitter.addWidget(terminal_container)
        # Make terminal panel start hidden but resizable later
        self.window.editor_terminal_splitter.setCollapsible(0, True)
        self.window.editor_terminal_splitter.setCollapsible(1, True)
        self.window.editor_terminal_splitter.setStretchFactor(0, 1)
        self.window.editor_terminal_splitter.setStretchFactor(1, 0)
        QTimer.singleShot(0, lambda: self.window.editor_terminal_splitter.setSizes([max(100, int(self.window.height() * 0.8)), 0]))

    def setup_preview_tabs(self):
        """Setup the preview tabs."""
        self.window.preview_tabs = QTabWidget()
        # Ensure the bottom pane can shrink
        self.window.preview_tabs.setMinimumHeight(0)
        self.window.preview_tabs.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Ignored)
        self.window.preview_tabs.setStyleSheet("""
            QTabWidget::pane { background-color: #1E1F22; border: none; border-radius: 8px; }
            QTabBar::tab { 
                background: #1E1F22; color: #BDC1C6; padding: 10px 20px; 
                border-top-left-radius: 8px; border-top-right-radius: 8px;
            }
            QTabBar::tab:selected { 
                background: #3C4043; color: #E8EAED; 
            }
        """)

        # No Inspect tab in Rust mode
        self.window.web_preview = None 

        # Python Output Preview Tab
        self.window.python_console_output = QPlainTextEdit()
        self.window.python_console_output.setMinimumHeight(0)
        self.window.python_console_output.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Ignored)
        self.window.python_console_output.setReadOnly(True)
        self.window.python_console_output.setFont(QFont("Consolas", 10))
        
        # Set custom context menu policy to style the right-click menu
        self.window.python_console_output.setContextMenuPolicy(Qt.CustomContextMenu)
        self.window.python_console_output.customContextMenuRequested.connect(
            lambda pos: self._show_rust_output_context_menu(pos)
        )
        
        self.window.python_console_output.setStyleSheet("""
            QPlainTextEdit {
                background-color: #1E1E1E; 
                padding: 10px; 
                margin: 0 5px 5px 0; 
                border: none;
                color: #D4D4D4;
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
        self.window.preview_tabs.addTab(self.window.python_console_output, "Rust Run")

        self.window.right_pane_splitter.addWidget(self.window.preview_tabs)
        # Set proportions after the window is shown to avoid zero sizes
        self.window.right_pane_splitter.setCollapsible(0, True)
        self.window.right_pane_splitter.setCollapsible(1, True)
        self.window.right_pane_splitter.setStretchFactor(0, 4)
        self.window.right_pane_splitter.setStretchFactor(1, 6)
        QTimer.singleShot(0, lambda: self.window.right_pane_splitter.setSizes([max(80, int(self.window.height() * 0.4)), max(80, int(self.window.height() * 0.6))]))

        self.window.preview_tabs.currentChanged.connect(self.window.on_tab_changed)
        
        # IMPORTANT: Ensure preview_tabs is visible by default (Files view is default)
        # This ensures proper initial state before window_state_manager restoration
        self.window.preview_tabs.setVisible(True)
        self.window.preview_tabs.show()

    def setup_status_bar(self):
        """Setup the status bar."""
        status_bar = self.window.statusBar()
        status_bar.setStyleSheet("""
            QStatusBar {
                background-color: #131314; 
                color: #BDC1C6; 
                border-top: 1px solid #2C2E33;
            }
            QStatusBar::item {
                border: none;
            }
        """)

        # Check if WebEngine is available
        try:
            from PySide6.QtWebEngineWidgets import QWebEngineView
            WEB_ENGINE_AVAILABLE = True
        except ImportError:
            WEB_ENGINE_AVAILABLE = False
        
        import sys
        if getattr(sys, "frozen", False):
            WEB_ENGINE_AVAILABLE = False
        
        if not WEB_ENGINE_AVAILABLE:
            self.window.statusBar().showMessage("HTML Preview disabled (QtWebEngineWidgets not found)", 5000)
    
    def _setup_file_loading_hook(self):
        """Setup hook to intercept file loading and create file-based projects"""
        try:
            # Store original load_file method
            original_load_file = self.window.manage_widget.load_file
            
            def wrapped_load_file(fp):
                """Wrapper that saves current project and creates file-based project"""
                # Save current project state before loading a file
                try:
                    if hasattr(self.window, 'manage_widget') and hasattr(self.window.manage_widget, 'top_toolbar'):
                        project_state = self.window.manage_widget.top_toolbar.project_state
                        active_project = project_state.get_active_project()
                        
                        if active_project:
                            # Save current canvas state to the active project
                            from Manage.document_io import SaveLoadManager
                            save_manager = SaveLoadManager()
                            canvas_state = save_manager.collect_state(self.window.manage_widget)
                            project_state.update_project_canvas(active_project.id, canvas_state)
                            print(f"[Rust.py] Saved Project {active_project.id} state before loading file")
                except Exception as e:
                    print(f"[Rust.py] Error saving project before load: {e}")
                
                # Now load the file
                original_load_file(fp)
                
                # After loading, create/switch to a project named after the file
                QTimer.singleShot(300, lambda: self._create_file_project(fp))
            
            # Replace the load_file method
            self.window.manage_widget.load_file = wrapped_load_file
            print(f"[Rust.py] File loading hook installed successfully")
        except Exception as e:
            print(f"[Rust.py] Error setting up file loading hook: {e}")
            import traceback
            traceback.print_exc()
    
    def _create_file_project(self, fp: str):
        """Create or update a project for the loaded file"""
        try:
            print(f"[Rust.py] _create_file_project called for: {fp}")
            
            if not hasattr(self.window, 'manage_widget') or not hasattr(self.window.manage_widget, 'top_toolbar'):
                print(f"[Rust.py] ERROR: manage_widget or top_toolbar not available!")
                return
            
            if not fp:
                print(f"[Rust.py] ERROR: No file path provided!")
                return
            
            import os
            filename = os.path.basename(fp)
            project_state = self.window.manage_widget.top_toolbar.project_state
            
            print(f"[Rust.py] Looking for existing project named: {filename}")
            print(f"[Rust.py] Current projects: {[p.name for p in project_state.get_all_projects()]}")
            
            # Check if a project with this filename already exists
            existing_project = None
            for project in project_state.get_all_projects():
                if project.name == filename:
                    existing_project = project
                    break
            
            if existing_project:
                # Update existing project with new canvas state
                print(f"[Rust.py] Found existing project: {filename} (ID: {existing_project.id})")
                self._update_file_project(existing_project.id, filename)
            else:
                # Create new project named after the file
                print(f"[Rust.py] Creating NEW project for file: {filename}")
                new_project = project_state.create_project(name=filename)
                print(f"[Rust.py] Created project: {new_project.name} (ID: {new_project.id})")
                # Wait a bit more for canvas to be fully populated
                QTimer.singleShot(200, lambda: self._update_file_project(new_project.id, filename))
        except Exception as e:
            print(f"[Rust.py] ERROR in _create_file_project: {e}")
            import traceback
            traceback.print_exc()
    
    def _update_file_project(self, project_id: int, filename: str):
        """Update a file-based project with current canvas state and set as active"""
        try:
            project_state = self.window.manage_widget.top_toolbar.project_state
            
            # Collect current canvas state
            from Manage.document_io import SaveLoadManager
            save_manager = SaveLoadManager()
            canvas_state = save_manager.collect_state(self.window.manage_widget)
            
            # Update project
            project_state.update_project_canvas(project_id, canvas_state)
            project_state.set_active_project(project_id)
            
            # Refresh Layer menu
            self.window.manage_widget.top_toolbar.refresh_projects_list()
            
            print(f"[Rust.py] Canvas has {len(self.window.manage_widget.canvas.nodes)} nodes")
            print(f"[Rust.py] ✓ File project '{filename}' updated and set as active (ID: {project_id})")
        except Exception as e:
            print(f"[Rust.py] Error updating file project: {e}")
            import traceback
            traceback.print_exc()
    
    def _show_rust_output_context_menu(self, pos):
        """Show a styled context menu for the Rust Run output terminal."""
        from PySide6.QtWidgets import QMenu
        from PySide6.QtGui import QAction
        
        menu = QMenu(self.window.python_console_output)
        
        # Apply dark theme styling to the context menu
        menu.setStyleSheet("""
            QMenu {
                background-color: #2C2E33;
                color: #E8EAED;
                border: 1px solid #4A4D51;
                padding: 4px;
            }
            QMenu::item {
                background-color: transparent;
                padding: 6px 32px 6px 8px;
                border-radius: 3px;
            }
            QMenu::item:selected {
                background-color: #3C4043;
                color: #FFFFFF;
            }
            QMenu::item:disabled {
                color: #6C6C6C;
            }
            QMenu::separator {
                height: 1px;
                background-color: #4A4D51;
                margin: 4px 8px;
            }
            QMenu::icon {
                padding-left: 4px;
            }
        """)
        
        # Copy action with icon
        copy_action = QAction(QIcon("img/Connection.png"), "Copy", self.window)
        copy_action.triggered.connect(self.window.python_console_output.copy)
        # Enable only if there's selected text
        copy_action.setEnabled(self.window.python_console_output.textCursor().hasSelection())
        menu.addAction(copy_action)
        
        # Select All action with icon
        select_all_action = QAction(QIcon("img/Cursor.png"), "Select All", self.window)
        select_all_action.triggered.connect(self.window.python_console_output.selectAll)
        menu.addAction(select_all_action)
        
        # Show the menu at the cursor position
        menu.exec(self.window.python_console_output.mapToGlobal(pos))
