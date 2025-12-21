# Prompt 20 — Refactor `research_automation_spiderfoot.py` to stop writing `intelligence.*`

**File:** `intel_engine/modules/research_automation_spiderfoot.py`  
**Module/Class:** `Research_Automation_SpiderFoot`  
**Problem:** The module’s output shape is `{"intelligence": ...}` and/or expects an `intelligence` section that is not present in `intel_engine/schemas/profile_schema.json`.

## Refactor objective

- Eliminate all writes/returns that introduce `profile["intelligence"]` or any other non-schema top-level keys.
- Store SpiderFoot scan output under `profile["enrichment"]["raw_results"]`.
- Optionally (high confidence only): merge discovered entities into schema-supported lists:
  - `contact.emails`
  - `digital.domains`
  - `digital.ips`

## Inputs

- Profile targets:
  - `contact.emails`
  - `digital.domains`
  - `digital.ips`
  - `identity.full_name` (optional; only if used safely)

## Outputs

- `enrichment.raw_results` with a single entry per scan session:
  - `identifier`: a stable scan pivot (prefer the primary target used; else a concatenated label)
  - `type`: `"spiderfoot"`
  - `payload`: object containing:
    - `targets`, `scan_profile`, `modules_enabled`
    - extracted entities + relationship summaries
    - capped raw events list (respect existing max caps)
    - execution timing + any errors

## Implementation requirements

- Do not add `intelligence` anywhere.
- Ensure `enrichment` is initialized with all required keys; append a dict payload entry.
- Keep payload sizes bounded (cap raw events; truncate large strings).
- Keep entity merges conservative and deduped; never overwrite existing profile values.

## Note (orchestrator)

If `intel_engine/modules/research_ai_orchestrator.py` tags SpiderFoot output under `profile_section="digital"` today, consider switching to `"enrichment"` to reflect where the unstructured results now live.

