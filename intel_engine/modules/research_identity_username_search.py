"""
Research_Identity_Username_Search

Data Source:
  - Uses the Sherlock open-source dataset of username patterns and checks
    (https://github.com/sherlock-project/sherlock).

Purpose:
  - Expands identity coverage by probing a normalized username across social,
    forum, and service platforms and normalizing results into profile['social'].
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit, urlunsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from intel_engine.core.module_base import IntelModuleBase

_USER_AGENT = (
    "Mozilla/5.0 (compatible; IntelEngine/1.0; "
    "+https://github.com/sherlock-project/sherlock)"
)
_DEFAULT_TIMEOUT = 12
_MAX_BODY_BYTES = 200_000

_AVATAR_META_PATTERN = re.compile(
    r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
    re.IGNORECASE,
)
_IMAGE_SRC_PATTERN = re.compile(
    r'<link[^>]+rel=["\']image_src["\'][^>]+href=["\']([^"\']+)["\']',
    re.IGNORECASE,
)

_ACTIVITY_KEYWORDS = (
    "last active",
    "joined",
    "posts",
    "followers",
    "following",
    "recent",
    "activity",
)
_COMPLETENESS_KEYWORDS = (
    "bio",
    "about",
    "profile",
    "location",
    "website",
    "avatar",
)

_FORUM_HINTS = (
    "forum",
    "forums",
    "discussions",
    "discussion",
    "boards",
    "board",
    "community",
    "bbs",
)
_SOCIAL_HINTS = (
    "twitter",
    "instagram",
    "facebook",
    "tiktok",
    "linkedin",
    "youtube",
    "pinterest",
    "snapchat",
    "reddit",
    "mastodon",
    "threads",
    "bluesky",
    "tumblr",
    "weibo",
    "vk",
    "discord",
)


class _NoRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _load_profile_schema() -> Dict[str, Any]:
    candidate_paths = [
        Path(__file__).resolve().parents[1] / "schemas" / "profile_schema.json",
        Path(__file__).resolve().parents[2] / "schemas" / "profile_schema.json",
        Path(__file__).resolve().parents[2] / "profile_schema.json",
    ]
    schema_payload: Optional[Dict[str, Any]] = None
    for path in candidate_paths:
        if path.exists():
            with path.open("r", encoding="utf-8") as handle:
                schema_payload = json.load(handle)
            break
    if not schema_payload:
        raise FileNotFoundError(
            "Unable to locate schemas/profile_schema.json for validation."
        )
    return schema_payload


def _build_input_schema(schema_payload: Dict[str, Any]) -> Dict[str, Any]:
    contact_schema = schema_payload.get("properties", {}).get("contact")
    identity_schema = schema_payload.get("properties", {}).get("identity")
    return {
        "type": "object",
        "properties": {
            **({"contact": contact_schema} if contact_schema else {}),
            **({"identity": identity_schema} if identity_schema else {}),
        },
    }


def _build_social_output_schema(schema_payload: Dict[str, Any]) -> Dict[str, Any]:
    social_schema = schema_payload.get("properties", {}).get("social")
    if not social_schema:
        raise ValueError("profile_schema.json does not define a social section.")
    return {
        "type": "object",
        "required": ["social"],
        "properties": {"social": social_schema},
    }


def _load_sherlock_data() -> Dict[str, Any]:
    candidate_paths = [
        Path(__file__).resolve().parents[2]
        / "sherlock"
        / "sherlock_project"
        / "resources"
        / "data.json",
        Path(__file__).resolve().parents[1]
        / "sherlock"
        / "sherlock_project"
        / "resources"
        / "data.json",
    ]
    data_payload: Optional[Dict[str, Any]] = None
    for path in candidate_paths:
        if path.exists():
            with path.open("r", encoding="utf-8") as handle:
                data_payload = json.load(handle)
            break
    if not data_payload:
        raise FileNotFoundError(
            "Unable to locate sherlock_project/resources/data.json."
        )
    data_payload.pop("$schema", None)
    return data_payload


def _normalize_username(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    cleaned = value.strip().lstrip("@")
    cleaned = re.sub(r"[^A-Za-z0-9_.-]", "", cleaned)
    return cleaned or None


def _extract_usernames(profile: Dict[str, Any]) -> List[str]:
    candidates: List[str] = []
    contact = profile.get("contact", {}) if isinstance(profile, dict) else {}
    for entry in contact.get("usernames", []) or []:
        normalized = _normalize_username(str(entry))
        if normalized:
            candidates.append(normalized)
    identity = profile.get("identity", {}) if isinstance(profile, dict) else {}
    for entry in identity.get("aliases", []) or []:
        normalized = _normalize_username(str(entry))
        if normalized:
            candidates.append(normalized)
    return sorted(set(candidates))


def _interpolate_string(value: str, username: str) -> str:
    return value.replace("{}", username)


def _interpolate_payload(payload: Any, username: str) -> Any:
    if isinstance(payload, dict):
        return {key: _interpolate_payload(val, username) for key, val in payload.items()}
    if isinstance(payload, list):
        return [_interpolate_payload(val, username) for val in payload]
    if isinstance(payload, str):
        return _interpolate_string(payload, username)
    return payload


def _canonicalize_url(url: str) -> str:
    parts = urlsplit(url)
    scheme = (parts.scheme or "https").lower()
    netloc = parts.netloc.lower()
    path = parts.path.rstrip("/")
    return urlunsplit((scheme, netloc, path, parts.query, ""))


def _hash_url(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()


def _extract_avatar(html: str) -> Optional[str]:
    if not html:
        return None
    match = _AVATAR_META_PATTERN.search(html)
    if match:
        return match.group(1)
    match = _IMAGE_SRC_PATTERN.search(html)
    if match:
        return match.group(1)
    return None


def _score_keyword_hits(text: str, keywords: Sequence[str], max_score: int) -> float:
    if not text:
        return 0.0
    lowered = text.lower()
    hits = sum(1 for keyword in keywords if keyword in lowered)
    return min(1.0, hits / max_score) if max_score else 0.0


def _classify_platform(name: str, url_main: str, tags: Any) -> str:
    combined = f"{name} {url_main}".lower()
    if any(hint in combined for hint in _FORUM_HINTS):
        return "forum"
    if any(hint in combined for hint in _SOCIAL_HINTS):
        return "social"
    if isinstance(tags, (list, tuple)):
        tags = " ".join(str(tag) for tag in tags)
    if isinstance(tags, str) and "forum" in tags.lower():
        return "forum"
    return "service"


def _build_headers(extra_headers: Optional[Dict[str, Any]], username: str) -> Dict[str, str]:
    headers = {"User-Agent": _USER_AGENT}
    if extra_headers and isinstance(extra_headers, dict):
        for key, value in extra_headers.items():
            if value is None:
                continue
            if isinstance(value, str):
                headers[str(key)] = _interpolate_string(value, username)
            else:
                headers[str(key)] = str(value)
    return headers


def _fetch_url(
    url: str,
    method: str,
    headers: Dict[str, str],
    payload: Optional[Dict[str, Any]],
    timeout: int,
    allow_redirects: bool,
    require_body: bool,
) -> Tuple[Optional[int], str, str]:
    data_bytes = None
    if payload is not None:
        data_bytes = json.dumps(payload).encode("utf-8")
        headers = {**headers, "Content-Type": "application/json"}
    request = Request(url, data=data_bytes, headers=headers, method=method)
    opener = build_opener() if allow_redirects else build_opener(_NoRedirectHandler())
    try:
        response = opener.open(request, timeout=timeout)
        status = response.getcode()
        final_url = response.geturl()
        if require_body:
            body_bytes = response.read(_MAX_BODY_BYTES)
            body_text = body_bytes.decode("utf-8", errors="ignore")
        else:
            body_text = ""
        return status, body_text, final_url
    except HTTPError as error:
        try:
            body_bytes = error.read(_MAX_BODY_BYTES) if require_body else b""
            body_text = body_bytes.decode("utf-8", errors="ignore")
        except Exception:
            body_text = ""
        return error.code, body_text, error.geturl()
    except (URLError, ValueError):
        return None, "", url


PROFILE_SCHEMA_PAYLOAD = _load_profile_schema()
SHERLOCK_DATA = _load_sherlock_data()


class Research_Identity_Username_Search(IntelModuleBase):
    """Search for a username across Sherlock platforms and normalize social hits."""

    MODULE_NAME = "Research_Identity_Username_Search"
    INPUT_SCHEMA = _build_input_schema(PROFILE_SCHEMA_PAYLOAD)
    OUTPUT_SCHEMA = _build_social_output_schema(PROFILE_SCHEMA_PAYLOAD)

    def __init__(self, timeout_s: int = _DEFAULT_TIMEOUT, logger: Optional[logging.Logger] = None) -> None:
        super().__init__(
            module_name=self.MODULE_NAME,
            profile_schema=self.INPUT_SCHEMA,
            output_schema=self.OUTPUT_SCHEMA,
            logger=logger,
        )
        self.timeout_s = max(3, int(timeout_s))

    def validate_input(self) -> None:
        super().validate_input()
        profile = self._current_profile or {}
        if not _extract_usernames(profile):
            raise ValueError(
                "Research_Identity_Username_Search requires at least one username."
            )

    def _execute_impl(self, profile: Dict[str, Any]) -> Dict[str, Any]:
        usernames = _extract_usernames(profile)
        social_section = self._prepare_social_section(profile)

        seen_hashes = {
            _hash_url(_canonicalize_url(url))
            for url in social_section.get("profile_links", [])
        }

        for username in usernames:
            for platform_name, platform in SHERLOCK_DATA.items():
                result = self._probe_platform(username, platform_name, platform)
                if not result:
                    continue
                canonical_url = result["canonical_url"]
                url_hash = _hash_url(canonical_url)
                if url_hash in seen_hashes:
                    continue
                seen_hashes.add(url_hash)

                social_section["platforms"].add(result["platform"])
                social_section["profile_links"].add(canonical_url)
                social_section["last_activity"].append(
                    {
                        "platform": result["platform"],
                        "timestamp": result["timestamp"],
                        "summary": result["summary"],
                    }
                )

        return {
            "social": {
                "platforms": sorted(social_section["platforms"]),
                "profile_links": sorted(social_section["profile_links"]),
                "last_activity": social_section["last_activity"],
            }
        }

    def _prepare_social_section(self, profile: Dict[str, Any]) -> Dict[str, Any]:
        social = profile.get("social", {}) if isinstance(profile, dict) else {}
        platforms = set(social.get("platforms", []) or [])
        links = set(social.get("profile_links", []) or [])
        last_activity = list(social.get("last_activity", []) or [])
        return {
            "platforms": platforms,
            "profile_links": links,
            "last_activity": last_activity,
        }

    def _probe_platform(
        self, username: str, platform_name: str, platform: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        regex_check = platform.get("regexCheck")
        if regex_check and re.search(regex_check, username) is None:
            return None

        url_template = platform.get("url")
        url_main = platform.get("urlMain", "")
        if not url_template:
            return None
        url_user = _interpolate_string(url_template, username)

        url_probe = platform.get("urlProbe")
        url_probe = _interpolate_string(url_probe, username) if url_probe else url_user

        error_type = platform.get("errorType")
        if isinstance(error_type, str):
            error_type = [error_type]
        if not error_type:
            return None

        request_method = platform.get("request_method")
        if request_method is None:
            request_method = "GET" if "message" in error_type else "HEAD"

        require_body = request_method != "HEAD" and "message" in error_type
        headers = _build_headers(platform.get("headers"), username)
        request_payload = platform.get("request_payload")
        if request_payload is not None:
            request_payload = _interpolate_payload(request_payload, username)

        allow_redirects = "response_url" not in error_type

        status, body, final_url = _fetch_url(
            url_probe,
            request_method,
            headers,
            request_payload,
            self.timeout_s,
            allow_redirects,
            require_body,
        )
        if status is None:
            return None

        query_available = False
        query_claimed = False

        if "message" in error_type:
            errors = platform.get("errorMsg")
            if isinstance(errors, str):
                errors = [errors]
            if errors:
                lowered = body.lower() if body else ""
                if any(error.lower() in lowered for error in errors):
                    query_available = True
                else:
                    query_claimed = True

        if "status_code" in error_type and not query_available:
            error_codes = platform.get("errorCode")
            if isinstance(error_codes, int):
                error_codes = [error_codes]
            if error_codes is not None and status in error_codes:
                query_available = True
            elif status < 200 or status >= 300:
                query_available = True
            else:
                query_claimed = True

        if "response_url" in error_type and not query_available:
            if 200 <= status < 300:
                query_claimed = True
            else:
                query_available = True

        if not query_claimed or query_available:
            return None

        category = _classify_platform(platform_name, url_main, platform.get("tags"))
        avatar_url = _extract_avatar(body)
        activity_score = _score_keyword_hits(body, _ACTIVITY_KEYWORDS, 6)
        completeness_score = _score_keyword_hits(body, _COMPLETENESS_KEYWORDS, 6)
        confidence = self._score_confidence(status, error_type, body)
        signal_score = min(
            1.0,
            confidence + (0.2 if avatar_url else 0.0) + (0.1 if body else 0.0),
        )
        relevance = min(
            1.0,
            0.4 * activity_score + 0.3 * completeness_score + 0.3 * signal_score,
        )

        timestamp = datetime.now(timezone.utc).isoformat()
        summary = (
            f"source=sherlock; username={username}; category={category}; "
            f"confidence={confidence:.2f}; relevance={relevance:.2f}; "
            f"activity={activity_score:.2f}; completeness={completeness_score:.2f}; "
            f"signals={signal_score:.2f}; status={status}; "
            f"avatar={avatar_url or 'none'}"
        )

        return {
            "platform": platform_name,
            "canonical_url": _canonicalize_url(final_url or url_user),
            "timestamp": timestamp,
            "summary": summary,
        }

    @staticmethod
    def _score_confidence(status: int, error_type: Iterable[str], body: str) -> float:
        if 200 <= status < 300:
            base = 0.7
        elif 300 <= status < 400:
            base = 0.55
        elif status in (401, 403):
            base = 0.5
        elif status in (429,):
            base = 0.35
        else:
            base = 0.2
        if "message" in error_type and body:
            base += 0.1
        return min(1.0, base)
