"""
Research_Domain_Email_Enumeration Module

Data Source:
  - theHarvester (https://github.com/laramies/theHarvester)

Purpose:
  - Early-stage domain reconnaissance for emails, subdomains, and hosts tied to a target.
  - Results are normalized and used to enrich profile['digital'] with schema-compliant fields.
"""

from __future__ import annotations

import ipaddress
import json
import logging
import re
import shutil
import socket
import subprocess
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from intel_engine.core.module_base import IntelModuleBase

_DOMAIN_PATTERN = re.compile(
    r"^(?=.{1,253}$)(?!-)[A-Za-z0-9-]{1,63}(?<!-)"
    r"(\.(?!-)[A-Za-z0-9-]{1,63}(?<!-))+$"
)
_EMAIL_PATTERN = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")

_ALLOWED_SOURCES = {"google", "bing", "duckduckgo"}


def _load_profile_schema() -> Dict[str, Any]:
    candidate_paths = [
        Path(__file__).resolve().parents[1] / "schemas" / "profile_schema.json",
        Path(__file__).resolve().parents[2] / "schemas" / "profile_schema.json",
        Path(__file__).resolve().parents[2] / "profile_schema.json",
    ]
    for path in candidate_paths:
        if path.exists():
            with path.open("r", encoding="utf-8") as handle:
                return json.load(handle)
    raise FileNotFoundError(
        "Unable to locate schemas/profile_schema.json for validation."
    )


def _build_digital_schemas() -> Tuple[Dict[str, Any], Dict[str, Any]]:
    schema = _load_profile_schema()
    digital_schema = schema.get("properties", {}).get("digital")
    if not digital_schema:
        raise ValueError("profile_schema.json does not define a digital section.")

    input_schema = {
        "type": "object",
        "required": ["digital"],
        "properties": {"digital": digital_schema},
    }
    output_schema = {
        "type": "object",
        "required": ["digital"],
        "properties": {"digital": digital_schema},
    }
    return input_schema, output_schema


def _normalize_domain(domain: str) -> str:
    cleaned = domain.strip().lower()
    if "://" in cleaned:
        cleaned = cleaned.split("://", 1)[1]
    cleaned = cleaned.split("/", 1)[0]
    cleaned = cleaned.split(":", 1)[0]
    return cleaned.strip(".")


def _is_valid_domain(domain: str) -> bool:
    return bool(_DOMAIN_PATTERN.match(domain))


def _is_valid_email(email: str) -> bool:
    if len(email) > 254:
        return False
    return bool(_EMAIL_PATTERN.fullmatch(email))


def _coerce_sources(sources: Optional[Iterable[str]]) -> List[str]:
    if not sources:
        return sorted(_ALLOWED_SOURCES)
    normalized: List[str] = []
    for entry in sources:
        if not entry:
            continue
        for source in str(entry).split(","):
            cleaned = source.strip().lower()
            if cleaned and cleaned in _ALLOWED_SOURCES:
                normalized.append(cleaned)
    return sorted(set(normalized)) or sorted(_ALLOWED_SOURCES)


def _is_ipv4(value: str) -> bool:
    try:
        return isinstance(ipaddress.ip_address(value), ipaddress.IPv4Address)
    except ValueError:
        return False


def _split_host_entry(entry: str) -> Tuple[str, Optional[str]]:
    cleaned = entry.strip()
    if not cleaned:
        return "", None
    if ":" not in cleaned:
        return cleaned, None
    host, ip = cleaned.rsplit(":", 1)
    host = host.strip()
    ip = ip.strip()
    if _is_ipv4(ip):
        return host, ip
    return cleaned, None


