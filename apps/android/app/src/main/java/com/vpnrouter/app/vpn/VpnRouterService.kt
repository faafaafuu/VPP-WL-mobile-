package com.vpnrouter.app.vpn

import android.content.Intent
import android.net.VpnService
import android.os.ParcelFileDescriptor

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
        stopSelf()
    }

    companion object {
        const val ACTION_CONNECT = "com.vpnrouter.app.CONNECT"
        const val ACTION_DISCONNECT = "com.vpnrouter.app.DISCONNECT"
        const val EXTRA_CONFIG_JSON = "com.vpnrouter.app.CONFIG_JSON"

        fun connectIntent(context: android.content.Context, configJson: String): Intent {
            return Intent(context, VpnRouterService::class.java)
                .setAction(ACTION_CONNECT)
                .putExtra(EXTRA_CONFIG_JSON, configJson)
        }
    }
}
