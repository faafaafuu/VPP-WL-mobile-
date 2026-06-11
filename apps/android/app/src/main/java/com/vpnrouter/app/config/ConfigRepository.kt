package com.vpnrouter.app.config

import com.vpnrouter.app.api.BackendApiClient
import com.vpnrouter.app.api.BackendApiException
import com.vpnrouter.app.api.isConfigFallbackAllowed
import com.vpnrouter.app.auth.TokenStore
import java.io.IOException

class ConfigRepository(
    private val apiClient: BackendApiClient,
    private val tokenStore: TokenStore,
    private val configStore: ConfigStore,
    private val clock: () -> Long = { System.currentTimeMillis() },
) {
    fun loadConfig(): ConfigLoadResult {
        val token = tokenStore.readAccessToken() ?: return ConfigLoadResult.AuthRequired

        return try {
            val configJson = apiClient.fetchConfig(token)
            configStore.saveLastKnownGoodConfig(configJson, clock())
            ConfigLoadResult.Fresh(configJson)
        } catch (error: BackendApiException) {
            if (error.isConfigFallbackAllowed()) {
                fallbackConfig() ?: throw error
            } else {
                throw error
            }
        } catch (error: IOException) {
            fallbackConfig() ?: throw error
        }
    }

    private fun fallbackConfig(): ConfigLoadResult.Cached? {
        val cached = configStore.readLastKnownGoodConfig() ?: return null
        return ConfigLoadResult.Cached(cached.configJson, cached.savedAtEpochMillis)
    }
}

sealed interface ConfigLoadResult {
    data class Fresh(val configJson: String) : ConfigLoadResult
    data class Cached(val configJson: String, val savedAtEpochMillis: Long) : ConfigLoadResult
    data object AuthRequired : ConfigLoadResult
}

