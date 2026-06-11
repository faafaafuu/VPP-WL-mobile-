import * as SecureStore from "expo-secure-store";

const ACCESS_TOKEN_KEY = "vpn_router_access_token";
const LAST_KNOWN_GOOD_CONFIG_KEY = "vpn_router_last_known_good_config";

export class SecureTokenStore {
  async readAccessToken(): Promise<string | null> {
    return SecureStore.getItemAsync(ACCESS_TOKEN_KEY);
  }

  async saveAccessToken(token: string): Promise<void> {
    await SecureStore.setItemAsync(ACCESS_TOKEN_KEY, token, {
      keychainAccessible: SecureStore.AFTER_FIRST_UNLOCK_THIS_DEVICE_ONLY
    });
  }

  async clearAccessToken(): Promise<void> {
    await SecureStore.deleteItemAsync(ACCESS_TOKEN_KEY);
  }

  async readLastKnownGoodConfig(): Promise<string | null> {
    return SecureStore.getItemAsync(LAST_KNOWN_GOOD_CONFIG_KEY);
  }

  async saveLastKnownGoodConfig(configJson: string): Promise<void> {
    await SecureStore.setItemAsync(LAST_KNOWN_GOOD_CONFIG_KEY, configJson, {
      keychainAccessible: SecureStore.AFTER_FIRST_UNLOCK_THIS_DEVICE_ONLY
    });
  }
}
