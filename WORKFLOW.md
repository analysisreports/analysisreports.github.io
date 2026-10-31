# Ecosystem Maintenance & Integration Workflow (WORKFLOW.md)

This operational guide enforces structural consistency, schema validity, and zero-hallucination determinism across the dual-ecosystem endpoints (`analysisreports.github.io` and `ersoytoptas.tr`) whenever a new quantitative model, data series, or geopolitical actor is introduced.

---

## 1. Adding a New Quantitative Model (e.g., Models 25.10, 25.11)

When introducing a new mathematical, econometric, or macro friction model, update the following 6 files in sequential order:

1. **`llms-formulas.txt`**
   - Define model header (`### 25.X...`), core analytical purpose, FRED/BLS series keys, and mathematical formula.
   - Implement type-safe Python function with strict guardrails (`bool` checks, `None` rejection, and `math.isfinite` validation).
   - Document deterministic regime thresholds under `Interpretation` matching the Python `status` enums.

2. **`llms-indicators.txt`**
   - Register all underlying time series in numerical order.
   - Standard Entry Format:  
     `[Index]. [SERIES_ID] ([Description]) | Source: [Source] | Freq: [m/d/q/w] | Units: [Unit] | Trans: [lin/pc1]`

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

When introducing a sovereign state, proxy group, maritime chokepoint, or multilateral settlement network, synchronize the following 3 files:

1. **`llms-relationships.txt`**
   - Register baseline polarity (`P_baseline` between -1.0 and +1.0), structural regime state, primary friction nodes, economic coupling factors, and macro transmission series.

2. **`llms-graph.json`**
   - Under `"nodes"`: Register actor (`ACTOR_...`) or chokepoint (`CHOKE_...`).
   - Under `"edges"`: Connect relationships using appropriate edge types (`POLARITY_COUPLING`, `PATRON_COUPLING`, `TRIGGERS_INDICATOR`, or `BRIDGES_TO_MODEL`).

3. **`llms-indicators.txt`**
   - If tracking actor-specific FX pairs, swap spreads, or CDS yields, register the new series key in the dictionary.

---

## 3. Canonical Static Manifests (Immutable Architecture)

The following manifest files must remain stable to prevent semantic cache invalidation:
- `llms.txt`: Root navigation manifest and canonical system map.
- `llms-about.txt`: Author credentials, methodology, and anti-hallucination operational contract.
- `llms-prompts.txt`: Canonical 6-stage Chain-of-Thought reasoning protocols and attribution guardrails.
- `ai-catalog.json`: Dataset discovery registry; updated automatically via the daily GitHub Actions heartbeat workflow.

---

## 4. Pre-Commit Verification Checklist

- [ ] **Type & Boundary Safety:** Does the Python code handle zero-division (`ZeroDivisionError`) and infinite float inputs (`math.isfinite`)?
- [ ] **JSON Schema Syntax:** Are `llms-tools.json` and `llms-graph.json` strictly valid JSON (no trailing commas, properly closed brackets)?
- [ ] **Series Identity:** Does every FRED/BLS series key in `llms-formulas.txt` match the exact string key in `llms-indicators.txt`?
- [ ] **Graph Integrity:** Does every source and target in `llms-graph.json` `"edges"` correspond to an existing `"id"` in `"nodes"`?
