"use client";

import { useEffect, useState } from "react";
import { api, apiErrorMessage } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { ScheduledAnalysis } from "@/lib/types";

export default function SchedulesPage() {
  const { user } = useAuth();
  const [schedules, setSchedules] = useState<ScheduledAnalysis[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({
    name: "", source_type: "database", connection_id: "", query: "",
    frequency: "daily", alert_on_quality_drop: "", alert_channels: ["email"],
  });
  const [connections, setConnections] = useState<any[]>([]);
  const [error, setError] = useState("");

  const fetchData = async () => {
    try {
      const [schedRes, connRes] = await Promise.all([
        api.get("/api/schedules"),
        api.get("/api/connectors").catch(() => ({ data: [] })),
      ]);
      setSchedules(schedRes.data);
      setConnections(connRes.data);
    } catch { /* empty */ }
    setLoading(false);
  };

  useEffect(() => { fetchData(); }, []);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    try {
      await api.post("/api/schedules", {
        ...form,
        alert_on_quality_drop: form.alert_on_quality_drop ? Number(form.alert_on_quality_drop) / 100 : null,
      });
      setShowForm(false);
      fetchData();
    } catch (err) {
      setError(apiErrorMessage(err));
    }
  };

  const toggleSchedule = async (id: string) => {
    await api.patch(`/api/schedules/${id}/toggle`);
    fetchData();
  };

  const triggerRun = async (id: string) => {
    try {
      await api.post(`/api/schedules/${id}/run`);
      alert("Run triggered successfully");
    } catch (err) {
      alert(apiErrorMessage(err));
    }
  };

  const deleteSchedule = async (id: string) => {
    await api.delete(`/api/schedules/${id}`);
    fetchData();
  };

  if (user?.plan === "free") {
    return (
      <div className="container-page py-10">
        <h1 className="text-2xl font-bold text-slate-900 mb-4">Scheduled Analysis</h1>
        <div className="rounded-lg border border-amber-200 bg-amber-50 p-6 text-center">
          <p className="text-amber-800">Scheduled analysis is available on Pro and Team plans.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="container-page py-10">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-slate-900">Scheduled Analysis</h1>
        <button onClick={() => setShowForm(!showForm)} className="btn-primary">
          {showForm ? "Cancel" : "+ New Schedule"}
        </button>
      </div>

      {showForm && (
        <form onSubmit={handleCreate} className="mb-8 rounded-lg border border-slate-200 bg-white p-6 space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Name</label>
              <input className="input-field" value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} required />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Frequency</label>
              <select className="input-field" value={form.frequency} onChange={e => setForm({ ...form, frequency: e.target.value })}>
                <option value="hourly">Hourly</option>
                <option value="daily">Daily</option>
                <option value="weekly">Weekly</option>
                <option value="monthly">Monthly</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Database Connection</label>
              <select className="input-field" value={form.connection_id} onChange={e => setForm({ ...form, connection_id: e.target.value })}>
                <option value="">Select a connection</option>
                {connections.map((c: any) => (
                  <option key={c.id} value={c.id}>{c.name}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Alert on quality drop (%)</label>
              <input className="input-field" type="number" placeholder="e.g. 10" value={form.alert_on_quality_drop} onChange={e => setForm({ ...form, alert_on_quality_drop: e.target.value })} />
            </div>
            <div className="col-span-2">
              <label className="block text-sm font-medium text-slate-700 mb-1">SQL Query</label>
              <textarea className="input-field font-mono text-sm" rows={3} value={form.query} onChange={e => setForm({ ...form, query: e.target.value })} placeholder="SELECT * FROM your_table LIMIT 10000" />
            </div>
          </div>
          {error && <p className="text-sm text-red-600">{error}</p>}
          <button type="submit" className="btn-primary">Create Schedule</button>
        </form>
      )}

      {loading ? (
        <p className="text-slate-500">Loading...</p>
      ) : schedules.length === 0 ? (
        <div className="rounded-lg border border-slate-200 bg-white p-8 text-center text-slate-500">
          No scheduled analyses yet. Set up recurring data profiling to monitor quality over time.
        </div>
      ) : (
        <div className="space-y-3">
          {schedules.map(s => (
            <div key={s.id} className="flex items-center justify-between rounded-lg border border-slate-200 bg-white p-4">
              <div>
                <div className="flex items-center gap-2">
                  <h3 className="font-medium text-slate-900">{s.name}</h3>
                  <span className={`text-xs px-2 py-0.5 rounded-full ${s.is_active ? "bg-green-100 text-green-700" : "bg-slate-100 text-slate-500"}`}>
                    {s.is_active ? "Active" : "Paused"}
                  </span>
                </div>
                <p className="text-sm text-slate-500">
                  {s.frequency} &middot; {s.source_type}
                  {s.next_run_at && ` · Next: ${new Date(s.next_run_at).toLocaleString()}`}
                </p>
              </div>
              <div className="flex gap-2">
                <button onClick={() => triggerRun(s.id)} className="btn-secondary text-xs">Run Now</button>
                <button onClick={() => toggleSchedule(s.id)} className="btn-secondary text-xs">
                  {s.is_active ? "Pause" : "Resume"}
                </button>
                <button onClick={() => deleteSchedule(s.id)} className="text-xs text-red-600 hover:text-red-800">Delete</button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
