"""
UI Components Module 2 - Custom Content Editors
Contains resizable editors for Text, Image, and Video content nodes
"""

import os
from PySide6.QtCore import Qt, Signal, QSize, QEvent, QUrl
from PySide6.QtGui import (
    QPainter, QPen, QBrush, QColor, QFont, QPixmap, QMouseEvent, QResizeEvent
)
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, 
    QFrame, QSizeGrip, QPlainTextEdit, QSlider
)
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtMultimediaWidgets import QVideoWidget

from .data_analysis import DARK_THEME


class ResizableTextEditor(QFrame):
    """ A movable, resizable frame for custom text editing (for Text Content nodes). """
    closed = Signal()
    text_changed = Signal(str)  # Emits the updated text content

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(400, 300)
        self.setWindowFlags(Qt.SubWindow | Qt.FramelessWindowHint)
        self.setFrameShape(QFrame.StyledPanel)
        
        # --- Custom Styling ---
        self.setStyleSheet(f"""
            ResizableTextEditor {{
                background-color: {DARK_THEME['bg_primary']};
                border: 1px solid {DARK_THEME['border']};
                border-radius: 15px;
            }}
        """)

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(1, 1, 1, 1)
        self.main_layout.setSpacing(0)

        # --- Title Bar ---
        self.title_bar = QWidget()
        self.title_bar.setFixedHeight(35)
        self.title_bar.setStyleSheet(f"""
            QWidget {{
                background-color: {DARK_THEME['bg_secondary']};
                border-top-left-radius: 14px;
                border-top-right-radius: 14px;
                border-bottom: 1px solid {DARK_THEME['border']};
            }}
        """)
        title_layout = QHBoxLayout(self.title_bar)
        title_layout.setContentsMargins(15, 0, 5, 0)

        self.title_label = QLabel("Text Content")
        self.title_label.setStyleSheet(f"color: {DARK_THEME['text_primary']}; font-weight: bold; border: none;")
        
        self.close_button = QPushButton("✕")
        self.close_button.setFixedSize(25, 25)
        self.close_button.setStyleSheet("""
            QPushButton { background: transparent; color: #BDC1C6; border: none; font-size: 16px; }
            QPushButton:hover { color: #E81123; }
        """)
        self.close_button.clicked.connect(self.hide)
        self.close_button.clicked.connect(self.closed.emit)

        title_layout.addWidget(self.title_label)
        title_layout.addStretch()
        title_layout.addWidget(self.close_button)

        # --- Text Editor (QPlainTextEdit for better performance with large text) ---
        self.editor = QPlainTextEdit()
        self.editor.setPlaceholderText("Write your notes, explanations, or documentation here...")
        
        # Set a nice readable font for writing
        font = QFont("Segoe UI", 11)
        self.editor.setFont(font)
        self._base_font = QFont(font)
        
        # Enable word wrap for comfortable writing
        self.editor.setLineWrapMode(QPlainTextEdit.WidgetWidth)
        
        # Connect text changes
        self.editor.textChanged.connect(self._on_text_changed)
        
        # Install event filter for zoom shortcuts
        self.editor.installEventFilter(self)
        
        self.editor.setStyleSheet(f"""
            QPlainTextEdit {{ 
                border: none; 
                border-bottom-left-radius: 14px; 
                border-bottom-right-radius: 14px;
                padding: 15px;
                background-color: {DARK_THEME['bg_primary']};
                color: {DARK_THEME['text_primary']};
                selection-background-color: {DARK_THEME['accent']};
            }}
            QScrollBar:vertical {{
                background: #1E1F22;
                width: 12px;
                border: none;
                border-radius: 0px;
                margin: 0px;
            }}
            QScrollBar::handle:vertical {{
                background: rgba(85, 85, 85, 0.6);
                border-radius: 0px;
                min-height: 20px;
                margin: 2px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: rgba(102, 102, 102, 0.9);
            }}
            QScrollBar::handle:vertical:pressed {{
                background: rgba(119, 119, 119, 1.0);
            }}
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {{
                height: 0px;
                background: none;
            }}
            QScrollBar::add-page:vertical,
            QScrollBar::sub-page:vertical {{
                background: none;
            }}
            QScrollBar:horizontal {{
                background: #1E1F22;
                height: 12px;
                border: none;
                border-radius: 0px;
                margin: 0px;
            }}
            QScrollBar::handle:horizontal {{
                background: rgba(85, 85, 85, 0.6);
                border-radius: 0px;
                min-width: 20px;
                margin: 2px;
            }}
            QScrollBar::handle:horizontal:hover {{
                background: rgba(102, 102, 102, 0.9);
            }}
            QScrollBar::handle:horizontal:pressed {{
                background: rgba(119, 119, 119, 1.0);
            }}
            QScrollBar::add-line:horizontal,
            QScrollBar::sub-line:horizontal {{
                width: 0px;
                background: none;
            }}
            QScrollBar::add-page:horizontal,
            QScrollBar::sub-page:horizontal {{
                background: none;
            }}
        """)

        self.main_layout.addWidget(self.title_bar)
        self.main_layout.addWidget(self.editor)

        # --- Resizing Grip ---
        self.grip = QSizeGrip(self)
        self.grip.setFixedSize(16, 16)
        
        self._drag_start_position = None
        self._current_node = None  # Store reference to the node being edited

    def set_text_content(self, title: str, text: str, node=None):
        """Set the content of the text editor."""
        self.title_label.setText(title)
        self.editor.setPlainText(text or "")
        self._current_node = node

    def get_text_content(self) -> str:
        """Get the current text content."""
        return self.editor.toPlainText()

    def _on_text_changed(self):
        """Handle text changes and update the node."""
        if self._current_node:
            try:
                # Update the node's data with the new text
                if hasattr(self._current_node, 'data') and isinstance(self._current_node.data, dict):
                    self._current_node.data['text_content'] = self.get_text_content()
                    # Emit signal for external listeners
                    self.text_changed.emit(self.get_text_content())
            except Exception:
                pass

    def resizeEvent(self, event: QResizeEvent):
        """Places the grip in the bottom-right corner."""
        super().resizeEvent(event)
        self.grip.move(self.width() - self.grip.width(), self.height() - self.grip.height())

    def mousePressEvent(self, event: QMouseEvent):
        """Captures mouse press for dragging the window."""
        if event.button() == Qt.LeftButton and self.title_bar.geometry().contains(event.pos()):
            self._drag_start_position = event.globalPosition().toPoint() - self.pos()
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent):
        """Moves the window if dragging."""
        if self._drag_start_position:
            self.move(event.globalPosition().toPoint() - self._drag_start_position)
            event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent):
        """Resets the drag position."""
        self._drag_start_position = None
        event.accept()

    def eventFilter(self, obj, event):
        """Handle zoom shortcuts (Ctrl+Plus, Ctrl+Minus, Ctrl+0)."""
        try:
            if obj is self.editor and event.type() == QEvent.KeyPress and (event.modifiers() & Qt.ControlModifier):
                if event.key() in (Qt.Key_Plus, Qt.Key_Equal):
                    # Zoom in
                    f = self.editor.font()
                    f.setPointSizeF(f.pointSizeF() + 1)
                    self.editor.setFont(f)
                    return True
                if event.key() == Qt.Key_Minus:
                    # Zoom out
                    f = self.editor.font()
                    f.setPointSizeF(max(6, f.pointSizeF() - 1))
                    self.editor.setFont(f)
                    return True
                if event.key() == Qt.Key_0:
                    # Reset zoom
                    if getattr(self, '_base_font', None):
                        self.editor.setFont(self._base_font)
                    return True
        except Exception:
            pass
        return super().eventFilter(obj, event)


