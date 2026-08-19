"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import RequireAuth from "@/components/RequireAuth";
import Navbar from "@/components/Navbar";
import { api, apiErrorMessage } from "@/lib/api";
import { AnalysisSummary, UsageOut } from "@/lib/types";
import { useAuth } from "@/lib/auth";

function formatBytes(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function StatusBadge({ status }: { status: string }) {
  const styles: Record<string, string> = {
    completed: "bg-green-100 text-green-800",
    failed: "bg-red-100 text-red-800",
    processing: "bg-amber-100 text-amber-800",
    pending: "bg-slate-100 text-slate-700",
  };
  return <span className={`badge ${styles[status] || styles.pending}`}>{status}</span>;
}

export default function DashboardPage() {
  return (
    <RequireAuth>
      <DashboardContent />
    </RequireAuth>
  );
}

function DashboardContent() {
  const { user } = useAuth();
  const [analyses, setAnalyses] = useState<AnalysisSummary[]>([]);
  const [usage, setUsage] = useState<UsageOut | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([api.get<AnalysisSummary[]>("/api/analyses"), api.get<UsageOut>("/api/analyses/usage")])
      .then(([analysesRes, usageRes]) => {
        setAnalyses(analysesRes.data);
        setUsage(usageRes.data);
      })
      .catch((err) => setError(apiErrorMessage(err)))
      .finally(() => setLoading(false));
  }, []);

  return (
    <main>
      <Navbar />
      <div className="container-page py-10">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl font-semibold text-slate-900">Welcome back{user?.full_name ? `, ${user.full_name}` : ""}</h1>
            <p className="mt-1 text-sm text-slate-600">
              {usage ? `${usage.analyses_used_this_month} / ${usage.analyses_limit} analyses used this month on the ${usage.plan} plan` : ""}
            </p>
          </div>
          <Link href="/upload" className="btn-primary">+ New Analysis</Link>
        </div>

        {error && <p className="mt-6 text-sm text-red-600">{error}</p>}

        <div className="mt-8 card overflow-hidden">
          {loading ? (
            <div className="p-10 text-center text-sm text-slate-500">Loading your analyses...</div>
          ) : analyses.length === 0 ? (
            <div className="p-10 text-center">
              <p className="text-sm text-slate-600">You haven&apos;t analyzed any datasets yet.</p>
              <Link href="/upload" className="btn-primary mt-4 inline-flex">Analyze your first dataset</Link>
            </div>
          ) : (
            <table className="w-full text-left text-sm">
              <thead className="border-b border-slate-200 bg-slate-50 text-slate-500">
                <tr>
                  <th className="px-4 py-3 font-medium">Dataset</th>
                  <th className="px-4 py-3 font-medium">Date</th>
                  <th className="px-4 py-3 font-medium">Size</th>
                  <th className="px-4 py-3 font-medium">Quality</th>
                  <th className="px-4 py-3 font-medium">ML Readiness</th>
                  <th className="px-4 py-3 font-medium">Issues</th>
                  <th className="px-4 py-3 font-medium">Status</th>
                  <th className="px-4 py-3 font-medium"></th>
                </tr>
              </thead>
              <tbody>
                {analyses.map((a) => (
                  <tr key={a.id} className="border-b border-slate-100 last:border-0">
                    <td className="px-4 py-3 font-medium text-slate-900">{a.dataset_name}</td>
                    <td className="px-4 py-3 text-slate-600">{new Date(a.created_at).toLocaleDateString()}</td>
                    <td className="px-4 py-3 text-slate-600">
                      {formatBytes(a.file_size_bytes)}{a.row_count ? ` · ${a.row_count.toLocaleString()} rows` : ""}
                    </td>
                    <td className="px-4 py-3 text-slate-600">{a.quality_score != null ? `${Math.round(a.quality_score)}/100` : "—"}</td>
                    <td className="px-4 py-3 text-slate-600">{a.ml_readiness_score != null ? `${Math.round(a.ml_readiness_score)}/100` : "—"}</td>
                    <td className="px-4 py-3 text-slate-600">{a.issue_count ?? "—"}</td>
                    <td className="px-4 py-3"><StatusBadge status={a.status} /></td>
                    <td className="px-4 py-3 text-right">
                      <Link href={`/analysis/${a.id}`} className="text-brand-600 hover:underline">View report</Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </main>
  );
}
