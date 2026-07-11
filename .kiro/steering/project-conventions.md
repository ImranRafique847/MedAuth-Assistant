# MedAuth Assistant — Project Conventions

## Stack
- **AI/LLM**: AWS Bedrock with Anthropic Claude (claude-3-5-sonnet-20241022-v2:0), called via `boto3`
- **Backend**: FastAPI + SQLite (via `database.py`), served with `uvicorn`
- **Frontend**: Streamlit (`app.py`), communicates with the backend over HTTP
- **Python deps**: managed in `requirements.txt` — boto3, fastapi, uvicorn, pydantic, streamlit, requests, python-dotenv

## Agent Pipeline
The system uses a 4-agent pipeline orchestrated in `orchestrator.py`:

1. **Compliance Agent** (`compliance_agent.py`) — runs in parallel with Clinical; checks administrative/procedural completeness only, no medical judgment
2. **Clinical Agent** (`clinical_agent.py`) — runs in parallel with Compliance; evaluates medical necessity via Claude on Bedrock
3. **Coverage Agent** (`coverage_agent.py`) — runs after Clinical (depends on its output); checks against payer policies in `policies.json` using keyword matching, no LLM
4. **Synthesis Agent** (`synthesis_agent.py`) — pure Python, no LLM; combines all three outputs using a weighted score + 3-gate rubric to produce a draft recommendation

Execution order: Phase 1 (Compliance + Clinical in parallel via `asyncio.gather`) → Phase 2 (Coverage) → Phase 3 (Synthesis).

## Conventions

### Adding or modifying agents
- Each agent exposes an `evaluate_case(case: dict) -> dict` function as its public interface
- Agents that call Bedrock must handle `ClientError` and return a graceful fallback dict on failure
- Claude responses are always expected as JSON; strip markdown fences before parsing
- Always include `case_id` in the returned dict

### Bedrock calls
- Use `boto3.client("bedrock-runtime", region_name=AWS_REGION)`
- `BEDROCK_MODEL_ID` and `AWS_REGION` are module-level constants — keep them easy to change
- `max_tokens` should be conservative (400–600) unless there's a clear reason for more

### Data
- `cases.json` — sample PA test cases with `expected_outcome` for testing
- `policies.json` — payer policies used by the Coverage Agent; add new policies here, not in code

### Database
- All persistence goes through `database.py` — do not add direct `sqlite3` calls elsewhere
- Schema lives in `init_db()`; migrations are manual for now (SQLite, showcase scope)

### API
- All routes live in `main.py`; follow existing REST patterns (`/review`, `/requests`, `/requests/{id}/decision`)
- Use Pydantic models for all request/response shapes

### Frontend
- `app.py` is the only frontend file; keep UI logic and API calls together there
- Always call the FastAPI backend via `API_URL` — no direct agent imports in the frontend

## Do Not
- Do not introduce new frameworks, ORMs, vector DBs, or message queues without discussing first
- Do not add LLM calls to the Coverage Agent or Synthesis Agent — they are intentionally deterministic
- Do not bypass `database.py` for persistence
- Do not push secrets or AWS credentials into source files — use env vars or `aws configure`
