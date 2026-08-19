"use client";

import { useEffect, useState } from "react";
import { api, apiErrorMessage } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { WebhookConfig } from "@/lib/types";

export default function WebhooksPage() {
  const { user } = useAuth();
  const [webhooks, setWebhooks] = useState<WebhookConfig[]>([]);
  const [events, setEvents] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ name: "", url: "", secret: "", events: [] as string[] });
  const [error, setError] = useState("");

  const fetchData = async () => {
    try {
      const [whRes, evRes] = await Promise.all([
        api.get("/api/webhooks"),
        api.get("/api/webhooks/events"),
      ]);
      setWebhooks(whRes.data);
      setEvents(evRes.data.events);
    } catch { /* empty */ }
    setLoading(false);
  };

  useEffect(() => { fetchData(); }, []);

  const toggleEvent = (ev: string) => {
    setForm(prev => ({
      ...prev,
      events: prev.events.includes(ev) ? prev.events.filter(e => e !== ev) : [...prev.events, ev],
    }));
  };

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    if (form.events.length === 0) { setError("Select at least one event"); return; }
    try {
      await api.post("/api/webhooks", form);
      setShowForm(false);
      setForm({ name: "", url: "", secret: "", events: [] });
      fetchData();
    } catch (err) {
      setError(apiErrorMessage(err));
    }
  };

  const toggleWebhook = async (id: string) => {
    await api.patch(`/api/webhooks/${id}/toggle`);
    fetchData();
  };

  const deleteWebhook = async (id: string) => {
    await api.delete(`/api/webhooks/${id}`);
    fetchData();
  };

  if (user?.plan === "free") {
    return (
      <div className="container-page py-10">
        <h1 className="text-2xl font-bold text-slate-900 mb-4">Webhooks</h1>
        <div className="rounded-lg border border-amber-200 bg-amber-50 p-6 text-center">
          <p className="text-amber-800">Webhooks are available on Pro and Team plans.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="container-page py-10">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-slate-900">Webhooks</h1>
        <button onClick={() => setShowForm(!showForm)} className="btn-primary">
          {showForm ? "Cancel" : "+ New Webhook"}
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
              <label className="block text-sm font-medium text-slate-700 mb-1">URL</label>
              <input className="input-field" type="url" value={form.url} onChange={e => setForm({ ...form, url: e.target.value })} required placeholder="https://..." />
            </div>
            <div className="col-span-2">
              <label className="block text-sm font-medium text-slate-700 mb-1">Secret (optional, for HMAC signing)</label>
              <input className="input-field" value={form.secret} onChange={e => setForm({ ...form, secret: e.target.value })} />
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-2">Events</label>
            <div className="flex flex-wrap gap-2">
              {events.map(ev => (
                <button key={ev} type="button" onClick={() => toggleEvent(ev)}
                  className={`text-xs px-3 py-1.5 rounded-full border ${form.events.includes(ev) ? "bg-brand-50 border-brand-300 text-brand-700" : "bg-white border-slate-200 text-slate-600"}`}>
                  {ev}
                </button>
              ))}
            </div>
          </div>
          {error && <p className="text-sm text-red-600">{error}</p>}
          <button type="submit" className="btn-primary">Create Webhook</button>
        </form>
      )}

      {loading ? (
        <p className="text-slate-500">Loading...</p>
      ) : webhooks.length === 0 ? (
        <div className="rounded-lg border border-slate-200 bg-white p-8 text-center text-slate-500">
          No webhooks configured. Set up webhooks to get notified when analyses complete or alerts trigger.
        </div>
      ) : (
        <div className="space-y-3">
          {webhooks.map(w => (
            <div key={w.id} className="flex items-center justify-between rounded-lg border border-slate-200 bg-white p-4">
              <div>
                <div className="flex items-center gap-2">
                  <h3 className="font-medium text-slate-900">{w.name}</h3>
                  <span className={`text-xs px-2 py-0.5 rounded-full ${w.is_active ? "bg-green-100 text-green-700" : "bg-slate-100 text-slate-500"}`}>
                    {w.is_active ? "Active" : "Disabled"}
                  </span>
                  {w.failure_count > 0 && (
                    <span className="text-xs px-2 py-0.5 rounded-full bg-red-100 text-red-700">{w.failure_count} failures</span>
                  )}
                </div>
                <p className="text-sm text-slate-500 truncate max-w-md">{w.url}</p>
                <p className="text-xs text-slate-400">{w.events.join(", ")}</p>
              </div>
              <div className="flex gap-2">
                <button onClick={() => toggleWebhook(w.id)} className="btn-secondary text-xs">{w.is_active ? "Disable" : "Enable"}</button>
                <button onClick={() => deleteWebhook(w.id)} className="text-xs text-red-600 hover:text-red-800">Delete</button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
