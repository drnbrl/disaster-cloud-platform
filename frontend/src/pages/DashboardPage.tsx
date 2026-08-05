import { useQuery } from "@tanstack/react-query";
import { Link, useNavigate } from "react-router-dom";
import { Bar, BarChart, CartesianGrid, Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { TooltipProps } from "recharts";
import { getDashboard, updateRequestStatus } from "../api";
import { logout } from "../auth";
import { MapView } from "../components/MapView";
import { PriorityBadge } from "../components/PriorityBadge";
import type { DisasterRequest, GlobalStats, PriorityLevel, RequestStatus } from "../types";

const statuses: RequestStatus[] = ["RECEIVED", "REVIEWED", "ASSIGNED", "IN_PROGRESS", "RESOLVED", "REJECTED"];
type PriorityStatKey = "lowRequests" | "mediumRequests" | "highRequests" | "criticalRequests";

const emptyGlobalStats: GlobalStats = {
  totalRequests: 0,
  criticalRequests: 0,
  highRequests: 0,
  mediumRequests: 0,
  lowRequests: 0,
  waterRequests: 0,
  foodRequests: 0,
  shelterRequests: 0,
  medicalRequests: 0,
  electricityRequests: 0,
  babySupportRequests: 0,
  affectedPeople: 0,
  injuredPeople: 0
};

const priorityCategories: Array<{ level: PriorityLevel; name: string; color: string; statKey: PriorityStatKey }> = [
  { level: "low", name: "Düşük", color: "#22c55e", statKey: "lowRequests" },
  { level: "medium", name: "Orta", color: "#eab308", statKey: "mediumRequests" },
  { level: "high", name: "Yüksek", color: "#f97316", statKey: "highRequests" },
  { level: "critical", name: "Kritik", color: "#ef4444", statKey: "criticalRequests" }
];

interface PriorityDatum {
  level: PriorityLevel;
  name: string;
  color: string;
  value: number;
}

function toSafeCount(value: unknown): number {
  return typeof value === "number" && Number.isFinite(value) && value > 0 ? value : 0;
}

export function DashboardPage() {
  const navigate = useNavigate();
  const query = useQuery({ queryKey: ["dashboard"], queryFn: getDashboard, refetchInterval: 10000 });
  if (query.isLoading) return <main className="centered">Dashboard yükleniyor…</main>;
  if (query.error) return <main className="centered"><p className="error-box">{query.error.message}</p></main>;
  if (!query.data) return null;

  const global = query.data.global ?? emptyGlobalStats;
  const cities = query.data.cities ?? [];
  const recentRequests = query.data.recentRequests ?? [];
  const priorityData: PriorityDatum[] = priorityCategories.map(({ level, name, color, statKey }) => ({
    level,
    name,
    color,
    value: toSafeCount(global[statKey])
  }));
  const priorityTotal = priorityData.reduce((total, item) => total + item.value, 0);
  const priorityLegendPayload = priorityData.map(({ level, name, color }) => ({ id: level, value: name, type: "circle" as const, color }));
  const needData = [
    { name: "Su", value: toSafeCount(global.waterRequests) }, { name: "Gıda", value: toSafeCount(global.foodRequests) },
    { name: "Barınma", value: toSafeCount(global.shelterRequests) }, { name: "Sağlık", value: toSafeCount(global.medicalRequests) },
    { name: "Bebek", value: toSafeCount(global.babySupportRequests) }
  ];

  async function changeStatus(id: string, status: RequestStatus) {
    await updateRequestStatus(id, status);
    await query.refetch();
  }

  return (
    <main className="dashboard-page">
      <nav className="admin-nav"><strong>Disaster Operations</strong><div><Link to="/admin/allocation">Kaynak dağıtımı</Link><button className="link-button" onClick={() => void logout().then(() => navigate("/admin/login"))}>Çıkış</button></div></nav>
      <header className="dashboard-header"><div><p className="eyebrow">Kriz merkezi</p><h1>Operasyon dashboard’u</h1></div><button className="button secondary" onClick={() => void query.refetch()}>Yenile</button></header>
      <section className="stats-grid">
        <Stat label="Toplam talep" value={toSafeCount(global.totalRequests)} /><Stat label="Kritik talep" value={toSafeCount(global.criticalRequests)} />
        <Stat label="Etkilenen kişi" value={toSafeCount(global.affectedPeople)} /><Stat label="Yaralı bildirimi" value={toSafeCount(global.injuredPeople)} />
      </section>
      <section className="dashboard-grid">
        <article className="panel chart-panel">
          <h2>Öncelik dağılımı</h2>
          <div className="priority-chart-wrap">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie data={priorityData} dataKey="value" nameKey="name" outerRadius={90} label={priorityTotal > 0}>
                  {priorityData.map(({ level, color }) => <Cell key={level} fill={color} />)}
                </Pie>
                <Tooltip content={<PriorityTooltip />} />
                <Legend payload={priorityLegendPayload} />
              </PieChart>
            </ResponsiveContainer>
            {priorityTotal === 0 && <p className="empty-chart">Öncelik verisi yok</p>}
          </div>
        </article>
        <article className="panel chart-panel"><h2>İhtiyaç kategorileri</h2><ResponsiveContainer width="100%" height={260}><BarChart data={needData}><CartesianGrid strokeDasharray="3 3" /><XAxis dataKey="name" /><YAxis allowDecimals={false} /><Tooltip /><Bar dataKey="value" /></BarChart></ResponsiveContainer></article>
      </section>
      <section className="panel"><h2>Harita</h2><MapView requests={recentRequests} /></section>
      <section className="panel table-panel">
        <div className="section-heading"><h2>Son talepler</h2><span>{recentRequests.length} kayıt</span></div>
        <div className="table-scroll">
          <table className="request-table">
            <thead>
              <tr><th>Şehir</th><th>Adres</th><th>Koordinat</th><th>Özet</th><th>Öncelik</th><th>Puan</th><th>Kişi</th><th>Durum</th></tr>
            </thead>
            <tbody>
              {recentRequests.map(request => (
                <tr key={request.requestId}>
                  <td><strong>{request.city}</strong><small>{request.district?.trim() || "İlçe belirtilmedi"}</small></td>
                  <td>{request.address?.trim() || "Adres belirtilmedi"}</td>
                  <td>{formatCoordinates(request)}</td>
                  <td>{request.summary ?? "Analiz bekleniyor"}</td>
                  <td><PriorityBadge level={request.priorityLevel} /></td>
                  <td>{request.priorityScore ?? "-"}</td>
                  <td>{request.peopleCount ?? "-"}</td>
                  <td><select value={request.requestStatus} onChange={e => void changeStatus(request.requestId, e.target.value as RequestStatus)}>{statuses.map(status => <option key={status}>{status}</option>)}</select></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
      <section className="panel"><h2>Şehir özeti</h2><div className="city-grid">{cities.map(city => <article className="city-card" key={city.scope}><strong>{city.city}</strong><span>{city.totalRequests ?? 0} talep</span><span>{city.criticalRequests ?? 0} kritik</span></article>)}</div></section>
    </main>
  );
}

function Stat({ label, value }: { label: string; value: number }) {
  return <article className="stat-card"><span>{label}</span><strong>{value.toLocaleString("tr-TR")}</strong></article>;
}

function PriorityTooltip({ active, payload }: TooltipProps<number, string>) {
  if (!active || !payload?.length) return null;

  const item = payload[0]?.payload as PriorityDatum | undefined;
  if (!item) return null;

  return (
    <div className="chart-tooltip">
      <span className="chart-tooltip-row">
        <span className="chart-tooltip-swatch" style={{ backgroundColor: item.color }} />
        <strong>{item.name}</strong>
      </span>
      <span>{item.value.toLocaleString("tr-TR")}</span>
    </div>
  );
}

function formatCoordinates(request: DisasterRequest): string {
  if (!hasValidCoordinate(request.latitude, -90, 90) || !hasValidCoordinate(request.longitude, -180, 180)) {
    return "Koordinat belirtilmedi";
  }
  return `${request.latitude.toFixed(4)}, ${request.longitude.toFixed(4)}`;
}

function hasValidCoordinate(value: number | undefined, min: number, max: number): value is number {
  return typeof value === "number" && Number.isFinite(value) && value >= min && value <= max;
}
