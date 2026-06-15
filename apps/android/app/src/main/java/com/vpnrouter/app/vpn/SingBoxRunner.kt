package com.vpnrouter.app.vpn

import android.net.VpnService

interface SingBoxRunner {
    fun start(configJson: String)
    fun stop()

    companion object {
        fun create(service: VpnService): SingBoxRunner {
            return ReflectionLibboxRunner.createOrNull(service) ?: MissingSingBoxRunner()
        }
    }
}

class MissingSingBoxRunner : SingBoxRunner {
    override fun start(configJson: String) {
        error("sing-box/libbox runtime is not bundled yet; see docs/oss-decisions.md")
    }

    override fun stop() = Unit
}
