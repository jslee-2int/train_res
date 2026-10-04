"""데모 결과가 있는 UI를 logs/ui_preview.png로 저장."""
import os
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from pathlib import Path
from PyQt6.QtGui import QFont, QFontDatabase
from PyQt6.QtWidgets import QApplication
from gui_theme import STYLE
from ktx_app import MainWindow
from ktx_watch import DemoSource, now_kst


def main():
    app = QApplication([])
    # offscreen 플랫폼은 Windows 시스템 폰트를 자동 탐색하지 않을 수 있다.
    font_path = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / "malgun.ttf"
    if font_path.exists():
        QFontDatabase.addApplicationFont(str(font_path))
    app.setStyle("Fusion")
    app.setFont(QFont("Malgun Gothic", 10))
    app.setStyleSheet(STYLE)
    window = MainWindow(demo=True)
    config = window.read_config(False)
    window.config = config
    trip = config.trips[0]
    source = DemoSource()
    source.search(trip, now_kst())
    window.on_cycle({trip: source.search(trip, now_kst())}, {})
    window.tabs.setTabVisible(1, False)
    window.pages[0].table.selectRow(1)
    window.on_train_clicked(1, 4)
    window.show()
    app.processEvents()
    output = Path(__file__).parent / "logs" / "ui_preview.png"
    output.parent.mkdir(exist_ok=True)
    if not window.grab().save(str(output)):
        raise RuntimeError("미리보기 저장 실패")
    window.close()
    print(output)


if __name__ == "__main__":
    main()
