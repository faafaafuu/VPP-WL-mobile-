import Foundation
import Security

struct StoredConfig {
    let data: Data
    let savedAt: Date
}

protocol ConfigStore {
    func readLastKnownGoodConfig() throws -> StoredConfig?
    func saveLastKnownGoodConfig(_ data: Data, savedAt: Date) throws
    func clearLastKnownGoodConfig() throws
}

final class KeychainConfigStore: ConfigStore {
    private let service = "com.vpnrouter.app.config"
    private let account = "last_known_good_config"

    func readLastKnownGoodConfig() throws -> StoredConfig? {
        var query = baseQuery()
        query[kSecReturnData as String] = true
        query[kSecMatchLimit as String] = kSecMatchLimitOne
        var item: CFTypeRef?
        let status = SecItemCopyMatching(query as CFDictionary, &item)
        if status == errSecItemNotFound { return nil }
        guard status == errSecSuccess, let data = item as? Data else { throw KeychainError(status) }
        return StoredConfig(data: data, savedAt: Date())
    }

    func saveLastKnownGoodConfig(_ data: Data, savedAt: Date) throws {
        try clearLastKnownGoodConfig()
        var item = baseQuery()
        item[kSecValueData as String] = data
        item[kSecAttrAccessible as String] = kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly
        let status = SecItemAdd(item as CFDictionary, nil)
        guard status == errSecSuccess else { throw KeychainError(status) }
    }

    func clearLastKnownGoodConfig() throws {
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

