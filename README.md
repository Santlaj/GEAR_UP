# Legal Metrology Compliance Scanning Platform

Government enforcement platform for Legal Metrology (Packaged Commodities) Rules, 2011.

## Docs
- `rules.md` — hard engineering constraints (read before editing)
- `DECISIONS.md` — stack choices
- `shared/schema.ts` — generated from `backend/app/schema.py` (do not hand-edit)

## Layout
| Path | Role |
|------|------|
| `backend/` | FastAPI, shared Pydantic schema, rule engine, reports, RLS SQL |
| `new_frontend/` | Inspector PWA (offline queue + Tesseract geometry) |
| `admin/` | District / state / national / auditor dashboards |
| `shared/` | Generated TypeScript types |

## Quick start
```powershell
# DB
docker compose up -d db

# API
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
copy .env.example .env
python -m app.seed
uvicorn app.main:app --reload --port 8000

# Inspector PWA (port 5173)
cd ..\new_frontend
npm install
npm run dev

# Admin portal (port 5174)
cd ..\admin
npm install
npm run dev
```

Demo users (see seed): `inspector@lmcs.gov.in` / `inspect-demo`, `district@lmcs.gov.in` / `district-demo`.

## §8 self-check status (current foundation)
- [x] Shared schema single source (`backend/app/schema.py` → `shared/schema.ts`)
- [x] Jurisdiction query params overridden by JWT (`apply_server_scope` + tests)
- [x] Rule engine has zero LLM/network calls
- [x] PDF + DOCX from same `ScanRecord`
- [x] Override creates new hashed version (no mutate)
- [x] Audit + scan_reports APPEND-only grants in `backend/sql/rls.sql`
- [x] GPS + inspector_id required on capture path
- [x] RLS policies + probe test (`tests/test_rls.py`)
- [ ] Full role dashboards (inspector mgmt, trends, exports, 2FA, delegation) — scaffolded; expand next
