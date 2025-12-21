"""
Research_Framework_ReconNG Module

Integrates the Recon-ng framework into the intelligence engine with a structured
workflow: initialize a workspace, execute selected Recon-ng modules, parse the
workspace database, and deliver correlated intelligence output for analysts.
"""

from __future__ import annotations

import json
import logging
import re
import shutil
import sqlite3
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from intel_engine.core.module_base import IntelModuleBase

_EMAIL_PATTERN = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_DOMAIN_PATTERN = re.compile(r"\b(?:[A-Za-z0-9-]+\.)+[A-Za-z]{2,}\b")

_DEFAULT_SELECTION = ("whois", "breach", "contacts")
_DEFAULT_MODULES = {
    "whois": {
        "domain": ("recon/domains-contacts/whois_pocs", "SOURCE"),
        "company": ("recon/companies-contacts/whois_pocs", "SOURCE"),
        "contact": ("recon/contacts-contacts/whois_pocs", "SOURCE"),
    },
    "breach": {
        "domain": ("recon/domains-credentials/hibp_breach", "SOURCE"),
        "company": ("recon/companies-credentials/hibp_breach", "SOURCE"),
        "contact": ("recon/contacts-credentials/hibp_breach", "SOURCE"),
    },
    "contacts": {
        "domain": ("recon/domains-contacts/whois_pocs", "SOURCE"),
        "company": ("recon/companies-contacts/companies_contacts", "SOURCE"),
        "contact": ("recon/contacts-contacts/mangle", "SOURCE"),
    },
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


def _build_intelligence_output_schema(
    profile_schema: Dict[str, Any]
) -> Dict[str, Any]:
    intelligence_schema = (
        profile_schema.get("properties", {}).get("intelligence")
        if profile_schema
        else None
    )
    if intelligence_schema:
        return {
            "type": "object",
            "required": ["intelligence"],
            "properties": {"intelligence": intelligence_schema},
        }
    return {
        "type": "object",
        "required": ["intelligence"],
        "properties": {
            "intelligence": {
                "type": "object",
                "required": ["reconng"],
                "properties": {
                    "reconng": {
                        "type": "object",
                        "required": [
                            "workspace",
                            "target",
                            "modules_requested",
                            "modules_run",
                            "records",
                            "correlations",
                            "anomalies",
                            "confidence_summary",
                            "execution",
                        ],
                        "properties": {
                            "workspace": {"type": "string"},
                            "target": {
                                "type": "object",
                                "required": ["type", "value"],
                                "properties": {
                                    "type": {"type": "string"},
                                    "value": {"type": "string"},
                                },
                            },
                            "modules_requested": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                            "modules_run": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "required": ["category", "module", "status"],
                                    "properties": {
                                        "category": {"type": "string"},
                                        "module": {"type": "string"},
                                        "status": {"type": "string"},
                                        "option": {"type": "string"},
                                        "details": {"type": "string"},
                                    },
                                },
                            },
                            "records": {
                                "type": "object",
                                "properties": {
                                    "domains": {
                                        "type": "array",
                                        "items": {"type": "object"},
                                    },
                                    "companies": {
                                        "type": "array",
                                        "items": {"type": "object"},
                                    },
                                    "contacts": {
                                        "type": "array",
                                        "items": {"type": "object"},
                                    },
                                    "credentials": {
                                        "type": "array",
                                        "items": {"type": "object"},
                                    },
                                    "breaches": {
                                        "type": "array",
                                        "items": {"type": "object"},
                                    },
                                    "hosts": {
                                        "type": "array",
                                        "items": {"type": "object"},
                                    },
                                },
                            },
                            "correlations": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "required": [
                                        "left",
                                        "right",
                                        "reason",
                                        "confidence",
                                    ],
                                    "properties": {
                                        "left": {"type": "string"},
                                        "right": {"type": "string"},
                                        "reason": {"type": "string"},
                                        "confidence": {"type": "number"},
                                    },
                                },
                            },
                            "anomalies": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "required": ["signal", "severity", "details"],
                                    "properties": {
                                        "signal": {"type": "string"},
                                        "severity": {"type": "string"},
                                        "details": {"type": "string"},
                                    },
                                },
                            },
                            "confidence_summary": {
                                "type": "object",
                                "required": ["min", "max", "average"],
                                "properties": {
                                    "min": {"type": "number"},
                                    "max": {"type": "number"},
                                    "average": {"type": "number"},
                                },
                            },
                            "execution": {
                                "type": "object",
                                "required": ["return_code", "stdout", "stderr"],
                                "properties": {
                                    "return_code": {"type": "integer"},
                                    "stdout": {"type": "string"},
                                    "stderr": {"type": "string"},
                                },
                            },
                        },
                    }
                },
            }
        },
    }


