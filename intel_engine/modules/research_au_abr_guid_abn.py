"""
Research_AU_ABR_GUID_ABN

Enriches Australian business identity information using the ABR GUID API.
Requires the environment variable ABR_GUID to be set with your GUID key.

- Updates only schema-defined fields in profile["business"]: abn, acn, company_names, gst_status.
- Stores raw ABR API responses in profile["enrichment"]["raw_results"].
- Logs results and enforces rate limiting.
"""

import os
import time
import json
import urllib.request
import urllib.parse

from typing import Any, Dict, List

# Import IntelModuleBase from your project structure
try:
  from intel_engine.modules.base import IntelModuleBase
except ImportError:
  IntelModuleBase = object  # fallback for context where base is not available

SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "..", "schemas", "profile_schema.json")

def load_schema():
  with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
    schema = json.load(f)
  business_keys = list(schema.get("properties", {}).get("business", {}).get("properties", {}).keys())
  enrichment_keys = list(schema.get("properties", {}).get("enrichment", {}).get("properties", {}).keys())
  return business_keys, enrichment_keys

BUSINESS_KEYS, ENRICHMENT_KEYS = load_schema()

class Research_AU_ABR_GUID_ABN(IntelModuleBase):
  """
  Enriches profile["business"] using the ABR GUID API.
  Requires ABR_GUID environment variable.
  """

  ABR_ABN_URL = "https://abr.business.gov.au/json/AbnDetails.aspx"
  ABR_NAME_URL = "https://abr.business.gov.au/json/MatchingNames.aspx"
  USER_AGENT = "IntelEngine-ABR/1.0 (contact: example@example.com)"

  def __init__(self):
    self.guid = os.environ.get("ABR_GUID")
    if not self.guid:
      raise RuntimeError("ABR_GUID environment variable is required for ABR API access.")
    super().__init__()

  def enrich(self, profile: Dict[str, Any]) -> Dict[str, Any]:
    business = profile.get("business", {})
    enrichment = profile.setdefault("enrichment", {})
    raw_results = enrichment.setdefault("raw_results", [])

    abn = business.get("abn")
    company_names = business.get("company_names", [])
    full_name = profile.get("identity", {}).get("full_name")

    identifier = None
    abn_result = None
    name_result = None

    # 1. Try ABN
    if abn:
      identifier = abn
      abn_result = self.query_abn(abn)
      if abn_result:
        self.update_business_from_abn(business, abn_result)
        self.append_raw_result(raw_results, abn, "abr_abn_details", abn_result)
        self.log_result(f"ABN lookup: {abn} - found")
      else:
        self.log_result(f"ABN lookup: {abn} - not found")
      time.sleep(0.3)
    # 2. Try company name
    elif company_names:
      identifier = company_names[0]
      name_result = self.query_name(company_names[0])
      if name_result:
        self.append_raw_result(raw_results, company_names[0], "abr_matching_names", name_result)
        self.log_result(f"Company name lookup: {company_names[0]} - {len(name_result.get('Names', []))} results")
        # Try to enrich with first ABN if available
        abn_from_name = self.extract_first_abn_from_names(name_result)
        if abn_from_name:
          abn_result = self.query_abn(abn_from_name)
          if abn_result:
            self.update_business_from_abn(business, abn_result)
            self.append_raw_result(raw_results, abn_from_name, "abr_abn_details", abn_result)
            self.log_result(f"ABN from name lookup: {abn_from_name} - found")
          time.sleep(0.3)
      else:
        self.log_result(f"Company name lookup: {company_names[0]} - not found")
      time.sleep(0.3)
    # 3. Try full name
    elif full_name:
      identifier = full_name
      name_result = self.query_name(full_name)
      if name_result:
        self.append_raw_result(raw_results, full_name, "abr_matching_names", name_result)
        self.log_result(f"Full name lookup: {full_name} - {len(name_result.get('Names', []))} results")
        abn_from_name = self.extract_first_abn_from_names(name_result)
        if abn_from_name:
          abn_result = self.query_abn(abn_from_name)
          if abn_result:
            self.update_business_from_abn(business, abn_result)
            self.append_raw_result(raw_results, abn_from_name, "abr_abn_details", abn_result)
            self.log_result(f"ABN from full name lookup: {abn_from_name} - found")
          time.sleep(0.3)
      else:
        self.log_result(f"Full name lookup: {full_name} - not found")
      time.sleep(0.3)
    else:
      self.log_result("No ABN, company name, or full name available for lookup.")

    # Only keep allowed keys in business
    profile["business"] = {k: v for k, v in business.items() if k in BUSINESS_KEYS}
    profile["enrichment"]["raw_results"] = raw_results
    return profile

  def query_abn(self, abn: str) -> Dict[str, Any]:
    params = {
      "abn": abn,
      "guid": self.guid
    }
    url = f"{self.ABR_ABN_URL}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": self.USER_AGENT})
    try:
      with urllib.request.urlopen(req, timeout=10) as resp:
        data = resp.read()
        return json.loads(data)
    except Exception as e:
      self.log_result(f"Error querying ABN {abn}: {e}")
      return {}

  def query_name(self, name: str) -> Dict[str, Any]:
    params = {
      "name": name,
      "maxResults": 10,
      "guid": self.guid
    }
    url = f"{self.ABR_NAME_URL}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": self.USER_AGENT})
    try:
      with urllib.request.urlopen(req, timeout=10) as resp:
        data = resp.read()
        return json.loads(data)
    except Exception as e:
      self.log_result(f"Error querying name {name}: {e}")
      return {}

  def update_business_from_abn(self, business: Dict[str, Any], abn_result: Dict[str, Any]):
    # Only update allowed fields
    abn = abn_result.get("Abn")
    acn = abn_result.get("Acn")
    entity_name = abn_result.get("EntityName")
    gst = abn_result.get("Gst")
    if abn:
      business["abn"] = abn
    if acn:
      business["acn"] = acn
    if entity_name:
      names = business.get("company_names", [])
      if entity_name not in names:
        names.append(entity_name)
      business["company_names"] = names
    if gst:
      business["gst_status"] = gst

  def append_raw_result(self, raw_results: List[Dict[str, Any]], identifier: str, typ: str, payload: Any):
    # Truncate payload if huge
    payload_str = json.dumps(payload)
    if len(payload_str) > 10000:
      payload = payload_str[:10000] + "...[truncated]"
    raw_results.append({
      "identifier": identifier,
      "type": typ,
      "payload": payload
    })

  def extract_first_abn_from_names(self, name_result: Dict[str, Any]) -> str:
    names = name_result.get("Names", [])
    if names and isinstance(names, list):
      for entry in names:
        abn = entry.get("Abn")
        if abn:
          return abn
    return ""

  def log_result(self, msg: str):
    # Use the base class logger if available, else print
    if hasattr(super(), "log_result"):
      super().log_result(msg)
    else:
      print(msg)
