"""목록 중심의 중성 회색/블루 데스크톱 테마."""

STYLE = """
QWidget { font-family: 'Malgun Gothic', 'Segoe UI', sans-serif; font-size: 13px; color: #253447; }
QMainWindow, QWidget#Root { background: #F4F6FA; }
QFrame#Sidebar { background: #FFFFFF; border-right: 1px solid #E3E8EF; }
QFrame#Card { background: white; border: 1px solid #E3E8EF; border-radius: 14px; }
QFrame#Hero { background: #103D43; border: none; border-radius: 16px; }
QLabel { background: transparent; border: none; }
QLabel#Brand { font-size: 19px; font-weight: 800; color: #087F8C; }
QLabel#Title { font-size: 25px; font-weight: 700; color: #172B42; }
QLabel#Section { font-size: 14px; font-weight: 700; color: #172B42; }
QLabel#Muted { color: #748297; font-size: 12px; }
QLabel#HeroTitle { color: #FFFFFF; font-size: 28px; font-weight: 700; }
QLabel#HeroSub { color: #BBD4D6; font-size: 13px; }
QLabel#Metric { font-size: 25px; font-weight: 700; color: #087F8C; }
QLabel#Mode { background: #E5F5F1; color: #087F68; padding: 6px 12px; border-radius: 12px; font-size: 12px; }
QLabel#Banner { background: #E6F5F0; color: #146B51; border: 1px solid #B6DFCE; border-radius: 10px; padding: 12px; }
QLineEdit, QDateEdit, QTimeEdit, QSpinBox, QComboBox {
    background: #F8FAFC; border: 1px solid #DCE3EC; border-radius: 7px;
    padding: 7px 9px; min-height: 22px; selection-background-color: #087F8C;
}
QLineEdit:focus, QDateEdit:focus, QTimeEdit:focus, QSpinBox:focus, QComboBox:focus { border: 1px solid #087F8C; background: white; }
QWidget:disabled { color: #98A3B3; }
QPushButton { background: #FFFFFF; border: 1px solid #DCE3EC; border-radius: 8px; padding: 9px 16px; font-weight: 600; min-height: 23px; }
QPushButton:hover { background: #EDF5F6; border-color: #78B6BD; }
QPushButton:pressed { background: #DDECEF; }
QPushButton#Primary { background: #087F8C; color: white; border-color: #087F8C; }
QPushButton#Primary:hover { background: #066A76; }
QPushButton#Stop { background: #FFF1F0; color: #B54545; border-color: #F2D0CD; }
QPushButton:disabled { background: #EDF0F4; color: #A5AFBC; border-color: #E4E8EE; }
QCheckBox { spacing: 7px; }
QCheckBox::indicator { width: 16px; height: 16px; }
QTabWidget::pane { background: white; border: 1px solid #E3E8EF; border-radius: 10px; }
QTabBar::tab { background: transparent; color: #758297; padding: 12px 20px; border-bottom: 3px solid transparent; }
QTabBar::tab:selected { color: #087F8C; border-bottom: 3px solid #087F8C; font-weight: 700; }
QTableWidget { background: white; alternate-background-color: #FAFBFD; border: none; gridline-color: #EFF2F6; selection-background-color: #E5F3F5; selection-color: #253447; }
QTableWidget::item { padding: 10px 7px; border-bottom: 1px solid #EFF2F6; }
QHeaderView::section { background: #F7F9FC; color: #78859A; border: none; border-bottom: 1px solid #E3E8EF; padding: 12px 7px; font-size: 12px; font-weight: 600; }
QPlainTextEdit { background: #F8FAFC; color: #526176; border: 1px solid #E3E8EF; border-radius: 8px; padding: 9px; font-size: 12px; }
QScrollArea { background: transparent; border: none; }
QScrollBar:vertical { background: transparent; width: 8px; margin: 2px; }
QScrollBar::handle:vertical { background: #CCD6E0; min-height: 24px; border-radius: 3px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QProgressBar { background: #E5EDF0; border: none; border-radius: 2px; max-height: 4px; }
QProgressBar::chunk { background: #20A699; border-radius: 2px; }
QToolTip { background: #172B42; color: white; border: none; padding: 7px; }
"""

# 기존 위젯 구성을 유지하면서 모든 색상 역할을 한 팔레트로 통일한다.
for old, new in {
    "#253447": "#303744", "#F4F6FA": "#F6F7F9", "#E3E8EF": "#E3E6EC",
    "#103D43": "#F6F7F9", "#087F8C": "#326BDB", "#172B42": "#252C38",
    "#748297": "#737D8C", "#BBD4D6": "#737D8C", "#E5F5F1": "#ECF1FC",
    "#087F68": "#365BA0", "#E6F5F0": "#EEF6F1", "#146B51": "#356549",
    "#B6DFCE": "#D6E7DB", "#DCE3EC": "#DCE0E7", "#EDF5F6": "#F2F5FA",
    "#78B6BD": "#A6B9D9", "#DDECEF": "#E6EDFA", "#066A76": "#275CC5",
    "#758297": "#737D8C", "#E5F3F5": "#E9F0FF", "#E5EDF0": "#E4E9F1",
    "#20A699": "#7297E1",
}.items():
    STYLE = STYLE.replace(old, new)

STYLE += """
QWidget#Content { background: #F6F7F9; }
QWidget#SideContent { background: #FFFFFF; }
QLabel#Brand { color: #252C38; font-size: 19px; }
QFrame#Card { border-radius: 9px; }
QFrame#Route { background: #FAFBFC; border: 1px solid #E3E6EC; border-radius: 9px; }
QFrame#Route[selected="true"] { background: #F4F7FF; border-color: #7FA5F5; }
QFrame#Hero { background: transparent; border: none; border-bottom: 1px solid #E2E5EB; border-radius: 0; }
QLabel#HeroTitle { color: #343E50; font-size: 18px; }
QLabel#HeroSub { color: #737D8C; font-size: 12px; }
QLabel#Metric { color: #252C38; font-size: 23px; }
QLabel#Mode { border-radius: 6px; font-size: 11px; }
QLabel#Target { background: #EDF3FF; color: #31599B; border: 1px solid #D8E4FA; border-radius: 7px; padding: 10px 12px; }
QLineEdit, QDateEdit, QTimeEdit, QSpinBox, QComboBox { background: #FFFFFF; color: #303848; selection-color: white; }
QLineEdit:disabled, QDateEdit:disabled, QTimeEdit:disabled, QSpinBox:disabled, QComboBox:disabled { background: #F3F4F6; color: #9AA2B0; border-color: #E5E7EB; }
QComboBox QAbstractItemView { background: white; color: #303848; selection-background-color: #EDF3FF; selection-color: #245BBB; }
QPushButton#Primary:disabled, QPushButton#Stop:disabled { background: #ECEFF3; color: #9AA2B0; border-color: #E0E4EA; }
QCheckBox, QRadioButton { background: transparent; spacing: 7px; }
QRadioButton::indicator { width: 14px; height: 14px; border: 1px solid #B5BECC; border-radius: 8px; background: white; }
QRadioButton::indicator:checked { border: 4px solid #326BDB; width: 8px; height: 8px; border-radius: 8px; background: white; }
QTableWidget::item:selected { background: #E9F0FF; color: #234B8F; }
QTableWidget::item:focus { border: 1px solid #86A8EB; }
QPlainTextEdit { background: #FFFFFF; }
QMenu { background: white; color: #303848; border: 1px solid #DCE0E7; padding: 5px; }
QMenu::item { padding: 8px 22px; }
QMenu::item:selected { background: #EDF3FF; }
"""
