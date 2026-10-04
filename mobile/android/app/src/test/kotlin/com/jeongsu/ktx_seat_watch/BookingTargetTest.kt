package com.jeongsu.ktx_seat_watch

import org.junit.Assert.*
import org.junit.Test
import java.text.SimpleDateFormat

class BookingTargetTest {
    private val target = BookingTarget("006", "대전", "서울", "2026-10-04T07:10:00+09:00", "general")
    private val now = SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ssXXX").parse("2026-10-03T12:00:00+09:00")!!.time
    @Test fun validatesFutureTripAndNormalizesNumber() {
        target.validate(now)
        assertTrue(target.matchesTitle("KTX 6"))
        assertTrue(target.matchesTitle("KTX-산천 006"))
        assertFalse(target.matchesTitle("KTX 106"))
        assertFalse(target.matchesTitle("ITX 006"))
        assertFalse(target.matchesTitle("KTX 006 바로 예매"))
        assertEquals("2026년 10월 4일", target.dateLabel)
    }
    @Test fun rejectsExpiredWrongRouteAndMalformedTargets() {
        assertThrows(IllegalArgumentException::class.java) { target.validate(now + 3 * 86400000L) }
        assertThrows(IllegalArgumentException::class.java) { target.copy(dep = "서대전").validate(now) }
        assertThrows(IllegalArgumentException::class.java) { target.copy(number = "").validate(now) }
        assertThrows(IllegalArgumentException::class.java) { target.copy(seat = "invalid").validate(now) }
        assertThrows(IllegalArgumentException::class.java) { target.copy(departure = "2026-10-04").validate(now) }
    }
}
