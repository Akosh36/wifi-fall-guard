package uz.akosh.fallguard

import android.Manifest
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri

/** Calls the ambulance number: directly when the owner allowed calls, otherwise opens the dialer with it filled in. */
object Dialer {
    fun intent(context: Context, number: String): Intent {
        val canCall = context.checkSelfPermission(Manifest.permission.CALL_PHONE) == PackageManager.PERMISSION_GRANTED
        return Intent(if (canCall) Intent.ACTION_CALL else Intent.ACTION_DIAL, Uri.parse("tel:$number"))
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
    }

    fun dial(context: Context, number: String) {
        runCatching { context.startActivity(intent(context, number)) }
    }

    /** Dials once per fall episode (``key``), and only when automatic dialling is switched on. */
    fun autoDial(context: Context, key: String, number: String): Boolean {
        val prefs = Prefs(context)
        if (!prefs.autoDial || key.isBlank() || prefs.dialedKey == key) return false
        prefs.dialedKey = key
        dial(context, number)
        return true
    }
}
