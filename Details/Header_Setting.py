from PySide6.QtWidgets import QMenu, QMenuBar, QWidget, QHBoxLayout, QLabel, QWidgetAction
from PySide6.QtGui import QAction, QIcon, QPixmap
from PySide6.QtCore import Qt
from functools import partial

def populate_recent_files(main_window, recent_menu):
    """Clears and repopulates the 'Open Recent' menu."""
    recent_menu.clear()
    if not main_window.recent_files:
        action = QAction("No Recent Files", main_window)
        action.setEnabled(False)
        recent_menu.addAction(action)
    else:
        for path in main_window.recent_files:
            # Use a partial to capture the correct path for the lambda
            action = QAction(path, main_window)
            action.triggered.connect(partial(main_window.open_file_for_editing, path))
            recent_menu.addAction(action)

def create_main_menu_bar(main_window):
    """
    Creates the application's main menu bar, including all menus and styling.
    """
    menu_bar = QMenuBar()
    menu_bar.setStyleSheet("""
        QMenuBar {
            background-color: transparent;
            color: #BDC1C6;
            font-size: 14px;
        }
        QMenuBar::item {
            padding: 8px 10px;
        }
        QMenuBar::item:selected {
            background: #3C4043;
            color: #E8EAED;
        }
        QMenu {
            background: #282A2E;
            color: #E8EAED;
            font-size: 13px;
            border: 1px solid #4A4D51;
            border-radius: 4px;
            min-width: 240px;
        }
        QMenu::item {
            padding: 8px 24px;
        }
        QMenu::item:selected {
            background: #4A4D51;
        }
        QMenu::separator {
            height: 1px;
            background-color: #4A4D51;
            margin: 6px 1px;
        }
        QMenu::right-arrow {
            subcontrol-origin: padding;
            subcontrol-position: right center;
            right: 15px;
        }
        QMenu::item.shortcut {
            color: #9DA0A5;
        }
    """)

    # --- File Menu ---
    file_menu = menu_bar.addMenu("&File")

    new_file_action = QAction("New File", main_window)
    new_file_action.setShortcut("Ctrl+N")
    new_file_action.triggered.connect(main_window.create_new_file)
    file_menu.addAction(new_file_action)

    new_window_action = QAction("New Window", main_window)
    new_window_action.setShortcut("Ctrl+Shift+N")
    new_window_action.triggered.connect(main_window.new_window)
    file_menu.addAction(new_window_action)

    # New Cargo project creation in the current opened folder
    new_cargo_action = QAction("New Cargo", main_window)
    new_cargo_action.setShortcut("Ctrl+Alt+C")
    new_cargo_action.triggered.connect(main_window.create_cargo_project_here)
    file_menu.addAction(new_cargo_action)

    file_menu.addSeparator()

    open_file_action = QAction("Open File...", main_window)
    open_file_action.setShortcut("Ctrl+O")
    open_file_action.triggered.connect(main_window.open_file)
    file_menu.addAction(open_file_action)

    open_folder_action = QAction("Open Folder...", main_window)
    open_folder_action.setShortcut("Ctrl+K, Ctrl+O")
    open_folder_action.triggered.connect(main_window.open_folder)
    file_menu.addAction(open_folder_action)


    recent_menu = file_menu.addMenu("Open Recent")
    recent_menu.aboutToShow.connect(lambda: populate_recent_files(main_window, recent_menu))

    file_menu.addSeparator()

    save_action = QAction("Save", main_window)
    save_action.setShortcut("Ctrl+S")
    save_action.triggered.connect(main_window.save_file)
    file_menu.addAction(save_action)

    save_as_action = QAction("Save As...", main_window)
    save_as_action.setShortcut("Ctrl+Shift+S")
    save_as_action.triggered.connect(main_window.save_as_file)
    file_menu.addAction(save_as_action)

    save_all_action = QAction("Save All", main_window)
    save_all_action.setShortcut("Ctrl+K S")
    save_all_action.triggered.connect(main_window.save_all_files)
    file_menu.addAction(save_all_action)

    file_menu.addSeparator()

    preferences_menu = file_menu.addMenu("Preferences")
    settings_action = QAction("Settings", main_window)
    settings_action.triggered.connect(main_window.open_settings_dialog)
    preferences_menu.addAction(settings_action)

    file_menu.addSeparator()

    close_editor_action = QAction("Close Editor", main_window)
    close_editor_action.setShortcut("Ctrl+F4")
    close_editor_action.triggered.connect(main_window.close_current_editor)
    file_menu.addAction(close_editor_action)

    close_folder_action = QAction("Close Folder", main_window)
    close_folder_action.setShortcut("Ctrl+K F")
    close_folder_action.triggered.connect(main_window.close_folder)
    file_menu.addAction(close_folder_action)

    close_window_action = QAction("Close Window", main_window)
    close_window_action.setShortcut("Alt+F4")
    close_window_action.triggered.connect(main_window.close)
    file_menu.addAction(close_window_action)

    file_menu.addSeparator()

    exit_action = QAction("Exit", main_window)
    exit_action.triggered.connect(main_window.close)
    file_menu.addAction(exit_action)

    # --- Edit Menu ---
    edit_menu = menu_bar.addMenu("&Edit")
    edit_menu.addAction(QAction("Undo", main_window, shortcut="Ctrl+Z", triggered=main_window.undo))
    edit_menu.addAction(QAction("Redo", main_window, shortcut="Ctrl+Y", triggered=main_window.redo))
    edit_menu.addSeparator()
    edit_menu.addAction(QAction("Cut", main_window, shortcut="Ctrl+X", triggered=main_window.cut))
    edit_menu.addAction(QAction("Copy", main_window, shortcut="Ctrl+C", triggered=main_window.copy))
    edit_menu.addAction(QAction("Paste", main_window, shortcut="Ctrl+V", triggered=main_window.paste))
    edit_menu.addSeparator()
    edit_menu.addAction(QAction("Find", main_window, shortcut="Ctrl+F", triggered=main_window.find_text))
    replace_action = QAction("Replace", main_window)
    replace_action.setShortcut("Ctrl+H")
    replace_action.triggered.connect(main_window.replace_text)
    edit_menu.addAction(replace_action)
    edit_menu.addSeparator()
    toggle_line_comment_action = QAction("Toggle Line Comment", main_window)
    toggle_line_comment_action.setShortcut("Ctrl+/")
    toggle_line_comment_action.triggered.connect(main_window.toggle_line_comment)
    edit_menu.addAction(toggle_line_comment_action)
    toggle_block_comment_action = QAction("Toggle Block Comment", main_window)
    toggle_block_comment_action.setShortcut("Shift+Alt+A")
    toggle_block_comment_action.triggered.connect(main_window.toggle_block_comment)
    edit_menu.addAction(toggle_block_comment_action)


    # --- Selection Menu ---
    selection_menu = menu_bar.addMenu("&Selection")
    selection_menu.addAction(QAction("Select All", main_window, shortcut="Ctrl+A", triggered=main_window.select_all))
    selection_menu.addAction(QAction("Expand Selection", main_window, shortcut="Alt+Shift+Right", triggered=main_window.expand_selection))
    selection_menu.addAction(QAction("Shrink Selection", main_window, shortcut="Alt+Shift+Left", triggered=main_window.shrink_selection))
    selection_menu.addSeparator()
    selection_menu.addAction(QAction("Copy Line Up", main_window, shortcut="Alt+Shift+Up", triggered=main_window.copy_line_up))
    selection_menu.addAction(QAction("Copy Line Down", main_window, shortcut="Alt+Shift+Down", triggered=main_window.copy_line_down))
    selection_menu.addAction(QAction("Move Line Up", main_window, shortcut="Alt+Up", triggered=main_window.move_line_up))
    selection_menu.addAction(QAction("Move Line Down", main_window, shortcut="Alt+Down", triggered=main_window.move_line_down))
    selection_menu.addSeparator()
    # Multi-cursor shortcuts (handled in editor):
    selection_menu.addAction(QAction("Add Cursor Above", main_window, shortcut="Ctrl+Alt+Up", triggered=main_window.add_cursor_above))
    selection_menu.addAction(QAction("Add Cursor Below", main_window, shortcut="Ctrl+Alt+Down", triggered=main_window.add_cursor_below))
    selection_menu.addAction(QAction("Add Cursors to Line Ends", main_window, shortcut="Alt+Shift+I"))
    
    select_next_occurrence_action = QAction("Select Next Occurrence", main_window)
    select_next_occurrence_action.setShortcut("Ctrl+D")
    select_next_occurrence_action.triggered.connect(main_window.select_next_occurrence)
    selection_menu.addAction(select_next_occurrence_action)
    
    select_all_occurrences_action = QAction("Select All Occurrences", main_window)
    select_all_occurrences_action.setShortcut("Ctrl+F2")
    select_all_occurrences_action.triggered.connect(main_window.select_all_occurrences)
    selection_menu.addAction(select_all_occurrences_action)

    # --- View Menu ---
    view_menu = menu_bar.addMenu("&View")
    view_menu.addAction("Toggle Terminal").triggered.connect(main_window.toggle_terminal_panel)

    # --- Terminal Menu ---
    terminal_menu = menu_bar.addMenu("&Terminal")
    new_terminal_action = QAction("New Terminal", main_window)
    new_terminal_action.setShortcut("Ctrl+Shift+`")
    new_terminal_action.triggered.connect(main_window.add_new_terminal)
    terminal_menu.addAction(new_terminal_action)

    # --- Help Menu ---
    help_menu = menu_bar.addMenu("&Help")
    welcome_action = QAction("Welcome", main_window)
    welcome_action.triggered.connect(main_window.show_welcome_page)
    help_menu.addAction(welcome_action)
    documentation_action = QAction("Documentation", main_window)
    documentation_action.triggered.connect(main_window.open_documentation)
    help_menu.addAction(documentation_action)
    help_menu.addSeparator()
    keyboard_shortcuts_action = QAction("Keyboard Shortcuts", main_window)
    keyboard_shortcuts_action.setShortcut("Ctrl+K, Ctrl+R")
    keyboard_shortcuts_action.triggered.connect(main_window.show_keyboard_shortcuts)
    help_menu.addAction(keyboard_shortcuts_action)
    video_tutorials_action = QAction("Video Tutorials", main_window)
    video_tutorials_action.triggered.connect(main_window.open_video_tutorials)
    help_menu.addAction(video_tutorials_action)
    tips_and_tricks_action = QAction("Tips and Tricks", main_window)
    tips_and_tricks_action.triggered.connect(main_window.show_tips_and_tricks)
    help_menu.addAction(tips_and_tricks_action)
    help_menu.addSeparator()
    youtube_action = QAction("Join Us On Youtube", main_window)
    youtube_action.triggered.connect(main_window.join_youtube)
    help_menu.addAction(youtube_action)
    report_issue_action = QAction("Report Issue", main_window)
    report_issue_action.triggered.connect(main_window.report_issue)
    help_menu.addAction(report_issue_action)
    help_menu.addSeparator()
    license_widget = QWidget()
    license_widget.setStyleSheet("QWidget { background: transparent; padding: 0px; margin: 0px; border: 0px; } QWidget:hover { background: #4A4D51; }")
    license_layout = QHBoxLayout(license_widget)
    license_layout.setContentsMargins(24, 8, 15, 8) # L, T, R, B
    license_label = QLabel("View License")
    license_label.setStyleSheet("color: #E8EAED;")
    license_icon = QLabel()
    license_icon.setPixmap(QPixmap("img/Lincense.png").scaled(16, 16, Qt.KeepAspectRatio, Qt.SmoothTransformation))
    license_layout.addWidget(license_label)
    license_layout.addStretch()
    license_layout.addWidget(license_icon)
    
    license_action = QWidgetAction(main_window)
    license_action.setDefaultWidget(license_widget)
    license_action.triggered.connect(main_window.view_license)
    help_menu.addAction(license_action)

    update_action = QAction("Check For Updates", main_window)
    update_action.triggered.connect(main_window.check_for_updates)
    help_menu.addAction(update_action)
    help_menu.addSeparator()
    about_action = QAction("About", main_window)
    about_action.triggered.connect(main_window.show_about_dialog)
    help_menu.addAction(about_action)

    return menu_bar
