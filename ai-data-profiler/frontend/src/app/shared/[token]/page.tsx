"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { API_URL } from "@/lib/api";
import { AnalysisDetail } from "@/lib/types";

export default function SharedReportPage() {
  const params = useParams();
  const token = params.token as string;
  const [report, setReport] = useState<AnalysisDetail | null>(null);
  const [error, setError] = useState("");
  const [needsPassword, setNeedsPassword] = useState(false);
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(true);

  const fetchReport = async (pw?: string) => {
    setLoading(true);
    try {
      const url = new URL(`${API_URL}/api/reports/shared/${token}`);
      if (pw) url.searchParams.set("password", pw);
      const resp = await fetch(url.toString());
      if (resp.status === 401) {
        setNeedsPassword(true);
        setError("This report is password protected.");
        setLoading(false);
        return;
      }
      if (!resp.ok) {
        const data = await resp.json();
        setError(data.detail || "Report not found");
        setLoading(false);
        return;
      }
      const data = await resp.json();
      setReport(data);
      setNeedsPassword(false);
      setError("");
    } catch {
      setError("Failed to load report");
    }
    setLoading(false);
  };

  useEffect(() => { fetchReport(); }, [token]);

  if (loading) {
    return <div className="container-page py-20 text-center text-slate-500">Loading shared report...</div>;
  }

  if (needsPassword) {
    return (
      <div className="container-page py-20 max-w-md mx-auto">
        <div className="rounded-lg border border-slate-200 bg-white p-8 text-center">
          <h1 className="text-xl font-bold text-slate-900 mb-4">Password Required</h1>
          <p className="text-sm text-slate-500 mb-4">This report is password protected.</p>
          <form onSubmit={(e) => { e.preventDefault(); fetchReport(password); }} className="space-y-3">
            <input type="password" className="input-field w-full" placeholder="Enter password" value={password} onChange={e => setPassword(e.target.value)} />
            <button type="submit" className="btn-primary w-full">View Report</button>
          </form>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="container-page py-20 text-center">
        <h1 className="text-xl font-bold text-slate-900 mb-2">Shared Report</h1>
        <p className="text-red-600">{error}</p>
      </div>
    );
  }

  if (!report) return null;

  return (
    <div className="container-page py-10">
      <div className="mb-6">
        <div className="flex items-center gap-2 text-sm text-slate-500 mb-2">
          <span className="flex h-6 w-6 items-center justify-center rounded-md bg-brand-600 text-xs text-white">AI</span>
          AI Data Profiler &middot; Shared Report
        </div>
        <h1 className="text-2xl font-bold text-slate-900">{report.dataset_name}</h1>
        <p className="text-sm text-slate-500 mt-1">
          {report.row_count?.toLocaleString()} rows &middot; {report.column_count} columns
          &middot; Quality: {report.quality_score ? `${(report.quality_score * 100).toFixed(0)}%` : "N/A"}
        </p>
      </div>

      {/* Quality summary */}
      {report.quality_result && (
        <div className="mb-6 rounded-lg border border-slate-200 bg-white p-6">
          <h2 className="text-lg font-semibold text-slate-900 mb-3">Data Quality</h2>
          <div className="grid grid-cols-3 gap-4 text-center">
            <div className="p-3 rounded-lg bg-slate-50">
              <p className="text-2xl font-bold text-slate-900">{report.quality_result.total_issues}</p>
              <p className="text-xs text-slate-500">Total Issues</p>
            </div>
            <div className="p-3 rounded-lg bg-slate-50">
              <p className="text-2xl font-bold text-slate-900">{report.quality_score ? `${(report.quality_score * 100).toFixed(0)}%` : "—"}</p>
              <p className="text-xs text-slate-500">Quality Score</p>
            </div>
            <div className="p-3 rounded-lg bg-slate-50">
              <p className="text-2xl font-bold text-slate-900">{report.ml_readiness_score ? `${(report.ml_readiness_score * 100).toFixed(0)}%` : "—"}</p>
              <p className="text-xs text-slate-500">ML Readiness</p>
            </div>
          </div>
        </div>
      )}

      {/* AI insights */}
      {report.ai_insights?.executive_summary && (
        <div className="mb-6 rounded-lg border border-slate-200 bg-white p-6">
          <h2 className="text-lg font-semibold text-slate-900 mb-3">AI Insights</h2>
          <p className="text-slate-700">{report.ai_insights.executive_summary}</p>
        </div>
      )}

      {/* Issues list */}
      {report.quality_result?.issues && report.quality_result.issues.length > 0 && (
        <div className="rounded-lg border border-slate-200 bg-white p-6">
          <h2 className="text-lg font-semibold text-slate-900 mb-3">Issues ({report.quality_result.issues.length})</h2>
          <div className="space-y-2">
            {report.quality_result.issues.slice(0, 20).map((issue: any, i: number) => (
              <div key={i} className="flex items-start gap-3 p-3 rounded-lg bg-slate-50">
                <span className={`text-xs px-2 py-0.5 rounded-full mt-0.5 ${
                  issue.severity === "CRITICAL" ? "bg-red-100 text-red-700" :
                  issue.severity === "HIGH" ? "bg-orange-100 text-orange-700" :
                  issue.severity === "MEDIUM" ? "bg-amber-100 text-amber-700" :
                  "bg-slate-100 text-slate-600"}`}>{issue.severity}</span>
                <div>
                  <p className="text-sm font-medium text-slate-900">{issue.type}</p>
                  <p className="text-xs text-slate-500">{issue.detail}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
