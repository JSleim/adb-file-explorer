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

QPushButton#panel_close_btn {
    background: transparent;
    border: none;
    border-radius: 4px;
    color: #667085;
    font-size: 16px;
    font-weight: 600;
}
QPushButton#panel_close_btn:hover {
    background: #e6ebf2;
    color: #b42318;
}
/* ── Navigation bar ────────────────────────────────────── */
#nav_container {
    background: #ffffff;
    border-bottom: 1px solid #e4e4e4;
    padding: 2px;
}
QPushButton#back_btn {
    background: #ffffff;
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    font-size: 13px;
    font-weight: 600;
    padding: 2px 8px;
    color: #344054;
}
QPushButton#up_btn {
    background: #ffffff;
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    font-size: 13px;
    font-weight: 600;
    padding: 2px 8px;
    color: #344054;
}
QPushButton#up_btn:hover {
    background: #e3effa;
    border-color: #4a8fe0;
    color: #1a5a9e;
}
QPushButton#up_btn:pressed {
    background: #dce8f5;
}
QPushButton#back_btn:hover {
    background: #e3effa;
    border-color: #4a8fe0;
    color: #1a5a9e;
}
QPushButton#back_btn:disabled, QPushButton#up_btn:disabled {
    background: #f5f7fa;
    color: #ccc;
    border-color: #e4eaf1;
}
QPushButton#back_btn:pressed {
    background: #dce8f5;
}
QPushButton#back_btn:focus, QPushButton#up_btn:focus {
    border: 1px solid #4a8fe0;
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
QMessageBox QCheckBox#apply_to_all_conflicts {
    color: #444;
    font-size: 12px;
    spacing: 8px;
    padding: 8px 10px;
    border: 1px solid transparent;
    border-radius: 6px;
}
QMessageBox QCheckBox#apply_to_all_conflicts:hover {
    background: #f0f7ff;
}
QMessageBox QCheckBox#apply_to_all_conflicts:focus {
    border-color: #4a8fe0;
}
QMessageBox QCheckBox#apply_to_all_conflicts:disabled {
    color: #999;
}
QMessageBox QCheckBox#apply_to_all_conflicts::indicator {
    width: 16px;
    height: 16px;
    border: 1px solid #b8c0cc;
    border-radius: 4px;
    background: #fff;
}
QMessageBox QCheckBox#apply_to_all_conflicts::indicator:hover {
    border-color: #4a8fe0;
}
QMessageBox QCheckBox#apply_to_all_conflicts::indicator:checked {
    background: #4a8fe0;
    border-color: #4a8fe0;
}
QMessageBox QCheckBox#apply_to_all_conflicts::indicator:disabled {
    background: #f0f0f0;
    border-color: #d8d8d8;
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

#panel_header {
    background: #f0f4fa;
    border-bottom: 1px solid #d0d8e4;
}
#panel_header #device_header {
    padding: 0 2px;
    background: transparent;
    border: none;
    color: #243447;
}
QDialog#device_chooser { background: #f8fafc; }
QLabel#chooser_prompt { color: #344054; font-weight: 600; }
QListWidget#device_picker {
    background: #ffffff; border: 1px solid #cbd5e1; border-radius: 6px;
    color: #1f2937; outline: 0;
}
QListWidget#device_picker::item { padding: 8px 10px; margin: 2px 4px; border-radius: 4px; }
QListWidget#device_picker::item:hover { background: #eef4fb; }
QListWidget#device_picker::item:selected { background: #dbeafe; color: #1d4ed8; }

