import { BackendApiClient, BackendApiError } from "../api/backendClient";
import { SecureTokenStore } from "../storage/secureStore";

export type ConfigState =
  | { kind: "idle" }
  | { kind: "fresh"; configJson: string }
  | { kind: "last-known-good"; configJson: string }
  | { kind: "auth-required" }
  | { kind: "subscription-required" }
  | { kind: "error"; message: string };

export class ConfigRepository {
  constructor(
    private readonly apiClient: BackendApiClient,
    private readonly tokenStore: SecureTokenStore
  ) {}

  async loadConfig(): Promise<ConfigState> {
    const token = await this.tokenStore.readAccessToken();
    if (!token) {
      return { kind: "auth-required" };
    }

    try {
      const configJson = await this.apiClient.fetchConfig(token);
      await this.tokenStore.saveLastKnownGoodConfig(configJson);
      return { kind: "fresh", configJson };
    } catch (error) {
      if (error instanceof BackendApiError) {
        if (error.statusCode === 401) {
          await this.tokenStore.clearAccessToken();
          return { kind: "auth-required" };
        }

        if (error.statusCode === 403) {
          return { kind: "subscription-required" };
        }

        if (error.allowsConfigFallback()) {
          const fallback = await this.tokenStore.readLastKnownGoodConfig();
          if (fallback) {
            return { kind: "last-known-good", configJson: fallback };
          }
        }

        return { kind: "error", message: error.message };
      }

      const fallback = await this.tokenStore.readLastKnownGoodConfig();
      if (fallback) {
        return { kind: "last-known-good", configJson: fallback };
      }

      return { kind: "error", message: "Unable to load VPN config" };
    }
  }
}
