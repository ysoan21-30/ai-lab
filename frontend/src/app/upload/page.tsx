"use client";

import { useCallback, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import RequireAuth from "@/components/RequireAuth";
import Navbar from "@/components/Navbar";
import { api, apiErrorMessage } from "@/lib/api";

type Stage = "idle" | "uploading" | "processing" | "error";

export default function UploadPage() {
  return (
    <RequireAuth>
      <UploadContent />
    </RequireAuth>
  );
}

function UploadContent() {
  const [stage, setStage] = useState<Stage>("idle");
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const router = useRouter();

  const handleFile = useCallback(async (file: File) => {
    setError(null);
    const ext = file.name.split(".").pop()?.toLowerCase();
    if (!ext || !["csv", "xlsx", "xls", "parquet"].includes(ext)) {
      setError("Only .csv, .xlsx, and .parquet files are supported.");
      setStage("error");
      return;
    }

    setStage("uploading");
    setProgress(0);
    const formData = new FormData();
    formData.append("file", file);

    try {
      const res = await api.post("/api/analyses", formData, {
        headers: { "Content-Type": "multipart/form-data" },
        onUploadProgress: (evt) => {
          if (evt.total) {
            const pct = Math.round((evt.loaded / evt.total) * 100);
            setProgress(pct);
            if (pct === 100) setStage("processing");
          }
        },
      });
      router.push(`/analysis/${res.data.id}`);
    } catch (err) {
      setError(apiErrorMessage(err));
      setStage("error");
    }
  }, [router]);

  function onDrop(e: React.DragEvent) {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files?.[0];
    if (file) handleFile(file);
  }

  return (
    <main>
      <Navbar />
      <div className="container-page max-w-2xl py-14">
        <h1 className="text-2xl font-semibold text-slate-900">New Analysis</h1>
        <p className="mt-1 text-sm text-slate-600">Upload a CSV, Excel (.xlsx), or Parquet file to generate a data-quality and ML-readiness report.</p>

        <div
          onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
          onDragLeave={() => setDragOver(false)}
          onDrop={onDrop}
          onClick={() => inputRef.current?.click()}
          className={`mt-8 cursor-pointer rounded-xl border-2 border-dashed p-14 text-center transition-colors ${
            dragOver ? "border-brand-500 bg-brand-50" : "border-slate-300 bg-white"
          }`}
        >
          <input
            ref={inputRef}
            type="file"
            accept=".csv,.xlsx,.xls,.parquet"
            className="hidden"
            onChange={(e) => e.target.files?.[0] && handleFile(e.target.files[0])}
          />

          {stage === "idle" && (
            <>
              <p className="text-sm font-medium text-slate-700">Drag & drop your file here, or click to browse</p>
              <p className="mt-1 text-xs text-slate-500">CSV, XLSX, or Parquet — size limits depend on your plan</p>
            </>
          )}

          {stage === "uploading" && (
            <div>
              <p className="text-sm font-medium text-slate-700">Uploading... {progress}%</p>
              <div className="mx-auto mt-3 h-2 w-full max-w-xs overflow-hidden rounded-full bg-slate-200">
                <div className="h-full bg-brand-600 transition-all" style={{ width: `${progress}%` }} />
              </div>
            </div>
          )}

          {stage === "processing" && (
            <div>
              <div className="mx-auto h-8 w-8 animate-spin rounded-full border-2 border-brand-600 border-t-transparent" />
              <p className="mt-3 text-sm font-medium text-slate-700">Analyzing your dataset...</p>
              <p className="mt-1 text-xs text-slate-500">Running profiling, quality checks, and AI insight generation.</p>
            </div>
          )}

          {stage === "error" && (
            <div>
              <p className="text-sm font-medium text-red-700">{error}</p>
              <button
                onClick={(e) => { e.stopPropagation(); setStage("idle"); setError(null); }}
                className="btn-secondary mt-4"
              >
                Try again
              </button>
            </div>
          )}
        </div>

        <ul className="mt-6 space-y-1 text-xs text-slate-500">
          <li>• Files are validated for structure, size, and content — not just their extension.</li>
          <li>• Uploaded files are deleted immediately after processing.</li>
          <li>• Only aggregated statistics are sent to the AI model, never your raw data.</li>
        </ul>
      </div>
    </main>
  );
}
