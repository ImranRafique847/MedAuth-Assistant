"use client";
import { useState, useRef } from "react";
import { uploadPrescription, submitCase, PipelineResult } from "@/lib/api";
import PipelineTrace from "./PipelineTrace";
import RecommendationBadge from "./RecommendationBadge";
import AgentCard from "./AgentCard";

export default function UploadTab() {
  const [extracted, setExtracted] = useState<Record<string, any> | null>(null);
  const [extracting, setExtracting] = useState(false);
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<PipelineResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const handleUpload = async () => {
    const file = fileRef.current?.files?.[0];
    if (!file) return;
    setExtracting(true);
    setError(null);
    setExtracted(null);
    setResult(null);
    try {
      const data = await uploadPrescription(file);
      setExtracted(data);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setExtracting(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!extracted) return;
    const fd = new FormData(e.currentTarget);
    setRunning(true);
    setError(null);
    setResult(null);
    try {
      const res = await submitCase({
        case_id: fd.get("case_id"),
        member_id: fd.get("member_id"),
        patient_age: Number(fd.get("patient_age")),
        diagnosis: fd.get("diagnosis"),
        clinical_notes: fd.get("clinical_notes"),
        requested_treatment: fd.get("requested_treatment"),
        prior_treatments_tried: String(fd.get("prior_treatments_tried") ?? "")
          .split(",").map((s) => s.trim()).filter(Boolean),
      });
      setResult(res);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setRunning(false);
    }
  };

  const cls = `w-full bg-ink/60 border border-panelLine rounded-lg px-3 py-2 text-sm
               text-paper focus:border-signal-accent transition`;

  return (
    <div className="space-y-8">
      <div>
        <h2 className="font-display text-2xl mb-1">Upload a prescription</h2>
        <p className="text-muted text-sm">Typed PDFs only — handwritten prescriptions are not supported.</p>
      </div>

      <div className="border border-panelLine rounded-xl p-6 bg-panel/60 space-y-4">
        <label className="block space-y-2">
          <span className="text-xs uppercase tracking-wide text-muted font-mono-data">PDF file</span>
          <input ref={fileRef} type="file" accept=".pdf"
            className="block w-full text-sm text-muted file:mr-4 file:py-2 file:px-4
                       file:rounded-full file:border file:border-panelLine file:text-xs
                       file:font-mono-data file:bg-ink/60 file:text-paper/80
                       hover:file:border-signal-accent transition" />
        </label>
        <button onClick={handleUpload} disabled={extracting}
          className="px-5 py-2 rounded-full bg-signal-accent text-ink font-medium text-sm
                     disabled:opacity-40 hover:brightness-110 transition">
          {extracting ? "Extracting…" : "Extract data"}
        </button>
      </div>

      {error && <div className="text-signal-fail text-sm font-mono-data">{error}</div>}

      {extracted && (
        <form onSubmit={handleSubmit}
          className="border border-panelLine rounded-xl p-6 bg-panel/60 space-y-4">
          <p className="text-xs font-mono-data text-muted">
            Extraction confidence: <span className="text-paper">{extracted.extraction_confidence ?? "unknown"}</span>
            — review and correct before submitting.
          </p>
          {[
            ["case_id", "Case ID", extracted.case_id ?? ""],
            ["member_id", "Member ID", extracted.member_id ?? ""],
            ["patient_age", "Patient age", extracted.patient_age ?? ""],
            ["diagnosis", "Diagnosis", extracted.diagnosis ?? ""],
            ["clinical_notes", "Clinical notes", extracted.clinical_notes ?? ""],
            ["requested_treatment", "Requested treatment", extracted.requested_treatment ?? ""],
            ["prior_treatments_tried", "Prior treatments (comma separated)",
              (extracted.prior_treatments_tried ?? []).join(", ")],
          ].map(([name, label, defaultVal]) => (
            <label key={name as string} className="block space-y-1.5">
              <span className="text-xs uppercase tracking-wide text-muted font-mono-data">{label}</span>
              {(name === "diagnosis" || name === "clinical_notes") ? (
                <textarea name={name as string} defaultValue={defaultVal as string} rows={3} className={cls} />
              ) : (
                <input name={name as string} defaultValue={defaultVal as string} className={cls} />
              )}
            </label>
          ))}
          <button type="submit" disabled={running}
            className="px-5 py-2 rounded-full bg-signal-accent text-ink font-medium text-sm
                       disabled:opacity-40 hover:brightness-110 transition">
            {running ? "Running pipeline…" : "Run AI review"}
          </button>
        </form>
      )}

      {(running || result) && (
        <div className="border border-panelLine rounded-xl p-6 bg-panel/60 space-y-6">
          <PipelineTrace gates={result?.gates} running={running} />
          {result && (
            <>
              <div className="flex items-center gap-4">
                <RecommendationBadge recommendation={result.recommendation} />
                <span className="font-mono-data text-sm text-muted">score {result.weighted_confidence_score}</span>
              </div>
              <div className="grid gap-3">
                {Object.entries(result.agent_outputs).map(([name, data]) => (
                  <AgentCard key={name} name={name} data={data} />
                ))}
              </div>
              {result.record_id && (
                <p className="text-sm text-muted">Saved as record #{result.record_id} — review it in the Queue tab.</p>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}
