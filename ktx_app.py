"""KTX Seat Watch — PyQt6 Windows 데스크톱 앱."""
from __future__ import annotations

import argparse
import math
import sys
import time
from dataclasses import replace

from PyQt6.QtCore import QDate, QTime, QTimer, Qt
from PyQt6.QtGui import QColor, QFont, QIcon, QPainter, QPen, QPixmap
from PyQt6.QtWidgets import (
    QApplication, QButtonGroup, QRadioButton, QCheckBox, QComboBox, QDateEdit, QFrame, QHBoxLayout,
    QHeaderView, QLabel, QLineEdit, QMainWindow, QMenu, QPlainTextEdit,
    QProgressBar, QPushButton, QScrollArea, QSpinBox, QSystemTrayIcon,
    QTableWidget, QTableWidgetItem, QTabWidget, QTimeEdit, QVBoxLayout, QWidget,
)

from desktop_worker import WatchConfig, WatchWorker
from gui_theme import STYLE
from ktx_watch import Trip, now_kst, seat_text, sort_trains


def label(text, name=None):
    widget = QLabel(text)
    widget.setTextFormat(Qt.TextFormat.PlainText)
    if name:
        widget.setObjectName(name)
    return widget


def app_icon(size=256):
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.scale(size / 64, size / 64)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor("#326BDB"))
    painter.drawRoundedRect(0, 0, 64, 64, 16, 16)
    painter.setBrush(QColor("#FFFFFF"))
    painter.drawRoundedRect(17, 10, 30, 39, 8, 8)
    painter.setBrush(QColor("#326BDB"))
    painter.drawRoundedRect(21, 16, 22, 15, 3, 3)
    painter.drawEllipse(22, 38, 5, 5)
    painter.drawEllipse(37, 38, 5, 5)
    painter.setPen(QPen(QColor("#FFFFFF"), 3))
    painter.drawLine(23, 49, 18, 55)
    painter.drawLine(41, 49, 46, 55)
    painter.end()
    return QIcon(pix)


class RouteInput(QFrame):
    def __init__(self, title, start, end):
        super().__init__()
        self.setObjectName("Route")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 14, 15, 14)
        layout.setSpacing(9)
        self.enabled = QRadioButton(title)
        self.enabled.setStyleSheet("font-weight: 700;")
        layout.addWidget(self.enabled)
        self.fields = QWidget()
        fields = QVBoxLayout(self.fields)
        fields.setContentsMargins(0, 0, 0, 0)
        fields.setSpacing(8)
        today = now_kst()
        tomorrow = QDate(today.year, today.month, today.day).addDays(1)
        self.date = QDateEdit(tomorrow)
        self.date.setCalendarPopup(True)
        self.date.setDisplayFormat("yyyy.MM.dd")
        self.date.setMinimumDate(tomorrow.addDays(-1))
        fields.addWidget(self.date)
        row = QHBoxLayout()
        self.start = QTimeEdit(QTime(start, 0))
        self.end = QTimeEdit(QTime(end, 0))
        for widget in (self.start, self.end):
            widget.setDisplayFormat("HH:mm")
        row.addWidget(self.start)
        row.addWidget(label("—", "Muted"))
        row.addWidget(self.end)
        fields.addLayout(row)
        layout.addWidget(self.fields)
        self.enabled.toggled.connect(self.fields.setEnabled)
        self.enabled.toggled.connect(self.update_selected_style)
        self.fields.setEnabled(False)

    def update_selected_style(self, selected):
        self.setProperty("selected", selected)
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()

    def trip(self, dep, arr):
        return Trip(dep, arr, self.date.date().toString("yyyyMMdd"),
                    self.start.time().toString("HHmmss"), self.end.time().toString("HHmmss"))


