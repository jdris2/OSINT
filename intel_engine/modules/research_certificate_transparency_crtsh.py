"""
Research_Certificate_Transparency_CrtSh

Discovers subdomains via Certificate Transparency logs using crt.sh.
- For up to 5 domains in profile["digital"]["domains"], queries crt.sh for subdomains.
- Adds discovered FQDNs to profile["digital"]["domains"] (normalized, deduped, no wildcards).
- Stores raw crt.sh results in profile["enrichment"]["raw_results"] with type: "crtsh".
- Dedupe aggressively, ignore invalid domains/hosts.
- max_hosts param (default 300) limits number of domains added.
- Handles crt.sh fragility (timeouts, retries with backoff).
"""

import urllib.request
import urllib.error
import json
import time
import socket
from typing import Any, Dict, List, Set

try:
  from intel_engine.modules.base import IntelModuleBase
except ImportError:
  IntelModuleBase = object

CRT_SH_URL = "https://crt.sh/?q=%25.{domain}&exclude=expired&deduplicate=Y&output=json"
USER_AGENT = "IntelEngine-crtsh/1.0 (contact: example@example.com)"

def dedupe_list(seq):
  seen = set()
  return [x for x in seq if not (x in seen or seen.add(x))]

def normalize_domain(host):
  # Lowercase, strip leading/trailing whitespace, remove wildcards
  if not isinstance(host, str):
    return None
  host = host.strip().lower()
  if host.startswith("*."):
    host = host[2:]
  # Basic FQDN check: at least one dot, no spaces, no wildcards
  if "." not in host or " " in host or "*" in host:
    return None
  return host

class Research_Certificate_Transparency_CrtSh(IntelModuleBase):
  """
  Discover subdomains via crt.sh and update profile.
  """

  def enrich(self, profile: Dict[str, Any], max_hosts: int = 300) -> Dict[str, Any]:
    digital = profile.setdefault("digital", {})
    domains = digital.get("domains", [])
    enrichment = profile.setdefault("enrichment", {})
    raw_results = enrichment.setdefault("raw_results", [])

    # Limit to first 5 domains to avoid noise
    base_domains = [d for d in domains if isinstance(d, str)]
    base_domains = base_domains[:5]

    all_found: Set[str] = set(domains)
    crtsh_raw_rows: List[Dict[str, Any]] = []
    total_added = 0

    for domain in base_domains:
      url = CRT_SH_URL.format(domain=domain)
      req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
      attempt = 0
      while attempt < 2:
        try:
          with urllib.request.urlopen(req, timeout=15) as resp:
            if resp.status != 200:
              self.log_result(f"crt.sh {domain}: HTTP {resp.status}")
              break
            data = resp.read()
            try:
              rows = json.loads(data)
            except Exception as e:
              self.log_result(f"crt.sh {domain}: JSON decode error {e}")
              break
            crtsh_raw_rows.extend(rows)
            # Extract FQDNs from 'name_value' field
            for row in rows:
              name_val = row.get("name_value")
              if not name_val:
                continue
              # name_value can be multiline (multiple domains)
              for host in name_val.split("\n"):
                norm = normalize_domain(host)
                if norm and norm not in all_found:
                  all_found.add(norm)
                  total_added += 1
                  if total_added >= max_hosts:
                    break
              if total_added >= max_hosts:
                break
            break  # Success, exit retry loop
        except (urllib.error.URLError, socket.timeout) as e:
          self.log_result(f"crt.sh {domain}: timeout or error {e}, retrying...")
          time.sleep(2.0)
          attempt += 1
        except Exception as e:
          self.log_result(f"crt.sh {domain}: error {e}")
          break
      if total_added >= max_hosts:
        break

    # Update domains (deduped, max_hosts)
    digital["domains"] = dedupe_list(list(all_found))[:max_hosts]

    # Store raw results (trimmed to top N for summary)
    raw_payload = {
      "queried_domains": base_domains,
      "type": "crtsh",
      "rows": crtsh_raw_rows[:max_hosts],  # only top N
      "total_rows": len(crtsh_raw_rows),
      "note": f"Trimmed to {max_hosts} rows for summary"
    }
    raw_results.append({
      "identifier": ",".join(base_domains),
      "type": "crtsh",
      "payload": raw_payload
    })
    enrichment["raw_results"] = raw_results
    self.log_result(f"crt.sh: Added {total_added} new domains from CT logs")
    return profile

  def log_result(self, msg: str):
    if hasattr(super(), "log_result"):
      super().log_result(msg)
    else:
      print(msg)
