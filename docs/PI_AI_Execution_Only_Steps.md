# PI INTEL SYSTEM -- CLEAN EXECUTION-ONLY TASK FLOW (PASTE-AND-GO)

## TASK 1 -- Create Project Folder Structure

This sets up the entire project scaffold. Paste once, and it handles
structure, boilerplate, and docs.

> ✅ COPY & PASTE THIS PROMPT:

You are acting as a senior full-stack engineer. I want you to create a
complete folder structure for a modular AI-driven OSINT and PI
intelligence engine.\
\
TASK:\
\
1. Create the following structure:\
/intel_engine\
/core -- main logic, engine orchestrator, base classes\
/modules -- each intelligence module will live here\
/schemas -- input/output JSON schemas for module communication\
/ai -- AI-based planning/decision controller\
/reports -- exports and human-readable reports\
/tests -- all test files for validation\
\
2. Add \_\_init\_\_.py files to each folder.\
3. Create a README.md that explains each folder's purpose in 1 sentence
each.\
4. Output a Python script that builds this structure automatically.\
\
Respond with the full folder structure as text and include the script.\
Do not ask questions. Do not skip any part.

## TASK 2 -- Generate Profile Schema (Universal Data Format)

This defines the standard all modules will use to output results.

> ✅ COPY & PASTE THIS PROMPT:

You are creating the central profile schema for a modular AI-based OSINT
and PI system.\
\
TASK:\
\
1. Create a JSON Schema (Draft-07) called profile_schema.json.\
2. It should represent the complete structure of a person\'s digital,
legal, business, and social footprint.\
3. Required top-level fields:\
- identity: { full_name, aliases, dob, gender }\
- contact: { emails, phones, usernames, addresses }\
- digital: { ips, domains, devices, exposed_ports }\
- business: { abn, acn, company_names, roles, gst_status }\
- legal: { bankruptcies, court_cases, sanctions }\
- metadata: { documents, authors, file_sources }\
- social: { platforms, profile_links, last_activity }\
- geo: { cities, geo_coordinates }\
- risk: { exposure_score, red_flags }\
\
4. Output the JSON Schema. This file will be used by every module for
validation.\
\
Do not ask questions. Output the schema and stop.

## TASK 3 -- Build Module Template (All Modules Use This)

You only run this once. It defines how every module is shaped.

> ✅ COPY & PASTE THIS PROMPT:

You are building the module template for a modular intelligence system.\
\
TASK:\
\
1. Create a Python base class named IntelModuleBase.\
2. This class should live in: core/module_base.py\
3. The base class must include:\
- def execute(self, profile): \# core method each module overrides\
- def validate_input(self): \# validates profile against schema\
- def validate_output(self): \# ensures module output matches schema\
- def log_result(self): \# logs clean result with module tag\
\
4. Add docstrings to each method for clarity.\
5. This base will be inherited by all future modules.\
\
Respond with the full Python code. Do not leave any method empty.

## TASK 4 -- Generate a Working Research Module (ABN Lookup)

This is the first research module and will act as a working template.

> ✅ COPY & PASTE THIS PROMPT:

You are creating the first working module for the PI system.\
\
TASK:\
\
1. Create a module called Research_ABN_Lookup.\
2. Place it in: modules/research_abn_lookup.py\
3. Inherit from IntelModuleBase (core/module_base.py).\
4. Simulate a real ABN search using a mock API or placeholder function.\
5. Accept input: a name or business name from the profile.\
6. Output under profile\[\'business\'\] with:\
- abn, entity_name, registration_date, status, state, gst_status\
\
7. Include logging, schema validation, and inline documentation.\
\
Return full working code for this module. Do not skip validation or
schema linking.

## TASK 5 -- Build the AI Planner Logic Core

This creates the brain of the engine. It tells the system what module to
run next.

> ✅ COPY & PASTE THIS PROMPT:

You are writing the central planning logic for an intelligence engine.\
\
TASK:\
\
1. Create a class called AIPlanner in ai/planner.py.\
2. It should include the following methods:\
- analyze_gaps(profile): Checks for missing data in major schema
fields.\
- suggest_modules(profile, history): Returns a ranked list of modules to
run next.\
3. Logic must:\
- Never suggest a module already in the history log.\
- Prioritize modules based on completeness of schema fields.\
- Output suggested modules as a list of dicts: {module_name: score}\
\
Use inline comments to explain your reasoning logic in
suggest_modules().\
Output full code. Do not use placeholders.

## TASK 6 -- Build Report Generator (Readable Exports)

This takes the final profile and exports it in various formats.

> ✅ COPY & PASTE THIS PROMPT:

You are building the report system for the PI engine.\
\
TASK:\
\
1. Create a class named IntelReportBuilder in
reports/report_builder.py.\
2. This class must generate:\
- profile_report.json (raw structured data)\
- profile_report.md or profile_report.txt (formatted readable
intelligence report)\
\
3. Report must contain:\
- Identity summary\
- Known aliases, companies, phones, socials\
- Geo summary and IP/device data\
- Legal and exposure risks (highlight red flags)\
- Sources used (modules that added each field)\
- Risk score total\
\
Output all data to /reports/output/. Include inline comments.\
Return complete class code.

## TASK 7 -- TEMPLATE: Create Any Future Research Module (REUSABLE)

Use this every time you want a new research module added.

> ✅ COPY & PASTE THIS PROMPT:

You are building a research module using the existing base.\
\
TASK:\
\
1. Create a module named \[INSERT_MODULE_NAME\] in
modules/\[insert_file_name\].py\
2. Inherit from IntelModuleBase (core/module_base.py)\
3. Module must:\
- Accept a valid profile\
- Perform a lookup, scrape or data extract\
- Output clean, schema-compliant data into the correct section\
- Validate schema and log its source\
\
Replace mock functions with real lookups when available.\
Add docstring explaining the data source and purpose.\
\
Do not skip logging or schema compliance.\
Return complete working code.
