# Prompt 08 — AusTender procurement linkage (free key on request)

**File:** `intel_engine/modules/research_au_austender.py`  
**Module/Class:** `Research_AU_AusTender`  
**Purpose:** Discover government procurement relationships for AU entities (supplier names, contract metadata).

## Data sources

- AusTender API (keyed; free registration) OR data.gov.au dataset endpoint if no key available.

## API key

- `AUSTENDER_API_KEY` env var (if using API mode).

## Inputs

- `business.company_names`, `business.abn` (if present)

## Outputs

- `profile["enrichment"]["raw_results"]` (`type: "austender_contracts"`) with contract summaries
- Default to raw-only; avoid writing into `business.roles` unless you have strong, explicit role evidence.

## Implementation requirements

- Provide a `mode="api"|"dataset"` setting based on env var presence.
- Strong normalization/dedupe for supplier names.
- Track query terms + result counts in `.log_result()` output.

