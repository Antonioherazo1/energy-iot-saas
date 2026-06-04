import { Activity, Download, Gauge, LogOut, Plus, PlugZap, RefreshCw, Zap } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import type { FormEvent, ReactNode } from "react";
import type { EChartsOption } from "echarts";

import Chart from "./components/Chart";
import {
  createDevice,
  getChannelTimeSeries,
  getCurrentUser,
  getDashboardWebSocketUrl,
  getDailyEnergy,
  getDeviceStatus,
  getLatestTelemetry,
  getMonthlyEnergy,
  getOrganizations,
  getSummary,
  login,
  downloadTelemetryCsv,
} from "./lib/api";
import type { DashboardSummary, DeviceStatus, EnergyBucket, LatestTelemetry, Organization, User } from "./types";

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
  const [email, setEmail] = useState("admin@thinc.site.com");
  const [password, setPassword] = useState("");
  const [user, setUser] = useState<User | null>(null);
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [devices, setDevices] = useState<DeviceStatus[]>([]);
  const [latest, setLatest] = useState<LatestTelemetry[]>([]);
  const [daily, setDaily] = useState<EnergyBucket[]>([]);
  const [monthly, setMonthly] = useState<EnergyBucket[]>([]);
  const [channelData, setChannelData] = useState<LatestTelemetry[]>([]);
  const [organizations, setOrganizations] = useState<Organization[]>([]);
  const [deviceName, setDeviceName] = useState("");
  const [deviceCode, setDeviceCode] = useState("");
  const [newDeviceKey, setNewDeviceKey] = useState("");
  const [newDeviceCode, setNewDeviceCode] = useState("");
  const [lastUpdatedAt, setLastUpdatedAt] = useState<Date | null>(null);
  const [loading, setLoading] = useState(false);
  const [creatingDevice, setCreatingDevice] = useState(false);
  const [error, setError] = useState("");
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
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo cargar el dashboard");
      setUser(null);
      localStorage.removeItem(tokenKey);
      setToken("");
    } finally {
      setLoading(false);
    }
  }

  async function handleLogin(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setError("");
    try {
      const response = await login(email, password);
      localStorage.setItem(tokenKey, response.access_token);
      localStorage.setItem(refreshKey, response.refresh_token);
      setToken(response.access_token);
      await loadDashboard(response.access_token);
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
      const createdDevice = await createDevice(token, organizationId, deviceName.trim(), deviceCode.trim());
      setDeviceName("");
      setDeviceCode("");
      setNewDeviceCode(createdDevice.code);
      setNewDeviceKey(createdDevice.device_key);
      await loadDashboard(token);
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo crear el dispositivo");
    } finally {
      setCreatingDevice(false);
    }
  }

  useEffect(() => {
    if (token) {
      void loadDashboard(token);
    }
  }, []);

  useEffect(() => {
    if (!token || !user) {
      return;
    }
    const interval = window.setInterval(() => {
      void loadDashboard(token);
    }, 10000);
    return () => window.clearInterval(interval);
  }, [token, user]);

  useEffect(() => {
    if (!token || !user) {
      return;
    }

    const socket = new WebSocket(getDashboardWebSocketUrl());
    socket.onmessage = () => {
      if (realtimeReloadRef.current) {
        window.clearTimeout(realtimeReloadRef.current);
      }
      realtimeReloadRef.current = window.setTimeout(() => {
        void loadDashboard(token);
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
  }, [token, user]);

  const powerChartOption = useMemo<EChartsOption>(() => {
    return {
      grid: { left: 42, right: 16, top: 28, bottom: 34 },
      tooltip: { trigger: "axis" },
      xAxis: {
        type: "category",
        data: latest.map((item) => item.device_name),
        axisLabel: { color: "#526071" }
      },
      yAxis: {
        type: "value",
        axisLabel: { color: "#526071" },
        splitLine: { lineStyle: { color: "#e4e8ef" } }
      },
      series: [
        {
          type: "bar",
          data: latest.map((item) => numeric(item.power)),
          itemStyle: { color: "#0f766e", borderRadius: [4, 4, 0, 0] },
          name: "Potencia W"
        }
      ]
    };
  }, [latest]);

  const dailyEnergyOption = useMemo<EChartsOption>(() => {
    return {
      grid: { left: 42, right: 16, top: 28, bottom: 34 },
      tooltip: { trigger: "axis" },
      xAxis: {
        type: "category",
        data: daily.map((item) => item.period),
        axisLabel: { color: "#526071" }
      },
      yAxis: {
        type: "value",
        axisLabel: { color: "#526071" },
        splitLine: { lineStyle: { color: "#e4e8ef" } }
      },
      series: [
        {
          type: "line",
          smooth: true,
          areaStyle: { color: "rgba(37, 99, 235, 0.12)" },
          lineStyle: { color: "#2563eb", width: 3 },
          symbolSize: 7,
          data: daily.map((item) => numeric(item.energy_kwh)),
          name: "kWh diario"
        }
      ]
    };
  }, [daily]);

  const channelsOption = useMemo<EChartsOption>(() => {
    const labels = channelData.map((_, i) => `#${i + 1}`);
    return {
      grid: { left: 42, right: 16, top: 36, bottom: 34 },
      tooltip: { trigger: "axis" },
      legend: { bottom: 0, textStyle: { color: "#526071", fontSize: 11 }, icon: "circle" },
      xAxis: {
        type: "category",
        data: labels,
        axisLabel: { color: "#526071", fontSize: 10, show: false },
      },
      yAxis: {
        type: "value",
        name: "Amperios",
        axisLabel: { color: "#526071" },
        splitLine: { lineStyle: { color: "#e4e8ef" } },
      },
      series: [
        {
          type: "line", smooth: true, symbol: "none", name: "CH1",
          data: channelData.map((d) => numeric(d.ch1)),
          lineStyle: { color: "#0f766e", width: 2 },
        },
        {
          type: "line", smooth: true, symbol: "none", name: "CH2",
          data: channelData.map((d) => numeric(d.ch2)),
          lineStyle: { color: "#2563eb", width: 2 },
        },
        {
          type: "line", smooth: true, symbol: "none", name: "CH3",
          data: channelData.map((d) => numeric(d.ch3)),
          lineStyle: { color: "#d97706", width: 2 },
        },
        {
          type: "line", smooth: true, symbol: "none", name: "CH4",
          data: channelData.map((d) => numeric(d.ch4)),
          lineStyle: { color: "#dc2626", width: 2 },
        },
      ],
    };
  }, [channelData]);

  const monthlyEnergyOption = useMemo<EChartsOption>(() => {
    return {
      grid: { left: 42, right: 16, top: 28, bottom: 34 },
      tooltip: { trigger: "axis" },
      xAxis: {
        type: "category",
        data: monthly.map((item) => item.period.slice(0, 7)),
        axisLabel: { color: "#526071" }
      },
      yAxis: {
        type: "value",
        axisLabel: { color: "#526071" },
        splitLine: { lineStyle: { color: "#e4e8ef" } }
      },
      series: [
        {
          type: "bar",
          data: monthly.map((item) => numeric(item.energy_kwh)),
          itemStyle: { color: "#334155", borderRadius: [4, 4, 0, 0] },
          name: "kWh mensual"
        }
      ]
    };
  }, [monthly]);

  if (!token || !user) {
    return (
      <main className="grid min-h-screen place-items-center bg-panel px-4 py-8 text-ink">
        <section className="w-full max-w-md rounded-lg border border-line bg-white p-6 shadow-sm">
          <div className="mb-6 flex items-center gap-3">
            <div className="grid h-11 w-11 place-items-center rounded-md bg-brand text-white">
              <Zap size={22} />
            </div>
            <div>
              <h1 className="text-xl font-semibold">Energy IoT</h1>
              <p className="text-sm text-slate-500">Panel industrial de monitoreo</p>
            </div>
          </div>

          <form className="space-y-4" onSubmit={handleLogin}>
            <label className="block">
              <span className="mb-1 block text-sm font-medium">Email</span>
              <input
                className="h-11 w-full rounded-md border border-line px-3 outline-none focus:border-brand"
                type="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                required
              />
            </label>
            <label className="block">
              <span className="mb-1 block text-sm font-medium">Password</span>
              <input
                className="h-11 w-full rounded-md border border-line px-3 outline-none focus:border-brand"
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                required
              />
            </label>
            {error ? <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p> : null}
            <button
              className="flex h-11 w-full items-center justify-center gap-2 rounded-md bg-brand px-4 font-medium text-white disabled:opacity-60"
              disabled={loading}
              type="submit"
            >
              <PlugZap size={18} />
              Entrar
            </button>
          </form>
        </section>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-panel text-ink">
      <header className="border-b border-line bg-white">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-4 px-4 py-4">
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
              onClick={() => downloadTelemetryCsv(token)}
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

      <section className="mx-auto max-w-7xl px-4 py-6">
        {error ? <p className="mb-4 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p> : null}

        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
          <Metric title="Dispositivos" value={summary?.total_devices ?? 0} icon={<Gauge size={18} />} />
          <Metric title="Online" value={summary?.online_devices ?? 0} icon={<Activity size={18} />} tone="ok" />
          <Metric title="Offline" value={summary?.offline_devices ?? 0} icon={<Activity size={18} />} tone="warn" />
          <Metric title="Potencia actual" value={formatNumber(summary?.current_power, " W")} icon={<Zap size={18} />} />
          <Metric title="Energia acumulada" value={formatNumber(summary?.latest_energy_kwh, " kWh")} icon={<PlugZap size={18} />} />
        </div>

        <div className="mt-6 grid gap-4 xl:grid-cols-3">
          <Panel title="Potencia por dispositivo">
            <Chart option={powerChartOption} />
          </Panel>
          <Panel title="Consumo diario">
            <Chart option={dailyEnergyOption} />
          </Panel>
          <Panel title="Consumo mensual">
            <Chart option={monthlyEnergyOption} />
          </Panel>
        </div>

        <div className="mt-6">
          <Panel title="Corriente por canal (A)">
            <Chart option={channelsOption} />
          </Panel>
        </div>

        <div className="mt-6 grid gap-4 xl:grid-cols-[1fr_1.4fr]">
          <Panel title="Estado de dispositivos">
            <form className="mb-4 grid gap-3 rounded-md border border-line bg-slate-50 p-3 md:grid-cols-[1fr_1fr_auto]" onSubmit={handleCreateDevice}>
              <input
                className="h-10 rounded-md border border-line px-3 text-sm outline-none focus:border-brand"
                onChange={(event) => setDeviceName(event.target.value)}
                placeholder="Nombre del dispositivo"
                required
                value={deviceName}
              />
              <input
                className="h-10 rounded-md border border-line px-3 font-mono text-sm outline-none focus:border-brand"
                onChange={(event) => setDeviceCode(event.target.value)}
                placeholder="codigo-mqtt"
                required
                value={deviceCode}
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

          <Panel title="Ultima telemetria">
            <div className="overflow-x-auto">
              <table className="w-full min-w-[920px] text-left text-sm">
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
                  {latest.map((item) => (
                    <tr className="border-b border-slate-100" key={item.device_id}>
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
