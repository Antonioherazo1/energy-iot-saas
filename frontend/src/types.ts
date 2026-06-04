export type TokenResponse = {
  access_token: string;
  refresh_token: string;
  token_type: string;
};

export type User = {
  id: string;
  email: string;
  full_name: string;
  is_active: boolean;
};

export type Organization = {
  id: string;
  name: string;
  plan: string;
  device_limit: number;
  role: string;
};

export type Device = {
  id: string;
  organization_id: string;
  name: string;
  code: string;
  is_active: boolean;
  last_seen_at: string | null;
};

export type DeviceWithCredentials = Device & {
  device_key: string;
};

export type DashboardSummary = {
  total_devices: number;
  online_devices: number;
  offline_devices: number;
  current_power: string;
  latest_energy_kwh: string;
};

export type DeviceStatus = {
  device_id: string;
  name: string;
  code: string;
  is_active: boolean;
  is_online: boolean;
  last_seen_at: string | null;
};

export type LatestTelemetry = {
  device_id: string;
  device_name: string;
  device_code: string;
  recorded_at: string | null;
  voltage: string | null;
  current: string | null;
  power: string | null;
  energy_kwh: string | null;
  frequency: string | null;
  power_factor: string | null;
  ch1: string | null;
  ch2: string | null;
  ch3: string | null;
  ch4: string | null;
  ch1_energy_kwh: string | null;
  ch2_energy_kwh: string | null;
  ch3_energy_kwh: string | null;
  ch4_energy_kwh: string | null;
};

export type DeviceChannel = {
  id: string;
  device_id: string;
  channel_number: number;
  name: string;
  voltage: number;
  is_active: boolean;
};

export type EnergyBucket = {
  period: string;
  energy_kwh: string;
};
