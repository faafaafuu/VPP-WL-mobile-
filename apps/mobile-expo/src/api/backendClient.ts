export type ReceiptRequest = {
  platform: "sandbox" | "apple" | "google";
  receipt: string;
  device_id: string;
  product_id: string;
};

export type ReceiptResponse = {
  access_token: string;
  token_type: "Bearer";
  expires_at: string;
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
