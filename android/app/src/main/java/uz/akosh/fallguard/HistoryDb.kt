package uz.akosh.fallguard

import android.content.ContentValues
import android.content.Context
import android.database.sqlite.SQLiteDatabase
import android.database.sqlite.SQLiteOpenHelper
import org.json.JSONArray
import org.json.JSONObject

/**
 * Status history and events kept on the phone, so they stay readable when the
 * home server or the network is down. The alert service writes, the page reads
 * through the JS bridge.
 */
class HistoryDb private constructor(context: Context) :
    SQLiteOpenHelper(context.applicationContext, "history.db", null, 1) {

    companion object {
        private const val KEEP_DAYS = 30
        @Volatile private var instance: HistoryDb? = null
        fun get(context: Context): HistoryDb =
            instance ?: synchronized(this) { instance ?: HistoryDb(context).also { instance = it } }

        private val COLS = listOf("t", "state", "activity", "motion", "fall", "x", "y", "breath", "heart", "security")
    }

    override fun onCreate(db: SQLiteDatabase) {
        db.execSQL(
            "CREATE TABLE status (t REAL PRIMARY KEY, state TEXT, activity TEXT, motion REAL, fall REAL, " +
                "x REAL, y REAL, breath REAL, heart REAL, security TEXT)"
        )
        db.execSQL("CREATE TABLE events (t REAL NOT NULL, type TEXT NOT NULL, PRIMARY KEY (t, type))")
    }

    override fun onUpgrade(db: SQLiteDatabase, oldVersion: Int, newVersion: Int) {}

    /** One row from a live status message (the server's /ws JSON). */
    fun addStatus(s: JSONObject, t: Double) {
        val loc = s.optJSONObject("location")
        val vit = s.optJSONObject("vitals")
        val row = JSONObject()
            .put("t", t).put("state", s.optString("state")).put("activity", s.optString("activity"))
            .put("motion", s.optDouble("motion", 0.0))
            .put("fall", s.optJSONObject("probs")?.optDouble("fall", 0.0) ?: 0.0)
            .put("x", loc?.opt("x")).put("y", loc?.opt("y"))
            .put("breath", vit?.opt("breath_bpm")).put("heart", vit?.opt("heart_bpm"))
            .put("security", s.optJSONObject("security")?.optString("state") ?: "off")
        insert(row)
    }

    /** Rows from /api/history (same column names); ``every`` keeps one row in that many. */
    fun addRows(rows: JSONArray, every: Int = 10) {
        writableDatabase.beginTransaction()
        try {
            for (i in 0 until rows.length() step every) insert(rows.getJSONObject(i))
            writableDatabase.setTransactionSuccessful()
        } finally {
            writableDatabase.endTransaction()
        }
    }

    private fun insert(row: JSONObject) {
        val v = ContentValues()
        for (c in COLS) {
            when (val x = row.opt(c)) {
                null, JSONObject.NULL -> v.putNull(c)
                is Number -> v.put(c, x.toDouble())
                else -> v.put(c, x.toString())
            }
        }
        writableDatabase.insertWithOnConflict("status", null, v, SQLiteDatabase.CONFLICT_REPLACE)
    }

    fun addEvents(events: JSONArray) {
        for (i in 0 until events.length()) {
            val e = events.getJSONObject(i)
            val v = ContentValues().apply { put("t", e.getDouble("t")); put("type", e.getString("type")) }
            writableDatabase.insertWithOnConflict("events", null, v, SQLiteDatabase.CONFLICT_IGNORE)
        }
    }

    fun lastT(): Double = scalar("SELECT MAX(t) FROM status")
    fun lastEventT(): Double = scalar("SELECT MAX(t) FROM events")

    private fun scalar(sql: String): Double =
        readableDatabase.rawQuery(sql, null).use { c -> if (c.moveToFirst() && !c.isNull(0)) c.getDouble(0) else 0.0 }

    /** Rows since ``since`` (oldest first), thinned to at most ``maxPoints``. */
    fun historyJson(since: Double, maxPoints: Int): String {
        val out = JSONArray()
        readableDatabase.rawQuery(
            "SELECT ${COLS.joinToString()} FROM status WHERE t >= ? ORDER BY t", arrayOf(since.toString())
        ).use { c ->
            val step = maxOf(1, c.count / maxOf(1, maxPoints))
            var i = 0
            while (c.moveToNext()) {
                if (i++ % step != 0) continue
                val o = JSONObject()
                COLS.forEachIndexed { k, name ->
                    when {
                        c.isNull(k) -> o.put(name, JSONObject.NULL)
                        name in setOf("state", "activity", "security") -> o.put(name, c.getString(k))
                        else -> o.put(name, c.getDouble(k))
                    }
                }
                out.put(o)
            }
        }
        return out.toString()
    }

    fun eventsJson(limit: Int): String {
        val out = JSONArray()
        readableDatabase.rawQuery("SELECT t, type FROM events ORDER BY t DESC LIMIT ?", arrayOf(limit.toString())).use { c ->
            while (c.moveToNext()) out.put(JSONObject().put("t", c.getDouble(0)).put("type", c.getString(1)))
        }
        return out.toString()
    }

    fun prune(now: Double) {
        writableDatabase.delete("status", "t < ?", arrayOf((now - KEEP_DAYS * 86400).toString()))
    }
}
