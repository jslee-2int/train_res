import contextlib
import io
import unittest
from dataclasses import replace
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import Mock, patch

import ktx_watch as app


NOW = datetime(2030, 1, 1, 8, tzinfo=app.KST)
TRIP = app.Trip("대전", "서울", "20300101", "090000", "120000")


def train(number="101", hour=9, minutes=60, general="13", special="13"):
    dep = NOW.replace(hour=hour)
    return app.Train(number, "KTX", "대전", "서울", dep,
                     dep + timedelta(minutes=minutes), general, special)


def raw(t):
    return SimpleNamespace(train_no=t.number, train_type_name=t.name,
                           dep_name=t.dep, arr_name=t.arr,
                           dep_date=t.departure.strftime("%Y%m%d"),
                           dep_time=t.departure.strftime("%H%M%S"),
                           arr_date=t.arrival.strftime("%Y%m%d"),
                           arr_time=t.arrival.strftime("%H%M%S"),
                           general_seat=t.general, special_seat=t.special)


class WatchTests(unittest.TestCase):
    def test_mobile_adapter_midnight_and_seat_codes(self):
        row = SimpleNamespace(
            train_no="103", train_class_name="KTX-산천", train_group_name="KTX",
            departure_date="20300101", departure_time="233000", arrival_time="003000",
            departure_station_name="대전", arrival_station_name="서울", raw={},
            general_reservation_code="13", special_reservation_code="11",
        )
        result = app.convert_train(app.mobile_row(row))
        self.assertEqual(result.minutes, 60)
        self.assertEqual(result.arrival.day, 2)
        self.assertTrue(result.available("special"))
        self.assertFalse(result.available("general"))

    def test_mobile_adapter_missing_time_fails_explicitly(self):
        row = SimpleNamespace(departure_date="20300101", departure_time=None, arrival_time="100000")
        with self.assertRaisesRegex(RuntimeError, "누락"):
            app.mobile_row(row)

    def test_server_rejection_is_not_transient_connection_failure(self):
        self.assertTrue(app.is_service_rejection(RuntimeError("앱을 최신 버전으로 업데이트")))
        self.assertFalse(app.is_service_rejection(TimeoutError("timed out")))

    def test_sold_out_to_available_and_reopen(self):
        tracker = app.AvailabilityTracker()
        sold = train()
        opened = replace(sold, general="11")
        self.assertEqual(tracker.update([sold], "general"), [])
        self.assertEqual(tracker.update([opened], "general"), [opened])
        self.assertEqual(tracker.update([opened], "general"), [])
        self.assertEqual(tracker.update([], "general"), [])
        self.assertEqual(tracker.update([opened], "general"), [])
        tracker.update([sold], "general")
        self.assertEqual(tracker.update([opened], "general"), [opened])

    def test_seat_class_and_unknown_status(self):
        special = train(special="11")
        self.assertFalse(special.available("general"))
        self.assertTrue(special.available("special"))
        self.assertTrue(special.available("any"))
        self.assertFalse(train(general="09").available("general"))

    def test_sort_orders(self):
        early = train("101", 9, 150)
        fast = train("103", 10, 45)
        self.assertEqual(app.sort_trains([fast, early], "departure"), [early, fast])
        self.assertEqual(app.sort_trains([early, fast], "duration"), [fast, early])
        self.assertEqual(app.sort_trains([early, fast], "arrival"), [fast, early])

    def test_second_page_and_end_filter(self):
        a, b, late = train(), train("103", 10), train("105", 13)
        fetch = Mock(side_effect=[[raw(a)], [raw(b), raw(late)]])
        result = app.search_pages(fetch, TRIP, NOW, pause=lambda _: None)
        self.assertEqual(result, [a, b])
        self.assertEqual(fetch.call_args_list[1].args[1], "090001")

    def test_midnight_does_not_wrap_to_start(self):
        late = replace(train(), departure=NOW.replace(hour=23, minute=59),
                       arrival=(NOW + timedelta(days=1)).replace(hour=1))
        trip = replace(TRIP, start="230000", end="235900")
        fetch = Mock(return_value=[raw(late)])
        self.assertEqual(app.search_pages(fetch, trip, NOW, pause=lambda _: None), [late])
        self.assertEqual(fetch.call_count, 1)
        self.assertEqual(late.minutes, 61)

    def test_stuck_page_is_error(self):
        fetch = Mock(return_value=[raw(train())])
        with self.assertRaisesRegex(RuntimeError, "진행"):
            app.search_pages(fetch, TRIP, NOW, pause=lambda _: None)

    def test_elapsed_trip_makes_no_request(self):
        fetch = Mock()
        self.assertEqual(app.search_pages(fetch, TRIP, NOW.replace(hour=14)), [])
        fetch.assert_not_called()

    def test_cancel_before_request(self):
        fetch = Mock()
        with self.assertRaises(app.SearchCancelled):
            app.search_pages(fetch, TRIP, NOW, cancelled=lambda: True)
        fetch.assert_not_called()

    def test_cancel_during_request_discards_partial_result(self):
        cancelled = Mock(side_effect=[False, True])
        fetch = Mock(return_value=[raw(train())])
        with self.assertRaises(app.SearchCancelled):
            app.search_pages(fetch, TRIP, NOW, cancelled=cancelled)

    def test_return_options_and_invalid_interval(self):
        with patch.object(app, "now_kst", return_value=NOW):
            args, trips = app.parse_args(["--date", "2030-01-02", "--return-date", "2030-01-03",
                                          "--return-start", "18:00"])
            self.assertEqual(len(trips), 2)
            self.assertEqual(trips[1].date, "20300103")
            self.assertEqual(trips[1].start, "180000")
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                app.parse_args(["--interval", "0"])

    def test_demo_opens_same_train(self):
        source = app.DemoSource()
        a = source.search(TRIP, NOW)
        b = source.search(TRIP, NOW + timedelta(seconds=60))
        self.assertEqual(a[0].key, b[0].key)
        self.assertFalse(a[0].available("general"))
        self.assertTrue(b[0].available("general"))

    def test_one_direction_failure_does_not_hide_other(self):
        with patch.object(app, "now_kst", return_value=NOW):
            args, trips = app.parse_args(["--date", "2030-01-01", "--once", "--train", "00101"])
            source = Mock()
            source.search.side_effect = [RuntimeError("offline"), [train(general="11")]]
            with patch.object(app.Notifier, "notify") as notify, contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(app.run(args, trips, source), 1)
                notify.assert_called_once()

    def test_retry_limit_and_backoff(self):
        with patch.object(app, "now_kst", return_value=NOW):
            args, trips = app.parse_args(["--date", "2030-01-01", "--direction", "up"])
            source = Mock()
            source.search.side_effect = RuntimeError("offline")
            with patch.object(app.time, "sleep") as sleep, contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(app.run(args, trips, source), 1)
                self.assertEqual(source.search.call_count, 5)
                self.assertEqual([c.args[0] for c in sleep.call_args_list], [120, 240, 480, 900])


if __name__ == "__main__":
    unittest.main()
