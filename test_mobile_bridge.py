"""Exercise the Android JSON contract without an Android device or live requests."""
import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from ktx_watch import now_kst, ServiceRejected
from datetime import timedelta

path = Path(__file__).parent / "mobile/android/app/src/main/python/mobile_api.py"
spec = importlib.util.spec_from_file_location("mobile_api", path)
bridge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge)


class CancelFlag:
    def __init__(self, value=False):
        self.value = value

    def get(self):
        return self.value


class MobileBridgeTests(unittest.TestCase):
    def setUp(self):
        self.cfg = dict(dep="대전", arr="서울", date=(now_kst() + timedelta(days=1)).strftime("%Y%m%d"),
                        start="070000", end="120000", demo=True, seat="special")

    def query(self, **changes):
        return json.loads(bridge.query(json.dumps(dict(self.cfg, **changes)), CancelFlag()))

    def test_demo_monitor_keeps_selected_train_and_seat(self):
        target = self.query()["trains"][1]
        first = self.query(target=target, round=0)["trains"]
        opened = self.query(target=target, round=1)["trains"]
        self.assertEqual(len(opened), 1)
        self.assertEqual(opened[0]["number"], target["number"])
        self.assertEqual(first[0]["special"], "13")
        self.assertEqual(opened[0]["special"], "11")
        self.assertEqual(opened[0]["general"], "13")

    def test_cancellation_returns_no_partial_results(self):
        result = json.loads(bridge.query(json.dumps(self.cfg), CancelFlag(True)))
        self.assertEqual(result, {"cancelled": True})

    def test_expired_target_stops(self):
        target = self.query()["trains"][0]
        target["departure"] = (now_kst() - timedelta(minutes=1)).isoformat()
        self.assertTrue(self.query(target=target)["expired"])

    def test_service_rejection_is_fatal(self):
        with patch.object(bridge, "KorailSource", side_effect=ServiceRejected("access denied")):
            result = self.query(demo=False)
        self.assertTrue(result["fatal"])

    def test_transient_network_error_can_retry(self):
        with patch.object(bridge, "KorailSource", side_effect=ConnectionError("offline")):
            result = self.query(demo=False)
        self.assertFalse(result["fatal"])


if __name__ == "__main__":
    unittest.main()
