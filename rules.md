# Project Rules

These rules apply to every file you create or edit in this repository, for
the entire project, regardless of which module you're working on. They are
hard constraints, not suggestions. If a request conflicts with these rules,
follow these rules and say so, rather than silently violating them.

---

## 1. File granularity — the core rule

**Do not create a new file for a small piece of logic that has no reason to
live independently.** A large number of tiny, near-empty files makes the
codebase harder to navigate, not easier — it does not automatically mean
"clean code."

Before creating a new file, ask, in order:

1. *Is this a genuine runtime/deployment boundary?* (a separate service, a
   separate frontend app, a separate worker/lambda). If yes → new file/module
   is justified.
2. *Will this be imported by three or more unrelated modules?* If yes → it
   likely deserves its own file so those modules share one implementation
   instead of copy-pasting.
3. **Does it represent one cohesive domain concept that a teammate would
   look for by name** (e.g. rule-engine.ts, report-hashing.ts,
   jurisdiction-scope.ts)? If yes → its own file is fine, but put ALL
   closely related functions for that concept in it, don't split further.

*If the answer to all three is no* — e.g. a single helper function, a
single small class, a single route handler, a single Pydantic/type
definition that's only used in one place — it belongs inside the most
relevant existing file, not in a new one. A file whose entire content could
be described as "one small function used by one caller" should not exist as
a separate file.

Concrete anti-patterns to avoid:
- One file per Pydantic/TypeScript model when the models form one cohesive
  domain (e.g. don't split Declaration, Product, Ingredient,
  ScanRecord into four files — they belong in one schema.py/schema.ts
  together, exactly as the shared schema in the master prompt describes).
- One file per API route handler when a group of routes shares a resource
  (e.g. all /scans/* routes belong in one router file, not five).
- Wrapping a single library call in its own "service" file with no added
  logic, just to have a service layer.
- A utils/ folder full of one-function files. Group related utilities into
  one file by theme (e.g. hash-utils.ts with all hashing-related helpers
  together).

*The reverse failure mode also applies and is equally bad*: do not cram
unrelated domains into one giant file either (e.g. do not put rule-engine
logic and report-PDF-rendering logic in the same file just to reduce file
count — those are two different cohesive concepts per rule 3 above). The
target is cohesion-based grouping, not a line-count target in either
direction. If you're unsure, prefer fewer, well-organized files over more,
narrowly-scoped ones — but each file should still have one clear, nameable
purpose.

---

## 2. Single source of truth for types/schemas

All domain types (ScanRecord, Declaration, Role, verdict enums, etc.)
are defined in exactly one shared schema module, as specified in the master
prompt. No module may redeclare, duplicate, or locally "adjust" one of these
types. If a module seems to need a field the shared schema doesn't have,
extend the shared schema — do not add a local, parallel field. This is the
direct fix for verdict-vocabulary mismatches between pipeline stages seen in
earlier prototypes, and it must not regress.

---

## 3. Consistency checks before finishing any task

Before considering any task complete, grep the codebase for any other place
that represents the same concept (a status enum, a role name, a field name)
and confirm they match exactly. Do not introduce a second spelling/casing of
an existing concept (e.g. needs_review vs needsReview vs NEEDS_REVIEW —
pick the shared schema's casing and use it everywhere, including in the
database, API responses, and frontend).

---

## 4. Security defaults

- Never implement an access restriction only in the frontend/UI. Every
  restriction described anywhere in the spec must be enforced server-side
  (middleware or DB-level), with the UI hiding as a secondary convenience
  layer at most.
- Never trust a client-supplied jurisdiction/scope parameter (district_id,
  state_id, inspector_id, etc.). Server-derived scope from the auth token
  always wins, silently overriding any conflicting client value.
- Any table that should be append-only (audit logs, report version history)
  must have no UPDATE/DELETE grant for application roles at the database
  level — don't rely on "the API just doesn't expose that route."

---

## 5. Determinism where legal defensibility matters

The rule engine (compliance pass/fail logic) must never call an LLM or any
non-deterministic service at evaluation time. If you find yourself wanting to
call a model inside the rule-engine evaluation path, stop — that logic
belongs in the extraction stage, not the rule engine.

---

## 6. Versioning, not overwriting

Anywhere the spec describes an "override" or "edit" of something that was
already generated (a report, a verdict), the correct implementation is: leave
the original record untouched, and create a new, linked version. Never
overwrite history. If you're about to write an UPDATE statement on a
report/verdict row, stop and check whether this should be an INSERT of a new
version instead.

---

## 7. Comments and naming

- Comment why, not what — don't narrate obvious code line by line.
- Name things after the domain concept they represent (match the shared
  schema's vocabulary), not after implementation details.

---

## 8. Before you write code

Skim the relevant section of the master prompt and this file. If what you're
about to build conflicts with either, resolve the conflict in favor of these
documents and flag it in your response rather than proceeding silently.
