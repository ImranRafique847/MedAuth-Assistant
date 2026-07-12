"use client";
import { useEffect, useState } from "react";
import { fetchQueue, submitDecision, QueueRecord } from "@/lib/api";
import RecommendationBadge from "./RecommendationBadge";

export default function QueueTab() {
  const [records, setRecords] = useState<QueueRecord[]>([]);
  const [notes, setNotes] = useState<Record<number, string>>({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchQueue();
      setRecords(data);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const decide = async (id: number, decision: "ACCEPT" | "OVERRIDE") => {
    await submitDecision(id, decision, notes[id] || "");
    load();
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="font-display text-2xl">Human reviewer queue</h2>
        <button onClick={load}
          className="text-xs font-mono-data text-muted border border-panelLine rounded-full px-3 py-1.5
                     hover:text-paper hover:border-signal-accent transition">
          refresh
        </button>
      </div>

      {error && <div className="text-signal-fail text-sm font-mono-data">{error}</div>}
      {loading && <div className="text-muted text-sm">Loading…</div>}

      <div className="space-y-4">
        {records.map((r) => (
          <div key={r.id} className="border border-panelLine rounded-xl p-5 bg-panel/60 space-y-3">
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="font-mono-data text-sm text-paper/90">{r.case_id}</p>
                <p className="text-sm text-muted mt-0.5">{r.diagnosis} → {r.requested_treatment}</p>
              </div>
              <RecommendationBadge recommendation={r.ai_recommendation} />
            </div>
            <p className="text-xs font-mono-data text-muted">confidence {r.weighted_confidence_score}</p>
            {r.reviewer_decision ? (
              <p className="text-sm text-signal-pass font-mono-data">
                ✓ {r.reviewer_decision} — {r.reviewer_notes || "no notes"}
              </p>
            ) : (
              <div className="flex items-center gap-3 pt-2">
                <input placeholder="notes (optional)" value={notes[r.id] || ""}
                  onChange={(e) => setNotes({ ...notes, [r.id]: e.target.value })}
                  className="flex-1 bg-ink/60 border border-panelLine rounded-lg px-3 py-1.5 text-sm
                             text-paper focus:border-signal-accent transition" />
                <button onClick={() => decide(r.id, "ACCEPT")}
                  className="px-4 py-1.5 rounded-full bg-signal-pass/15 text-signal-pass
                             border border-signal-pass/40 text-sm hover:bg-signal-pass/25 transition">
                  Accept
                </button>
                <button onClick={() => decide(r.id, "OVERRIDE")}
                  className="px-4 py-1.5 rounded-full bg-signal-fail/15 text-signal-fail
                             border border-signal-fail/40 text-sm hover:bg-signal-fail/25 transition">
                  Override
                </button>
              </div>
            )}
          </div>
        ))}
        {!loading && records.length === 0 && (
          <p className="text-muted text-sm">No requests yet — submit one from Upload or Manual Entry.</p>
        )}
      </div>
    </div>
  );
}
