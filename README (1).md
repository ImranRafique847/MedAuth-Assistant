# MedAuth Assistant — Next.js UI

A clinical-panel styled frontend for the MedAuth Assistant prior authorization
pipeline. Replaces the Streamlit prototype with a production-style Next.js app.

## Design

Dark ink-navy surface, a serif display face (Fraunces) for headings, monospace
(IBM Plex Mono) for IDs/scores/gate states — reads like a lab instrument panel
rather than a generic healthcare app. The signature element is the pipeline
trace: an EKG-style line that lights up each of the four downstream gates
(Eligibility, Compliance, Clinical, Coverage) as results come back.

## Setup

```bash
npm install
cp .env.local.example .env.local
```

Edit `.env.local` if your FastAPI backend runs somewhere other than
`http://localhost:8000`.

## Run

```bash
npm run dev
```

Open http://localhost:3000

**Backend must be running first:**
```bash
uvicorn main:app --reload
```

## IMPORTANT — enable CORS on the backend

Next.js runs on a different port (3000) than FastAPI (8000), so the backend
must allow cross-origin requests. Add this to `main.py`:

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)
```

Without this, the browser will block every request from the Next.js app to
the API with a CORS error.

## Structure

```
app/
  layout.tsx        # root layout, loads global styles
  page.tsx           # tab navigation + page shell
  globals.css        # design tokens, fonts, pulse animation
components/
  PipelineTrace.tsx  # signature EKG-style gate tracker
  RecommendationBadge.tsx
  AgentCard.tsx      # expandable per-agent JSON output
  UploadTab.tsx       # PDF upload -> extract -> review
  ManualTab.tsx       # manual form entry -> review
  QueueTab.tsx        # human reviewer accept/override queue
lib/
  api.ts              # typed fetch client for the FastAPI backend
```

## Build for production

```bash
npm run build
npm start
```
