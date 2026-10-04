import 'dart:async';
import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_localizations/flutter_localizations.dart';

const blue = Color(0xFF326BDB),
    ink = Color(0xFF17243B),
    muted = Color(0xFF758196);
const channel = MethodChannel('ktx/watch');
String two(int n) => n.toString().padLeft(2, '0');
DateTime koreaNow() => DateTime.now().toUtc().add(const Duration(hours: 9));
String clockOf(String s) => s.substring(11, 16);
String seatText(String s) => switch (s) {
  '11' => '가능',
  '13' => '매진',
  '00' => '없음',
  _ => '확인 필요',
};
void main() => runApp(const KtxApp());

class KtxApp extends StatelessWidget {
  const KtxApp({super.key});
  @override
  Widget build(BuildContext context) => MaterialApp(
    title: 'KTX 좌석 알림',
    debugShowCheckedModeBanner: false,
    locale: const Locale('ko'),
    supportedLocales: const [Locale('ko'), Locale('en')],
    localizationsDelegates: GlobalMaterialLocalizations.delegates,
    theme: ThemeData(
      useMaterial3: true,
      colorScheme: ColorScheme.fromSeed(
        seedColor: blue,
      ).copyWith(primary: blue),
      scaffoldBackgroundColor: const Color(0xFFF4F6FA),
      appBarTheme: const AppBarTheme(
        backgroundColor: Color(0xFFF4F6FA),
        foregroundColor: ink,
        scrolledUnderElevation: 0,
      ),
      filledButtonTheme: FilledButtonThemeData(
        style: FilledButton.styleFrom(
          minimumSize: const Size(0, 52),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(16),
          ),
        ),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          minimumSize: const Size(0, 48),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(14),
          ),
        ),
      ),
    ),
    home: const HomePage(),
  );
}

class HomePage extends StatefulWidget {
  const HomePage({super.key});
  @override
  State<HomePage> createState() => _HomePageState();
}