QTabWidget#path_tabs {
    background: #ffffff;
}
QTabWidget#path_tabs::pane {
    background: #ffffff;
    border: 1px solid #d0d8e4;
    border-top: none;
}
QTabWidget#path_tabs QTabBar::tab {
    background: #e8edf4;
    color: #526174;
    border: 1px solid #d0d8e4;
    border-bottom: 2px solid transparent;
    padding: 6px 12px;
    min-width: 72px;
    max-width: 180px;
    margin-right: 2px;
}
QTabWidget#path_tabs QTabBar::tab:hover {
    background: #f0f7ff;
    color: #1a5a9e;
}
QTabWidget#path_tabs QTabBar::tab:selected {
    background: #ffffff;
    color: #1a5a9e;
    border-bottom-color: #4a8fe0;
}
QTabWidget#path_tabs QTabBar QToolButton#close_path_tab_btn {
    color: #475467;
    background: transparent;
    border: none;
    border-radius: 3px;
    font-size: 12px;
    font-weight: 700;
    min-width: 20px;
    max-width: 20px;
    min-height: 20px;
    max-height: 20px;
    padding: 0;
}
QTabWidget#path_tabs QTabBar QToolButton#close_path_tab_btn:hover {
    color: #ffffff;
    background: #b42318;
}
QTabWidget#path_tabs QTabBar QToolButton#close_path_tab_btn:pressed {
    background: #912018;
}
QTabWidget#path_tabs QTabBar QToolButton#close_path_tab_btn:focus {
    border: 1px solid #4a8fe0;
}
QTabWidget#path_tabs QTabBar QToolButton#ScrollLeftButton,
QTabWidget#path_tabs QTabBar QToolButton#ScrollRightButton {
    color: #344054;
    background: #ffffff;
    border: 1px solid #d0d8e4;
    border-radius: 6px;
    font-size: 11px;
    font-weight: 700;
    min-width: 14px;
    max-width: 14px;
    min-height: 24px;
    max-height: 24px;
    padding: 0;
}
QTabWidget#path_tabs QTabBar QToolButton#ScrollLeftButton:hover,
QTabWidget#path_tabs QTabBar QToolButton#ScrollRightButton:hover {
    color: #ffffff;
    background: #e3effa;
    border-color: #4a8fe0;
}
QTabWidget#path_tabs QTabBar QToolButton#ScrollLeftButton:disabled,
QTabWidget#path_tabs QTabBar QToolButton#ScrollRightButton:disabled {
    color: #98a2b3;
    background: #f7f9fc;
    border-color: #e4eaf1;
}
QPushButton#panel_close_btn {
    background: #fef3f2;
    border: 1px solid #fda29b;
    border-radius: 6px;
    color: #b42318;
    font-size: 13px;
    font-weight: 700;
    padding: 0;
}
QPushButton#panel_close_btn:hover {
    background: #b42318;
    border-color: #b42318;
    color: #ffffff;
}
QPushButton#panel_close_btn:pressed {
    background: #912018;
    border-color: #912018;
}
QPushButton#panel_close_btn:focus {
    border: 2px solid #4a8fe0;
}
QPushButton#add_path_tab_btn {
    background: #e3effa;
    border: 1px solid #c5d9ef;
    border-radius: 6px;
    color: #1a5a9e;
    font-size: 17px;
    font-weight: 600;
    padding: 0;
    min-width: 30px;
    max-width: 30px;
    min-height: 30px;
    max-height: 30px;
}
QPushButton#add_path_tab_btn:hover {
    background: #d4e7f8;
    border-color: #4a8fe0;
}
QPushButton#add_path_tab_btn:pressed {
    background: #c5d9ef;
}
QToolBar QPushButton#add_panel_btn,
QToolBar QPushButton#add_tab_btn {
    min-width: 0;
    padding: 4px 10px;
    border-radius: 4px;
}
QToolBar QPushButton#add_panel_btn {
    background: transparent;
    border-color: transparent;
    color: #526174;
}
QToolBar QPushButton#add_panel_btn:hover {
    background: #f0f7ff;
    border-color: #d0d8e4;
    color: #1a5a9e;
}
QToolBar QPushButton#add_tab_btn {
    background: #e3effa;
    border-color: #c5d9ef;
    color: #1a5a9e;
}
QToolBar QPushButton#add_tab_btn:hover {
    background: #d4e7f8;
    border-color: #4a8fe0;
}
QToolBar QPushButton#add_panel_btn:focus,
QToolBar QPushButton#add_tab_btn:focus {
    border-color: #4a8fe0;
}
QWidget#path_tab_bar {
    qproperty-drawBase: 0;
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

