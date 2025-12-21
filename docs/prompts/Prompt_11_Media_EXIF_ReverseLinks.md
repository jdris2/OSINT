# Prompt 11 — Reverse image + EXIF (workflow-safe)

**File:** `intel_engine/modules/research_media_exif_reverse_links.py`  
**Module/Class:** `Research_Media_EXIF_ReverseLinks`  
**Purpose:** Extract EXIF from local images (if file paths provided) and generate reverse-search URLs (Lens/Bing/Yandex) rather than automating scraping.

## Inputs

- Use `profile["enrichment"]["identifiers"]` entries with `type` of `image_path` or `image_url` (store identifiers under `enrichment.identifiers` per schema).

## Outputs

- `geo.geo_coordinates` only if EXIF GPS is present and reliable
- `enrichment.raw_results` (`type: "exif"` and `type: "reverse_search_links"`)

## Implementation requirements

- No scraping of reverse image search engines; output links/workflow steps only.
- If image paths are used, validate file existence and handle errors cleanly.

