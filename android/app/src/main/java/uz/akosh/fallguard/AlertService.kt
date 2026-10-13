package uz.akosh.fallguard

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.media.AudioAttributes
import android.media.RingtoneManager
import android.os.Build
import android.os.Handler
import android.os.IBinder
import android.os.Looper
import androidx.core.app.NotificationCompat
import androidx.core.app.ServiceCompat
import androidx.core.content.ContextCompat
import okhttp3.Call
import okhttp3.Callback
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import okhttp3.Response
import okhttp3.WebSocket
import okhttp3.WebSocketListener
import org.json.JSONObject
import java.io.IOException
import java.util.concurrent.TimeUnit

/**
 * Keeps a WebSocket to the server's /ws while the app is in the background,
 * stores the status history on the phone (also fetching what was missed while
 * offline) and raises a loud, full-screen notification when the room turns red:
 * a fall, or any movement while the home security mode is on.
 */
class AlertService : Service() {

    companion object {
        const val ACTION_ACK = "uz.akosh.fallguard.ACK"
        const val ACTION_ANSWER = "uz.akosh.fallguard.ANSWER"
        const val EXTRA_CALL = "call"
        const val EXTRA_POLICE = "police"
        private const val ID_ESC = 3
        private const val ID_POLICE = 4
        private const val CH_MONITOR = "monitor"
        private const val CH_ALERT = "alerts_v1"
        private const val ID_MONITOR = 1
        private const val ID_ALERT = 2
        private val RED = setOf("fall_suspected", "alert", "intrusion")
        private val ACTIVITY_UZ = mapOf(
            "empty" to "xona bo'sh", "still" to "qimirlamayapti", "walk" to "yuryapti",
            "sit" to "o'tiribdi", "lie" to "yotibdi", "fall" to "yiqildi",
        )

        fun start(context: Context) =
            ContextCompat.startForegroundService(context, Intent(context, AlertService::class.java))

        fun stop(context: Context) {
            context.stopService(Intent(context, AlertService::class.java))
        }
    }