def _truncate(text: str, limit: int = 4000) -> str:
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "..."


def _normalize_target_type(target_type: str) -> str:
    cleaned = str(target_type).strip().lower()
    if cleaned not in {"domain", "company", "contact"}:
        raise ValueError(f"Unsupported target_type '{target_type}'.")
    return cleaned


def _quote_reconng(value: str) -> str:
    if not value:
        return "\"\""
    escaped = value.replace("\\", "\\\\").replace("\"", "\\\"")
    if re.search(r"\s", escaped):
        return f"\"{escaped}\""
    return escaped


def _dedupe_records(records: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = set()
    deduped: List[Dict[str, Any]] = []
    for record in records:
        key = json.dumps(record, sort_keys=True, default=str)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(record)
    return deduped


def _extract_emails(records: Iterable[Dict[str, Any]]) -> List[str]:
    emails: List[str] = []
    for record in records:
        for value in record.values():
            if isinstance(value, str) and _EMAIL_PATTERN.fullmatch(value.strip()):
                emails.append(value.strip().lower())
    return sorted(set(emails))


def _extract_domains(records: Iterable[Dict[str, Any]]) -> List[str]:
    domains: List[str] = []
    for record in records:
        for value in record.values():
            if isinstance(value, str) and _DOMAIN_PATTERN.fullmatch(value.strip()):
                domains.append(value.strip().lower())
    return sorted(set(domains))


def _resolve_default_reconng_root() -> Path:
    return Path(__file__).resolve().parents[2] / "vendor" / "recon-ng"


class Research_Framework_ReconNG(IntelModuleBase):
    """Run Recon-ng modules, parse workspace data, and enrich intelligence output."""

    MODULE_NAME = "Research_Framework_ReconNG"

    def __init__(
        self,
        workspace_name: str,
        target: str,
        target_type: str = "domain",
        module_selection: Optional[Iterable[Any]] = None,
        reconng_root: Optional[Path] = None,
        reconng_path: Optional[str] = None,
        workspace_root: Optional[Path] = None,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        profile_schema = _load_profile_schema()
        output_schema = _build_intelligence_output_schema(profile_schema)
        super().__init__(
            module_name=self.MODULE_NAME,
            profile_schema=profile_schema,
            output_schema=output_schema,
            logger=logger,
        )
        if not workspace_name:
            raise ValueError("workspace_name is required.")
        if not target:
            raise ValueError("target is required.")
        self.workspace_name = workspace_name.strip()
        self.target = target.strip()
        self.target_type = _normalize_target_type(target_type)
        self.module_selection = self._normalize_module_selection(module_selection)
        self.reconng_root = (
            Path(reconng_root).expanduser()
            if reconng_root
            else _resolve_default_reconng_root()
        )
        self.reconng_path = reconng_path
        self.workspace_root = (
            Path(workspace_root).expanduser()
            if workspace_root
            else Path.home() / ".recon-ng" / "workspaces"
        )

    def validate_input(self) -> None:
        super().validate_input()
        if not self.workspace_name:
            raise ValueError("workspace_name cannot be empty.")
        if not self.target:
            raise ValueError("target cannot be empty.")

    def _execute_impl(self, profile: Dict[str, Any]) -> Dict[str, Any]:
        reconng_path = self._resolve_reconng_path()
        self._initialize_workspace(reconng_path)
        self._seed_target(reconng_path)

        self._last_result = {
            "input": {
                "workspace": self.workspace_name,
                "target": {"type": self.target_type, "value": self.target},
                "module_selection": self.module_selection,
            }
        }
        self.log_result()

        module_runs: List[Dict[str, Any]] = []
        last_exec = {"return_code": 0, "stdout": "", "stderr": ""}
        for module_spec in self.module_selection:
            run_info = self._run_module(reconng_path, module_spec)
            module_runs.append(run_info)
            last_exec = {
                "return_code": run_info.get("return_code", 0),
                "stdout": run_info.get("stdout", ""),
                "stderr": run_info.get("stderr", ""),
            }

        workspace_db = self._resolve_workspace_db()
        if not workspace_db:
            raise FileNotFoundError(
                "Recon-ng workspace database not found after execution."
            )

        records = self._load_workspace_records(workspace_db)
        deduped_records = {
            table: _dedupe_records(rows) for table, rows in records.items()
        }
        correlations = self._build_correlations(deduped_records)
        anomalies = self._flag_anomalies(deduped_records, correlations)
        confidence_summary = self._summarize_confidence(correlations)

        intelligence = {
            "reconng": {
                "workspace": self.workspace_name,
                "target": {"type": self.target_type, "value": self.target},
                "modules_requested": [spec["category"] for spec in self.module_selection],
                "modules_run": [
                    {
                        "category": spec["category"],
                        "module": spec["module"],
                        "status": spec["status"],
                        "option": spec.get("option", ""),
                        "details": spec.get("details", ""),
                    }
                    for spec in module_runs
                ],
                "records": deduped_records,
                "correlations": correlations,
                "anomalies": anomalies,
                "confidence_summary": confidence_summary,
                "execution": {
                    "return_code": int(last_exec.get("return_code", 0)),
                    "stdout": _truncate(last_exec.get("stdout", "")),
                    "stderr": _truncate(last_exec.get("stderr", "")),
                },
            }
        }

        profile["intelligence"] = intelligence
        return {"intelligence": intelligence}

    def _resolve_reconng_path(self) -> str:
        if self.reconng_path:
            return self.reconng_path
        candidate = self.reconng_root / "recon-ng"
        if candidate.exists():
            return str(candidate)
        resolved = shutil.which("recon-ng")
        if not resolved:
            raise FileNotFoundError(
                "recon-ng binary not found; clone the repo or update PATH."
            )
        return resolved

    def _normalize_module_selection(
        self, module_selection: Optional[Iterable[Any]]
    ) -> List[Dict[str, str]]:
        selection = list(module_selection) if module_selection else list(_DEFAULT_SELECTION)
        normalized: List[Dict[str, str]] = []

        for entry in selection:
            if isinstance(entry, dict):
                module = str(entry.get("module", "")).strip()
                if not module:
                    raise ValueError("Module selection entries must include 'module'.")
                normalized.append(
                    {
                        "category": str(entry.get("category", module)),
                        "module": module,
                        "option": str(entry.get("option", "SOURCE")),
                        "option_value": str(entry.get("option_value", self.target)),
                    }
                )
                continue

            token = str(entry).strip()
            if not token:
                continue
            lowered = token.lower()
            if lowered in _DEFAULT_MODULES:
                module, option = _DEFAULT_MODULES[lowered].get(
                    self.target_type, _DEFAULT_MODULES[lowered]["domain"]
                )
                normalized.append(
                    {
                        "category": lowered,
                        "module": module,
                        "option": option,
                        "option_value": self.target,
                    }
                )
            else:
                normalized.append(
                    {
                        "category": "custom",
                        "module": token,
                        "option": "SOURCE",
                        "option_value": self.target,
                    }
                )

        if not normalized:
            raise ValueError("No recon-ng modules selected for execution.")
        return normalized

    def _initialize_workspace(self, reconng_path: str) -> None:
        self.workspace_root.mkdir(parents=True, exist_ok=True)
        select_commands = [
            f"workspaces select {_quote_reconng(self.workspace_name)}",
            "exit",
        ]
        _, _, return_code = self._run_reconng_script(
            reconng_path, select_commands
        )
        if return_code == 0:
            return

        create_commands = [
            f"workspaces add {_quote_reconng(self.workspace_name)}",
            f"workspaces select {_quote_reconng(self.workspace_name)}",
            "exit",
        ]
        self._run_reconng_script(reconng_path, create_commands)

    def _seed_target(self, reconng_path: str) -> None:
        insert_command = self._build_target_insert()
        commands = [
            f"workspaces select {_quote_reconng(self.workspace_name)}",
            insert_command,
            "exit",
        ]
        self._run_reconng_script(reconng_path, commands)

    def _build_target_insert(self) -> str:
        target_value = _quote_reconng(self.target)
        if self.target_type == "domain":
            return f"add domains {target_value}"
        if self.target_type == "company":
            return f"add companies {target_value}"
        return f"add contacts {target_value}"

    def _run_module(
        self, reconng_path: str, module_spec: Dict[str, str]
    ) -> Dict[str, Any]:
        module_name = module_spec["module"]
        option_key = module_spec.get("option", "SOURCE")
        option_value = module_spec.get("option_value", self.target)
        commands = [
            f"workspaces select {_quote_reconng(self.workspace_name)}",
            f"modules load {module_name}",
            f"options set {option_key} {_quote_reconng(option_value)}",
            "run",
            "exit",
        ]
        stdout, stderr, return_code = self._run_reconng_script(
            reconng_path, commands
        )
        status = "success" if return_code == 0 else "error"
        details = stderr.strip() or stdout.strip()
        return {
            "category": module_spec["category"],
            "module": module_name,
            "status": status,
            "option": option_key,
            "details": _truncate(details),
            "stdout": stdout,
            "stderr": stderr,
            "return_code": return_code,
        }

    def _run_reconng_script(
        self, reconng_path: str, commands: Iterable[str]
    ) -> Tuple[str, str, int]:
        script_body = "\n".join(commands) + "\n"
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".rc", delete=False, encoding="utf-8"
        ) as handle:
            handle.write(script_body)
            script_path = handle.name

        try:
            cwd = str(self.reconng_root) if self.reconng_root.exists() else None
            process = subprocess.run(
                [reconng_path, "-r", script_path],
                capture_output=True,
                text=True,
                check=False,
                cwd=cwd,
            )
            return process.stdout or "", process.stderr or "", process.returncode
        finally:
            Path(script_path).unlink(missing_ok=True)

    def _resolve_workspace_db(self) -> Optional[Path]:
        candidates = [
            self.workspace_root / self.workspace_name / "data.db",
            Path.home()
            / ".recon-ng"
            / "workspaces"
            / self.workspace_name
            / "data.db",
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate

        workspace_dir = self.workspace_root / self.workspace_name
        if workspace_dir.exists():
            for path in workspace_dir.rglob("data.db"):
                return path
        return None

    def _load_workspace_records(self, db_path: Path) -> Dict[str, List[Dict[str, Any]]]:
        tables_of_interest = {
            "domains",
            "companies",
            "contacts",
            "credentials",
            "breaches",
            "hosts",
        }
        records: Dict[str, List[Dict[str, Any]]] = {table: [] for table in tables_of_interest}
        conn = sqlite3.connect(str(db_path))
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            table_names = {row[0] for row in cursor.fetchall()}
            for table in tables_of_interest:
                if table not in table_names:
                    continue
                cursor.execute(f"PRAGMA table_info({table})")
                columns = [row[1] for row in cursor.fetchall()]
                if not columns:
                    continue
                cursor.execute(f"SELECT * FROM {table}")
                rows = cursor.fetchall()
                records[table] = [
                    {columns[idx]: value for idx, value in enumerate(row)}
                    for row in rows
                ]
        finally:
            conn.close()
        return records

    def _build_correlations(
        self, records: Dict[str, List[Dict[str, Any]]]
    ) -> List[Dict[str, Any]]:
        domains = _extract_domains(records.get("domains", []))
        contacts = records.get("contacts", [])
        emails = _extract_emails(contacts)
        credentials = records.get("credentials", [])
        breaches = records.get("breaches", [])

        correlations: List[Dict[str, Any]] = []
        for email in emails:
            email_domain = email.split("@")[-1]
            for domain in domains:
                if email_domain == domain or email_domain.endswith(f".{domain}"):
                    confidence = self._score_confidence(email, domain)
                    correlations.append(
                        {
                            "left": email,
                            "right": domain,
                            "reason": "contact email domain matches discovered domain",
                            "confidence": confidence,
                        }
                    )

        for record in credentials + breaches:
            for value in record.values():
                if isinstance(value, str) and _EMAIL_PATTERN.fullmatch(value.strip()):
                    confidence = self._score_confidence(value, self.target)
                    correlations.append(
                        {
                            "left": value.strip().lower(),
                            "right": self.target,
                            "reason": "credential/breach entry matches contact email",
                            "confidence": confidence,
                        }
                    )
        return correlations

    def _score_confidence(self, left: str, right: str) -> float:
        score = 0.4
        if self.target_type == "domain":
            if right.lower().endswith(self.target.lower()):
                score += 0.3
            if "@" in left and left.split("@")[-1].endswith(self.target.lower()):
                score += 0.3
        if self.target_type == "company":
            if self.target.lower() in left.lower() or self.target.lower() in right.lower():
                score += 0.3
        if self.target_type == "contact":
            if self.target.lower() in left.lower() or self.target.lower() in right.lower():
                score += 0.2
        return min(score, 1.0)

    def _flag_anomalies(
        self,
        records: Dict[str, List[Dict[str, Any]]],
        correlations: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        anomalies: List[Dict[str, Any]] = []
        breaches = records.get("breaches") or []
        credentials = records.get("credentials") or []

        if breaches:
            anomalies.append(
                {
                    "signal": "breach_exposure",
                    "severity": "high",
                    "details": f"{len(breaches)} breach records identified.",
                }
            )
        if credentials:
            anomalies.append(
                {
                    "signal": "credential_exposure",
                    "severity": "high",
                    "details": f"{len(credentials)} credential records identified.",
                }
            )

        if self.target_type == "domain":
            emails = _extract_emails(records.get("contacts", []))
            off_domain = [
                email
                for email in emails
                if not email.endswith(f"@{self.target.lower()}")
            ]
            if off_domain:
                anomalies.append(
                    {
                        "signal": "off_domain_contacts",
                        "severity": "medium",
                        "details": f"{len(off_domain)} contacts use non-target domains.",
                    }
                )

        if not correlations:
            anomalies.append(
                {
                    "signal": "low_correlation",
                    "severity": "low",
                    "details": "No strong cross-module correlations detected.",
                }
            )
        return anomalies

    def _summarize_confidence(
        self, correlations: List[Dict[str, Any]]
    ) -> Dict[str, float]:
        if not correlations:
            return {"min": 0.0, "max": 0.0, "average": 0.0}
        scores = [float(entry["confidence"]) for entry in correlations]
        return {
            "min": min(scores),
            "max": max(scores),
            "average": sum(scores) / len(scores),
        }
