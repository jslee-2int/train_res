package com.jeongsu.ktx_seat_watch

import android.app.Activity
import android.os.Bundle
import android.widget.Toast
import org.json.JSONObject

// Notification taps enter an Activity directly, including when Flutter is closed.
class BookingActivity : Activity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val config = intent.getStringExtra("config")
        if (BookingAssistService.enabled(this) && config != null) {
            try { BookingAssistService.start(this, JSONObject(config)) }
            catch (e: Exception) {
                Toast.makeText(this, e.message ?: "예매 화면 준비를 시작하지 못했습니다.", Toast.LENGTH_LONG).show()
            }
        } else if (!BookingLink.open(this)) {
            Toast.makeText(this, "코레일+를 열지 못했습니다. 앱 설치 및 사용 가능 여부를 확인해 주세요.", Toast.LENGTH_LONG).show()
        }
        finish()
    }
}
