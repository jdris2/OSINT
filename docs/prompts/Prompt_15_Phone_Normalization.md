# Prompt 15 — Phone enrichment (offline normalization)

**File:** `intel_engine/modules/research_phone_normalization.py`  
**Module/Class:** `Research_Phone_Normalization`  
**Purpose:** Normalize AU phone numbers and infer coarse region where possible without paid APIs.

## Inputs

- `contact.phones`

## Outputs

- Replace/append normalized E.164-style numbers back into `contact.phones` (dedupe)
- Store parsing details into `enrichment.raw_results` (`type: "phone_normalization"`)

## Implementation requirements

- No carrier lookups unless you have a truly free dataset.
- Handle messy input and keep original value in raw results.

