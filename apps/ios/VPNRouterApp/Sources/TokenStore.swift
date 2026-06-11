import Foundation
import Security

protocol TokenStore {
    func readAccessToken() throws -> String?
    func saveAccessToken(_ token: String) throws
    func clearAccessToken() throws
}

final class KeychainTokenStore: TokenStore {
    private let service = "com.vpnrouter.app.auth"
    private let account = "access_token"

    func readAccessToken() throws -> String? {
        var query = baseQuery()
        query[kSecReturnData as String] = true
        query[kSecMatchLimit as String] = kSecMatchLimitOne
        var item: CFTypeRef?
        let status = SecItemCopyMatching(query as CFDictionary, &item)
        if status == errSecItemNotFound { return nil }
        guard status == errSecSuccess, let data = item as? Data else { throw KeychainError(status) }
        return String(data: data, encoding: .utf8)
    }

    func saveAccessToken(_ token: String) throws {
        try clearAccessToken()
        var item = baseQuery()
        item[kSecValueData as String] = Data(token.utf8)
        item[kSecAttrAccessible as String] = kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly
        let status = SecItemAdd(item as CFDictionary, nil)
        guard status == errSecSuccess else { throw KeychainError(status) }
    }

    func clearAccessToken() throws {
        let status = SecItemDelete(baseQuery() as CFDictionary)
        guard status == errSecSuccess || status == errSecItemNotFound else { throw KeychainError(status) }
    }

    private func baseQuery() -> [String: Any] {
        [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account
        ]
    }
}

struct KeychainError: Error {
    let status: OSStatus

    init(_ status: OSStatus) {
        self.status = status
    }
}

