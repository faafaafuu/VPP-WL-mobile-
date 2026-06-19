package com.vpnrouter.app

import android.app.Activity
import android.content.Intent
import android.graphics.Color
import android.net.VpnService
import android.os.Bundle
import android.widget.Button
import android.widget.LinearLayout
import android.widget.TextView
import com.vpnrouter.app.api.BackendApiClient
import com.vpnrouter.app.auth.EncryptedTokenStore
import com.vpnrouter.app.config.ConfigLoadResult
import com.vpnrouter.app.config.ConfigRepository
import com.vpnrouter.app.config.EncryptedConfigStore
import com.vpnrouter.app.vpn.VpnRouterService

class MainActivity : Activity() {
    private lateinit var status: TextView
    private lateinit var configRepository: ConfigRepository

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        configRepository = ConfigRepository(
            apiClient = BackendApiClient(DEFAULT_API_BASE_URL),
            tokenStore = EncryptedTokenStore(applicationContext),
            configStore = EncryptedConfigStore(applicationContext),
        )

        val title = TextView(this).apply {
            text = "VPN Router"
            textSize = 28f
            setTextColor(Color.rgb(17, 24, 39))
        }
        status = TextView(this).apply {
            text = "Ready"
            textSize = 18f
            setTextColor(Color.rgb(75, 85, 99))
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
                setBackgroundColor(Color.WHITE)
                setPadding(dp(24), dp(32), dp(24), dp(24))
                layoutParams = LinearLayout.LayoutParams(
                    LinearLayout.LayoutParams.MATCH_PARENT,
                    LinearLayout.LayoutParams.MATCH_PARENT,
                )
                addView(title)
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
        status.text = "Loading VPN config"
        Thread {
            runCatching { configRepository.loadConfig() }
                .onSuccess { result ->
                    when (result) {
                        is ConfigLoadResult.Fresh -> startVpnWithConfig(result.configJson, "Connected with fresh config")
                        is ConfigLoadResult.Cached -> startVpnWithConfig(result.configJson, "Connected with cached config")
                        ConfigLoadResult.AuthRequired -> showStatus("Subscription activation required")
                    }
                }
                .onFailure { error ->
                    showStatus(error.message ?: "Unable to load VPN config")
                }
        }.start()
    }

    private fun startVpnWithConfig(configJson: String, message: String) {
        startService(VpnRouterService.connectIntent(this, configJson))
        showStatus(message)
    }

    private fun showStatus(message: String) {
        runOnUiThread {
            status.text = message
        }
    }

    private fun dp(value: Int): Int {
        return (value * resources.displayMetrics.density).toInt()
    }

    private companion object {
        const val VPN_PERMISSION_REQUEST = 1001
        const val DEFAULT_API_BASE_URL = "http://10.0.2.2:8080"
    }
}
