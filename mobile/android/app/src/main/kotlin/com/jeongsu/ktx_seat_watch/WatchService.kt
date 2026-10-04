package com.jeongsu.ktx_seat_watch

import android.app.*
import android.content.Intent
import android.content.pm.ServiceInfo
import android.os.*
import org.json.JSONObject

class WatchService : Service() {
    private val handler = Handler(Looper.getMainLooper())
    private var wakeLock: PowerManager.WakeLock? = null
    private var active = false
    private var previous = false
    private var round = 0
    private lateinit var config: JSONObject
    private val poll = Runnable { poll() }
    private val limit = Runnable { finish("연속 감시 시간(5시간 50분)이 끝났습니다. 앱에서 다시 확인하세요.", true) }
    private val manager get() = getSystemService(NotificationManager::class.java)
    override fun onBind(intent: Intent?) = null
    override fun onCreate() {
        super.onCreate()
        WatchState.init(applicationContext)
        if (Build.VERSION.SDK_INT >= 26) {
            manager.createNotificationChannel(NotificationChannel("watch", "감시 상태", NotificationManager.IMPORTANCE_LOW))
            val alert = NotificationChannel("seats", "좌석 발견 및 감시 종료", NotificationManager.IMPORTANCE_HIGH)
            alert.enableVibration(true)
            manager.createNotificationChannel(alert)
        }
    }
    private fun notification(text: String, alert: Boolean, booking: Boolean = false): Notification {
        val launch = PendingIntent.getActivity(this, 0, Intent(this, MainActivity::class.java), PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
        val destination = if (booking) PendingIntent.getActivity(this, 4, BookingLink.intent(this, config), PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT) else launch
        val stop = PendingIntent.getService(this, 1, Intent(this, WatchService::class.java).setAction("STOP"), PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
        val b = if (Build.VERSION.SDK_INT >= 26) Notification.Builder(this, if (alert) "seats" else "watch") else Notification.Builder(this)
        b.setSmallIcon(R.drawable.ic_notification).setContentTitle(if (alert) "KTX 좌석 알림" else "KTX 좌석 감시 중")
            .setContentText(text).setStyle(Notification.BigTextStyle().bigText(text)).setContentIntent(destination)
            .setOngoing(!alert).setAutoCancel(alert).setShowWhen(alert)
        if (alert) b.setDefaults(Notification.DEFAULT_ALL) else b.addAction(0, "감시 중지", stop)
        if (booking) b.addAction(0, "코레일+ 예매 준비", destination)
        return b.build()
    }
    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (intent?.action == "STOP") { finish("알림에서 감시를 중지했습니다.", false); return START_NOT_STICKY }
        if (active) return START_NOT_STICKY
        val raw = intent?.getStringExtra("config") ?: run { stopSelf(); return START_NOT_STICKY }
        try {
            config = JSONObject(raw)
            val target = config.getJSONObject("target")
            val message = "${target.getString("dep")} → ${target.getString("arr")} · KTX ${target.getString("number")}" + if (config.optBoolean("demo")) " · 데모" else ""
            if (Build.VERSION.SDK_INT >= 29) startForeground(1, notification(message, false), ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC)
            else startForeground(1, notification(message, false))
            active = true
            wakeLock = (getSystemService(POWER_SERVICE) as PowerManager).newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "KTX:SeatWatch").also { it.acquire(21000_000L) }
            WatchState.begin(config, true)
            handler.postDelayed(limit, 21000_000L)
            poll()
        } catch (e: Exception) { finish("감시를 시작하지 못했습니다: ${e.message}", true) }
        return START_NOT_STICKY
    }
    private fun poll() {
        if (!active || WatchState.phase != "watching") { stopSelf(); return }
        WatchState.put("nextPoll", 0)
        config.put("round", round)
        WatchState.query(config) { response ->
            if (!active) return@query
            if (response.optBoolean("expired")) { finish("선택한 열차의 출발 시간이 지나 감시를 종료했습니다.", true); return@query }
            if (response.has("error")) {
                val error = "조회 실패: ${response.optString("error")}"
                if (response.optBoolean("fatal")) { finish(error, true); return@query }
                WatchState.log("$error · 다음 주기에 재시도합니다.")
            } else {
                val trains = response.getJSONArray("trains")
                WatchState.put("lastUpdated", System.currentTimeMillis())
                if (trains.length() > 0) {
                    val train = trains.getJSONObject(0)
                    WatchState.put("current", train)
                    val seat = config.optString("seat", "general")
                    val available = (seat != "special" && train.optString("general") == "11") || (seat != "general" && train.optString("special") == "11")
                    if (available && !previous) {
                        val prefix = if (config.optBoolean("demo")) "[데모] " else ""
                        val grade = if (seat == "special") "특실" else if (seat == "any") "일반실/특실" else "일반실"
                        val message = "${prefix}KTX ${train.getString("number")} $grade 좌석 발견! ${train.getString("dep")} → ${train.getString("arr")} · ${train.getString("departure").take(16).replace('T', ' ')} · 알림을 눌러 코레일에서 예매하세요."
                        WatchState.log(message)
                        manager.notify(2, notification(message, true, booking = true))
                    } else WatchState.log("선택 열차 확인 완료 · ${if (available) "좌석 있음" else "매진"}")
                    previous = available
                } else WatchState.log("선택 열차가 응답에 없습니다. 다음 주기에 다시 확인합니다.")
                round++
            }
            val interval = config.optInt("interval", 60).coerceIn(5, 600) * 1000L
            WatchState.put("nextPoll", System.currentTimeMillis() + interval)
            handler.postDelayed(poll, interval)
        }
    }
    private fun finish(message: String, notify: Boolean) {
        active = false
        WatchState.stop(message)
        if (notify) manager.notify(3, notification(message, true))
        stopForeground(STOP_FOREGROUND_REMOVE)
        stopSelf()
    }
    override fun onTimeout(startId: Int, fgsType: Int) {
        finish("Android 백그라운드 실행 한도에 도달해 감시를 종료했습니다.", true)
    }
    override fun onDestroy() {
        handler.removeCallbacksAndMessages(null)
        if (wakeLock?.isHeld == true) wakeLock?.release()
        if (active && WatchState.phase == "watching") WatchState.stop("감시 서비스가 종료되었습니다.")
        active = false
        super.onDestroy()
    }
}
