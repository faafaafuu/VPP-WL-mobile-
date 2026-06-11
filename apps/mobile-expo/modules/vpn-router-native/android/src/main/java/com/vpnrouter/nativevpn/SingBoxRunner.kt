package com.vpnrouter.nativevpn

interface SingBoxRunner {
    fun start(configJson: String, tunFd: Int)
    fun stop()
}