class ResultPage(QWidget):
    def __init__(self):
        super().__init__()
        box = QVBoxLayout(self)
        box.setContentsMargins(14, 12, 14, 12)
        self.note = label("검색 조건을 설정하고 열차를 조회하세요.", "Muted")
        self.note.setWordWrap(True)
        box.addWidget(self.note)
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["열차", "출발", "도착", "소요", "일반실", "특실"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().hide()
        self.table.verticalHeader().setDefaultSectionSize(58)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.setMinimumHeight(140)
        box.addWidget(self.table)

    def display(self, trains, stale=False):
        selected = self.selected_train()
        self.table.blockSignals(True)
        self.table.clearSelection()
        self.table.setRowCount(len(trains))
        for row, train in enumerate(trains):
            values = [f"KTX {train.number}", train.departure.strftime("%H:%M"),
                      train.arrival.strftime("%H:%M"), f"{train.minutes}분",
                      seat_text(train.general), seat_text(train.special)]
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setData(Qt.ItemDataRole.UserRole, train)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                item.setToolTip(f"{train.name} · {train.departure:%Y-%m-%d %H:%M} → {train.arrival:%Y-%m-%d %H:%M}"
                                + ("\n이전 조회 결과입니다. 현재 좌석 상태를 확인할 수 없습니다." if stale else ""))
                if col in (1, 2):
                    font = item.font()
                    font.setPointSize(12)
                    font.setBold(True)
                    item.setFont(font)
                if col >= 4:
                    good = value == "가능" and not stale
                    item.setForeground(QColor("#326BDB" if good else "#929BAB"))
                    if good:
                        font = item.font()
                        font.setBold(True)
                        item.setFont(font)
                if stale:
                    item.setForeground(QColor("#98A3B3"))
                self.table.setItem(row, col, item)
            if selected is not None and selected.key == train.key:
                self.table.selectRow(row)
        self.table.blockSignals(False)

    def selected_train(self):
        selected = self.table.selectionModel().selectedRows()
        if not selected:
            return None
        return self.table.item(selected[0].row(), 0).data(Qt.ItemDataRole.UserRole)


class MainWindow(QMainWindow):
    def __init__(self, demo=False):
        super().__init__()
        self.worker = None
        self.config = None
        self.results = {}
        self.errors = {}
        self.stamps = {}
        self.next_poll = None
        self.closing = False
        self.stopping = False
        self.alert_count = 0
        self.setWindowTitle("KTX Seat Watch · 대전 ↔ 서울")
        self.setWindowIcon(app_icon())
        self.resize(1280, 900)
        self.setMinimumSize(1080, 720)
        root = QWidget()
        root.setObjectName("Root")
        self.setCentralWidget(root)
        layout = QHBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.build_sidebar(demo))
        main_scroll = QScrollArea()
        main_scroll.setWidgetResizable(True)
        main_scroll.setWidget(self.build_content())
        layout.addWidget(main_scroll, 1)
        self.make_tray()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(500)
        self.demo.toggled.connect(self.update_mode)
        self.update_mode()

    def build_sidebar(self, demo):
        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(308)
        outer = QVBoxLayout(sidebar)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        content.setObjectName("SideContent")
        box = QVBoxLayout(content)
        box.setContentsMargins(22, 26, 22, 22)
        box.setSpacing(15)
        box.addWidget(label("KTX Seat Watch", "Brand"))
        box.addWidget(label("나의 열차 · 좌석 알림", "Muted"))
        self.inputs = QWidget()
        inputs = QVBoxLayout(self.inputs)
        inputs.setContentsMargins(0, 6, 0, 0)
        inputs.setSpacing(14)
        inputs.addWidget(label("여정 설정", "Section"))
        self.up = RouteInput("01   대전 → 서울", 7, 12)
        self.down = RouteInput("02   서울 → 대전", 17, 23)
        self.direction_group = QButtonGroup(self)
        self.direction_group.setExclusive(True)
        self.direction_group.addButton(self.up.enabled)
        self.direction_group.addButton(self.down.enabled)
        self.up.enabled.setChecked(True)
        inputs.addWidget(self.up)
        inputs.addWidget(self.down)
        inputs.addWidget(label("알림 조건", "Section"))
        self.seat = QComboBox()
        for text, value in [("일반실", "general"), ("특실", "special"), ("일반실 + 특실", "any")]:
            self.seat.addItem(text, value)
        inputs.addWidget(self.seat)
        row = QHBoxLayout()
        row.addWidget(label("조회 간격", "Muted"))
        self.interval = QSpinBox()
        self.interval.setRange(5, 900)
        self.interval.setValue(60)
        self.interval.setSuffix(" 초")
        row.addWidget(self.interval, 1)
        inputs.addLayout(row)
        self.numbers = QLineEdit()
        self.numbers.setPlaceholderText("열차 번호 · 목록 선택 시 자동 입력")
        self.numbers.setToolTip("열차를 클릭하면 번호가 입력됩니다. 비우면 전체 열차를 조회하며, 감시는 선택한 열차에만 적용됩니다.")
        inputs.addWidget(self.numbers)
        self.demo = QCheckBox("데모 모드 · 실제 열차가 아닙니다")
        self.demo.setChecked(demo)
        inputs.addWidget(self.demo)
        box.addWidget(self.inputs)
        self.sound = QCheckBox("좌석 발견 시 알림음")
        self.sound.setChecked(True)
        box.addWidget(self.sound)
        box.addStretch()
        hint = label("감시 중에는 앱을 실행해 두세요.\n예매는 코레일톡에서 진행할 수 있습니다.", "Muted")
        hint.setWordWrap(True)
        box.addWidget(hint)
        scroll.setWidget(content)
        outer.addWidget(scroll)
        return sidebar

    def build_content(self):
        content = QWidget()
        content.setObjectName("Content")
        box = QVBoxLayout(content)
        box.setContentsMargins(28, 20, 28, 18)
        box.setSpacing(12)
        header = QHBoxLayout()
        header.addWidget(label("열차 조회", "Title"))
        header.addStretch()
        self.mode = label("", "Mode")
        header.addWidget(self.mode)
        box.addLayout(header)
        hero = QFrame()
        hero.setObjectName("Hero")
        hero_box = QVBoxLayout(hero)
        hero_box.setContentsMargins(0, 0, 0, 14)
        hero_box.addWidget(label("대전  ↔  서울", "HeroTitle"))
        hero_box.addWidget(label("시간표에서 원하는 열차와 좌석 등급을 선택하세요.", "HeroSub"))
        box.addWidget(hero)
        metrics = QHBoxLayout()
        self.total = self.add_metric_card(metrics, "조회된 열차", "—")
        self.available = self.add_metric_card(metrics, "선택 좌석 예약 가능", "—")
        self.countdown = self.add_metric_card(metrics, "다음 조회까지", "대기")
        box.addLayout(metrics)
        actions = QHBoxLayout()
        self.search_button = QPushButton("열차 조회")
        self.search_button.clicked.connect(lambda: self.start_search(False))
        self.watch_button = QPushButton("선택 열차 감시")
        self.watch_button.setObjectName("Primary")
        self.watch_button.clicked.connect(lambda: self.start_search(True))
        self.stop_button = QPushButton("중지")
        self.stop_button.setObjectName("Stop")
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self.stop_search)
        for button in (self.search_button, self.watch_button, self.stop_button):
            actions.addWidget(button)
        actions.addStretch()
        self.order = QComboBox()
        for title, value in [("출발이 빠른 순", "departure"), ("소요시간 짧은 순", "duration"), ("도착이 빠른 순", "arrival")]:
            self.order.addItem(title, value)
        self.order.currentIndexChanged.connect(self.refresh_tables)
        actions.addWidget(self.order)
        box.addLayout(actions)
        self.target_note = label("목록에서 열차와 일반실/특실을 선택한 뒤 감시를 시작하세요.", "Target")
        self.target_note.setWordWrap(True)
        box.addWidget(self.target_note)
        self.banner = label("", "Banner")
        self.banner.setWordWrap(True)
        self.banner.hide()
        box.addWidget(self.banner)
        self.tabs = QTabWidget()
        self.pages = [ResultPage(), ResultPage()]
        self.tabs.addTab(self.pages[0], "대전 → 서울")
        self.tabs.addTab(self.pages[1], "서울 → 대전")
        for page in self.pages:
            page.table.cellClicked.connect(self.on_train_clicked)
            page.table.itemSelectionChanged.connect(self.update_target_note)
        self.seat.currentIndexChanged.connect(self.update_target_note)
        box.addWidget(self.tabs, 1)
        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        box.addWidget(self.progress)
        status_row = QHBoxLayout()
        self.status = label("조회 대기 · 한국 표준시 (KST)", "Muted")
        self.status.setWordWrap(True)
        status_row.addWidget(self.status, 1)
        self.tray_button = QPushButton("트레이로")
        self.tray_button.clicked.connect(self.hide_to_tray)
        status_row.addWidget(self.tray_button)
        box.addLayout(status_row)
        log_row = QHBoxLayout()
        log_row.addWidget(label("알림 기록", "Section"))
        log_row.addStretch()
        clear = QPushButton("기록 지우기")
        clear.clicked.connect(lambda: self.log.clear())
        log_row.addWidget(clear)
        box.addLayout(log_row)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(300)
        self.log.setFixedHeight(80)
        self.log.setPlaceholderText("조회 상태와 좌석 알림이 여기에 표시됩니다.")
        box.addWidget(self.log)
        return content

    def add_metric_card(self, layout, title, value):
        card = QFrame()
        card.setObjectName("Card")
        box = QVBoxLayout(card)
        box.setContentsMargins(18, 13, 18, 13)
        box.addWidget(label(title, "Muted"))
        number = label(value, "Metric")
        box.addWidget(number)
        layout.addWidget(card, 1)
        return number

    def make_tray(self):
        self.tray = QSystemTrayIcon(self.windowIcon(), self)
        self.tray.setToolTip("KTX Seat Watch")
        menu = QMenu(self)
        menu.addAction("앱 열기", self.restore_window)
        menu.addAction("감시 중지", self.stop_search)
        menu.addSeparator()
        menu.addAction("종료", self.close)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self.tray_activated)
        self.tray.messageClicked.connect(self.restore_window)
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray.show()
        else:
            self.tray_button.setEnabled(False)
            self.tray_button.setToolTip("이 환경에서는 시스템 트레이를 사용할 수 없습니다.")

    def tray_activated(self, reason):
        if reason in (QSystemTrayIcon.ActivationReason.Trigger, QSystemTrayIcon.ActivationReason.DoubleClick):
            self.restore_window()

    def restore_window(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def hide_to_tray(self):
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.hide()
            self.tray.showMessage("KTX Seat Watch", "앱이 트레이에서 계속 실행됩니다. 아이콘을 클릭하면 다시 열립니다.")

    def update_mode(self):
        self.mode.setText("DEMO · 모의 데이터" if self.demo.isChecked() else "KTX · 실제 조회")

    def add_log(self, text):
        line = f"{now_kst():%H:%M:%S}  {text}"
        self.log.appendPlainText(line)
        if sys.stdout is not None:
            print(line, flush=True)

    def read_config(self, monitor):
        self.interval.interpretText()
        trips = []
        if self.up.enabled.isChecked():
            trips.append(self.up.trip("대전", "서울"))
        if self.down.enabled.isChecked():
            trips.append(self.down.trip("서울", "대전"))
        if not trips:
            raise ValueError("조회할 방향을 하나 이상 선택하세요.")
        for trip in trips:
            if trip.start > trip.end:
                raise ValueError(f"{trip.dep} → {trip.arr}: 시작 시간이 종료 시간보다 늦습니다.")
            if trip.deadline < now_kst():
                raise ValueError(f"{trip.dep} → {trip.arr}: 선택한 시간대가 이미 지났습니다.")
        tokens = self.numbers.text().replace(",", " ").split()
        if any(not n.isascii() or not n.isdigit() for n in tokens):
            raise ValueError("열차 번호는 숫자로 입력하고 쉼표 또는 공백으로 구분하세요.")
        target = None
        if monitor:
            page = self.pages[0 if trips[0].dep == "대전" else 1]
            target = page.selected_train()
            if target is None:
                raise ValueError("먼저 열차를 조회하고 목록에서 감시할 열차를 선택하세요.")
            trip = trips[0]
            if (self.config is None or self.config.demo != self.demo.isChecked()
                    or target.departure.strftime("%Y%m%d") != trip.date
                    or not trip.start <= target.departure.strftime("%H%M%S") <= trip.end
                    or (target.dep, target.arr) != (trip.dep, trip.arr)):
                raise ValueError("조회 조건이 바뀌었습니다. 다시 조회한 뒤 열차를 선택하세요.")
            if target.departure <= now_kst():
                raise ValueError("이미 출발한 열차입니다. 다시 조회하세요.")
            # 전체 시간대를 순회하지 않고 선택 열차의 출발 시각만 조회한다.
            clock = target.departure.strftime("%H%M%S")
            trips = [replace(trip, start=clock, end=clock)]
        return WatchConfig(tuple(trips), self.seat.currentData(), self.interval.value(),
                           frozenset(n.lstrip("0") or "0" for n in tokens) if not monitor else frozenset(),
                           self.demo.isChecked(), monitor, target)

    def on_train_clicked(self, row, column):
        if self.worker is not None:
            return
        train = self.pages[self.tabs.currentIndex()].selected_train()
        if train is not None:
            self.numbers.setText(train.number)
        if column in (4, 5):
            self.seat.setCurrentIndex(0 if column == 4 else 1)
        self.update_target_note()

    def update_target_note(self):
        if not hasattr(self, "pages"):
            return
        active = self.worker is not None and self.config and self.config.monitor
        train = self.config.target if active else self.pages[self.tabs.currentIndex()].selected_train()
        seat = self.config.seat if active else self.seat.currentData()
        seat_name = {"general": "일반실", "special": "특실", "any": "일반실 또는 특실"}[seat]
        if train:
            self.target_note.setText(f"{'감시 중' if active else '감시 대상'}: {train.dep} → {train.arr} · "
                                     f"KTX {train.number} · {train.departure:%m/%d %H:%M} · {seat_name}")
        else:
            self.target_note.setText("목록에서 열차와 일반실/특실을 선택한 뒤 감시를 시작하세요.")

    def start_search(self, monitor):
        if self.worker is not None:
            return
        try:
            config = self.read_config(monitor)
        except ValueError as exc:
            self.show_banner(str(exc), error=True)
            return
        self.config = config
        self.tabs.setCurrentIndex(0 if config.trips[0].dep == "대전" else 1)
        for index, dep in enumerate(("대전", "서울")):
            self.tabs.setTabVisible(index, config.trips[0].dep == dep)
        self.results.clear()
        self.errors.clear()
        self.stamps.clear()
        self.banner.hide()
        self.next_poll = None
        self.stopping = False
        self.inputs.setEnabled(False)
        self.search_button.setEnabled(False)
        self.watch_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.countdown.setText("조회 중")
        self.progress.setRange(0, 0)
        self.refresh_tables()
        self.worker = WatchWorker(config, self)
        self.update_target_note()
        self.worker.cycle.connect(self.on_cycle)
        self.worker.seats_found.connect(self.on_alert)
        self.worker.status.connect(self.on_status)
        self.worker.waiting.connect(self.on_waiting)
        self.worker.fatal.connect(self.on_fatal)
        self.worker.finished.connect(self.on_finished)
        self.add_log(f"{'데모 · ' if config.demo else ''}{'좌석 감시 시작' if monitor else '열차 조회 시작'}")
        if monitor:
            self.add_log(self.target_note.text())
            self.add_log(f"조회 간격: {config.interval}초 (조회 완료 후 대기)")
        self.worker.start()

    def on_status(self, message):
        if self.stopping:
            return
        self.status.setText(message)
        if "조회 중" in message:
            self.next_poll = None
            self.countdown.setText("조회 중")
            self.progress.setRange(0, 0)

    def on_waiting(self, deadline):
        if self.stopping:
            return
        self.next_poll = deadline
        self.progress.setRange(0, 1)
        self.progress.setValue(1)
        self.tick()

    def on_cycle(self, results, errors):
        if self.stopping:
            return
        self.errors = errors
        for trip, trains in results.items():
            self.results[trip] = trains
            self.stamps[trip] = now_kst()
        for trip, error in errors.items():
            self.add_log(f"{trip.dep} → {trip.arr} 조회 실패: {error}")
        if errors:
            if any(trip in self.stamps for trip in errors):
                message = "조회에 실패했습니다. 아래는 이전 조회 결과이며, 현재 좌석 상태는 확인할 수 없습니다."
            else:
                message = "조회에 실패해 열차 정보를 가져오지 못했습니다. 아래 오류 안내를 확인하세요."
            self.show_banner(message, error=True)
        else:
            self.banner.hide()
            self.add_log(f"조회 완료 · {sum(len(t) for t in results.values())}개 열차")
        self.refresh_tables()

    def refresh_tables(self):
        if not hasattr(self, "pages"):
            return
        total = available = 0
        for index, (dep, arr) in enumerate([("대전", "서울"), ("서울", "대전")]):
            trip = next((t for t in self.config.trips if t.dep == dep), None) if self.config else None
            page = self.pages[index]
            rows = self.results.get(trip, [])
            rows = [t for t in rows if t.departure > now_kst()]
            stale = trip in self.errors
            page.display(sort_trains(rows, self.order.currentData()), stale)
            self.tabs.setTabText(index, f"{dep} → {arr}   {len(rows)}")
            if trip is None:
                page.note.setText("검색 조건을 설정하고 조회하세요." if self.config is None else "이번 조회에서 선택하지 않은 방향입니다.")
            elif stale:
                stamp = self.stamps.get(trip)
                prefix = f"이전 결과 ({stamp:%H:%M:%S})" if stamp else "조회 결과 없음"
                page.note.setText(f"{prefix} · 조회 실패: {self.errors[trip]}")
            elif trip in self.stamps:
                page.note.setText(f"{trip.date[:4]}.{trip.date[4:6]}.{trip.date[6:]} · {self.stamps[trip]:%H:%M:%S} 조회 · "
                                  + (f"{len(rows)}개 열차" if rows else "조건에 맞는 열차가 없습니다."))
            else:
                page.note.setText("열차를 조회하고 있습니다…")
            if not stale:
                total += len(rows)
                available += sum(t.available(self.config.seat) for t in rows) if self.config else 0
        self.total.setText(str(total) if self.config else "—")
        self.available.setText(str(available) if self.config else "—")
        self.update_target_note()

    def show_banner(self, message, error=False):
        self.banner.setText(message)
        self.banner.setStyleSheet("background: #FFF3EB; color: #9A522A; border-color: #F1D5BE;" if error else "")
        self.banner.show()

    def on_alert(self, trains):
        if self.stopping:
            return
        prefix = "[데모] " if self.config.demo else ""
        details = []
        for train in trains:
            seats = "/".join(name for name, code, kind in [("일반실", train.general, "general"), ("특실", train.special, "special")]
                             if code == "11" and self.config.seat in (kind, "any"))
            text = f"{train.dep} → {train.arr} · KTX {train.number} · {train.departure:%m/%d %H:%M} · {seats}"
            details.append(text)
            self.add_log(f"{prefix}좌석 발견! {text}")
        self.alert_count += len(trains)
        self.show_banner(f"{prefix}{len(trains)}개 열차에서 좌석을 찾았습니다. {details[0]} — 알림 기록을 확인하세요.")
        QApplication.alert(self, 5000)
        if self.sound.isChecked():
            QApplication.beep()
        if self.tray.isVisible():
            self.tray.showMessage(f"{prefix}KTX 좌석 발견", "\n".join(details[:4]),
                                  QSystemTrayIcon.MessageIcon.Information, 10000)

    def on_fatal(self, message):
        if self.stopping:
            return
        self.show_banner(message, error=True)
        self.status.setText("오류로 중지됨")
        self.add_log(message)

    def stop_search(self):
        if self.worker is not None:
            self.stopping = True
            self.next_poll = None
            self.worker.stop()
            self.stop_button.setEnabled(False)
            self.status.setText("중지 중 · 진행 중인 요청이 끝나면 종료됩니다.")
            self.countdown.setText("중지 중")

    def on_finished(self):
        worker = self.worker
        self.worker = None
        if worker:
            worker.deleteLater()
        self.next_poll = None
        self.inputs.setEnabled(True)
        self.search_button.setEnabled(True)
        self.watch_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.countdown.setText("대기")
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        if self.stopping:
            self.status.setText("감시가 중지되었습니다.")
        self.add_log("작업 종료")
        if self.closing:
            self.close()

    def tick(self):
        if self.next_poll is not None:
            seconds = max(0, math.ceil(self.next_poll - time.monotonic()))
            self.countdown.setText(f"{seconds}초")

    def closeEvent(self, event):
        if self.worker is not None:
            self.closing = True
            self.stop_search()
            event.ignore()
            return
        self.tray.hide()
        event.accept()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--demo", action="store_true", help="모의 데이터 모드로 시작")
    args = parser.parse_args(argv)
    app = QApplication(sys.argv[:1])
    app.setApplicationName("KTX Seat Watch")
    app.setOrganizationName("KTX Seat Watch")
    app.setStyle("Fusion")
    app.setFont(QFont("Malgun Gothic", 10))
    app.setStyleSheet(STYLE)
    window = MainWindow(demo=args.demo)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
