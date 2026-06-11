package com.vpnrouter.app

import android.app.Activity
import android.content.Intent
import android.net.VpnService
import android.os.Bundle
import android.widget.Button
import android.widget.LinearLayout
import android.widget.TextView
import com.vpnrouter.app.vpn.VpnRouterService

class MainActivity : Activity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        val status = TextView(this).apply {
            text = "Ready"
            textSize = 18f
        }
        val connect = Button(this).apply {
            text = "Connect"
            setOnClickListener {
                val prepareIntent = VpnService.prepare(this@MainActivity)
                if (prepareIntent != null) {
                    startActivityForResult(prepareIntent, VPN_PERMISSION_REQUEST)
                } else {
                    startVpnService()
                }
            }
        }

        setContentView(
            LinearLayout(this).apply {
                orientation = LinearLayout.VERTICAL
                setPadding(32, 32, 32, 32)
                addView(status)
                addView(connect)
            }
        )
    }

    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        super.onActivityResult(requestCode, resultCode, data)
        if (requestCode == VPN_PERMISSION_REQUEST && resultCode == RESULT_OK) {
            startVpnService()
        }
    }

    private fun startVpnService() {
        startService(Intent(this, VpnRouterService::class.java).setAction(VpnRouterService.ACTION_CONNECT))
    }

    private companion object {
        const val VPN_PERMISSION_REQUEST = 1001
    }
}

