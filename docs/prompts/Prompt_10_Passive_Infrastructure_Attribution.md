# Prompt 10 — Passive infrastructure attribution (no scanning)

**File:** `intel_engine/modules/research_passive_infra_attribution.py`  
**Module/Class:** `Research_Passive_Infrastructure_Attribution`  
**Purpose:** Attribute domains/IPs using only passive/public registries (RDAP, DNS resolution) without port scanning.

## Inputs

- `digital.domains`, `digital.ips`

## Outputs

- `digital.ips`: add resolved A records for discovered domains (dedupe)
- `enrichment.raw_results` (`type: "infra_attribution"`) containing RDAP org, nameservers, resolved IPs, and attribution notes
- Add `risk.red_flags` only for clear, evidence-backed issues; avoid speculation.

## Implementation requirements

- Use only DNS + RDAP/registry HTTP calls (no port scanning).
- Timeouts + retry once; include a small delay to avoid hammering endpoints.

