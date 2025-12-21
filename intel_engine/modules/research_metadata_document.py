"""
Research_Metadata_Document_Extraction

Data Source:
  - Metagoofil (https://github.com/laramies/metagoofil) for public document
    discovery and metadata extraction.

Purpose:
  - Discover attribution clues (authors, emails, software, creation dates)
    from publicly exposed documents tied to a target domain.
"""

from __future__ import annotations

import html
import json
import logging
import os
import re
import shutil
import subprocess
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple
from xml.etree import ElementTree

from intel_engine.core.module_base import IntelModuleBase

_ALLOWED_FILE_TYPES = ("pdf", "docx", "xls")
_DEFAULT_FILE_TYPES = ("pdf", "docx", "xls")
_DEFAULT_SEARCH_LIMIT = 200
_DEFAULT_FILE_LIMIT = 50

_CREATION_DATE_RE = re.compile(
    rb"/CreationDate\s*\(D:(\d{4})(\d{2})(\d{2})(\d{0,2})(\d{0,2})(\d{0,2})"
)


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


def _build_schemas(
    profile_schema: Dict[str, Any]
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    digital_schema = profile_schema.get("properties", {}).get("digital")
    metadata_schema = profile_schema.get("properties", {}).get("metadata")
    if not digital_schema or not metadata_schema:
        raise ValueError("profile_schema.json is missing digital or metadata schema.")

    input_schema = {
        "type": "object",
        "required": ["digital", "metadata"],
        "properties": {
            "digital": digital_schema,
            "metadata": metadata_schema,
        },
    }

    output_schema = {
        "type": "object",
        "required": ["digital"],
        "properties": {"digital": digital_schema},
    }

    return input_schema, output_schema


def _select_python_interpreter() -> str:
    for candidate in ("python2", "python2.7", "python"):
        resolved = shutil.which(candidate)
        if resolved:
            return resolved
    raise FileNotFoundError("Unable to locate a Python interpreter.")


def _find_metagoofil_root() -> Path:
    candidate_paths = [
        Path(__file__).resolve().parents[2] / "metagoofil",
        Path(__file__).resolve().parents[3] / "metagoofil",
        Path.cwd() / "metagoofil",
    ]
    for path in candidate_paths:
        if (path / "metagoofil.py").exists():
            return path
    raise FileNotFoundError("Unable to locate metagoofil repository root.")


def _extract_list_items(html_text: str, class_name: str) -> List[str]:
    list_block = re.search(
        rf"<ul[^>]*class=[\"']{re.escape(class_name)}[\"'][^>]*>(.*?)</ul>",
        html_text,
        re.DOTALL | re.IGNORECASE,
    )
    if not list_block:
        return []
    items = re.findall(r"<li[^>]*>(.*?)</li>", list_block.group(1), re.DOTALL)
    cleaned = []
    for item in items:
        text = html.unescape(re.sub(r"<[^>]+>", "", item)).strip()
        if text:
            cleaned.append(text)
    return cleaned


def _unique(values: Iterable[str]) -> List[str]:
    seen = set()
    result = []
    for value in values:
        cleaned = value.strip()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        result.append(cleaned)
    return result


def _parse_pdf_creation_date(path: Path) -> Optional[str]:
    try:
        payload = path.read_bytes()
    except OSError:
        return None
    match = _CREATION_DATE_RE.search(payload)
    if not match:
        return None
    parts = match.groups()
    year, month, day = (int(parts[0]), int(parts[1]), int(parts[2]))
    hour = int(parts[3]) if parts[3] else 0
    minute = int(parts[4]) if parts[4] else 0
    second = int(parts[5]) if parts[5] else 0
    try:
        return datetime(year, month, day, hour, minute, second).isoformat()
    except ValueError:
        return None


def _parse_office_creation_date(path: Path) -> Optional[str]:
    try:
        with zipfile.ZipFile(path) as handle:
            with handle.open("docProps/core.xml") as core_handle:
                tree = ElementTree.parse(core_handle)
    except (KeyError, OSError, zipfile.BadZipFile, ElementTree.ParseError):
        return None

    for tag in (
        "{http://purl.org/dc/terms/}created",
        "{http://purl.org/dc/terms/}modified",
    ):
        element = tree.find(f".//{tag}")
        if element is not None and element.text:
            return element.text.strip()
    return None


def _extract_creation_date(path: Path) -> Optional[str]:
    suffix = path.suffix.lower().lstrip(".")
    if suffix == "pdf":
        return _parse_pdf_creation_date(path)
    if suffix in {"docx", "xlsx", "pptx"}:
        return _parse_office_creation_date(path)
    if suffix == "xls":
        return _parse_office_creation_date(path)
    return None


def _normalize_file_types(
    requested: Sequence[str],
) -> List[str]:
    cleaned = []
    for value in requested:
        lowered = value.strip().lower()
        if lowered and lowered in _ALLOWED_FILE_TYPES:
            cleaned.append(lowered)
    return _unique(cleaned) or list(_DEFAULT_FILE_TYPES)


class Research_Metadata_Document_Extraction(IntelModuleBase):
    def __init__(self, logger: Optional[logging.Logger] = None) -> None:
        profile_schema = _load_profile_schema()
        input_schema, output_schema = _build_schemas(profile_schema)
        super().__init__(
            module_name="Research_Metadata_Document_Extraction",
            profile_schema=input_schema,
            output_schema=output_schema,
            logger=logger,
        )

    def _execute_impl(self, profile: Dict[str, Any]) -> Dict[str, Any]:
        digital = profile.get("digital", {})
        metadata = profile.get("metadata", {})
        domains = digital.get("domains") or []
        if not domains:
            raise ValueError("No target domains supplied in profile.digital.domains.")

        target_domain = domains[0].strip()
        document_types = _normalize_file_types(
            [doc.get("type", "") for doc in metadata.get("documents", [])]
        )

        self._last_result = {
            "source": "Metagoofil",
            "input": {
                "target_domain": target_domain,
                "document_types": document_types,
                "search_limit": _DEFAULT_SEARCH_LIMIT,
                "file_limit": _DEFAULT_FILE_LIMIT,
            },
        }
        self.log_result()

        metagoofil_root = _find_metagoofil_root()
        python_exec = _select_python_interpreter()

        with tempfile.TemporaryDirectory(prefix="metagoofil_") as temp_dir:
            output_dir = Path(temp_dir) / "downloads"
            output_dir.mkdir(parents=True, exist_ok=True)
            output_html = Path(temp_dir) / "results.html"

            command = [
                python_exec,
                str(metagoofil_root / "metagoofil.py"),
                "-d",
                target_domain,
                "-t",
                ",".join(document_types),
                "-l",
                str(_DEFAULT_SEARCH_LIMIT),
                "-n",
                str(_DEFAULT_FILE_LIMIT),
                "-o",
                str(output_dir),
                "-f",
                str(output_html),
            ]

            self.logger.info(
                "Running Metagoofil for domain %s with types %s",
                target_domain,
                ", ".join(document_types),
            )

            result = subprocess.run(
                command,
                cwd=str(metagoofil_root),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                check=False,
            )

            if result.returncode != 0:
                raise RuntimeError(
                    "Metagoofil execution failed: " + (result.stdout or "").strip()
                )

            html_text = ""
            if output_html.exists():
                html_text = output_html.read_text(encoding="utf-8", errors="ignore")

            authors = _unique(_extract_list_items(html_text, "userslist"))
            software = _unique(_extract_list_items(html_text, "softlist"))
            emails = _unique(_extract_list_items(html_text, "emailslist"))

            document_metadata = []
            for file_path in output_dir.glob("**/*"):
                if not file_path.is_file():
                    continue
                creation_date = _extract_creation_date(file_path)
                document_metadata.append(
                    {
                        "name": file_path.name,
                        "created": creation_date,
                        "location": str(file_path),
                    }
                )

            device_entries = []
            for author in authors:
                device_entries.append(
                    {
                        "type": "document_metadata_author",
                        "identifier": f"{author} (source: metagoofil)",
                    }
                )
            for email in emails:
                device_entries.append(
                    {
                        "type": "document_metadata_email",
                        "identifier": f"{email} (source: metagoofil)",
                    }
                )
            for product in software:
                device_entries.append(
                    {
                        "type": "document_metadata_software",
                        "os": product,
                        "identifier": f"{product} (source: metagoofil)",
                    }
                )
            for doc in document_metadata:
                identifier = doc["name"]
                created_value = doc.get("created")
                if created_value:
                    identifier = f"{identifier} created {created_value}"
                entry = {
                    "type": "document_metadata_document",
                    "identifier": f"{identifier} (source: metagoofil)",
                }
                if created_value:
                    entry["last_seen"] = created_value
                device_entries.append(entry)

            merged_devices = list(digital.get("devices") or [])
            merged_devices.extend(device_entries)

            output_digital = {
                "ips": list(digital.get("ips") or []),
                "domains": _unique(list(domains) + [target_domain]),
                "devices": merged_devices,
                "exposed_ports": list(digital.get("exposed_ports") or []),
            }

        result = {"digital": output_digital}
        self._last_result = {"source": "Metagoofil", "result": result}
        self.log_result()
        return result
