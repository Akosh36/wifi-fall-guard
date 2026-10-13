package uz.akosh.fallguard

import android.Manifest
import android.annotation.SuppressLint
import android.app.Activity
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.view.View
import android.view.WindowInsets
import android.webkit.WebChromeClient
import android.widget.LinearLayout
import android.webkit.JavascriptInterface
import android.webkit.WebResourceRequest
import android.webkit.WebResourceResponse
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.webkit.WebViewAssetLoader

/**
 * Full-screen WebView with the live 3D room page (bundled from wfg/server/static/app).
 * The page talks to the server itself; this class adds the native bits: settings storage,
 * alarm sound / vibration and the background alert service.
 */
class MainActivity : Activity() {

    companion object {
        @Volatile var visible = false
        // served over http so the page may open ws:// and http:// connections to the home server
        private const val START_URL = "http://appassets.androidplatform.net/assets/index.html"
    }

    private lateinit var web: WebView
    private lateinit var statusSpacer: View
    private lateinit var prefs: Prefs

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        prefs = Prefs(this)
        val assets = WebViewAssetLoader.Builder()
            .setHttpAllowed(true)
            .addPathHandler("/assets/", WebViewAssetLoader.AssetsPathHandler(this))
            .build()

        web = WebView(this).apply {
            settings.javaScriptEnabled = true
            settings.domStorageEnabled = true
            settings.mediaPlaybackRequiresUserGesture = false
            settings.mixedContentMode = WebSettings.MIXED_CONTENT_ALWAYS_ALLOW
            setBackgroundColor(getColor(R.color.bg))
            addJavascriptInterface(Bridge(), "WFG")
            webChromeClient = WebChromeClient() // lets the page use alert() / confirm()
            webViewClient = object : WebViewClient() {
                override fun shouldInterceptRequest(view: WebView, request: WebResourceRequest): WebResourceResponse? =
                    assets.shouldInterceptRequest(request.url)
            }
        }
        // Android 15 draws apps edge-to-edge: keep the page between the status bar (clock, network,
        // battery) and the navigation bar, with spacers in their place. The top one takes the page's
        // header colour (green / red) through the bridge.
        statusSpacer = View(this).apply { setBackgroundColor(getColor(R.color.ok)) }
        val navSpacer = View(this).apply { setBackgroundColor(getColor(R.color.bg)) }
        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setBackgroundColor(getColor(R.color.bg))
            addView(statusSpacer, LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, 0))
            addView(web, LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, 0, 1f))
            addView(navSpacer, LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, 0))
        }
        root.setOnApplyWindowInsetsListener { v, insets ->
            val bars = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
                insets.getInsets(WindowInsets.Type.systemBars() or WindowInsets.Type.displayCutout())
                    .let { intArrayOf(it.left, it.top, it.right, it.bottom) }
            } else {
                @Suppress("DEPRECATION")
                intArrayOf(insets.systemWindowInsetLeft, insets.systemWindowInsetTop,
                    insets.systemWindowInsetRight, insets.systemWindowInsetBottom)
            }
            v.setPadding(bars[0], 0, bars[2], 0)
            statusSpacer.layoutParams = statusSpacer.layoutParams.apply { height = bars[1] }
            navSpacer.layoutParams = navSpacer.layoutParams.apply { height = bars[3] }
            insets
        }
        setContentView(root)
        if (savedInstanceState == null) web.loadUrl(START_URL) else web.restoreState(savedInstanceState)

        if (Build.VERSION.SDK_INT >= 33 &&
            checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED
        ) {
            requestPermissions(arrayOf(Manifest.permission.POST_NOTIFICATIONS), 1)
        }
        if (prefs.monitoring) AlertService.start(this)
    }

    override fun onResume() {
        super.onResume()
        visible = true
        web.onResume()
        web.evaluateJavascript("window.wfgResume && wfgResume()", null) // restart the alarm if still red
    }

    override fun onPause() {
        visible = false
        web.onPause()
        Alarm.stop() // background alerts are the service's job
        super.onPause()
    }

    override fun onSaveInstanceState(outState: Bundle) {
        super.onSaveInstanceState(outState)
        web.saveState(outState)
    }

    override fun onDestroy() {
        web.destroy()
        super.onDestroy()
    }

    /** Exposed to the page as `window.WFG`. */
    inner class Bridge {
        @JavascriptInterface fun getServer(): String = prefs.server
        @JavascriptInterface fun getDemo(): Boolean = prefs.demo
        @JavascriptInterface fun getToken(): String = prefs.token

        /** History stored on the phone by the alert service, readable while offline. */
        @JavascriptInterface
        fun history(since: Double, maxPoints: Int): String = HistoryDb.get(this@MainActivity).historyJson(since, maxPoints)

        @JavascriptInterface
        fun events(limit: Int): String = HistoryDb.get(this@MainActivity).eventsJson(limit)

        @JavascriptInterface
        fun setConfig(server: String, demo: Boolean, token: String) {
            prefs.server = server
            prefs.demo = demo
            prefs.token = token
            runOnUiThread {
                if (prefs.monitoring) AlertService.start(this@MainActivity) else AlertService.stop(this@MainActivity)
            }
        }

        /** Colour of the strip behind the status bar, so it continues the page header. */
        @JavascriptInterface
        fun setBarColor(color: String) {
            runCatching { android.graphics.Color.parseColor(color) }.onSuccess { c ->
                runOnUiThread { statusSpacer.setBackgroundColor(c) }
            }
        }

        @JavascriptInterface
        fun alarm(on: Boolean) {
            runOnUiThread { if (on && visible) Alarm.start(this@MainActivity) else Alarm.stop() }
        }
    }
}
