# Prompt 02 — auDA RDAP for `.au` domains (registrant + nameservers)

**File:** `intel_engine/modules/research_au_auda_rdap.py`  
**Module/Class:** `Research_AU_auDA_RDAP`  
**Purpose:** Pull authoritative RDAP for `.au` domains and extract registrant/org hints + nameservers + status without adding new schema fields.

## Data sources (public)

- RDAP: `https://rdap.audns.net.au/domain/{domain}` (fallback to generic RDAP if needed)

## Inputs

- `profile["digital"]["domains"]` (iterate; filter to `.au`)

## Outputs

- Summaries:
  - Add discovered domains (e.g., canonical + `www`) back into `profile["digital"]["domains"]` (dedupe).
- Raw:
  - Append RDAP JSON to `profile["enrichment"]["raw_results"]` with `type: "rdap_domain"`.
- Optional enrichment signals:
  - If RDAP yields obvious org/entity name, add to `profile["business"]["company_names"]` (dedupe), and include the justification/confidence in raw results.

## Implementation requirements

- Strict schema: do not create `digital.domains_rdap` or similar.
- Use `urllib.request` only (no extra deps).
- Handle 404/429 gracefully; log errors in result summary.

