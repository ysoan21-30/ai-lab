"use client";

import { useEffect, useState } from "react";
import { api, apiErrorMessage } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { DatabaseConnection } from "@/lib/types";

export default function ConnectorsPage() {
  const { user } = useAuth();
  const [connections, setConnections] = useState<DatabaseConnection[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({
    name: "", connector_type: "postgresql", host: "localhost", port: 5432,
    database_name: "", username: "", password: "",
  });
  const [error, setError] = useState("");
  const [testResult, setTestResult] = useState<string | null>(null);

  const fetchConnections = async () => {
    try {
      const { data } = await api.get("/api/connectors");
      setConnections(data);
    } catch { /* empty */ }
    setLoading(false);
  };

  useEffect(() => { fetchConnections(); }, []);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    try {
      await api.post("/api/connectors", {
        ...form,
        port: Number(form.port) || undefined,
      });
      setShowForm(false);
      setForm({ name: "", connector_type: "postgresql", host: "localhost", port: 5432, database_name: "", username: "", password: "" });
      fetchConnections();
    } catch (err) {
      setError(apiErrorMessage(err));
    }
  };

  const testConnection = async (id: string) => {
    setTestResult(null);
    try {
      const { data } = await api.post(`/api/connectors/${id}/test`);
      setTestResult(data.success ? "Connection successful" : `Failed: ${data.message}`);
    } catch (err) {
      setTestResult(apiErrorMessage(err));
    }
  };

  const deleteConnection = async (id: string) => {
    await api.delete(`/api/connectors/${id}`);
    fetchConnections();
  };

  if (user?.plan === "free") {
    return (
      <div className="container-page py-10">
        <h1 className="text-2xl font-bold text-slate-900 mb-4">Database Connectors</h1>
        <div className="rounded-lg border border-amber-200 bg-amber-50 p-6 text-center">
          <p className="text-amber-800">Database connectors are available on Pro and Team plans.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="container-page py-10">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-slate-900">Database Connectors</h1>
        <button onClick={() => setShowForm(!showForm)} className="btn-primary">
          {showForm ? "Cancel" : "+ New Connection"}
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
              <label className="block text-sm font-medium text-slate-700 mb-1">Type</label>
              <select className="input-field" value={form.connector_type} onChange={e => setForm({ ...form, connector_type: e.target.value })}>
                <option value="postgresql">PostgreSQL</option>
                <option value="mysql">MySQL</option>
                <option value="sqlite">SQLite</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Host</label>
              <input className="input-field" value={form.host} onChange={e => setForm({ ...form, host: e.target.value })} />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Port</label>
              <input className="input-field" type="number" value={form.port} onChange={e => setForm({ ...form, port: Number(e.target.value) })} />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Database</label>
              <input className="input-field" value={form.database_name} onChange={e => setForm({ ...form, database_name: e.target.value })} required />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Username</label>
              <input className="input-field" value={form.username} onChange={e => setForm({ ...form, username: e.target.value })} />
            </div>
            <div className="col-span-2">
              <label className="block text-sm font-medium text-slate-700 mb-1">Password</label>
              <input className="input-field" type="password" value={form.password} onChange={e => setForm({ ...form, password: e.target.value })} />
            </div>
          </div>
          {error && <p className="text-sm text-red-600">{error}</p>}
          <button type="submit" className="btn-primary">Create Connection</button>
        </form>
      )}

      {testResult && (
        <div className={`mb-4 rounded-lg p-3 text-sm ${testResult.includes("successful") ? "bg-green-50 text-green-700" : "bg-red-50 text-red-700"}`}>
          {testResult}
        </div>
      )}

      {loading ? (
        <p className="text-slate-500">Loading...</p>
      ) : connections.length === 0 ? (
        <div className="rounded-lg border border-slate-200 bg-white p-8 text-center text-slate-500">
          No database connections yet. Create one to start profiling data directly from your database.
        </div>
      ) : (
        <div className="space-y-3">
          {connections.map(c => (
            <div key={c.id} className="flex items-center justify-between rounded-lg border border-slate-200 bg-white p-4">
              <div>
                <h3 className="font-medium text-slate-900">{c.name}</h3>
                <p className="text-sm text-slate-500">
                  {c.connector_type.toUpperCase()} &middot; {c.host}:{c.port} &middot; {c.database_name}
                </p>
              </div>
              <div className="flex gap-2">
                <button onClick={() => testConnection(c.id)} className="btn-secondary text-xs">Test</button>
                <button onClick={() => deleteConnection(c.id)} className="text-xs text-red-600 hover:text-red-800">Delete</button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
