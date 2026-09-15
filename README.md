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

---

## Production Cloud Deployment (Render + Vercel + Neon)

### 1. Push to GitHub
Ensure `.env` files and local virtualenvs are untracked (protected automatically by `.gitignore`):
```powershell
git add .
git commit -m "feat: prepare production cloud deployment for Render and Vercel"
git branch -M main
git remote add origin https://github.com/<YOUR_USERNAME>/<YOUR_REPOSITORY>.git
git push -u origin main
```

### 2. Deploy Backend on Render
1. Go to [Render Dashboard](https://dashboard.render.com/) -> **New** -> **Web Service**.
2. Connect your GitHub repository.
3. Configure the service:
   - **Name**: `pramaan-backend`
   - **Root Directory**: `backend`
   - **Environment**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   - **Health Check Path**: `/health`
4. Add **Environment Variables** in Render:
   - `PYTHON_VERSION`: `3.11.9`
   - `DATABASE_URL`: `postgresql+asyncpg://lmcs_app:<PASSWORD>@<HOST>/neondb?ssl=require`
   - `DATABASE_ADMIN_URL`: `postgresql+asyncpg://neondb_owner:<PASSWORD>@<HOST>/neondb?ssl=require`
   - `GROQ_API_KEY`: `gsk_...`
   - `GROQ_MODEL`: `qwen/qwen3.8-27b`
   - `JWT_SECRET`: `<32-character-secret>`
   - `VERIFY_BASE_URL`: `https://<YOUR_RENDER_SUBDOMAIN>.onrender.com/verify`
5. Click **Deploy Web Service**. Once deployed, copy your Render URL (e.g. `https://pramaan-backend.onrender.com`).

### 3. Deploy Frontend on Vercel
1. Go to [Vercel Dashboard](https://vercel.com/) -> **Add New Project**.
2. Import your GitHub repository.
3. In the project setup screen:
   - **Framework Preset**: `Vite`
   - **Root Directory**: Click `Edit` and select `new_frontend`
   - **Build Command**: `npm run build`
   - **Output Directory**: `dist`
4. Expand **Environment Variables** and add:
   - `VITE_API_BASE_URL`: `https://<YOUR_RENDER_SUBDOMAIN>.onrender.com/api`
5. Click **Deploy**. Vercel will build and serve your inspector portal. All API requests and static evidence captures will route to Render seamlessly.

