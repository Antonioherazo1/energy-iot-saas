import { Activity, Download, Gauge, LogOut, Plus, PlugZap, RefreshCw, Zap } from "lucide-react";
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
  downloadTelemetryCsv,
  getTelemetryByRange,
  getChannelDaySeries,
  deleteDevice,
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
  const [showChannelConfig, setShowChannelConfig] = useState(false);
  const [configChannels, setConfigChannels] = useState<DeviceChannel[]>([]);
  const [savingChannels, setSavingChannels] = useState(false);
  const [rangeStart, setRangeStart] = useState("");
  const [rangeEnd, setRangeEnd] = useState("");
  const [rangeData, setRangeData] = useState<LatestTelemetry[]>([]);
  const [rangeLoading, setRangeLoading] = useState(false);
  const realtimeReloadRef = useRef<number | null>(null);

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
    try {
      const data = await getRealtimeCurrents(token, selectedDeviceId, realtimeMinutes);
      setCurrentBuffer(data);
    } catch {
      // ignore
    }
  }

  useEffect(() => {
    if (!selectedDeviceId) return;
    setCurrentBuffer([]);
    void loadRealtimeBuffer();
    const interval = window.setInterval(loadRealtimeBuffer, 5000);
    return () => window.clearInterval(interval);
  }, [token, selectedDeviceId, realtimeMinutes]);

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

    const activeChannels = deviceChannels.length > 0
      ? deviceChannels.filter((ch) => ch.is_active)
      : [1, 2, 3, 4].map((n) => ({
          id: `ch${n}`,
          channel_number: n,
          name: `Canal ${n}`,
          voltage: 110,
          is_active: true,
        })) as DeviceChannel[];

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
            <span className="hidden text-sm text-slate-500 md:inline">
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
              className="inline-flex h-10 items-center gap-2 rounded-md border border-line bg-white px-3 text-sm font-medium"
              onClick={() => {
                const startUtc = rangeStart ? new Date(rangeStart).toISOString() : undefined;
                const endUtc = rangeEnd ? new Date(rangeEnd).toISOString() : undefined;
                downloadTelemetryCsv(token, startUtc, endUtc);
              }}
              type="button"
            >
              <Download size={16} />
              CSV
            </button>
            <button
              className="inline-flex h-10 items-center gap-2 rounded-md border border-line bg-white px-3 text-sm font-medium"
              onClick={logout}
              type="button"
            >
              <LogOut size={16} />
              Salir
            </button>
          </div>
        </div>
      </header>

      <section className="mx-auto max-w-4xl px-4 py-6">
        {error ? <p className="mb-4 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p> : null}

        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-5">
          <Metric title="Dispositivos" value={summary?.total_devices ?? 0} icon={<Gauge size={18} />} />
          <Metric title="Online" value={summary?.online_devices ?? 0} icon={<Activity size={18} />} tone="ok" />
          <Metric title="Offline" value={summary?.offline_devices ?? 0} icon={<Activity size={18} />} tone="warn" />
          <Metric title="Potencia actual" value={formatNumber(summary?.current_power, " W")} icon={<Zap size={18} />} />
          <Metric title="Energia acumulada" value={formatNumber(summary?.latest_energy_kwh, " kWh")} icon={<PlugZap size={18} />} />
        </div>

        <div className="mt-6">
          <div className="flex flex-wrap gap-2 border-b border-line pb-2">
            {latest.map((lt) => (
              <button
                key={lt.device_id}
                className={`rounded-md px-4 py-2 text-sm font-medium ${
                  selectedDeviceId === lt.device_id
                    ? "bg-brand text-white"
                    : "bg-white text-ink border border-line hover:bg-slate-50"
                }`}
                onClick={() => setSelectedDeviceId(lt.device_id)}
                type="button"
              >
                {lt.device_name}
              </button>
            ))}
            {selectedDeviceId && (
              <button
                className="rounded-md px-4 py-2 text-sm font-medium border border-line bg-white text-ink hover:bg-slate-50"
                onClick={() => {
                  setConfigChannels(deviceChannels.length > 0 ? deviceChannels.map(ch => ({ ...ch, voltage: Number(ch.voltage) })) : [1,2,3,4].map(n => ({ id: `new-${n}`, device_id: selectedDeviceId, channel_number: n, name: `Canal ${n}`, voltage: 110, is_active: true } as DeviceChannel)));
                  setShowChannelConfig(true);
                }}
                type="button"
              >
                Configurar canales
              </button>
            )}
            {selectedDeviceId && (
              <button
                className="rounded-md px-4 py-2 text-sm font-medium border border-red-200 bg-white text-red-600 hover:bg-red-50"
                onClick={async () => {
                  if (!window.confirm("¿Eliminar este dispositivo? Se borrarán todos sus datos.")) return;
                  try {
                    await deleteDevice(token, selectedDeviceId);
                    await loadDashboard(token);
                  } catch {
                    alert("Error al eliminar el dispositivo");
                  }
                }}
                type="button"
              >
                Eliminar
              </button>
            )}
          </div>
        </div>

        {selectedDeviceId && deviceChannels.length > 0 ? (
          <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
            {deviceChannels.filter((ch) => ch.is_active).map((ch) => {
              const lt = latest.find((l) => l.device_id === selectedDeviceId);
              const currentVal = lt ? numeric(lt[`ch${ch.channel_number}` as keyof LatestTelemetry] as string | null) : 0;
              const powerVal = currentVal * ch.voltage;
              const energyVal = lt ? numeric(lt[`ch${ch.channel_number}_energy_kwh` as keyof LatestTelemetry] as string | null) : 0;
              return (
                <Panel key={ch.id} title={`${ch.name}`}>
                  <div className="space-y-1 text-sm">
                    <p className="text-xs text-slate-500">{ch.voltage} V</p>
                    <p><span className="font-semibold">{currentVal.toFixed(2)}</span> A</p>
                    <p><span className="font-semibold">{powerVal.toFixed(1)}</span> W</p>
                    <p className="text-xs text-slate-500">{energyVal.toFixed(6)} kWh</p>
                  </div>
                </Panel>
              );
            })}
          </div>
        ) : null}

        <div className="mt-4 overflow-x-auto">
            <Panel title="Corriente por canal (A) - Tiempo real">
              {bufferLoading ? (
                <div className="flex items-center justify-center py-8 text-sm text-slate-500">Cargando...</div>
              ) : currentBuffer.length === 0 ? (
                <div className="flex items-center justify-center py-8 text-sm text-slate-500">Sin datos en los últimos {realtimeMinutes} minutos</div>
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
          <div className="flex flex-wrap items-end gap-4 mb-3">
            <div>
              <label className="mb-1 block text-xs font-medium text-slate-600">Fecha</label>
              <input
                className="h-10 w-40 rounded-md border border-line px-3 text-sm outline-none focus:border-brand"
                type="date"
                value={dayDate}
                onChange={(e) => setDayDate(e.target.value)}
              />
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-slate-600">Hora desde</label>
              <input
                className="h-10 w-24 rounded-md border border-line px-3 text-sm outline-none focus:border-brand"
                type="number" min={0} max={23}
                value={channelHourFrom}
                onChange={(e) => setChannelHourFrom(Number(e.target.value))}
                onFocus={(e) => e.target.select()}
              />
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-slate-600">Hora hasta</label>
              <input
                className="h-10 w-24 rounded-md border border-line px-3 text-sm outline-none focus:border-brand"
                type="number" min={1} max={24}
                value={channelHourTo}
                onChange={(e) => setChannelHourTo(Number(e.target.value))}
                onFocus={(e) => e.target.select()}
              />
            </div>
            {selectedDeviceId && deviceChannels.length > 0 ? (
              <span className="pb-2 text-xs text-slate-500">
                {daySeries.length} registros{dayLoading ? " · cargando..." : ""}
              </span>
            ) : null}
          </div>
          <Panel title="Corriente por canal (A) - Histórico">
            <Chart option={channelsOption} />
          </Panel>
        </div>

        <div className="mt-6 grid grid-cols-1 gap-4 xl:grid-cols-3">
          <Panel title="Energia por canal (kWh) - Hoy">
            <div className="space-y-2 text-sm">
              {deviceChannels.filter((ch) => ch.is_active).length > 0 ? (
                deviceChannels.filter((ch) => ch.is_active).map((ch) => {
                  const chData = channelDailyEnergy.find((d) => d.channel_number === ch.channel_number);
                  const energy = chData ? numeric(chData.energy_kwh) : 0;
                  return (
                    <div className="flex justify-between border-b border-slate-100 py-1" key={ch.channel_number}>
                      <span className="text-slate-600">{ch.name}</span>
                      <span className="font-semibold">{energy.toFixed(2)} kWh</span>
                    </div>
                  );
                })
              ) : (
                <p className="text-slate-400">Selecciona un dispositivo con canales configurados</p>
              )}
            </div>
          </Panel>
          <Panel title="Consumo del período">
            {(() => {
              const periodTotal = billingDaily.reduce((s, b) => s + numeric(b.energy_kwh), 0);
              const days = billingDaily.map((d) => {
                const parts = d.period.split("-");
                return parts.length >= 3 ? `${parts[2]}/${parts[1]}` : d.period;
              });
              const vals = billingDaily.map((d) => numeric(d.energy_kwh));
              const dayCount = billingDaily.length;
              const avgDaily = dayCount > 0 ? periodTotal / dayCount : 0;
              const now = new Date();
              const billingDate = new Date(now.getFullYear(), now.getMonth(), billingStartDay);
              if (billingDate > now) billingDate.setMonth(billingDate.getMonth() - 1);
              const periodStartStr = billingDate.toLocaleDateString("es-CO", { day: "numeric", month: "short" });
              const todayStr = now.toLocaleDateString("es-CO", { day: "numeric", month: "short" });
              return (
                <div className="space-y-2 text-sm">
                  <p className="text-3xl font-semibold text-brand">{periodTotal.toFixed(2)} <span className="text-lg font-normal text-slate-500">kWh</span></p>
                  <p className="text-xs text-slate-400">{periodStartStr} → {todayStr} · ~{avgDaily.toFixed(1)} kWh/día</p>
                  {billingDaily.length > 0 && (
                    <Chart option={{
                      grid: { left: 36, right: 8, top: 8, bottom: 28 },
                      xAxis: { type: "category", data: days, axisLabel: { rotate: 90, fontSize: 9, color: "#526071", interval: Math.max(1, Math.floor(days.length / 15)) } },
                      yAxis: { type: "value", axisLabel: { fontSize: 9, color: "#526071" }, splitLine: { lineStyle: { color: "#e4e8ef" } } },
                      series: [{ type: "bar", data: vals, itemStyle: { color: "#0f766e" } }],
                      tooltip: { trigger: "axis" },
                    }} />
                  )}
                </div>
              );
            })()}
          </Panel>
          <Panel title="Comparativo mensual">
            {(() => {
              const periodTotal = billingDaily.reduce((s, b) => s + numeric(b.energy_kwh), 0);
              const now = new Date();
              const billingDate = new Date(now.getFullYear(), now.getMonth(), billingStartDay);
              if (billingDate > now) billingDate.setMonth(billingDate.getMonth() - 1);
              const periodStart = billingDate.toLocaleDateString("es-CO", { day: "numeric", month: "short" });
              const todayStr = now.toLocaleDateString("es-CO", { day: "numeric", month: "short" });
              return (
                <div className="space-y-2 text-sm">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-3xl font-semibold text-accent">{periodTotal.toFixed(2)} <span className="text-lg font-normal text-slate-500">kWh</span></p>
                      <p className="text-xs text-slate-400">Desde {periodStart} hasta {todayStr}</p>
                    </div>
                    <div className="flex items-center gap-1 text-xs">
                      <span className="text-slate-400">Corte dia</span>
                      <input
                        className="h-7 w-12 rounded border border-line px-2 text-center text-xs outline-none focus:border-brand"
                        type="number" min={1} max={28}
                        value={billingStartDay}
                        onChange={(e) => {
                          const v = Number(e.target.value);
                          if (v >= 1 && v <= 28) {
                            setBillingStartDay(v);
                            localStorage.setItem("billing_start_day", String(v));
                          }
                        }}
                      />
                    </div>
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

        <div className="mt-6 grid grid-cols-1 gap-4 xl:grid-cols-[1fr_1.4fr]">
          <Panel title="Estado de dispositivos">
            <form className="mb-4 grid gap-3 rounded-md border border-line bg-slate-50 p-3 md:grid-cols-[1fr_1fr_auto]" onSubmit={handleCreateDevice}>
              <input
                className="h-10 rounded-md border border-line px-3 text-sm outline-none focus:border-brand"
                onChange={(event) => setCreateDeviceName(event.target.value)}
                placeholder="Nombre del dispositivo"
                required
                value={createDeviceName}
              />
              <input
                className="h-10 rounded-md border border-line px-3 font-mono text-sm outline-none focus:border-brand"
                onChange={(event) => setCreateDeviceCode(event.target.value)}
                placeholder="codigo-mqtt"
                required
                value={createDeviceCode}
              />
              <button
                className="inline-flex h-10 items-center justify-center gap-2 rounded-md bg-brand px-3 text-sm font-medium text-white disabled:opacity-60"
                disabled={creatingDevice}
                type="submit"
              >
                <Plus size={16} />
                Crear
              </button>
            </form>
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
                        <span className={device.is_online ? "status-ok" : "status-off"}>{device.is_online ? "Online" : "Offline"}</span>
                      </td>
                      <td className="py-3 text-slate-600">{formatDate(device.last_seen_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Panel>

          <Panel title="Telemetria por rango">
            <div className="mb-4 flex flex-wrap items-end gap-2 rounded-md border border-line bg-slate-50 p-3">
              <label className="flex-1 min-w-[180px]">
                <span className="mb-1 block text-xs font-medium text-slate-600">Desde</span>
                <input
                  className="h-10 w-full rounded-md border border-line px-3 text-sm outline-none focus:border-brand"
                  type="datetime-local"
                  value={rangeStart}
                  onChange={(e) => setRangeStart(e.target.value)}
                />
              </label>
              <label className="flex-1 min-w-[180px]">
                <span className="mb-1 block text-xs font-medium text-slate-600">Hasta</span>
                <input
                  className="h-10 w-full rounded-md border border-line px-3 text-sm outline-none focus:border-brand"
                  type="datetime-local"
                  value={rangeEnd}
                  onChange={(e) => setRangeEnd(e.target.value)}
                />
              </label>
              <button
                className="inline-flex h-10 items-center gap-2 rounded-md bg-brand px-4 text-sm font-medium text-white disabled:opacity-60"
                disabled={rangeLoading}
                onClick={loadRange}
                type="button"
              >
                <RefreshCw size={16} />
                Consultar
              </button>
              <button
                className="inline-flex h-10 items-center gap-2 rounded-md border border-line bg-white px-3 text-sm font-medium"
                onClick={() => {
                  const startUtc = rangeStart ? new Date(rangeStart).toISOString() : undefined;
                  const endUtc = rangeEnd ? new Date(rangeEnd).toISOString() : undefined;
                  downloadTelemetryCsv(token, startUtc, endUtc);
                }}
                type="button"
              >
                <Download size={16} />
                CSV
              </button>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[640px] text-left text-sm">
                <thead className="border-b border-line text-slate-500">
                  <tr>
                    <th className="py-3 font-medium">Dispositivo</th>
                    <th className="py-3 font-medium">CH1 (A)</th>
                    <th className="py-3 font-medium">CH2 (A)</th>
                    <th className="py-3 font-medium">CH3 (A)</th>
                    <th className="py-3 font-medium">CH4 (A)</th>
                    <th className="py-3 font-medium">Potencia</th>
                    <th className="py-3 font-medium">kWh</th>
                    <th className="py-3 font-medium">Fecha</th>
                  </tr>
                </thead>
                <tbody>
                  {rangeData.length === 0 ? (
                    <tr><td className="py-6 text-center text-slate-400" colSpan={8}>Selecciona un rango y presiona Consultar</td></tr>
                  ) : rangeData.map((item, i) => (
                    <tr className="border-b border-slate-100" key={`${item.device_id}-${i}`}>
                      <td className="py-3 font-medium">{item.device_name}</td>
                      <td className="py-3">{formatNumber(item.ch1, " A")}</td>
                      <td className="py-3">{formatNumber(item.ch2, " A")}</td>
                      <td className="py-3">{formatNumber(item.ch3, " A")}</td>
                      <td className="py-3">{formatNumber(item.ch4, " A")}</td>
                      <td className="py-3">{formatNumber(item.power, " W")}</td>
                      <td className="py-3">{formatNumber(item.energy_kwh, " kWh")}</td>
                      <td className="py-3 text-slate-600">{formatDate(item.recorded_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Panel>
        </div>
      </section>

      {showChannelConfig ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={() => setShowChannelConfig(false)}>
          <section className="mx-4 w-full max-w-lg rounded-lg border border-line bg-white p-6 shadow-lg" onClick={(e) => e.stopPropagation()}>
            <h2 className="mb-4 text-lg font-semibold">Configurar canales</h2>
            <div className="space-y-3">
              {configChannels.map((ch, i) => (
                <div className="flex items-center gap-3" key={ch.channel_number}>
                  <input
                    type="checkbox"
                    className="h-5 w-5 accent-brand"
                    checked={ch.is_active}
                    onChange={() => {
                      const next = [...configChannels];
                      next[i] = { ...next[i], is_active: !next[i].is_active };
                      setConfigChannels(next);
                    }}
                  />
                  <span className="w-20 text-sm text-slate-500">Canal {ch.channel_number}</span>
                  <input
                    className="flex-1 h-10 rounded-md border border-line px-3 text-sm outline-none focus:border-brand"
                    value={ch.name}
                    onChange={(e) => {
                      const next = [...configChannels];
                      next[i] = { ...next[i], name: e.target.value };
                      setConfigChannels(next);
                    }}
                  />
                  <select
                    className="h-10 w-24 rounded-md border border-line px-2 text-sm outline-none focus:border-brand"
                    value={ch.voltage}
                    onChange={(e) => {
                      const next = [...configChannels];
                      next[i] = { ...next[i], voltage: Number(e.target.value) };
                      setConfigChannels(next);
                    }}
                  >
                    <option value={110}>110 V</option>
                    <option value={220}>220 V</option>
                  </select>
                </div>
              ))}
            </div>
            {error ? <p className="mt-3 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p> : null}
            <div className="mt-4 flex gap-3">
              <button
                className="flex-1 h-11 rounded-md border border-line bg-white text-sm font-medium"
                onClick={() => setShowChannelConfig(false)}
                type="button"
              >
                Cancelar
              </button>
              <button
                className="flex-1 h-11 rounded-md bg-brand text-sm font-medium text-white disabled:opacity-60"
                disabled={savingChannels}
                onClick={async () => {
                  if (!token || !selectedDeviceId) return;
                  setSavingChannels(true);
                  setError("");
                  try {
                    await Promise.all(
                      configChannels.map((ch) =>
                        updateChannel(token, selectedDeviceId, ch.channel_number, {
                          name: ch.name,
                          voltage: ch.voltage,
                          is_active: ch.is_active,
                        })
                      )
                    );
                    setShowChannelConfig(false);
                    await loadDeviceChannels(selectedDeviceId);
                  } catch (err) {
                    setError(err instanceof Error ? err.message : "Error al guardar");
                  } finally {
                    setSavingChannels(false);
                  }
                }}
                type="button"
              >
                {savingChannels ? "Guardando..." : "Guardar"}
              </button>
            </div>
          </section>
        </div>
      ) : null}
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