class Research_Domain_Email_Enumeration(IntelModuleBase):
    """Enumerate domain emails, subdomains, and hosts using theHarvester."""

    MODULE_NAME = "Research_Domain_Email_Enumeration"

    def __init__(
        self,
        domain: Optional[str] = None,
        result_limit: int = 200,
        sources: Optional[Iterable[str]] = None,
        harvester_path: Optional[str] = None,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        input_schema, output_schema = _build_digital_schemas()
        super().__init__(
            module_name=self.MODULE_NAME,
            profile_schema=input_schema,
            output_schema=output_schema,
            logger=logger,
        )
        self.domain = _normalize_domain(domain) if domain else None
        self.result_limit = max(1, int(result_limit))
        self.sources = _coerce_sources(sources)
        self.harvester_path = harvester_path

    def _execute_impl(self, profile: Dict[str, Any]) -> Dict[str, Any]:
        target_domain = self._resolve_target_domain(profile)
        if not _is_valid_domain(target_domain):
            raise ValueError(f"Invalid target domain: {target_domain}")

        harvest_result = self._run_enumeration(target_domain)
        emails, hosts, ips_from_harvester = self._parse_harvest(harvest_result, target_domain)
        subdomains = self._extract_subdomains(target_domain, hosts, emails)
        resolved_ips = self._resolve_hosts(hosts)

        ranked_emails = self._rank_entities(emails)
        ranked_hosts = self._rank_entities(hosts)
        ranked_subdomains = self._rank_entities(subdomains)

        self._last_result = {
            "source": "theHarvester",
            "input": {
                "domain": target_domain,
                "result_limit": self.result_limit,
                "sources": list(self.sources),
            },
            "counts": {
                "emails": len(emails),
                "hosts": len(hosts),
                "subdomains": len(subdomains),
                "ips": len(set(ips_from_harvester + resolved_ips)),
            },
            "ranked": {
                "emails": ranked_emails[:10],
                "hosts": ranked_hosts[:10],
                "subdomains": ranked_subdomains[:10],
            },
        }
        self.log_result()

        digital = self._prepare_digital_section(profile)
        digital["domains"] = self._merge_unique(
            digital.get("domains", []),
            [target_domain] + hosts + subdomains,
        )
        digital["ips"] = self._merge_unique(
            digital.get("ips", []),
            ips_from_harvester + resolved_ips,
        )

        return {"digital": digital}

    def _resolve_target_domain(self, profile: Dict[str, Any]) -> str:
        if self.domain:
            return self.domain
        digital = profile.get("digital", {})
        domains = digital.get("domains") or []
        if not domains:
            raise ValueError("No target domain provided or available in profile.digital.domains")
        return _normalize_domain(domains[0])

    def _run_enumeration(self, domain: str) -> Dict[str, Any]:
        command = self._build_harvester_command(domain)
        if not command:
            self.logger.warning("theHarvester executable not found; skipping enumeration.")
            return {}

        output_base = None
        try:
            with tempfile.TemporaryDirectory(prefix="harvester_") as temp_dir:
                output_base = Path(temp_dir) / "harvest"
                cmd = command + [
                    "-d",
                    domain,
                    "-l",
                    str(self.result_limit),
                    "-b",
                    ",".join(self.sources),
                    "-f",
                    str(output_base),
                ]
                result = subprocess.run(
                    cmd,
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=180,
                )
                if result.returncode != 0:
                    self.logger.warning(
                        "theHarvester returned non-zero exit status %s", result.returncode
                    )
                json_path = Path(f"{output_base}.json")
                if not json_path.exists():
                    self.logger.warning("theHarvester JSON output not found at %s", json_path)
                    return {}
                with json_path.open("r", encoding="utf-8") as handle:
                    return json.load(handle)
        except subprocess.TimeoutExpired:
            self.logger.error("theHarvester timed out for domain %s", domain)
        except (OSError, json.JSONDecodeError) as exc:
            self.logger.error("theHarvester execution failed: %s", exc)
        finally:
            if output_base:
                self._cleanup_report_files(output_base)
        return {}

    def _cleanup_report_files(self, output_base: Path) -> None:
        for extension in (".json", ".xml"):
            path = Path(f"{output_base}{extension}")
            if path.exists():
                try:
                    path.unlink()
                except OSError:
                    self.logger.debug("Failed to cleanup %s", path)

    def _build_harvester_command(self, domain: str) -> List[str]:
        if self.harvester_path:
            return self._normalize_harvester_path(self.harvester_path)

        executable = shutil.which("theHarvester")
        if executable:
            return [executable]

        repo_path = Path(__file__).resolve().parents[2] / "theHarvester" / "theHarvester.py"
        if repo_path.exists():
            python_cmd = self._resolve_python()
            return [python_cmd, str(repo_path)]

        self.logger.warning("theHarvester not found for domain %s", domain)
        return []

    def _normalize_harvester_path(self, path: str) -> List[str]:
        candidate = Path(path)
        if candidate.is_dir():
            script = candidate / "theHarvester.py"
            if script.exists():
                python_cmd = self._resolve_python()
                return [python_cmd, str(script)]
        if candidate.exists():
            if candidate.name.endswith(".py"):
                python_cmd = self._resolve_python()
                return [python_cmd, str(candidate)]
            return [str(candidate)]
        return []

    def _resolve_python(self) -> str:
        repo_root = Path(__file__).resolve().parents[2]
        for venv_name in (".venv312", ".venv"):
            python_path = repo_root / venv_name / "bin" / "python"
            if python_path.exists():
                return str(python_path)
        return shutil.which("python3") or shutil.which("python") or "python3"

    def _parse_harvest(
        self, payload: Dict[str, Any], domain: str
    ) -> Tuple[List[str], List[str], List[str]]:
        emails: List[str] = []
        hosts: List[str] = []
        ips: List[str] = []

        for entry in payload.get("emails", []) or []:
            email = str(entry).strip().lower().strip(".")
            if not _is_valid_email(email):
                continue
            if not email.split("@", 1)[1].endswith(domain):
                continue
            emails.append(email)

        for entry in payload.get("hosts", []) or []:
            host_entry = str(entry).strip().lower()
            if not host_entry:
                continue
            host, ip = _split_host_entry(host_entry)
            if host and _is_valid_domain(host) and host.endswith(domain):
                hosts.append(host)
            if ip and _is_ipv4(ip):
                ips.append(ip)

        for entry in payload.get("ips", []) or []:
            ip = str(entry).strip()
            if _is_ipv4(ip):
                ips.append(ip)

        return emails, hosts, sorted(set(ips))

    def _extract_subdomains(
        self, domain: str, hosts: List[str], emails: List[str]
    ) -> List[str]:
        subdomains: List[str] = []
        for host in hosts:
            if host != domain and host.endswith(domain):
                subdomains.append(host)
        for email in emails:
            host = email.split("@", 1)[1]
            if host != domain and host.endswith(domain):
                subdomains.append(host)
        return [host for host in subdomains if _is_valid_domain(host)]

    def _resolve_hosts(self, hosts: List[str]) -> List[str]:
        ips: List[str] = []
        for host in sorted(set(hosts)):
            try:
                _, _, resolved = socket.gethostbyname_ex(host)
            except socket.gaierror:
                continue
            for ip in resolved:
                if _is_ipv4(ip):
                    ips.append(ip)
        return sorted(set(ips))

    def _rank_entities(self, entities: List[str]) -> List[str]:
        counts = Counter(entities)
        return [item for item, _ in counts.most_common()]

    def _prepare_digital_section(self, profile: Dict[str, Any]) -> Dict[str, Any]:
        source = profile.get("digital", {}) or {}
        digital: Dict[str, Any] = {}
        for key, value in source.items():
            if key in {"ips", "domains", "devices", "exposed_ports"}:
                digital[key] = value if isinstance(value, list) else []
        digital.setdefault("ips", [])
        digital.setdefault("domains", [])
        digital.setdefault("devices", [])
        digital.setdefault("exposed_ports", [])
        return digital

    def _merge_unique(self, existing: Iterable[str], incoming: Iterable[str]) -> List[str]:
        combined: List[str] = []
        seen = set()
        for item in list(existing) + list(incoming):
            cleaned = str(item).strip().lower()
            if not cleaned or cleaned in seen:
                continue
            if _is_ipv4(cleaned) or _is_valid_domain(cleaned):
                seen.add(cleaned)
                combined.append(cleaned)
        return combined
