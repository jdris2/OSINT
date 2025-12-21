# OSINT Intel Engine – Module Build Prompts

This folder is a “prompt library”: each file is a ready-to-run instruction set you can copy/paste into an LLM agent (Codex, ChatGPT, etc.) to generate or refactor code in this repo in a consistent way.

## What these prompts are for (and how they fit in)

The `intel_engine/` package is a modular OSINT “intel engine”. Modules take a single input object (`profile`, a dict shaped by a JSON Schema) and enrich it with structured, schema-compliant findings.

Use these prompts to:

- Add new research/enrichment modules under `intel_engine/modules/`.
- Add utilities or integrations that support module execution.
- Refactor existing modules so they stop writing schema-unknown keys and instead store raw/unstructured outputs in `profile["enrichment"]["raw_results"]`.

The end goal is that every module “plugs in” cleanly: predictable inputs, predictable output locations, and auditable raw evidence attached to the profile.

## The contract: schema + raw results

This repo uses `intel_engine/schemas/profile_schema.json` as the contract between modules.

- Modules should only mutate keys that exist in the schema.
- If a data source returns variable/unstructured output (most do), store it as an `enrichment.raw_results[]` entry:
  - `identifier`: what you searched (domain/email/username/ip/file path/etc.)
  - `type`: stable label for the lookup (e.g., `rdap_domain`, `whois`, `image_exif`)
  - `payload`: the raw response or derived data as an object/dict (wrap lists/strings in an object)

This is what lets the engine keep “summary” fields clean while still preserving the full evidence trail.

## Where generated code should land

Most prompts specify the exact file path to create/update. In this repo, the usual locations are:

- Base class: `intel_engine/core/module_base.py` (`IntelModuleBase`)
- Modules: `intel_engine/modules/*.py`
- Schema: `intel_engine/schemas/profile_schema.json`
- Reports: `intel_engine/reports/*`

If you add a module that should be importable from `intel_engine.modules`, update `intel_engine/modules/__init__.py` to export it (optional, but keeps imports tidy).

## How to “complete” a prompt successfully

When you run one of these prompts in an agent, sanity-check the output before merging it:

1. **Path + class name match** the prompt header.
2. Module inherits `IntelModuleBase` and uses `execute(profile)` / `_execute_impl(profile)` pattern.
3. **No schema-unknown writes** (especially to `profile` root and `profile["digital"]`).
4. Raw/unstructured data is appended to `profile["enrichment"]["raw_results"]`.
5. Secrets are handled via environment variables (never hardcoded in code or docs).
6. The module logs via `.log_result()` and handles rate limits / HTTP errors gracefully.

For quick manual exercising, see `run.py` (it currently runs the ABN example module).

## Index

### Packs

- `PI_AI_Execution_Only_Steps.md`
- `PI_Module_Prompt_Pack_Enforced.md`
- `MODULE_PROMPTS.md`

Notes:
- `PI_AI_Execution_Only_Steps.md` is a generic “bootstrap” sequence; this repo already contains the scaffold under `intel_engine/`, so treat it as reference unless you’re rebuilding from scratch.
- `PI_Module_Prompt_Pack_Enforced.md` and `MODULE_PROMPTS.md` are higher-level prompt packs when you want multiple modules generated with the same enforcement rules.

### Individual Prompts

1. `Prompt_01_AU_ABR_GUID_ABN.md`
2. `Prompt_02_AU_auDA_RDAP.md`
3. `Prompt_03_Certificate_Transparency_CrtSh.md`
4. `Prompt_04_Wayback_CDX.md`
5. `Prompt_05_CommonCrawl_Index.md`
6. `Prompt_06_AU_DFAT_Sanctions.md`
7. `Prompt_07_AU_Trove.md`
8. `Prompt_08_AU_AusTender.md`
9. `Prompt_09_Integrations_Credentials_Utility.md`
10. `Prompt_10_Passive_Infrastructure_Attribution.md`
11. `Prompt_11_Media_EXIF_ReverseLinks.md`
12. `Prompt_12_Timeline_Aggregator.md`
13. `Prompt_13_Entity_Graph_Builder.md`
14. `Prompt_14_CodeRepo_Exposure_GitHub.md`
15. `Prompt_15_Phone_Normalization.md`
16. `Prompt_16_Evidence_Packager.md`
17. `Prompt_17_Refactor_To_Enrichment_RawResults.md`
18. `Prompt_18_Refactor_Domain_WHOIS_To_RawResults.md`
19. `Prompt_19_Refactor_ReconNG_To_RawResults.md`
20. `Prompt_20_Refactor_SpiderFoot_To_RawResults.md`
21. `Prompt_21_Refactor_Satellite_Geo_To_RawResults.md`

Tip: Prompts `17+` are “schema compliance refactors” — use them when a module currently writes convenient but schema-unknown fields (the fix is almost always: move that output into `enrichment.raw_results` and only promote high-confidence summaries into schema-defined arrays like `digital.domains`, `contact.emails`, etc.).
