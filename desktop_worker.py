"""조회 스레드: 네트워크와 감시 대기는 GUI 스레드 밖에서 실행한다."""
from dataclasses import dataclass
import threading
import time

from PyQt6.QtCore import QThread, pyqtSignal

from ktx_watch import AvailabilityTracker, DemoSource, KorailSource, SearchCancelled, ServiceRejected, Train, Trip, now_kst


@dataclass(frozen=True)
class WatchConfig:
    trips: tuple[Trip, ...]
    seat: str = "general"
    interval: int = 60
    numbers: frozenset[str] = frozenset()
    demo: bool = False
    monitor: bool = False
    target: Train | None = None


class WatchWorker(QThread):
    cycle = pyqtSignal(object, object)  # {Trip: list[Train]}, {Trip: error}
    seats_found = pyqtSignal(object)
    status = pyqtSignal(str)
    waiting = pyqtSignal(float)  # monotonic deadline
    fatal = pyqtSignal(str)

    def __init__(self, config, parent=None, source_factory=None):
        super().__init__(parent)
        self.config = config
        self.cancel_event = threading.Event()
        self.source_factory = source_factory

    def stop(self):
        self.cancel_event.set()

    def run(self):
        source = None
        cfg = self.config
        tracker = AvailabilityTracker()
        failures = {trip: 0 for trip in cfg.trips}
        try:
            if cfg.monitor and cfg.target is None:
                self.fatal.emit("감시할 열차를 목록에서 선택하세요.")
                return
            source = self.source_factory() if self.source_factory else (
                DemoSource(cfg.target, cfg.seat) if cfg.demo else KorailSource())
            while not self.cancel_event.is_set():
                active = [trip for trip in cfg.trips if trip.deadline >= now_kst()]
                if not active:
                    self.status.emit("조회 시간대가 지나 감시를 종료했습니다.")
                    return
                results = {trip: [] for trip in cfg.trips if trip not in active}
                errors = {}
                alerts = []
                for trip in active:
                    if self.cancel_event.is_set():
                        return
                    self.status.emit(f"{trip.dep} → {trip.arr} 조회 중…")
                    try:
                        trains = source.search(trip, now_kst(), cancelled=self.cancel_event.is_set)
                        if self.cancel_event.is_set():
                            return
                        trains = [t for t in trains if t.departure > now_kst()]
                        if cfg.monitor:
                            trains = [t for t in trains if t.key == cfg.target.key]
                        if cfg.numbers:
                            trains = [t for t in trains if (t.number.lstrip("0") or "0") in cfg.numbers]
                        results[trip] = trains
                        failures[trip] = 0
                        if cfg.monitor:
                            alerts.extend(tracker.update(trains, cfg.seat))
                    except SearchCancelled:
                        return
                    except ServiceRejected as exc:
                        errors[trip] = str(exc)
                        self.cycle.emit(results, errors)
                        self.fatal.emit(str(exc))
                        return
                    except Exception as exc:
                        failures[trip] += 1
                        errors[trip] = f"{type(exc).__name__}: {exc}"
                if self.cancel_event.is_set():
                    return
                self.cycle.emit(results, errors)
                if alerts:
                    self.seats_found.emit(alerts)
                if not cfg.monitor:
                    self.status.emit("조회 실패" if errors else "조회 완료")
                    return
                failure_count = max(failures[t] for t in active)
                if failure_count >= 5:
                    self.fatal.emit("같은 방향에서 5회 연속 조회에 실패해 감시를 중지했습니다.")
                    return
                delay = min(cfg.interval * 2 ** failure_count, 900)
                self.status.emit("연결 오류 · 재시도 대기" if errors else "좌석 감시 중")
                self.waiting.emit(time.monotonic() + delay)
                if self.cancel_event.wait(delay):
                    return
        except Exception as exc:
            self.fatal.emit(f"{type(exc).__name__}: {exc}")
        finally:
            if source is not None:
                source.close()
