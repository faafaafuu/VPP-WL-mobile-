export type ReceiptRequest = {
  platform: "sandbox" | "apple" | "google";
  receipt: string;
  device_id: string;
  product_id: string;
};

export type AuthInitResponse = {
  user_id: string;
};

export type ReceiptResponse = {
  access_token: string;
  token_type: "Bearer";
  expires_at: string;
};

export type PublicNode = {
  id: string;
  region: string;
  provider: string;
  country_code: string;
  protocol: string;
  status: string;
  health: string;
  health_score: number;
  latency_ms: number | null;
  success_rate: number;
  priority: number;
  score: number;
};

export type SubscriptionSummary = {
  active: boolean;
  platform: "sandbox" | "apple" | "google";
  product_id: string;
  expires_at: string;
};

export type MeResponse = {
  user_id: string;
  subscription: SubscriptionSummary | null;
};

export class BackendApiError extends Error {
  constructor(
    public readonly statusCode: number,
    message: string
  ) {
    super(message);
  }

  allowsConfigFallback(): boolean {
    return this.statusCode === 503 || this.statusCode >= 500;
  }
}

export class BackendApiClient {
  constructor(private readonly baseUrl: string) {}

  async initAuth(deviceId: string): Promise<AuthInitResponse> {
    const response = await fetch(`${this.baseUrl}/api/auth/init`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({ device_id: deviceId })
    });

    if (!response.ok) {
      throw new BackendApiError(response.status, await safeErrorMessage(response));
    }

    return (await response.json()) as AuthInitResponse;
  }

  async fetchConfig(accessToken: string): Promise<string> {
    const response = await fetch(`${this.baseUrl}/api/config`, {
      headers: {
        Authorization: `Bearer ${accessToken}`
      }
    });

    if (!response.ok) {
      throw new BackendApiError(response.status, await safeErrorMessage(response));
    }

    return JSON.stringify(await response.json());
  }

  async fetchMe(accessToken: string): Promise<MeResponse> {
    const response = await fetch(`${this.baseUrl}/api/me`, {
      headers: {
        Authorization: `Bearer ${accessToken}`
      }
    });

    if (!response.ok) {
      throw new BackendApiError(response.status, await safeErrorMessage(response));
    }

    return (await response.json()) as MeResponse;
  }

  async fetchNodes(accessToken: string): Promise<PublicNode[]> {
    const response = await fetch(`${this.baseUrl}/api/nodes`, {
      headers: {
        Authorization: `Bearer ${accessToken}`
      }
    });

    if (!response.ok) {
      throw new BackendApiError(response.status, await safeErrorMessage(response));
    }

    const payload = await response.json();
    return Array.isArray(payload.nodes) ? (payload.nodes as PublicNode[]) : [];
  }

  async submitReceipt(payload: ReceiptRequest): Promise<ReceiptResponse> {
    const response = await fetch(`${this.baseUrl}/api/auth/receipt`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify(payload)
    });

    if (!response.ok) {
      throw new BackendApiError(response.status, await safeErrorMessage(response));
    }

    return (await response.json()) as ReceiptResponse;
  }
}

async function safeErrorMessage(response: Response): Promise<string> {
  try {
    const payload = await response.json();
    return typeof payload.error === "string" ? payload.error : "Backend request failed";
  } catch {
    return "Backend request failed";
  }
}
