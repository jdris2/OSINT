# Prompt 03 — Certificate Transparency (crt.sh) subdomain discovery

**File:** `intel_engine/modules/research_certificate_transparency_crtsh.py`  
**Module/Class:** `Research_Certificate_Transparency_CrtSh`  
**Purpose:** Discover subdomains via CT logs (high-signal infra pivot) and feed `digital.domains` safely.

## Data sources

- crt.sh JSON output: `https://crt.sh/?q=%25.{domain}&exclude=expired&deduplicate=Y&output=json`

## Inputs

- `profile["digital"]["domains"][0]` (base domain) or iterate all domains (cap at N=5 to avoid noise)

## Outputs

- `profile["digital"]["domains"]`: add discovered FQDNs (normalize, lower, strip wildcards)
- `profile["enrichment"]["raw_results"]`: store raw crt.sh rows (or a trimmed subset) with `type: "crtsh"`

## Implementation requirements

- Dedupe aggressively; ignore invalid domains/hosts.
- Provide a `max_hosts` param default `300`; store only top N in summary.
- Expect crt.sh fragility (timeouts); retry once with backoff.

