package com.jeongsu.ktx_seat_watch

import android.accessibilityservice.AccessibilityService
import android.accessibilityservice.AccessibilityServiceInfo
import android.accessibilityservice.GestureDescription
import android.app.KeyguardManager
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.graphics.Rect
import android.graphics.Path
import android.graphics.Bitmap
import android.os.Build
import android.view.Display
import com.google.mlkit.vision.common.InputImage
import com.google.mlkit.vision.text.TextRecognition
import com.google.mlkit.vision.text.latin.TextRecognizerOptions
import android.os.Handler
import android.os.Looper
import android.provider.Settings
import android.view.accessibility.AccessibilityEvent
import android.view.accessibility.AccessibilityManager
import android.view.accessibility.AccessibilityNodeInfo
import android.widget.Toast
import org.json.JSONObject

class BookingAssistService : AccessibilityService() {
    companion object {
        private var instance: BookingAssistService? = null
        fun enabled(context: Context): Boolean {
            val manager = context.getSystemService(Context.ACCESSIBILITY_SERVICE) as AccessibilityManager
            return manager.getEnabledAccessibilityServiceList(AccessibilityServiceInfo.FEEDBACK_ALL_MASK)
                .any { ComponentName.unflattenFromString(it.id) == ComponentName(context, BookingAssistService::class.java) }
        }
        fun settings(context: Context) {
            context.startActivity(Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS))
        }
        fun start(context: Context, cfg: JSONObject) {
            check(enabled(context) && instance != null) { "접근성 설정에서 ‘KTX 예매 화면 준비’를 켠 뒤 다시 눌러 주세요." }
            check(!(context.getSystemService(Context.KEYGUARD_SERVICE) as KeyguardManager).isKeyguardLocked) { "휴대폰 잠금을 풀고 다시 눌러 주세요." }
            check(!cfg.optBoolean("demo")) { "데모 열차는 자동 준비할 수 없습니다. 실제 열차를 조회해 주세요." }
            val t = cfg.getJSONObject("target")
            val target = BookingTarget(t.getString("number"), t.getString("dep"), t.getString("arr"),
                t.getString("departure"), cfg.optString("seat", "general"))
            target.validate()
            val launch = context.packageManager.getLaunchIntentForPackage("com.korail.talk")
            check(launch != null) { "코레일+를 먼저 설치해 주세요." }
            instance!!.begin(target)
            try { context.startActivity(launch) }
            catch (e: Exception) { instance?.finish("코레일+ 실행 실패"); throw e }
        }
        fun cancel() { instance?.finish("예매 화면 준비를 중지했습니다.") }
    }

    private val handler = Handler(Looper.getMainLooper())
    private var target: BookingTarget? = null
    private var phase = "home"
    private var deadline = 0L
    private var phaseSince = 0L
    private var steps = 0
    private var pages = 0
    private var generation = 0
    private var readingRows = false
    private var nextActionAt = 0L
    private var startedAt = 0L
    private val recognizer by lazy { TextRecognition.getClient(TextRecognizerOptions.DEFAULT_OPTIONS) }
    private var selectedDate = false
    private var selectedHour = false
    private var resultsVerified = false
    private val tick = Runnable { runStep() }
    override fun onServiceConnected() { instance = this; WatchState.init(applicationContext) }
    override fun onAccessibilityEvent(event: AccessibilityEvent?) { /* One serialized timer owns all actions. */ }
    override fun onInterrupt() { finish("접근성 기능이 중단되어 자동 준비를 멈췄습니다.") }
    override fun onDestroy() { finish("접근성 서비스가 종료되었습니다."); instance = null; super.onDestroy() }

    private fun begin(t: BookingTarget) {
        handler.removeCallbacksAndMessages(null)
        generation++; readingRows = false; nextActionAt = 0
        target = t; phase = "home"; steps = 0; pages = 0
        startedAt = System.currentTimeMillis()
        selectedDate = false; selectedHour = false; resultsVerified = false
        deadline = System.currentTimeMillis() + 120_000; phaseSince = System.currentTimeMillis()
        status("KTX ${t.number} 예매 화면 준비 중 · 예약 버튼은 직접 눌러 주세요.")
        handler.postDelayed(tick, 600)
    }
    private fun status(message: String) { WatchState.put("assistStatus", message) }
    private fun finish(message: String) {
        if (target == null) return
        target = null; generation++; readingRows = false; handler.removeCallbacksAndMessages(null)
        android.util.Log.i("KtxBookingAssist", "finished elapsedMs=${System.currentTimeMillis() - startedAt}")
        status(message); WatchState.log(message)
        Toast.makeText(this, message, Toast.LENGTH_LONG).show()
    }
    private fun transition(next: String) {
        phase = next; phaseSince = System.currentTimeMillis()
        android.util.Log.i("KtxBookingAssist", "phase=$next")
    }
    private fun nodes(root: AccessibilityNodeInfo): List<AccessibilityNodeInfo> {
        val out = ArrayList<AccessibilityNodeInfo>()
        fun visit(n: AccessibilityNodeInfo, depth: Int) {
            if (depth > 40 || out.size > 1800) return
            if (n.isVisibleToUser) out.add(n)
            for (i in 0 until n.childCount) n.getChild(i)?.let { visit(it, depth + 1) }
        }
        visit(root, 0); return out
    }
    private fun label(n: AccessibilityNodeInfo) = (n.contentDescription ?: n.text)?.toString()?.trim().orEmpty()
    private fun clickable(node: AccessibilityNodeInfo): AccessibilityNodeInfo? {
        var n: AccessibilityNodeInfo? = node
        repeat(5) {
            val current = n ?: return null
            if (current.packageName?.toString() != "com.korail.talk") return null
            if (current.isClickable && current.isEnabled) return current
            n = current.parent
        }
        return null
    }
    private fun click(n: AccessibilityNodeInfo?): Boolean = n != null && clickable(n)?.performAction(AccessibilityNodeInfo.ACTION_CLICK) == true
    private fun rect(n: AccessibilityNodeInfo) = Rect().also { n.getBoundsInScreen(it) }
    private fun scrollRows(list: AccessibilityNodeInfo, sheetTop: Int): Boolean {
        val bounds = rect(list)
        val bottom = minOf(bounds.bottom, sheetTop)
        val height = bottom - bounds.top
        if (height < 200) return false
        // Overlap pages; a full-page scroll could skip rows hidden by the selection panel.
        val path = Path().apply {
            moveTo(bounds.centerX().toFloat(), bounds.top + height * .85f)
            lineTo(bounds.centerX().toFloat(), bounds.top + height * .60f)
        }
        return dispatchGesture(GestureDescription.Builder()
            .addStroke(GestureDescription.StrokeDescription(path, 0, 250)).build(), null, null)
    }
    private fun findVisibleTrain(t: BookingTarget, list: AccessibilityNodeInfo,
                                 rows: List<AccessibilityNodeInfo>, sheetTop: Int) {
        if (Build.VERSION.SDK_INT < 30) {
            finish("이 휴대폰에서는 화면의 열차 번호를 읽을 수 없습니다. 목록에서 직접 선택해 주세요."); return
        }
        if (readingRows || rows.isEmpty()) return
        val token = generation
        val rowBounds = rows.map { rect(it) }
        val cropBounds = rect(list).apply { bottom = minOf(bottom, sheetTop) }
        readingRows = true
        fun current() = token == generation && target == t && phase == "rows" &&
            rootInActiveWindow?.packageName?.toString() == "com.korail.talk" &&
            !(getSystemService(KEYGUARD_SERVICE) as KeyguardManager).isKeyguardLocked
        fun failed() {
            if (token != generation) return
            readingRows = false
            finish("목록의 글자를 읽지 못했습니다. 코레일+에서 열차를 직접 선택해 주세요.")
        }
        takeScreenshot(Display.DEFAULT_DISPLAY, mainExecutor, object : TakeScreenshotCallback {
            override fun onFailure(errorCode: Int) { failed() }
            override fun onSuccess(result: ScreenshotResult) {
                val hardware = result.hardwareBuffer
                val wrapped = Bitmap.wrapHardwareBuffer(hardware, result.colorSpace)
                val bitmap = wrapped?.copy(Bitmap.Config.ARGB_8888, false)
                wrapped?.recycle(); hardware.close()
                if (bitmap == null) { failed(); return }
                if (!current()) { bitmap.recycle(); if (token == generation) readingRows = false; return }
                cropBounds.intersect(0, 0, bitmap.width, bitmap.height)
                val cropped = Bitmap.createBitmap(bitmap, cropBounds.left, cropBounds.top, cropBounds.width(), cropBounds.height())
                if (cropped !== bitmap) bitmap.recycle()
                recognizer.process(InputImage.fromBitmap(cropped, 0))
                    .addOnSuccessListener { text ->
                        if (!current()) return@addOnSuccessListener
                        // Discard stale coordinates if a user or animation moved the list.
                        val fresh = rootInActiveWindow?.let { nodes(it) }.orEmpty()
                        val elements = text.textBlocks.flatMap { it.lines }.flatMap { it.elements }
                        val match = rowBounds.firstOrNull { row ->
                            val words = elements.filter { element -> element.boundingBox?.let {
                                row.contains(it.centerX() + cropBounds.left, it.centerY() + cropBounds.top)
                            } == true }.map { it.text }
                            TrainRowText.matches(words, t.number, t.departure.substring(11, 16))
                        }
                        if (match != null) {
                            val row = fresh.firstOrNull { it.className?.toString() == "android.widget.Button" &&
                                it.isClickable && label(it).isEmpty() && rect(it) == match }
                            if (row != null && click(row)) {
                                android.util.Log.i("KtxBookingAssist", "target row clicked directly")
                                nextActionAt = System.currentTimeMillis() + 600
                            }
                        } else if (pages++ < 18) {
                            if (!scrollRows(list, sheetTop)) failed()
                            nextActionAt = System.currentTimeMillis() + 750
                        } else finish("목록에서 열차 번호와 출발 시각을 찾지 못했습니다. 직접 확인해 주세요.")
                    }
                    .addOnFailureListener { failed() }
                    .addOnCompleteListener { cropped.recycle(); if (token == generation) readingRows = false }
            }
        })
    }
    private fun runStep() {
        val t = target ?: return
        try {
            if (System.currentTimeMillis() > deadline || steps++ > 400) { finish("자동 준비 시간이 초과되었습니다. 코레일+에서 직접 확인해 주세요."); return }
            if ((getSystemService(KEYGUARD_SERVICE) as KeyguardManager).isKeyguardLocked) { finish("화면이 잠겨 자동 준비를 중지했습니다."); return }
            if (System.currentTimeMillis() < nextActionAt || readingRows) { handler.postDelayed(tick, 200); return }
            val root = rootInActiveWindow
            if (root?.packageName?.toString() != "com.korail.talk") {
                if (System.currentTimeMillis() - startedAt > 5000) { finish("다른 화면으로 이동하여 자동 준비를 중지했습니다."); return }
            } else {
                val all = nodes(root)
                fun exact(s: String) = all.firstOrNull { label(it) == s }
                fun prefix(s: String) = all.firstOrNull { label(it).startsWith(s) }
                // Only this specific informational dialog is acknowledged. Login,
                // terms, errors, purchase confirmation and all other dialogs stop us.
                if (all.any { label(it) in setOf(
                    "KTX-산천 2개를 연결해 운행하는 열차입니다. 반드시 열차 번호와 호차를 확인 후 승차해 주세요.",
                    "조회한 도착역과 인접한 수서역에 도착하는 열차입니다."
                ) }) {
                    click(exact("확인"))
                } else if (phase == "home") {
                    if (prefix("출발역 ") != null && prefix("도착역 ") != null) {
                        if (prefix("출발역 ${t.dep} 선택됨") == null) {
                            if (click(prefix("출발역 "))) transition("dep")
                        } else if (prefix("도착역 ${t.arr} 선택됨") == null) {
                            if (click(prefix("도착역 "))) transition("arr")
                        } else if (click(prefix("가는날,"))) transition("date")
                    } else if (all.any { Regex("^.+ 출발 .+ 도착$").matches(label(it)) } && exact("수정") != null) {
                        click(exact("이전"))
                    } else if (exact("홈") != null) click(exact("홈"))
                } else if (phase == "dep" || phase == "arr") {
                    val station = if (phase == "dep") t.dep else t.arr
                    if (exact(if (phase == "dep") "출발역 선택" else "도착역 선택") != null) {
                        val choice = all.firstOrNull { label(it) == station || label(it) == "$station 가까운 역" || label(it) == "$station 선택" }
                        if (click(choice)) transition("home")
                    }
                } else if (phase == "date" && exact("가는날 선택") != null) {
                    val month = all.firstOrNull { Regex("[0-9]{4}년 [0-9]{1,2}월").matches(label(it)) }
                    if (month != null && label(month) != t.monthLabel) {
                        val values = Regex("[0-9]+").findAll(label(month)).map { it.value.toInt() }.toList()
                        click(exact(if (values[0] * 12 + values[1] < t.year * 12 + t.month) "다음달" else "이전달"))
                    } else if (!selectedDate) {
                        if (click(prefix(t.datePrefix))) selectedDate = true
                    } else if (!selectedHour) {
                        val hour = exact("${t.hour}시")
                        if (hour != null && rect(hour).width() > 20 && click(hour)) selectedHour = true
                        else {
                            val hours = all.filter { Regex("[0-9]{1,2}시").matches(label(it)) }
                            val scroll = all.firstOrNull { it.isScrollable && hours.any { h -> rect(it).contains(rect(h)) } }
                            val first = hours.mapNotNull { label(it).removeSuffix("시").toIntOrNull() }.minOrNull()
                            scroll?.performAction(if (first != null && t.hour < first) AccessibilityNodeInfo.ACTION_SCROLL_BACKWARD else AccessibilityNodeInfo.ACTION_SCROLL_FORWARD)
                        }
                    } else if (all.any { label(it).startsWith(t.dateLabel) } && exact("${t.hour}시 이후") != null) {
                        if (click(exact("선택 완료"))) transition("search")
                    }
                } else if (phase == "search") {
                    val summary = prefix("가는날,")?.let { label(it) }.orEmpty()
                    if (prefix("출발역 ${t.dep} 선택됨") != null && prefix("도착역 ${t.arr} 선택됨") != null &&
                        summary.contains(t.dateLabel) && summary.contains("${t.hour}시 이후")) {
                        // Leave passenger choices visible and require the supported one-adult setting.
                        if (prefix("인원, 어른 1명,") == null || prefix("좌석, 일반 좌석,") == null) {
                            finish("인원은 어른 1명·일반 좌석으로 설정한 뒤 다시 준비해 주세요."); return
                        }
                        if (click(exact("열차 조회"))) transition("rows")
                    }
                } else if (phase == "rows") {
                    val routeOk = all.any { label(it) == "${t.dep} 출발 ${t.arr} 도착" }
                    val dateOk = all.any { label(it).startsWith(t.dateLabel) && label(it).contains("%02d:00시 이후".format(t.hour)) }
                    // The date/filter header collapses when the list scrolls. Verify
                    // it before the first selection, then retain that verified query.
                    if (routeOk && dateOk) resultsVerified = true
                    val visibleDate = all.firstOrNull { Regex("^[0-9]{4}년 .*시 이후$").matches(label(it)) }
                    if (resultsVerified && visibleDate != null && !dateOk) {
                        finish("조회 날짜가 변경되어 자동 준비를 중지했습니다."); return
                    }
                    if (routeOk && resultsVerified && exact("수정") != null) {
                        val title = all.firstOrNull { t.matchesTitle(label(it)) }
                        if (title != null && exact("바로 예매") != null) {
                            val general = exact("일반실")?.let { clickable(it) }
                            val grade = if (t.seat == "special" || (t.seat == "any" && general == null)) "특실" else "일반실"
                            val option = exact(grade)?.let { clickable(it) }
                            if (option?.isChecked == true) {
                                if (clickable(exact("바로 예매")!!) != null) {
                                    finish("KTX ${t.number} $grade 준비 완료. 열차·날짜를 확인하고 ‘바로 예매’를 직접 눌러 주세요."); return
                                }
                            } else if (option != null) click(option)
                        } else {
                            // Read visible numbers and times locally, then open only the target row.
                            val list = all.firstOrNull { it.isScrollable && rect(it).height() > 300 }
                            val sheetTop = exact("운행 정보")?.let { rect(it).top } ?: Int.MAX_VALUE
                            val rows = all.filter { it.className?.toString() == "android.widget.Button" && it.isClickable &&
                                label(it).isEmpty() && list != null && rect(list).contains(rect(it)) && rect(it).bottom < sheetTop }
                                .sortedBy { rect(it).top }
                            if (list != null) findVisibleTrain(t, list, rows, sheetTop)
                        }
                    }
                }
                if (System.currentTimeMillis() - phaseSince > 35_000 && phase != "rows") {
                    finish("예상하지 못한 화면입니다. 로그인·안내창을 직접 확인한 뒤 다시 준비해 주세요."); return
                }
            }
        } catch (_: Exception) { finish("화면이 변경되어 자동 준비를 중지했습니다. 다시 시도해 주세요."); return }
        if (target != null) handler.postDelayed(tick, 400)
    }
}
