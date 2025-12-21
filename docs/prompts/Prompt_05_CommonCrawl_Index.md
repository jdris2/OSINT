# Prompt 05 — Common Crawl index discovery (archived URLs → hosts)

**File:** `intel_engine/modules/research_commoncrawl_index.py`  
**Module/Class:** `Research_CommonCrawl_Index`  
**Purpose:** Query Common Crawl index to discover URLs and extract hostnames/subdomains.

## Data sources

- Index list: `https://index.commoncrawl.org/collinfo.json`
- Query: `https://index.commoncrawl.org/{index}-index?url=*.{domain}/*&output=json`

## Inputs

- `profile["digital"]["domains"]`

## Outputs

- `profile["digital"]["domains"]`: add discovered hosts
- `profile["enrichment"]["raw_results"]`: store sampled lines + stats (`type: "commoncrawl_index"`)

## Implementation requirements

- Select latest 1–2 indexes only (limit volume).
- Stream lines; stop after `max_records`.
- Handle large responses safely (do not load everything into memory).

