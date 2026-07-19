"""Light and dark theme stylesheets for ADB Explorer."""

LIGHT = """
/* ── Root / Global ─────────────────────────────────────── */
QMainWindow, QDialog {
    background-color: #f5f5f5;
}
QWidget {
    font-family: "Segoe UI Variable", "Segoe UI", "Helvetica Neue", sans-serif;
    font-size: 12px;
    color: #2c2c2c;
}

/* ── Device header ─────────────────────────────────────── */
#device_header {
    font-weight: 700;
    font-size: 13px;
    padding: 4px 8px;
    background: #f0f4fa;
    border-bottom: 1px solid #d0d8e4;
}

/* ── Navigation bar ────────────────────────────────────── */
#nav_container {
    background: #ffffff;
    border-bottom: 1px solid #e4e4e4;
    padding: 2px;
}
QPushButton#back_btn {
    background: transparent;
    border: 1px solid #d8d8d8;
    border-radius: 4px;
    font-size: 14px;
    padding: 2px 8px;
    color: #555;
}
QPushButton#back_btn:hover {
    background: #f0f0f0;
    border-color: #c8c8c8;
}
QPushButton#back_btn:disabled {
    color: #ccc;
    border-color: #eee;
}
QPushButton#back_btn:pressed {
    background: #e4e4e4;
}
#nav_container QPushButton {
    background: transparent;
    border: 1px solid #d8d8d8;
    border-radius: 4px;
    padding: 4px 12px;
    color: #444;
}
#nav_container QPushButton:hover {
    background: #f0f7ff;
    border-color: #4a8fe0;
    color: #4a8fe0;
}
#nav_container QPushButton:pressed {
    background: #dce8f5;
}
#search_bar, QLineEdit {
    background: #ffffff;
    border: 1px solid #d8d8d8;
    border-radius: 4px;
    padding: 3px 8px;
    font-size: 12px;
    selection-background-color: #4a8fe0;
}
#search_bar:focus, QLineEdit:focus {
    border-color: #4a8fe0;
}
QLineEdit#path_display {
    padding: 3px 8px;
    font-size: 11px;
}

/* ── Tree view (file browser) ──────────────────────────── */
QTreeView {
    background-color: #ffffff;
    alternate-background-color: #fafafa;
    border: none;
    outline: none;
    font-size: 12px;
}
QTreeView::item {
    padding: 3px 2px;
    min-height: 26px;
}
QTreeView::item:selected:active {
    background-color: #e3effa;
    color: #1a5a9e;
}
QTreeView::item:selected:!active {
    background-color: #f0f0f0;
    color: #444;
}
QTreeView::item:hover:!selected {
    background-color: #f5f7fa;
}
QTreeView QHeaderView {
    background: #fafafa;
}
QTreeView QHeaderView::section {
    background: #fafafa;
    color: #888;
    font-weight: 600;
    font-size: 10px;
    letter-spacing: 0.5px;
    padding: 5px 4px;
    border: none;
    border-bottom: 1px solid #e4e4e4;
    border-right: 1px solid #eee;
}

/* ── Menu bar ──────────────────────────────────────────── */
QMenuBar {
    background: #ffffff;
    border-bottom: 1px solid #e4e4e4;
    padding: 1px 4px;
}
QMenuBar::item {
    padding: 4px 10px;
    border-radius: 4px;
    color: #444;
}
QMenuBar::item:selected {
    background: #f0f7ff;
    color: #1a5a9e;
}
QMenuBar::item:pressed {
    background: #e3effa;
}

/* ── Context / Menu ────────────────────────────────────── */
QMenu {
    background: #ffffff;
    border: 1px solid #d8d8d8;
    border-radius: 6px;
    padding: 3px;
}
QMenu::item {
    padding: 5px 28px 5px 14px;
    border-radius: 3px;
    font-size: 12px;
}
QMenu::item:selected {
    background: #f0f7ff;
    color: #1a5a9e;
}
QMenu::separator {
    height: 1px;
    background: #e8e8e8;
    margin: 3px 6px;
}
QMenu::item:disabled {
    color: #ccc;
}

/* ── Toolbar ────────────────────────────────────────────── */
QToolBar {
    background: #ffffff;
    border-bottom: 1px solid #e4e4e4;
    padding: 1px 6px;
    spacing: 2px;
}
QToolBar QToolButton {
    background: transparent;
    border: 1px solid transparent;
    border-radius: 4px;
    padding: 4px 12px;
    color: #555;
}
QToolBar QToolButton:hover {
    background: #f0f7ff;
    border-color: #d8d8d8;
    color: #4a8fe0;
}
QToolBar QToolButton:pressed {
    background: #dce8f5;
}
QToolBar QToolButton:disabled {
    color: #ccc;
}

/* ── Task manager (floating panel) ──────────────────────── */
#task_manager {
    background: #ffffff;
    border: 1px solid #d8d8d8;
    border-radius: 8px;
}
#task_manager QLabel { color: #333; }
#task_manager QPushButton { background: transparent; color: #555; }
#task_header {
    background: #f8f9fa;
    border-bottom: 1px solid #e8e8e8;
    border-radius: 8px 8px 0 0;
}
#task_header_title { font-weight: 600; font-size: 11px; color: #555; }
#task_count { font-size: 10px; color: #888; }
#task_toggle {
    border: 1px solid #ccc; border-radius: 3px; font-size: 10px;
    min-width: 18px; min-height: 18px; max-width: 18px; max-height: 18px;
}
#task_scroll { border: none; background: transparent; }
#task_container { background: #ffffff; }
#task_none { color: #888; margin: 8px; }
#task_title { font-weight: 600; font-size: 11px; color: #333; }
#task_status { font-size: 10px; color: #888; }
#task_spinner { color: #4a8fe0; font-size: 14px; }

/* ── Status bar ─────────────────────────────────────────── */
QStatusBar {
    background: #fcfcfc;
    border-top: 1px solid #e4e4e4;
    color: #888;
    font-size: 11px;
    padding: 1px 6px;
}
QStatusBar QLabel {
    color: #888;
    font-size: 11px;
}
QStatusBar QCheckBox {
    font-size: 11px;
    color: #777;
    spacing: 3px;
}
QStatusBar QCheckBox::indicator {
    width: 12px;
    height: 12px;
    border: 1.5px solid #c8c8c8;
    border-radius: 2px;
    background: #fff;
}
QStatusBar QCheckBox::indicator:checked {
    background: #4a8fe0;
    border-color: #4a8fe0;
}
QStatusBar QCheckBox::indicator:hover {
    border-color: #4a8fe0;
}

/* ── Scrollbars ─────────────────────────────────────────── */
QScrollBar:vertical {
    background: transparent;
    width: 6px;
}
QScrollBar::handle:vertical {
    background: #d0d0d0;
    border-radius: 3px;
    min-height: 24px;
}
QScrollBar::handle:vertical:hover {
    background: #b0b0b0;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}
QScrollBar:horizontal {
    background: transparent;
    height: 6px;
}
QScrollBar::handle:horizontal {
    background: #d0d0d0;
    border-radius: 3px;
    min-width: 24px;
}
QScrollBar::handle:horizontal:hover {
    background: #b0b0b0;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0;
}

/* ── Progress / Buttons / Dialogs ──────────────────────── */
QProgressBar {
    border: none;
    border-radius: 4px;
    background: #eee;
    text-align: center;
    font-size: 11px;
    color: #666;
    height: 16px;
}
QProgressBar::chunk {
    background: #4a8fe0;
    border-radius: 4px;
}
QMessageBox {
    background: #ffffff;
}
QMessageBox QLabel {
    font-size: 12px;
    color: #444;
}
QPushButton {
    background: #fff;
    border: 1px solid #d8d8d8;
    border-radius: 4px;
    padding: 4px 16px;
    min-width: 60px;
    color: #444;
}
QPushButton:hover {
    background: #f0f7ff;
    border-color: #4a8fe0;
    color: #4a8fe0;
}
QPushButton:pressed {
    background: #dce8f5;
}
QInputDialog QLabel {
    font-size: 12px;
    color: #444;
}
"""

