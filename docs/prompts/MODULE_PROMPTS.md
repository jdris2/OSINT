# 🔍 PI INTEL SYSTEM – NEXT MODULES PROMPT PACK

**Enforced Template Applied** | Schema Validation Required | Logging Mandatory

---

## 📋 Module Template Requirements

All modules must:
- Inherit from `IntelModuleBase` (located in `core/module_base.py`)
- Accept a profile object with relevant fields
- Store results using schema-compliant field names
- Validate output using `schemas/profile_schema.json`
- Log inputs and results using `.log_result()` method
- Include docstring explaining data source and purpose

---

## 📚 Module Prompt Index

| Prompt File | Module Name |
| --- | --- |
| [GHunt_Module.md](GHunt_Module.md) | Research_Account_Google_Intel |
| [Metagoofil_Module.md](Metagoofil_Module.md) | Research_Metadata_Document_Extraction |
| [Photon_Module.md](Photon_Module.md) | Research_Web_Crawling_Photon |
| [ReconNG_Module.md](ReconNG_Module.md) | Research_Framework_ReconNG |
| [Sherlock_Module.md](Sherlock_Module.md) | Research_Identity_Username_Search |
| [Skiptracer_Module.md](Skiptracer_Module.md) | Research_Enrichment_Skiptracer |
| [SpiderFoot_Module.md](SpiderFoot_Module.md) | Research_Automation_SpiderFoot |
| [Twint_Module.md](Twint_Module.md) | Research_Social_Twitter_Intelligence |
| [theHarvester_Module.md](theHarvester_Module.md) | Research_Domain_Email_Enumeration |

---

## 🟦 Module 1: Research_CrossPlatform_Identity_Resolution

**File:** `modules/research_crossplatform_identity.py`

**Purpose:** Identity graph resolution across platforms

**Logic:**
- Accept username or email input
- Search public data: GitHub, Reddit, Instagram, LinkedIn
- Resolve linked accounts and generate identity graph
- Store in `profile['social']`

---

## 🟦 Module 2: Research_Historical_Account_Mutations

**File:** `modules/research_account_mutations.py`

**Purpose:** Track account name and alias changes

**Logic:**
- Track username, account name, or alias changes across platforms
- Use public archives or API history
- Document mutations chronologically
- Store in `profile['history']`

---

## 🟦 Module 3: Research_SocialNetwork_InfluenceMap

**File:** `modules/research_social_network.py`

**Purpose:** Social graph analysis and influence scoring

**Logic:**
- Analyze public engagement (mentions, replies, shared links)
- Build social network graph
- Calculate influence scores for subject
- Store in `profile['social']`

---

## 🟦 Module 4: Research_Media_ReverseImage_Correlation

**File:** `modules/research_media_image.py`

**Purpose:** Media metadata extraction and reverse image search

**Logic:**
- Extract metadata from image or media link
- Perform public reverse image search
- Identify first-seen, reuse, and correlations
- Store in `profile['media']`

---

## 🟦 Module 5: Research_Activity_Timeline_Reconstruction

**File:** `modules/research_timeline.py`

**Purpose:** Unified chronological timeline aggregation

**Logic:**
- Aggregate events, posts, breaches, and digital actions
- Create chronologically ordered timeline
- Unify across data sources
- Store in `profile['timeline']`

---

## 🟦 Module 6: Research_Infrastructure_Attribution_Enhanced

**File:** `modules/research_infra_attribution.py`

**Purpose:** Enhanced infrastructure and hosting attribution

**Logic:**
- Perform ASN correlation
- Analyze TLS certificates
- Use passive DNS correlation
- Enhance domain and IP attribution
- Store in `profile['digital']`

---

## 🟦 Module 7: Research_Deception_Signal_Detector

**File:** `modules/research_deception_signals.py`

**Purpose:** Detect manipulation and automation signals

**Logic:**
- Analyze account activity for deception patterns
- Detect manipulation and automation signals
- Use behavioral and linguistic analysis
- Store in `profile['risk']`

---

## 🟦 Module 8: Research_TextGeolocation_Inference

**File:** `modules/research_text_geo.py`

**Purpose:** Location inference from text and behavior

**Logic:**
- Extract linguistic clues
- Analyze temporal patterns
- Use contextual information
- Infer possible locations
- Store in `profile['geo']`

---

## 🟦 Module 9: Research_EntityRelationship_GraphBuilder

**File:** `modules/research_entity_graph.py`

**Purpose:** Multi-entity relationship graph construction

**Logic:**
- Build relationship graph between entities
- Connect people, accounts, domains
- Integrate input from multiple modules
- Maintain graph structure
- Store in `profile['relationships']`

---

## 🟦 Module 10: Research_AI_Collection_Orchestrator

**File:** `modules/research_ai_orchestrator.py`

**Purpose:** Intelligent module sequencing and coordination

**Logic:**
- Use investigation objectives to select modules
- Call other research modules in dependency-aware sequence
- Avoid logic duplication
- Orchestrate module execution flow
- Store in `profile['orchestration']`

---

## ✅ Quality Checklist

- [ ] Module inherits from `IntelModuleBase`
- [ ] Input validation implemented
- [ ] Schema validation against `schemas/profile_schema.json`
- [ ] Results logged via `.log_result()`
- [ ] Docstring explains data source and purpose
- [ ] No skipped validation steps
- [ ] Fully functional, production-ready code
