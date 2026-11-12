# Ecosystem Maintenance & Integration Workflow (WORKFLOW.md)

This operational guide enforces structural consistency, schema validity, and zero-hallucination determinism across the dual-ecosystem endpoints (`analysisreports.github.io` and `ersoytoptas.tr`) whenever a new quantitative model, data series, or geopolitical actor is introduced.

---

## 1. Adding or Revising a Quantitative Model

For a new model or a material change to an existing model, synchronize the following sources and derived outputs. Do not treat this as an add-only checklist:

1. **`llms-formulas.txt`** — Define the model purpose, exact series IDs, units, formula, date-alignment/missing-data rules, and interpretation. Use canonical entity IDs from `llms-entities-id.txt`. Only document calibrated thresholds; when thresholds are unavailable, use and document `UNCLASSIFIED` rather than inventing regimes.
2. **Series and indicator catalogs** — Add each input to its provider registry (for example `llms-fred-series.txt`) and to `llms-indicators.txt`; add its `IND_...` identity to `llms-entities-id.txt` when the graph uses one. Let provider sync jobs produce observation JSON; never hand-write observations or use stale values as live inputs.
3. **`scripts/calculate_models.py`** — Implement or revise the calculation with strict input, unit, finite-number, and date guards. Keep optional context metrics distinct from formula inputs and do not substitute fixed values for missing live data.
4. **`llms-tools.json`** — If the model is exposed as a callable tool, keep its function description, parameter names, units, required arguments, and validation needs consistent with the implementation.
5. **`llms-full.txt`** — Update the model registry entry and its series list.
6. **`llms-graph.json`** — Ensure all input indicator nodes exist and model edges use `INGESTS_SERIES` with accurate roles. Remove obsolete model-input edges; retain an indicator node if other relationships still use it.
7. **`llms-relationships.txt`** — If the model has geopolitical transmission linkages, update its section under `## 8. ADVANCED MACROECONOMIC MODEL & GEOPOLITICAL TRIGGER LINKAGES`, including exact inputs and emitted status values.
8. **Generated model snapshots** — Regenerate `llms-models.json` and `llms-models.txt` only through the live-data pipeline after all required inputs are available. Never patch observed values or statuses into these outputs by hand; report the snapshot as stale when regeneration is blocked.
9. **Verification** — Run the focused model tests and the repository's graph, entity, JSON, and cross-file consistency checks. Confirm every graph edge endpoint exists and every referenced series is registered.

For Model 11, the FRED sync requests GDPPOT for the exact GDPC1 quarter through the FRED API when a key is available, then the FRED CSV endpoint if needed. Network failures are retried; neither endpoint may supply a different quarter or a cached substitute. If both fail, model refresh fails and existing model snapshots remain unchanged and may be stale.

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
- `llms-ecb-series.txt` & `llms-ecb-series.json`: Monitored European Central Bank time-series and automated transformation engine.
- `llms-worldbank-series.txt` & `llms-worldbank-series.json`: Monitored World Bank Commodity time-series registry and automated transformation engine.
- `llms-imf-series.txt` & `llms-imf-series.json`: Monitored International Monetary Fund time-series registry and automated transformation engine.
- `llms-relationships.json`: Dynamic geopolitical polarity and active regime state machine twin.
- `llms-models.json`: Real-time evaluated macroeconomic models and quantitative regime twin.
- `ai-catalog.json`: Dataset discovery registry; updated automatically via the daily GitHub Actions heartbeat workflow.

---

## 4. Pre-Commit Verification Checklist

- [ ] **Type & Boundary Safety:** Does the Python code handle zero-division (`ZeroDivisionError`) and infinite float inputs (`math.isfinite`)?
- [ ] **JSON Schema Syntax:** Are `llms-tools.json`, `llms-graph.json`, `llms-relationships.json`, `llms-fred-series.json`, `llms-ecb-series.json`, `llms-worldbank-series.json`, and `llms-imf-series.json` strictly valid JSON (no trailing commas, properly closed brackets)?
- [ ] **Entity Identity:** Does every actor, central bank, ministry, and chokepoint match its exact canonical ID in `llms-entities-id.txt`?
- [ ] **Series Identity:** Does every FRED/BLS/ECB/WB/IMF series key in `llms-formulas.txt` match the exact string key in `llms-indicators.txt` and corresponding series registries?
- [ ] **Graph Integrity:** Does every source and target in `llms-graph.json` `"edges"` correspond to an existing `"id"` in `"nodes"`?
- [ ] **Dual-Twin Parity:** Are the dynamic tables in `llms-relationships.txt` and `llms-relationships.json` perfectly synchronized?
