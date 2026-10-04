package com.jeongsu.ktx_seat_watch

import org.junit.Assert.*
import org.junit.Test

class TrainRowTextTest {
    @Test fun requiresNumberAndDepartureInSameRow() {
        assertTrue(TrainRowText.matches(listOf("KTX", "006", "07:10", "08:25"), "6", "07:10"))
        assertTrue(TrainRowText.matches(listOf("006·", "07:10"), "006", "07:10"))
        assertTrue(TrainRowText.matches(listOf("KTX", "006-", "07:10"), "006", "07:10"))
        assertFalse(TrainRowText.matches(listOf("202", "07:10"), "006", "07:10"))
        assertFalse(TrainRowText.matches(listOf("006", "08:10"), "006", "07:10"))
        assertFalse(TrainRowText.matches(listOf("1006", "07:10"), "006", "07:10"))
        assertFalse(TrainRowText.matches(listOf("00600", "07:10"), "006", "07:10"))
    }
}
