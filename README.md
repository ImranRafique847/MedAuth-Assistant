# MedAuth Assistant — 5-Agent Prior Authorization AI

An AI pipeline that automates health insurance prior authorization review using
5 specialized agents on AWS Bedrock (Claude), with a FastAPI backend and
Streamlit reviewer UI.

Inspired by Microsoft's Prior-Authorization-Multi-Agent-Solution-Accelerator,
rebuilt for AWS Bedrock + a solo-developer-friendly flat Python structure.

---

## Architecture

```
Submit case (Manual form or PDF upload)
            |
            v
    [Phase 0]
    Eligibility Agent          ← Is this patient an active, paid member?
            |                    If NOT → DENY - NOT ELIGIBLE (stops here,
            |                              no LLM calls wasted)
            v
    [Phase 1 — parallel]
    Compliance Agent  +  Clinical Agent
            |                    |
            |                    v
            |            [Phase 2]
            |            Coverage Agent  (needs Clinical's output)
            |                    |
            v                    v
                [Phase 3]
                Synthesis Agent  (weighted score + 3-gate rubric)
                        |
                        v
                Human Reviewer  (Accept / Override)
                        |
                        v
                Audit trail  (SQLite)
```

---

## Agents

| Agent | Phase | Uses LLM? | Job |
|---|---|---|---|
| **Eligibility Agent** | 0 | No | Looks up member ID in `members.json`; checks premium paid, coverage active, dates valid |
| **Compliance Agent** | 1 (parallel) | Yes — Claude | Checks administrative completeness of the PA request |
| **Clinical Agent** | 1 (parallel) | Yes — Claude | Evaluates medical necessity and step therapy |
| **Coverage Agent** | 2 | No | Matches treatment against payer policies in `policies.json` |
| **Synthesis Agent** | 3 | No | Weighted score (40% coverage + 30% clinical + 20% compliance + 10% policy match) + 3-gate rubric → draft recommendation |

---

## Project Structure

```
MedAuth-Assistant/
├── eligibility_agent.py       # Step 0: member eligibility database lookup
├── clinical_agent.py          # Medical necessity evaluation via Claude
├── compliance_agent.py        # Administrative completeness check via Claude
├── coverage_agent.py          # Payer policy rules check (deterministic)
├── synthesis_agent.py         # Weighted scoring + recommendation (deterministic)
├── prescription_parser.py     # Extracts structured data from uploaded PDF
├── orchestrator.py            # Wires all 5 agents in correct order
├── main.py                    # FastAPI backend
├── app.py                     # Streamlit reviewer UI
├── database.py                # SQLite audit trail
├── members.json               # Sample member records (eligibility testing)
├── cases.json                 # Sample PA test cases
├── policies.json              # Sample payer policies
└── requirements.txt
```

---

## Setup

**1. Install dependencies:**
```bash
pip install -r requirements.txt
```

**2. Configure AWS credentials:**
```bash
aws configure
```
Or create a `.env` file (see `.env` template — never commit this):
```
AWS_ACCESS_KEY_ID=your_key
AWS_SECRET_ACCESS_KEY=your_secret
AWS_REGION=us-east-1
BEDROCK_MODEL_ID=us.anthropic.claude-sonnet-4-5-20250929-v1:0
```

**3. Enable Bedrock model access:**

In the [AWS Bedrock console](https://console.aws.amazon.com/bedrock) → Model access →
request access to your chosen Claude model. Then update `BEDROCK_MODEL_ID` in `.env`
to match the inference profile ID (use `us.` prefix for cross-region profiles).

---

## Running

**Option A — quick pipeline test (terminal only):**
```bash
python orchestrator.py
```
Runs two test cases: MEM-1001 (eligible → full pipeline) and MEM-1002
(ineligible → short-circuits at Step 0).

**Option B — full app (API + UI):**

Terminal 1 — start the backend:
```bash
uvicorn main:app --reload
```

Terminal 2 — start the frontend:
```bash
streamlit run app.py
```

Open `http://localhost:8501`. Use the **Manual Entry** tab to submit cases,
or the **Upload Prescription** tab to upload a typed PDF. Results appear
in the **Review Queue** tab for Accept/Override.

**Test member IDs:**
| Member ID | Status |
|---|---|
| MEM-1001 | Active, paid — eligible |
| MEM-1002 | Inactive, overdue — ineligible (pipeline stops here) |
| MEM-1003 | Active, paid — eligible |
| MEM-1004 | Expired — ineligible |
| MEM-1005 | Active, paid — eligible |

---

## How the Decision is Made

1. **Eligibility Agent** — deterministic DB lookup. Fails fast if member is not active/paid.
2. **Compliance + Clinical** — run in parallel via `asyncio.gather`. Both call Claude on Bedrock.
3. **Coverage Agent** — runs after Clinical (needs its output). Keyword-matches treatment to `policies.json`.
4. **Synthesis Agent** applies:
   - A **3-gate rubric** (Compliance, Clinical, Coverage — all must PASS to auto-approve)
   - A **weighted confidence score**: 40% coverage + 30% clinical + 20% compliance + 10% policy match
5. Output is always a **draft recommendation** — a human reviewer must Accept or Override it.
   Every decision is logged with a timestamp for the audit trail.

**Recommendation values:**
- `APPROVE` — all gates PASS and score ≥ 0.75
- `DENY - NOT ELIGIBLE` — eligibility gate failed
- `DENY - CRITERIA NOT MET` — clinical or coverage gate failed
- `PEND - INCOMPLETE REQUEST` — compliance gate failed
- `PEND - MANUAL REVIEW REQUIRED` — gates pass but score below threshold

---

## Known Limitations / What to Extend Next

- Coverage Agent uses simple keyword matching — swap in a vector DB (e.g. Chroma)
  for semantic search against policy documents
- Prescription parser supports **typed PDFs only** — handwritten OCR is too
  unreliable for medical use
- No appeal-letter auto-drafting yet (natural next feature on denial flow)
- SQLite is fine for a showcase; swap to Postgres for production
- `members.json` is a flat file — replace with a real member database query
