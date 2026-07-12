const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export interface PipelineResult {
  case_id: string;
  recommendation: string;
  weighted_confidence_score: number;
  gates: Record<string, string>;
  agent_outputs: Record<string, any>;
  requires_human_review: boolean;
  record_id?: number;
}

export interface QueueRecord {
  id: number;
  case_id: string;
  diagnosis: string;
  requested_treatment: string;
  ai_recommendation: string;
  weighted_confidence_score: number;
  reviewer_decision: string | null;
  reviewer_notes: string | null;
  created_at: string;
}

export async function submitCase(payload: Record<string, any>): Promise<PipelineResult> {
  const res = await fetch(`${API}/review`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail ?? `API error ${res.status}`);
  }
  return res.json();
}

export async function uploadPrescription(file: File): Promise<Record<string, any>> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${API}/upload-prescription`, {
    method: "POST",
    body: form,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail ?? `API error ${res.status}`);
  }
  return res.json();
}

export async function fetchQueue(): Promise<QueueRecord[]> {
  const res = await fetch(`${API}/requests`);
  if (!res.ok) throw new Error(`API error ${res.status}`);
  return res.json();
}

export async function submitDecision(
  id: number,
  decision: "ACCEPT" | "OVERRIDE",
  notes: string
): Promise<void> {
  const res = await fetch(`${API}/requests/${id}/decision`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ decision, notes }),
  });
  if (!res.ok) throw new Error(`API error ${res.status}`);
}
