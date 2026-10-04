package com.jeongsu.ktx_seat_watch

import android.content.Context
import android.os.Handler
import android.os.Looper
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import org.json.JSONArray
import org.json.JSONObject
import java.util.concurrent.Executors
import java.util.concurrent.atomic.AtomicBoolean

// State is only mutated on the main thread. Python and HTTP run on a worker.
object WatchState {
    lateinit var context: Context
    val handler = Handler(Looper.getMainLooper())
    private val worker = Executors.newSingleThreadExecutor()
    private var cancel = AtomicBoolean(false)
    var phase = "idle"
        private set
    private var state = JSONObject()
    fun init(ctx: Context) {
        if (::context.isInitialized) return
        context = ctx.applicationContext
        val saved = context.getSharedPreferences("watch", 0).getString("state", null)
        state = try { JSONObject(saved ?: "{}") } catch (_: Exception) { JSONObject() }
        val interrupted = state.optString("phase") in listOf("watching", "searching")
        state.put("phase", "idle").put("nextPoll", 0)
        if (!state.has("trains")) state.put("trains", JSONArray())
        if (!state.has("logs")) state.put("logs", JSONArray())
        if (interrupted) log("앱이 종료되어 감시가 중단되었습니다. 열차를 다시 조회해 시작하세요.")
    }
    fun snapshot(): String = state.toString()
    fun put(key: String, value: Any) { state.put(key, value); persist() }
    private fun persist() {
        context.getSharedPreferences("watch", 0).edit().putString("state", state.toString()).apply()
    }
    fun log(message: String) {
        state.put("message", message)
        val logs = state.optJSONArray("logs") ?: JSONArray()
        logs.put(JSONObject().put("time", System.currentTimeMillis()).put("message", message))
        while (logs.length() > 100) logs.remove(0)
        state.put("logs", logs)
        persist()
    }
    fun stop(message: String) {
        cancel.set(true)
        phase = "idle"
        state.put("phase", phase).put("nextPoll", 0)
        log(message)
    }
    fun begin(config: JSONObject, monitoring: Boolean) {
        cancel.set(true)
        cancel = AtomicBoolean(false)
        phase = if (monitoring) "watching" else "searching"
        state.put("phase", phase).put("config", config).put("nextPoll", 0).remove("current")
        if (!monitoring) state.put("trains", JSONArray()).put("lastUpdated", 0)
        log(if (monitoring) "선택한 열차의 좌석을 감시합니다." else "열차를 조회하고 있습니다.")
    }
    fun query(config: JSONObject, done: (JSONObject) -> Unit) {
        val token = cancel
        val payload = config.toString()
        worker.execute {
            val response = try {
                if (!Python.isStarted()) Python.start(AndroidPlatform(context))
                JSONObject(Python.getInstance().getModule("mobile_api").callAttr("query", payload, token).toString())
            } catch (e: Exception) { JSONObject().put("error", e.message ?: "조회 오류").put("fatal", true) }
            handler.post {
                if (!token.get() && !response.optBoolean("cancelled")) done(response)
            }
        }
    }
    fun search(config: JSONObject) {
        begin(config, false)
        query(config) { response ->
            if (response.has("error")) stop("조회 실패: ${response.optString("error")}")
            else {
                put("trains", response.getJSONArray("trains"))
                put("lastUpdated", System.currentTimeMillis())
                put("searchUpdated", System.currentTimeMillis())
                stop("${response.getJSONArray("trains").length()}개 열차를 찾았습니다. 좌석 등급을 선택하세요.")
            }
        }
    }
}
