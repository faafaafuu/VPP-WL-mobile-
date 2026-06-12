import { BackendApiClient, BackendApiError, VersionResponse } from "../api/backendClient";

export type VersionState =
  | { kind: "idle" }
  | { kind: "loading" }
  | { kind: "ready"; version: VersionResponse }
  | { kind: "error"; message: string };

export class VersionRepository {
  constructor(private readonly apiClient: BackendApiClient) {}

  async loadVersion(): Promise<VersionState> {
    try {
      return { kind: "ready", version: await this.apiClient.fetchVersion() };
    } catch (error) {
      if (error instanceof BackendApiError) {
        return { kind: "error", message: error.message };
      }
      return { kind: "error", message: "Unable to load API version" };
    }
  }
}
