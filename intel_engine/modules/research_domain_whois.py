"""
Research_Domain_WHOIS_Owner Module

This module queries WHOIS data for all domains listed in the profile's digital section.
It extracts registrant name, creation date, registrar, and country for each domain.
The data source is the public WHOIS service (port 43), accessed via socket.
Results are stored in the profile['digital']['domains_whois'] field, schema-compliant.
"""

import socket
import re
from typing import Any, Dict, List, Optional

from intel_engine.core.module_base import IntelModuleBase

class Research_Domain_WHOIS_Owner(IntelModuleBase):
    def __init__(self, logger=None):
        super().__init__(
            module_name="Research_Domain_WHOIS_Owner",
            profile_schema=None,  # Use default or pass schema if needed
            output_schema=None,   # Use default or pass schema if needed
            logger=logger,
        )

    def _execute_impl(self, profile: Dict[str, Any]) -> Dict[str, Any]:
        digital = profile.get("digital", {})
        domains = digital.get("domains", [])
        whois_results = []

        for domain in domains:
            whois_data = self.query_whois(domain)
            parsed = self.parse_whois(whois_data)
            parsed["domain"] = domain
            whois_results.append(parsed)

        # Store results in a schema-compliant field
        # We'll use 'domains_whois' as a new field in digital
        output = dict(profile)
        output = output.copy()
        output.setdefault("digital", {}).update({"domains_whois": whois_results})
        return output

    def query_whois(self, domain: str) -> str:
        """Query the WHOIS server for a domain using port 43."""
        # Determine the correct WHOIS server for the TLD
        tld = domain.split('.')[-1].lower()
        whois_server = self.get_whois_server(tld)
        if not whois_server:
            return "WHOIS server not found for TLD: " + tld

        response = ""
        try:
            with socket.create_connection((whois_server, 43), timeout=8) as s:
                s.sendall((domain + "\r\n").encode("utf-8"))
                while True:
                    data = s.recv(4096)
                    if not data:
                        break
                    response += data.decode(errors="ignore")
        except Exception as e:
            response = f"WHOIS query failed: {e}"
        return response

    def get_whois_server(self, tld: str) -> Optional[str]:
        """Return the default WHOIS server for a given TLD."""
        # Minimal mapping for common TLDs
        servers = {
            "com": "whois.verisign-grs.com",
            "net": "whois.verisign-grs.com",
            "org": "whois.pir.org",
            "info": "whois.afilias.net",
            "biz": "whois.neulevel.biz",
            "io": "whois.nic.io",
            "co": "whois.nic.co",
            "us": "whois.nic.us",
            "uk": "whois.nic.uk",
            "au": "whois.audns.net.au",
            "de": "whois.denic.de",
            "fr": "whois.afnic.fr",
            "ru": "whois.tcinet.ru",
            "xyz": "whois.nic.xyz",
        }
        return servers.get(tld)

    def parse_whois(self, data: str) -> Dict[str, Any]:
        """Extract registrant name, creation date, registrar, and country from WHOIS data."""
        def search(patterns, text):
            for pat in patterns:
                m = re.search(pat, text, re.IGNORECASE)
                if m:
                    return m.group(1).strip()
            return None

        registrant_patterns = [
            r"Registrant Name:\s*(.+)",
            r"Registrant:\s*(.+)",
            r"Holder Name:\s*(.+)",
        ]
        creation_patterns = [
            r"Creation Date:\s*([0-9\-T:Z]+)",
            r"Created On:\s*([0-9\-T:Z]+)",
            r"Registered On:\s*([0-9\-T:Z]+)",
            r"Domain Create Date:\s*([0-9\-T:Z]+)",
        ]
        registrar_patterns = [
            r"Registrar:\s*(.+)",
            r"Sponsoring Registrar:\s*(.+)",
        ]
        country_patterns = [
            r"Registrant Country:\s*([A-Z]{2,})",
            r"Country:\s*([A-Z]{2,})",
        ]

        return {
            "registrant_name": search(registrant_patterns, data) or "",
            "creation_date": search(creation_patterns, data) or "",
            "registrar": search(registrar_patterns, data) or "",
            "country": search(country_patterns, data) or "",
            "raw_whois": data[:1000],  # Store a snippet for reference/debugging
        }
