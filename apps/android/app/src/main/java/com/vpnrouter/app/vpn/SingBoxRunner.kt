package com.vpnrouter.app.vpn

interface SingBoxRunner {
    fun start(configJson: String, tunFileDescriptor: Int)
    fun stop()
}

class MissingSingBoxRunner : SingBoxRunner {
    override fun start(configJson: String, tunFileDescriptor: Int) {
        error("sing-box/libbox runtime is not bundled yet; see docs/oss-decisions.md")
    }

    override fun stop() = Unit
}

