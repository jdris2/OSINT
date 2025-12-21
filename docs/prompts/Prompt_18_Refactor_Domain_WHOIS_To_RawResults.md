# Prompt 18 — Refactor `research_domain_whois.py` to stop writing `digital.domains_whois`

**File:** `intel_engine/modules/research_domain_whois.py`  
**Module/Class:** `Research_Domain_WHOIS_Owner`  
**Problem:** The module writes `profile["digital"]["domains_whois"]`, but `digital` is `additionalProperties: false` and only allows `domains`, `ips`, `devices`, `exposed_ports`.

## Refactor objective

- Remove any write to `digital.domains_whois` (or any other new `digital.*` key).
- Record WHOIS output only in `profile["enrichment"]["raw_results"]`.

## Inputs

- `profile["digital"]["domains"]` (list of domains)

## Outputs

- `enrichment.raw_results` with one entry per domain:
  - `identifier`: the domain queried
  - `type`: `"whois"`
  - `payload`: object containing:
    - `domain`, `tld`, `whois_server`
    - parsed fields: `registrant_name`, `creation_date`, `registrar`, `country`
    - raw WHOIS (truncate to a safe size; keep the current snippet behaviour)
    - error details if query fails

## Implementation requirements

- Keep network behaviour conservative: timeout, no infinite reads, handle missing WHOIS server mapping.
- Do not add new schema fields anywhere else (no `digital.domains_whois`).
- Ensure `enrichment` is initialized with required keys before appending.
- Ensure each `raw_results[].payload` is a dict (wrap text under `{"text": ...}` if needed).

