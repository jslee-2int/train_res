import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ktx_seat_watch/main.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  late Map<String, dynamic> snapshot;
  late List<MethodCall> calls;
  setUp(() {
    snapshot = {'phase': 'idle', 'trains': [], 'logs': []};
    calls = [];
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(channel, (call) async {
          calls.add(call);
          if (call.method == 'snapshot') return jsonEncode(snapshot);
          if (call.method == 'notifications') return true;
          if (call.method == 'search') {
            final cfg = jsonDecode(call.arguments);
            final d = cfg['date'] as String;
            snapshot = {
              'phase': 'idle',
              'config': cfg,
              'logs': [],
              'trains': [
                {
                  'number': '100',
                  'name': 'KTX',
                  'dep': cfg['dep'],
                  'arr': cfg['arr'],
                  'departure':
                      '${d.substring(0, 4)}-${d.substring(4, 6)}-${d.substring(6, 8)}T07:00:00+09:00',
                  'arrival':
                      '${d.substring(0, 4)}-${d.substring(4, 6)}-${d.substring(6, 8)}T08:05:00+09:00',
                  'minutes': 65,
                  'general': '13',
                  'special': '13',
                },
              ],
            };
          }
          if (call.method == 'watch') {
            snapshot = {
              ...snapshot,
              'phase': 'watching',
              'config': jsonDecode(call.arguments),
              'nextPoll': DateTime.now().millisecondsSinceEpoch + 60000,
            };
          }
          if (call.method == 'stop') {
            snapshot = {...snapshot, 'phase': 'idle', 'nextPoll': 0};
          }
          return null;
        });
  });
  tearDown(
    () => TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(channel, null),
  );
  Future<void> open(WidgetTester tester) async {
    tester.view.physicalSize = const Size(390, 844);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    await tester.pumpWidget(const KtxApp());
    await tester.pumpAndSettle();
  }

  Future<void> savedDemo() async {
    final day = koreaNow().add(const Duration(days: 1));
    await channel.invokeMethod(
      'search',
      jsonEncode({
        'dep': '대전',
        'arr': '서울',
        'date': '${day.year}${two(day.month)}${two(day.day)}',
        'start': '070000',
        'end': '120000',
        'demo': true,
        'seat': 'general',
        'interval': 60,
      }),
    );
    calls.clear();
  }

  testWidgets('saved demo defaults to live and hides cached demo results', (
    tester,
  ) async {
    await savedDemo();
    await open(tester);
    expect(find.text('실제 조회'), findsOneWidget);
    expect(find.text('조회 결과 0'), findsOneWidget);
    final button = find.widgetWithText(FilledButton, '열차 조회');
    await tester.ensureVisible(button);
    await tester.pumpAndSettle();
    await tester.tap(button);
    await tester.pumpAndSettle();
    final sent = jsonDecode(
      calls.firstWhere((c) => c.method == 'search').arguments,
    );
    expect(sent['demo'], isFalse);
    await tester.pumpWidget(const SizedBox());
  });

  testWidgets('returning to a running demo keeps its mode visible', (
    tester,
  ) async {
    await savedDemo();
    final config = Map<String, dynamic>.from(snapshot['config']);
    config['target'] = snapshot['trains'][0];
    snapshot = {...snapshot, 'phase': 'watching', 'config': config};
    await open(tester);
    expect(find.text('좌석을 지켜보고 있어요'), findsOneWidget);
    expect(find.text('데모'), findsOneWidget);
    expect(find.text('실제 조회'), findsNothing);
    expect(calls.every((c) => c.method == 'snapshot'), isTrue);
    await tester.pumpWidget(const SizedBox());
  });

  testWidgets(
    'booking preparation sends watched target without stopping monitor',
    (tester) async {
      await savedDemo();
      final config = Map<String, dynamic>.from(snapshot['config']);
      config['target'] = snapshot['trains'][0];
      snapshot = {...snapshot, 'phase': 'watching', 'config': config};
      await open(tester);
      final booking = find.text('이 열차 예매 화면 준비');
      await tester.scrollUntilVisible(booking, 250);
      await tester.pumpAndSettle();
      await tester.tap(booking);
      await tester.pumpAndSettle();
      final requests = calls.where((c) => c.method == 'prepareBooking');
      expect(requests, hasLength(1));
      final request = jsonDecode(requests.single.arguments);
      expect(request['target'], config['target']);
      expect(request['seat'], config['seat']);
      expect(request['demo'], config['demo']);
      expect(calls.any((c) => c.method == 'stop'), isFalse);
      expect(snapshot['phase'], 'watching');
      expect(tester.takeException(), isNull);
      await tester.pumpWidget(const SizedBox());
    },
  );

  testWidgets('booking launch failure is shown and monitor stays active', (
    tester,
  ) async {
    await savedDemo();
    final config = Map<String, dynamic>.from(snapshot['config']);
    config['target'] = snapshot['trains'][0];
    snapshot = {...snapshot, 'phase': 'watching', 'config': config};
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(channel, (call) async {
          if (call.method == 'snapshot') return jsonEncode(snapshot);
          if (call.method == 'prepareBooking') {
            throw PlatformException(
              code: 'booking',
              message: '코레일+를 열지 못했습니다.',
            );
          }
          return null;
        });
    await open(tester);
    final booking = find.text('이 열차 예매 화면 준비');
    await tester.scrollUntilVisible(booking, 250);
    await tester.pumpAndSettle();
    await tester.tap(booking);
    await tester.pumpAndSettle();
    expect(find.text('코레일+를 열지 못했습니다.'), findsOneWidget);
    expect(snapshot['phase'], 'watching');
    expect(
      tester
          .widget<OutlinedButton>(
            find.ancestor(
              of: booking,
              matching: find.byWidgetPredicate((w) => w is OutlinedButton),
            ),
          )
          .onPressed,
      isNotNull,
    );
    await tester.pumpWidget(const SizedBox());
  });

  testWidgets('small phone supports larger text without overflow', (
    tester,
  ) async {
    tester.platformDispatcher.textScaleFactorTestValue = 1.3;
    addTearDown(tester.platformDispatcher.clearTextScaleFactorTestValue);
    await open(tester);
    tester.view.physicalSize = const Size(320, 640);
    await tester.pumpAndSettle();
    expect(tester.takeException(), isNull);
    await tester.tap(find.text('좌석 감시'));
    await tester.pumpAndSettle();
    expect(tester.takeException(), isNull);
    await tester.pumpWidget(const SizedBox());
  });
  testWidgets('phone layout and empty watch state', (tester) async {
    await open(tester);
    expect(find.text('어느 열차를 찾으세요?'), findsOneWidget);
    expect(tester.takeException(), isNull);
    await tester.tap(find.text('좌석 감시'));
    await tester.pumpAndSettle();
    expect(find.text('먼저 조회 결과에서 좌석을 선택하세요.'), findsOneWidget);
    expect(tester.takeException(), isNull);
    await tester.pumpWidget(const SizedBox());
  });
  testWidgets('selected seat is sent to background monitor and stop works', (
    tester,
  ) async {
    await open(tester);
    final button = find.widgetWithText(FilledButton, '열차 조회');
    await tester.ensureVisible(button);
    await tester.pumpAndSettle();
    await tester.tap(button);
    await tester.pumpAndSettle();
    final special = find.text('특실 · 매진');
    await tester.ensureVisible(special);
    await tester.pumpAndSettle();
    await tester.tap(special);
    await tester.pumpAndSettle();
    await tester.tap(find.text('좌석 감시'));
    await tester.pumpAndSettle();
    final start = find.text('선택 열차 감시 시작');
    await tester.ensureVisible(start);
    await tester.pumpAndSettle();
    await tester.tap(start);
    await tester.pumpAndSettle();
    final cfg = jsonDecode(
      calls.firstWhere((c) => c.method == 'watch').arguments,
    );
    expect(cfg['seat'], 'special');
    expect(cfg['target']['number'], '100');
    final stop = find.text('감시 중지');
    await tester.ensureVisible(stop);
    await tester.pumpAndSettle();
    await tester.tap(stop);
    await tester.pumpAndSettle();
    expect(calls.any((c) => c.method == 'stop'), isTrue);
    expect(tester.takeException(), isNull);
    await tester.pumpWidget(const SizedBox());
  });
  testWidgets('changing direction invalidates old results', (tester) async {
    await open(tester);
    final button = find.widgetWithText(FilledButton, '열차 조회');
    await tester.ensureVisible(button);
    await tester.pumpAndSettle();
    await tester.tap(button);
    await tester.pumpAndSettle();
    expect(find.text('조회 결과 1'), findsOneWidget);
    final direction = find.text('서울 → 대전');
    await tester.ensureVisible(direction);
    await tester.pumpAndSettle();
    await tester.tap(direction);
    await tester.pumpAndSettle();
    await tester.ensureVisible(find.text('조회 결과 0'));
    await tester.pumpAndSettle();
    expect(find.text('조회 결과 0'), findsOneWidget);
    await tester.pumpWidget(const SizedBox());
  });
}
