# Prior Authorization AI — Full Multi-Agent System

A 4-agent AI pipeline that automates health insurance prior authorization
review, inspired by Microsoft's Prior-Authorization-Multi-Agent-Solution-Accelerator,
rebuilt for AWS Bedrock + a solo-freelancer-friendly stack.

## Architecture

```
Submit case
    |
    v
[Phase 1 - parallel]
Compliance Agent  +  Clinical Agent
    |                    |
    |                    v
    |            [Phase 2]
    |            Coverage Agent (needs Clinical's output)
    |                    |
    v                    v
        [Phase 3]
        Synthesis Agent (weighted scoring + 3-gate rubric)
                |
                v
        Human Reviewer (Accept / Override)
                |
                v
        Saved to audit trail (SQLite)
```

## Project structure

```
prior-auth-ai/
├── agents/
│   ├── clinical_agent.py      # Checks medical necessity
│   ├── compliance_agent.py    # Checks paperwork completeness
│   ├── coverage_agent.py      # Checks against payer policy rules
│   └── synthesis_agent.py     # Combines all 3 into final recommendation
├── orchestrator.py             # Runs agents in correct parallel/sequential order
├── api/
│   └── main.py                 # FastAPI backend
├── db/
│   └── database.py              # SQLite audit trail storage
├── frontend/
│   └── app.py                   # Streamlit reviewer UI
├── data/
│   ├── sample_prescriptions/cases.json   # 5 test cases
│   └── sample_policies/policies.json     # 5 sample payer policies
├── tests/
│   └── test_clinical_agent.py
└── requirements.txt
```

## Setup

1. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

2. Configure AWS credentials:
   ```
   aws configure
   ```
   or set env vars: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`

3. In AWS Bedrock console, request access to a Claude model, then update
   `BEDROCK_MODEL_ID` in `agents/clinical_agent.py` and
   `agents/compliance_agent.py` to match your exact model ID.

## Running it

**Option A — quick pipeline test (terminal only):**
```
python orchestrator.py
```
Runs one sample case through all 4 agents and prints the final decision.

**Option B — full app (API + UI):**

Terminal 1 — start the backend:
```
uvicorn api.main:app --reload
```

Terminal 2 — start the frontend:
```
streamlit run frontend/app.py
```

Then open the Streamlit URL (usually http://localhost:8501), submit a case
in "Submit New Case", and manage decisions in "Review Queue".

**Option C — run test suite:**
```
python tests/test_clinical_agent.py
```

## How the decision is made

- **Compliance Agent** + **Clinical Agent** run in parallel (`asyncio.gather`)
- **Coverage Agent** runs after, using Clinical's output
- **Synthesis Agent** applies:
  - A 3-gate rubric (Compliance, Clinical, Coverage — all must PASS to auto-approve)
  - A weighted confidence score: 40% coverage + 30% clinical + 20% compliance + 10% policy match
- Final output is always a **draft recommendation** — a human reviewer must
  Accept or Override it before it's final. This is logged with a timestamp
  for the audit trail.

## Known limitations / what to extend next

- Coverage Agent uses simple keyword matching, not semantic search — swap in
  a vector DB (e.g. Chroma) for real fuzzy matching against policy documents
- No appeal-letter auto-drafting yet (good next feature — see denial flow)
- No PDF/document upload — assumes structured text input
- SQLite is fine for a showcase; swap to Postgres for production
