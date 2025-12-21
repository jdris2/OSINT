# Prompt 19 — Refactor `research_framework_reconng.py` to stop writing `intelligence.*`

**File:** `intel_engine/modules/research_framework_reconng.py`  
**Module/Class:** `Research_Framework_ReconNG`  
**Problem:** The module’s output shape is `{"intelligence": ...}` and/or expects an `intelligence` section that is not present in `intel_engine/schemas/profile_schema.json` (`additionalProperties: false` at root).

## Refactor objective

- Eliminate all writes/returns that introduce `profile["intelligence"]` or any other non-schema top-level keys.
- Store Recon-ng run output under `profile["enrichment"]["raw_results"]` only.
- Optionally (high confidence only): merge discovered `emails` into `contact.emails` and discovered `domains` into `digital.domains` (dedupe + normalize).

## Inputs

- Module args: `target`, `target_type`, `workspace_name` (as currently used by the orchestrator)
- Profile context (optional): `contact.emails`, `digital.domains`, `business.company_names`

## Outputs

- `enrichment.raw_results` with a single entry per run:
  - `identifier`: the `target` value used
  - `type`: `"reconng"`
  - `payload`: object containing:
    - `target_type`, `workspace`, `modules_requested`, `modules_run`
    - extracted records summary (domains/emails/hosts/contacts/etc.)
    - correlations/anomalies if computed
    - execution metadata: return code, truncated stdout/stderr, runtime timings
    - errors/warnings (including missing binary, permission issues, DB parse errors)

## Implementation requirements

- Do not add `intelligence` anywhere (top-level or nested).
- Ensure enrichment is schema-compliant when present (initialize required keys; append to `raw_results`).
- Keep `payload` JSON-serializable (convert `Path`, `datetime`, etc. to strings).
- Truncate large stdout/stderr/DB blobs inside `payload` (store summaries + capped samples).

## Note (orchestrator)

If `intel_engine/modules/research_ai_orchestrator.py` expects `profile_section="intelligence"` for Recon-ng, update the orchestrator mapping to `"enrichment"` (or ignore `profile_section` entirely) so the system’s metadata stays consistent.

