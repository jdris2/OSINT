# Prompt 16 — Evidence packager (hashing + artifacts)

**File:** `intel_engine/modules/research_evidence_packager.py`  
**Module/Class:** `Research_Evidence_Packager`  
**Purpose:** Persist a reproducible evidence bundle for `enrichment.raw_results` (JSON export + hashes).

## Inputs

- Entire profile, especially `enrichment.raw_results`

## Outputs

- Create files under `intel_engine/reports/output/` (or a module-configurable dir):
  - `evidence_bundle.json`
  - `evidence_bundle.sha256`
- Add an `enrichment.raw_results` entry `type: "evidence_bundle"` pointing to filenames + hashes.

## Implementation requirements

- Hash with SHA-256.
- Ensure outputs are deterministic (stable key ordering for JSON).