QPushButton#panel_close_btn {
    background: transparent;
    border: none;
    border-radius: 4px;
    color: #a6adc8;
    font-size: 16px;
    font-weight: 600;
}
QPushButton#panel_close_btn:hover {
    background: #45475a;
    color: #f38ba8;
}
/* ── Navigation bar ────────────────────────────────────── */
#nav_container {
    background: #181825;
    border-bottom: 1px solid #313244;
    padding: 2px;
}
QPushButton#back_btn {
    background: #1e1e2e;
    border: 1px solid #45475a;
    border-radius: 6px;
    font-size: 13px;
    font-weight: 600;
    padding: 2px 8px;
    color: #cdd6f4;
}
QPushButton#up_btn {
    background: #1e1e2e;
    border: 1px solid #45475a;
    border-radius: 6px;
    font-size: 13px;
    font-weight: 600;
    padding: 2px 8px;
    color: #cdd6f4;
}
QPushButton#up_btn:hover {
    background: #313244;
    border-color: #89b4fa;
    color: #89b4fa;
}
QPushButton#up_btn:pressed {
    background: #45475a;
}
QPushButton#back_btn:hover {
    background: #313244;
    border-color: #89b4fa;
    color: #89b4fa;
}
QPushButton#back_btn:disabled, QPushButton#up_btn:disabled {
    background: #181825;
    color: #585b70;
    border-color: #313244;
}
QPushButton#back_btn:pressed {
    background: #45475a;
}
QPushButton#back_btn:focus, QPushButton#up_btn:focus {
    border: 1px solid #89b4fa;
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
QMessageBox QCheckBox#apply_to_all_conflicts {
    color: #cdd6f4;
    font-size: 12px;
    spacing: 8px;
    padding: 8px 10px;
    border: 1px solid transparent;
    border-radius: 6px;
}
QMessageBox QCheckBox#apply_to_all_conflicts:hover {
    background: #313244;
}
QMessageBox QCheckBox#apply_to_all_conflicts:focus {
    border-color: #89b4fa;
}
QMessageBox QCheckBox#apply_to_all_conflicts:disabled {
    color: #6c7086;
}
QMessageBox QCheckBox#apply_to_all_conflicts::indicator {
    width: 16px;
    height: 16px;
    border: 1px solid #585b70;
    border-radius: 4px;
    background: #181825;
}
QMessageBox QCheckBox#apply_to_all_conflicts::indicator:hover {
    border-color: #89b4fa;
}
QMessageBox QCheckBox#apply_to_all_conflicts::indicator:checked {
    background: #89b4fa;
    border-color: #89b4fa;
}
QMessageBox QCheckBox#apply_to_all_conflicts::indicator:disabled {
    background: #313244;
    border-color: #45475a;
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

#panel_header {
    background: #181825;
    border-bottom: 1px solid #313244;
}
#panel_header #device_header {
    padding: 0 2px;
    background: transparent;
    border: none;
    color: #cdd6f4;
}
QDialog#device_chooser { background: #11111b; }
QLabel#chooser_prompt { color: #cdd6f4; font-weight: 600; }
QListWidget#device_picker {
    background: #1e1e2e; border: 1px solid #45475a; border-radius: 6px;
    color: #cdd6f4; outline: 0;
}
QListWidget#device_picker::item { padding: 8px 10px; margin: 2px 4px; border-radius: 4px; }
QListWidget#device_picker::item:hover { background: #313244; }
QListWidget#device_picker::item:selected { background: #45475a; color: #89b4fa; }

