package com.vpnrouter.app.api

import java.net.HttpURLConnection
import java.net.URL

class BackendApiClient(
    private val baseUrl: String,
) {
    fun fetchConfig(accessToken: String): String {
        val connection = openConnection("/api/config")
        connection.setRequestProperty("Authorization", "Bearer $accessToken")
        connection.requestMethod = "GET"
        return readJson(connection)
    }

    fun submitReceipt(requestJson: String): String {
        val connection = openConnection("/api/auth/receipt")
        connection.requestMethod = "POST"
        connection.doOutput = true
        connection.outputStream.use { stream ->
            stream.write(requestJson.toByteArray(Charsets.UTF_8))
        }
        return readJson(connection)
    }

    private fun openConnection(path: String): HttpURLConnection {
        return (URL(baseUrl.trimEnd('/') + path).openConnection() as HttpURLConnection).apply {
            connectTimeout = 10_000
            readTimeout = 10_000
            setRequestProperty("Content-Type", "application/json")
            setRequestProperty("Accept", "application/json")
        }
    }

    private fun readJson(connection: HttpURLConnection): String {
        val status = connection.responseCode
        val stream = if (status in 200..299) connection.inputStream else connection.errorStream
        val body = stream?.bufferedReader(Charsets.UTF_8)?.use { it.readText() }.orEmpty()
        if (status !in 200..299) {
            throw BackendApiException(status, body)
        }
        return body
    }
}

class BackendApiException(
    val statusCode: Int,
    responseBody: String,
) : RuntimeException("Backend request failed: $statusCode $responseBody")

