import { DollarSign, Download, LogOut, Menu, Plus, PlugZap, RefreshCw, Settings, Trash2, Zap } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import type { FormEvent, ReactNode } from "react";
import type { EChartsOption } from "echarts";

import Chart from "./components/Chart";
import {
  createDevice,
  getBillingDailyChannels,
  getBillingDailyEnergy,
  getBillingMonthlyEnergy,
  getChannelTimeSeries,
  getCurrentUser,
  getDashboardWebSocketUrl,
  getDailyEnergy,
  getDeviceChannels,
  getDeviceStatus,
  getLatestTelemetry,
  getMonthlyEnergy,
  getOrganizations,
  getRealtimeCurrents,
  getSummary,
  login,
  signup,
  downloadTelemetryExcel,
  getTelemetryByRange,
  getChannelDaySeries,
  deleteDevice,
  getDbSize,
  linkDevice,
  setupChannels,
  updateChannel,
} from "./lib/api";
import type { DashboardSummary, DeviceChannel, DeviceStatus, EnergyBucket, LatestTelemetry, Organization, User } from "./types";

const tokenKey = "energy_iot_access_token";
const refreshKey = "energy_iot_refresh_token";

function numeric(value: string | null | undefined): number {
  return Number(value ?? 0);
}



function formatNumber(value: string | number | null | undefined, suffix = "") {
  const number = Number(value ?? 0);
  return `${new Intl.NumberFormat("es-CO", { maximumFractionDigits: 2 }).format(number)}${suffix}`;
}

function formatDate(value: string | null) {
  if (!value) {
    return "Sin datos";
  }
  return new Intl.DateTimeFormat("es-CO", {
    dateStyle: "short",
    timeStyle: "short"
  }).format(new Date(value));
}