QTabWidget#path_tabs {
    background: #1e1e2e;
}
QTabWidget#path_tabs::pane {
    background: #1e1e2e;
    border: 1px solid #313244;
    border-top: none;
}
QTabWidget#path_tabs QTabBar::tab {
    background: #181825;
    color: #a6adc8;
    border: 1px solid #313244;
    border-bottom: 2px solid transparent;
    padding: 6px 12px;
    min-width: 72px;
    max-width: 180px;
    margin-right: 2px;
}
QTabWidget#path_tabs QTabBar::tab:hover {
    background: #313244;
    color: #cdd6f4;
}
QTabWidget#path_tabs QTabBar::tab:selected {
    background: #1e1e2e;
    color: #89b4fa;
    border-bottom-color: #89b4fa;
}
QTabWidget#path_tabs QTabBar QToolButton#close_path_tab_btn {
    color: #a6adc8;
    background: transparent;
    border: none;
    border-radius: 3px;
    font-size: 12px;
    font-weight: 700;
    min-width: 20px;
    max-width: 20px;
    min-height: 20px;
    max-height: 20px;
    padding: 0;
}
QTabWidget#path_tabs QTabBar QToolButton#close_path_tab_btn:hover {
    color: #1e1e2e;
    background: #f38ba8;
}
QTabWidget#path_tabs QTabBar QToolButton#close_path_tab_btn:pressed {
    background: #d76b87;
}
QTabWidget#path_tabs QTabBar QToolButton#close_path_tab_btn:focus {
    border: 1px solid #89b4fa;
}
QTabWidget#path_tabs QTabBar QToolButton#ScrollLeftButton,
QTabWidget#path_tabs QTabBar QToolButton#ScrollRightButton {
    color: #cdd6f4;
    background: #1e1e2e;
    border: 1px solid #45475a;
    border-radius: 6px;
    font-size: 11px;
    font-weight: 700;
    min-width: 14px;
    max-width: 14px;
    min-height: 24px;
    max-height: 24px;
    padding: 0;
}
QTabWidget#path_tabs QTabBar QToolButton#ScrollLeftButton:hover,
QTabWidget#path_tabs QTabBar QToolButton#ScrollRightButton:hover {
    color: #cdd6f4;
    background: #313244;
    border-color: #89b4fa;
}
QTabWidget#path_tabs QTabBar QToolButton#ScrollLeftButton:disabled,
QTabWidget#path_tabs QTabBar QToolButton#ScrollRightButton:disabled {
    color: #585b70;
    background: #1e1e2e;
    border-color: #313244;
}
QPushButton#panel_close_btn {
    background: #512b38;
    border: 1px solid #f38ba8;
    border-radius: 6px;
    color: #f38ba8;
    font-size: 13px;
    font-weight: 700;
    padding: 0;
}
QPushButton#panel_close_btn:hover {
    background: #f38ba8;
    border-color: #f38ba8;
    color: #1e1e2e;
}
QPushButton#panel_close_btn:pressed {
    background: #d76b87;
    border-color: #d76b87;
}
QPushButton#panel_close_btn:focus {
    border: 2px solid #89b4fa;
}
QPushButton#add_path_tab_btn {
    background: #313244;
    border: 1px solid #45475a;
    border-radius: 6px;
    color: #89b4fa;
    font-size: 17px;
    font-weight: 600;
    padding: 0;
    min-width: 30px;
    max-width: 30px;
    min-height: 30px;
    max-height: 30px;
}
QPushButton#add_path_tab_btn:hover {
    background: #45475a;
    border-color: #89b4fa;
}
QPushButton#add_path_tab_btn:pressed {
    background: #585b70;
}
QToolBar QPushButton#add_panel_btn,
QToolBar QPushButton#add_tab_btn {
    min-width: 0;
    padding: 4px 10px;
    border-radius: 4px;
}
QToolBar QPushButton#add_panel_btn {
    background: transparent;
    border-color: transparent;
    color: #a6adc8;
}
QToolBar QPushButton#add_panel_btn:hover {
    background: #313244;
    border-color: #45475a;
    color: #89b4fa;
}
QToolBar QPushButton#add_tab_btn {
    background: #313244;
    border-color: #45475a;
    color: #89b4fa;
}
QToolBar QPushButton#add_tab_btn:hover {
    background: #45475a;
    border-color: #89b4fa;
}
QToolBar QPushButton#add_panel_btn:focus,
QToolBar QPushButton#add_tab_btn:focus {
    border-color: #89b4fa;
}
QWidget#path_tab_bar {
    qproperty-drawBase: 0;
}"""
