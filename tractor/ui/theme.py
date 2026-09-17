from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel

STYLE = """
QWidget { background: #f7f8fa; color: #202a38; font-family: 'Inter', 'Noto Sans', sans-serif;
          font-size: 14px; }
QMainWindow { background: #f7f8fa; }
QLabel { background: transparent; }
QLabel#muted { color: #6b7685; font-size: 12px; }
QLabel#eyebrow { color: #737e8a; font-size: 11px; font-weight: 600; letter-spacing: 2px; }
QLabel#hero { color: #172333; font-size: 60px; font-weight: 700; letter-spacing: 8px; }
QLabel#brand { color: #172333; font-size: 20px; font-weight: 700; letter-spacing: 3px; }
QLabel#heading { font-size: 23px; font-weight: 600; }
QLabel#resultTitle { font-size: 18px; font-weight: 600; color: #23364e; }
QLabel#badge { color: #806126; font-size: 10px; font-weight: 700; letter-spacing: 1px; }
QLineEdit, QComboBox, QSpinBox, QTextEdit, QListWidget, QTreeWidget {
    background: #ffffff; border: 1px solid #dce1e7; border-radius: 7px;
    padding: 9px; selection-background-color: #dce8f6; selection-color: #172333;
}
QLineEdit:focus, QComboBox:focus { border: 1px solid #8096af; }
QLineEdit#searchInput { font-size: 19px; padding: 18px; border-radius: 10px; }
QPushButton { background: #ffffff; border: 1px solid #dce1e7; border-radius: 7px;
              padding: 9px 15px; color: #344358; }
QPushButton:hover { background: #edf1f6; border-color: #b7c3d0; }
QPushButton:pressed { background: #e1e7ee; }
QPushButton:disabled { color: #9aa3af; background: #f0f2f5; }
QPushButton#primary { background: #243a53; color: #ffffff; border: 1px solid #243a53;
                      font-weight: 600; padding: 15px 23px; }
QPushButton#primary:hover { background: #314d6c; }
QPushButton#primary:disabled { background: #8190a1; border-color: #8190a1; }
QPushButton#quiet { background: transparent; border: 0; color: #65758a; }
QPushButton#quiet:hover { color: #243a53; background: #e9edf3; }
QFrame#resultCard { background: #ffffff; border: 1px solid #e1e5eb; border-radius: 10px; }
QFrame#rule { background: #e0e5eb; max-height: 1px; border: 0; }
QScrollArea { border: 0; background: transparent; }
QScrollBar:vertical { background: transparent; width: 8px; margin: 0; }
QScrollBar::handle:vertical { background: #ccd4df; border-radius: 4px; min-height: 30px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QProgressBar { border: 0; background: #e7ebf1; height: 3px; max-height: 3px; }
QProgressBar::chunk { background: #a78345; }
QTabWidget::pane { border: 1px solid #dce1e7; background: #fff; }
QTabBar::tab { padding: 10px 18px; background: #edf0f4; }
QTabBar::tab:selected { background: #fff; color: #243a53; }
QHeaderView::section { background: #edf1f6; border: 0; padding: 8px; color: #5d6b7b; }
QCheckBox { spacing: 10px; padding: 7px; }
QToolTip { background: #243a53; color: #ffffff; border: 0; padding: 5px; }
"""


def label(text: str, role: str = "", wrap: bool = False) -> QLabel:
    widget = QLabel(text)
    widget.setTextFormat(Qt.TextFormat.PlainText)
    widget.setObjectName(role)
    widget.setWordWrap(wrap)
    return widget
