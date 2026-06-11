package com.vpnrouter.app.config

data class StoredConfig(
    val configJson: String,
    val savedAtEpochMillis: Long,
)

interface ConfigStore {
    fun readLastKnownGoodConfig(): StoredConfig?
    fun saveLastKnownGoodConfig(configJson: String, savedAtEpochMillis: Long)
    fun clearLastKnownGoodConfig()
}

