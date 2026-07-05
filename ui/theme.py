STYLESHEET = """
/* ── Root / Global ─────────────────────────────────────── */
QMainWindow, QDialog {
    background-color: #f5f5f5;
}
QWidget {
    font-family: "Segoe UI Variable", "Segoe UI", "Helvetica Neue", sans-serif;
    font-size: 12px;
    color: #2c2c2c;
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
    background: #fafafa;
    border: 1px solid #e4e4e4;
    border-radius: 4px;
    padding: 3px 8px;
    color: #777;
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

/* ── Context menu ───────────────────────────────────────── */
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

/* ── Progress / Message dialogs ─────────────────────────── */
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

/* ── Input dialogs ──────────────────────────────────────── */
QInputDialog QLabel {
    font-size: 12px;
    color: #444;
}
"""
