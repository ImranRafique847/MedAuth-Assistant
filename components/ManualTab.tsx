"use client";
import { useState } from "react";
import { submitCase, PipelineResult } from "@/lib/api";
import PipelineTrace from "./PipelineTrace";
import RecommendationBadge from "./RecommendationBadge";
import AgentCard from "./AgentCard";

const empty = {
  case_id: "CASE-NEW-001",
  member_id: "MEM-1001",
  patient_age: 45,
  diagnosis: "",
  clinical_notes: "",
  requested_treatment: "",
  prior_treatments_tried: "",
};

export default function ManualTab() {
  const [form, setForm] = useState(empty);
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<PipelineResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const set = (k: string, v: any) => setForm({ ...form, [k]: v });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setRunning(true);
    setError(null);
    setResult(null);
    try {
      const res = await submitCase({
        ...form,
        patient_age: Number(form.patient_age),
        prior_treatments_tried: form.prior_treatments_tried
          .split(",").map((s) => s.trim()).filter(Boolean),
      });
      setResult(res);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setRunning(false);
    }
  };

  return (
    <div className="space-y-8">
      <div>
        <h2 className="font-display text-2xl mb-1">Submit a request manually</h2>
        <p className="text-muted text-sm">
          Test member IDs —{" "}
          <span className="font-mono-data text-signal-pass">MEM-1001</span> active,{" "}
          <span className="font-mono-data text-signal-fail">MEM-1002</span> inactive.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-4 border border-panelLine rounded-xl p-6 bg-panel/60">
        <Row>
          <Field label="Case ID" value={form.case_id} onChange={(v) => set("case_id", v)} />
          <Field label="Member ID" value={form.member_id} onChange={(v) => set("member_id", v)} mono />
        </Row>
        <Field label="Patient age" value={form.patient_age} onChange={(v) => set("patient_age", v)} />
        <Field label="Diagnosis" value={form.diagnosis} onChange={(v) => set("diagnosis", v)} area />
        <Field label="Clinical notes" value={form.clinical_notes} onChange={(v) => set("clinical_notes", v)} area />
        <Field label="Requested treatment" value={form.requested_treatment} onChange={(v) => set("requested_treatment", v)} />
        <Field label="Prior treatments (comma separated)" value={form.prior_treatments_tried}
          onChange={(v) => set("prior_treatments_tried", v)} />
        <button type="submit" disabled={running}
          className="px-5 py-2 rounded-full bg-signal-accent text-ink font-medium text-sm
                     disabled:opacity-40 hover:brightness-110 transition">
          {running ? "Running pipeline…" : "Run AI review"}
        </button>
      </form>

      {error && <div className="text-signal-fail text-sm font-mono-data">{error}</div>}

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

function Row({ children }: { children: React.ReactNode }) {
  return <div className="grid grid-cols-2 gap-4">{children}</div>;
}

function Field({ label, value, onChange, area, mono }: {
  label: string; value: any; onChange: (v: string) => void; area?: boolean; mono?: boolean;
}) {
  const cls = `w-full bg-ink/60 border border-panelLine rounded-lg px-3 py-2 text-sm
               text-paper focus:border-signal-accent transition ${mono ? "font-mono-data" : ""}`;
  return (
    <label className="block space-y-1.5">
      <span className="text-xs uppercase tracking-wide text-muted font-mono-data">{label}</span>
      {area ? (
        <textarea value={value} onChange={(e) => onChange(e.target.value)} rows={3} className={cls} />
      ) : (
        <input value={value} onChange={(e) => onChange(e.target.value)} className={cls} />
      )}
    </label>
  );
}
