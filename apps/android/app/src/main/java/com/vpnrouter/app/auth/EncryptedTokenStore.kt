package com.vpnrouter.app.auth

import android.content.Context
import com.vpnrouter.app.storage.EncryptedPreferencesFactory

class EncryptedTokenStore(context: Context) : TokenStore {
    private val preferences = EncryptedPreferencesFactory.create(context, PREFS_NAME)

    override fun readAccessToken(): String? {
        return preferences.getString(KEY_ACCESS_TOKEN, null)
    }

    override fun saveAccessToken(token: String) {
        require(token.isNotBlank()) { "token must not be blank" }
        preferences.edit()
            .putString(KEY_ACCESS_TOKEN, token)
            .apply()
    }

    override fun clearAccessToken() {
        preferences.edit()
            .remove(KEY_ACCESS_TOKEN)
            .apply()
    }

    private companion object {
        const val PREFS_NAME = "vpn_router_auth"
        const val KEY_ACCESS_TOKEN = "access_token"
    }
}

