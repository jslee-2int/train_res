"""PyQt6 설치 후 실행되는 GUI/스레드 동작 테스트. 외부 네트워크는 사용하지 않는다."""
import importlib.util
import os
import unittest
from dataclasses import replace
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
HAS_QT = importlib.util.find_spec("PyQt6") is not None

if HAS_QT:
    from PyQt6.QtCore import QDate
    from PyQt6.QtWidgets import QApplication
    from desktop_worker import WatchConfig, WatchWorker
    from gui_theme import STYLE
    from ktx_app import MainWindow
    from ktx_watch import DemoSource, now_kst, Trip, ServiceRejected


@unittest.skipUnless(HAS_QT, "PyQt6가 설치되지 않아 GUI 실행 테스트 생략")
class DesktopTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setStyle("Fusion")
        cls.app.setStyleSheet(STYLE)

    def setUp(self):
        self.window = MainWindow(demo=True)

    def tearDown(self):
        self.window.close()
        self.window.deleteLater()
        self.app.processEvents()

    def monitor_config(self, index=0, seat="general"):
        cfg = self.window.read_config(False)
        self.window.config = cfg
        rows = DemoSource().search(cfg.trips[0], now_kst())
        self.window.on_cycle({cfg.trips[0]: rows}, {})
        self.window.pages[0].table.selectRow(index)
        self.window.seat.setCurrentIndex(self.window.seat.findData(seat))
        return self.window.read_config(True)

    def test_default_config_has_one_direction(self):
        cfg = self.monitor_config()
        self.assertEqual(len(cfg.trips), 1)
        self.assertEqual(cfg.trips[0].dep, "대전")
        self.assertTrue(cfg.demo)
        self.assertTrue(cfg.monitor)
        self.assertEqual(cfg.seat, "general")

    def test_window_shows_and_renders(self):
        # QWidget/QPaintDevice.metric 가상 함수와 헬퍼 이름 충돌 방지.
        self.window.show()
        self.app.processEvents()
        self.assertGreater(self.window.logicalDpiX(), 0)
        frame = self.window.grab()
        self.assertFalse(frame.isNull())
        self.assertGreater(frame.width(), 0)

    def test_invalid_number_is_visible_without_starting_worker(self):
        self.window.numbers.setText("wrong")
        self.window.start_search(True)
        self.assertIsNone(self.window.worker)
        self.assertIn("열차 번호", self.window.banner.text())

    def test_direction_selection_is_exclusive(self):
        self.window.down.enabled.setChecked(True)
        self.assertFalse(self.window.up.enabled.isChecked())
        self.assertFalse(self.window.up.fields.isEnabled())
        self.assertTrue(self.window.down.fields.isEnabled())
        cfg = self.window.read_config(False)
        self.assertEqual(len(cfg.trips), 1)
        self.assertEqual(cfg.trips[0].dep, "서울")

    def test_first_failure_does_not_claim_previous_results(self):
        self.window.config = self.window.read_config(False)
        self.window.on_cycle({}, {self.window.config.trips[0]: "server rejected"})
        self.assertNotIn("이전", self.window.banner.text())

    def test_table_sort_and_stale_results(self):
        cfg = self.window.read_config(False)
        self.window.config = cfg
        trip = cfg.trips[0]
        source = DemoSource()
        source.search(trip, now_kst())
        rows = source.search(trip, now_kst())
        self.window.on_cycle({trip: rows}, {})
        self.assertEqual(self.window.available.text(), "1")
        self.window.order.setCurrentIndex(1)
        self.assertEqual(self.window.pages[0].table.item(0, 0).text(), "KTX 102")
        self.window.on_cycle({}, {trip: "offline"})
        self.assertEqual(self.window.available.text(), "0")
        self.assertIn("이전 결과", self.window.pages[0].note.text())

    def test_one_shot_worker_emits_results_but_no_alerts(self):
        cfg = self.window.read_config(False)
        worker = WatchWorker(cfg)
        reports, alerts = [], []
        worker.cycle.connect(lambda results, errors: reports.append((results, errors)))
        worker.seats_found.connect(alerts.extend)
        worker.run()
        self.assertEqual(len(reports), 1)
        self.assertEqual(len(reports[0][0]), 1)
        self.assertEqual(alerts, [])

    def test_monitor_detects_opening_and_stops_during_wait(self):
        cfg = self.monitor_config()
        worker = WatchWorker(cfg)
        alerts, reports = [], []
        worker.seats_found.connect(alerts.extend)
        worker.cycle.connect(lambda results, errors: reports.append(results))
        with patch.object(worker.cancel_event, "wait", side_effect=[False, True]):
            worker.run()
        self.assertEqual(len(reports), 2)
        self.assertEqual(len(alerts), 1)

    def test_failure_retries_stop_and_close_source(self):
        class Offline:
            closed = False

            def search(self, *args, **kwargs):
                raise RuntimeError("offline")

            def close(self):
                self.closed = True
        source = Offline()
        worker = WatchWorker(self.monitor_config(), source_factory=lambda: source)
        fatal = []
        worker.fatal.connect(fatal.append)
        with patch.object(worker.cancel_event, "wait", return_value=False) as wait:
            worker.run()
        self.assertEqual(wait.call_count, 4)
        self.assertEqual(len(fatal), 1)
        self.assertTrue(source.closed)

    def test_cancelled_worker_makes_no_query(self):
        worker = WatchWorker(self.monitor_config())
        reports = []
        worker.cycle.connect(lambda results, errors: reports.append(results))
        worker.stop()
        worker.run()
        self.assertEqual(reports, [])

    def test_service_rejection_stops_without_retry(self):
        from unittest.mock import Mock
        source = Mock()
        source.search.side_effect = ServiceRejected("업데이트 필요")
        worker = WatchWorker(self.monitor_config(), source_factory=lambda: source)
        fatal = []
        worker.fatal.connect(fatal.append)
        with patch.object(worker.cancel_event, "wait") as wait:
            worker.run()
        wait.assert_not_called()
        source.search.assert_called_once()
        source.close.assert_called_once()
        self.assertEqual(fatal, ["업데이트 필요"])

    def test_monitor_requires_selection(self):
        self.window.start_search(True)
        self.assertIsNone(self.window.worker)
        self.assertIn("선택", self.window.banner.text())

    def test_typed_five_seconds_is_committed_and_used_by_worker(self):
        self.monitor_config()
        self.window.interval.lineEdit().setText("5 초")
        cfg = self.window.read_config(True)
        self.assertEqual(self.window.interval.value(), 5)
        self.assertEqual(cfg.interval, 5)
        worker = WatchWorker(cfg)
        deadlines = []
        worker.waiting.connect(deadlines.append)
        with patch("desktop_worker.time.monotonic", return_value=100.0), \
                patch.object(worker.cancel_event, "wait", return_value=True) as wait:
            worker.run()
        wait.assert_called_once_with(5)
        self.assertEqual(deadlines, [105.0])
        self.assertEqual(self.window.interval.value(), 5)

    def test_selected_train_and_clicked_seat_become_watch_target(self):
        cfg = self.monitor_config(index=1)
        self.window.on_train_clicked(1, 5)
        cfg = self.window.read_config(True)
        self.assertEqual(cfg.target.number, "101")
        self.assertEqual(self.window.numbers.text(), "101")
        self.assertEqual(cfg.seat, "special")
        self.assertEqual(cfg.trips[0].start, cfg.target.departure.strftime("%H%M%S"))
        self.assertEqual(cfg.trips[0].start, cfg.trips[0].end)
        self.window.order.setCurrentIndex(1)
        self.assertEqual(self.window.read_config(True).target.key, cfg.target.key)

    def test_row_click_updates_number_and_keeps_seat_preference(self):
        self.monitor_config(index=1, seat="special")
        self.window.on_train_clicked(1, 0)
        self.assertEqual(self.window.numbers.text(), "101")
        self.assertEqual(self.window.seat.currentData(), "special")
        self.window.pages[0].table.selectRow(2)
        self.window.on_train_clicked(2, 4)
        self.assertEqual(self.window.numbers.text(), "102")
        self.assertEqual(self.window.seat.currentData(), "general")

    def test_monitor_excludes_other_trains_and_wrong_seat_class(self):
        from unittest.mock import Mock
        cfg = self.monitor_config(index=1, seat="special")
        target_general_only = replace(cfg.target, general="11", special="13")
        target_special_open = replace(cfg.target, general="11", special="11")
        other = replace(cfg.target, number="999", general="11", special="11")
        source = Mock()
        source.search.side_effect = [[other, target_general_only], [other, target_special_open], [other, target_special_open]]
        worker = WatchWorker(cfg, source_factory=lambda: source)
        alerts, reports = [], []
        worker.seats_found.connect(alerts.extend)
        worker.cycle.connect(lambda rows, errors: reports.append(rows))
        with patch.object(worker.cancel_event, "wait", side_effect=[False, False, True]):
            worker.run()
        self.assertEqual(alerts, [target_special_open])
        self.assertTrue(all(len(rows[cfg.trips[0]]) == 1 for rows in reports))
        for call in source.search.call_args_list:
            self.assertEqual(call.args[0].start, cfg.target.departure.strftime("%H%M%S"))
            self.assertEqual(call.args[0].start, call.args[0].end)

    def test_changed_date_rejects_old_selection(self):
        self.monitor_config()
        self.window.up.date.setDate(self.window.up.date.date().addDays(1))
        with self.assertRaisesRegex(ValueError, "조건"):
            self.window.read_config(True)


if __name__ == "__main__":
    unittest.main()
