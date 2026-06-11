package com.vpnrouter.app.vpn

import android.content.Intent
import android.net.VpnService
import android.os.ParcelFileDescriptor

class VpnRouterService : VpnService() {
    private var tun: ParcelFileDescriptor? = null
    private val runner: SingBoxRunner = MissingSingBoxRunner()

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        when (intent?.action) {
            ACTION_CONNECT -> connect()
            ACTION_DISCONNECT -> disconnect()
        }
        return START_STICKY
    }

    override fun onDestroy() {
        disconnect()
        super.onDestroy()
    }

    private fun connect() {
        if (tun != null) return
        tun = Builder()
            .setSession("VPN Router")
            .addAddress("172.19.0.2", 30)
            .addRoute("0.0.0.0", 0)
            .establish()

        // The backend-provided sing-box config and libbox runner will be wired here
        // after the runtime distribution/license decision is made.
        val fd = tun?.fd ?: return
        runCatching { runner.start("{}", fd) }
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
    }
}

