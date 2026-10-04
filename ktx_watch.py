"""대전 ↔ 서울 KTX 조회 및 좌석 알림. Python 3.11 이상."""
from __future__ import annotations

import argparse
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
import os
import threading
import time
from types import SimpleNamespace

KST = timezone(timedelta(hours=9))


def now_kst():
    return datetime.now(KST)


@dataclass(frozen=True)
class Trip:
    dep: str
    arr: str
    date: str
    start: str
    end: str

    @property
    def deadline(self):
        return datetime.strptime(self.date + self.end, "%Y%m%d%H%M%S").replace(tzinfo=KST)


@dataclass(frozen=True)
class Train:
    number: str
    name: str
    dep: str
    arr: str
    departure: datetime
    arrival: datetime
    general: str
    special: str

    @property
    def key(self):
        return (self.number, self.dep, self.arr, self.departure)

    @property
    def minutes(self):
        return int((self.arrival - self.departure).total_seconds() // 60)

    def available(self, seat):
        return ((seat in ("general", "any") and self.general == "11")
                or (seat in ("special", "any") and self.special == "11"))


def convert_train(raw):
    def stamp(date, clock):
        return datetime.strptime(date + clock, "%Y%m%d%H%M%S").replace(tzinfo=KST)
    return Train(str(raw.train_no), raw.train_type_name, raw.dep_name, raw.arr_name,
                 stamp(raw.dep_date, raw.dep_time), stamp(raw.arr_date, raw.arr_time),
                 raw.general_seat, raw.special_seat)


def sort_trains(trains, order):
    keys = {
        "departure": lambda t: (t.departure, t.arrival, t.number),
        "arrival": lambda t: (t.arrival, t.departure, t.number),
        "duration": lambda t: (t.minutes, t.departure, t.number),
    }
    return sorted(trains, key=keys[order])


class AvailabilityTracker:
    def __init__(self):
        self.previous = {}

    def update(self, trains, seat):
        alerts = []
        for train in trains:
            available = train.available(seat)
            if available and not self.previous.get(train.key, False):
                alerts.append(train)
            self.previous[train.key] = available
        # 누락된 열차/실패한 조회는 매진으로 간주하지 않는다.
        return alerts


class KorailSource:
    def __init__(self):
        try:
            from korail_mobile_api import KorailClient, TrainSearchQuery
            from korail_mobile_api.config import KorailConfig
        except ImportError as exc:
            raise RuntimeError("조회 모듈 업데이트가 필요합니다. 앱을 닫고 setup_app.bat을 실행한 후 다시 시작하세요.") from exc
        self.query_type = TrainSearchQuery
        self.client = KorailClient(KorailConfig(timeout=20.0, netfunnel_timeout=15.0, netfunnel_wait_limit=30.0))

    def page(self, trip, cursor):
        try:
            result = self.client.search_trains(self.query_type(
                departure_station_code=trip.dep, arrival_station_code=trip.arr,
                departure_date=trip.date, departure_time=cursor, train_group_code="100",
            ))
            return [mobile_row(row) for row in result.trains]
        except Exception as exc:
            if str(getattr(exc, "code", "")) in {"P100", "P114", "WRG000000", "WRD000061", "WRT300005"}:
                return []
            if is_service_rejection(exc):
                raise ServiceRejected(
                    "코레일 서버가 현재 조회 요청을 거절했습니다. 자동 감시를 중지합니다. "
                    "setup_app.bat으로 조회 모듈을 갱신한 뒤에도 같으면 코레일 공식 앱에서 확인하세요. "
                    f"서버 응답: {exc}"
                ) from exc
            raise

    def search(self, trip, now, cancelled=None):
        return search_pages(self.page, trip, now, cancelled=cancelled)

    def close(self):
        self.client.close()


class ServiceRejected(RuntimeError):
    """재시도로 해결되지 않는 클라이언트 호환성/접근 거절 응답."""


def is_service_rejection(exc):
    message = str(exc)
    return (type(exc).__name__ in {"KorailDynaPathError", "KorailAppUpdateRequiredError", "KorailQueueRejectedError"}
            or any(token in message for token in ("최신 버전", "MACRO", "미허가 도구", "-2000")))


def mobile_row(row):
    """새 클라이언트 모델을 공용 페이지 처리기의 입력으로 변환한다."""
    dep_date, dep_time, arr_time = row.departure_date, row.departure_time, row.arrival_time
    if not dep_date or not dep_time or not arr_time:
        raise RuntimeError("조회 응답에서 열차 날짜 또는 시간이 누락되었습니다.")
    arr_date = row.raw.get("h_arv_dt")
    if not arr_date:
        departure_day = datetime.strptime(dep_date, "%Y%m%d")
        arr_date = (departure_day + timedelta(days=int(arr_time < dep_time))).strftime("%Y%m%d")
    return SimpleNamespace(
        train_no=row.train_no, train_type_name=row.train_class_name or row.train_group_name or "",
        dep_name=row.departure_station_name, arr_name=row.arrival_station_name,
        dep_date=dep_date, dep_time=dep_time, arr_date=str(arr_date), arr_time=arr_time,
        general_seat=row.general_reservation_code, special_seat=row.special_reservation_code,
    )


class SearchCancelled(Exception):
    """사용자가 중지한 조회. 부분 결과를 최신 결과로 반환하지 않는다."""


def search_pages(fetch, trip, now, pause=time.sleep, cancelled=None):
    """첫 페이지 이후 열차도 조회하며 날짜가 바뀌면 중단한다."""
    if trip.deadline < now:
        return []
    start = datetime.strptime(trip.date + trip.start, "%Y%m%d%H%M%S").replace(tzinfo=KST)
    start = max(start, now.replace(microsecond=0) + timedelta(seconds=1))
    if start > trip.deadline:
        return []
    cursor = start.strftime("%H%M%S")
    found = {}
    for _ in range(200):
        if cancelled and cancelled():
            raise SearchCancelled()
        rows = fetch(trip, cursor)
        if cancelled and cancelled():
            raise SearchCancelled()
        if not rows:
            break
        trains = [convert_train(row) for row in rows]
        for train in trains:
            if (start <= train.departure <= trip.deadline
                    and train.dep == trip.dep and train.arr == trip.arr
                    and train.name.upper().startswith("KTX")):
                found[train.key] = train
        last = max(t.departure for t in trains)
        if last >= trip.deadline:
            break
        next_start = last + timedelta(seconds=1)
        if next_start.strftime("%Y%m%d") != trip.date:
            break
        next_cursor = next_start.strftime("%H%M%S")
        if next_cursor <= cursor:
            raise RuntimeError("조회 페이지가 진행되지 않습니다. 코레일 응답을 확인하세요.")
        cursor = next_cursor
        pause(1)
    else:
        raise RuntimeError("조회 페이지 한도를 초과했습니다.")
    return list(found.values())


class DemoSource:
    def __init__(self, target=None, seat="general"):
        self.calls = {}
        self.starts = {}
        self.target = target
        self.seat = seat

    def search(self, trip, now, cancelled=None):
        if cancelled and cancelled():
            raise SearchCancelled()
        count = self.calls.get(trip, 0)
        self.calls[trip] = count + 1
        if self.target is not None:
            train = self.target
            if count > 0:
                train = replace(train, **({"special": "11"} if self.seat == "special" else {"general": "11"}))
            return [train] if train.departure > now else []
        start = datetime.strptime(trip.date + trip.start, "%Y%m%d%H%M%S").replace(tzinfo=KST)
        start = max(start, now.replace(microsecond=0) + timedelta(minutes=10))
        start = self.starts.setdefault(trip, start)
        trains = [Train(str(100 + i), "KTX(모의)", trip.dep, trip.arr,
                        start + timedelta(minutes=i * 20),
                        start + timedelta(minutes=i * 20 + 65 - i * 5),
                        "11" if count > 0 and i == 0 else "13", "13")
                  for i in range(3)]
        return [t for t in trains if t.departure <= trip.deadline]

    def close(self):
        pass


def seat_text(code):
    return {"11": "가능", "13": "매진", "00": "없음"}.get(code, "확인필요")


def train_text(train):
    return (f"{train.name} {train.number} | {train.dep}→{train.arr} | "
            f"{train.departure:%m-%d %H:%M} → {train.arrival:%m-%d %H:%M} | "
            f"{train.minutes}분 | 일반실 {seat_text(train.general)} / 특실 {seat_text(train.special)}")


class Notifier:
    def __init__(self, popup=True):
        self.popup = popup
        self.lock = threading.Lock()

    def notify(self, trains):
        message = "\n".join(train_text(t) for t in trains)
        print(f"\n[좌석 알림] 선택한 좌석이 있습니다!\n{message}\n코레일톡에서 확인하세요.", flush=True)
        if os.name == "nt":
            import winsound
            winsound.PlaySound("SystemExclamation", winsound.SND_ALIAS | winsound.SND_ASYNC)
            if self.popup and self.lock.acquire(blocking=False):
                def show():
                    try:
                        import ctypes
                        ctypes.windll.user32.MessageBoxW(0, message, "KTX 좌석 알림", 0x40 | 0x10000)
                    finally:
                        self.lock.release()
                threading.Thread(target=show, daemon=True).start()
        else:
            print("\a", end="", flush=True)


def date_arg(value):
    try:
        return datetime.strptime(value.replace("-", ""), "%Y%m%d").strftime("%Y%m%d")
    except ValueError as exc:
        raise argparse.ArgumentTypeError("날짜는 YYYY-MM-DD 또는 YYYYMMDD 형식입니다.") from exc


def time_arg(value):
    try:
        clean = value.replace(":", "")
        if len(clean) != 4 or not clean.isdigit():
            raise ValueError()
        return datetime.strptime(clean, "%H%M").strftime("%H%M%S")
    except ValueError as exc:
        raise argparse.ArgumentTypeError("시간은 HH:MM 또는 HHMM 형식입니다.") from exc


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", type=date_arg, default=now_kst().strftime("%Y%m%d"), help="조회 날짜 (기본: 한국 오늘)")
    parser.add_argument("--direction", choices=["both", "up", "down"], default="both", help="both: 양방향, up: 대전→서울, down: 서울→대전")
    parser.add_argument("--start", type=time_arg, default="00:00", help="출발 시간 하한 HH:MM")
    parser.add_argument("--end", type=time_arg, default="23:59", help="출발 시간 상한 HH:MM")
    parser.add_argument("--return-date", type=date_arg, help="서울→대전 날짜 (기본: --date)")
    parser.add_argument("--return-start", type=time_arg, help="서울→대전 출발 시간 하한")
    parser.add_argument("--return-end", type=time_arg, help="서울→대전 출발 시간 상한")
    parser.add_argument("--sort", choices=["departure", "duration", "arrival"], default="departure")
    parser.add_argument("--seat", choices=["general", "special", "any"], default="general", help="알림 대상 좌석 (기본: 일반실)")
    parser.add_argument("--train", action="append", default=[], help="감시 열차 번호; 여러 번 지정 가능")
    parser.add_argument("--interval", type=int, default=60, help="조회 완료 후 대기 초 (최소 5초)")
    parser.add_argument("--once", action="store_true", help="한 번만 조회")
    parser.add_argument("--no-popup", action="store_true", help="Windows 팝업 끄기")
    parser.add_argument("--demo", action="store_true", help="접속 없이 모의 데이터 실행; 두 번째 조회에서 좌석 발생")
    args = parser.parse_args(argv)
    if args.interval < 5:
        parser.error("--interval은 5초 이상이어야 합니다.")
    if any(not number.isdigit() for number in args.train):
        parser.error("--train은 숫자 열차 번호입니다.")
    trips = []
    if args.direction in ("both", "up"):
        trips.append(Trip("대전", "서울", args.date, args.start, args.end))
    if args.direction in ("both", "down"):
        trips.append(Trip("서울", "대전", args.return_date or args.date,
                          args.return_start or args.start, args.return_end or args.end))
    for trip in trips:
        if trip.start > trip.end:
            parser.error(f"{trip.dep}→{trip.arr}: 시작 시간은 종료 시간 이하여야 합니다.")
        if trip.deadline < now_kst():
            parser.error(f"{trip.dep}→{trip.arr}: 조회 시간대가 이미 지났습니다.")
    return args, trips


def run(args, trips, source):
    tracker = AvailabilityTracker()
    notifier = Notifier(not args.no_popup)
    failures = {trip: 0 for trip in trips}
    wanted = {n.lstrip("0") or "0" for n in args.train}
    while True:
        active = [t for t in trips if t.deadline >= now_kst()]
        if not active:
            print("모든 조회 시간대가 지나 감시를 종료합니다.")
            return 0
        print(f"\n{'[모의 데이터] ' if args.demo else ''}[조회 {now_kst():%Y-%m-%d %H:%M:%S} KST]", flush=True)
        any_failed = False
        for trip in active:
            print(f"\n{trip.dep} → {trip.arr} ({trip.date})", flush=True)
            try:
                trains = sort_trains(source.search(trip, now_kst()), args.sort)
            except ServiceRejected as exc:
                print(str(exc), flush=True)
                return 1
            except Exception as exc:
                failures[trip] += 1
                any_failed = True
                print(f"조회 실패 {failures[trip]}/5: {type(exc).__name__}: {exc}", flush=True)
                continue
            failures[trip] = 0
            trains = [t for t in trains if t.departure > now_kst()]
            if wanted:
                trains = [t for t in trains if (t.number.lstrip("0") or "0") in wanted]
            if not trains:
                print("조건에 맞는 열차가 없습니다. (매진 여부와 별개)")
            for train in trains:
                print(train_text(train))
            alerts = tracker.update(trains, args.seat)
            if alerts:
                notifier.notify(alerts)
        if args.once:
            return 1 if any_failed else 0
        if max(failures.values()) >= 5:
            print("연속 조회 실패로 종료합니다. 연결 상태와 코레일 서비스 응답을 확인하세요.")
            return 1
        delay = min(args.interval * 2 ** max(failures.values()), 900)
        print(f"\n{delay}초 후 다시 조회합니다. 종료: Ctrl+C", flush=True)
        time.sleep(delay)


def main(argv=None):
    args, trips = parse_args(argv)
    source = None
    try:
        source = DemoSource() if args.demo else KorailSource()
        return run(args, trips, source)
    except KeyboardInterrupt:
        print("\n감시를 종료했습니다.")
        return 0
    except RuntimeError as exc:
        print(str(exc))
        return 1
    finally:
        if source:
            source.close()


if __name__ == "__main__":
    raise SystemExit(main())
