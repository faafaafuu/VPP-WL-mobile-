import Foundation

enum ConfigLoadResult {
    case fresh(Data)
    case cached(Data, Date)
    case authRequired
}

final class ConfigRepository {
    private let apiClient: ApiClient
    private let tokenStore: TokenStore
    private let configStore: ConfigStore

    init(apiClient: ApiClient, tokenStore: TokenStore, configStore: ConfigStore) {
        self.apiClient = apiClient
        self.tokenStore = tokenStore
        self.configStore = configStore
    }

    func loadConfig() async throws -> ConfigLoadResult {
        guard let token = try tokenStore.readAccessToken() else {
            return .authRequired
        }

        do {
            let data = try await apiClient.fetchConfig(accessToken: token)
            try configStore.saveLastKnownGoodConfig(data, savedAt: Date())
            return .fresh(data)
        } catch let error as ApiError where error.allowsConfigFallback {
            if let cached = try configStore.readLastKnownGoodConfig() {
                return .cached(cached.data, cached.savedAt)
            }
            throw error
        }
    }
}