class _HomePageState extends State<HomePage> with WidgetsBindingObserver {
  Map<String, dynamic> state = {};
  Map<String, dynamic>? selected;
  DateTime date = koreaNow().add(const Duration(days: 1));
  TimeOfDay start = const TimeOfDay(hour: 7, minute: 0),
      end = const TimeOfDay(hour: 12, minute: 0);
  bool reverse = false,
      demo = false,
      busy = false,
      initialized = false,
      refreshing = false;
  int interval = 60, tab = 0;
  String seat = 'general', sort = 'departure';
  Timer? timer;
  String get phase => state['phase'] ?? 'idle';
  bool get watching => phase == 'watching';
  bool get locked => busy || phase != 'idle';
  String get dep => reverse ? '서울' : '대전';
  String get arr => reverse ? '대전' : '서울';
  String timeCode(TimeOfDay t) => '${two(t.hour)}${two(t.minute)}00';
  String timeText(TimeOfDay t) => '${two(t.hour)}:${two(t.minute)}';
  Map<String, dynamic> config() => {
    'dep': dep,
    'arr': arr,
    'date': '${date.year}${two(date.month)}${two(date.day)}',
    'start': timeCode(start),
    'end': timeCode(end),
    'demo': demo,
    'seat': seat,
    'interval': interval,
  };
  List<Map<String, dynamic>> get trains {
    final cfg = state['config'] as Map?;
    if (cfg == null ||
        [
          'dep',
          'arr',
          'date',
          'start',
          'end',
          'demo',
        ].any((k) => cfg[k] != config()[k])) {
      return [];
    }
    final rows = (state['trains'] as List? ?? [])
        .map((e) => Map<String, dynamic>.from(e))
        .toList();
    rows.sort(
      (a, b) => sort == 'duration'
          ? (a['minutes'] as int).compareTo(b['minutes'] as int)
          : a[sort].toString().compareTo(b[sort].toString()),
    );
    return rows;
  }

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    refresh();
    timer = Timer.periodic(const Duration(seconds: 1), (_) => refresh());
  }

  @override
  void dispose() {
    timer?.cancel();
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState s) {
    if (s == AppLifecycleState.resumed) refresh();
  }

  Future<void> refresh() async {
    if (refreshing) return;
    refreshing = true;
    try {
      final raw = await channel.invokeMethod<String>('snapshot');
      if (!mounted || raw == null) return;
      final next = jsonDecode(raw) as Map<String, dynamic>;
      setState(() {
        state = next;
        if (!initialized) {
          initialized = true;
          final cfg = next['config'] as Map?;
          if (cfg != null) {
            reverse = cfg['dep'] == '서울';
            // Restore demo only for a job which is still running. A new idle
            // screen defaults to live queries, even after a previous demo.
            demo =
                (phase == 'watching' || phase == 'searching') &&
                cfg['demo'] == true;
            interval = cfg['interval'] ?? 60;
            seat = cfg['seat'] ?? 'general';
            final d = cfg['date'].toString();
            date = DateTime(
              int.parse(d.substring(0, 4)),
              int.parse(d.substring(4, 6)),
              int.parse(d.substring(6, 8)),
            );
            TimeOfDay parse(String s) => TimeOfDay(
              hour: int.parse(s.substring(0, 2)),
              minute: int.parse(s.substring(2, 4)),
            );
            start = parse(cfg['start']);
            end = parse(cfg['end']);
            if (watching) {
              selected = Map<String, dynamic>.from(cfg['target']);
              tab = 1;
            }
          }
        }
      });
    } catch (_) {
      /* Preserve last known state during Activity transitions. */
    } finally {
      refreshing = false;
    }
  }

  void message(String text) {
    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(text)));
    }
  }

  Future<void> invoke(String method, [Map<String, dynamic>? args]) async {
    setState(() => busy = true);
    try {
      await channel.invokeMethod(
        method,
        args == null ? null : jsonEncode(args),
      );
      await refresh();
    } on PlatformException catch (e) {
      message(e.message ?? '작업을 실행하지 못했습니다.');
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Future<void> search() async {
    if (timeCode(start).compareTo(timeCode(end)) > 0) {
      message('종료 시간을 시작 시간 이후로 지정하세요.');
      return;
    }
    setState(() => selected = null);
    await invoke('search', config());
  }

  Future<void> watch() async {
    if (selected == null) return;
    try {
      if (await channel.invokeMethod<bool>('notifications') != true) {
        message('좌석 알림을 받으려면 알림 권한을 허용하세요.');
        return;
      }
      await invoke('watch', {...config(), 'target': selected});
      if (mounted) setState(() => tab = 1);
    } on PlatformException catch (e) {
      message(e.message ?? '알림 권한을 확인하지 못했습니다.');
    }
  }

  Future<void> pickDate() async {
    final now = koreaNow(),
        today = DateTime(koreaNow().year, koreaNow().month, koreaNow().day);
    final d = await showDatePicker(
      context: context,
      initialDate: date.isBefore(today) ? today : date,
      firstDate: today,
      lastDate: now.add(const Duration(days: 365)),
      helpText: '출발 날짜',
      cancelText: '취소',
      confirmText: '선택',
    );
    if (d != null) {
      setState(() {
        date = d;
        selected = null;
      });
    }
  }

  Future<void> pickTime(bool first) async {
    final t = await showTimePicker(
      context: context,
      initialTime: first ? start : end,
      helpText: first ? '시작 시간' : '종료 시간',
      cancelText: '취소',
      confirmText: '선택',
      builder: (c, w) => MediaQuery(
        data: MediaQuery.of(c).copyWith(alwaysUse24HourFormat: true),
        child: w!,
      ),
    );
    if (t != null) {
      setState(() {
        if (first) {
          start = t;
        } else {
          end = t;
        }
        selected = null;
      });
    }
  }

  Widget panel(Widget child) => Container(
    width: double.infinity,
    padding: const EdgeInsets.all(20),
    decoration: BoxDecoration(
      color: Colors.white,
      borderRadius: BorderRadius.circular(24),
    ),
    child: child,
  );
  Widget badge(String text, Color color) => Container(
    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
    decoration: BoxDecoration(
      color: color.withValues(alpha: .1),
      borderRadius: BorderRadius.circular(8),
    ),
    child: Text(
      text,
      style: TextStyle(color: color, fontSize: 12, fontWeight: FontWeight.w700),
    ),
  );
  Widget heading(String text, String sub) => Padding(
    padding: const EdgeInsets.only(bottom: 20),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          text,
          style: const TextStyle(
            fontSize: 23,
            fontWeight: FontWeight.w800,
            color: ink,
          ),
        ),
        const SizedBox(height: 8),
        Text(sub, style: const TextStyle(color: muted, height: 1.5)),
      ],
    ),
  );
  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: const Row(
        children: [
          Icon(Icons.train_rounded, color: blue),
          SizedBox(width: 9),
          Flexible(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'KTX Seat Watch',
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: TextStyle(fontSize: 19, fontWeight: FontWeight.w800),
                ),
                SizedBox(height: 2),
                Text(
                  'For Shin Yong-woo',
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: TextStyle(
                    fontSize: 11,
                    fontWeight: FontWeight.w500,
                    color: muted,
                    letterSpacing: 0.3,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
      actions: [
        IconButton(
          onPressed: help,
          tooltip: '사용 안내',
          icon: const Icon(Icons.info_outline_rounded),
        ),
      ],
    ),
    body: SafeArea(
      top: false,
      child: Align(
        alignment: Alignment.topCenter,
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 640),
          child: ListView(
            key: PageStorageKey('page-$tab'),
            padding: const EdgeInsets.fromLTRB(20, 12, 20, 28),
            children: tab == 0
                ? searchPage()
                : tab == 1
                ? watchPage()
                : historyPage(),
          ),
        ),
      ),
    ),
    bottomNavigationBar: NavigationBar(
      selectedIndex: tab,
      onDestinationSelected: (i) => setState(() => tab = i),
      destinations: const [
        NavigationDestination(icon: Icon(Icons.search_rounded), label: '열차 조회'),
        NavigationDestination(
          icon: Icon(Icons.notifications_active_outlined),
          label: '좌석 감시',
        ),
        NavigationDestination(
          icon: Icon(Icons.history_rounded),
          label: '알림 기록',
        ),
      ],
    ),
  );
  List<Widget> searchPage() => [
    Container(
      padding: const EdgeInsets.all(24),
      decoration: BoxDecoration(
        gradient: const LinearGradient(colors: [Color(0xFF173C81), blue]),
        borderRadius: BorderRadius.circular(26),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            '기다리는 좌석, 놓치지 않게',
            style: TextStyle(color: Color(0xFFC4D8FF), fontSize: 13),
          ),
          const SizedBox(height: 16),
          Row(
            children: [
              Text(
                dep,
                style: const TextStyle(
                  color: Colors.white,
                  fontSize: 30,
                  fontWeight: FontWeight.w800,
                ),
              ),
              const Expanded(
                child: Icon(Icons.east_rounded, color: Color(0xFF9CBFFF)),
              ),
              Text(
                arr,
                style: const TextStyle(
                  color: Colors.white,
                  fontSize: 30,
                  fontWeight: FontWeight.w800,
                ),
              ),
            ],
          ),
          const SizedBox(height: 14),
          const Text(
            '열차를 고르면, 좌석이 생길 때 알려드려요.',
            style: TextStyle(color: Colors.white, fontSize: 13),
          ),
        ],
      ),
    ),
    const SizedBox(height: 20),
    panel(
      Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Expanded(
                child: Text(
                  '어느 열차를 찾으세요?',
                  style: TextStyle(fontWeight: FontWeight.w800, fontSize: 17),
                ),
              ),
              badge(demo ? '데모' : '실제 조회', demo ? Colors.orange : blue),
            ],
          ),
          const SizedBox(height: 18),
          SizedBox(
            width: double.infinity,
            child: SegmentedButton<bool>(
              segments: const [
                ButtonSegment(value: false, label: Text('대전 → 서울')),
                ButtonSegment(value: true, label: Text('서울 → 대전')),
              ],
              selected: {reverse},
              onSelectionChanged: locked
                  ? null
                  : (s) => setState(() {
                      reverse = s.first;
                      selected = null;
                      start = TimeOfDay(hour: reverse ? 17 : 7, minute: 0);
                      end = TimeOfDay(hour: reverse ? 23 : 12, minute: 0);
                    }),
            ),
          ),
          const SizedBox(height: 16),
          SizedBox(
            width: double.infinity,
            child: OutlinedButton.icon(
              onPressed: locked ? null : pickDate,
              icon: const Icon(Icons.calendar_today_outlined, size: 18),
              label: Text(
                '${date.year}.${two(date.month)}.${two(date.day)}  출발',
              ),
            ),
          ),
          const SizedBox(height: 10),
          Row(
            children: [
              Expanded(
                child: OutlinedButton(
                  onPressed: locked ? null : () => pickTime(true),
                  child: Text('${timeText(start)} 부터'),
                ),
              ),
              const Padding(
                padding: EdgeInsets.symmetric(horizontal: 10),
                child: Text('—'),
              ),
              Expanded(
                child: OutlinedButton(
                  onPressed: locked ? null : () => pickTime(false),
                  child: Text('${timeText(end)} 까지'),
                ),
              ),
            ],
          ),
          const SizedBox(height: 14),
          SizedBox(
            width: double.infinity,
            child: FilledButton.icon(
              onPressed: locked ? null : search,
              icon: const Icon(Icons.search_rounded),
              label: Text(phase == 'searching' ? '열차를 찾고 있어요' : '열차 조회'),
            ),
          ),
          if (phase == 'searching')
            Center(
              child: TextButton(
                onPressed: () => invoke('stop'),
                child: const Text('조회 중지'),
              ),
            ),
          SwitchListTile.adaptive(
            contentPadding: EdgeInsets.zero,
            dense: true,
            title: const Text('데모 모드'),
            subtitle: const Text('실제 요청 없이 알림 체험'),
            value: demo,
            onChanged: locked
                ? null
                : (v) => setState(() {
                    demo = v;
                    selected = null;
                  }),
          ),
        ],
      ),
    ),
    const SizedBox(height: 24),
    Row(
      children: [
        Expanded(
          child: Text(
            '조회 결과 ${trains.length}',
            style: const TextStyle(fontSize: 19, fontWeight: FontWeight.w800),
          ),
        ),
        DropdownButton<String>(
          value: sort,
          underline: const SizedBox(),
          items: const [
            DropdownMenuItem(value: 'departure', child: Text('출발순')),
            DropdownMenuItem(value: 'arrival', child: Text('도착순')),
            DropdownMenuItem(value: 'duration', child: Text('소요시간순')),
          ],
          onChanged: (v) => setState(() => sort = v!),
        ),
      ],
    ),
    if (state['message'] != null)
      Padding(
        padding: const EdgeInsets.only(bottom: 12),
        child: Text(
          state['message'],
          style: const TextStyle(color: muted, fontSize: 12, height: 1.5),
        ),
      ),
    if (trains.isEmpty)
      panel(
        const Column(
          children: [
            Icon(Icons.train_outlined, size: 40, color: Color(0xFFA5B3C8)),
            SizedBox(height: 12),
            Text('원하는 시간대의 열차를 조회하세요.', style: TextStyle(color: muted)),
          ],
        ),
      ),
    if (trains.isNotEmpty && (state['searchUpdated'] as int? ?? 0) > 0)
      Padding(
        padding: const EdgeInsets.only(bottom: 12),
        child: Text(
          '조회 당시 좌석 · ${DateTime.fromMillisecondsSinceEpoch(state['searchUpdated'], isUtc: true).add(const Duration(hours: 9)).toString().substring(5, 19)} (한국 시간)',
          style: const TextStyle(color: muted, fontSize: 12),
        ),
      ),
    for (final t in trains)
      Padding(padding: const EdgeInsets.only(bottom: 12), child: trainCard(t)),
    if (selected != null && !watching)
      FilledButton.icon(
        onPressed: locked ? null : () => setState(() => tab = 1),
        icon: const Icon(Icons.notifications_none_rounded),
        label: Text('KTX ${selected!['number']} 감시 설정'),
      ),
  ];
  Widget trainCard(Map<String, dynamic> t, {bool controls = true}) {
    final chosen =
        selected?['number'] == t['number'] &&
        selected?['departure'] == t['departure'];
    return Container(
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(22),
        border: Border.all(
          color: chosen ? blue : const Color(0xFFE6EAF1),
          width: chosen ? 1.5 : 1,
        ),
      ),
      child: Column(
        children: [
          Row(
            children: [
              badge('KTX ${t['number']}', blue),
              const Spacer(),
              if (chosen)
                const Icon(Icons.check_circle_rounded, color: blue, size: 20),
              Text(
                '  ${t['minutes']}분',
                style: const TextStyle(color: muted, fontSize: 12),
              ),
            ],
          ),
          const SizedBox(height: 17),
          Row(
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      clockOf(t['departure']),
                      style: const TextStyle(
                        fontSize: 28,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                    Text(t['dep'], style: const TextStyle(color: muted)),
                  ],
                ),
              ),
              const Icon(Icons.east_rounded, color: Color(0xFFC2CCDB)),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.end,
                  children: [
                    Text(
                      clockOf(t['arrival']),
                      style: const TextStyle(
                        fontSize: 28,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                    Text(t['arr'], style: const TextStyle(color: muted)),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 18),
          Row(
            children: [
              for (final kind in ['general', 'special']) ...[
                if (kind == 'special') const SizedBox(width: 10),
                Expanded(
                  child: OutlinedButton(
                    style: OutlinedButton.styleFrom(
                      backgroundColor: chosen && seat == kind
                          ? const Color(0xFFEFF4FF)
                          : null,
                      side: BorderSide(
                        color: chosen && seat == kind
                            ? blue
                            : const Color(0xFFE1E7EF),
                      ),
                    ),
                    onPressed: !controls || locked
                        ? null
                        : () => setState(() {
                            selected = t;
                            seat = kind;
                          }),
                    child: Text(
                      '${kind == 'general' ? '일반실' : '특실'} · ${seatText(t[kind])}',
                      style: TextStyle(
                        fontSize: 12,
                        color: t[kind] == '11' ? blue : muted,
                      ),
                    ),
                  ),
                ),
              ],
            ],
          ),
        ],
      ),
    );
  }

  List<Widget> watchPage() {
    final cfg = state['config'] as Map?;
    final target = watching
        ? Map<String, dynamic>.from(cfg?['target'] ?? {})
        : selected;
    final next = state['nextPoll'] as int? ?? 0;
    final seconds = ((next - DateTime.now().millisecondsSinceEpoch) / 1000)
        .ceil()
        .clamp(0, 600);
    return [
      heading(
        watching ? '좌석을 지켜보고 있어요' : '내 열차만, 조용히 기다리기',
        watching ? '화면을 꺼도 감시가 이어집니다.' : '열차 한 편과 좌석 등급을 선택해 감시합니다.',
      ),
      if (target == null || target.isEmpty)
        panel(
          Column(
            children: [
              const Icon(
                Icons.notifications_none_rounded,
                size: 48,
                color: muted,
              ),
              const SizedBox(height: 16),
              const Text('먼저 조회 결과에서 좌석을 선택하세요.'),
              const SizedBox(height: 16),
              FilledButton(
                onPressed: () => setState(() => tab = 0),
                child: const Text('열차 조회로 이동'),
              ),
            ],
          ),
        )
      else ...[
        trainCard(
          Map<String, dynamic>.from(
            watching ? state['current'] ?? target : target,
          ),
          controls: false,
        ),
        const SizedBox(height: 16),
        panel(
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  badge(watching ? '감시 중' : '감시 준비', blue),
                  const Spacer(),
                  if (demo) badge('데모', Colors.orange),
                ],
              ),
              const SizedBox(height: 16),
              const Text(
                '알림 받을 좌석',
                style: TextStyle(fontWeight: FontWeight.w700),
              ),
              const SizedBox(height: 10),
              Wrap(
                spacing: 8,
                children: [
                  for (final e in {
                    'general': '일반실',
                    'special': '특실',
                    'any': '둘 다',
                  }.entries)
                    ChoiceChip(
                      label: Text(e.value),
                      selected: seat == e.key,
                      onSelected: locked
                          ? null
                          : (_) => setState(() => seat = e.key),
                    ),
                ],
              ),
              const SizedBox(height: 12),
              Row(
                children: [
                  const Expanded(
                    child: Text(
                      '조회 간격',
                      style: TextStyle(fontWeight: FontWeight.w700),
                    ),
                  ),
                  DropdownButton<int>(
                    value: interval,
                    items: [
                      for (final n in [5, 15, 30, 60, 120, 300, 600])
                        DropdownMenuItem(value: n, child: Text('$n초')),
                    ],
                    onChanged: locked
                        ? null
                        : (v) => setState(() => interval = v!),
                  ),
                ],
              ),
              const Text(
                '조회 완료 후 다음 주기를 기다립니다.',
                style: TextStyle(color: muted, fontSize: 12),
              ),
              const SizedBox(height: 20),
              if (watching) ...[
                Text(
                  next == 0 ? '좌석을 확인하고 있어요' : '다음 조회까지 $seconds초',
                  style: const TextStyle(
                    color: blue,
                    fontSize: 22,
                    fontWeight: FontWeight.w700,
                  ),
                ),
                const SizedBox(height: 12),
                Text(
                  state['message'] ?? '',
                  style: const TextStyle(color: muted, height: 1.5),
                ),
                const SizedBox(height: 18),
              ],
              SizedBox(
                width: double.infinity,
                child: FilledButton.icon(
                  onPressed: busy
                      ? null
                      : watching
                      ? () => invoke('stop')
                      : locked
                      ? null
                      : watch,
                  icon: Icon(
                    watching
                        ? Icons.stop_rounded
                        : Icons.notifications_active_outlined,
                  ),
                  label: Text(watching ? '감시 중지' : '선택 열차 감시 시작'),
                ),
              ),
            ],
          ),
        ),
        const SizedBox(height: 16),
        SizedBox(
          width: double.infinity,
          child: OutlinedButton.icon(
            onPressed: busy
                ? null
                : () => invoke('prepareBooking', {
                    ...(watching ? Map<String, dynamic>.from(cfg!) : config()),
                    'target': target,
                  }),
            icon: const Icon(Icons.open_in_new_rounded),
            label: const Text('이 열차 예매 화면 준비'),
          ),
        ),
        const SizedBox(height: 10),
        const Text(
          '접근성 기능을 켜면 날짜·구간을 입력하고 열차·등급을 선택합니다. 어른 1명·일반 좌석 설정에서 사용하세요. 마지막 예약·결제는 직접 진행하며 좌석 확보를 보장하지 않습니다. 화면을 잠그거나 다른 앱으로 이동하면 중지됩니다.',
          style: TextStyle(color: muted, fontSize: 12, height: 1.6),
        ),
        if (state['assistStatus'] != null)
          Padding(
            padding: const EdgeInsets.only(top: 10),
            child: Text(
              state['assistStatus'],
              style: const TextStyle(color: blue),
            ),
          ),
        Wrap(
          spacing: 8,
          children: [
            TextButton(
              onPressed: () => invoke('openBooking'),
              child: const Text('코레일+만 열기'),
            ),
            TextButton(
              onPressed: () => invoke('cancelBooking'),
              child: const Text('화면 준비 중지'),
            ),
          ],
        ),
      ],
      const SizedBox(height: 16),
      panel(
        Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              state['assistEnabled'] == true
                  ? '예매 화면 준비 · 사용 가능'
                  : '예매 화면 준비 · 접근성 설정 필요',
              style: const TextStyle(fontWeight: FontWeight.w700),
            ),
            const SizedBox(height: 8),
            const Text(
              '코레일+ 화면의 글자·버튼과 목록 이미지를 휴대폰 안에서 읽고 열차를 선택합니다. 화면 내용은 파일로 저장하거나 전송하지 않습니다. 알림 또는 준비 버튼을 누를 때만 최대 2분간 실행하며 예약·결제 버튼은 누르지 않습니다.',
              style: TextStyle(color: muted, fontSize: 12, height: 1.6),
            ),
            TextButton(
              onPressed: () => invoke('assistSettings'),
              child: const Text('접근성 설정 열기'),
            ),
          ],
        ),
      ),
      const SizedBox(height: 20),
      panel(
        Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              '화면을 끄기 전에',
              style: TextStyle(fontWeight: FontWeight.w800),
            ),
            const SizedBox(height: 10),
            const Text(
              '알림 권한을 허용하고, 앱 배터리 사용을 제한하지 않도록 설정하세요. 절전 모드·네트워크 상태에 따라 조회가 늦어질 수 있습니다.\n\n한 번에 최대 5시간 50분 감시합니다. Android 실행 한도나 강제 종료로 중단되면 다시 시작해야 합니다.',
              style: TextStyle(color: muted, height: 1.6, fontSize: 13),
            ),
            TextButton(
              onPressed: () => invoke('batterySettings'),
              child: const Text('앱 배터리·알림 설정 열기'),
            ),
          ],
        ),
      ),
    ];
  }

  List<Widget> historyPage() {
    final logs = (state['logs'] as List? ?? []).reversed.toList();
    return [
      heading('알림 기록', '좌석 발견과 조회 상태를 최근 100개까지 보관합니다.'),
      if (logs.isEmpty)
        panel(const Text('아직 기록이 없습니다.', style: TextStyle(color: muted))),
      for (final e in logs)
        Padding(
          padding: const EdgeInsets.only(bottom: 10),
          child: panel(
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Icon(
                  e['message'].toString().contains('발견')
                      ? Icons.notifications_active_rounded
                      : Icons.schedule_rounded,
                  color: blue,
                  size: 20,
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(e['message'], style: const TextStyle(height: 1.5)),
                      const SizedBox(height: 6),
                      Text(
                        DateTime.fromMillisecondsSinceEpoch(
                          e['time'],
                        ).toLocal().toString().substring(0, 19),
                        style: const TextStyle(color: muted, fontSize: 11),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
        ),
    ];
  }

  void help() => showDialog(
    context: context,
    builder: (c) => AlertDialog(
      title: const Text('KTX 좌석 알림'),
      content: const SingleChildScrollView(
        child: Text(
          '1. 날짜·시간을 정하고 열차를 조회하세요.\n2. 열차 카드의 일반실 또는 특실을 선택하세요.\n3. 좌석 감시에서 시작을 누르세요.\n\n화면이 꺼져도 상태 알림과 함께 감시합니다. 절전 정책이나 네트워크에 따라 지연될 수 있습니다. Android 실행 한도에 도달하면 중지합니다.\n\n데모 모드는 두 번째 감시 조회에서 좌석 발견 알림을 보여줍니다. 실제 좌석이 아닙니다.\n\n비공식 조회 도구이며 예매 기능은 없습니다.',
        ),
      ),
      actions: [
        TextButton(onPressed: () => Navigator.pop(c), child: const Text('확인')),
      ],
    ),
  );
}
