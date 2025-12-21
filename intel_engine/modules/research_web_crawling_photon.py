"""
Research_Web_Crawling_Photon

Data Source:
  - Photon (https://github.com/s0md3v/Photon)

Purpose:
  - Crawl a target site to map its exposed web attack surface and extract
    URLs, assets, emails, and endpoints for digital footprint analysis.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import shlex
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple
from urllib.parse import urljoin, urlsplit, urlunsplit

from intel_engine.core.module_base import IntelModuleBase

_EMAIL_PATTERN = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_URL_PATTERN = re.compile(r"https?://[^\s\"'<>]+")
_ASSET_EXTENSIONS = {
    ".js",
    ".css",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".svg",
    ".webp",
    ".ico",
    ".pdf",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".ppt",
    ".pptx",
    ".zip",
    ".rar",
    ".7z",
}


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


def _normalize_url(value: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        return ""
    if "://" not in cleaned:
        cleaned = f"https://{cleaned}"
    parts = urlsplit(cleaned)
    if not parts.netloc:
        return ""
    path = parts.path or "/"
    return urlunsplit((parts.scheme, parts.netloc, path, "", ""))


def _is_valid_url(value: str) -> bool:
    parts = urlsplit(value)
    return parts.scheme in {"http", "https"} and bool(parts.netloc)


def _canonicalize_url(value: str) -> str:
    parts = urlsplit(value)
    netloc = parts.netloc.lower()
    if netloc.endswith(":80"):
        netloc = netloc[:-3]
    if netloc.endswith(":443"):
        netloc = netloc[:-4]
    path = parts.path or "/"
    if path != "/" and path.endswith("/"):
        path = path[:-1]
    return urlunsplit((parts.scheme.lower(), netloc, path, parts.query, ""))


def _base_domain(netloc: str) -> str:
    cleaned = netloc.split(":", 1)[0].lower()
    if cleaned.startswith("www."):
        cleaned = cleaned[4:]
    return cleaned


def _is_asset(url: str) -> bool:
    parts = urlsplit(url)
    path = parts.path.lower()
    for ext in _ASSET_EXTENSIONS:
        if path.endswith(ext):
            return True
    return False


def _dedupe_hash(entries: Sequence[str]) -> List[str]:
    seen: set[str] = set()
    unique: List[str] = []
    for entry in entries:
        fingerprint = hashlib.sha1(entry.encode("utf-8")).hexdigest()
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        unique.append(entry)
    return unique


class Research_Web_Crawling_Photon(IntelModuleBase):
    """Crawl web targets via Photon and map URLs, assets, emails, and endpoints."""

    MODULE_NAME = "Research_Web_Crawling_Photon"

    def __init__(
        self,
        base_url: Optional[str] = None,
        depth: int = 2,
        threads: int = 6,
        timeout_s: int = 180,
        photon_path: Optional[str] = None,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        input_schema, output_schema = _build_digital_schemas()
        super().__init__(
            module_name=self.MODULE_NAME,
            profile_schema=input_schema,
            output_schema=output_schema,
            logger=logger,
        )
        self.base_url = _normalize_url(base_url) if base_url else None
        self.depth = max(1, int(depth))
        self.threads = max(1, int(threads))
        self.timeout_s = max(30, int(timeout_s))
        self.photon_path = photon_path

    def _execute_impl(self, profile: Dict[str, Any]) -> Dict[str, Any]:
        target_url = self._resolve_target_url(profile)
        if not _is_valid_url(target_url):
            raise ValueError(f"Invalid target URL: {target_url}")

        self._last_result = {
            "source": "Photon",
            "input": {
                "target_url": target_url,
                "depth": self.depth,
                "threads": self.threads,
            },
        }
        self.log_result()

        output_dir = Path(tempfile.mkdtemp(prefix="photon_"))
        self._run_photon(target_url, output_dir)
        extracted = self._extract_results(output_dir, target_url)
        base_domain = _base_domain(urlsplit(target_url).netloc)
        if base_domain:
            extracted["domains"] = self._merge_unique(
                extracted["domains"], [base_domain]
            )

        digital = self._prepare_digital_section(profile)
        digital["domains"] = self._merge_unique(
            digital.get("domains", []), extracted["domains"]
        )
        digital["devices"] = self._merge_devices(
            digital.get("devices", []),
            extracted["devices"],
        )

        result = {"digital": digital}
        self._last_result = {"source": "Photon", "result": result}
        self.log_result()
        return result

    def _resolve_target_url(self, profile: Dict[str, Any]) -> str:
        if self.base_url:
            return self.base_url
        digital = profile.get("digital", {})
        domains = digital.get("domains") or []
        if domains:
            return _normalize_url(domains[0])
        raise ValueError("No target URL provided or found in profile.digital.domains")

    def _run_photon(self, url: str, output_dir: Path) -> None:
        command = self._build_photon_command()
        if not command:
            raise RuntimeError(
                "Photon executable not found. Configure PHOTON_COMMAND or PHOTON_PATH."
            )
        cmd = command + [
            "-u",
            url,
            "-l",
            str(self.depth),
            "-t",
            str(self.threads),
            "-o",
            str(output_dir),
            "-e",
            "json",
        ]
        try:
            subprocess.run(
                cmd,
                check=False,
                capture_output=True,
                text=True,
                timeout=self.timeout_s,
            )
        except subprocess.TimeoutExpired:
            self.logger.warning("Photon crawl timed out for %s", url)

    def _build_photon_command(self) -> List[str]:
        env_template = os.environ.get("PHOTON_COMMAND")
        if env_template:
            return shlex.split(env_template)

        photon_path = self.photon_path or os.environ.get("PHOTON_PATH")
        if photon_path:
            if photon_path.endswith(".py"):
                return [shutil.which("python3") or "python3", photon_path]
            return [photon_path]

        repo_path = Path(__file__).resolve().parents[2] / "Photon" / "photon.py"
        if repo_path.exists():
            return [shutil.which("python3") or "python3", str(repo_path)]

        photon_cmd = shutil.which("photon")
        if photon_cmd:
            return [photon_cmd]

        return []

    def _extract_results(
        self, output_dir: Path, base_url: str
    ) -> Dict[str, List[Any]]:
        datasets = self._load_datasets(output_dir)

        internal_urls = self._normalize_dataset_urls(
            datasets.get("internal", []), base_url
        )
        external_urls = self._normalize_dataset_urls(
            datasets.get("external", []), base_url
        )
        asset_urls = self._normalize_dataset_urls(
            datasets.get("files", []) + datasets.get("scripts", []), base_url
        )
        endpoint_urls = self._normalize_dataset_urls(
            datasets.get("endpoints", []) + datasets.get("fuzzable", []), base_url
        )

        email_hits = self._extract_emails(
            datasets.get("intel", [])
            + datasets.get("internal", [])
            + datasets.get("external", [])
        )

        internal_urls = self._dedupe_urls(internal_urls)
        external_urls = self._dedupe_urls(external_urls)
        asset_urls = [url for url in asset_urls if _is_asset(url)]
        asset_urls = self._dedupe_urls(asset_urls)
        endpoint_urls = self._dedupe_urls(endpoint_urls)
        email_hits = sorted({email.lower() for email in email_hits})

        devices: List[Dict[str, str]] = []
        devices.extend(self._build_device_entries("url_internal", internal_urls))
        devices.extend(self._build_device_entries("url_external", external_urls))
        devices.extend(self._build_device_entries("asset", asset_urls))
        devices.extend(self._build_device_entries("endpoint", endpoint_urls))
        devices.extend(self._build_device_entries("email", email_hits))

        domains = self._extract_domains(
            internal_urls + external_urls + asset_urls + endpoint_urls, email_hits
        )

        return {"devices": devices, "domains": domains}

    def _load_datasets(self, output_dir: Path) -> Dict[str, List[str]]:
        export_path = output_dir / "exported.json"
        if export_path.exists():
            try:
                with export_path.open("r", encoding="utf-8") as handle:
                    payload = json.load(handle)
                return {
                    key: [str(item) for item in value or []]
                    for key, value in payload.items()
                }
            except (OSError, json.JSONDecodeError):
                pass

        dataset_names = [
            "internal",
            "external",
            "files",
            "scripts",
            "endpoints",
            "fuzzable",
            "intel",
        ]
        datasets: Dict[str, List[str]] = {}
        for name in dataset_names:
            path = output_dir / name
            if not path.exists():
                datasets[name] = []
                continue
            try:
                datasets[name] = [
                    line.strip()
                    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines()
                    if line.strip()
                ]
            except OSError:
                datasets[name] = []
        return datasets

    def _normalize_dataset_urls(self, entries: Iterable[str], base_url: str) -> List[str]:
        urls: List[str] = []
        for entry in entries:
            if not entry:
                continue
            candidate = entry.strip()
            if _URL_PATTERN.search(candidate):
                for hit in _URL_PATTERN.findall(candidate):
                    if _is_valid_url(hit):
                        urls.append(_canonicalize_url(hit))
                continue
            if candidate.startswith("//"):
                candidate = f"https:{candidate}"
            if candidate.startswith("/"):
                candidate = urljoin(base_url, candidate)
            if candidate.startswith("./"):
                candidate = urljoin(base_url, candidate[2:])
            if _is_valid_url(candidate):
                urls.append(_canonicalize_url(candidate))
        return urls

    def _dedupe_urls(self, entries: Sequence[str]) -> List[str]:
        canonical = [_canonicalize_url(entry) for entry in entries if _is_valid_url(entry)]
        return _dedupe_hash(canonical)

    def _extract_emails(self, entries: Iterable[str]) -> List[str]:
        emails: List[str] = []
        for entry in entries:
            if not entry:
                continue
            emails.extend(_EMAIL_PATTERN.findall(entry))
        return emails

    def _extract_domains(self, urls: Sequence[str], emails: Sequence[str]) -> List[str]:
        domains: List[str] = []
        for url in urls:
            if not _is_valid_url(url):
                continue
            netloc = _base_domain(urlsplit(url).netloc)
            if netloc:
                domains.append(netloc)
        for email in emails:
            if "@" in email:
                domain = email.split("@", 1)[1].lower()
                if domain:
                    domains.append(domain)
        return _dedupe_hash(domains)

    def _build_device_entries(
        self, entry_type: str, identifiers: Sequence[str]
    ) -> List[Dict[str, str]]:
        return [
            {"type": entry_type, "identifier": identifier}
            for identifier in identifiers
            if identifier
        ]

    def _prepare_digital_section(self, profile: Dict[str, Any]) -> Dict[str, Any]:
        allowed_keys = {"ips", "domains", "devices", "exposed_ports"}
        source = profile.get("digital", {}) or {}
        digital = {}
        for key in allowed_keys:
            value = source.get(key, [])
            digital[key] = value if isinstance(value, list) else []
        digital.setdefault("ips", [])
        digital.setdefault("domains", [])
        digital.setdefault("devices", [])
        digital.setdefault("exposed_ports", [])
        return digital

    def _merge_unique(self, existing: Sequence[str], incoming: Iterable[str]) -> List[str]:
        seen = {entry for entry in existing}
        merged = list(existing)
        for entry in incoming:
            if entry not in seen:
                seen.add(entry)
                merged.append(entry)
        return merged


class ResearchWebCrawlingPhoton(Research_Web_Crawling_Photon):
    """Backwards-compatible alias for module discovery."""

    def _merge_devices(
        self, existing: Sequence[Dict[str, Any]], incoming: Iterable[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        merged = [dict(item) for item in existing]
        seen: set[str] = set()
        for item in merged:
            fingerprint = f"{item.get('type','')}::{item.get('identifier','')}"
            seen.add(hashlib.sha1(fingerprint.encode("utf-8")).hexdigest())
        for item in incoming:
            fingerprint = f"{item.get('type','')}::{item.get('identifier','')}"
            digest = hashlib.sha1(fingerprint.encode("utf-8")).hexdigest()
            if digest in seen:
                continue
            seen.add(digest)
            merged.append(dict(item))
        return merged
