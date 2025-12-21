# Prompt 21 — Refactor `research_satellite_geo.py` to schema-compliant `geo` + `enrichment.raw_results`

**File:** `intel_engine/modules/research_satellite_geo.py`  
**Module/Class:** `Research_Satellite_Image_GeoMatch`  
**Problems:**
- Uses `profile["images"]` (not in schema; root `additionalProperties: false`).
- Writes `profile["geo"]` with keys not allowed by schema (geo only allows `cities`, `geo_coordinates`).
- Uses a `run()` method and an import path that does not match the rest of `intel_engine`.

## Refactor objective

- Stop using `profile["images"]`. Read image paths from a schema-compliant location:
  - Prefer `profile["metadata"]["file_sources"]` (list of URIs/paths) or `metadata.documents[*].file_sources` if that’s the existing pattern in this repo.
- Write structured geo output only to:
  - `geo.geo_coordinates`: list of `{latitude, longitude, radius_m?}`
  - `geo.cities`: list of strings (can be empty, but must exist)
- Store all unstructured extraction/match details in `enrichment.raw_results`.

## Outputs

- `geo`:
  - Ensure `geo.cities` exists (empty list if unknown)
  - Append any extracted GPS points to `geo.geo_coordinates` (dedupe)
- `enrichment.raw_results`:
  - One entry per processed image:
    - `identifier`: the image path/URI
    - `type`: `"image_exif_geo"`
    - `payload`: object containing extracted EXIF GPS fields, conversion results, simulated match output, and any errors

## Implementation requirements

- Convert this module to the standard engine interface:
  - Import `IntelModuleBase` from `intel_engine.core.module_base`
  - Implement `_execute_impl(self, profile) -> Dict[str, Any]`
  - Use `execute()` (do not rely on a custom `run()` entrypoint)
- Keep dependencies conservative; if PIL/Pillow is unavailable, record a graceful error into `raw_results` and return without mutating unknown schema fields.
- Initialize `enrichment` with required keys before appending.

