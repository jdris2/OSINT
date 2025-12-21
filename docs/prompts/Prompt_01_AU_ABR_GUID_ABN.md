# Prompt 01 — AU ABR GUID enrichment (proper ABR API)

**File:** `intel_engine/modules/research_au_abr_guid_abn.py`  
**Module/Class:** `Research_AU_ABR_GUID_ABN`  
**Purpose:** Enrich business identity (ABN, entity name, state, GST) using ABR GUID API (free GUID registration).

## Data sources

- ABR JSON API: `https://abr.business.gov.au/json/AbnDetails.aspx?abn={ABN}&guid={GUID}`
- ABR JSON API: `https://abr.business.gov.au/json/MatchingNames.aspx?name={NAME}&maxResults={N}&guid={GUID}`

## Inputs (profile fields)

- `profile["business"]["abn"]` (preferred) OR
- `profile["business"]["company_names"][0]` OR
- `profile["identity"]["full_name"]` (fallback)

## Outputs (must be schema-compliant)

- Update `profile["business"]` only with schema-defined keys: `abn`, `acn` (if available), `company_names` (append entity name if new), `gst_status`
- Store detailed ABR payloads in `profile["enrichment"]["raw_results"]` entries:
  - `identifier`: the searched ABN or name
  - `type`: `"abr_abn_details"` / `"abr_matching_names"`
  - `payload`: raw JSON response (trim if huge)

## API key handling

- Read `ABR_GUID` from environment; raise a clear error if missing (do not hardcode).
- Mention the env var in the module docstring (do not write secrets into the repo).

## Implementation requirements

- Inherit `IntelModuleBase`.
- Build input/output schema by loading `intel_engine/schemas/profile_schema.json` and extracting `business` + `enrichment` subsections.
- Add rate limiting (e.g., 250–500ms sleep between requests) and a deterministic `User-Agent`.
- Log via `.log_result()`; include counts + which identifier was used.
- Do not create new fields in `business` beyond those already in the schema.

