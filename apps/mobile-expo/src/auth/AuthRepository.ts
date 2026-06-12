import { BackendApiClient, BackendApiError } from "../api/backendClient";
import { SecureTokenStore } from "../storage/secureStore";

export type AuthState =
  | { kind: "idle" }
  | { kind: "checking" }
  | { kind: "initializing" }
  | { kind: "initialized"; userId: string }
  | { kind: "activating" }
  | { kind: "exporting" }
  | { kind: "exported"; exportedJson: string }
  | { kind: "deleting" }
  | { kind: "deleted" }
  | { kind: "active"; expiresAt: string }
  | { kind: "auth-required" }
  | { kind: "subscription-required" }
  | { kind: "error"; message: string };

export class AuthRepository {
  constructor(
    private readonly apiClient: BackendApiClient,
    private readonly tokenStore: SecureTokenStore
  ) {}

  async initDevice(deviceId: string): Promise<AuthState> {
    const normalizedDeviceId = deviceId.trim();
    if (!normalizedDeviceId) {
      return { kind: "error", message: "Device ID is required" };
    }

    try {
      const response = await this.apiClient.initAuth(normalizedDeviceId);
      return { kind: "initialized", userId: response.user_id };
    } catch (error) {
      if (error instanceof BackendApiError) {
        return { kind: "error", message: error.message };
      }
      return { kind: "error", message: "Unable to initialize user" };
    }
  }

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

  async loadCurrentSubscription(): Promise<AuthState> {
    const token = await this.tokenStore.readAccessToken();
    if (!token) {
      return { kind: "auth-required" };
    }

    try {
      const response = await this.apiClient.fetchMe(token);
      if (!response.subscription?.active) {
        return { kind: "subscription-required" };
      }
      return { kind: "active", expiresAt: response.subscription.expires_at };
    } catch (error) {
      if (error instanceof BackendApiError && error.statusCode === 401) {
        await this.tokenStore.clearAccessToken();
        return { kind: "auth-required" };
      }
      if (error instanceof BackendApiError) {
        return { kind: "error", message: error.message };
      }
      return { kind: "error", message: "Unable to load subscription" };
    }
  }

  async exportAccountData(): Promise<AuthState> {
    const token = await this.tokenStore.readAccessToken();
    if (!token) {
      return { kind: "auth-required" };
    }

    try {
      const response = await this.apiClient.exportMe(token);
      return { kind: "exported", exportedJson: JSON.stringify(response.data, null, 2) };
    } catch (error) {
      if (error instanceof BackendApiError && error.statusCode === 401) {
        await this.tokenStore.clearAccessToken();
        return { kind: "auth-required" };
      }
      if (error instanceof BackendApiError) {
        return { kind: "error", message: error.message };
      }
      return { kind: "error", message: "Unable to export account data" };
    }
  }

  async deleteAccount(): Promise<AuthState> {
    const token = await this.tokenStore.readAccessToken();
    if (!token) {
      return { kind: "auth-required" };
    }

    try {
      const response = await this.apiClient.deleteMe(token);
      if (!response.deleted) {
        return { kind: "error", message: "Account deletion was not confirmed by backend" };
      }
      await this.tokenStore.clearAccessToken();
      await this.tokenStore.clearLastKnownGoodConfig();
      return { kind: "deleted" };
    } catch (error) {
      if (error instanceof BackendApiError && error.statusCode === 401) {
        await this.tokenStore.clearAccessToken();
        await this.tokenStore.clearLastKnownGoodConfig();
        return { kind: "auth-required" };
      }
      if (error instanceof BackendApiError) {
        return { kind: "error", message: error.message };
      }
      return { kind: "error", message: "Unable to delete account" };
    }
  }
}
