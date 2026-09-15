# Architectural & Stack Decisions

This document records the technology stack and architectural design decisions for the Legal Metrology Compliance Scanning Platform (PRAMAAN | प्रमाण), along with one-line justifications per choice.

1. **Frontend: React 18 + Vite + TypeScript**
   - *Justification:* Delivers blazing sub-second load times, strict compile-time type safety across government forms, and native offline PWA service worker capabilities.

2. **Single Source of Truth: `src/shared/schema.ts`**
   - *Justification:* Guarantees structural parity between data models, rule verdicts, report rendering, and UI without manual re-declaration or divergence.

3. **Client-Side Optical Geometry: Calibrated Coordinate Engine**
   - *Justification:* Runs entirely on-device to calculate pixel-to-millimeter physical scales from barcode dimensions without network latency or server load.

4. **Rule Engine: Deterministic In-Memory Ruleset (`src/rule-engine/index.ts`)**
   - *Justification:* Enforces Legal Metrology (Packaged Commodities) Rules, 2011 deterministically with zero runtime AI/LLM calls to guarantee legal defensibility in court.

5. **Tamper-Evident Hashing: Web Crypto API SHA-256 Hash Chaining**
   - *Justification:* Produces cryptographic SHA-256 checksums linking each report version (`previous_report_hash` -> `report_hash`) for evidentiary integrity under Section 15 of the LM Act, 2009.

6. **Offline Queue: IndexedDB Storage with Sync Counter**
   - *Justification:* Persists field captures and GPS telemetry locally when network drops in rural mandis, automatically synchronizing once reconnected.

7. **Styling: Authentic Indian Government Design System (CSS + Lucide Icons)**
   - *Justification:* Matches exact NIC government portal aesthetics, National Ashoka Lion emblem, gazette borders, and formal bilingual typography without heavyweight runtime overhead.

8. **Jurisdictional Scoping: Strict Role-Based Access Control Middleware Simulation**
   - *Justification:* Enforces rigid jurisdictional boundaries (Inspector, District Officer, State Admin, National Admin, Auditor) at the data layer to prevent cross-district leaks.