DARK = """
/* ── Root / Global ─────────────────────────────────────── */
QMainWindow, QDialog {
    background-color: #1e1e2e;
}
QWidget {
    font-family: "Segoe UI Variable", "Segoe UI", "Helvetica Neue", sans-serif;
    font-size: 12px;
    color: #cdd6f4;
}

/* ── Device header ─────────────────────────────────────── */
#device_header {
    font-weight: 700;
    font-size: 13px;
    padding: 4px 8px;
    background: #181825;
    border-bottom: 1px solid #313244;
    color: #cdd6f4;
}

/* ── Navigation bar ────────────────────────────────────── */
#nav_container {
    background: #181825;
    border-bottom: 1px solid #313244;
    padding: 2px;
}
QPushButton#back_btn {
    background: transparent;
    border: 1px solid #45475a;
    border-radius: 4px;
    font-size: 14px;
    padding: 2px 8px;
    color: #a6adc8;
}
QPushButton#back_btn:hover {
    background: #313244;
    border-color: #585b70;
}
QPushButton#back_btn:disabled {
    color: #585b70;
    border-color: #313244;
}
QPushButton#back_btn:pressed {
    background: #45475a;
}
#nav_container QPushButton {
    background: transparent;
    border: 1px solid #45475a;
    border-radius: 4px;
    padding: 4px 12px;
    color: #a6adc8;
}
#nav_container QPushButton:hover {
    background: #313244;
    border-color: #89b4fa;
    color: #89b4fa;
}
#nav_container QPushButton:pressed {
    background: #45475a;
}
#search_bar, QLineEdit {
    background: #181825;
    border: 1px solid #45475a;
    border-radius: 4px;
    padding: 3px 8px;
    font-size: 12px;
    color: #cdd6f4;
    selection-background-color: #89b4fa;
    selection-color: #1e1e2e;
}
#search_bar:focus, QLineEdit:focus {
    border-color: #89b4fa;
}
QLineEdit#path_display {
    background: #181825;
    border: 1px solid #313244;
    border-radius: 4px;
    padding: 3px 8px;
    color: #6c7086;
    font-size: 11px;
}

/* ── Tree view (file browser) ──────────────────────────── */
QTreeView {
    background-color: #1e1e2e;
    alternate-background-color: #181825;
    border: none;
    outline: none;
    font-size: 12px;
}
QTreeView::item {
    padding: 3px 2px;
    min-height: 26px;
}
QTreeView::item:selected:active {
    background-color: #313244;
    color: #89b4fa;
}
QTreeView::item:selected:!active {
    background-color: #313244;
    color: #a6adc8;
}
QTreeView::item:hover:!selected {
    background-color: #282840;
}
QTreeView QHeaderView {
    background: #181825;
}
QTreeView QHeaderView::section {
    background: #181825;
    color: #6c7086;
    font-weight: 600;
    font-size: 10px;
    letter-spacing: 0.5px;
    padding: 5px 4px;
    border: none;
    border-bottom: 1px solid #313244;
    border-right: 1px solid #282840;
}

/* ── Menu bar ──────────────────────────────────────────── */
QMenuBar {
    background: #181825;
    border-bottom: 1px solid #313244;
    padding: 1px 4px;
}
QMenuBar::item {
    padding: 4px 10px;
    border-radius: 4px;
    color: #a6adc8;
}
QMenuBar::item:selected {
    background: #313244;
    color: #89b4fa;
}
QMenuBar::item:pressed {
    background: #45475a;
}

/* ── Context / Menu ────────────────────────────────────── */
QMenu {
    background: #181825;
    border: 1px solid #45475a;
    border-radius: 6px;
    padding: 3px;
}
QMenu::item {
    padding: 5px 28px 5px 14px;
    border-radius: 3px;
    font-size: 12px;
    color: #cdd6f4;
}
QMenu::item:selected {
    background: #313244;
    color: #89b4fa;
}
QMenu::separator {
    height: 1px;
    background: #313244;
    margin: 3px 6px;
}
QMenu::item:disabled {
    color: #585b70;
}

/* ── Toolbar ────────────────────────────────────────────── */
QToolBar {
    background: #181825;
    border-bottom: 1px solid #313244;
    padding: 1px 6px;
    spacing: 2px;
}
QToolBar QToolButton {
    background: transparent;
    border: 1px solid transparent;
    border-radius: 4px;
    padding: 4px 12px;
    color: #a6adc8;
}
QToolBar QToolButton:hover {
    background: #313244;
    border-color: #45475a;
    color: #89b4fa;
}
QToolBar QToolButton:pressed {
    background: #45475a;
}
QToolBar QToolButton:disabled {
    color: #585b70;
}

/* ── Task manager (floating panel) ──────────────────────── */
#task_manager {
    background: #181825;
    border: 1px solid #45475a;
    border-radius: 8px;
}
#task_manager QLabel { color: #cdd6f4; }
#task_manager QPushButton { background: transparent; color: #a6adc8; }
#task_header {
    background: #1e1e2e;
    border-bottom: 1px solid #313244;
    border-radius: 8px 8px 0 0;
}
#task_header_title { font-weight: 600; font-size: 11px; color: #a6adc8; }
#task_count { font-size: 10px; color: #6c7086; }
#task_toggle {
    border: 1px solid #585b70; border-radius: 3px; font-size: 10px;
    color: #a6adc8;
    min-width: 18px; min-height: 18px; max-width: 18px; max-height: 18px;
}
#task_scroll { border: none; background: transparent; }
#task_container { background: #181825; }
#task_none { color: #6c7086; margin: 8px; }
#task_title { font-weight: 600; font-size: 11px; color: #cdd6f4; }
#task_status { font-size: 10px; color: #6c7086; }
#task_spinner { color: #89b4fa; font-size: 14px; }

/* ── Status bar ─────────────────────────────────────────── */
QStatusBar {
    background: #181825;
    border-top: 1px solid #313244;
    color: #6c7086;
    font-size: 11px;
    padding: 1px 6px;
}
QStatusBar QLabel {
    color: #6c7086;
    font-size: 11px;
}
QStatusBar QCheckBox {
    font-size: 11px;
    color: #6c7086;
    spacing: 3px;
}
QStatusBar QCheckBox::indicator {
    width: 12px;
    height: 12px;
    border: 1.5px solid #45475a;
    border-radius: 2px;
    background: #1e1e2e;
}
QStatusBar QCheckBox::indicator:checked {
    background: #89b4fa;
    border-color: #89b4fa;
}
QStatusBar QCheckBox::indicator:hover {
    border-color: #89b4fa;
}

/* ── Scrollbars ─────────────────────────────────────────── */
QScrollBar:vertical {
    background: transparent;
    width: 6px;
}
QScrollBar::handle:vertical {
    background: #45475a;
    border-radius: 3px;
    min-height: 24px;
}
QScrollBar::handle:vertical:hover {
    background: #585b70;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}
QScrollBar:horizontal {
    background: transparent;
    height: 6px;
}
QScrollBar::handle:horizontal {
    background: #45475a;
    border-radius: 3px;
    min-width: 24px;
}
QScrollBar::handle:horizontal:hover {
    background: #585b70;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0;
}

/* ── Progress / Buttons / Dialogs ──────────────────────── */
QProgressBar {
    border: none;
    border-radius: 4px;
    background: #313244;
    text-align: center;
    font-size: 11px;
    color: #a6adc8;
    height: 16px;
}
QProgressBar::chunk {
    background: #89b4fa;
    border-radius: 4px;
}
QMessageBox {
    background: #1e1e2e;
}
QMessageBox QLabel {
    font-size: 12px;
    color: #cdd6f4;
}
QPushButton {
    background: #313244;
    border: 1px solid #45475a;
    border-radius: 4px;
    padding: 4px 16px;
    min-width: 60px;
    color: #cdd6f4;
}
QPushButton:hover {
    background: #45475a;
    border-color: #89b4fa;
    color: #89b4fa;
}
QPushButton:pressed {
    background: #585b70;
}
QInputDialog QLabel {
    font-size: 12px;
    color: #cdd6f4;
}
"""
