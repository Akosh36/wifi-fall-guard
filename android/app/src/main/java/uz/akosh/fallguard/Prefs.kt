package uz.akosh.fallguard

import android.content.Context

/** Server address and demo flag, shared by the page (via the JS bridge) and the alert service. */
class Prefs(context: Context) {
    private val sp = context.getSharedPreferences("fallguard", Context.MODE_PRIVATE)

    var server: String
        get() = sp.getString("server", "") ?: ""
        set(v) = sp.edit().putString("server", v).apply()

    var token: String
        get() = sp.getString("token", "") ?: ""
        set(v) = sp.edit().putString("token", v).apply()

    var demo: Boolean
        get() = sp.getBoolean("demo", false)
        set(v) = sp.edit().putBoolean("demo", v).apply()

    /** Name shown on the server when this phone answers "call an ambulance?". */
    var name: String
        get() = sp.getString("name", "") ?: ""
        set(v) = sp.edit().putString("name", v).apply()

    /** Dial the ambulance from this phone as soon as the server decides to call. */
    var autoDial: Boolean
        get() = sp.getBoolean("auto_dial", false)
        set(v) = sp.edit().putBoolean("auto_dial", v).apply()

    /** Episode already dialled for, so one fall never makes two calls. */
    var dialedKey: String
        get() = sp.getString("dialed", "") ?: ""
        set(v) = sp.edit().putString("dialed", v).apply()

    /** Server URL for ``path`` with the API token, if one is set. */
    fun url(path: String): String {
        val sep = if ('?' in path) "&" else "?"
        return server + path + if (token.isBlank()) "" else sep + "token=" + java.net.URLEncoder.encode(token, "UTF-8")
    }

    /** The service only watches a real server; demo mode lives entirely in the page. */
    val monitoring: Boolean get() = server.isNotBlank() && !demo
}
