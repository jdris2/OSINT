# Prompt 17 — Refactor non-compliant modules to write only `enrichment.raw_results`

**Purpose:** Update existing modules that currently write schema-unknown fields (top-level or nested) so that all unstructured/variable output is stored in `profile["enrichment"]["raw_results"]` (and only schema-defined fields are mutated elsewhere).

## Goal

- No module should introduce new keys anywhere outside the schema defined in `intel_engine/schemas/profile_schema.json`.
- Any output that does not have a defined schema location must be recorded as an `enrichment.raw_results[]` entry.

## Background (schema contract)

- `profile_schema.json` uses `additionalProperties: false` for the profile root and many nested objects (notably `digital`, `enrichment`, etc.).
- `enrichment.raw_results` items must be objects with:
  - `identifier` (string)
  - `type` (string)
  - `payload` (object; can be any shape, but must be a JSON object/dict)

## Refactor requirements (apply to every target module)

1. **Remove all schema-unknown writes**
   - Delete/replace any `profile["some_new_key"] = ...` where `some_new_key` is not a top-level schema property.
   - Delete/replace any `profile["digital"]["some_new_key"] = ...` (or `.update(...)`) where the key is not one of: `domains`, `ips`, `devices`, `exposed_ports`.
   - Do not create “convenience” fields like `digital.domains_whois`, `intelligence.*`, `images`, etc.

2. **Write raw results into `enrichment.raw_results`**
   - Ensure `profile["enrichment"]` exists and is fully schema-compliant when present (populate required keys).
   - Append entries like:
     - `identifier`: the pivot value (domain/email/phone/username/ip/file path), normalized if possible
     - `type`: stable event name (e.g., `"whois"`, `"reconng"`, `"spiderfoot"`, `"image_exif"`)
     - `payload`: dict containing the raw output, key parameters, and any errors/warnings
   - If the raw output is a list/string, wrap it: `payload={"data": raw_output}` or `payload={"text": raw_text}`.

3. **Only mutate schema-defined “summary” fields when safe**
   - If the module extracts high-confidence, schema-supported values, it may merge them into:
     - `contact.emails`, `contact.phones`, `contact.usernames`
     - `digital.domains`, `digital.ips`
     - `geo.geo_coordinates`, `geo.cities`
   - Dedupe, normalize, and never overwrite user-provided values.

4. **Initialization pattern (must not add unknown keys to `enrichment`)**

Use this exact shape when creating enrichment from scratch:

```python
from datetime import datetime, timezone

enrichment = profile.setdefault("enrichment", {})
enrichment.setdefault("identifiers", [])
enrichment.setdefault("sources", [])
enrichment.setdefault("signals", {"accounts": [], "locations": [], "associations": []})
enrichment.setdefault("correlations", [])
enrichment.setdefault("scores", {"completeness": 0.0, "freshness": 0.0, "risk": 0.0})
enrichment.setdefault(
    "metadata",
    {"tool": MODULE_NAME, "queried_at": datetime.now(timezone.utc).isoformat()},
)
enrichment.setdefault("raw_results", [])
```

5. **Return shape**
   - Prefer returning the updated `profile` (or `{"enrichment": enrichment}` if the rest of the system expects partial updates), but do not rely on return value alone if orchestration currently ignores it; always ensure schema-compliant in-place updates if that is the engine’s pattern.

## Acceptance checklist

- No new keys are written to `profile` root or any `additionalProperties: false` sub-object.
- Every non-schema output is present in `enrichment.raw_results` with `payload` as an object/dict.
- `enrichment` (if present) includes: `identifiers`, `sources`, `signals`, `correlations`, `scores`, `metadata`, `raw_results`.