class ResizableImageEditor(QFrame):
    """ A movable, resizable frame for image upload and display (for Image Content nodes). """
    closed = Signal()
    image_changed = Signal(str)  # Emits the image file path

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(400, 350)
        self.setWindowFlags(Qt.SubWindow | Qt.FramelessWindowHint)
        self.setFrameShape(QFrame.StyledPanel)
        
        # --- Custom Styling ---
        self.setStyleSheet(f"""
            ResizableImageEditor {{
                background-color: {DARK_THEME['bg_primary']};
                border: 1px solid {DARK_THEME['border']};
                border-radius: 15px;
            }}
        """)

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(1, 1, 1, 1)
        self.main_layout.setSpacing(0)

        # --- Title Bar ---
        self.title_bar = QWidget()
        self.title_bar.setFixedHeight(35)
        self.title_bar.setStyleSheet(f"""
            QWidget {{
                background-color: {DARK_THEME['bg_secondary']};
                border-top-left-radius: 14px;
                border-top-right-radius: 14px;
                border-bottom: 1px solid {DARK_THEME['border']};
            }}
        """)
        title_layout = QHBoxLayout(self.title_bar)
        title_layout.setContentsMargins(15, 0, 5, 0)

        self.title_label = QLabel("Image Content")
        self.title_label.setStyleSheet(f"color: {DARK_THEME['text_primary']}; font-weight: bold; border: none;")
        
        self.close_button = QPushButton("✕")
        self.close_button.setFixedSize(25, 25)
        self.close_button.setStyleSheet("""
            QPushButton { background: transparent; color: #BDC1C6; border: none; font-size: 16px; }
            QPushButton:hover { color: #E81123; }
        """)
        self.close_button.clicked.connect(self.hide)
        self.close_button.clicked.connect(self.closed.emit)

        title_layout.addWidget(self.title_label)
        title_layout.addStretch()
        title_layout.addWidget(self.close_button)

        # --- Content Area ---
        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(15, 15, 15, 15)
        self.content_layout.setSpacing(10)
        
        # Image display label
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setMinimumSize(300, 300)
        self.image_label.setStyleSheet(f"""
            QLabel {{
                background-color: {DARK_THEME['bg_secondary']};
                border: 2px dashed {DARK_THEME['border']};
                border-radius: 10px;
                color: {DARK_THEME['text_secondary']};
                font-size: 14px;
            }}
        """)
        self.image_label.setText("Click 'Upload Image' to select an image\n\n(Max 10MB)")
        self.content_layout.addWidget(self.image_label, 1)
        
        # Upload button (styled like toolbar buttons)
        self.upload_button = QPushButton("Upload Image")
        self.upload_button.setFixedHeight(40)
        self.upload_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {DARK_THEME['bg_secondary']};
                color: {DARK_THEME['text_primary']};
                border: 1px solid {DARK_THEME['border']};
                border-radius: 8px;
                font-size: 14px;
                font-weight: bold;
                padding: 8px 16px;
            }}
            QPushButton:hover {{
                background-color: {DARK_THEME['bg_tertiary']};
                border-color: {DARK_THEME['text_secondary']};
            }}
            QPushButton:pressed {{
                background-color: {DARK_THEME['bg_primary']};
            }}
        """)
        self.upload_button.clicked.connect(self._upload_image)
        self.content_layout.addWidget(self.upload_button)
        
        # Info label
        self.info_label = QLabel("Supported formats: PNG, JPG, JPEG, GIF, BMP")
        self.info_label.setAlignment(Qt.AlignCenter)
        self.info_label.setStyleSheet(f"color: {DARK_THEME['text_secondary']}; font-size: 11px;")
        self.content_layout.addWidget(self.info_label)

        self.content_widget.setStyleSheet(f"""
            QWidget {{
                background-color: {DARK_THEME['bg_primary']};
                border-bottom-left-radius: 14px;
                border-bottom-right-radius: 14px;
            }}
        """)

        self.main_layout.addWidget(self.title_bar)
        self.main_layout.addWidget(self.content_widget)

        # --- Resizing Grip ---
        self.grip = QSizeGrip(self)
        self.grip.setFixedSize(16, 16)
        
        self._drag_start_position = None
        self._current_node = None
        self._image_path = None

    def set_image_content(self, title: str, image_path: str, node=None):
        """Set the image content."""
        self.title_label.setText(title)
        self._current_node = node
        self._image_path = image_path
        
        if image_path and os.path.exists(image_path):
            self._display_image(image_path)
        else:
            self.image_label.setText("Click 'Upload Image' to select an image\n\n(Max 10MB)")

    def _display_image(self, image_path: str):
        """Display the image in the label."""
        try:
            pixmap = QPixmap(image_path)
            if not pixmap.isNull():
                # Scale to fit while maintaining aspect ratio
                scaled_pixmap = pixmap.scaled(
                    self.image_label.size(),
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation
                )
                self.image_label.setPixmap(scaled_pixmap)
                self.info_label.setText(f"Image: {os.path.basename(image_path)}")
            else:
                self.image_label.setText("❌\n\nFailed to load image")
        except Exception as e:
            self.image_label.setText(f"❌\n\nError loading image:\n{str(e)}")

    def _upload_image(self):
        """Open file dialog to upload an image."""
        from PySide6.QtWidgets import QFileDialog, QMessageBox
        
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Image",
            "",
            "Images (*.png *.jpg *.jpeg *.gif *.bmp);;All Files (*)"
        )
        
        if file_path:
            # Check file size (max 10MB)
            try:
                file_size = os.path.getsize(file_path)
                max_size = 10 * 1024 * 1024  # 10MB in bytes
                
                if file_size > max_size:
                    QMessageBox.warning(
                        self,
                        "File Too Large",
                        f"Image size is {file_size / (1024*1024):.2f}MB.\nMaximum allowed size is 10MB."
                    )
                    return
                
                # Store the image path
                self._image_path = file_path
                self._display_image(file_path)
                
                # Update node data
                if self._current_node:
                    try:
                        if hasattr(self._current_node, 'data') and isinstance(self._current_node.data, dict):
                            self._current_node.data['image_path'] = file_path
                            self.image_changed.emit(file_path)
                    except Exception:
                        pass
                        
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to load image:\n{str(e)}")

    def resizeEvent(self, event: QResizeEvent):
        """Places the grip in the bottom-right corner and rescales image."""
        super().resizeEvent(event)
        self.grip.move(self.width() - self.grip.width(), self.height() - self.grip.height())
        
        # Rescale image if one is loaded
        if self._image_path and os.path.exists(self._image_path):
            self._display_image(self._image_path)

    def mousePressEvent(self, event: QMouseEvent):
        """Captures mouse press for dragging the window."""
        if event.button() == Qt.LeftButton and self.title_bar.geometry().contains(event.pos()):
            self._drag_start_position = event.globalPosition().toPoint() - self.pos()
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent):
        """Moves the window if dragging."""
        if self._drag_start_position:
            self.move(event.globalPosition().toPoint() - self._drag_start_position)
            event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent):
        """Resets the drag position."""
        self._drag_start_position = None
        event.accept()


class ResizableVideoEditor(QFrame):
    """ A movable, resizable frame for video upload and playback (for Video Content nodes). """
    closed = Signal()
    video_changed = Signal(str)  # Emits the video file path

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(500, 450)
        self.setWindowFlags(Qt.SubWindow | Qt.FramelessWindowHint)
        self.setFrameShape(QFrame.StyledPanel)
        
        # --- Custom Styling ---
        self.setStyleSheet(f"""
            ResizableVideoEditor {{
                background-color: {DARK_THEME['bg_primary']};
                border: 1px solid {DARK_THEME['border']};
                border-radius: 15px;
            }}
        """)

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(1, 1, 1, 1)
        self.main_layout.setSpacing(0)

        # --- Title Bar ---
        self.title_bar = QWidget()
        self.title_bar.setFixedHeight(35)
        self.title_bar.setStyleSheet(f"""
            QWidget {{
                background-color: {DARK_THEME['bg_secondary']};
                border-top-left-radius: 14px;
                border-top-right-radius: 14px;
                border-bottom: 1px solid {DARK_THEME['border']};
            }}
        """)
        title_layout = QHBoxLayout(self.title_bar)
        title_layout.setContentsMargins(15, 0, 5, 0)

        self.title_label = QLabel("Video Content")
        self.title_label.setStyleSheet(f"color: {DARK_THEME['text_primary']}; font-weight: bold; border: none;")
        
        self.close_button = QPushButton("✕")
        self.close_button.setFixedSize(25, 25)
        self.close_button.setStyleSheet("""
            QPushButton { background: transparent; color: #BDC1C6; border: none; font-size: 16px; }
            QPushButton:hover { color: #E81123; }
        """)
        self.close_button.clicked.connect(self._on_close)

        title_layout.addWidget(self.title_label)
        title_layout.addStretch()
        title_layout.addWidget(self.close_button)

        # --- Content Area ---
        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(15, 15, 15, 15)
        self.content_layout.setSpacing(10)
        
        # Video widget for playback
        self.video_widget = QVideoWidget()
        self.video_widget.setMinimumSize(400, 250)
        self.video_widget.setStyleSheet(f"""
            QVideoWidget {{
                background-color: {DARK_THEME['bg_secondary']};
                border: 2px solid {DARK_THEME['border']};
                border-radius: 10px;
            }}
        """)
        self.content_layout.addWidget(self.video_widget, 1)
        
        # Placeholder label (shown when no video is loaded)
        self.placeholder_label = QLabel()
        self.placeholder_label.setAlignment(Qt.AlignCenter)
        self.placeholder_label.setMinimumSize(400, 300)
        self.placeholder_label.setStyleSheet(f"""
            QLabel {{
                background-color: {DARK_THEME['bg_secondary']};
                border: 2px dashed {DARK_THEME['border']};
                border-radius: 10px;
                color: {DARK_THEME['text_secondary']};
                font-size: 14px;
            }}
        """)
        self.placeholder_label.setText("Click 'Upload Video' to select a video\n\n(Max 100MB)")
        self.content_layout.addWidget(self.placeholder_label, 1)
        
        # Media player setup
        self.media_player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.media_player.setAudioOutput(self.audio_output)
        self.media_player.setVideoOutput(self.video_widget)
        
        # Connect media player signals
        self.media_player.positionChanged.connect(self._update_position)
        self.media_player.durationChanged.connect(self._update_duration)
        self.media_player.playbackStateChanged.connect(self._update_play_button)
        
        # Progress slider (with fixed height to ensure visibility)
        self.position_slider = QSlider(Qt.Horizontal)
        self.position_slider.setRange(0, 0)
        self.position_slider.sliderMoved.connect(self._set_position)
        self.position_slider.setFixedHeight(30)
        self.position_slider.setStyleSheet(f"""
            QSlider {{
                margin-top: 10px;
                margin-bottom: 5px;
            }}
            QSlider::groove:horizontal {{
                background: {DARK_THEME['bg_secondary']};
                height: 8px;
                border-radius: 4px;
                border: 1px solid {DARK_THEME['border']};
            }}
            QSlider::handle:horizontal {{
                background: {DARK_THEME['text_secondary']};
                width: 16px;
                height: 16px;
                margin: -5px 0;
                border-radius: 8px;
                border: 1px solid {DARK_THEME['border']};
            }}
            QSlider::handle:horizontal:hover {{
                background: white;
                width: 18px;
                height: 18px;
                margin: -6px 0;
                border-radius: 9px;
            }}
            QSlider::sub-page:horizontal {{
                background: {DARK_THEME['text_secondary']};
                border-radius: 4px;
            }}
        """)
        self.content_layout.addWidget(self.position_slider, 0)
        
        # Video controls container
        self.controls_widget = QWidget()
        self.controls_layout = QHBoxLayout(self.controls_widget)
        self.controls_layout.setContentsMargins(0, 5, 0, 0)
        self.controls_layout.setSpacing(10)
        
        # Play/Pause button (icon only) - LEFT SIDE
        self.play_button = QPushButton("▶")
        self.play_button.setFixedSize(36, 36)
        self.play_button.setToolTip("Play")
        self.play_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {DARK_THEME['bg_secondary']};
                color: {DARK_THEME['text_primary']};
                border: 1px solid {DARK_THEME['border']};
                border-radius: 18px;
                font-size: 14px;
            }}
            QPushButton:hover {{
                background-color: {DARK_THEME['bg_tertiary']};
            }}
            QPushButton:pressed {{
                background-color: {DARK_THEME['bg_primary']};
            }}
            QPushButton:disabled {{
                background-color: {DARK_THEME['bg_secondary']};
                color: {DARK_THEME['text_secondary']};
            }}
        """)
        self.play_button.clicked.connect(self._toggle_playback)
        self.play_button.setEnabled(False)
        self.controls_layout.addWidget(self.play_button)
        
        # Stop button (icon only) - LEFT SIDE
        self.stop_button = QPushButton("⏹")
        self.stop_button.setFixedSize(36, 36)
        self.stop_button.setToolTip("Stop")
        self.stop_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {DARK_THEME['bg_secondary']};
                color: {DARK_THEME['text_primary']};
                border: 1px solid {DARK_THEME['border']};
                border-radius: 18px;
                font-size: 14px;
            }}
            QPushButton:hover {{
                background-color: {DARK_THEME['bg_tertiary']};
            }}
            QPushButton:pressed {{
                background-color: {DARK_THEME['bg_primary']};
            }}
            QPushButton:disabled {{
                background-color: {DARK_THEME['bg_secondary']};
                color: {DARK_THEME['text_secondary']};
            }}
        """)
        self.stop_button.clicked.connect(self._stop_playback)
        self.stop_button.setEnabled(False)
        self.controls_layout.addWidget(self.stop_button)
        
        # Time label - LEFT SIDE after buttons
        self.time_label = QLabel("00:00 / 00:00")
        self.time_label.setStyleSheet(f"color: {DARK_THEME['text_secondary']}; font-size: 11px;")
        self.controls_layout.addWidget(self.time_label)
        
        self.controls_layout.addStretch()
        
        # Volume slider - RIGHT SIDE
        volume_label = QLabel("🔊")
        volume_label.setStyleSheet(f"color: {DARK_THEME['text_secondary']};")
        self.controls_layout.addWidget(volume_label)
        
        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(50)
        self.volume_slider.setFixedWidth(100)
        self.volume_slider.setFixedHeight(20)
        self.volume_slider.valueChanged.connect(self._set_volume)
        self.volume_slider.setStyleSheet(f"""
            QSlider::groove:horizontal {{
                background: {DARK_THEME['bg_secondary']};
                height: 6px;
                border-radius: 3px;
                border: 1px solid {DARK_THEME['border']};
            }}
            QSlider::handle:horizontal {{
                background: {DARK_THEME['text_secondary']};
                width: 12px;
                height: 12px;
                margin: -4px 0;
                border-radius: 6px;
                border: 1px solid {DARK_THEME['border']};
            }}
            QSlider::handle:horizontal:hover {{
                background: white;
                width: 14px;
                height: 14px;
                margin: -5px 0;
                border-radius: 7px;
            }}
            QSlider::sub-page:horizontal {{
                background: {DARK_THEME['text_secondary']};
                border-radius: 3px;
            }}
        """)
        self.controls_layout.addWidget(self.volume_slider)
        
        self.content_layout.addWidget(self.controls_widget)
        self.controls_widget.hide()  # Hidden until video is loaded
        
        # Upload button
        self.upload_button = QPushButton("Upload Video")
        self.upload_button.setFixedHeight(40)
        self.upload_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {DARK_THEME['bg_secondary']};
                color: {DARK_THEME['text_primary']};
                border: 1px solid {DARK_THEME['border']};
                border-radius: 8px;
                font-size: 14px;
                font-weight: bold;
                padding: 8px 16px;
            }}
            QPushButton:hover {{
                background-color: {DARK_THEME['bg_tertiary']};
                border-color: {DARK_THEME['text_secondary']};
            }}
            QPushButton:pressed {{
                background-color: {DARK_THEME['bg_primary']};
            }}
        """)
        self.upload_button.clicked.connect(self._upload_video)
        self.content_layout.addWidget(self.upload_button)
        
        # Info label
        self.info_label = QLabel("Supported formats: MP4, AVI, MOV, MKV, WEBM")
        self.info_label.setAlignment(Qt.AlignCenter)
        self.info_label.setStyleSheet(f"color: {DARK_THEME['text_secondary']}; font-size: 11px;")
        self.content_layout.addWidget(self.info_label)

        self.content_widget.setStyleSheet(f"""
            QWidget {{
                background-color: {DARK_THEME['bg_primary']};
                border-bottom-left-radius: 14px;
                border-bottom-right-radius: 14px;
            }}
        """)

        self.main_layout.addWidget(self.title_bar)
        self.main_layout.addWidget(self.content_widget)

        # --- Resizing Grip ---
        self.grip = QSizeGrip(self)
        self.grip.setFixedSize(16, 16)
        
        self._drag_start_position = None
        self._current_node = None
        self._video_path = None
        
        # Set initial volume
        self._set_volume(50)

    def set_video_content(self, title: str, video_path: str, node=None):
        """Set the video content."""
        self.title_label.setText(title)
        self._current_node = node
        self._video_path = video_path
        
        if video_path and os.path.exists(video_path):
            self._load_video(video_path)
        else:
            self.placeholder_label.show()
            self.video_widget.hide()
            self.position_slider.hide()
            self.controls_widget.hide()
            self.placeholder_label.setText("Click 'Upload Video' to select a video\n\n(Max 100MB)")

    def _load_video(self, video_path: str):
        """Load and prepare video for playback."""
        try:
            file_name = os.path.basename(video_path)
            
            # Load the video
            self.media_player.setSource(QUrl.fromLocalFile(video_path))
            
            # Show video widget and controls, hide placeholder
            self.placeholder_label.hide()
            self.video_widget.show()
            self.position_slider.show()
            self.controls_widget.show()
            
            # Enable controls
            self.play_button.setEnabled(True)
            self.stop_button.setEnabled(True)
            
            # Update info
            file_size = os.path.getsize(video_path)
            size_mb = file_size / (1024 * 1024)
            self.info_label.setText(f"Video: {file_name} ({size_mb:.2f} MB)")
            
        except Exception as e:
            self.placeholder_label.show()
            self.video_widget.hide()
            self.position_slider.hide()
            self.controls_widget.hide()
            self.placeholder_label.setText(f"❌\n\nError loading video:\n{str(e)}")
    
    def _toggle_playback(self):
        """Toggle between play and pause."""
        if self.media_player.playbackState() == QMediaPlayer.PlayingState:
            self.media_player.pause()
        else:
            self.media_player.play()
    
    def _stop_playback(self):
        """Stop video playback."""
        self.media_player.stop()
    
    def _set_position(self, position):
        """Set video position from slider."""
        self.media_player.setPosition(position)
    
    def _set_volume(self, volume):
        """Set audio volume (0-100)."""
        self.audio_output.setVolume(volume / 100.0)
    
    def _update_position(self, position):
        """Update slider position as video plays."""
        self.position_slider.setValue(position)
        self._update_time_label()
    
    def _update_duration(self, duration):
        """Update slider range when video duration is known."""
        self.position_slider.setRange(0, duration)
        self._update_time_label()
    
    def _update_time_label(self):
        """Update the time display label."""
        position = self.media_player.position()
        duration = self.media_player.duration()
        
        pos_min = position // 60000
        pos_sec = (position % 60000) // 1000
        dur_min = duration // 60000
        dur_sec = (duration % 60000) // 1000
        
        self.time_label.setText(f"{pos_min:02d}:{pos_sec:02d} / {dur_min:02d}:{dur_sec:02d}")
    
    def _update_play_button(self, state):
        """Update play button icon and tooltip based on playback state."""
        if state == QMediaPlayer.PlayingState:
            self.play_button.setText("⏸")
            self.play_button.setToolTip("Pause")
        else:
            self.play_button.setText("▶")
            self.play_button.setToolTip("Play")
    
    def _on_close(self):
        """Handle close button - stop playback and hide."""
        self.media_player.stop()
        self.hide()
        self.closed.emit()

    def _upload_video(self):
        """Open file dialog to upload a video."""
        from PySide6.QtWidgets import QFileDialog, QMessageBox
        
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Video",
            "",
            "Videos (*.mp4 *.avi *.mov *.mkv *.webm *.flv *.wmv);;All Files (*)"
        )
        
        if file_path:
            # Check file size (max 100MB)
            try:
                file_size = os.path.getsize(file_path)
                max_size = 100 * 1024 * 1024  # 100MB in bytes
                
                if file_size > max_size:
                    QMessageBox.warning(
                        self,
                        "File Too Large",
                        f"Video size is {file_size / (1024*1024):.2f}MB.\nMaximum allowed size is 100MB."
                    )
                    return
                
                # Store the video path
                self._video_path = file_path
                self._load_video(file_path)
                
                # Update node data
                if self._current_node:
                    try:
                        if hasattr(self._current_node, 'data') and isinstance(self._current_node.data, dict):
                            self._current_node.data['video_path'] = file_path
                            self.video_changed.emit(file_path)
                    except Exception:
                        pass
                        
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to load video:\n{str(e)}")

    def resizeEvent(self, event: QResizeEvent):
        """Places the grip in the bottom-right corner."""
        super().resizeEvent(event)
        self.grip.move(self.width() - self.grip.width(), self.height() - self.grip.height())

    def mousePressEvent(self, event: QMouseEvent):
        """Captures mouse press for dragging the window."""
        if event.button() == Qt.LeftButton and self.title_bar.geometry().contains(event.pos()):
            self._drag_start_position = event.globalPosition().toPoint() - self.pos()
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent):
        """Moves the window if dragging."""
        if self._drag_start_position:
            self.move(event.globalPosition().toPoint() - self._drag_start_position)
            event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent):
        """Resets the drag position."""
        self._drag_start_position = None
        event.accept()
