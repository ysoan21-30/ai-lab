"use client";

import { useEffect, useState } from "react";
import { api, apiErrorMessage } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { CustomRule } from "@/lib/types";

const OPERATORS = [
  { value: "not_null", label: "Not Null", needsCol: true, needsVal: false },
  { value: "unique", label: "Unique", needsCol: true, needsVal: false },
  { value: "min", label: "Minimum", needsCol: true, needsVal: true },
  { value: "max", label: "Maximum", needsCol: true, needsVal: true },
  { value: "between", label: "Between", needsCol: true, needsVal: true },
  { value: "regex", label: "Regex Match", needsCol: true, needsVal: true },
  { value: "in_list", label: "In List", needsCol: true, needsVal: true },
];

export default function RulesPage() {
  const { user } = useAuth();
  const [rules, setRules] = useState<CustomRule[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({
    name: "", column_name: "", operator: "not_null",
    value: "", severity: "warning", description: "",
  });
  const [error, setError] = useState("");

  const fetchRules = async () => {
    try {
      const { data } = await api.get("/api/rules");
      setRules(data);
    } catch { /* empty */ }
    setLoading(false);
  };

  useEffect(() => { fetchRules(); }, []);

  const selectedOp = OPERATORS.find(o => o.value === form.operator);

  const parseValue = () => {
    if (!form.value) return null;
    if (form.operator === "between") {
      const [min, max] = form.value.split(",").map(s => s.trim());
      return { min: Number(min), max: Number(max) };
    }
    if (form.operator === "in_list") {
      return form.value.split(",").map(s => s.trim());
    }
    if (["min", "max"].includes(form.operator)) {
      return Number(form.value);
    }
    return form.value;
  };

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    try {
      await api.post("/api/rules", {
        name: form.name,
        column_name: form.column_name || null,
        operator: form.operator,
        value: selectedOp?.needsVal ? parseValue() : null,
        severity: form.severity,
        description: form.description || null,
      });
      setShowForm(false);
      setForm({ name: "", column_name: "", operator: "not_null", value: "", severity: "warning", description: "" });
      fetchRules();
    } catch (err) {
      setError(apiErrorMessage(err));
    }
  };

  const toggleRule = async (id: string) => {
    await api.patch(`/api/rules/${id}/toggle`);
    fetchRules();
  };

  const deleteRule = async (id: string) => {
    await api.delete(`/api/rules/${id}`);
    fetchRules();
  };

  if (user?.plan === "free") {
    return (
      <div className="container-page py-10">
        <h1 className="text-2xl font-bold text-slate-900 mb-4">Custom Quality Rules</h1>
        <div className="rounded-lg border border-amber-200 bg-amber-50 p-6 text-center">
          <p className="text-amber-800">Custom quality rules are available on Pro and Team plans.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="container-page py-10">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-slate-900">Custom Quality Rules</h1>
        <button onClick={() => setShowForm(!showForm)} className="btn-primary">
          {showForm ? "Cancel" : "+ New Rule"}
        </button>
      </div>

      {showForm && (
        <form onSubmit={handleCreate} className="mb-8 rounded-lg border border-slate-200 bg-white p-6 space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Rule Name</label>
              <input className="input-field" value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} required placeholder="e.g. Email must not be null" />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Column</label>
              <input className="input-field" value={form.column_name} onChange={e => setForm({ ...form, column_name: e.target.value })} placeholder="Column name" />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Check Type</label>
              <select className="input-field" value={form.operator} onChange={e => setForm({ ...form, operator: e.target.value })}>
                {OPERATORS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Severity</label>
              <select className="input-field" value={form.severity} onChange={e => setForm({ ...form, severity: e.target.value })}>
                <option value="info">Info</option>
                <option value="warning">Warning</option>
                <option value="critical">Critical</option>
              </select>
            </div>
            {selectedOp?.needsVal && (
              <div className="col-span-2">
                <label className="block text-sm font-medium text-slate-700 mb-1">
                  Value {form.operator === "between" ? "(min, max)" : form.operator === "in_list" ? "(comma-separated)" : ""}
                </label>
                <input className="input-field" value={form.value} onChange={e => setForm({ ...form, value: e.target.value })}
                  placeholder={form.operator === "between" ? "0, 100" : form.operator === "in_list" ? "A, B, C" : form.operator === "regex" ? "^[a-z]+$" : "42"} />
              </div>
            )}
            <div className="col-span-2">
              <label className="block text-sm font-medium text-slate-700 mb-1">Description (optional)</label>
              <input className="input-field" value={form.description} onChange={e => setForm({ ...form, description: e.target.value })} />
            </div>
          </div>
          {error && <p className="text-sm text-red-600">{error}</p>}
          <button type="submit" className="btn-primary">Create Rule</button>
        </form>
      )}

      {loading ? (
        <p className="text-slate-500">Loading...</p>
      ) : rules.length === 0 ? (
        <div className="rounded-lg border border-slate-200 bg-white p-8 text-center text-slate-500">
          No custom rules yet. Define rules to automatically validate your datasets during analysis.
        </div>
      ) : (
        <div className="space-y-3">
          {rules.map(r => (
            <div key={r.id} className="flex items-center justify-between rounded-lg border border-slate-200 bg-white p-4">
              <div>
                <div className="flex items-center gap-2">
                  <h3 className="font-medium text-slate-900">{r.name}</h3>
                  <span className={`text-xs px-2 py-0.5 rounded-full ${r.is_active ? "bg-green-100 text-green-700" : "bg-slate-100 text-slate-500"}`}>
                    {r.is_active ? "Active" : "Disabled"}
                  </span>
                  <span className={`text-xs px-2 py-0.5 rounded-full ${
                    r.severity === "critical" ? "bg-red-100 text-red-700" : r.severity === "warning" ? "bg-amber-100 text-amber-700" : "bg-blue-100 text-blue-700"
                  }`}>{r.severity}</span>
                </div>
                <p className="text-sm text-slate-500">
                  {r.operator.replace("_", " ")} {r.column_name ? `on "${r.column_name}"` : "(dataset-wide)"}
                  {r.value ? ` · value: ${JSON.stringify(r.value)}` : ""}
                </p>
              </div>
              <div className="flex gap-2">
                <button onClick={() => toggleRule(r.id)} className="btn-secondary text-xs">{r.is_active ? "Disable" : "Enable"}</button>
                <button onClick={() => deleteRule(r.id)} className="text-xs text-red-600 hover:text-red-800">Delete</button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
