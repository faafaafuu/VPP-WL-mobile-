import { BackendApiClient, BackendApiError } from "../api/backendClient";
import { SecureTokenStore } from "../storage/secureStore";

export type AuthState =
  | { kind: "idle" }
  | { kind: "activating" }
  | { kind: "active"; expiresAt: string }
  | { kind: "error"; message: string };

export class AuthRepository {
  constructor(
    private readonly apiClient: BackendApiClient,
    private readonly tokenStore: SecureTokenStore
  ) {}

  async activateSandboxReceipt(deviceId: string, receipt: string): Promise<AuthState> {
    const normalizedDeviceId = deviceId.trim();
    const normalizedReceipt = receipt.trim();

    if (!normalizedDeviceId || !normalizedReceipt) {
      return { kind: "error", message: "Device ID and receipt are required" };
    }

    try {
      const response = await this.apiClient.submitReceipt({
        platform: "sandbox",
        receipt: normalizedReceipt,
        device_id: normalizedDeviceId,
        product_id: "vpn.monthly"
      });
      await this.tokenStore.saveAccessToken(response.access_token);
      return { kind: "active", expiresAt: response.expires_at };
    } catch (error) {
      if (error instanceof BackendApiError) {
        return { kind: "error", message: error.message };
      }
      return { kind: "error", message: "Unable to activate subscription" };
    }
  }
}
