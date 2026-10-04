package com.jeongsu.ktx_seat_watch

import java.text.SimpleDateFormat
import java.util.Locale
import java.util.TimeZone

data class BookingTarget(val number: String, val dep: String, val arr: String,
                         val departure: String, val seat: String) {
    val year get() = departure.substring(0, 4).toInt()
    val month get() = departure.substring(5, 7).toInt()
    val day get() = departure.substring(8, 10).toInt()
    val hour get() = departure.substring(11, 13).toInt()
    val dateLabel get() = "${year}년 ${month}월 ${day}일"
    val monthLabel get() = "${year}년 ${month}월"
    val datePrefix get() = "${month}월 ${day}일 ("
    fun validate(now: Long = System.currentTimeMillis()) {
        require(number.matches(Regex("[0-9]{1,5}"))) { "열차 번호가 올바르지 않습니다." }
        require(setOf(dep, arr) == setOf("대전", "서울")) { "현재 자동 준비는 대전↔서울만 지원합니다." }
        require(seat in listOf("general", "special", "any")) { "좌석 등급이 올바르지 않습니다." }
        require(departure.matches(Regex("[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}\\+09:00"))) { "출발 시각이 올바르지 않습니다." }
        val format = SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ssXXX", Locale.US).apply {
            isLenient = false; timeZone = TimeZone.getTimeZone("Asia/Seoul")
        }
        val time = format.parse(departure)?.time ?: error("출발 시각이 올바르지 않습니다.")
        require(time > now) { "출발 시간이 지난 열차입니다. 다시 조회해 주세요." }
        require(time - now <= 32L * 24 * 60 * 60 * 1000) { "32일 이내 열차만 자동 준비할 수 있습니다." }
    }
    fun matchesTitle(label: String): Boolean {
        val match = Regex("^KTX(?:-[가-힣A-Za-z]+)?\\s+([0-9]{1,5})$").matchEntire(label.trim())
        return match?.groupValues?.get(1)?.toIntOrNull() == number.toIntOrNull()
    }
}
