"""
Window State Manager
Handles saving and restoring window geometry, position, and panel sizes (like VS Code)
"""

import os
import json
from PySide6.QtCore import Qt, QRect, QSize, QPoint


class WindowStateManager:
    """Manages window state persistence (size, position, maximized state, panel sizes)"""
    
    def __init__(self, main_window):
        self.main_window = main_window
        self.state_file = os.path.join(main_window.settings_dir, "window_state.json")
        # Track the last normal (non-maximized) geometry separately
        self._last_normal_geometry = None
        self._was_maximized_before = False
        
    def save_window_state(self):
        """Save window geometry, position, maximized state, and panel sizes"""
        try:
            state = {}
            
            # Window geometry and state
            is_maximized = self.main_window.isMaximized()
            state['maximized'] = is_maximized
            
            # Save geometry intelligently
            if is_maximized:
                # When maximized, use the stored normal geometry if available
                if self._last_normal_geometry:
                    geom = self._last_normal_geometry
                else:
                    # Fallback to normalGeometry() if we don't have it stored
                    geom = self.main_window.normalGeometry()
            else:
                # When not maximized, save current geometry and store it
                geom = self.main_window.geometry()
                # Store this as the last normal geometry for future use
                self._last_normal_geometry = geom
            
            state['x'] = geom.x()
            state['y'] = geom.y()
            state['width'] = geom.width()
            state['height'] = geom.height()
            
            # Save splitter sizes (main horizontal splitter)
            try:
                if hasattr(self.main_window, 'main_splitter'):
                    sizes = self.main_window.main_splitter.sizes()
                    state['main_splitter_sizes'] = sizes
            except Exception:
                pass
            
            # Save right pane splitter sizes (editor + preview tabs)
            try:
                if hasattr(self.main_window, 'right_pane_splitter'):
                    sizes = self.main_window.right_pane_splitter.sizes()
                    state['right_pane_splitter_sizes'] = sizes
            except Exception:
                pass
            
            # Save terminal splitter sizes (if terminal is visible)
            try:
                if hasattr(self.main_window, 'terminal_splitter'):
                    sizes = self.main_window.terminal_splitter.sizes()
                    state['terminal_splitter_sizes'] = sizes
            except Exception:
                pass
            
            # Save file tree width
            try:
                if hasattr(self.main_window, 'tree_view'):
                    state['file_tree_width'] = self.main_window.tree_view.width()
            except Exception:
                pass
            
            # Save Rust console (preview tabs) height
            try:
                if hasattr(self.main_window, 'python_console_output'):
                    state['rust_console_height'] = self.main_window.python_console_output.height()
            except Exception:
                pass
            
            # Save which left panel is active (Files, Search, etc.)
            try:
                if hasattr(self.main_window, 'left_pane_stack'):
                    state['active_left_panel'] = self.main_window.left_pane_stack.currentIndex()
            except Exception:
                pass
            
            # Save preview_tabs visibility state
            try:
                if hasattr(self.main_window, 'preview_tabs'):
                    state['preview_tabs_visible'] = self.main_window.preview_tabs.isVisible()
            except Exception:
                pass
            
            # Ensure settings dir exists
            os.makedirs(self.main_window.settings_dir, exist_ok=True)
            
            # Write to file
            with open(self.state_file, 'w', encoding='utf-8') as f:
                json.dump(state, f, indent=2)
                
        except Exception as e:
            print(f"[WindowStateManager] Error saving window state: {e}")
    
    def on_window_state_changed(self):
        """Called when window state changes (maximize/restore)"""
        try:
            is_maximized = self.main_window.isMaximized()
            
            # If transitioning from normal to maximized, save the current geometry
            if is_maximized and not self._was_maximized_before:
                self._last_normal_geometry = self.main_window.normalGeometry()
            
            self._was_maximized_before = is_maximized
            
            # Save state after change
            self.save_window_state()
        except Exception as e:
            print(f"[WindowStateManager] Error in state change: {e}")
    
    def restore_window_state(self):
        """Restore window geometry, position, maximized state, and panel sizes"""
        try:
            if not os.path.exists(self.state_file):
                return
            
            with open(self.state_file, 'r', encoding='utf-8') as f:
                state = json.load(f)
            
            # Always restore the saved geometry first (this sets the "normal" size)
            x = state.get('x', 100)
            y = state.get('y', 100)
            width = state.get('width', 1400)
            height = state.get('height', 900)
            
            # Set the geometry (this becomes the "normal" geometry for restore)
            self.main_window.setGeometry(x, y, width, height)
            
            # Store this as the last normal geometry
            self._last_normal_geometry = QRect(x, y, width, height)
            
            # Then maximize if it was maximized
            if state.get('maximized', False):
                # Use QTimer to maximize after the window is shown to avoid icon flicker
                from PySide6.QtCore import QTimer
                QTimer.singleShot(50, self.main_window.showMaximized)
                self._was_maximized_before = True
            else:
                self._was_maximized_before = False
            
            # Restore splitter sizes after a short delay to ensure UI is ready
            from PySide6.QtCore import QTimer
            QTimer.singleShot(100, lambda: self._restore_splitter_sizes(state))
            
        except Exception as e:
            print(f"[WindowStateManager] Error restoring window state: {e}")
    
    def _restore_splitter_sizes(self, state):
        """Restore splitter sizes (called after UI is ready)"""
        try:
            # Restore main splitter (file tree + editor area)
            if 'main_splitter_sizes' in state and hasattr(self.main_window, 'main_splitter'):
                sizes = state['main_splitter_sizes']
                if sizes and len(sizes) >= 2:
                    self.main_window.main_splitter.setSizes(sizes)
            
            # Restore which left panel was active (Files=0, Search=1, etc.)
            active_panel = state.get('active_left_panel', 0)
            
            # Check which button is actually checked (more reliable than saved state)
            files_is_active = False
            try:
                if hasattr(self.main_window, 'files_button'):
                    files_is_active = self.main_window.files_button.isChecked()
            except Exception:
                files_is_active = (active_panel == 0)
            
            # If Files panel is active, ensure preview_tabs is visible
            if files_is_active or active_panel == 0:
                # Files panel - always show preview_tabs
                if hasattr(self.main_window, 'preview_tabs'):
                    self.main_window.preview_tabs.setVisible(True)
                    self.main_window.preview_tabs.show()
                    self.main_window.preview_tabs.raise_()
                
                # Use saved sizes if reasonable, otherwise use defaults
                if hasattr(self.main_window, 'right_pane_splitter'):
                    h = max(200, self.main_window.right_pane_splitter.height())
                    default_sizes = [int(h * 0.4), int(h * 0.6)]
                    
                    saved_sizes = state.get('right_pane_splitter_sizes', [])
                    if saved_sizes and len(saved_sizes) >= 2 and saved_sizes[1] > 100:
                        self.main_window.right_pane_splitter.setSizes(saved_sizes)
                    else:
                        self.main_window.right_pane_splitter.setSizes(default_sizes)
                    
                    self.main_window.right_pane_splitter.update()
            else:
                # Search or other panel - restore as saved
                if 'right_pane_splitter_sizes' in state and hasattr(self.main_window, 'right_pane_splitter'):
                    sizes = state['right_pane_splitter_sizes']
                    if sizes and len(sizes) >= 2:
                        self.main_window.right_pane_splitter.setSizes(sizes)
                
                if 'preview_tabs_visible' in state and hasattr(self.main_window, 'preview_tabs'):
                    visible = state['preview_tabs_visible']
                    self.main_window.preview_tabs.setVisible(visible)
            
            # Restore terminal splitter
            if 'terminal_splitter_sizes' in state and hasattr(self.main_window, 'terminal_splitter'):
                sizes = state['terminal_splitter_sizes']
                if sizes and len(sizes) >= 2:
                    self.main_window.terminal_splitter.setSizes(sizes)
            
        except Exception as e:
            print(f"[WindowStateManager] Error restoring splitter sizes: {e}")
