package com.vpnrouter.nativevpn

import android.content.Context
import android.content.Intent
import android.net.VpnService
import android.os.ParcelFileDescriptor

class VpnRouterService : VpnService() {
    private var tun: ParcelFileDescriptor? = null
    private val runner: SingBoxRunner = MissingSingBoxRunner()

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        when (intent?.action) {
            ACTION_CONNECT -> connect(intent.getStringExtra(EXTRA_CONFIG_JSON) ?: "{}")
            ACTION_DISCONNECT -> disconnect()
        }
        return START_STICKY
    }

    override fun onDestroy() {
        disconnect()
        super.onDestroy()
    }

    private fun connect(configJson: String) {
        if (tun != null) {
            VpnRouterStatus.current = VpnStatus.CONNECTED
            return
        }

        VpnRouterStatus.current = VpnStatus.CONNECTING
        tun = Builder()
            .setSession("VPN Router")
            .addAddress("172.19.0.2", 30)
            .addRoute("0.0.0.0", 0)
            .establish()

        val fd = tun?.fd
        if (fd == null) {
            VpnRouterStatus.current = VpnStatus.ERROR
            stopSelf()
            return
        }

        runCatching { runner.start(configJson, fd) }
            .onSuccess { VpnRouterStatus.current = VpnStatus.CONNECTED }
            .onFailure { VpnRouterStatus.current = VpnStatus.ERROR }
    }

    private fun disconnect() {
        runCatching { runner.stop() }
        tun?.close()
        tun = null
        VpnRouterStatus.current = VpnStatus.DISCONNECTED
        stopSelf()
    }

    companion object {
        private const val ACTION_CONNECT = "com.vpnrouter.nativevpn.CONNECT"
        private const val ACTION_DISCONNECT = "com.vpnrouter.nativevpn.DISCONNECT"
        private const val EXTRA_CONFIG_JSON = "com.vpnrouter.nativevpn.CONFIG_JSON"

        fun start(context: Context, configJson: String) {
            context.startService(
                Intent(context, VpnRouterService::class.java)
                    .setAction(ACTION_CONNECT)
                    .putExtra(EXTRA_CONFIG_JSON, configJson)
            )
        }

        fun stop(context: Context) {
            context.startService(Intent(context, VpnRouterService::class.java).setAction(ACTION_DISCONNECT))
        }
    }
}
