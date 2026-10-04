package com.jeongsu.ktx_seat_watch

import android.content.Intent
import android.content.Context
import android.content.ActivityNotFoundException
import android.net.Uri
import org.json.JSONObject

object BookingLink {
    private const val PACKAGE = "com.korail.talk"

    // Resolve when tapped, so installing/removing the app after an alert works.
    fun intent(context: Context, config: JSONObject): Intent = Intent(context, BookingActivity::class.java)
        .putExtra("config", config.toString())

    fun open(context: Context): Boolean {
        val app = context.packageManager.getLaunchIntentForPackage(PACKAGE)
        val destinations = listOfNotNull(
            app,
            Intent(Intent.ACTION_VIEW, Uri.parse("market://details?id=$PACKAGE"))
                .setPackage("com.android.vending"),
            Intent(Intent.ACTION_VIEW, Uri.parse("https://play.google.com/store/apps/details?id=$PACKAGE"))
                .addCategory(Intent.CATEGORY_BROWSABLE)
        )
        for (destination in destinations) {
            try {
                context.startActivity(destination)
                return true
            } catch (_: ActivityNotFoundException) {
                // Try the installation page if the app cannot be launched.
            } catch (_: SecurityException) {
                // A disabled/restricted app may not be launchable.
            }
        }
        return false
    }
}
