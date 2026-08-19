"use client";

import { useEffect, useState } from "react";
import RequireAuth from "@/components/RequireAuth";
import Navbar from "@/components/Navbar";
import { api, apiErrorMessage } from "@/lib/api";
import { useAuth } from "@/lib/auth";

interface Overview {
  total_users: number;
  active_users_30d: number;
  total_analyses: number;
  avg_processing_time_ms: number | null;
  error_count: number;
  subscription_counts: Record<string, number>;
  estimated_mrr_inr: number;
  total_llm_cost_usd: number;
  dataset_size_distribution: Record<string, number>;
}

export default function AdminPage() {
  return (
    <RequireAuth>
      <AdminContent />
    </RequireAuth>
  );
}

function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="card p-5">
      <div className="text-xs font-medium text-slate-500">{label}</div>
      <div className="mt-1 text-2xl font-semibold text-slate-900">{value}</div>
    </div>
  );
}

function AdminContent() {
  const { user } = useAuth();
  const [overview, setOverview] = useState<Overview | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.get<Overview>("/api/admin/overview").then((res) => setOverview(res.data)).catch((err) => setError(apiErrorMessage(err)));
  }, []);

  if (user && !user.is_admin) {
    return (
      <main><Navbar /><div className="container-page py-14 text-sm text-red-600">Admin access required.</div></main>
    );
  }

  return (
    <main>
      <Navbar />
      <div className="container-page py-10">
        <h1 className="text-2xl font-semibold text-slate-900">Admin Dashboard</h1>
        {error && <p className="mt-4 text-sm text-red-600">{error}</p>}
        {overview && (
          <>
            <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <Stat label="Total Users" value={overview.total_users} />
              <Stat label="Active Users (30d)" value={overview.active_users_30d} />
              <Stat label="Total Analyses" value={overview.total_analyses} />
              <Stat label="Errors" value={overview.error_count} />
              <Stat label="Avg Processing Time" value={overview.avg_processing_time_ms ? `${Math.round(overview.avg_processing_time_ms)} ms` : "—"} />
              <Stat label="Estimated MRR" value={`₹${overview.estimated_mrr_inr.toLocaleString()}`} />
              <Stat label="Total LLM Cost" value={`$${overview.total_llm_cost_usd.toFixed(4)}`} />
            </div>

            <div className="mt-8 grid gap-6 md:grid-cols-2">
              <div className="card p-5">
                <h2 className="text-sm font-semibold text-slate-900">Subscriptions by Plan</h2>
                <ul className="mt-3 space-y-1 text-sm text-slate-700">
                  {Object.entries(overview.subscription_counts).map(([plan, count]) => (
                    <li key={plan} className="flex justify-between"><span className="capitalize">{plan}</span><span>{count}</span></li>
                  ))}
                </ul>
              </div>
              <div className="card p-5">
                <h2 className="text-sm font-semibold text-slate-900">Dataset Size Distribution</h2>
                <ul className="mt-3 space-y-1 text-sm text-slate-700">
                  {Object.entries(overview.dataset_size_distribution).map(([bucket, count]) => (
                    <li key={bucket} className="flex justify-between"><span>{bucket}</span><span>{count}</span></li>
                  ))}
                </ul>
              </div>
            </div>
            <p className="mt-6 text-xs text-slate-500">This dashboard never displays raw dataset contents from user uploads.</p>
          </>
        )}
      </div>
    </main>
  );
}
