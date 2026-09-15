# SIH 2026 — Automated Compliance Checker for Packaged Commodities

Backend engine for deterministic, auditable compliance checking of packaged
commodities against Legal Metrology (Packaged Commodities) Rules, 2011 and
FSSAI Food Safety and Standards (Labelling and Display) Regulations, 2020.

## Quick Start

```bash
cd backend
pip install -e ".[dev]"
pytest
```

## Architecture

The pipeline order is **fixed in code** and never controlled by JSON data:

```
EXTRACT → RESOLVE → NORMALIZE → CLASSIFY → DOMAIN MAP
→ SCOPE → RETRIEVE → DATE FILTER → CAPABILITY FILTER
→ EVALUATE → VERIFICATION GATE → EVIDENCE
→ AGGREGATE → VIOLATION → REPORT → AUDIT
```

## Principles

- Legal rules are **DATA** (JSON).
- Pipeline order is **CODE** (Python).
- Evidence is **TRACEABLE** (provenance on every field).
- Reports are **IMMUTABLE/VERSIONED** (hash-chained).
- Audit trail is **APPEND-ONLY**.
- Final legal verdict is **DETERMINISTIC** (never invented by an LLM).