    private val http = OkHttpClient.Builder().pingInterval(15, TimeUnit.SECONDS).build()
    private val main = Handler(Looper.getMainLooper())
    private lateinit var prefs: Prefs
    private lateinit var db: HistoryDb
    private val io = java.util.concurrent.Executors.newSingleThreadExecutor()
    private var lastSaved = 0.0
    private var lastSavedKey = ""
    @Volatile private var socket: WebSocket? = null
    private var server = ""
    private var lastState = ""
    private var lastLine = ""
    private val lastEscKey = mutableMapOf<Boolean, String>()
    private var stopped = false

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        prefs = Prefs(this)
        db = HistoryDb.get(this)
        createChannels()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        val type = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.UPSIDE_DOWN_CAKE)
            ServiceInfo.FOREGROUND_SERVICE_TYPE_SPECIAL_USE else 0
        ServiceCompat.startForeground(this, ID_MONITOR, monitorNotification("Ulanmoqda…"), type)
        if (!prefs.monitoring) {
            stopSelf()
            return START_NOT_STICKY
        }
        if (intent?.action == ACTION_ACK) acknowledge()
        if (intent?.action == ACTION_ANSWER) {
            answer(intent.getBooleanExtra(EXTRA_CALL, false), intent.getBooleanExtra(EXTRA_POLICE, false))
        }
        if (socket == null || server != prefs.server) connect()
        return START_STICKY
    }

    override fun onDestroy() {
        stopped = true
        io.shutdown()
        main.removeCallbacksAndMessages(null)
        socket?.cancel()
        Alarm.stop()
        super.onDestroy()
    }

    private fun connect() {
        socket?.cancel()
        server = prefs.server
        val url = prefs.url("/ws").replaceFirst(Regex("^http"), "ws")
        socket = http.newWebSocket(Request.Builder().url(url).build(), object : WebSocketListener() {
            override fun onOpen(webSocket: WebSocket, response: Response) = backfill()

            override fun onMessage(webSocket: WebSocket, text: String) {
                val json = runCatching { JSONObject(text) }.getOrNull() ?: return
                main.post { onStatus(json) }
            }

            // only the current socket reconnects; a socket replaced by connect() just goes away
            override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) = retry(webSocket)
            override fun onClosed(webSocket: WebSocket, code: Int, reason: String) = retry(webSocket)
        })
    }

    private fun retry(failed: WebSocket) {
        main.post {
            if (stopped || failed !== socket) return@post
            socket = null
            onStatus(JSONObject().put("state", "offline"))
            main.postDelayed({ if (!stopped && socket == null) connect() }, 5000)
        }
    }

    /** Fetch the rows and events the server recorded while this phone was not listening. */
    private fun backfill() = io.execute {
        runCatching {
            val since = db.lastT().takeIf { it > 0 } ?: (System.currentTimeMillis() / 1000.0 - 24 * 3600)
            getJson("/api/history?since=$since&limit=20000")?.let { db.addRows(org.json.JSONArray(it)) }
            fetchEvents()
            db.prune(System.currentTimeMillis() / 1000.0)
        }
    }

    private fun fetchEvents() = getJson("/api/events?limit=200")?.let { db.addEvents(org.json.JSONArray(it)) }

    private fun getJson(path: String): String? =
        http.newCall(Request.Builder().url(prefs.url(path)).build()).execute().use { r ->
            if (r.isSuccessful) r.body?.string() else null
        }

    private fun save(s: JSONObject, state: String, security: String) {
        val now = System.currentTimeMillis() / 1000.0
        val t = s.optDouble("server_time", now).takeIf { !it.isNaN() } ?: now
        val key = "$state/$security"
        if (t - lastSaved < 5 && key == lastSavedKey) return // one row per 5 s unless something changes
        lastSaved = t
        lastSavedKey = key
        io.execute { runCatching { db.addStatus(s, t) } }
    }

    private fun onStatus(s: JSONObject) {
        val security = s.optJSONObject("security")?.optString("state") ?: "off"
        val state = if (security == "intrusion") "intrusion" else s.optString("state")
        save(s, s.optString("state"), security)
        val red = state in RED
        val wasRed = lastState in RED
        if (state != lastState && (red || wasRed)) io.execute { runCatching { fetchEvents() } }
        val line = when {
            state == "intrusion" -> "XAVF: uyda begona harakat!"
            red -> "XAVF: yiqilish!"
            security == "armed" -> "Qo'riqlanmoqda · harakat yo'q"
            security == "arming" -> "Qo'riqlash yoqilmoqda"
            state == "offline" -> "Server bilan aloqa yo'q"
            state == "waiting_for_nodes" || state == "starting" -> "Platalardan signal kutilmoqda"
            else -> "Normal · " + (ACTIVITY_UZ[s.optString("activity")] ?: s.optString("activity"))
        }
        if (line != lastLine) {
            getSystemService(NotificationManager::class.java).notify(ID_MONITOR, monitorNotification(line))
            lastLine = line
        }
        // a stronger alert once the detector escalates from "suspected" to "alert" (person did not get up)
        if (red && (!wasRed || (state == "alert" && lastState != "alert"))) showAlert(state)
        if (!red && wasRed) {
            getSystemService(NotificationManager::class.java).cancel(ID_ALERT)
        }
        s.optJSONObject("escalation")?.let { onEscalation(it, police = false) }
        s.optJSONObject("police")?.let { onEscalation(it, police = true) }
        lastState = state
    }

    private fun showAlert(state: String) {
        // when the app is on screen the page shows the red dialog and plays the alarm itself
        if (MainActivity.visible) return
        val open = PendingIntent.getActivity(
            this, 0, Intent(this, MainActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
        val ack = PendingIntent.getService(
            this, 1, Intent(this, AlertService::class.java).setAction(ACTION_ACK),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
        val text = getString(
            when (state) {
                "intrusion" -> R.string.alert_text_intrusion
                "alert" -> R.string.alert_text_alert
                else -> R.string.alert_text_suspected
            }
        )
        val n = NotificationCompat.Builder(this, CH_ALERT)
            .setSmallIcon(R.drawable.ic_stat)
            .setColor(ContextCompat.getColor(this, R.color.bad))
            .setColorized(true)
            .setContentTitle(getString(if (state == "intrusion") R.string.intrusion_title else R.string.alert_title))
            .setContentText(text)
            .setStyle(NotificationCompat.BigTextStyle().bigText(text))
            .setPriority(NotificationCompat.PRIORITY_MAX)
            .setCategory(NotificationCompat.CATEGORY_ALARM)
            .setContentIntent(open)
            .setFullScreenIntent(open, true)
            .apply { if (state != "intrusion") addAction(0, getString(R.string.ack), ack) }
            .setAutoCancel(true)
            .build()
        n.flags = n.flags or Notification.FLAG_INSISTENT // repeat the sound until someone reacts
        getSystemService(NotificationManager::class.java).notify(ID_ALERT, n)
    }

    /**
     * After a fall (ambulance, 103) or an intrusion in security mode (police, 102): a question with
     * answer buttons, the countdown, or the call itself.
     */
    private fun onEscalation(e: JSONObject, police: Boolean) {
        val state = e.optString("state", "idle")
        val key = "${e.optDouble("started_at")}/$state"
        if (key == lastEscKey[police]) return
        lastEscKey[police] = key
        val nm = getSystemService(NotificationManager::class.java)
        val id = if (police) ID_POLICE else ID_ESC
        if (state !in setOf("asking", "countdown", "called")) {
            nm.cancel(id)
            return
        }
        io.execute { runCatching { fetchEvents() } }
        val number = e.optString("number", if (police) "102" else "103")
        val episode = (if (police) "police-" else "") + e.optDouble("started_at").toString()
        if (MainActivity.visible) { // the page shows the same question and dials by itself
            return
        }
        fun pi(code: Int, i: Intent) = PendingIntent.getService(this, code, i, PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
        fun answerIntent(call: Boolean) = Intent(this, AlertService::class.java).setAction(ACTION_ANSWER)
            .putExtra(EXTRA_CALL, call).putExtra(EXTRA_POLICE, police)
        val base = if (police) 20 else 10 // separate request codes so the two kinds of buttons never mix
        val open = PendingIntent.getActivity(
            this, base, Intent(this, MainActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                .apply { if (state == "called") putExtra(MainActivity.EXTRA_DIAL_NUMBER, number).putExtra(MainActivity.EXTRA_DIAL_KEY, episode) },
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
        val reason = e.optString("reason")
        val (title, text) = when {
            police && state == "asking" -> getString(R.string.police_ask_title) to
                "Qo'riqlash rejimida uyda begona harakat. Politsiya ($number) chaqirilsinmi? O'zingiz kirgan bo'lsangiz \"Kerak emas\"ni bosing."
            police && state == "countdown" -> getString(R.string.police_countdown_title) to
                "$reason. ${e.optInt("cancel_seconds", 30)} soniyada bekor qilinmasa, $number chaqiriladi."
            police -> getString(R.string.police_called_title) to "Qaror: ${e.optString("called_by")}. $number ga qo'ng'iroq qiling." +
                (e.optString("address").takeIf { it.isNotBlank() }?.let { " Manzil: $it" } ?: "")
            state == "asking" -> getString(R.string.esc_ask_title) to "Odam yiqildi va turmayapti: $reason. Tez yordam ($number) chaqirilsinmi?"
            state == "countdown" -> getString(R.string.esc_countdown_title) to
                "$reason. ${e.optInt("cancel_seconds", 30)} soniyada bekor qilinmasa, $number chaqiriladi."
            else -> getString(R.string.esc_called_title) to
                "Qaror: ${e.optString("called_by")}. $number ga qo'ng'iroq qiling." +
                (e.optString("address").takeIf { it.isNotBlank() }?.let { " Manzil: $it" } ?: "")
        }
        val b = NotificationCompat.Builder(this, CH_ALERT)
            .setSmallIcon(R.drawable.ic_stat)
            .setColor(ContextCompat.getColor(this, R.color.bad))
            .setColorized(true)
            .setContentTitle(title)
            .setContentText(text)
            .setStyle(NotificationCompat.BigTextStyle().bigText(text))
            .setPriority(NotificationCompat.PRIORITY_MAX)
            .setCategory(NotificationCompat.CATEGORY_ALARM)
            .setContentIntent(open)
            .setFullScreenIntent(open, true)
        when (state) {
            "asking" -> b.addAction(0, getString(R.string.esc_yes), pi(base + 1, answerIntent(true)))
                .addAction(0, getString(R.string.esc_no), pi(base + 2, answerIntent(false)))
            "countdown" -> b.addAction(0, getString(R.string.esc_now), pi(base + 1, answerIntent(true)))
                .addAction(0, getString(R.string.esc_cancel), pi(base + 2, answerIntent(false)))
            else -> b.addAction(0, getString(R.string.esc_dial) + " $number",
                PendingIntent.getActivity(this, base + 3, Dialer.intent(this, number), PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE))
        }
        val n = b.build()
        n.flags = n.flags or Notification.FLAG_INSISTENT
        nm.cancel(ID_ALERT)
        nm.notify(id, n)
    }

    private fun answer(call: Boolean, police: Boolean) {
        getSystemService(NotificationManager::class.java).cancel(if (police) ID_POLICE else ID_ESC)
        val body = JSONObject().put("call", call).put("who", prefs.name.ifBlank { "Telefon" }).toString()
        val req = Request.Builder().url(prefs.url(if (police) "/api/police" else "/api/escalation"))
            .post(body.toRequestBody("application/json".toMediaType())).build()
        http.newCall(req).enqueue(object : Callback {
            override fun onFailure(call: Call, e: IOException) {}
            override fun onResponse(call: Call, response: Response) = response.close()
        })
    }

    private fun acknowledge() {
        getSystemService(NotificationManager::class.java).cancel(ID_ALERT)
        val req = Request.Builder().url(prefs.url("/api/ack")).post(ByteArray(0).toRequestBody()).build()
        http.newCall(req).enqueue(object : Callback {
            override fun onFailure(call: Call, e: IOException) {}
            override fun onResponse(call: Call, response: Response) = response.close()
        })
    }

    private fun monitorNotification(text: String): Notification {
        val open = PendingIntent.getActivity(
            this, 2, Intent(this, MainActivity::class.java),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
        return NotificationCompat.Builder(this, CH_MONITOR)
            .setSmallIcon(R.drawable.ic_stat)
            .setColor(ContextCompat.getColor(this, R.color.ok))
            .setContentTitle(getString(R.string.monitor_title))
            .setContentText(text)
            .setOngoing(true)
            .setOnlyAlertOnce(true)
            .setContentIntent(open)
            .build()
    }

    private fun createChannels() {
        val nm = getSystemService(NotificationManager::class.java)
        nm.createNotificationChannel(
            NotificationChannel(CH_MONITOR, getString(R.string.channel_monitor), NotificationManager.IMPORTANCE_LOW)
        )
        nm.createNotificationChannel(
            NotificationChannel(CH_ALERT, getString(R.string.channel_alerts), NotificationManager.IMPORTANCE_HIGH).apply {
                enableVibration(true)
                vibrationPattern = longArrayOf(0, 600, 300, 600, 300, 600)
                setBypassDnd(true)
                lockscreenVisibility = Notification.VISIBILITY_PUBLIC
                setSound(
                    RingtoneManager.getDefaultUri(RingtoneManager.TYPE_ALARM),
                    AudioAttributes.Builder().setUsage(AudioAttributes.USAGE_ALARM).build(),
                )
            }
        )
    }
}
