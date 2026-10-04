"""Android bridge; the desktop and APK use the same search and filtering code."""
import json
from dataclasses import replace
from datetime import datetime

from ktx_watch import (Trip, Train, KorailSource, DemoSource, SearchCancelled,
                       ServiceRejected, now_kst)


def query(payload, cancelled):
    cfg = json.loads(payload)
    trip = Trip(cfg["dep"], cfg["arr"], cfg["date"], cfg["start"], cfg["end"])
    target = cfg.get("target")
    source = None
    try:
        if target:
            train = Train(target["number"], target["name"], target["dep"], target["arr"],
                          datetime.fromisoformat(target["departure"]),
                          datetime.fromisoformat(target["arrival"]),
                          target["general"], target["special"])
            if train.departure <= now_kst():
                return json.dumps({"trains": [], "expired": True})
            trip = replace(trip, date=train.departure.strftime("%Y%m%d"),
                           start=train.departure.strftime("%H%M%S"),
                           end=train.departure.strftime("%H%M%S"))
        if cfg.get("demo"):
            source = DemoSource(train if target else None, cfg.get("seat", "general"))
            if target and cfg.get("round", 0) > 0:
                source.search(trip, now_kst(), cancelled=cancelled.get)
        else:
            source = KorailSource()
        trains = source.search(trip, now_kst(), cancelled=cancelled.get)
        if target:
            trains = [t for t in trains if t.key == train.key]
        return json.dumps({"trains": [dict(number=t.number, name=t.name, dep=t.dep,
                    arr=t.arr, departure=t.departure.isoformat(), arrival=t.arrival.isoformat(),
                    minutes=t.minutes, general=t.general, special=t.special) for t in trains]},
                          ensure_ascii=False)
    except SearchCancelled:
        return json.dumps({"cancelled": True})
    except Exception as exc:
        return json.dumps({"error": str(exc), "fatal": isinstance(exc, ServiceRejected)},
                          ensure_ascii=False)
    finally:
        if source:
            source.close()
