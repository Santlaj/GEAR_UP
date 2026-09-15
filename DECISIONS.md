# Stack decisions

| Choice | Decision | Why |
|--------|----------|-----|
| Backend | Python 3.12 + FastAPI | WeasyPrint PDF and python-docx were the lower-friction path for dual-format reports; keeps extraction + reports in one language. |
| Shared schema | Pydantic v2 in `backend/app/schema.py` | Single runtime source of truth; OpenAPI/JSON Schema drives generated frontend types — no hand-duplicated enums. |
| Frontend types | Generated TypeScript from the Pydantic JSON Schema (`shared/schema.ts`) | Prevents verdict/field vocabulary drift between pipeline stages and UI. |
| Inspector PWA | React + TypeScript + Vite + Workbox + IndexedDB | Matches §2; installable offline queue is a first-class requirement. |
| Admin portals | Same React+Vite stack, separate `admin/` app (distinct origin) | Runtime/deployment boundary from inspector PWA; auth middleware rejects wrong-portal JWTs. |
| Database | PostgreSQL 16 with RLS | Hard requirement (§6/§7); second enforcement layer beyond middleware. |
| OCR geometry | Tesseract.js in the PWA | Client-side bounding boxes only; text not used downstream. |
| Field extraction | Groq API, Qwen3.8 VLM, JSON mode, `reasoning_effort="none"` | Spec §4; structured fields + confidence for rule engine. |
| PDF | WeasyPrint from one Jinja HTML template | Deterministic layout from `ScanRecord`; matches prototype path. |
| DOCX | python-docx from the same `ScanRecord` + shared template data | Both formats required; same source object as PDF. |
| Auth | JWT (`role` + `district_id` / `state_id` claims) | Spec §2/§7; server-derived scope always wins over client params. |
| Tests | pytest (+ httpx AsyncClient) for API/RLS/hash-chain | Needed for §8 scoping, RLS, and report-hash tests. |

Deviations from the master prompt: none.
