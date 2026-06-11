package com.vpnrouter.nativevpn

import android.net.VpnService
import expo.modules.kotlin.modules.Module
import expo.modules.kotlin.modules.ModuleDefinition

class VpnRouterNativeModule : Module() {
    override fun definition() = ModuleDefinition {
        Name("VpnRouterNative")

        AsyncFunction("start") { configJson: String ->
            val context = appContext.reactContext
                ?: throw IllegalStateException("React context is unavailable")
            val activity = appContext.currentActivity

            if (activity != null && VpnService.prepare(activity) != null) {
                throw IllegalStateException("Android VPN permission must be granted before starting the tunnel")
            }

            VpnRouterService.start(context, configJson)
        }

        AsyncFunction("stop") {
            val context = appContext.reactContext
                ?: throw IllegalStateException("React context is unavailable")
            VpnRouterService.stop(context)
        }

        AsyncFunction("status") {
            VpnRouterStatus.current.value
        }
    }
}
