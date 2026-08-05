import type { PriorityLevel } from "../types";
const labels: Record<PriorityLevel, string> = { low: "Düşük", medium: "Orta", high: "Yüksek", critical: "Kritik" };
export function PriorityBadge({ level }: { level?: PriorityLevel }) {
  return level ? <span className={`badge badge-${level}`}>{labels[level]}</span> : <span className="badge badge-pending">Bekleniyor</span>;
}
