const STYLES: Record<string, string> = {
  CRITICAL: "bg-red-100 text-red-800",
  HIGH: "bg-orange-100 text-orange-800",
  MEDIUM: "bg-amber-100 text-amber-800",
  LOW: "bg-slate-100 text-slate-700",
};

export default function SeverityBadge({ severity }: { severity: string }) {
  return <span className={`badge ${STYLES[severity] || STYLES.LOW}`}>{severity}</span>;
}
