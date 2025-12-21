# Prompt 07 — Trove (NLA) media search (free key on request)

**File:** `intel_engine/modules/research_au_trove.py`  
**Module/Class:** `Research_AU_Trove`  
**Purpose:** Find historical/public mentions for a person/entity to support timelines and adverse media flags.

## Data sources

- Trove API v2 (requires key): use the official Trove endpoint for searching newspaper/collection items.

## API key

- `TROVE_API_KEY` env var required.

## Inputs

- `identity.full_name`, `identity.aliases`, `business.company_names`, optional `geo.cities`

## Outputs

- Store results in `profile["enrichment"]["raw_results"]` (`type: "trove_results"`) including query + top N items + citations/URLs.
- Optional: if strong adverse mention (user-configured keywords), add `risk.red_flags` with `category: "adverse_media"`.

## Implementation requirements

- Do not scrape the Trove website; API only.
- Default `max_results=25` and store only key fields (title, date, url, snippet).
- Add basic query-throttling and handle rate limits.

