# Lease Deal Room: Agent Instructions

## Product

Private AI deal room for US commercial real estate brokers. Broker uploads 20-50 lease PDFs + 1 Rent Roll (CSV/Excel). System extracts 8 key terms per lease with exact PDF page citations, audits lease rent vs Rent Roll, flags mismatches, and exports a clean Excel Lease Abstract.

This is an MVP (4-5 days) but must be production-grade and extendable for a real client. NO overengineering.

## Stack

- Backend: Python, FastAPI (single service, no microservices), SQLAlchemy + Alembic, Postgres
- Vector DB: Qdrant (single collection, payload filters)
- Orchestration: LangGraph
- PDF parsing: PyMuPDF (Docling only if needed later)
- Excel: openpyxl / pandas
- Frontend (Day 4): React/vite with tanstack query/router, 3 panels (upload | extracted table + flags | PDF page viewer)
- Infra: docker-compose (Postgres, Qdrant, Redis)

## Architecture Rules

- Layers: api/ (HTTP only) -> services/ (business logic) -> graph/, audit/, parsing/, vectorstore/, llm/, exporters/
- api/ never contains business logic. No DB or Qdrant calls inside route handlers.
- vectorstore/ and llm/ are thin wrappers so providers can be swapped in one place.
- audit/ is pure Python, no LLM calls. Deterministic and unit-testable.
- Config only via core/config.py (pydantic-settings). No hardcoded secrets or URLs.

## Core Design Decisions (do not change without asking)

1. Qdrant payload per chunk: deal_id, tenant_name, file_name, page_number, text. Payload indexes on deal_id and tenant_name.
2. Retrieval is ALWAYS filtered by deal_id + tenant_name. Tenants' data must never mix.
3. Extraction runs per lease, one at a time, using only that tenant's retrieved chunks.
4. Every extracted field returns: value, page_number, quote. Python verifies the quote exists in that page's text. On failure: 1 retry, then mark field as unverified.
5. The 8 terms: Base Rent, Escalations, Lease Term (start/end), Early Termination, CAM/NNN Caps, Roof/HVAC Responsibility, Renewal Options, Security Deposit.
6. LangGraph per-lease graph, 4 nodes: retrieve_context -> extract_terms -> verify_citations (conditional retry to extract_terms, max 1) -> audit_rent_roll. Excel export is a normal function outside the graph.
7. Concurrency across leases via asyncio.gather + semaphore (5), not graph fan-out.
8. Background work: FastAPI BackgroundTasks for MVP. Move to ARQ only if needed.

## Code Standards

- Senior-engineer quality: type hints everywhere, Pydantic schemas for all I/O, async where I/O bound, structured logging, custom exceptions in core/exceptions.py.
- Small focused functions, no god-files, no dead code, no premature abstractions.
- Unit tests in backend/tests/unit/ as proper pytest files (not terminal one-liners). Integration tests in tests/integration/.
- Never invent libraries/APIs. If unsure about a library's API, check docs or ask.

## Working Protocol (IMPORTANT)

1. At session start: read AGENTS.md and docs/PROGRESS.md ONLY. Do NOT re-scan the whole repo. Open other files only when the current task needs them.
2. Work on ONE step at a time, the "Next Step" in PROGRESS.md, unless told otherwise.
3. Before coding: state the plan in 3-5 lines. Keep replies short.
4. After finishing a step: update docs/PROGRESS.md (done list, files touched, decisions, next step, known issues). This is mandatory, not optional.
5. If a requirement is ambiguous or conflicts with the decisions above, ask before building.
6. Do not refactor or touch unrelated files.
