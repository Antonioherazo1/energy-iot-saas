import type {
  DashboardSummary,
  DeviceWithCredentials,
  DeviceStatus,
  EnergyBucket,
  LatestTelemetry,
  Organization,
  TokenResponse,
  User
} from "../types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "/api/v1";

type RequestOptions = {
  token?: string;
  body?: unknown;
};

export function getDashboardWebSocketUrl(): string {
  const apiUrl = new URL(API_BASE_URL, window.location.origin);
  apiUrl.protocol = apiUrl.protocol === "https:" ? "wss:" : "ws:";
  apiUrl.pathname = `${apiUrl.pathname.replace(/\/$/, "")}/ws/dashboard`;
  apiUrl.search = "";
  return apiUrl.toString();
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const headers: HeadersInit = {
    "Content-Type": "application/json"
  };
  if (options.token) {
    headers.Authorization = `Bearer ${options.token}`;
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: options.body ? "POST" : "GET",
    headers,
    body: options.body ? JSON.stringify(options.body) : undefined
  });

  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `HTTP ${response.status}`);
  }

  return response.json() as Promise<T>;
}

export function login(email: string, password: string): Promise<TokenResponse> {
  return request<TokenResponse>("/auth/login", { body: { email, password } });
}

export function getCurrentUser(token: string): Promise<User> {
  return request<User>("/auth/me", { token });
}

export function getOrganizations(token: string): Promise<Organization[]> {
  return request<Organization[]>("/organizations", { token });
}

export function createDevice(token: string, organizationId: string, name: string, code: string): Promise<DeviceWithCredentials> {
  return request<DeviceWithCredentials>("/devices", {
    token,
    body: {
      organization_id: organizationId,
      name,
      code
    }
  });
}

export function getSummary(token: string): Promise<DashboardSummary> {
  return request<DashboardSummary>("/dashboard/summary", { token });
}

export function getDeviceStatus(token: string): Promise<DeviceStatus[]> {
  return request<DeviceStatus[]>("/dashboard/devices/status", { token });
}

export function getLatestTelemetry(token: string): Promise<LatestTelemetry[]> {
  return request<LatestTelemetry[]>("/dashboard/telemetry/latest", { token });
}

export function getDailyEnergy(token: string): Promise<EnergyBucket[]> {
  return request<EnergyBucket[]>("/dashboard/energy/daily?limit=30", { token });
}

export function getMonthlyEnergy(token: string): Promise<EnergyBucket[]> {
  return request<EnergyBucket[]>("/dashboard/energy/monthly?limit=12", { token });
}