export default function App() {
  const [token, setToken] = useState(() => localStorage.getItem(tokenKey) ?? "");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [orgName, setOrgName] = useState("");
  const [authMode, setAuthMode] = useState<"login" | "signup">("login");
  const [user, setUser] = useState<User | null>(null);
const [summary, setSummary] = useState<DashboardSummary | null>(null);
const [devices, setDevices] = useState<DeviceStatus[]>([]);
const [latest, setLatest] = useState<LatestTelemetry[]>([]);
const [daily, setDaily] = useState<EnergyBucket[]>([]);
const [monthly, setMonthly] = useState<EnergyBucket[]>([]);
const [organizations, setOrganizations] = useState<Organization[]>([]);
  const [channelData, setChannelData] = useState<LatestTelemetry[]>([]);
  const [newDeviceKey, setNewDeviceKey] = useState("");
  const [newDeviceCode, setNewDeviceCode] = useState("");
  const [createDeviceName, setCreateDeviceName] = useState("");
  const [createDeviceCode, setCreateDeviceCode] = useState("");
  const [lastUpdatedAt, setLastUpdatedAt] = useState<Date | null>(null);
  const [loading, setLoading] = useState(false);
  const [creatingDevice, setCreatingDevice] = useState(false);
  const [error, setError] = useState("");
  const [onboardingStep, setOnboardingStep] = useState(0);
  const [onboardingChannels, setOnboardingChannels] = useState(4);
  const [channelConfigs, setChannelConfigs] = useState<Array<{ name: string; voltage: number }>>([]);
  const [deviceCode, setDeviceCode] = useState("");
  const [deviceName, setDeviceName] = useState("");
  const [linking, setLinking] = useState(false);
  const [selectedDeviceId, setSelectedDeviceId] = useState<string | null>(null);
  const [deviceChannels, setDeviceChannels] = useState<DeviceChannel[]>([]);
  const [dayDate, setDayDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [daySeries, setDaySeries] = useState<LatestTelemetry[]>([]);
  const [dayLoading, setDayLoading] = useState(false);
  const [currentBuffer, setCurrentBuffer] = useState<LatestTelemetry[]>([]);
  const [bufferLoading, setBufferLoading] = useState(false);
  const [realtimeMinutes, setRealtimeMinutes] = useState(10);
  const [billingStartDay, setBillingStartDay] = useState(() => {
    const saved = localStorage.getItem("billing_start_day");
    return saved ? Number(saved) : 1;
  });
  const [billingDaily, setBillingDaily] = useState<EnergyBucket[]>([]);
  const [billingMonthly, setBillingMonthly] = useState<EnergyBucket[]>([]);
  const [channelDailyEnergy, setChannelDailyEnergy] = useState<{ channel_number: number; energy_kwh: string }[]>([]);
  const [channelHourFrom, setChannelHourFrom] = useState(0);
  const [channelHourTo, setChannelHourTo] = useState(() => Math.max(1, Math.min(24, new Date().getHours() + 1)));
  const [configChannels, setConfigChannels] = useState<DeviceChannel[]>([]);
  const [savingChannels, setSavingChannels] = useState(false);
  const [rangeStart, setRangeStart] = useState("");
  const [rangeEnd, setRangeEnd] = useState("");
  const [rangeData, setRangeData] = useState<LatestTelemetry[]>([]);
  const [rangeLoading, setRangeLoading] = useState(false);
  const [showSideMenu, setShowSideMenu] = useState(false);
  const [sideSection, setSideSection] = useState<string | null>(null);
  const [kwhRate, setKwhRate] = useState(() => {
    const saved = localStorage.getItem("kwh_rate");
    return saved ? Number(saved) : 800;
  });
  const realtimeReloadRef = useRef<number | null>(null);
  const [dbSize, setDbSize] = useState<number | null>(null);

  async function loadDashboard(activeToken = token) {
    if (!activeToken) {
      return;
    }

    setLoading(true);
    setError("");
    try {
      const [currentUser, orgData, summaryData, deviceData, latestData, dailyData, monthlyData, channels] = await Promise.all([
        getCurrentUser(activeToken),
        getOrganizations(activeToken),
        getSummary(activeToken),
        getDeviceStatus(activeToken),
        getLatestTelemetry(activeToken),
        getDailyEnergy(activeToken),
        getMonthlyEnergy(activeToken),
        getChannelTimeSeries(activeToken),
        getDbSize(activeToken).then((r) => setDbSize(r.size_mb)).catch(() => {}),
      ]);
      setUser(currentUser);
      setOrganizations(orgData);
      setSummary(summaryData);
      setDevices(deviceData);
      setLatest(latestData);
      setDaily(dailyData.reverse());
      setMonthly(monthlyData.reverse());
      setChannelData(channels);
      setLastUpdatedAt(new Date());
      if (deviceData.length > 0) {
        const stillExists = selectedDeviceId && deviceData.some((d) => d.device_id === selectedDeviceId);
        if (!stillExists) {
          setSelectedDeviceId(deviceData[0].device_id);
        }
      } else {
        setSelectedDeviceId(null);
      }
      if (orgData.length > 0 && deviceData.length === 0 && onboardingStep === 0) {
        setOnboardingStep(0);
      } else if (deviceData.length > 0) {
        setOnboardingStep(4);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo cargar el dashboard");
      setUser(null);
      localStorage.removeItem(tokenKey);
      setToken("");
    } finally {
      setLoading(false);
    }
  }

  async function handleAuth(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setError("");
    try {
      const response = authMode === "login"
        ? await login(email, password)
        : await signup(email, password, fullName.trim(), orgName.trim());
      localStorage.setItem(tokenKey, response.access_token);
      localStorage.setItem(refreshKey, response.refresh_token);
      setToken(response.access_token);
      if (authMode === "signup") {
        const currentUser = await getCurrentUser(response.access_token);
        setUser(currentUser);
        const orgs = await getOrganizations(response.access_token);
        setOrganizations(orgs);
        setOnboardingStep(0);
      } else {
        await loadDashboard(response.access_token);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo iniciar sesion");
    } finally {
      setLoading(false);
    }
  }

  function logout() {
    localStorage.removeItem(tokenKey);
    setToken("");
    setUser(null);
    setPassword("");
    setAuthMode("login");
    setOnboardingStep(0);
  }

  function startOnboardingChannels(count: number) {
    setOnboardingChannels(count);
    setChannelConfigs(
      Array.from({ length: count }, (_, i) => ({ name: `Canal ${i + 1}`, voltage: 110 }))
    );
    setOnboardingStep(1);
  }

  function handleLinkDevice() {
    if (!organizations[0] || !deviceCode.trim() || !deviceName.trim()) return;
    setLinking(true);
    setError("");
    const orgId = organizations[0].id;
    linkDevice(token, orgId, deviceName.trim(), deviceCode.trim())
      .then((device) => {
        return setupChannels(token, device.id, channelConfigs.map((ch, i) => ({
          channel_number: i + 1,
          name: ch.name,
          voltage: ch.voltage,
        }))).then(() => device);
      })
      .then(() => {
        setOnboardingStep(3);
      })
      .catch((err) => {
        setError(err instanceof Error ? err.message : "Error al vincular dispositivo");
      })
      .finally(() => setLinking(false));
  }

  async function handleCreateDevice(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const organizationId = organizations[0]?.id;
    if (!organizationId) {
      setError("No hay una organizacion disponible para crear dispositivos");
      return;
    }

    setCreatingDevice(true);
    setError("");
    try {
      const createdDevice = await createDevice(token, organizationId, createDeviceName.trim(), createDeviceCode.trim());
      setCreateDeviceName("");
      setCreateDeviceCode("");
      setNewDeviceCode(createdDevice.code);
      setNewDeviceKey(createdDevice.device_key);
      await loadDashboard(token);
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo crear el dispositivo");
    } finally {
      setCreatingDevice(false);
    }
  }

  function toLocalIso(date: Date): string {
    const pad = (n: number) => n.toString().padStart(2, "0");
    return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
  }

  useEffect(() => {
    if (!rangeEnd && token) {
      setRangeEnd(toLocalIso(new Date()));
    }
  }, [token]);

  async function loadRange() {
    if (!rangeStart || !rangeEnd || !token) return;
    setRangeLoading(true);
    setError("");
    try {
      const startUtc = new Date(rangeStart).toISOString();
      const endUtc = new Date(rangeEnd).toISOString();
      const data = await getTelemetryByRange(token, startUtc, endUtc);
      setRangeData(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error al cargar rango");
    } finally {
      setRangeLoading(false);
    }
  }

  async function loadDeviceChannels(deviceId: string) {
    if (!token) return;
    try {
      const channels = await getDeviceChannels(token, deviceId);
      setDeviceChannels(channels);
    } catch {
      // ignore
    }
  }

  async function loadDaySeries() {
    if (!token || !selectedDeviceId || !dayDate) return;
    setDayLoading(true);
    try {
      const data = await getChannelDaySeries(token, selectedDeviceId, dayDate);
      setDaySeries(data);
    } catch {
      // ignore
    } finally {
      setDayLoading(false);
    }
  }

  useEffect(() => {
    if (selectedDeviceId) {
      void loadDeviceChannels(selectedDeviceId);
    }
  }, [selectedDeviceId]);

  useEffect(() => {
    if (selectedDeviceId) {
      void loadDaySeries();
    }
  }, [selectedDeviceId, dayDate]);

  async function loadRealtimeBuffer() {
    if (!token || !selectedDeviceId) return;
    if (currentBuffer.length === 0) setBufferLoading(true);
    try {
      const data = await getRealtimeCurrents(token, selectedDeviceId, realtimeMinutes);
      setCurrentBuffer(data);
    } catch {
      // ignore
    } finally {
      setBufferLoading(false);
    }
  }

  async function pollLatestTelemetry() {
    if (!token) return;
    try {
      const data = await getLatestTelemetry(token);
      setLatest(data);
      setLastUpdatedAt(new Date());
    } catch {
      // ignore
    }
  }

  useEffect(() => {
    if (!selectedDeviceId) return;
    setCurrentBuffer([]);
    const timer = setTimeout(() => void loadRealtimeBuffer(), 50);
    const bufInterval = window.setInterval(() => void loadRealtimeBuffer(), 5000);
    return () => { clearTimeout(timer); window.clearInterval(bufInterval); };
  }, [token, selectedDeviceId, realtimeMinutes]);

  useEffect(() => {
    if (!token) return;
    void pollLatestTelemetry();
    const ltInterval = window.setInterval(() => void pollLatestTelemetry(), 3000);
    return () => window.clearInterval(ltInterval);
  }, [token]);

  async function loadBillingData() {
    if (!token) return;
    try {
      const [daily, monthly] = await Promise.all([
        getBillingDailyEnergy(token, billingStartDay),
        getBillingMonthlyEnergy(token, billingStartDay),
      ]);
      setBillingDaily(daily);
      setBillingMonthly(monthly);
    } catch {
      // ignore
    }
  }

  useEffect(() => {
    if (token && onboardingStep === 0 && user === null) {
      void loadDashboard(token);
    }
  }, []);

  useEffect(() => {
    if (!token || !user || onboardingStep > 0) {
      return;
    }
    const interval = window.setInterval(() => {
      void loadDashboard(token);
    }, 10000);
    return () => window.clearInterval(interval);
  }, [token, user, onboardingStep]);

  useEffect(() => {
    if (!token || !user || onboardingStep > 0) {
      return;
    }

    const socket = new WebSocket(getDashboardWebSocketUrl());
    socket.onmessage = () => {
      if (realtimeReloadRef.current) {
        window.clearTimeout(realtimeReloadRef.current);
      }
      realtimeReloadRef.current = window.setTimeout(() => {
        void loadDashboard(token);
        if (selectedDeviceId) {
          void loadDaySeries();
          void loadRealtimeBuffer();
        }
      }, 250);
    };
    socket.onerror = () => {
      socket.close();
    };

    return () => {
      if (realtimeReloadRef.current) {
        window.clearTimeout(realtimeReloadRef.current);
      }
      socket.close();
    };
  }, [token, user, onboardingStep]);

  useEffect(() => {
    if (!token || !user) return;
    if (onboardingStep < 3) return;
    void loadBillingData();
  }, [token, user, onboardingStep, billingStartDay]);

  async function loadChannelDailyEnergy() {
    if (!token || !selectedDeviceId) return;
    try {
      const data = await getBillingDailyChannels(token, selectedDeviceId);
      setChannelDailyEnergy(data);
    } catch {
      // ignore
    }
  }

  useEffect(() => {
    if (!token || !selectedDeviceId) return;
    void loadChannelDailyEnergy();
  }, [token, selectedDeviceId]);

  const channelsOption = useMemo<EChartsOption>(() => {
    const colors = ["#0f766e", "#2563eb", "#d97706", "#dc2626"];
    const sourceData = daySeries.length > 0 ? daySeries : channelData;

    const step = Math.max(1, Math.floor(sourceData.length / 500));
    const sampled = sourceData.filter((_, i) => i % step === 0 || i === sourceData.length - 1);

    const filtered = sampled.filter((d) => {
      if (!d.recorded_at) return true;
      const h = new Date(d.recorded_at).getHours();
      return h >= channelHourFrom && h < channelHourTo;
    });

    const times = filtered.map((d) => {
      const t = new Date(d.recorded_at ?? "");
      return `${String(t.getHours()).padStart(2, "0")}:${String(t.getMinutes()).padStart(2, "0")}`;
    });

    const activeChannels = deviceChannels.filter((ch) => ch.is_active);

    const series = activeChannels
      .map((ch, idx) => ({
        type: "line" as const,
        smooth: true,
        symbol: "none",
        name: ch.name,
        data: filtered.map((d) => numeric(d[`ch${ch.channel_number}` as keyof LatestTelemetry] as string | null)),
        lineStyle: { color: colors[idx % colors.length], width: 2 },
      }));

    return {
      grid: { left: 56, right: 16, top: 48, bottom: 72 },
      tooltip: { trigger: "axis" },
      legend: { bottom: 4, textStyle: { color: "#526071", fontSize: 11 }, icon: "circle" },
      xAxis: {
        type: "category",
        data: times,
        axisLabel: {
          color: "#526071",
          fontSize: 10,
          rotate: 90,
          showMaxLabel: true,
          interval: Math.max(1, Math.floor(times.length / 24)),
        },
      },
      yAxis: {
        type: "value",
        name: "Amperios",
        axisLabel: { color: "#526071" },
        splitLine: { lineStyle: { color: "#e4e8ef" } },
      },
      series,
    };
  }, [channelData, daySeries, deviceChannels, channelHourFrom, channelHourTo]);

  const realtimeCurrentOption = useMemo<EChartsOption>(() => {
    const colors = ["#0f766e", "#2563eb", "#d97706", "#dc2626"];
    const times = currentBuffer.map((d) => {
      const t = new Date(d.recorded_at ?? "");
      return `${String(t.getHours()).padStart(2, "0")}:${String(t.getMinutes()).padStart(2, "0")}:${String(t.getSeconds()).padStart(2, "0")}`;
    });
    const series = deviceChannels
      .filter((ch) => ch.is_active)
      .map((ch) => {
        const key = `ch${ch.channel_number}` as keyof LatestTelemetry;
        return {
          type: "line" as const,
          smooth: true,
          symbol: "none",
          name: ch.name,
          data: currentBuffer.map((d) => numeric(d[key] as string | null)),
          lineStyle: { color: colors[(ch.channel_number - 1) % colors.length], width: 2 },
        };
      });
    return {
      grid: { left: 56, right: 16, top: 48, bottom: 72 },
      tooltip: { trigger: "axis" },
      legend: { bottom: 4, textStyle: { color: "#526071", fontSize: 11 }, icon: "circle" },
      xAxis: {
        type: "category",
        data: times,
        axisLabel: {
          color: "#526071",
          fontSize: 10,
          rotate: 90,
          showMaxLabel: true,
          interval: Math.max(1, Math.floor(times.length / 24)),
        },
      },
      yAxis: {
        type: "value",
        name: "Amperios",
        axisLabel: { color: "#526071" },
        splitLine: { lineStyle: { color: "#e4e8ef" } },
      },
      series,
    };
  }, [currentBuffer, deviceChannels]);

  if (!token || !user || (onboardingStep === 0 && user === null)) {
    const signingUp = authMode === "signup";
    return (
      <main className="grid min-h-screen place-items-center bg-panel px-4 py-8 text-ink">
        <section className="w-full max-w-md rounded-lg border border-line bg-white p-6 shadow-sm">
          <div className="mb-6 flex items-center gap-3">
            <div className="grid h-11 w-11 place-items-center rounded-md bg-brand text-white">
              <Zap size={22} />
            </div>
            <div>
              <h1 className="text-xl font-semibold">Energy IoT</h1>
              <p className="text-sm text-slate-500">Monitoreo industrial</p>
            </div>
          </div>

          <div className="mb-4 flex rounded-md border border-line overflow-hidden">
            <button
              className={`flex-1 py-2 text-sm font-medium ${!signingUp ? "bg-brand text-white" : "bg-white text-ink"}`}
              onClick={() => { setAuthMode("login"); setError(""); }}
              type="button"
            >Iniciar sesion</button>
            <button
              className={`flex-1 py-2 text-sm font-medium ${signingUp ? "bg-brand text-white" : "bg-white text-ink"}`}
              onClick={() => { setAuthMode("signup"); setError(""); }}
              type="button"
            >Crear cuenta</button>
          </div>

          <form className="space-y-4" onSubmit={handleAuth}>
            {signingUp ? (
              <label className="block">
                <span className="mb-1 block text-sm font-medium">Nombre completo</span>
                <input
                  className="h-11 w-full rounded-md border border-line px-3 outline-none focus:border-brand"
                  type="text"
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  required
                />
              </label>
            ) : null}
            {signingUp ? (
              <label className="block">
                <span className="mb-1 block text-sm font-medium">Nombre de la empresa</span>
                <input
                  className="h-11 w-full rounded-md border border-line px-3 outline-none focus:border-brand"
                  type="text"
                  value={orgName}
                  onChange={(e) => setOrgName(e.target.value)}
                  required
                />
              </label>
            ) : null}
            <label className="block">
              <span className="mb-1 block text-sm font-medium">Email</span>
              <input
                className="h-11 w-full rounded-md border border-line px-3 outline-none focus:border-brand"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
            </label>
            <label className="block">
              <span className="mb-1 block text-sm font-medium">Password</span>
              <input
                className="h-11 w-full rounded-md border border-line px-3 outline-none focus:border-brand"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                minLength={8}
              />
            </label>
            {error ? <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p> : null}
            <button
              className="flex h-11 w-full items-center justify-center gap-2 rounded-md bg-brand px-4 font-medium text-white disabled:opacity-60"
              disabled={loading}
              type="submit"
            >
              <PlugZap size={18} />
              {signingUp ? "Crear cuenta" : "Entrar"}
            </button>
          </form>
        </section>
      </main>
    );
  }

  if (onboardingStep <= 2) {
    return (
      <main className="grid min-h-screen place-items-center bg-panel px-4 py-8 text-ink">
        <section className="w-full max-w-xl rounded-lg border border-line bg-white p-6 shadow-sm">
          <div className="mb-6 flex items-center gap-3">
            <div className="grid h-10 w-10 place-items-center rounded-md bg-brand text-white">
              <Zap size={21} />
            </div>
            <div>
              <h1 className="text-lg font-semibold">Configuracion inicial</h1>
              <p className="text-sm text-slate-500">Paso {onboardingStep + 1} de 3</p>
            </div>
          </div>

          {/* Step 0: elegir 1 o 4 canales */}
          {onboardingStep === 0 ? (
            <div className="space-y-4">
              <p className="text-sm text-slate-600">Cuantos canales mide tu dispositivo?</p>
              <div className="grid grid-cols-2 gap-3">
                <button
                  className="rounded-lg border-2 border-line p-6 text-center hover:border-brand hover:bg-brand/5"
                  onClick={() => startOnboardingChannels(1)}
                  type="button"
                >
                  <span className="text-2xl font-bold">1</span>
                  <p className="mt-1 text-sm text-slate-500">Canal</p>
                </button>
                <button
                  className="rounded-lg border-2 border-line p-6 text-center hover:border-brand hover:bg-brand/5"
                  onClick={() => startOnboardingChannels(4)}
                  type="button"
                >
                  <span className="text-2xl font-bold">4</span>
                  <p className="mt-1 text-sm text-slate-500">Canales</p>
                </button>
              </div>
            </div>
          ) : null}

          {/* Step 1: configurar canales */}
          {onboardingStep === 1 ? (
            <div className="space-y-4">
              <p className="text-sm text-slate-600">Nombra cada canal y define su voltaje:</p>
              {channelConfigs.map((ch, i) => (
                <div className="flex gap-3 items-end" key={i}>
                  <label className="flex-1">
                    <span className="mb-1 block text-xs font-medium text-slate-600">Canal {i + 1}</span>
                    <input
                      className="h-10 w-full rounded-md border border-line px-3 text-sm outline-none focus:border-brand"
                      value={ch.name}
                      onChange={(e) => {
                        const next = [...channelConfigs];
                        next[i] = { ...next[i], name: e.target.value };
                        setChannelConfigs(next);
                      }}
                    />
                  </label>
                  <label className="w-28">
                    <span className="mb-1 block text-xs font-medium text-slate-600">Voltaje</span>
                    <select
                      className="h-10 w-full rounded-md border border-line px-3 text-sm outline-none focus:border-brand"
                      value={ch.voltage}
                      onChange={(e) => {
                        const next = [...channelConfigs];
                        next[i] = { ...next[i], voltage: Number(e.target.value) };
                        setChannelConfigs(next);
                      }}
                    >
                      <option value={110}>110 V</option>
                      <option value={220}>220 V</option>
                    </select>
                  </label>
                </div>
              ))}
              <button
                className="mt-2 flex h-11 w-full items-center justify-center gap-2 rounded-md bg-brand px-4 font-medium text-white"
                onClick={() => setOnboardingStep(2)}
                type="button"
              >
                Continuar
              </button>
            </div>
          ) : null}

          {/* Step 2: vincular dispositivo */}
          {onboardingStep === 2 ? (
            <div className="space-y-4">
              <p className="text-sm text-slate-600">Ingresa el codigo MQTT de tu ESP32 y un nombre para identificarlo:</p>
              <label className="block">
                <span className="mb-1 block text-sm font-medium">Nombre del dispositivo</span>
                <input
                  className="h-11 w-full rounded-md border border-line px-3 outline-none focus:border-brand"
                  placeholder="Ej: Piso 1, Sala de maquinas"
                  value={deviceName}
                  onChange={(e) => setDeviceName(e.target.value)}
                />
              </label>
              <label className="block">
                <span className="mb-1 block text-sm font-medium">Codigo MQTT</span>
                <input
                  className="h-11 w-full rounded-md border border-line px-3 font-mono text-sm outline-none focus:border-brand"
                  placeholder="Ej: 3C8A1F50727C"
                  value={deviceCode}
                  onChange={(e) => setDeviceCode(e.target.value)}
                />
                <p className="mt-1 text-xs text-slate-400">Este codigo viene configurado en tu ESP32</p>
              </label>
              {error ? <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p> : null}
              <button
                className="flex h-11 w-full items-center justify-center gap-2 rounded-md bg-brand px-4 font-medium text-white disabled:opacity-60"
                disabled={linking || !deviceCode.trim() || !deviceName.trim()}
                onClick={handleLinkDevice}
                type="button"
              >
                {linking ? "Vinculando..." : "Vincular dispositivo"}
              </button>
            </div>
          ) : null}
        </section>
      </main>
    );
  }

  if (onboardingStep === 3) {
    return (
      <main className="grid min-h-screen place-items-center bg-panel px-4 py-8 text-ink">
        <section className="w-full max-w-md rounded-lg border border-line bg-white p-6 shadow-sm text-center">
          <div className="mx-auto mb-4 grid h-16 w-16 place-items-center rounded-full bg-green-100 text-green-700">
            <Zap size={32} />
          </div>
          <h2 className="text-xl font-semibold">Dispositivo configurado</h2>
          <p className="mt-2 text-sm text-slate-600">
            Tu dispositivo <strong>{deviceName}</strong> ya esta vinculado y listo para recibir datos.
          </p>
          <button
            className="mt-6 flex h-11 w-full items-center justify-center gap-2 rounded-md bg-brand px-4 font-medium text-white"
            onClick={() => { setOnboardingStep(4); void loadDashboard(token); }}
            type="button"
          >
            Ir al dashboard
          </button>
        </section>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-panel text-ink">
      <header className="border-b border-line bg-white">
        <div className="mx-auto flex max-w-4xl flex-wrap items-center justify-between gap-4 px-4 py-4">
          <div className="flex items-center gap-3">
            <div className="grid h-10 w-10 place-items-center rounded-md bg-brand text-white">
              <Zap size={21} />
            </div>
            <div>
              <h1 className="text-lg font-semibold">Energy IoT</h1>
              <p className="text-sm text-slate-500">{user.full_name}</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <span className="hidden items-center gap-3 text-sm text-slate-500 md:flex">
              {dbSize !== null ? <span className="text-xs text-slate-400">BD {dbSize.toFixed(1)} MB</span> : null}
              {lastUpdatedAt ? `Actualizado ${lastUpdatedAt.toLocaleTimeString("es-CO")}` : "Sin actualizar"}
            </span>
            <button
              className="inline-flex h-10 items-center gap-2 rounded-md border border-line bg-white px-3 text-sm font-medium"
              onClick={() => void loadDashboard()}
              type="button"
            >
              <RefreshCw size={16} />
              Actualizar
            </button>
            <button
              className="inline-flex h-10 w-10 items-center justify-center rounded-md border border-line bg-white"
              onClick={() => setShowSideMenu(true)}
              type="button"
            >
              <Menu size={18} />
            </button>
          </div>
        </div>
      </header>

      <section className="mx-auto max-w-4xl px-4 py-6">
        {error ? <p className="mb-4 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p> : null}

        {/* Device tabs at top */}
        <div className="mt-2">
          <div className="flex flex-wrap items-center gap-0 border-b border-line">
            {latest.map((lt) => (
              <button
                key={lt.device_id}
                className={`-mb-px px-5 py-2.5 text-sm font-medium transition-colors ${
                  selectedDeviceId === lt.device_id
                    ? "border-b-2 border-brand text-brand"
                    : "text-slate-500 hover:text-ink"
                }`}
                onClick={() => setSelectedDeviceId(lt.device_id)}
                type="button"
              >
                {lt.device_name}
              </button>
            ))}
            <span className="ml-auto flex items-center gap-2 px-2 text-xs text-slate-400">
              {latest.length} disp.
              <button
                className="inline-flex h-7 w-7 items-center justify-center rounded-md border border-line text-slate-500 hover:bg-slate-50"
                onClick={() => setSideSection("create-device")}
                type="button"
                title="Agregar dispositivo"
              >
                <Plus size={14} />
              </button>
            </span>
          </div>
        </div>

        {selectedDeviceId && deviceChannels.length > 0 ? (
          <>
            {/* Row 1: Phase cards with current, power, cost rate */}
            <div className="rounded-lg border border-line bg-white p-4 shadow-sm">
              <div className="flex flex-wrap gap-3">
                {deviceChannels.filter((ch) => ch.is_active).map((ch) => {
                  const lt = latest.find((l) => l.device_id === selectedDeviceId);
                  const currentVal = lt ? numeric(lt[`ch${ch.channel_number}` as keyof LatestTelemetry] as string | null) : 0;
                  const powerVal = currentVal * ch.voltage;
                  const costRate = (powerVal / 1000) * kwhRate;
                  return (
                    <div className="flex min-w-[240px] flex-1 items-center gap-4 rounded-md border border-line p-3" key={ch.id}>
                      <div>
                        <p className="text-xs font-medium text-slate-500">{ch.name}</p>
                        <p className="text-xs text-slate-400">{ch.voltage}V</p>
                      </div>
                      <div className="text-center">
                        <p className="text-xs text-slate-400">A</p>
                        <p className="text-4xl font-bold text-ink transition-all duration-200">{currentVal.toFixed(2)}</p>
                      </div>
                      <div className="text-center">
                        <p className="text-xs text-slate-400">W</p>
                        <p className="text-4xl font-bold text-brand transition-all duration-200">{powerVal.toFixed(1)}</p>
                      </div>
                      <div className="text-center">
                        <p className="text-xs text-slate-400">COP/h <span className="text-[10px] text-slate-300">instantáneo</span></p>
                        <p className="text-4xl font-bold text-accent transition-all duration-200">{Intl.NumberFormat("es-CO", { maximumFractionDigits: 0 }).format(costRate)}</p>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Row 2: Total power, daily energy & cost */}
            <div className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-3">
              <div className="rounded-lg border border-line bg-white p-4 shadow-sm">
                <p className="text-xs font-medium text-slate-500">Potencia total <span className="ml-1 inline-block h-2 w-2 rounded-full bg-green-500 animate-pulse" /></p>
                <p className="mt-1 text-3xl font-bold text-ink">
                  {deviceChannels.filter((ch) => ch.is_active).reduce((sum, ch) => {
                    const lt = latest.find((l) => l.device_id === selectedDeviceId);
                    const c = lt ? numeric(lt[`ch${ch.channel_number}` as keyof LatestTelemetry] as string | null) : 0;
                    return sum + c * ch.voltage;
                  }, 0).toFixed(0)} <span className="text-base font-normal text-slate-500">W</span>
                </p>
                <p className="mt-2 text-sm text-slate-400">Tarifa: $ {Intl.NumberFormat("es-CO").format(kwhRate)} / kWh</p>
              </div>
              <div className="rounded-lg border border-line bg-white p-4 shadow-sm">
                <p className="mb-1 text-xs font-medium text-slate-500">Energia del dia</p>
                {deviceChannels.filter((ch) => ch.is_active).map((ch) => {
                  const chData = channelDailyEnergy.find((d) => d.channel_number === ch.channel_number);
                  return (
                    <div className="flex justify-between text-xs" key={ch.id}>
                      <span className="text-slate-500">{ch.name}</span>
                      <span className="font-medium">{chData ? numeric(chData.energy_kwh).toFixed(2) : "0.00"} kWh</span>
                    </div>
                  );
                })}
                <div className="mt-1 flex justify-between border-t border-line pt-1 text-xs font-semibold">
                  <span>Total</span>
                  <span>{channelDailyEnergy.reduce((s, d) => s + numeric(d.energy_kwh), 0).toFixed(2)} kWh</span>
                </div>
              </div>
              <div className="rounded-lg border border-line bg-white p-4 shadow-sm">
                <p className="mb-1 text-xs font-medium text-slate-500">Costo del dia</p>
                {deviceChannels.filter((ch) => ch.is_active).map((ch) => {
                  const chData = channelDailyEnergy.find((d) => d.channel_number === ch.channel_number);
                  const chCost = chData ? numeric(chData.energy_kwh) * kwhRate : 0;
                  return (
                    <div className="flex justify-between text-xs" key={ch.id}>
                      <span className="text-slate-500">{ch.name}</span>
                      <span className="font-medium">$ {Intl.NumberFormat("es-CO", { maximumFractionDigits: 0 }).format(chCost)}</span>
                    </div>
                  );
                })}
                <div className="mt-1 flex justify-between border-t border-line pt-1 text-xs font-semibold">
                  <span>Total</span>
                  <span>$ {Intl.NumberFormat("es-CO", { maximumFractionDigits: 0 }).format(channelDailyEnergy.reduce((s, d) => s + numeric(d.energy_kwh), 0) * kwhRate)}</span>
                </div>
              </div>
            </div>
          </>
        ) : null}

        <div className="mt-4 overflow-x-auto">
            <Panel title="Corriente por canal (A) - Tiempo real">
              {currentBuffer.length === 0 ? (
                bufferLoading ? (
                  <div className="flex items-center justify-center py-8 text-sm text-slate-500">Cargando...</div>
                ) : (
                  <div className="flex items-center justify-center py-8 text-sm text-slate-500">Sin datos en los últimos {realtimeMinutes} minutos</div>
                )
              ) : (
                <Chart option={realtimeCurrentOption} />
              )}
              <div className="mt-1 flex items-center justify-between text-xs text-slate-400">
                <div className="flex gap-1">
                  {[10, 30, 60].map((m) => (
                    <button
                      key={m}
                      className={`rounded px-2 py-0.5 ${realtimeMinutes === m ? "bg-brand text-white" : "bg-slate-100 text-slate-500 hover:bg-slate-200"}`}
                      onClick={() => setRealtimeMinutes(m)}
                      type="button"
                    >
                      {m} min
                    </button>
                  ))}
                </div>
                <span>{currentBuffer.length} registros · actualiza cada 5s</span>
              </div>
            </Panel>
          </div>

        <div className="mt-6 overflow-x-auto">
          <Panel title="Corriente por canal (A) - Histórico">
            <div className="-mt-2 mb-4 flex flex-wrap items-center gap-3 text-xs">
              <label className="flex items-center gap-1">
                <span className="text-slate-400">Fecha</span>
                <input className="h-8 w-36 rounded border border-line px-2 text-xs outline-none focus:border-brand" type="date" value={dayDate} onChange={(e) => setDayDate(e.target.value)} />
              </label>
              <label className="flex items-center gap-1">
                <span className="text-slate-400">Desde</span>
                <input className="h-8 w-16 rounded border border-line px-2 text-xs outline-none focus:border-brand" type="number" min={0} max={23} value={channelHourFrom} onChange={(e) => setChannelHourFrom(Number(e.target.value))} onFocus={(e) => e.target.select()} />
              </label>
              <label className="flex items-center gap-1">
                <span className="text-slate-400">Hasta</span>
                <input className="h-8 w-16 rounded border border-line px-2 text-xs outline-none focus:border-brand" type="number" min={1} max={24} value={channelHourTo} onChange={(e) => setChannelHourTo(Number(e.target.value))} onFocus={(e) => e.target.select()} />
              </label>
              <span className="text-slate-300">{daySeries.length} registros{dayLoading ? " · cargando" : ""}</span>
            </div>
            <Chart option={channelsOption} />
          </Panel>
        </div>

        <div className="mt-6 grid grid-cols-1 gap-4 xl:grid-cols-2">
          <Panel title="Consumo del período">
            {(() => {
              const now = new Date();
              const dayOfWeek = now.getDay();
              const monOffset = dayOfWeek === 0 ? -6 : 1 - dayOfWeek;
              const monday = new Date(now);
              monday.setDate(now.getDate() + monOffset);
              const weekDays = Array.from({ length: 7 }, (_, i) => {
                const d = new Date(monday);
                d.setDate(monday.getDate() + i);
                const dateStr = d.toISOString().split("T")[0];
                const dayData = daily.filter((item) => item.period === dateStr);
                const kwh = dayData.reduce((s, item) => s + numeric(item.energy_kwh), 0);
                return {
                  label: d.toLocaleDateString("es-CO", { weekday: "short" }),
                  cost: Math.round(kwh * kwhRate),
                  kwh,
                };
              });
              const weekTotal = weekDays.reduce((s, d) => s + d.kwh, 0);
              const weekStart = monday.toLocaleDateString("es-CO", { day: "numeric", month: "short" });
              const weekEnd = new Date(monday);
              weekEnd.setDate(monday.getDate() + 6);
              const weekEndStr = weekEnd.toLocaleDateString("es-CO", { day: "numeric", month: "short" });
              return (
                <div className="space-y-2 text-sm">
                  <div className="mb-3">
                    <p className="text-3xl font-semibold text-brand">{weekTotal.toFixed(2)} <span className="text-lg font-normal text-slate-500">kWh</span></p>
                    <p className="mt-1 text-lg font-medium text-slate-600">$ {Intl.NumberFormat("es-CO").format(Math.round(weekTotal * kwhRate))}</p>
                  </div>
                  <p className="text-xs text-slate-400">{weekStart} → {weekEndStr} · semana actual</p>
                  <Chart option={{
                    grid: { left: 36, right: 8, top: 8, bottom: 28 },
                    xAxis: { type: "category", data: weekDays.map((d) => d.label), axisLabel: { fontSize: 9, color: "#526071" } },
                    yAxis: { type: "value", axisLabel: { fontSize: 9, color: "#526071" }, splitLine: { lineStyle: { color: "#e4e8ef" } } },
                    series: [{
                      type: "bar",
                      data: weekDays.map((d) => d.kwh),
                      itemStyle: { color: "#0f766e" },
                    }],
                    tooltip: {
                      trigger: "axis",
                      formatter: (params: any) => {
                        const p = params[0];
                        const cost = Math.round(p.value * kwhRate);
                        return `<strong>${p.name}</strong><br/>${p.value.toFixed(2)} kWh<br/>$ ${Intl.NumberFormat("es-CO").format(cost)}`;
                      },
                    },
                  }} />
                </div>
              );
            })()}
          </Panel>
          <Panel title="Comparativo mensual">
            {(() => {
              const now = new Date();
              const months = Array.from({ length: 6 }, (_, i) => {
                const d = new Date(now.getFullYear(), now.getMonth() - (5 - i), 1);
                const y = d.getFullYear();
                const m = String(d.getMonth() + 1).padStart(2, "0");
                const period = `${y}-${m}-01`;
                const found = billingMonthly.find((item) => item.period === period);
                const kwh = found ? numeric(found.energy_kwh) : 0;
                return {
                  label: d.toLocaleDateString("es-CO", { month: "short" }),
                  kwh,
                  cost: Math.round(kwh * kwhRate),
                };
              });
              const total6 = months.reduce((s, m) => s + m.kwh, 0);
              return (
                <div className="space-y-2 text-sm">
                  <div className="mb-3">
                    <p className="text-3xl font-semibold text-accent">{total6.toFixed(2)} <span className="text-lg font-normal text-slate-500">kWh</span></p>
                    <p className="mt-1 text-lg font-medium text-slate-600">$ {Intl.NumberFormat("es-CO").format(Math.round(total6 * kwhRate))}</p>
                  </div>
                  <p className="text-xs text-slate-400">Ultimos 6 meses</p>
                  <Chart option={{
                    grid: { left: 52, right: 8, top: 8, bottom: 28 },
                    xAxis: { type: "category", data: months.map((m) => m.label), axisLabel: { rotate: 90, fontSize: 9, color: "#526071" } },
                    yAxis: { type: "value", axisLabel: { fontSize: 9, color: "#526071" }, splitLine: { lineStyle: { color: "#e4e8ef" } } },
                    series: [{
                      type: "bar",
                      data: months.map((m) => m.kwh),
                      itemStyle: { color: "#2563eb" },
                    }],
                    tooltip: {
                      trigger: "axis",
                      formatter: (params: any) => {
                        const p = params[0];
                        const cost = Math.round(p.value * kwhRate);
                        return `<strong>${p.name}</strong><br/>${p.value.toFixed(2)} kWh<br/>$ ${Intl.NumberFormat("es-CO").format(cost)}`;
                      },
                    },
                  }} />
                </div>
              );
            })()}
          </Panel>
          <Panel title="Periodo actual">
            {(() => {
              const periodTotal = billingDaily.reduce((s, b) => s + numeric(b.energy_kwh), 0);
              const periodCost = periodTotal * kwhRate;
              const todayTotal = billingDaily.length > 0 ? numeric(billingDaily[billingDaily.length - 1].energy_kwh) : 0;
              const todayCost = todayTotal * kwhRate;
              const now = new Date();
              const billingDate = new Date(now.getFullYear(), now.getMonth(), billingStartDay);
              if (billingDate > now) billingDate.setMonth(billingDate.getMonth() - 1);
              const periodStart = billingDate.toLocaleDateString("es-CO", { day: "numeric", month: "short" });
              const todayStr = now.toLocaleDateString("es-CO", { day: "numeric", month: "short" });
              const daysInPeriod = Math.round((now.getTime() - billingDate.getTime()) / 86400000) + 1;
              const avgDaily = daysInPeriod > 0 ? periodTotal / daysInPeriod : 0;
              const nextBillingDate = new Date(now.getFullYear(), now.getMonth() + 1, billingStartDay);
              const remainingDays = Math.round((nextBillingDate.getTime() - now.getTime()) / 86400000);
              const projectedTotal = periodTotal + avgDaily * remainingDays;
              const projectedCost = projectedTotal * kwhRate;
              return (
                <div className="space-y-2 text-sm">
                  <div>
                    <p className="text-3xl font-semibold text-accent">{periodTotal.toFixed(2)} <span className="text-lg font-normal text-slate-500">kWh</span></p>
                    <p className="text-xs text-slate-400">Desde {periodStart} hasta {todayStr}</p>
                  </div>
                  <div className="mt-3 grid grid-cols-2 gap-2 rounded-md border border-line bg-slate-50 p-3 text-xs">
                    <div><span className="text-slate-500">Hoy</span><p className="font-semibold text-ink">$ {Intl.NumberFormat("es-CO").format(Math.round(todayCost))}</p></div>
                    <div><span className="text-slate-500">Periodo</span><p className="font-semibold text-ink">$ {Intl.NumberFormat("es-CO").format(Math.round(periodCost))}</p></div>
                    <div><span className="text-slate-500">Proyeccion mensual</span><p className="font-semibold text-ink">$ {Intl.NumberFormat("es-CO").format(Math.round(projectedCost))}</p></div>
                    <div><span className="text-slate-500">Restan {remainingDays} dias</span><p className="font-semibold text-brand">$ {Intl.NumberFormat("es-CO").format(Math.round(projectedCost - periodCost))}</p></div>
                  </div>
                  {billingMonthly.length > 0 && (
                    <div className="mt-3">
                      <Chart option={{
                        grid: { left: 36, right: 8, top: 8, bottom: 28 },
                        xAxis: { type: "category", data: billingMonthly.slice().reverse().map((m) => {
                          const d = new Date(m.period + "T00:00:00");
                          d.setDate(d.getDate() + billingStartDay - 1);
                          return d.toLocaleDateString("es-CO", { month: "short" });
                        }), axisLabel: { rotate: 90, fontSize: 9, color: "#526071" } },
                        yAxis: { type: "value", axisLabel: { fontSize: 9, color: "#526071" }, splitLine: { lineStyle: { color: "#e4e8ef" } } },
                        series: [{ type: "bar", data: billingMonthly.slice().reverse().map((m) => numeric(m.energy_kwh)), itemStyle: { color: "#2563eb" } }],
                        tooltip: { trigger: "axis" },
                      }} />
                    </div>
                  )}
                </div>
              );
            })()}
          </Panel>
        </div>

        <div className="mt-6">
          <Panel title="Estado de dispositivos">
            {newDeviceKey ? (
              <div className="mb-4 rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
                <p className="font-semibold">Clave MQTT creada para {newDeviceCode}</p>
                <p className="mt-1 break-all font-mono text-xs">{newDeviceKey}</p>
                <p className="mt-2 text-xs">
                  Guarda esta clave ahora. El backend solo almacena su hash y no la volvera a mostrar.
                </p>
              </div>
            ) : null}
            <div className="overflow-x-auto">
              <table className="w-full min-w-[560px] text-left text-sm">
                <thead className="border-b border-line text-slate-500">
                  <tr>
                    <th className="py-3 font-medium">Dispositivo</th>
                    <th className="py-3 font-medium">Codigo</th>
                    <th className="py-3 font-medium">Estado</th>
                    <th className="py-3 font-medium">Ultimo dato</th>
                  </tr>
                </thead>
                <tbody>
                  {devices.map((device) => (
                    <tr className="border-b border-slate-100" key={device.device_id}>
                      <td className="py-3 font-medium">{device.name}</td>
                      <td className="py-3 font-mono text-xs">{device.code}</td>
                      <td className="py-3">
                        <span className={`inline-flex items-center gap-1.5 text-xs font-medium ${device.is_online ? "text-green-600" : "text-slate-400"}`}>
                          <span className={`h-2 w-2 rounded-full ${device.is_online ? "bg-green-500" : "bg-slate-300"}`} />
                          {device.is_online ? "Online" : "Offline"}
                        </span>
                      </td>
                      <td className="py-3 text-slate-600">{formatDate(device.last_seen_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Panel>
        </div>
      </section>

      {/* Side menu */}
      {showSideMenu && (
        <div className="fixed inset-0 z-50" onClick={() => setShowSideMenu(false)}>
          <div className="absolute inset-0 bg-black/40" />
          <aside className="absolute right-0 top-0 h-full w-72 bg-white shadow-lg" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between border-b border-line px-4 py-3">
              <h2 className="text-base font-semibold">Menu</h2>
              <button className="text-sm text-slate-400 hover:text-ink" onClick={() => setShowSideMenu(false)} type="button">✕</button>
            </div>
            <div className="space-y-1 p-3">
              <SideMenuItem icon={<Settings size={18} />} label="Configurar canales" onClick={() => { setConfigChannels(deviceChannels.map((dc) => ({ ...dc }))); setSideSection("channels"); setShowSideMenu(false); }} />
              <SideMenuItem icon={<Plus size={18} />} label="Crear dispositivo" onClick={() => { setSideSection("create-device"); setShowSideMenu(false); }} />
              <SideMenuItem icon={<Zap size={18} />} label="Corte de dia" onClick={() => { setSideSection("billing-day"); setShowSideMenu(false); }} />
              <SideMenuItem icon={<Download size={18} />} label="Descargar Excel" onClick={() => { setSideSection("download"); setShowSideMenu(false); }} />
              {selectedDeviceId && <SideMenuItem icon={<Trash2 size={18} />} label="Eliminar dispositivo" onClick={() => { setSideSection("delete"); setShowSideMenu(false); }} />}
              <SideMenuItem icon={<DollarSign size={18} />} label="Tarifa kWh" onClick={() => { setSideSection("kwh-rate"); setShowSideMenu(false); }} />
              <SideMenuItem icon={<LogOut size={18} />} label="Salir" onClick={() => { setSideSection("logout"); setShowSideMenu(false); }} />
            </div>
          </aside>
        </div>
      )}

      {/* Overlay: Configurar canales */}
      {sideSection === "channels" && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={() => setSideSection(null)}>
          <section className="mx-4 w-full max-w-lg rounded-lg border border-line bg-white p-6 shadow-lg" onClick={(e) => e.stopPropagation()}>
            <h2 className="mb-4 text-lg font-semibold">Configurar canales</h2>
            <div className="space-y-3">
              {configChannels.map((ch, i) => (
                <div className="flex items-center gap-3" key={ch.channel_number}>
                  <input type="checkbox" className="h-5 w-5 accent-brand" checked={ch.is_active} onChange={() => { const next = [...configChannels]; next[i] = { ...next[i], is_active: !next[i].is_active }; setConfigChannels(next); }} />
                  <span className="w-20 text-sm text-slate-500">Canal {ch.channel_number}</span>
                  <input className="flex-1 h-10 rounded-md border border-line px-3 text-sm outline-none focus:border-brand" value={ch.name} onChange={(e) => { const next = [...configChannels]; next[i] = { ...next[i], name: e.target.value }; setConfigChannels(next); }} />
                  <select className="h-10 w-24 rounded-md border border-line px-2 text-sm outline-none focus:border-brand" value={ch.voltage} onChange={(e) => { const next = [...configChannels]; next[i] = { ...next[i], voltage: Number(e.target.value) }; setConfigChannels(next); }}>
                    <option value={110}>110 V</option>
                    <option value={220}>220 V</option>
                  </select>
                </div>
              ))}
            </div>
            {error ? <p className="mt-3 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p> : null}
            <div className="mt-4 flex gap-3">
              <button className="flex-1 h-11 rounded-md border border-line bg-white text-sm font-medium" onClick={() => setSideSection(null)} type="button">Cancelar</button>
              <button className="flex-1 h-11 rounded-md bg-brand text-sm font-medium text-white disabled:opacity-60" disabled={savingChannels} onClick={async () => {
                if (!token || !selectedDeviceId) return;
                setSavingChannels(true); setError("");
                try {
                  await Promise.all(configChannels.map((ch) => updateChannel(token, selectedDeviceId, ch.channel_number, { name: ch.name, voltage: ch.voltage, is_active: ch.is_active })));
                  setSideSection(null);
                  await loadDeviceChannels(selectedDeviceId);
                } catch (err) { setError(err instanceof Error ? err.message : "Error al guardar"); }
                finally { setSavingChannels(false); }
              }} type="button">{savingChannels ? "Guardando..." : "Guardar"}</button>
            </div>
          </section>
        </div>
      )}

      {/* Overlay: Crear dispositivo */}
      {sideSection === "create-device" && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={() => setSideSection(null)}>
          <section className="mx-4 w-full max-w-md rounded-lg border border-line bg-white p-6 shadow-lg" onClick={(e) => e.stopPropagation()}>
            <h2 className="mb-4 text-lg font-semibold">Crear dispositivo</h2>
            <form className="space-y-3" onSubmit={handleCreateDevice}>
              <input className="h-10 w-full rounded-md border border-line px-3 text-sm outline-none focus:border-brand" onChange={(e) => setCreateDeviceName(e.target.value)} placeholder="Nombre del dispositivo" required value={createDeviceName} />
              <input className="h-10 w-full rounded-md border border-line px-3 font-mono text-sm outline-none focus:border-brand" onChange={(e) => setCreateDeviceCode(e.target.value)} placeholder="codigo-mqtt" required value={createDeviceCode} />
              <button className="w-full h-11 rounded-md bg-brand text-sm font-medium text-white disabled:opacity-60" disabled={creatingDevice} type="submit">{creatingDevice ? "Creando..." : "Crear"}</button>
            </form>
            <button className="mt-3 w-full h-11 rounded-md border border-line bg-white text-sm font-medium" onClick={() => setSideSection(null)} type="button">Cancelar</button>
          </section>
        </div>
      )}

      {/* Overlay: Corte de dia */}
      {sideSection === "billing-day" && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={() => setSideSection(null)}>
          <section className="mx-4 w-full max-w-xs rounded-lg border border-line bg-white p-6 shadow-lg" onClick={(e) => e.stopPropagation()}>
            <h2 className="mb-4 text-lg font-semibold">Corte de dia de facturacion</h2>
            <p className="mb-3 text-sm text-slate-500">Dia del mes en que inicia tu periodo de facturacion</p>
            <input className="h-10 w-full rounded-md border border-line px-3 text-sm outline-none focus:border-brand" type="number" min={1} max={28} value={billingStartDay} onChange={(e) => { const v = Number(e.target.value); if (v >= 1 && v <= 28) { setBillingStartDay(v); localStorage.setItem("billing_start_day", String(v)); } }} />
            <button className="mt-4 w-full h-11 rounded-md border border-line bg-white text-sm font-medium" onClick={() => setSideSection(null)} type="button">Cerrar</button>
          </section>
        </div>
      )}

      {/* Overlay: Descargar Excel */}
      {sideSection === "download" && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={() => setSideSection(null)}>
          <section className="mx-4 w-full max-w-sm rounded-lg border border-line bg-white p-6 shadow-lg" onClick={(e) => e.stopPropagation()}>
            <h2 className="mb-4 text-lg font-semibold">Descargar Excel</h2>
            <div className="space-y-3">
              <label><span className="mb-1 block text-xs font-medium text-slate-600">Desde</span>
                <input className="h-10 w-full rounded-md border border-line px-3 text-sm outline-none focus:border-brand" type="datetime-local" value={rangeStart} onChange={(e) => setRangeStart(e.target.value)} />
              </label>
              <label><span className="mb-1 block text-xs font-medium text-slate-600">Hasta</span>
                <input className="h-10 w-full rounded-md border border-line px-3 text-sm outline-none focus:border-brand" type="datetime-local" value={rangeEnd} onChange={(e) => setRangeEnd(e.target.value)} />
              </label>
              <button className="w-full h-11 rounded-md bg-brand text-sm font-medium text-white" onClick={() => { const s = rangeStart ? new Date(rangeStart).toISOString() : undefined; const e = rangeEnd ? new Date(rangeEnd).toISOString() : undefined; downloadTelemetryExcel(token, s, e); setSideSection(null); }} type="button">
                <Download size={16} className="inline mr-1" /> Descargar
              </button>
            </div>
            <button className="mt-3 w-full h-11 rounded-md border border-line bg-white text-sm font-medium" onClick={() => setSideSection(null)} type="button">Cerrar</button>
          </section>
        </div>
      )}

      {/* Overlay: Eliminar dispositivo */}
      {sideSection === "delete" && selectedDeviceId && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={() => setSideSection(null)}>
          <section className="mx-4 w-full max-w-sm rounded-lg border border-line bg-white p-6 shadow-lg" onClick={(e) => e.stopPropagation()}>
            <h2 className="mb-4 text-lg font-semibold text-red-600">Eliminar dispositivo</h2>
            <p className="mb-4 text-sm text-slate-500">¿Esta seguro de eliminar este dispositivo? Se borraran todos sus datos.</p>
            <div className="flex gap-3">
              <button className="flex-1 h-11 rounded-md border border-line bg-white text-sm font-medium" onClick={() => setSideSection(null)} type="button">Cancelar</button>
              <button className="flex-1 h-11 rounded-md bg-red-600 text-sm font-medium text-white" onClick={async () => {
                try { await deleteDevice(token, selectedDeviceId); await loadDashboard(token); setSideSection(null); }
                catch { alert("Error al eliminar el dispositivo"); }
              }} type="button">Eliminar</button>
            </div>
          </section>
        </div>
      )}

      {/* Overlay: Salir */}
      {sideSection === "logout" && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={() => setSideSection(null)}>
          <section className="mx-4 w-full max-w-xs rounded-lg border border-line bg-white p-6 shadow-lg" onClick={(e) => e.stopPropagation()}>
            <h2 className="mb-4 text-lg font-semibold">Salir</h2>
            <p className="mb-4 text-sm text-slate-500">¿Cerrar sesion?</p>
            <div className="flex gap-3">
              <button className="flex-1 h-11 rounded-md border border-line bg-white text-sm font-medium" onClick={() => setSideSection(null)} type="button">Cancelar</button>
              <button className="flex-1 h-11 rounded-md bg-brand text-sm font-medium text-white" onClick={() => { setSideSection(null); logout(); }} type="button">Salir</button>
            </div>
          </section>
        </div>
      )}

      {/* Overlay: Tarifa kWh */}
      {sideSection === "kwh-rate" && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={() => setSideSection(null)}>
          <section className="mx-4 w-full max-w-sm rounded-lg border border-line bg-white p-6 shadow-lg" onClick={(e) => e.stopPropagation()}>
            <h2 className="mb-4 text-lg font-semibold">Tarifa kWh</h2>
            <p className="mb-3 text-sm text-slate-500">Costo por kWh en COP para calcular el valor de la energia consumida</p>
            <input className="h-10 w-full rounded-md border border-line px-3 text-sm outline-none focus:border-brand" type="number" min={100} max={9999} value={kwhRate} onChange={(e) => { const v = Number(e.target.value); if (v >= 100) { setKwhRate(v); localStorage.setItem("kwh_rate", String(v)); } }} />
            <button className="mt-4 w-full h-11 rounded-md border border-line bg-white text-sm font-medium" onClick={() => setSideSection(null)} type="button">Cerrar</button>
          </section>
        </div>
      )}
    </main>
  );
}

function Metric({
  title,
  value,
  icon,
  tone = "default"
}: {
  title: string;
  value: string | number;
  icon: ReactNode;
  tone?: "default" | "ok" | "warn";
}) {
  const toneClass = tone === "ok" ? "text-brand" : tone === "warn" ? "text-amber-600" : "text-accent";
  return (
    <div className="rounded-lg border border-line bg-white p-4 shadow-sm">
      <div className={`mb-3 flex h-9 w-9 items-center justify-center rounded-md bg-slate-100 ${toneClass}`}>{icon}</div>
      <p className="text-sm text-slate-500">{title}</p>
      <p className="mt-1 text-2xl font-semibold">{value}</p>
    </div>
  );
}

function Panel({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="rounded-lg border border-line bg-white p-4 shadow-sm">
      <h2 className="mb-3 text-base font-semibold">{title}</h2>
      {children}
    </section>
  );
}

function SideMenuItem({ icon, label, onClick }: { icon: ReactNode; label: string; onClick: () => void }) {
  return (
    <button
      className="flex w-full items-center gap-3 rounded-md px-3 py-2.5 text-sm text-slate-700 hover:bg-slate-100"
      onClick={onClick}
      type="button"
    >
      {icon}
      {label}
    </button>
  );
}
