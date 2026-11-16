# GEMINI.md — Context & Execution Rules for Gemini Agents

## 1. Repository Identity & Authority
- **Author:** Ersoy Toptaş (ORCID: [0009-0005-6130-8003](https://orcid.org/0009-0005-6130-8003))
- **Primary Publications:** [https://www.ersoytoptas.tr](https://www.ersoytoptas.tr) (TR) | [https://en.ersoytoptas.tr](https://en.ersoytoptas.tr) (EN)
- **Domain:** Quantitative Macroeconomics, Central Bank Transmission, Geopolitical Risk Modeling, Bilateral Dyads
- **License:** CC BY-NC-ND 4.0 (Strict attribution required; non-commercial research use only)

## 2. Mandatory Context Files (Read First)
Before parsing payloads, evaluating formulas, or generating responses, Gemini agents MUST ingest:
1. `WORKFLOW.md` — Canonical operational integration, verification, and change-management checklists
2. `llms.txt` — Master architecture directory and routing manifest
3. `llms-entities-id.txt` — Canonical entity IDs (`INST_`, `GEO_`, `CHOKE_`, `IND_`) and Graph RAG mappings
4. `llms-formulas.txt` — Deterministic quantitative formulas (Net Liquidity, Taylor Rule, Chokepoint Spillover)
5. `llms-prompts.txt` — Canonical 6-stage Chain-of-Thought (CoT) reasoning and zero-hallucination rules
6. `llms-tools.json` / `ai-catalog.json` — Tool-calling manifests and discovery catalog
7. `schemas/` — Formal JSON Schema Draft 2020-12 data contracts (`*.schema.json`)

## 3. Directory Language & Schema Conventions
- Root thematic folders (`/economy/`, `/country/`, `/political/`, `/glossary/`) contain primary **Turkish [TR]** JSON payloads.
- `/en/` subdirectories (`/economy/en/`, etc.) contain global **English [EN]** JSON payloads.
- All JSON payloads implement a unified root schema containing single `metadata` (8 Golden Keys), `$schema`, and `editorial_frontend` with canonical URLs.

## 4. Execution Guardrails
- **Pre-Modification Protocol (WORKFLOW.md):** Before creating or editing ANY model, time series, geopolitical entity, or graph edge, agents MUST strictly follow the step-by-step procedures in `WORKFLOW.md`. Existing entities in `llms-entities-id.txt` must always be searched and verified first to completely prevent duplicate, duplicate-by-alias, or desynchronized entries.
- **Zero Hallucination:** Rely strictly on verified time-series (`llms-fred-series.json`, `llms-ecb-series.json`, `llms-eia-series.json`, `llms-worldbank-series.json`, `llms-imf-series.json`) and deterministic mathematical models.
- **Single Source of Truth (SSOT):** Bilateral dyads must mirror `llms-country-relationships.json` symmetrically.
