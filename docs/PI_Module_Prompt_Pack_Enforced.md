# PI INTEL SYSTEM – MODULE GENERATION PROMPT PACK (WITH TEMPLATE ENFORCEMENT)

## 🔒 IMPORTANT TEMPLATE RULE FOR ALL MODULES

All modules must follow this standard:
- Inherit from `IntelModuleBase` (found in `core/module_base.py`)
- Validate all input and output using `profile_schema.json` (found in `schemas/`)
- Use `.log_result()` from the base class to log source and result
- Only write to one section of the profile object using schema-compliant fields

---

### Research_Social_Twitter_Activity

**📂 File:** `modules/research_twitter_activity.py`  
**🧠 Target:** Find and extract a Twitter/X profile, bio, recent tweets, and follower count for the subject.  
**📦 Writes to:** `profile['social']`

**✅ COPY & PASTE THIS PROMPT:**

```
You are building a research module for a modular PI intelligence engine.

TASK:

1. Create a module named Research_Social_Twitter_Activity in modules/research_twitter_activity.py
2. Inherit from IntelModuleBase (located in core/module_base.py)
3. This module will:
- Accept a profile object with the relevant fields for this task
- Perform the following logic: Find and extract a Twitter/X profile, bio, recent tweets, and follower count for the subject.
- Store results inside profile['social'] using schema-compliant field names
- Validate output using schemas/profile_schema.json
- Log inputs and results using the .log_result() method

Include a docstring at the top that explains the data source and purpose.
Do not skip validation or logging. Return fully functional code only.
```


---

### Research_Shared_Breaches_HaveIBeenPwned

**📂 File:** `modules/research_data_breaches.py`  
**🧠 Target:** Check if subject's email(s) appear in known data breaches and include what leaked (passwords, location, etc).  
**📦 Writes to:** `profile['risk']`

**✅ COPY & PASTE THIS PROMPT:**

```
You are building a research module for a modular PI intelligence engine.

TASK:

1. Create a module named Research_Shared_Breaches_HaveIBeenPwned in modules/research_data_breaches.py
2. Inherit from IntelModuleBase (located in core/module_base.py)
3. This module will:
- Accept a profile object with the relevant fields for this task
- Perform the following logic: Check if subject's email(s) appear in known data breaches and include what leaked (passwords, location, etc).
- Store results inside profile['risk'] using schema-compliant field names
- Validate output using schemas/profile_schema.json
- Log inputs and results using the .log_result() method

Include a docstring at the top that explains the data source and purpose.
Do not skip validation or logging. Return fully functional code only.
```


---

### Research_Domain_WHOIS_Owner

**📂 File:** `modules/research_domain_whois.py`  
**🧠 Target:** Query WHOIS data on any known domains and return registrant name, creation date, registrar, and country.  
**📦 Writes to:** `profile['digital']`

**✅ COPY & PASTE THIS PROMPT:**

```
You are building a research module for a modular PI intelligence engine.

TASK:

1. Create a module named Research_Domain_WHOIS_Owner in modules/research_domain_whois.py
2. Inherit from IntelModuleBase (located in core/module_base.py)
3. This module will:
- Accept a profile object with the relevant fields for this task
- Perform the following logic: Query WHOIS data on any known domains and return registrant name, creation date, registrar, and country.
- Store results inside profile['digital'] using schema-compliant field names
- Validate output using schemas/profile_schema.json
- Log inputs and results using the .log_result() method

Include a docstring at the top that explains the data source and purpose.
Do not skip validation or logging. Return fully functional code only.
```


---

### Research_Phone_Number_Metadata

**📂 File:** `modules/research_phone_lookup.py`  
**🧠 Target:** Use a metadata API or database to resolve the country, carrier, and type (mobile/landline/VOIP) for each phone.  
**📦 Writes to:** `profile['contact']`

**✅ COPY & PASTE THIS PROMPT:**

```
You are building a research module for a modular PI intelligence engine.

TASK:

1. Create a module named Research_Phone_Number_Metadata in modules/research_phone_lookup.py
2. Inherit from IntelModuleBase (located in core/module_base.py)
3. This module will:
- Accept a profile object with the relevant fields for this task
- Perform the following logic: Use a metadata API or database to resolve the country, carrier, and type (mobile/landline/VOIP) for each phone.
- Store results inside profile['contact'] using schema-compliant field names
- Validate output using schemas/profile_schema.json
- Log inputs and results using the .log_result() method

Include a docstring at the top that explains the data source and purpose.
Do not skip validation or logging. Return fully functional code only.
```


---

### Research_CourtCases_AU_NSW

**📂 File:** `modules/research_au_court_nsw.py`  
**🧠 Target:** Search publicly listed NSW court filings by full name and return case numbers, court names, and filing status.  
**📦 Writes to:** `profile['legal']`

**✅ COPY & PASTE THIS PROMPT:**

