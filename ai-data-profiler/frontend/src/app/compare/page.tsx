"use client";

import { useCallback, useRef, useState } from "react";
import RequireAuth from "@/components/RequireAuth";
import Navbar from "@/components/Navbar";
import { api, apiErrorMessage } from "@/lib/api";

interface ColumnDiff {
  column: string;
  dtype_a: string;
  dtype_b: string;
  dtype_changed: boolean;
  missing_pct_a: number;
  missing_pct_b: number;
  missing_pct_delta: number;
  unique_a: number;
  unique_b: number;
  mean_a?: number;
  mean_b?: number;
  mean_pct_change?: number;
}

interface DistributionShift {
  column: string;
  mean_a: number;
  mean_b: number;
  cohens_d: number;
  severity: "LOW" | "MEDIUM" | "HIGH";
}

interface ComparisonResult {
  name_a: string;
  name_b: string;
  shape: {
    rows_a: number;
    rows_b: number;
    row_diff: number;
    row_diff_pct: number;
  };
  schema_diff: {
    columns_only_in_a: string[];
    columns_only_in_b: string[];
    common_columns: string[];
    column_count_a: number;
    column_count_b: number;
  };
  column_diffs: ColumnDiff[];
  quality_delta: {
    issues_a: number;
    issues_b: number;
    issues_delta: number;
    duplicates_pct_a: number;
    duplicates_pct_b: number;
  };
  distribution_shifts: DistributionShift[];
}

export default function ComparePage() {
  return (
    <RequireAuth>
      <CompareContent />
    </RequireAuth>
  );
}

