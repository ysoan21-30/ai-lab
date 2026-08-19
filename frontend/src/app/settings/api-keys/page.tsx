"use client";

import { useCallback, useEffect, useState } from "react";
import RequireAuth from "@/components/RequireAuth";
import Navbar from "@/components/Navbar";
import { api, apiErrorMessage } from "@/lib/api";
import { useAuth } from "@/lib/auth";

interface ApiKeyItem {
  id: string;
  label: string | null;
  created_at: string;
  last_used_at: string | null;
}

interface NewKey extends ApiKeyItem {
  raw_key: string;
}

export default function ApiKeysPage() {
  return (
    <RequireAuth>
      <ApiKeysContent />
    </RequireAuth>
  );
}

function ApiKeysContent() {
  const { user } = useAuth();
  const [keys, setKeys] = useState<ApiKeyItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [newKey, setNewKey] = useState<NewKey | null>(null);
  const [label, setLabel] = useState("");
  const [creating, setCreating] = useState(false);
  const [copied, setCopied] = useState(false);

  const fetchKeys = useCallback(async () => {
    try {
      const res = await api.get<ApiKeyItem[]>("/api/keys");
      setKeys(res.data);
    } catch (err) {
      setError(apiErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchKeys();
  }, [fetchKeys]);

  const handleCreate = async () => {
    setCreating(true);
    setError(null);
    try {
      const res = await api.post<NewKey>("/api/keys", { label: label || null });
      setNewKey(res.data);
      setLabel("");
      fetchKeys();
    } catch (err) {
      setError(apiErrorMessage(err));
    } finally {
      setCreating(false);
    }
  };

  const handleRevoke = async (keyId: string) => {
    if (!confirm("Revoke this API key? This cannot be undone.")) return;
    try {
      await api.delete(`/api/keys/${keyId}`);
      setKeys((prev) => prev.filter((k) => k.id !== keyId));
    } catch (err) {
      setError(apiErrorMessage(err));
    }
  };

  const copyKey = (key: string) => {
    navigator.clipboard.writeText(key);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  if (user?.plan !== "team") {
    return (
      <main>
        <Navbar />
        <div className="container-page max-w-2xl py-14 text-center">
          <h1 className="text-2xl font-semibold text-slate-900">API Keys</h1>
          <p className="mt-4 text-sm text-slate-600">
            API keys are available on the Team plan. Upgrade to get programmatic access to the AI Data Profiler API.
          </p>
        </div>
      </main>
    );
  }

  return (
    <main>
      <Navbar />
      <div className="container-page max-w-3xl py-14">
        <h1 className="text-2xl font-semibold text-slate-900">API Keys</h1>
        <p className="mt-1 text-sm text-slate-600">
          Create API keys to access the AI Data Profiler programmatically. Include the key as an <code className="text-xs bg-slate-100 px-1 py-0.5 rounded">X-API-Key</code> header.
        </p>

        {/* New key banner */}
        {newKey && (
          <div className="mt-6 rounded-lg bg-green-50 border border-green-200 p-4">
            <p className="text-sm font-medium text-green-800">API key created. Copy it now — you won&apos;t see it again.</p>
            <div className="mt-2 flex items-center gap-2">
              <code className="flex-1 overflow-x-auto rounded bg-white px-3 py-2 text-sm font-mono text-slate-900 border border-green-200">
                {newKey.raw_key}
              </code>
              <button onClick={() => copyKey(newKey.raw_key)} className="btn-secondary text-sm">
                {copied ? "Copied!" : "Copy"}
              </button>
            </div>
          </div>
        )}

        {/* Create form */}
        <div className="mt-6 flex items-end gap-3">
          <div className="flex-1">
            <label className="block text-sm font-medium text-slate-700 mb-1">Label (optional)</label>
            <input
              type="text"
              value={label}
              onChange={(e) => setLabel(e.target.value)}
              placeholder="e.g. CI pipeline, Jupyter notebook"
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-brand-500 focus:outline-none"
            />
          </div>
          <button onClick={handleCreate} disabled={creating} className="btn-primary whitespace-nowrap">
            {creating ? "Creating..." : "Create Key"}
          </button>
        </div>

        {error && <p className="mt-4 text-sm text-red-600">{error}</p>}

        {/* Key list */}
        <div className="mt-8 card overflow-hidden">
          {loading ? (
            <div className="p-8 text-center text-sm text-slate-500">Loading...</div>
          ) : keys.length === 0 ? (
            <div className="p-8 text-center text-sm text-slate-500">No API keys yet.</div>
          ) : (
            <table className="w-full text-left text-sm">
              <thead className="border-b border-slate-200 bg-slate-50 text-slate-500">
                <tr>
                  <th className="px-4 py-3 font-medium">Label</th>
                  <th className="px-4 py-3 font-medium">Created</th>
                  <th className="px-4 py-3 font-medium">Last Used</th>
                  <th className="px-4 py-3 font-medium"></th>
                </tr>
              </thead>
              <tbody>
                {keys.map((k) => (
                  <tr key={k.id} className="border-b border-slate-100 last:border-0">
                    <td className="px-4 py-3 text-slate-900">{k.label || <span className="text-slate-400">No label</span>}</td>
                    <td className="px-4 py-3 text-slate-600">{new Date(k.created_at).toLocaleDateString()}</td>
                    <td className="px-4 py-3 text-slate-600">{k.last_used_at ? new Date(k.last_used_at).toLocaleDateString() : "Never"}</td>
                    <td className="px-4 py-3 text-right">
                      <button onClick={() => handleRevoke(k.id)} className="text-sm text-red-600 hover:underline">
                        Revoke
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        {/* Usage example */}
        <div className="mt-8">
          <h2 className="text-sm font-semibold text-slate-900">Quick Start</h2>
          <pre className="mt-2 overflow-x-auto rounded-lg bg-slate-900 p-4 text-sm text-slate-100">
{`curl -X POST ${typeof window !== 'undefined' ? window.location.origin : 'http://localhost:8000'}/api/analyses \\
  -H "X-API-Key: adp_your_key_here" \\
  -F "file=@your_dataset.csv"`}
          </pre>
        </div>
      </div>
    </main>
  );
}