```
You are building a research module for a modular PI intelligence engine.

TASK:

1. Create a module named Research_CourtCases_AU_NSW in modules/research_au_court_nsw.py
2. Inherit from IntelModuleBase (located in core/module_base.py)
3. This module will:
- Accept a profile object with the relevant fields for this task
- Perform the following logic: Search publicly listed NSW court filings by full name and return case numbers, court names, and filing status.
- Store results inside profile['legal'] using schema-compliant field names
- Validate output using schemas/profile_schema.json
- Log inputs and results using the .log_result() method

Include a docstring at the top that explains the data source and purpose.
Do not skip validation or logging. Return fully functional code only.
```


---

### Research_Property_Ownership_AU_VIC

**📂 File:** `modules/research_property_vic.py`  
**🧠 Target:** Search public VIC property data and return properties owned, transaction history, and parcel IDs.  
**📦 Writes to:** `profile['geo']`

**✅ COPY & PASTE THIS PROMPT:**

```
You are building a research module for a modular PI intelligence engine.

TASK:

1. Create a module named Research_Property_Ownership_AU_VIC in modules/research_property_vic.py
2. Inherit from IntelModuleBase (located in core/module_base.py)
3. This module will:
- Accept a profile object with the relevant fields for this task
- Perform the following logic: Search public VIC property data and return properties owned, transaction history, and parcel IDs.
- Store results inside profile['geo'] using schema-compliant field names
- Validate output using schemas/profile_schema.json
- Log inputs and results using the .log_result() method

Include a docstring at the top that explains the data source and purpose.
Do not skip validation or logging. Return fully functional code only.
```


---

### Research_GitHub_Username_Profile

**📂 File:** `modules/research_github.py`  
**🧠 Target:** Find GitHub profiles that match a given username, extract name, bio, repos, and contribution history.  
**📦 Writes to:** `profile['social']`

**✅ COPY & PASTE THIS PROMPT:**

```
You are building a research module for a modular PI intelligence engine.

TASK:

1. Create a module named Research_GitHub_Username_Profile in modules/research_github.py
2. Inherit from IntelModuleBase (located in core/module_base.py)
3. This module will:
- Accept a profile object with the relevant fields for this task
- Perform the following logic: Find GitHub profiles that match a given username, extract name, bio, repos, and contribution history.
- Store results inside profile['social'] using schema-compliant field names
- Validate output using schemas/profile_schema.json
- Log inputs and results using the .log_result() method

Include a docstring at the top that explains the data source and purpose.
Do not skip validation or logging. Return fully functional code only.
```


---

### Research_Shady_Pastebin_Matches

**📂 File:** `modules/research_pastebin.py`  
**🧠 Target:** Scan Pastebin or paste dump aggregators for matches with email, phone, or alias from the profile.  
**📦 Writes to:** `profile['risk']`

**✅ COPY & PASTE THIS PROMPT:**

```
You are building a research module for a modular PI intelligence engine.

TASK:

1. Create a module named Research_Shady_Pastebin_Matches in modules/research_pastebin.py
2. Inherit from IntelModuleBase (located in core/module_base.py)
3. This module will:
- Accept a profile object with the relevant fields for this task
- Perform the following logic: Scan Pastebin or paste dump aggregators for matches with email, phone, or alias from the profile.
- Store results inside profile['risk'] using schema-compliant field names
- Validate output using schemas/profile_schema.json
- Log inputs and results using the .log_result() method

Include a docstring at the top that explains the data source and purpose.
Do not skip validation or logging. Return fully functional code only.
```


---

### Research_Documents_Metadata_Scan

**📂 File:** `modules/research_doc_metadata.py`  
**🧠 Target:** Extract metadata from document uploads including author, device name, creation app, GPS tags if any.  
**📦 Writes to:** `profile['metadata']`

**✅ COPY & PASTE THIS PROMPT:**

```
You are building a research module for a modular PI intelligence engine.

TASK:

1. Create a module named Research_Documents_Metadata_Scan in modules/research_doc_metadata.py
2. Inherit from IntelModuleBase (located in core/module_base.py)
3. This module will:
- Accept a profile object with the relevant fields for this task
- Perform the following logic: Extract metadata from document uploads including author, device name, creation app, GPS tags if any.
- Store results inside profile['metadata'] using schema-compliant field names
- Validate output using schemas/profile_schema.json
- Log inputs and results using the .log_result() method

Include a docstring at the top that explains the data source and purpose.
Do not skip validation or logging. Return fully functional code only.
```


---

### Research_Satellite_Image_GeoMatch

**📂 File:** `modules/research_satellite_geo.py`  
**🧠 Target:** Match image EXIF location data with satellite coordinates to estimate precise known addresses.  
**📦 Writes to:** `profile['geo']`

**✅ COPY & PASTE THIS PROMPT:**

```
You are building a research module for a modular PI intelligence engine.

TASK:

1. Create a module named Research_Satellite_Image_GeoMatch in modules/research_satellite_geo.py
2. Inherit from IntelModuleBase (located in core/module_base.py)
3. This module will:
- Accept a profile object with the relevant fields for this task
- Perform the following logic: Match image EXIF location data with satellite coordinates to estimate precise known addresses.
- Store results inside profile['geo'] using schema-compliant field names
- Validate output using schemas/profile_schema.json
- Log inputs and results using the .log_result() method

Include a docstring at the top that explains the data source and purpose.
Do not skip validation or logging. Return fully functional code only.
```


---
