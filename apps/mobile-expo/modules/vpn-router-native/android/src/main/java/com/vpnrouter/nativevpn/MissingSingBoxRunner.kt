package com.vpnrouter.nativevpn

class MissingSingBoxRunner : SingBoxRunner {
    override fun start(configJson: String, tunFd: Int) {
        throw IllegalStateException("sing-box/libbox runtime is not bundled yet")
    }

    override fun stop() = Unit
}
