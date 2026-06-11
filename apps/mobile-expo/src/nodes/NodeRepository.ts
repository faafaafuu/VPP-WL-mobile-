import { BackendApiClient, BackendApiError, PublicNode } from "../api/backendClient";
import { SecureTokenStore } from "../storage/secureStore";

export type NodesState =
  | { kind: "idle" }
  | { kind: "loading" }
  | { kind: "ready"; nodes: PublicNode[] }
  | { kind: "auth-required" }
  | { kind: "error"; message: string };

export class NodeRepository {
  constructor(
    private readonly apiClient: BackendApiClient,
    private readonly tokenStore: SecureTokenStore
  ) {}

  async loadNodes(): Promise<NodesState> {
    const token = await this.tokenStore.readAccessToken();
    if (!token) {
      return { kind: "auth-required" };
    }

    try {
      return { kind: "ready", nodes: await this.apiClient.fetchNodes(token) };
    } catch (error) {
      if (error instanceof BackendApiError && error.statusCode === 401) {
        await this.tokenStore.clearAccessToken();
        return { kind: "auth-required" };
      }
      if (error instanceof BackendApiError) {
        return { kind: "error", message: error.message };
      }
      return { kind: "error", message: "Unable to load nodes" };
    }
  }
}
