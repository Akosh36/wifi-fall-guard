package uz.akosh.fallguard

import android.content.Context

/** Server address and demo flag, shared by the page (via the JS bridge) and the alert service. */
class Prefs(context: Context) {
    private val sp = context.getSharedPreferences("fallguard", Context.MODE_PRIVATE)

    var server: String
        get() = sp.getString("server", "") ?: ""
        set(v) = sp.edit().putString("server", v).apply()

    var demo: Boolean
        get() = sp.getBoolean("demo", false)
        set(v) = sp.edit().putBoolean("demo", v).apply()

    /** The service only watches a real server; demo mode lives entirely in the page. */
    val monitoring: Boolean get() = server.isNotBlank() && !demo
}
