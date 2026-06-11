package com.vpnrouter.nativevpn

enum class VpnStatus(val value: String) {
    DISCONNECTED("disconnected"),
    CONNECTING("connecting"),
    CONNECTED("connected"),
    ERROR("error")
}

object VpnRouterStatus {
    @Volatile
    var current: VpnStatus = VpnStatus.DISCONNECTED
}
