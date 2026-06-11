package com.vpnrouter.app.auth

interface TokenStore {
    fun readAccessToken(): String?
    fun saveAccessToken(token: String)
    fun clearAccessToken()
}

