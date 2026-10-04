package com.jeongsu.ktx_seat_watch

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import android.provider.Settings
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel
import org.json.JSONObject

class MainActivity : FlutterActivity() {
    private var permissionResult: MethodChannel.Result? = null
    override fun configureFlutterEngine(engine: FlutterEngine) {
        super.configureFlutterEngine(engine)
        WatchState.init(applicationContext)
        MethodChannel(engine.dartExecutor.binaryMessenger, "ktx/watch").setMethodCallHandler { call, result ->
            try {
                when (call.method) {
                    "prepareBooking" -> {
                        BookingAssistService.start(this, JSONObject(call.arguments as String))
                        result.success(null)
                    }
                    "assistSettings" -> {
                        BookingAssistService.settings(this)
                        result.success(null)
                    }
                    "cancelBooking" -> {
                        BookingAssistService.cancel()
                        result.success(null)
                    }
                    "openBooking" -> {
                        if (BookingLink.open(this)) {
                            result.success(null)
                        } else {
                            result.error("booking", "코레일+를 열지 못했습니다. 앱 설치 및 사용 가능 여부를 확인해 주세요.", null)
                        }
                    }
                    "snapshot" -> result.success(JSONObject(WatchState.snapshot())
                        .put("assistEnabled", BookingAssistService.enabled(this)).toString())
                    "search" -> {
                        check(WatchState.phase == "idle") { "진행 중인 작업을 먼저 중지하세요." }
                        WatchState.search(JSONObject(call.arguments as String))
                        result.success(null)
                    }
                    "watch" -> {
                        check(WatchState.phase == "idle") { "진행 중인 작업을 먼저 중지하세요." }
                        val cfg = JSONObject(call.arguments as String)
                        check(cfg.has("target")) { "감시할 열차를 선택하세요." }
                        val intent = Intent(this, WatchService::class.java).putExtra("config", cfg.toString())
                        if (Build.VERSION.SDK_INT >= 26) startForegroundService(intent) else startService(intent)
                        result.success(null)
                    }
                    "stop" -> {
                        WatchState.stop("작업을 중지했습니다.")
                        stopService(Intent(this, WatchService::class.java))
                        result.success(null)
                    }
                    "notifications" -> {
                        if (Build.VERSION.SDK_INT >= 33 && checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
                            if (permissionResult != null) result.error("busy", "알림 권한을 확인 중입니다.", null)
                            else {
                                permissionResult = result
                                requestPermissions(arrayOf(Manifest.permission.POST_NOTIFICATIONS), 41)
                            }
                        } else result.success(true)
                    }
                    "batterySettings" -> {
                        startActivity(Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS,
                            android.net.Uri.parse("package:$packageName")))
                        result.success(null)
                    }
                    else -> result.notImplemented()
                }
            } catch (e: Exception) { result.error("native", e.message, null) }
        }
    }
    override fun onRequestPermissionsResult(code: Int, permissions: Array<out String>, grants: IntArray) {
        super.onRequestPermissionsResult(code, permissions, grants)
        if (code == 41) {
            permissionResult?.success(grants.isNotEmpty() && grants[0] == PackageManager.PERMISSION_GRANTED)
            permissionResult = null
        }
    }
}
