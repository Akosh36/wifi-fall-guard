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

    /** Server URL for ``path`` with the API token, if one is set. */
    fun url(path: String): String {
        val sep = if ('?' in path) "&" else "?"
        return server + path + if (token.isBlank()) "" else sep + "token=" + java.net.URLEncoder.encode(token, "UTF-8")
    }

    /** The service only watches a real server; demo mode lives entirely in the page. */
    val monitoring: Boolean get() = server.isNotBlank() && !demo
}
