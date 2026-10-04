package com.jeongsu.ktx_seat_watch

/** Match both fields in one visible row; the selection panel is verified again. */
internal object TrainRowText {
    fun matches(words: List<String>, number: String, departureTime: String): Boolean {
        val numberFound = words.any {
            it.trim(' ', '·', '.', ':', '|', '-', '–', '—').toIntOrNull() == number.toIntOrNull()
        }
        val timeFound = words.any { it.replace(" ", "").trim() == departureTime }
        return numberFound && timeFound
    }
}
