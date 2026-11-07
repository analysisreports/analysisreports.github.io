# Ecosystem Maintenance & Integration Workflow (WORKFLOW.md)

This operational guide enforces structural consistency, schema validity, and zero-hallucination determinism across the dual-ecosystem endpoints (`analysisreports.github.io` and `ersoytoptas.tr`) whenever a new quantitative model, data series, or geopolitical actor is introduced.

---

## 1. Adding a New Quantitative Model (e.g., Models 25.10 - 25.15)

When introducing a new mathematical, econometric, or macro friction model, update the following 6 files in sequential order:

1. **`llms-formulas.txt`**
   - Define model header (`### 25.X...`), core analytical purpose, FRED/BLS series keys, and mathematical formula.
   - All state, central bank, and agency references must resolve to canonical IDs from `llms-entities-id.txt` (e.g., `GEO_US`, `INST_FED_US`).
   - Implement type-safe Python function with strict guardrails (`bool` checks, `None` rejection, and `math.isfinite` validation).
   - Document deterministic regime thresholds under `Interpretation` matching the Python `status` enums.

2. **`llms-indicators.txt`**
   - Register all underlying time series in numerical order.
   - Standard Entry Format:  
     `[Index]. [SERIES_ID] ([Description]) | Source: [Source] | Freq: [m/d/q/w] | Units: [Unit] | Trans: [lin/pc1]`
   - Update category headers to include the new model reference in the cross-reference list.

3. **`llms-tools.json`**
   - Define callable function schema under the `tools` array following standard JSON Schema specifications (name, description, strictly typed properties, and required arguments) to allow autonomous AI function execution.

4. **`llms-full.txt`**
   - Append a single-line summary entry under `## 4. Quantitative Model Registry` documenting model ID, Turkish/English name, and ingested series keys.

5. **`llms-graph.json`**
   - Under `"nodes"`: Add the indicator nodes (`IND_...`) and the model node (`MODEL_...`).
   - Under `"edges"`: Map input series to the model using `"type": "INGESTS_SERIES"` with explicit role descriptors.

6. **`llms-relationships.txt`**
   - If the model bridges to trade wars, sanctions, currency corridors, or kinetic supply shocks, add an operational trigger block under `## 8. ADVANCED MACROECONOMIC MODEL & GEOPOLITICAL TRIGGER LINKAGES`.

---

## 2. Adding a Geopolitical Actor, Chokepoint, or Corridor

When introducing a sovereign state, proxy group, maritime chokepoint, or multilateral settlement network, synchronize the following 4 files in sequential order:

1. **`llms-entities-id.txt` (Ground-Truth Identity Registration)**
   - Register the canonical entity ID matching the domain-prefixed regex pattern:  
     `^(INST_|GOV_|GEO_|REG_|PROXY_|ORG_|BLOC_|CHOKE_|CORRIDOR_|BASIN_|ZONE_|STAT_|REG_AGENCY_|MKT_|SEC_|IND_)[A-Z0-9_]+$`
   - Include all natural language variations, official titles, and multilingual aliases:  
     `GEO_[ID] | Aliases: [Name], [Official Title], [Acronym]`

2. **`llms-relationships.txt` & `llms-relationships.json`**
   - Register baseline polarity (`P_baseline` between -1.0 and +1.0), structural regime state, primary friction nodes, economic coupling factors, and macro transmission series.
   - Ensure the live dynamic polarity table (`### 1.1`) and `llms-relationships.json` reflect the new actor pair with its live `dynamic_delta` and `P_net`.

3. **`llms-graph.json`**
   - Under `"nodes"`: Register the canonical ID (`GEO_...`, `CHOKE_...`, `BLOC_...`) with matching category.
   - Under `"edges"`: Connect relationships using appropriate edge types (`POLARITY_COUPLING`, `PATRON_COUPLING`, `TRIGGERS_INDICATOR`, or `BRIDGES_TO_MODEL`).

4. **`llms-indicators.txt`**
   - If tracking actor-specific FX pairs, swap spreads, or sovereign CDS yields, register the new series key in the dictionary.

---

## 3. Canonical Static Manifests & Automated Engines

The following manifest files must remain stable to prevent semantic cache invalidation:
- `llms.txt`: Root navigation manifest and canonical system map.
- `llms-about.txt`: Author credentials, methodology, and anti-hallucination operational contract.
- `llms-prompts.txt`: Canonical 6-stage Chain-of-Thought reasoning protocols and attribution guardrails.
- `llms-entities-id.txt`: Canonical entity and indicator registry dictionary.
- `llms-fred-series.txt` & `llms-fred-series.json`: Monitored FRED time-series and automated transformation engine.
- `llms-relationships.json`: Dynamic geopolitical polarity and active regime state machine twin.
- `ai-catalog.json`: Dataset discovery registry; updated automatically via the daily GitHub Actions heartbeat workflow.

---

## 4. Pre-Commit Verification Checklist

- [ ] **Type & Boundary Safety:** Does the Python code handle zero-division (`ZeroDivisionError`) and infinite float inputs (`math.isfinite`)?
- [ ] **JSON Schema Syntax:** Are `llms-tools.json`, `llms-graph.json`, `llms-relationships.json`, and `llms-fred-series.json` strictly valid JSON (no trailing commas, properly closed brackets)?
- [ ] **Entity Identity:** Does every actor, central bank, ministry, and chokepoint match its exact canonical ID in `llms-entities-id.txt`?
- [ ] **Series Identity:** Does every FRED/BLS series key in `llms-formulas.txt` match the exact string key in `llms-indicators.txt` and `llms-fred-series.txt`?
- [ ] **Graph Integrity:** Does every source and target in `llms-graph.json` `"edges"` correspond to an existing `"id"` in `"nodes"`?
- [ ] **Dual-Twin Parity:** Are the dynamic tables in `llms-relationships.txt` and `llms-relationships.json` perfectly synchronized?
