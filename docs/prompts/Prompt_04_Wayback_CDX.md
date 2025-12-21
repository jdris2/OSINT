# Prompt 04 — Wayback CDX host/URL discovery (historical pivots)

**File:** `intel_engine/modules/research_wayback_cdx.py`  
**Module/Class:** `Research_Wayback_CDX`  
**Purpose:** Use Wayback CDX to find historical URLs and hostnames for a domain; extract hostnames as subdomains; extract useful historic pages (contact/about/legal).

## Data sources

- CDX API: `https://web.archive.org/cdx/search/cdx?url=*.{domain}/*&output=json&fl=original,timestamp,statuscode,mimetype&filter=statuscode:200&collapse=urlkey`

## Inputs

- `profile["digital"]["domains"]`

## Outputs

- `profile["digital"]["domains"]`: add subdomains found in archived URLs
- `profile["enrichment"]["raw_results"]`: store sampled URL list + counts (`type: "wayback_cdx"`)
- Optional: add a few “high value” URLs to `profile["social"]["profile_links"]` only if they are actual profile pages; otherwise keep in raw results to avoid polluting `social`.

## Implementation requirements

- Do not download page bodies; CDX only.
- Add parameters `from_year`, `to_year`, `max_urls`.
- Normalize hosts; drop tracker/redirect garbage.

