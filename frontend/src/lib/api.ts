import type {
  DashboardSummary,
  Device,
  DeviceChannel,
  DeviceWithCredentials,
  DeviceStatus,
  EnergyBucket,
  LatestTelemetry,
  Organization,
  TokenResponse,
  User
} from "../types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "/api/v1";
const ACCESS_KEY = "energy_iot_access_token";
const REFRESH_KEY = "energy_iot_refresh_token";

type RequestOptions = {
  token?: string;
  body?: unknown;
};

let refreshPromise: Promise<string | null> | null = null;

export function getDashboardWebSocketUrl(): string {
  const apiUrl = new URL(API_BASE_URL, window.location.origin);
  apiUrl.protocol = apiUrl.protocol === "https:" ? "wss:" : "ws:";
  apiUrl.pathname = `${apiUrl.pathname.replace(/\/$/, "")}/ws/dashboard`;
  apiUrl.search = "";
  return apiUrl.toString();
}

async function attemptRefresh(): Promise<string | null> {
  const refreshToken = localStorage.getItem(REFRESH_KEY);
  if (!refreshToken) return null;

  try {
    const res = await fetch(`${API_BASE_URL}/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });
    if (!res.ok) {
      localStorage.removeItem(ACCESS_KEY);
      localStorage.removeItem(REFRESH_KEY);
      return null;
    }
    const data: TokenResponse & { refresh_token?: string } = await res.json();
    localStorage.setItem(ACCESS_KEY, data.access_token);
    if (data.refresh_token) {
      localStorage.setItem(REFRESH_KEY, data.refresh_token);
    }
    return data.access_token;
  } catch {
    localStorage.removeItem(ACCESS_KEY);
    localStorage.removeItem(REFRESH_KEY);
    return null;
  }
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

  if (response.status === 401 && options.token) {
    if (!refreshPromise) {
      refreshPromise = attemptRefresh();
    }
    const newToken = await refreshPromise;
    refreshPromise = null;

    if (newToken) {
      headers.Authorization = `Bearer ${newToken}`;
      const retry = await fetch(`${API_BASE_URL}${path}`, {
        method: options.body ? "POST" : "GET",
        headers,
        body: options.body ? JSON.stringify(options.body) : undefined,
      });
      if (retry.ok) return retry.json() as Promise<T>;
    }
    window.location.reload();
    throw new Error("Session expired");
  }

  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `HTTP ${response.status}`);
  }

  return response.json() as Promise<T>;
}

export function login(email: string, password: string): Promise<TokenResponse> {
  return request<TokenResponse>("/auth/login", { body: { email, password } });
}

export function signup(email: string, password: string, fullName: string, organizationName: string): Promise<TokenResponse> {
  return request<TokenResponse>("/auth/register", {
    body: { email, password, full_name: fullName, organization_name: organizationName },
  });
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

export function getChannelTimeSeries(token: string): Promise<LatestTelemetry[]> {
  return request<LatestTelemetry[]>("/dashboard/channels/latest?limit=60", { token });
}

export function downloadTelemetryCsv(token: string, start?: string, end?: string, limit = 500): void {
  const params = new URLSearchParams({ limit: String(limit) });
  if (start) params.set("start", start);
  if (end) params.set("end", end);
  const url = `${API_BASE_URL}/dashboard/telemetry/csv?${params}`;
  fetch(url, { headers: { Authorization: `Bearer ${token}` } })
    .then((res) => {
      if (!res.ok) throw new Error("Error al descargar");
      return res.blob();
    })
    .then((blob) => {
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = "telemetria.csv";
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(a.href);
    })
    .catch((err) => console.error("CSV download failed:", err));
}

export function getTelemetryByRange(token: string, start: string, end: string, limit = 200): Promise<LatestTelemetry[]> {
  return request<LatestTelemetry[]>(
    `/dashboard/telemetry/range?start=${encodeURIComponent(start)}&end=${encodeURIComponent(end)}&limit=${limit}`,
    { token }
  );
}

export function linkDevice(token: string, organizationId: string, name: string, code: string): Promise<Device> {
  return request<Device>("/devices/link", {
    token,
    body: { organization_id: organizationId, name, code },
  });
}

export function setupChannels(token: string, deviceId: string, channels: Array<{ channel_number: number; name: string; voltage: number }>): Promise<unknown> {
  return request(`/devices/${deviceId}/channels/setup`, {
    token,
    body: channels,
  });
}

export function getDeviceChannels(token: string, deviceId: string): Promise<DeviceChannel[]> {
  return request<DeviceChannel[]>(`/devices/${deviceId}/channels`, { token });
}

export function getChannelDaySeries(token: string, deviceId: string, date: string): Promise<LatestTelemetry[]> {
  return request<LatestTelemetry[]>(
    `/dashboard/channels/day?device_id=${deviceId}&date=${date}`,
    { token }
  );
}
