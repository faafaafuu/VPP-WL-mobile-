package com.vpnrouter.app.config

import android.content.Context
import com.vpnrouter.app.storage.EncryptedPreferencesFactory

class EncryptedConfigStore(context: Context) : ConfigStore {
    private val preferences = EncryptedPreferencesFactory.create(context, PREFS_NAME)

    override fun readLastKnownGoodConfig(): StoredConfig? {
        val configJson = preferences.getString(KEY_CONFIG_JSON, null) ?: return null
        val savedAt = preferences.getLong(KEY_SAVED_AT, 0L)
        if (savedAt <= 0L) return null
        return StoredConfig(configJson = configJson, savedAtEpochMillis = savedAt)
    }

    override fun saveLastKnownGoodConfig(configJson: String, savedAtEpochMillis: Long) {
        require(configJson.isNotBlank()) { "configJson must not be blank" }
        require(savedAtEpochMillis > 0L) { "savedAtEpochMillis must be positive" }
        preferences.edit()
            .putString(KEY_CONFIG_JSON, configJson)
            .putLong(KEY_SAVED_AT, savedAtEpochMillis)
            .apply()
    }

    override fun clearLastKnownGoodConfig() {
        preferences.edit()
            .remove(KEY_CONFIG_JSON)
            .remove(KEY_SAVED_AT)
            .apply()
    }

    private companion object {
        const val PREFS_NAME = "vpn_router_config"
        const val KEY_CONFIG_JSON = "last_known_good_config_json"
        const val KEY_SAVED_AT = "last_known_good_config_saved_at"
    }
}

