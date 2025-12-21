# Prompt 06 — DFAT sanctions screening (AU-focused)

**File:** `intel_engine/modules/research_au_dfat_sanctions.py`  
**Module/Class:** `Research_AU_DFAT_Sanctions`  
**Purpose:** Screen the subject against DFAT consolidated sanctions list and record matches in `legal.sanctions` plus `risk.red_flags`.

## Data sources (official DFAT)

- DFAT consolidated list feed (CSV/XML). Implement with a single URL constant and a docstring note that DFAT may change URLs over time.

## Inputs

- `profile["identity"]["full_name"]`, `profile["identity"]["aliases"]`, `profile["identity"]["dob"]`
- `profile["business"]["company_names"]` (for entity screening)

## Outputs (schema-defined)

- Append to `profile["legal"]["sanctions"]` objects shaped as:
  - `list` (e.g., `"DFAT Consolidated"`)
  - `authority` (e.g., `"DFAT"`)
  - `reason` (match rationale: name/DOB/alias)
  - `date` (if present)
- Append to `profile["risk"]["red_flags"]` with `category: "sanctions_match"` and severity based on match confidence
- Store raw matched record(s) in `profile["enrichment"]["raw_results"]` (`type: "dfat_sanctions_match"`)

## Implementation requirements

- Conservative matching: exact/normalized name match by default; optional fuzzy matching behind `enable_fuzzy=False`.
- Never claim certainty; always include confidence + match rationale.
- Handle empty/partial profiles gracefully (log + return no matches).

