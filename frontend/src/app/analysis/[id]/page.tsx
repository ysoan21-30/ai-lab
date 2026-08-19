"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import RequireAuth from "@/components/RequireAuth";
import Navbar from "@/components/Navbar";
import ScoreGauge from "@/components/ScoreGauge";
import SeverityBadge from "@/components/SeverityBadge";
import PlotlyChart from "@/components/PlotlyChart";
import { api, apiErrorMessage, API_URL } from "@/lib/api";
import { AnalysisDetail } from "@/lib/types";

export default function AnalysisPage() {
  return (
    <RequireAuth>
      <AnalysisContent />
    </RequireAuth>
  );
}

function download(path: string, filename: string) {
  const token = window.localStorage.getItem("access_token");
  fetch(`${API_URL}${path}`, { headers: { Authorization: `Bearer ${token}` } })
    .then(async (res) => {
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || "Export failed.");
      }
      return res.blob();
    })
    .then((blob) => {
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      a.click();
      URL.revokeObjectURL(url);
    })
    .catch((err) => alert(err.message));
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="card p-6">
      <h2 className="text-lg font-semibold text-slate-900">{title}</h2>
      <div className="mt-4">{children}</div>
    </section>
  );
}

function AnalysisContent() {
  const params = useParams<{ id: string }>();
  const [analysis, setAnalysis] = useState<AnalysisDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [targetColumn, setTargetColumn] = useState("");

  useEffect(() => {
    api.get<AnalysisDetail>(`/api/analyses/${params.id}`)
      .then((res) => {
        setAnalysis(res.data);
        setTargetColumn(res.data.target_result?.most_likely_target || "");
      })
      .catch((err) => setError(apiErrorMessage(err)));
  }, [params.id]);

  async function setTarget() {
    if (!targetColumn) return;
    try {
      const res = await api.post<AnalysisDetail>(`/api/analyses/${params.id}/target`, { column: targetColumn });
      setAnalysis(res.data);
    } catch (err) {
      alert(apiErrorMessage(err));
    }
  }

  if (error) return <main><Navbar /><div className="container-page py-14 text-sm text-red-600">{error}</div></main>;
  if (!analysis) return <main><Navbar /><div className="container-page py-14 text-sm text-slate-500">Loading report...</div></main>;

  if (analysis.status === "failed") {
    return (
      <main>
        <Navbar />
        <div className="container-page max-w-2xl py-14">
          <div className="card p-8 text-center">
            <h1 className="text-lg font-semibold text-red-700">Analysis failed</h1>
            <p className="mt-2 text-sm text-slate-600">{analysis.error_message}</p>
          </div>
        </div>
      </main>
    );
  }

  const readiness = analysis.ml_readiness_result;
  const ai = analysis.ai_insights;
  const charts = analysis.charts;
  const columns = analysis.profile_result?.column_profiles?.map((c: any) => c.column) || [];

  return (
    <main className="bg-slate-50">
      <Navbar />
      <div className="container-page space-y-6 py-10">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl font-semibold text-slate-900">{analysis.dataset_name}</h1>
            <p className="mt-1 text-sm text-slate-600">
              {analysis.row_count?.toLocaleString()} rows · {analysis.column_count} columns · analyzed {new Date(analysis.created_at).toLocaleString()}
            </p>
          </div>
          <div className="flex gap-2">
            <button className="btn-secondary" onClick={() => download(`/api/analyses/${analysis.id}/export/json`, `${analysis.dataset_name}.json`)}>Export JSON</button>
            <button className="btn-secondary" onClick={() => download(`/api/analyses/${analysis.id}/export/csv`, `${analysis.dataset_name}_issues.csv`)}>Export CSV</button>
            <button className="btn-primary" onClick={() => download(`/api/analyses/${analysis.id}/export/pdf`, `${analysis.dataset_name}_report.pdf`)}>Export PDF</button>
          </div>
        </div>

        <div className="card flex flex-wrap items-center justify-around gap-6 p-8">
          <ScoreGauge label="Data Quality Score" score={analysis.quality_score || 0} />
          <ScoreGauge label="ML Readiness Score" score={analysis.ml_readiness_score || 0} />
          {readiness && Object.entries(readiness.breakdown).map(([k, v]) => (
            <ScoreGauge key={k} label={k.replace(/_/g, " ")} score={v} size={90} />
          ))}
        </div>
        {readiness && <p className="text-xs text-slate-500">{readiness.disclaimer}</p>}

        {ai && (
          <Section title="AI-Generated Insights">
            {ai._meta?.source === "fallback_rules_based" && (
              <p className="mb-3 text-xs text-amber-700">
                Generated with deterministic rules (no AI model key configured on this server).
              </p>
            )}
            <p className="text-sm text-slate-700">{ai.executive_summary}</p>

            {ai.critical_issues?.length > 0 && (
              <div className="mt-5">
                <h3 className="text-sm font-semibold text-red-700">Critical Issues</h3>
                <ul className="mt-2 space-y-2">
                  {ai.critical_issues.map((i, idx) => (
                    <li key={idx} className="rounded-md bg-red-50 p-3 text-sm text-red-900">
                      <span className="font-medium">{i.title}:</span> {i.explanation}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            <div className="mt-5 grid gap-6 md:grid-cols-2">
              <div>
                <h3 className="text-sm font-semibold text-slate-900">Recommended Cleaning Steps</h3>
                <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-slate-700">
                  {ai.recommended_cleaning_steps?.map((s, i) => <li key={i}>{s}</li>)}
                </ul>
              </div>
              <div>
                <h3 className="text-sm font-semibold text-slate-900">Recommended Next Steps</h3>
                <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-slate-700">
                  {ai.recommended_next_steps?.map((s, i) => <li key={i}>{s}</li>)}
                </ul>
              </div>
              <div>
                <h3 className="text-sm font-semibold text-slate-900">Feature Engineering Suggestions</h3>
                <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-slate-700">
                  {ai.feature_engineering_suggestions?.map((s, i) => <li key={i}>{s}</li>)}
                </ul>
              </div>
              <div>
                <h3 className="text-sm font-semibold text-slate-900">Potential Modeling Concerns</h3>
                <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-slate-700">
                  {ai.potential_modeling_concerns?.length ? ai.potential_modeling_concerns.map((s, i) => <li key={i}>{s}</li>) : <li>None detected.</li>}
                </ul>
              </div>
            </div>

            {ai.leakage_warnings?.length > 0 && (
              <div className="mt-5 rounded-md bg-amber-50 p-3">
                <h3 className="text-sm font-semibold text-amber-800">Potential Data Leakage Warnings</h3>
                <ul className="mt-1 list-disc space-y-1 pl-5 text-sm text-amber-900">
                  {ai.leakage_warnings.map((s, i) => <li key={i}>{s}</li>)}
                </ul>
              </div>
            )}
          </Section>
        )}

        <Section title="Target Column">
          <p className="text-sm text-slate-600">{analysis.target_result?.note}</p>
          <div className="mt-3 flex items-center gap-3">
            <select value={targetColumn} onChange={(e) => setTargetColumn(e.target.value)} className="input max-w-xs">
              <option value="">Select a column...</option>
              {columns.map((c: string) => <option key={c} value={c}>{c}</option>)}
            </select>
            <button className="btn-secondary" onClick={setTarget}>Confirm Target</button>
          </div>
          {analysis.target_result?.class_imbalance && (
            <p className="mt-3 text-sm text-slate-700">
              Class imbalance: <SeverityBadge severity={analysis.target_result.class_imbalance.severity} />{" "}
              (ratio {analysis.target_result.class_imbalance.imbalance_ratio}:1) — {analysis.target_result.class_imbalance.recommendation}
            </p>
          )}
        </Section>

        {charts?.missing_values?.length > 0 && (
          <Section title="Missing Values">
            <PlotlyChart
              data={[{
                type: "bar",
                x: charts.missing_values.map((d: any) => d.missing_percentage),
                y: charts.missing_values.map((d: any) => d.column),
                orientation: "h",
                marker: { color: "#dc2626" },
              }]}
              layout={{ height: Math.max(250, charts.missing_values.length * 28), margin: { l: 140, r: 20, t: 10, b: 30 }, xaxis: { title: "% missing" } }}
            />
          </Section>
        )}

        {charts?.correlation_heatmap?.columns?.length > 1 && (
          <Section title="Correlation Heatmap">
            <PlotlyChart
              data={[{
                type: "heatmap",
                z: charts.correlation_heatmap.matrix,
                x: charts.correlation_heatmap.columns,
                y: charts.correlation_heatmap.columns,
                colorscale: "RdBu", zmin: -1, zmax: 1,
              }]}
              layout={{ height: 400, margin: { l: 100, r: 20, t: 10, b: 100 } }}
            />
          </Section>
        )}

        {charts?.class_distribution && (
          <Section title={`Class Distribution — ${charts.class_distribution.column}`}>
            <PlotlyChart
              data={[{
                type: "bar",
                x: charts.class_distribution.distribution.map((d: any) => d.class),
                y: charts.class_distribution.distribution.map((d: any) => d.proportion),
                marker: { color: "#2563eb" },
              }]}
              layout={{ height: 300, margin: { l: 50, r: 20, t: 10, b: 40 }, yaxis: { title: "proportion" } }}
            />
          </Section>
        )}

        {charts?.cardinality?.length > 0 && (
          <Section title="Cardinality (Categorical Columns)">
            <PlotlyChart
              data={[{
                type: "bar",
                x: charts.cardinality.map((d: any) => d.column),
                y: charts.cardinality.map((d: any) => d.cardinality),
                marker: { color: "#7c3aed" },
              }]}
              layout={{ height: 300, margin: { l: 50, r: 20, t: 10, b: 80 } }}
            />
          </Section>
        )}

        {charts?.outliers?.length > 0 && (
          <Section title="Outliers by Column">
            <PlotlyChart
              data={[{
                type: "bar",
                x: charts.outliers.map((d: any) => d.column),
                y: charts.outliers.map((d: any) => d.count),
                marker: { color: "#ea580c" },
              }]}
              layout={{ height: 300, margin: { l: 50, r: 20, t: 10, b: 80 } }}
            />
          </Section>
        )}

        <Section title={`Data Quality Issues (${analysis.quality_result?.total_issues ?? 0})`}>
          <div className="space-y-3">
            {analysis.quality_result?.issues?.map((issue, idx) => (
              <div key={idx} className="rounded-lg border border-slate-200 p-4">
                <div className="flex items-center justify-between gap-2">
                  <span className="text-sm font-medium text-slate-900">
                    {issue.column ? `${issue.column} — ` : ""}{issue.type.replace(/_/g, " ")}
                  </span>
                  <SeverityBadge severity={issue.severity} />
                </div>
                <p className="mt-1 text-sm text-slate-600">{issue.detail}</p>
                {issue.recommendation && (
                  <pre className="mt-2 overflow-x-auto rounded-md bg-slate-900 p-3 text-xs text-slate-100">{issue.recommendation}</pre>
                )}
              </div>
            ))}
            {(!analysis.quality_result?.issues || analysis.quality_result.issues.length === 0) && (
              <p className="text-sm text-slate-500">No data quality issues detected.</p>
            )}
          </div>
        </Section>
      </div>
    </main>
  );
}