function CompareContent() {
  const [fileA, setFileA] = useState<File | null>(null);
  const [fileB, setFileB] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ComparisonResult | null>(null);
  const refA = useRef<HTMLInputElement>(null);
  const refB = useRef<HTMLInputElement>(null);

  const handleCompare = useCallback(async () => {
    if (!fileA || !fileB) return;
    setLoading(true);
    setError(null);
    setResult(null);

    const formData = new FormData();
    formData.append("file_a", fileA);
    formData.append("file_b", fileB);

    try {
      const res = await api.post("/api/compare", formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      setResult(res.data);
    } catch (err) {
      setError(apiErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }, [fileA, fileB]);

  return (
    <main>
      <Navbar />
      <div className="container-page max-w-5xl py-14">
        <h1 className="text-2xl font-semibold text-slate-900">Compare Datasets</h1>
        <p className="mt-1 text-sm text-slate-600">
          Upload two datasets to get a side-by-side comparison: schema changes, distribution shifts, and quality deltas.
        </p>

        <div className="mt-8 grid grid-cols-1 gap-6 md:grid-cols-2">
          <FileDropZone
            label="Dataset A (baseline)"
            file={fileA}
            onFile={setFileA}
            inputRef={refA}
          />
          <FileDropZone
            label="Dataset B (new version)"
            file={fileB}
            onFile={setFileB}
            inputRef={refB}
          />
        </div>

        <div className="mt-6 flex items-center gap-4">
          <button
            onClick={handleCompare}
            disabled={!fileA || !fileB || loading}
            className="btn-primary disabled:opacity-50"
          >
            {loading ? "Comparing..." : "Compare"}
          </button>
          {error && <p className="text-sm text-red-600">{error}</p>}
        </div>

        {result && <ComparisonReport data={result} />}
      </div>
    </main>
  );
}

function FileDropZone({
  label,
  file,
  onFile,
  inputRef,
}: {
  label: string;
  file: File | null;
  onFile: (f: File) => void;
  inputRef: React.RefObject<HTMLInputElement>;
}) {
  const [dragOver, setDragOver] = useState(false);

  return (
    <div
      onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
      onDragLeave={() => setDragOver(false)}
      onDrop={(e) => {
        e.preventDefault();
        setDragOver(false);
        const f = e.dataTransfer.files?.[0];
        if (f) onFile(f);
      }}
      onClick={() => inputRef.current?.click()}
      className={`cursor-pointer rounded-xl border-2 border-dashed p-8 text-center transition-colors ${
        dragOver ? "border-brand-500 bg-brand-50" : file ? "border-green-300 bg-green-50" : "border-slate-300 bg-white"
      }`}
    >
      <input
        ref={inputRef}
        type="file"
        accept=".csv,.xlsx,.xls,.parquet"
        className="hidden"
        onChange={(e) => e.target.files?.[0] && onFile(e.target.files[0])}
      />
      <p className="text-sm font-medium text-slate-700">{label}</p>
      {file ? (
        <p className="mt-1 text-xs text-green-700">{file.name} ({(file.size / 1024).toFixed(1)} KB)</p>
      ) : (
        <p className="mt-1 text-xs text-slate-500">Drop a file or click to browse</p>
      )}
    </div>
  );
}

function ComparisonReport({ data }: { data: ComparisonResult }) {
  const { shape, schema_diff, column_diffs, quality_delta, distribution_shifts } = data;

  return (
    <div className="mt-10 space-y-8">
      {/* Overview */}
      <section>
        <h2 className="text-lg font-semibold text-slate-900">Overview</h2>
        <div className="mt-3 grid grid-cols-2 gap-4 md:grid-cols-4">
          <StatCard label="Rows (A)" value={shape.rows_a.toLocaleString()} />
          <StatCard label="Rows (B)" value={shape.rows_b.toLocaleString()} />
          <StatCard
            label="Row Change"
            value={`${shape.row_diff >= 0 ? "+" : ""}${shape.row_diff.toLocaleString()} (${shape.row_diff_pct >= 0 ? "+" : ""}${shape.row_diff_pct}%)`}
            color={shape.row_diff === 0 ? "slate" : "amber"}
          />
          <StatCard
            label="Columns (A / B)"
            value={`${schema_diff.column_count_a} / ${schema_diff.column_count_b}`}
          />
        </div>
      </section>

      {/* Schema Diff */}
      {(schema_diff.columns_only_in_a.length > 0 || schema_diff.columns_only_in_b.length > 0) && (
        <section>
          <h2 className="text-lg font-semibold text-slate-900">Schema Changes</h2>
          <div className="mt-3 grid grid-cols-1 gap-4 md:grid-cols-2">
            {schema_diff.columns_only_in_a.length > 0 && (
              <div className="rounded-lg bg-red-50 p-4">
                <p className="text-sm font-medium text-red-800">Removed in B ({schema_diff.columns_only_in_a.length})</p>
                <ul className="mt-2 space-y-1">
                  {schema_diff.columns_only_in_a.map((col) => (
                    <li key={col} className="text-sm text-red-700 font-mono">- {col}</li>
                  ))}
                </ul>
              </div>
            )}
            {schema_diff.columns_only_in_b.length > 0 && (
              <div className="rounded-lg bg-green-50 p-4">
                <p className="text-sm font-medium text-green-800">Added in B ({schema_diff.columns_only_in_b.length})</p>
                <ul className="mt-2 space-y-1">
                  {schema_diff.columns_only_in_b.map((col) => (
                    <li key={col} className="text-sm text-green-700 font-mono">+ {col}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        </section>
      )}

      {/* Distribution Shifts */}
      {distribution_shifts.length > 0 && (
        <section>
          <h2 className="text-lg font-semibold text-slate-900">Distribution Shifts</h2>
          <p className="mt-1 text-xs text-slate-500">Numeric columns with statistically significant mean shifts (Cohen&apos;s d &ge; 0.2)</p>
          <div className="mt-3 card overflow-hidden">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-slate-200 bg-slate-50 text-slate-500">
                <tr>
                  <th className="px-4 py-3 font-medium">Column</th>
                  <th className="px-4 py-3 font-medium">Mean (A)</th>
                  <th className="px-4 py-3 font-medium">Mean (B)</th>
                  <th className="px-4 py-3 font-medium">Cohen&apos;s d</th>
                  <th className="px-4 py-3 font-medium">Severity</th>
                </tr>
              </thead>
              <tbody>
                {distribution_shifts.map((s) => (
                  <tr key={s.column} className="border-b border-slate-100 last:border-0">
                    <td className="px-4 py-3 font-mono text-slate-900">{s.column}</td>
                    <td className="px-4 py-3 text-slate-600">{s.mean_a.toLocaleString(undefined, { maximumFractionDigits: 2 })}</td>
                    <td className="px-4 py-3 text-slate-600">{s.mean_b.toLocaleString(undefined, { maximumFractionDigits: 2 })}</td>
                    <td className="px-4 py-3 text-slate-600">{s.cohens_d.toFixed(3)}</td>
                    <td className="px-4 py-3">
                      <SeverityBadge severity={s.severity} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {/* Quality Delta */}
      <section>
        <h2 className="text-lg font-semibold text-slate-900">Quality Comparison</h2>
        <div className="mt-3 grid grid-cols-2 gap-4 md:grid-cols-3">
          <StatCard label="Issues (A)" value={String(quality_delta.issues_a)} />
          <StatCard label="Issues (B)" value={String(quality_delta.issues_b)} />
          <StatCard
            label="Issue Delta"
            value={`${quality_delta.issues_delta >= 0 ? "+" : ""}${quality_delta.issues_delta}`}
            color={quality_delta.issues_delta > 0 ? "red" : quality_delta.issues_delta < 0 ? "green" : "slate"}
          />
        </div>
      </section>

      {/* Column-by-column */}
      <section>
        <h2 className="text-lg font-semibold text-slate-900">Column Details ({column_diffs.length} common columns)</h2>
        <div className="mt-3 card overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-slate-200 bg-slate-50 text-slate-500">
              <tr>
                <th className="px-4 py-3 font-medium">Column</th>
                <th className="px-4 py-3 font-medium">Type A</th>
                <th className="px-4 py-3 font-medium">Type B</th>
                <th className="px-4 py-3 font-medium">Missing % (A)</th>
                <th className="px-4 py-3 font-medium">Missing % (B)</th>
                <th className="px-4 py-3 font-medium">Unique (A)</th>
                <th className="px-4 py-3 font-medium">Unique (B)</th>
              </tr>
            </thead>
            <tbody>
              {column_diffs.map((d) => (
                <tr key={d.column} className={`border-b border-slate-100 last:border-0 ${d.dtype_changed ? "bg-amber-50" : ""}`}>
                  <td className="px-4 py-3 font-mono text-slate-900">{d.column}</td>
                  <td className="px-4 py-3 text-slate-600">{d.dtype_a}</td>
                  <td className={`px-4 py-3 ${d.dtype_changed ? "text-amber-700 font-medium" : "text-slate-600"}`}>{d.dtype_b}</td>
                  <td className="px-4 py-3 text-slate-600">{d.missing_pct_a}%</td>
                  <td className={`px-4 py-3 ${d.missing_pct_delta > 5 ? "text-red-600 font-medium" : "text-slate-600"}`}>{d.missing_pct_b}%</td>
                  <td className="px-4 py-3 text-slate-600">{d.unique_a.toLocaleString()}</td>
                  <td className="px-4 py-3 text-slate-600">{d.unique_b.toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}

function StatCard({ label, value, color = "slate" }: { label: string; value: string; color?: string }) {
  const colorMap: Record<string, string> = {
    slate: "text-slate-900",
    amber: "text-amber-700",
    red: "text-red-700",
    green: "text-green-700",
  };
  return (
    <div className="card p-4">
      <p className="text-xs font-medium text-slate-500">{label}</p>
      <p className={`mt-1 text-xl font-semibold ${colorMap[color] || colorMap.slate}`}>{value}</p>
    </div>
  );
}

function SeverityBadge({ severity }: { severity: string }) {
  const styles: Record<string, string> = {
    LOW: "bg-yellow-100 text-yellow-800",
    MEDIUM: "bg-orange-100 text-orange-800",
    HIGH: "bg-red-100 text-red-800",
  };
  return <span className={`badge ${styles[severity] || styles.LOW}`}>{severity}</span>;
}
