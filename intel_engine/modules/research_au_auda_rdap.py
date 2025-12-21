"""
Research_AU_auDA_RDAP

Enriches .au domains using authoritative auDA RDAP.
- For each .au domain in profile["digital"]["domains"]:
    - Fetches RDAP from https://rdap.audns.net.au/domain/{domain}
    - Extracts registrant/org hints, nameservers, status
    - Adds discovered domains (canonical, www) to profile["digital"]["domains"] (dedupe)
    - Appends raw RDAP JSON to profile["enrichment"]["raw_results"] with type: "rdap_domain"
    - If org/entity name found, adds to profile["business"]["company_names"] (dedupe) and includes justification/confidence in raw results
- Handles 404/429 gracefully, logs errors
- Uses urllib.request only
- Does not add new schema fields
"""

import urllib.request
import urllib.error
import json
import time
from typing import Any, Dict, List

try:
  from intel_engine.modules.base import IntelModuleBase
except ImportError:
  IntelModuleBase = object

RDAP_URL = "https://rdap.audns.net.au/domain/{}"
USER_AGENT = "IntelEngine-auDA-RDAP/1.0 (contact: example@example.com)"

def dedupe_list(seq):
  seen = set()
  return [x for x in seq if not (x in seen or seen.add(x))]

class Research_AU_auDA_RDAP(IntelModuleBase):
  """
  Enriches .au domains using auDA RDAP.
  """

  def enrich(self, profile: Dict[str, Any]) -> Dict[str, Any]:
    digital = profile.setdefault("digital", {})
    domains = digital.get("domains", [])
    enrichment = profile.setdefault("enrichment", {})
    raw_results = enrichment.setdefault("raw_results", [])
    business = profile.setdefault("business", {})
    company_names = business.setdefault("company_names", [])

    # Only .au domains
    au_domains = [d for d in domains if isinstance(d, str) and d.lower().endswith(".au")]
    discovered_domains = set(domains)

    for domain in au_domains:
      # Add canonical and www forms
      base = domain.lower().lstrip("www.")
      discovered_domains.add(base)
      discovered_domains.add("www." + base)

      rdap_url = RDAP_URL.format(base)
      req = urllib.request.Request(rdap_url, headers={"User-Agent": USER_AGENT})
      try:
        with urllib.request.urlopen(req, timeout=10) as resp:
          if resp.status != 200:
            self.log_result(f"RDAP {domain}: HTTP {resp.status}")
            continue
          data = resp.read()
          rdap_json = json.loads(data)
      except urllib.error.HTTPError as e:
        if e.code == 404:
          self.log_result(f"RDAP {domain}: Not found (404)")
        elif e.code == 429:
          self.log_result(f"RDAP {domain}: Rate limited (429)")
        else:
          self.log_result(f"RDAP {domain}: HTTP error {e.code}")
        continue
      except Exception as e:
        self.log_result(f"RDAP {domain}: Error {e}")
        continue

      # Extract org/entity name
      org_name, org_justification = self.extract_org_name(rdap_json)
      if org_name:
        if org_name not in company_names:
          company_names.append(org_name)
        # Add justification/confidence to raw result
        justification = {
          "source": "auDA RDAP",
          "field": "registrant/entity",
          "value": org_name,
          "justification": org_justification,
          "confidence": "high" if org_justification else "medium"
        }
      else:
        justification = None

      # Extract nameservers
      nameservers = self.extract_nameservers(rdap_json)
      # Extract status
      status = rdap_json.get("status", [])

      # Append raw RDAP result
      raw_payload = {
        "domain": base,
        "rdap": rdap_json,
        "nameservers": nameservers,
        "status": status,
      }
      if org_name:
        raw_payload["org_name"] = org_name
        raw_payload["org_justification"] = org_justification
        raw_payload["org_confidence"] = justification["confidence"]
      raw_results.append({
        "identifier": base,
        "type": "rdap_domain",
        "payload": raw_payload,
        "justification": justification if justification else None
      })

      self.log_result(f"RDAP {domain}: Success, org={org_name}, nameservers={len(nameservers)}")
      time.sleep(0.3)  # polite rate limit

    # Dedupe and update domains and company_names
    digital["domains"] = dedupe_list(list(discovered_domains))
    business["company_names"] = dedupe_list(company_names)
    enrichment["raw_results"] = raw_results
    return profile

  def extract_org_name(self, rdap_json: Dict[str, Any]):
    # Try to extract org/entity name from RDAP
    # Look for entities with roles containing 'registrant' or 'registrar'
    entities = rdap_json.get("entities", [])
    for ent in entities:
      roles = ent.get("roles", [])
      vcard = ent.get("vcardArray", [])
      if "registrant" in roles or "registrar" in roles:
        name = self._extract_vcard_name(vcard)
        if name:
          return name, f"entity with roles {roles}"
    # Fallback: look for vcard name anywhere
    for ent in entities:
      vcard = ent.get("vcardArray", [])
      name = self._extract_vcard_name(vcard)
      if name:
        return name, "entity vcard"
    # Fallback: look for remarks
    remarks = rdap_json.get("remarks", [])
    for r in remarks:
      desc = r.get("description", [])
      for d in desc:
        if "registrant" in d.lower() or "entity" in d.lower():
          return d, "remarks"
    return None, None

  def _extract_vcard_name(self, vcard):
    # vcardArray: ["vcard", [ [ "fn", {}, "text", "Name" ], ... ] ]
    if isinstance(vcard, list) and len(vcard) == 2 and isinstance(vcard[1], list):
      for entry in vcard[1]:
        if isinstance(entry, list) and len(entry) >= 4 and entry[0] == "fn":
          return entry[3]
    return None

  def extract_nameservers(self, rdap_json: Dict[str, Any]):
    # nameservers: list of dicts with "ldhName"
    ns = []
    for n in rdap_json.get("nameservers", []):
      name = n.get("ldhName")
      if name:
        ns.append(name)
    return ns

  def log_result(self, msg: str):
    if hasattr(super(), "log_result"):
      super().log_result(msg)
    else:
      print(msg)
