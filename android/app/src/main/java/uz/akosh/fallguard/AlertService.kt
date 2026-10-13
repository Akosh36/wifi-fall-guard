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
 * Keeps a WebSocket to the server's /ws while the app is in the background and
 * raises a loud, full-screen notification when the room turns red (fall).
 */
class AlertService : Service() {

    companion object {
        const val ACTION_ACK = "uz.akosh.fallguard.ACK"
        private const val CH_MONITOR = "monitor"
        private const val CH_ALERT = "alerts_v1"
        private const val ID_MONITOR = 1
        private const val ID_ALERT = 2
        private val RED = setOf("fall_suspected", "alert")
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
    @Volatile private var socket: WebSocket? = null
    private var server = ""
    private var lastState = ""
    private var lastLine = ""
    private var stopped = false

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        prefs = Prefs(this)
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
        if (socket == null || server != prefs.server) connect()
        return START_STICKY
    }

    override fun onDestroy() {
        stopped = true
        main.removeCallbacksAndMessages(null)
        socket?.cancel()
        Alarm.stop()
        super.onDestroy()
    }

    private fun connect() {
        socket?.cancel()
        server = prefs.server
        val url = server.replaceFirst(Regex("^http"), "ws") + "/ws"
        socket = http.newWebSocket(Request.Builder().url(url).build(), object : WebSocketListener() {
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

    private fun onStatus(s: JSONObject) {
        val state = s.optString("state")
        val red = state in RED
        val wasRed = lastState in RED
        val line = when {
            red -> "XAVF: yiqilish!"
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
        val text = getString(if (state == "alert") R.string.alert_text_alert else R.string.alert_text_suspected)
        val n = NotificationCompat.Builder(this, CH_ALERT)
            .setSmallIcon(R.drawable.ic_stat)
            .setColor(ContextCompat.getColor(this, R.color.bad))
            .setColorized(true)
            .setContentTitle(getString(R.string.alert_title))
            .setContentText(text)
            .setStyle(NotificationCompat.BigTextStyle().bigText(text))
            .setPriority(NotificationCompat.PRIORITY_MAX)
            .setCategory(NotificationCompat.CATEGORY_ALARM)
            .setContentIntent(open)
            .setFullScreenIntent(open, true)
            .addAction(0, getString(R.string.ack), ack)
            .setAutoCancel(true)
            .build()
        n.flags = n.flags or Notification.FLAG_INSISTENT // repeat the sound until someone reacts
        getSystemService(NotificationManager::class.java).notify(ID_ALERT, n)
    }

    private fun acknowledge() {
        getSystemService(NotificationManager::class.java).cancel(ID_ALERT)
        val req = Request.Builder().url("${prefs.server}/api/ack").post(ByteArray(0).toRequestBody()).build()
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
