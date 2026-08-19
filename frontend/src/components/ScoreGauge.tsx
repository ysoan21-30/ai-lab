function scoreColor(score: number) {
  if (score >= 80) return { ring: "#16a34a", text: "text-green-700", bg: "bg-green-50" };
  if (score >= 60) return { ring: "#ca8a04", text: "text-amber-700", bg: "bg-amber-50" };
  return { ring: "#dc2626", text: "text-red-700", bg: "bg-red-50" };
}

export default function ScoreGauge({ label, score, size = 120 }: { label: string; score: number; size?: number }) {
  const colors = scoreColor(score);
  const circumference = 2 * Math.PI * 45;
  const offset = circumference - (score / 100) * circumference;

  return (
    <div className="flex flex-col items-center gap-2">
      <div className="relative" style={{ width: size, height: size }}>
        <svg viewBox="0 0 100 100" className="h-full w-full -rotate-90">
          <circle cx="50" cy="50" r="45" fill="none" stroke="#e2e8f0" strokeWidth="8" />
          <circle
            cx="50" cy="50" r="45" fill="none" stroke={colors.ring} strokeWidth="8"
            strokeDasharray={circumference} strokeDashoffset={offset} strokeLinecap="round"
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className={`text-2xl font-bold ${colors.text}`}>{Math.round(score)}</span>
          <span className="text-xs text-slate-500">/ 100</span>
        </div>
      </div>
      <span className="text-sm font-medium text-slate-700">{label}</span>
    </div>
  );
}
