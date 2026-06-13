package com.vpnrouter.app.vpn

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.net.VpnService
import android.os.ParcelFileDescriptor
import com.vpnrouter.app.MainActivity

class VpnRouterService : VpnService() {
    private var tun: ParcelFileDescriptor? = null
    private val runner: SingBoxRunner = MissingSingBoxRunner()

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        when (intent?.action) {
            ACTION_CONNECT -> connect(intent.getStringExtra(EXTRA_CONFIG_JSON))
            ACTION_DISCONNECT -> disconnect()
        }
        return START_STICKY
    }

    override fun onDestroy() {
        disconnect()
        super.onDestroy()
    }

    private fun connect(configJson: String?) {
        if (tun != null) return
        if (configJson.isNullOrBlank()) {
            stopSelf()
            return
        }

        startForeground(NOTIFICATION_ID, notification())
        tun = Builder()
            .setSession("VPN Router")
            .addAddress("172.19.0.2", 30)
            .addRoute("0.0.0.0", 0)
            .establish()

        val fd = tun?.fd ?: return
        runCatching { runner.start(configJson, fd) }
            .onFailure { disconnect() }
    }

    private fun disconnect() {
        runner.stop()
        tun?.close()
        tun = null
        stopForeground(STOP_FOREGROUND_REMOVE)
        stopSelf()
    }

    private fun notification(): Notification {
        val notificationManager = getSystemService(NotificationManager::class.java)
        val channel = NotificationChannel(
            NOTIFICATION_CHANNEL_ID,
            "VPN Router",
            NotificationManager.IMPORTANCE_LOW,
        ).apply {
            description = "VPN tunnel status"
        }
        notificationManager.createNotificationChannel(channel)

        val openAppIntent = PendingIntent.getActivity(
            this,
            0,
            Intent(this, MainActivity::class.java),
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT,
        )
        return Notification.Builder(this, NOTIFICATION_CHANNEL_ID)
            .setContentTitle("VPN Router")
            .setContentText("VPN tunnel is running")
            .setSmallIcon(android.R.drawable.ic_dialog_info)
            .setContentIntent(openAppIntent)
            .setOngoing(true)
            .build()
    }

    companion object {
        const val ACTION_CONNECT = "com.vpnrouter.app.CONNECT"
        const val ACTION_DISCONNECT = "com.vpnrouter.app.DISCONNECT"
        const val EXTRA_CONFIG_JSON = "com.vpnrouter.app.CONFIG_JSON"
        private const val NOTIFICATION_CHANNEL_ID = "vpn_router_status"
        private const val NOTIFICATION_ID = 1001

        fun connectIntent(context: Context, configJson: String): Intent {
            return Intent(context, VpnRouterService::class.java)
                .setAction(ACTION_CONNECT)
                .putExtra(EXTRA_CONFIG_JSON, configJson)
        }
    }
}
