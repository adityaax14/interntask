# SwasthiQ EOD Billing & Analytics Agent

A full-stack application that ingests a clinic's daily billing log and produces:

1. **Deterministic EOD Reconciliation** — total billed, collected, outstanding, refunds (split by payment mode)
2. **Analytics** — revenue by hour of day, top medicines by quantity and revenue
3. **AI Narrative Summary** — LLM-generated WhatsApp-style summary with every figure traced to the deterministic report

## Live Demo

- **Frontend (Vercel):** [https://interntask-sand.vercel.app/](https://interntask-sand.vercel.app/)
- **Backend API (Render):** [https://interntask-1-8qj6.onrender.com](https://interntask-1-8qj6.onrender.com)
*(Note: The backend is hosted on Render's free tier. The frontend is configured to ping the backend to keep it awake while the application is open.)*

## Tech Stack

| Layer    | Technology                                    |
|----------|-----------------------------------------------|
| Backend  | Python 3.13, FastAPI, Pydantic                |
| Frontend | React 19, Vite, Recharts, React Router        |
| LLM      | Groq API (Llama 3.3 70B, OpenAI-compatible)  |
| Storage  | In-memory (dict-based)                        |

## Project Structure

```
├── backend/
│   ├── app/
│   │   ├── main.py            # FastAPI entry point
│   │   ├── models.py          # Pydantic data models
│   │   ├── validators.py      # Row-level billing log validation
│   │   ├── reconciliation.py  # Deterministic reconciliation engine
│   │   ├── analytics.py       # Deterministic analytics engine
│   │   ├── narrative.py       # LLM narrative generator (agentic layer)
│   │   ├── routes.py          # REST API endpoints
│   │   └── storage.py         # In-memory storage
│   ├── tests/
│   │   └── test_reconciliation.py
│   ├── requirements.txt
│   └── .env
├── frontend/
│   └── src/
│       ├── App.jsx
│       ├── api.js             # API client
│       ├── index.css          # Design system
│       ├── components/
│       │   └── Sidebar.jsx
│       └── pages/
│           ├── Reconciliation.jsx
│           ├── Analytics.jsx
│           └── Narrative.jsx
├── sample_data/               # 3 clinic-day billing logs
└── README.md
```

## Quick Start

### Prerequisites

- Python 3.10+
- Node.js 18+
- npm

### Backend

```bash
cd backend

# Install dependencies
pip install -r requirements.txt

# Set your Groq API key in .env
# GROQ_API_KEY=gsk_xxx

# Start the server
uvicorn app.main:app --reload --port 8000

# Run tests
python -m pytest tests/ -v
```

### Frontend

```bash
cd frontend

# Install dependencies
npm install

# Start dev server
npm run dev
```

Open [http://localhost:5173](http://localhost:5173) and upload a billing log from the `sample_data/` directory.

## REST API Contracts

### `POST /api/billing/upload`

Upload a billing log JSON file.

**Request:** `multipart/form-data` with field `file` (JSON file)

**Response:**
```json
{
  "status": "ok",
  "clinic_id": "CLN-KNP-014",
  "date": "2026-07-27",
  "valid_records": 18,
  "rejected_records": 1,
  "validation_errors": [
    {
      "visit_id": "V-20260727-019",
      "field": "payment_mode",
      "message": "Missing required field 'payment_mode'. Every billing record must include: ..."
    }
  ]
}
```

### `GET /api/billing/reconciliation/{clinic_id}/{date}`

**Response:**
```json
{
  "clinic_id": "CLN-KNP-014",
  "date": "2026-07-27",
  "total_billed_paise": 326000,
  "total_collected_paise": 317200,
  "total_outstanding_paise": 2800,
  "total_refunds_paise": 0,
  "total_discount_paise": 6000,
  "visit_count": 18,
  "refund_count": 0,
  "pending_visit_count": 3,
  "mode_breakdown": [
    { "mode": "cash", "billed_paise": 129000, "collected_paise": 127000, "outstanding_paise": 500 },
    { "mode": "card", "billed_paise": 87000, "collected_paise": 82700, "outstanding_paise": 800 },
    { "mode": "upi", "billed_paise": 110000, "collected_paise": 107500, "outstanding_paise": 500 }
  ]
}
```

### `GET /api/billing/analytics/{clinic_id}/{date}`

**Response:**
```json
{
  "clinic_id": "CLN-KNP-014",
  "date": "2026-07-27",
  "revenue_by_hour": [
    { "hour": 9, "label": "9am", "revenue_paise": 9000 },
    { "hour": 10, "label": "10am", "revenue_paise": 56500 },
    ...
  ],
  "peak_hour": { "hour": 13, "label": "1pm", "revenue_paise": 75500 },
  "top_medicines_by_qty": [...],
  "top_medicines_by_revenue": [...]
}
```

### `GET /api/billing/narrative/{clinic_id}/{date}`

**Response:**
```json
{
  "clinic_id": "CLN-KNP-014",
  "date": "2026-07-27",
  "narrative": "Good evening! Here's today's summary...",
  "traced_figures": [
    { "display_value": "₹3,260", "field_name": "total_billed" },
    { "display_value": "₹3,172", "field_name": "total_collected" },
    ...
  ],
  "status": "success"
}
```

### `GET /api/billing/dates/{clinic_id}`

Returns available dates for a clinic.

### `GET /api/billing/clinics`

Returns list of clinics with uploaded data.

## Data Consistency

### How the deterministic layer ensures correctness

1. **Integer paise throughout** — All monetary values are stored as `int` (paise). No floating-point arithmetic is ever performed on money. Conversion to rupees happens only at the display/API response layer.

2. **Ground truth separation** — The reconciliation and analytics engines (`reconciliation.py`, `analytics.py`) never call an LLM. They compute results from validated records using pure arithmetic.

3. **Row-level validation** — Each billing record is validated against the schema before processing. Malformed rows (including duplicate `visit_id`s within the same file) are rejected with specific, actionable error messages (field name + what's wrong + how to fix). Partial processing continues for valid rows.

4. **LLM grounding** — The narrative layer receives the deterministic report as structured input. Every figure the LLM mentions must trace back to a report field. If the LLM produces a number not in the report, the auto-tracing fallback catches it.

5. **Idempotent storage** — Uploading the same file twice overwrites the previous data for that (clinic_id, date) pair, ensuring consistency.

### Edge cases handled

| Scenario | Handling |
|---|---|
| All-refunds day (July 25) | Billed/collected/outstanding = 0; refunds computed correctly; analytics empty (does not artificially drive billed/collected into negatives) |
| Empty day (July 26) | Graceful all-zero report; date extracted from filename |
| Missing payment_mode (V-019) | Rejected with specific error; remaining 18 records processed |
| Misspelled drug name (PARACETMOL) | Treated as distinct drug — the system does not autocorrect |
| Refund with positive amount | Validation error: "Refund amounts should be negative" |
| LLM failure/malformed response | Returns error status with message; does not crash |
| Extremely large file upload | Strict 10MB limit enforced on both frontend and backend to protect server memory (returns `413 Payload Too Large`) |

## Running Tests

```bash
cd backend
python -m pytest tests/ -v
```

Tests cover:
- ✅ Happy path reconciliation (July 27 — 18 valid records)
- ✅ All-refunds day (July 25)
- ✅ Empty day (July 26)
- ✅ Malformed row rejection (missing fields, invalid values)
- ✅ Paise precision (no floating-point errors)
- ✅ Payment mode breakdown correctness
- ✅ Peak hour identification
- ✅ Medicine ranking accuracy
