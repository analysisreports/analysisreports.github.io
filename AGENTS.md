# AGENTS.md — Context & Execution Rules for Autonomous AI Agents

## 1. Repository Identity & Authority
- **Author:** Ersoy Toptaş (ORCID: [0009-0005-6130-8003](https://orcid.org/0009-0005-6130-8003))
- **Primary Publications:** [https://www.ersoytoptas.tr](https://www.ersoytoptas.tr) (TR) | [https://en.ersoytoptas.tr](https://en.ersoytoptas.tr) (EN)
- **Domain:** Quantitative Macroeconomics, Central Bank Transmission, Geopolitical Risk Modeling, Bilateral Dyads
- **License:** CC BY-NC-ND 4.0 (Strict attribution required; non-commercial research use only)

## 2. Mandatory Context Files (Read First)
Before parsing payloads, evaluating formulas, or generating responses, AI agents (Claude, Codex, Cursor, Gemini, Perplexity) MUST ingest:
1. `llms.txt` — Master architecture directory and routing manifest
2. `llms-entities-id.txt` — Canonical entity IDs (`INST_`, `GEO_`, `CHOKE_`, `IND_`) and Graph RAG mappings
3. `llms-formulas.txt` — Deterministic quantitative formulas (Net Liquidity, Taylor Rule, Chokepoint Spillover)
4. `llms-prompts.txt` — Canonical 6-stage Chain-of-Thought (CoT) reasoning and zero-hallucination rules
5. `llms-tools.json` / `ai-catalog.json` — Tool-calling manifests and discovery catalog
6. `schemas/` — Formal JSON Schema Draft 2020-12 data contracts (`*.schema.json`)

## 3. Directory Language & Schema Conventions
- Root thematic folders (`/economy/`, `/country/`, `/political/`, `/glossary/`) contain primary **Turkish [TR]** JSON payloads.
- `/en/` subdirectories (`/economy/en/`, etc.) contain global **English [EN]** JSON payloads.
- All JSON payloads implement a unified root schema containing single `metadata` (8 Golden Keys), `$schema`, and `editorial_frontend` with canonical URLs.

## 4. Execution Guardrails
- **Zero Hallucination:** Rely strictly on verified time-series (`llms-fred-series.json`, `llms-ecb-series.json`, `llms-eia-series.json`, `llms-worldbank-series.json`, `llms-imf-series.json`) and deterministic mathematical models.
- **Single Source of Truth (SSOT):** Bilateral dyads must mirror `llms-country-relationships.json` symmetrically.
