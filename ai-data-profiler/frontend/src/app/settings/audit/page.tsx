"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { AuditLogEntry } from "@/lib/types";

export default function AuditPage() {
  const { user } = useAuth();
  const [logs, setLogs] = useState<AuditLogEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState("");

  const fetchLogs = async () => {
    try {
      const params: any = { limit: 100 };
      if (filter) params.resource_type = filter;
      const { data } = await api.get("/api/audit", { params });
      setLogs(data);
    } catch { /* empty */ }
    setLoading(false);
  };

  useEffect(() => { fetchLogs(); }, [filter]);

  if (user?.plan === "free") {
    return (
      <div className="container-page py-10">
        <h1 className="text-2xl font-bold text-slate-900 mb-4">Audit Trail</h1>
        <div className="rounded-lg border border-amber-200 bg-amber-50 p-6 text-center">
          <p className="text-amber-800">Audit trail is available on Pro and Team plans.</p>
        </div>
      </div>
    );
  }

  const actionColors: Record<string, string> = {
    create: "bg-green-100 text-green-700",
    update: "bg-blue-100 text-blue-700",
    delete: "bg-red-100 text-red-700",
    login: "bg-purple-100 text-purple-700",
    share: "bg-amber-100 text-amber-700",
    invite: "bg-teal-100 text-teal-700",
    export: "bg-indigo-100 text-indigo-700",
    revoke: "bg-red-100 text-red-700",
  };

  return (
    <div className="container-page py-10">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-slate-900">Audit Trail</h1>
        <select className="input-field w-48" value={filter} onChange={e => setFilter(e.target.value)}>
          <option value="">All resources</option>
          <option value="analysis">Analysis</option>
          <option value="team">Team</option>
          <option value="team_member">Team Members</option>
          <option value="connector">Connectors</option>
          <option value="rule">Rules</option>
          <option value="webhook">Webhooks</option>
        </select>
      </div>

      {loading ? (
        <p className="text-slate-500">Loading...</p>
      ) : logs.length === 0 ? (
        <div className="rounded-lg border border-slate-200 bg-white p-8 text-center text-slate-500">
          No audit logs yet. Actions will be recorded as you use the platform.
        </div>
      ) : (
        <div className="rounded-lg border border-slate-200 bg-white overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-left text-slate-600">
              <tr>
                <th className="px-4 py-3 font-medium">Time</th>
                <th className="px-4 py-3 font-medium">User</th>
                <th className="px-4 py-3 font-medium">Action</th>
                <th className="px-4 py-3 font-medium">Resource</th>
                <th className="px-4 py-3 font-medium">Details</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {logs.map(log => (
                <tr key={log.id} className="hover:bg-slate-50">
                  <td className="px-4 py-3 text-slate-500 whitespace-nowrap">
                    {new Date(log.created_at).toLocaleString()}
                  </td>
                  <td className="px-4 py-3 text-slate-700">{log.user_email || "System"}</td>
                  <td className="px-4 py-3">
                    <span className={`text-xs px-2 py-0.5 rounded-full ${actionColors[log.action] || "bg-slate-100 text-slate-600"}`}>
                      {log.action}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-slate-700">{log.resource_type}</td>
                  <td className="px-4 py-3 text-slate-500 text-xs max-w-xs truncate">
                    {log.details ? JSON.stringify(log.details) : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
