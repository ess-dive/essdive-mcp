#!/usr/bin/env python3
"""
ESS-DIVE MCP Server - Main entry point

This module implements a Model Context Protocol (MCP) server that provides
comprehensive tools for accessing and analyzing data from ESS-DIVE and ESS-DeepDive APIs.

MCP Tools Available:

**Dataset Search & Retrieval:**
  - search-datasets: Full-text search across ESS-DIVE datasets with filtering by creator,
    provider, publication date, temporal coverage, keywords, geographic bounds/nearby
    search, and local metadata-aware post-filters for fields exposed on full dataset
    records. Supports pagination and multiple result formats.
  - next-search-page / previous-search-page: Navigate the most recent dataset-search
    result set without exposing raw pagination cursors.
  - get-dataset: Retrieve detailed metadata for a specific dataset, including top-level
    package fields such as isPublic, dateUploaded, dateModified, citation, and
    available data files.
  - get-dataset-versions: List visible versions of a dataset from newest to oldest,
    with cursor-based pagination support for version history navigation.
  - next-dataset-versions-page / previous-dataset-versions-page: Navigate the most
    recent dataset-version history request without exposing raw pagination cursors.
  - get-dataset-status: Get workflow/status metadata for a dataset from the
    /packages/{identifier}/status endpoint.
  - get-dataset-permissions: Get sharing and access permission information for datasets.

**Identifier Conversion:**
  - doi-to-essdive-id: Convert Digital Object Identifiers (DOI) to ESS-DIVE dataset IDs.
    Handles multiple DOI formats (doi:10.xxxx, https://doi.org/10.xxxx, etc.).
  - essdive-id-to-doi: Convert ESS-DIVE dataset IDs to standardized DOI format.

**File-Level Metadata:**
  - parse-flmd-file: Parse File Level Metadata (FLMD) CSV files to extract filename and
    description mappings for dataset files.

**Project References:**
  - lookup-project-portal: Look up ESS-DIVE-related project names, acronyms, descriptions,
    and portal URLs from a shared local reference file.

**ESS-DeepDive Search & Analysis:**
  - search-ess-deepdive: Search the ESS-DeepDive fusion database for data fields by name,
    definition, value (text/numeric/date), and record count. Supports multi-page results.
  - get-ess-deepdive-dataset: Retrieve detailed field information and metadata for a
    specific file in the ESS-DeepDive database.
  - get-ess-deepdive-file: Get comprehensive file-level information including field names,
    data types, summary statistics, and download metadata from ESS-DeepDive.

**Mapping:**
  - coords-to-map-links: Convert points or a bounding box to viewable map links (e.g., geojson.io).

Authentication:
  Public dataset reads do not require authentication. An API token can still be
  provided via --token, --token-file, or ESSDIVE_API_TOKEN for authenticated
  requests such as private-data access.
"""
import asyncio
import os
import argparse
import json
import csv
import re
import logging
import traceback
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
import requests
from io import StringIO
from typing import Dict, List, Optional, Any, Union, Awaitable, TypeVar
import httpx
import yaml
from urllib.parse import quote
from urllib.parse import quote as url_quote

from fastmcp import FastMCP
from fastmcp.server.context import Context


LOGGER = logging.getLogger("essdive_mcp")
REQUEST_TIMEOUT_SECONDS = 30.0
T = TypeVar("T")
PROJECT_PORTALS_PATH = (
    Path(__file__).resolve().parents[2]
    / ".agents"
    / "skills"
    / "references"
    / "essdive_project_portals.yaml"
)


def _is_truthy(value: Optional[str]) -> bool:
    """Return True when a string value represents an enabled boolean."""
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _configure_logging(verbose: bool) -> None:
    """Configure logging for MCP runtime diagnostics."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    LOGGER.setLevel(level)


def _truncate_text(value: str, max_length: int = 500) -> str:
    """Return text truncated to a bounded size with an indicator."""
    if len(value) <= max_length:
        return value
    return f"{value[:max_length]}... [truncated]"


def _iter_exception_chain(exc: BaseException):
    """Yield an exception plus any causes/contexts."""
    current: Optional[BaseException] = exc
    seen_ids: set[int] = set()
    while current and id(current) not in seen_ids:
        seen_ids.add(id(current))
        yield current
        current = current.__cause__ or current.__context__


def _extract_http_error_details(exc: BaseException) -> Dict[str, Any]:
    """Extract HTTP-centric diagnostics from common request libraries."""
    if isinstance(exc, httpx.HTTPStatusError):
        response = exc.response
        request_url = str(
            response.request.url) if response.request else str(response.url)
        details: Dict[str, Any] = {
            "status_code": response.status_code,
            "url": request_url,
        }
        body = response.text.strip()
        if body:
            details["response_body_preview"] = _truncate_text(body)
        return details

    if isinstance(exc, httpx.RequestError):
        details = {"url": str(exc.request.url)} if exc.request else {}
        if str(exc):
            details["request_error"] = str(exc)
        return details

    if isinstance(exc, requests.HTTPError):
        response = exc.response
        if response is None:
            return {}
        details = {
            "status_code": response.status_code,
            "url": response.url,
        }
        body = response.text.strip()
        if body:
            details["response_body_preview"] = _truncate_text(body)
        return details

    if isinstance(exc, requests.RequestException):
        details: Dict[str, Any] = {}
        request = getattr(exc, "request", None)
        if request and getattr(request, "url", None):
            details["url"] = request.url
        if str(exc):
            details["request_error"] = str(exc)
        return details

    return {}


def _build_tool_error_payload(
    operation: str,
    exc: BaseException,
    verbose: bool = False,
    context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build a standard MCP tool error payload with optional diagnostics."""
    payload: Dict[str, Any] = {
        "error": {
            "operation": operation,
            "type": exc.__class__.__name__,
            "message": str(exc) or repr(exc),
        }
    }

    if context:
        payload["error"]["context"] = context

    for candidate in _iter_exception_chain(exc):
        http_details = _extract_http_error_details(candidate)
        if http_details:
            payload["error"]["http"] = http_details
            break

    if verbose:
        payload["error"]["traceback"] = traceback.format_exc()
    else:
        payload["error"]["hint"] = (
            "Run the MCP server with --verbose or set ESSDIVE_MCP_VERBOSE=1 for a traceback."
        )

    return payload


def _tool_error_response(
    operation: str,
    exc: BaseException,
    verbose: bool = False,
    context: Optional[Dict[str, Any]] = None,
) -> str:
    """Log and serialize a standard tool error response as JSON."""
    payload = _build_tool_error_payload(
        operation, exc, verbose=verbose, context=context)
    if verbose:
        LOGGER.exception("Tool %s failed", operation)
    else:
        LOGGER.error("Tool %s failed: %s", operation,
                     payload["error"]["message"])
    return json.dumps(payload, indent=2)


def _context_without_none(context: Dict[str, Any]) -> Dict[str, Any]:
    """Drop unset keys before emitting tool context."""
    return {key: value for key, value in context.items() if value is not None}


def _default_dataset_search_is_public(api_token: Optional[str]) -> Optional[bool]:
    """Use public-only search anonymously; allow private matches when authenticated."""
    return True if not api_token else None


def _is_essdive_empty_search_response(response: httpx.Response) -> bool:
    """Return True when ESS-DIVE encodes an empty search result as HTTP 404."""
    if response.status_code != 404:
        return False

    try:
        payload = response.json()
    except ValueError:
        return False

    detail = payload.get("detail")
    return (
        isinstance(detail, str)
        and detail.strip().lower() == "no datasets were found."
    )


def _empty_dataset_search_result(
    *,
    row_start: Optional[int],
    page_size: Optional[int],
    cursor: Optional[str],
    is_public: Optional[bool],
    creator: Optional[str],
    provider_name: Optional[str],
    text: Optional[str],
    date_published: Optional[str],
    begin_date: Optional[str],
    end_date: Optional[str],
    keywords: Optional[List[str]],
    sort: Optional[str],
    bbox: Optional[str],
    lat: Optional[float],
    lon: Optional[float],
    radius: Optional[float],
) -> Dict[str, Any]:
    """Return a stable empty search payload when the API reports no matches."""
    payload = {
        "total": 0,
        "result": [],
        "query": {
            "isPublic": is_public,
            "creator": creator,
            "providerName": provider_name,
            "text": text,
            "datePublished": date_published,
            "beginDate": begin_date,
            "endDate": end_date,
            "keywords": keywords,
            "sort": sort,
            "cursor": cursor,
            "bbox": bbox,
            "lat": lat,
            "lon": lon,
            "radius": radius,
        },
    }
    if page_size is not None:
        payload["pageSize"] = page_size
    if row_start is not None:
        payload["rowStart"] = row_start
    return payload


def _run_in_new_event_loop(awaitable: Awaitable[T]) -> T:
    """Run an awaitable in a dedicated event loop for sync helper functions."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(awaitable)
    finally:
        loop.close()


def _format_dataset_search_bbox(
    bbox: Union[str, List[float]],
) -> str:
    """Normalize a dataset-search bbox into the API's comma-delimited format."""
    if isinstance(bbox, str):
        parts = [part.strip() for part in bbox.split(",")]
    else:
        if len(bbox) != 4:
            raise ValueError(
                "bbox must contain exactly 4 values: min_lat,min_lon,max_lat,max_lon.")
        parts = [str(float(value)) for value in bbox]

    if len(parts) != 4:
        raise ValueError(
            "bbox must contain exactly 4 values: min_lat,min_lon,max_lat,max_lon.")

    try:
        return ",".join(str(float(part)) for part in parts)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            "bbox values must be numeric and ordered as min_lat,min_lon,max_lat,max_lon."
        ) from exc


def _as_list(value: Any) -> List[Any]:
    """Return a value as a list without splitting strings into characters."""
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _as_string_list(value: Any) -> List[str]:
    """Flatten strings and lists of strings into a clean list."""
    values: List[str] = []
    for item in _as_list(value):
        if item is None:
            continue
        if isinstance(item, list):
            values.extend(_as_string_list(item))
            continue
        text = str(item).strip()
        if text:
            values.append(text)
    return values


def _person_display_name(person: Dict[str, Any]) -> str:
    """Return a readable name for a person-like object."""
    given_name = str(person.get("givenName") or "").strip()
    family_name = str(person.get("familyName") or "").strip()
    full_name = f"{given_name} {family_name}".strip()
    return full_name or str(person.get("name") or "").strip()


def _person_search_strings(person: Dict[str, Any]) -> List[str]:
    """Collect useful text fields from a person object for local matching."""
    values = []
    values.extend(_as_string_list(_person_display_name(person)))
    values.extend(_as_string_list(person.get("email")))
    values.extend(_as_string_list(person.get("affiliation")))
    values.extend(_as_string_list(person.get("@id")))
    return values


def _organization_search_strings(organization: Dict[str, Any]) -> List[str]:
    """Collect useful text fields from an organization object for local matching."""
    values = []
    values.extend(_as_string_list(organization.get("name")))
    values.extend(_as_string_list(organization.get("email")))
    values.extend(_as_string_list(organization.get("@id")))
    return values


def _summarize_provider(provider: Any) -> List[str]:
    """Return readable provider summaries from dataset metadata."""
    summaries: List[str] = []

    for item in _as_list(provider):
        if isinstance(item, dict):
            name = str(item.get("name") or "").strip()
            member = item.get("member")

            member_labels: List[str] = []
            for member_item in _as_list(member):
                if isinstance(member_item, dict):
                    member_name = _person_display_name(member_item)
                    job_title = str(member_item.get("jobTitle") or "").strip()
                    affiliation = str(member_item.get("affiliation") or "").strip()
                    parts = [part for part in [member_name, job_title, affiliation] if part]
                    if parts:
                        member_labels.append(", ".join(parts))
                else:
                    text = str(member_item).strip()
                    if text:
                        member_labels.append(text)

            label = name or ", ".join(_organization_search_strings(item))
            if member_labels:
                if label:
                    label = f"{label} ({'; '.join(member_labels)})"
                else:
                    label = "; ".join(member_labels)
            if label:
                summaries.append(label)
            continue

        text = str(item).strip()
        if text:
            summaries.append(text)

    return summaries


def _format_result_user_note(user: Any) -> Optional[str]:
    """Return a human-readable visibility note derived from the API user field."""
    if user is None:
        return None

    user_text = str(user).strip()
    if not user_text:
        return None
    if user_text == "anonymous":
        return "Results include public data only."
    return f"User: {user_text}"


def _should_show_is_public(value: Any, user: Any) -> bool:
    """Hide redundant public flags for anonymous result sets."""
    if value is None:
        return False
    user_text = str(user).strip() if user is not None else ""
    if user_text == "anonymous" and value is True:
        return False
    return True


def _markdown_link(label: str, url: Optional[str]) -> Optional[str]:
    """Return a Markdown link when a URL is available."""
    if not url:
        return None
    return f"[{label}]({url})"


@dataclass
class SearchPaginationState:
    """State needed to continue paging through a dataset search."""

    search_kwargs: Dict[str, Any]
    local_filters: Dict[str, List[str]]
    format_type: str
    next_cursor: Optional[str]
    previous_cursor: Optional[str]


@dataclass
class VersionsPaginationState:
    """State needed to continue paging through dataset versions."""

    identifier: str
    format_type: str
    next_cursor: Optional[str]
    previous_cursor: Optional[str]


class PaginationStateStore:
    """Track per-session dataset-search and version-history context."""

    def __init__(self) -> None:
        self.search_by_session: Dict[str, SearchPaginationState] = {}
        self.versions_by_session: Dict[str, VersionsPaginationState] = {}

    def save_search(
        self,
        *,
        session_id: str,
        search_kwargs: Dict[str, Any],
        local_filters: Dict[str, List[str]],
        format_type: str,
        result: Dict[str, Any],
    ) -> None:
        base_kwargs = dict(search_kwargs)
        base_kwargs["cursor"] = None
        base_kwargs["row_start"] = None

        self.search_by_session[session_id] = SearchPaginationState(
            search_kwargs=base_kwargs,
            local_filters={key: list(values) for key, values in local_filters.items()},
            format_type=format_type,
            next_cursor=result.get("nextCursor"),
            previous_cursor=result.get("previousCursor"),
        )

    def get_search_followup(
        self,
        session_id: str,
        direction: str,
        *,
        format_override: Optional[str] = None,
    ) -> tuple[Dict[str, Any], Dict[str, List[str]], str]:
        search_state = self.search_by_session.get(session_id)
        if not search_state:
            raise ValueError("No prior dataset search is available for pagination.")

        cursor = (
            search_state.next_cursor
            if direction == "next"
            else search_state.previous_cursor
        )
        if not cursor:
            raise ValueError(
                f"No {direction} page is available for the most recent dataset search."
            )

        followup_kwargs = dict(search_state.search_kwargs)
        followup_kwargs["cursor"] = cursor
        followup_kwargs["row_start"] = None
        followup_kwargs["page_size"] = None
        return (
            followup_kwargs,
            {key: list(values) for key, values in search_state.local_filters.items()},
            format_override or search_state.format_type,
        )

    def save_versions(
        self,
        *,
        session_id: str,
        identifier: str,
        format_type: str,
        result: Dict[str, Any],
    ) -> None:
        self.versions_by_session[session_id] = VersionsPaginationState(
            identifier=identifier,
            format_type=format_type,
            next_cursor=result.get("nextCursor"),
            previous_cursor=result.get("previousCursor"),
        )

    def get_versions_followup(
        self,
        session_id: str,
        direction: str,
        *,
        format_override: Optional[str] = None,
    ) -> tuple[str, str, str]:
        versions_state = self.versions_by_session.get(session_id)
        if not versions_state:
            raise ValueError(
                "No prior dataset-version request is available for pagination."
            )

        cursor = (
            versions_state.next_cursor
            if direction == "next"
            else versions_state.previous_cursor
        )
        if not cursor:
            raise ValueError(
                f"No {direction} page is available for the most recent dataset-version request."
            )

        return (
            versions_state.identifier,
            cursor,
            format_override or versions_state.format_type,
        )


async def _execute_dataset_search_request(
    client: "ESSDiveClient",
    *,
    search_kwargs: Dict[str, Any],
    local_filters: Dict[str, List[str]],
) -> Dict[str, Any]:
    """Run an ESS-DIVE search and apply any local metadata filters."""
    result = await client.search_datasets(**search_kwargs)
    return await _apply_local_dataset_filters(client, result, local_filters)


def _render_formatted_output(
    formatted: Union[str, Dict[str, Any]],
    format_type: str,
) -> str:
    """Serialize formatted MCP tool output."""
    if format_type == "raw":
        return json.dumps(formatted, indent=2)
    if isinstance(formatted, dict):
        return json.dumps(formatted, indent=2)
    return str(formatted)


def _distribution_search_strings(
    distribution: Any,
    *,
    field: str,
) -> List[str]:
    """Collect a single distribution field across all file entries."""
    values: List[str] = []
    for item in _as_list(distribution):
        if isinstance(item, dict):
            values.extend(_as_string_list(item.get(field)))
    return values


def _summarize_temporal_coverage(temporal_coverage: Any) -> Optional[str]:
    """Return a compact temporal coverage string when available."""
    if not isinstance(temporal_coverage, dict):
        return None

    start_date = str(temporal_coverage.get("startDate") or "").strip()
    end_date = str(temporal_coverage.get("endDate") or "").strip()

    if start_date and end_date:
        return f"{start_date} to {end_date}"
    if start_date:
        return f"{start_date} onward"
    if end_date:
        return f"through {end_date}"
    return None


def _summarize_spatial_coverage(spatial_coverage: Any) -> List[str]:
    """Return readable spatial coverage summaries from ESS-DIVE place metadata."""
    summaries: List[str] = []

    for place in _as_list(spatial_coverage):
        if not isinstance(place, dict):
            continue

        descriptions = _as_string_list(place.get("description"))
        geo_entries = _as_list(place.get("geo"))
        geo_parts: List[str] = []
        for geo in geo_entries:
            if not isinstance(geo, dict):
                continue
            lat = geo.get("latitude")
            lon = geo.get("longitude")
            if lat is not None and lon is not None:
                geo_parts.append(f"{lat}, {lon}")

        description = "; ".join(descriptions)
        if description and geo_parts:
            summaries.append(f"{description} ({'; '.join(geo_parts)})")
        elif description:
            summaries.append(description)
        elif geo_parts:
            summaries.append("; ".join(geo_parts))

    return summaries


def _dataset_local_filter_candidates(
    dataset: Dict[str, Any],
    filter_name: str,
) -> List[str]:
    """Collect candidate strings for a local metadata filter."""
    if filter_name == "creator_affiliation":
        values: List[str] = []
        for creator in _as_list(dataset.get("creator")):
            if isinstance(creator, dict):
                values.extend(_as_string_list(creator.get("affiliation")))
        return values

    if filter_name == "variable_measured":
        return _as_string_list(dataset.get("variableMeasured"))

    if filter_name == "measurement_technique":
        return _as_string_list(dataset.get("measurementTechnique"))

    if filter_name == "funder":
        values: List[str] = []
        for funder in _as_list(dataset.get("funder")):
            if isinstance(funder, dict):
                values.extend(_organization_search_strings(funder))
            else:
                values.extend(_as_string_list(funder))
        return values

    if filter_name == "license":
        return _as_string_list(dataset.get("license"))

    if filter_name == "alternate_name":
        return _as_string_list(dataset.get("alternateName"))

    if filter_name == "editor":
        editor = dataset.get("editor")
        if isinstance(editor, dict):
            return _person_search_strings(editor)
        return _as_string_list(editor)

    if filter_name == "file_format":
        return _distribution_search_strings(
            dataset.get("distribution"), field="encodingFormat"
        )

    if filter_name == "file_name":
        return _distribution_search_strings(dataset.get("distribution"), field="name")

    if filter_name == "file_url":
        return _distribution_search_strings(
            dataset.get("distribution"), field="contentUrl"
        )

    return []


def _normalize_local_filter_values(
    value: Optional[Union[str, List[str]]],
) -> List[str]:
    """Normalize local filter values into a clean string list."""
    return _as_string_list(value)


def _dataset_matches_local_filters(
    dataset: Dict[str, Any],
    local_filters: Dict[str, List[str]],
) -> bool:
    """Return True when a dataset matches all requested local metadata filters."""
    for filter_name, expected_values in local_filters.items():
        if not expected_values:
            continue

        candidates = [
            candidate.lower()
            for candidate in _dataset_local_filter_candidates(dataset, filter_name)
            if candidate
        ]
        if not candidates:
            return False

        for expected in expected_values:
            normalized_expected = expected.strip().lower()
            if not normalized_expected:
                continue
            if not any(normalized_expected in candidate for candidate in candidates):
                return False

    return True


async def _hydrate_dataset_search_results(
    client: "ESSDiveClient",
    results: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Fetch full dataset records for a search result page."""
    semaphore = asyncio.Semaphore(5)

    async def fetch_item(item: Dict[str, Any]) -> Dict[str, Any]:
        dataset_id = item.get("id")
        if not dataset_id:
            return item

        async with semaphore:
            try:
                detail = await client.get_dataset(str(dataset_id))
            except Exception as exc:
                LOGGER.warning(
                    "Failed to hydrate dataset search result id=%s: %s",
                    dataset_id,
                    exc,
                )
                return item

        hydrated = dict(item)
        if isinstance(detail, dict):
            detail_dataset = detail.get("dataset")
            if isinstance(detail_dataset, dict):
                hydrated["dataset"] = detail_dataset
            for key in ("viewUrl", "citation", "dateUploaded", "dateModified", "isPublic"):
                if key in detail and key not in hydrated:
                    hydrated[key] = detail[key]
        return hydrated

    items = results.get("result", [])
    if not isinstance(items, list):
        return []
    return await asyncio.gather(*(fetch_item(item) for item in items))


async def _apply_local_dataset_filters(
    client: "ESSDiveClient",
    results: Dict[str, Any],
    local_filters: Dict[str, List[str]],
) -> Dict[str, Any]:
    """Apply metadata-aware local filters to search results using hydrated datasets."""
    active_filters = {
        key: values for key, values in local_filters.items() if values
    }
    if not active_filters:
        return results

    hydrated_items = await _hydrate_dataset_search_results(client, results)
    filtered_items = [
        item
        for item in hydrated_items
        if _dataset_matches_local_filters(item.get("dataset", {}), active_filters)
    ]

    filtered_results = dict(results)
    filtered_results["result"] = filtered_items
    filtered_results["total"] = len(filtered_items)

    query = filtered_results.get("query")
    if isinstance(query, dict):
        query = dict(query)
        query["localFilters"] = active_filters
        filtered_results["query"] = query

    filtered_results["filtering"] = {
        "mode": "api_search_then_local_metadata_filter",
        "native_total": results.get("total"),
        "scanned_results": len(hydrated_items),
        "matched_results": len(filtered_items),
        "local_filters": active_filters,
    }
    return filtered_results


def _normalize_lookup_text(value: str) -> str:
    """Normalize project lookup text for case-insensitive matching."""
    return re.sub(r"[^a-z0-9]+", "", value.lower())


@lru_cache(maxsize=1)
def _load_project_portals() -> List[Dict[str, Any]]:
    """Load portal metadata shared by the MCP server and Skills."""
    if not PROJECT_PORTALS_PATH.exists():
        raise FileNotFoundError(
            f"Project portal reference file not found: {PROJECT_PORTALS_PATH}"
        )

    with PROJECT_PORTALS_PATH.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle) or {}

    projects = payload.get("projects")
    if not isinstance(projects, list):
        raise ValueError(
            f"Expected 'projects' list in {PROJECT_PORTALS_PATH}, found {type(projects).__name__}."
        )

    normalized_projects: List[Dict[str, Any]] = []
    for item in projects:
        if not isinstance(item, dict):
            continue

        aliases = item.get("aliases") or []
        if not isinstance(aliases, list):
            aliases = [str(aliases)]

        normalized_projects.append(
            {
                "name": item.get("name"),
                "acronym": item.get("acronym"),
                "aliases": [str(alias) for alias in aliases if alias],
                "short_description": item.get("short_description"),
                "portal_url": item.get("portal_url"),
                "url": item.get("url") or item.get("portal_url"),
            }
        )

    return normalized_projects


def search_project_portals(
    query: Optional[str] = None,
    limit: int = 10,
) -> Dict[str, Any]:
    """Search the shared project portal reference list by acronym, name, or alias."""
    if limit <= 0:
        raise ValueError("limit must be greater than 0.")

    projects = _load_project_portals()
    if not query:
        return {
            "query": None,
            "count": len(projects),
            "results": projects[:limit],
            "source_file": str(PROJECT_PORTALS_PATH),
        }

    normalized_query = _normalize_lookup_text(query)
    if not normalized_query:
        raise ValueError("query must contain at least one letter or number.")

    scored_results: List[tuple[int, Dict[str, Any]]] = []
    for project in projects:
        name = str(project.get("name") or "")
        acronym = str(project.get("acronym") or "")
        description = str(project.get("short_description") or "")
        aliases = [str(alias) for alias in project.get("aliases") or []]

        score = 0
        candidates = [name, acronym, description, *aliases]
        normalized_candidates = [_normalize_lookup_text(value)
                                 for value in candidates if value]

        if acronym and normalized_query == _normalize_lookup_text(acronym):
            score = max(score, 120)
        if name and normalized_query == _normalize_lookup_text(name):
            score = max(score, 110)
        if any(normalized_query == _normalize_lookup_text(alias) for alias in aliases):
            score = max(score, 105)
        if acronym and normalized_query in _normalize_lookup_text(acronym):
            score = max(score, 95)
        if name and normalized_query in _normalize_lookup_text(name):
            score = max(score, 90)
        if any(normalized_query in _normalize_lookup_text(alias) for alias in aliases):
            score = max(score, 85)
        if any(normalized_query in candidate for candidate in normalized_candidates):
            score = max(score, 70)

        if score > 0:
            scored_results.append((score, project))

    scored_results.sort(
        key=lambda item: (-item[0], str(item[1].get("name") or "")))
    results = [item[1] for item in scored_results[:limit]]
    return {
        "query": query,
        "count": len(results),
        "results": results,
        "source_file": str(PROJECT_PORTALS_PATH),
    }


def _validate_dataset_search_spatial_params(
    bbox: Optional[Union[str, List[float]]] = None,
    lat: Optional[float] = None,
    lon: Optional[float] = None,
    radius: Optional[float] = None,
) -> Optional[str]:
    """Validate and normalize ESS-DIVE dataset spatial search parameters."""
    point_search_requested = any(
        value is not None for value in (lat, lon, radius))
    if bbox is not None and point_search_requested:
        raise ValueError(
            "Use either bbox or lat/lon/radius for spatial search, not both.")

    if point_search_requested and not all(value is not None for value in (lat, lon, radius)):
        raise ValueError(
            "lat, lon, and radius must all be provided together for point-based search.")

    if radius is not None and radius <= 0:
        raise ValueError("radius must be greater than 0 meters.")

    if bbox is None:
        return None

    return _format_dataset_search_bbox(bbox)


# Helper functions for FLMD parsing
def sanitize_tsv_field(value) -> str:
    """Normalize a value destined for TSV output.

    Replaces any newlines / carriage returns / tabs with a single space,
    collapses consecutive whitespace, and strips leading/trailing spaces.
    Non-string values are coerced to string. None becomes empty string.
    """
    if value is None:
        return ""
    if not isinstance(value, str):
        value = str(value)
    # Replace problematic control characters with space
    value = value.replace("\r", " ").replace("\n", " ").replace("\t", " ")
    # Collapse multiple whitespace to a single space
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def _norm_header_key(h: str) -> str:
    """Normalize a CSV header key for matching regardless of case/spacing/punct."""
    if not isinstance(h, str):
        h = str(h)
    return re.sub(r"[^a-z0-9]", "", h.lower())


def _bbox_from_points(points: List[List[float]]) -> List[float]:
    """Return [min_lat, min_lon, max_lat, max_lon] from a list of [lat, lon] points."""
    lats = [p[0] for p in points]
    lons = [p[1] for p in points]
    return [min(lats), min(lons), max(lats), max(lons)]


def _geojson_for_points(points: List[List[float]]) -> Dict[str, Any]:
    """Build a GeoJSON FeatureCollection for points (input points are [lat, lon])."""
    features = []
    for lat, lon in points:
        features.append(
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [lon, lat]},
                "properties": {},
            }
        )
    return {"type": "FeatureCollection", "features": features}


def _geojson_for_bbox(bbox: List[float]) -> Dict[str, Any]:
    """Build a GeoJSON Polygon for bbox [min_lat, min_lon, max_lat, max_lon]."""
    min_lat, min_lon, max_lat, max_lon = bbox
    coordinates = [
        [min_lon, min_lat],
        [min_lon, max_lat],
        [max_lon, max_lat],
        [max_lon, min_lat],
        [min_lon, min_lat],
    ]
    return {"type": "Polygon", "coordinates": [coordinates]}


def _geojson_io_link(geojson_obj: Dict[str, Any]) -> str:
    """Return a geojson.io link that loads the provided GeoJSON."""
    encoded = url_quote(json.dumps(geojson_obj, separators=(",", ":")))
    return f"https://geojson.io/#data=data:application/json,{encoded}"


def _osm_bbox_link(bbox: List[float]) -> str:
    """Return an OpenStreetMap link that frames the provided bbox."""
    min_lat, min_lon, max_lat, max_lon = bbox
    return (
        "https://www.openstreetmap.org/"
        f"?minlon={min_lon}&minlat={min_lat}&maxlon={max_lon}&maxlat={max_lat}"
    )


def _google_maps_center_link(
    center: List[float], zoom: Optional[int] = None
) -> str:
    """Return a Google Maps link centered on a point."""
    lat, lon = center
    params = f"api=1&map_action=map&center={lat},{lon}"
    if zoom is not None:
        params += f"&zoom={zoom}"
    return f"https://www.google.com/maps/@?{params}"


def _kml_document(name: str, placemarks: List[str]) -> str:
    """Return a KML document string with the provided placemarks."""
    inner = "\n".join(placemarks)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<kml xmlns="http://www.opengis.net/kml/2.2">\n'
        "  <Document>\n"
        f"    <name>{name}</name>\n"
        f"{inner}\n"
        "  </Document>\n"
        "</kml>"
    )


def _kml_point_placemark(name: str, lat: float, lon: float) -> str:
    """Return a KML placemark for a single point."""
    return (
        "    <Placemark>\n"
        f"      <name>{name}</name>\n"
        "      <Point>\n"
        f"        <coordinates>{lon},{lat},0</coordinates>\n"
        "      </Point>\n"
        "    </Placemark>"
    )


def _kml_bbox_placemark(name: str, bbox: List[float]) -> str:
    """Return a KML placemark for a bounding box polygon."""
    min_lat, min_lon, max_lat, max_lon = bbox
    coords = " ".join(
        [
            f"{min_lon},{min_lat},0",
            f"{min_lon},{max_lat},0",
            f"{max_lon},{max_lat},0",
            f"{max_lon},{min_lat},0",
            f"{min_lon},{min_lat},0",
        ]
    )
    return (
        "    <Placemark>\n"
        f"      <name>{name}</name>\n"
        "      <Polygon>\n"
        "        <outerBoundaryIs>\n"
        "          <LinearRing>\n"
        f"            <coordinates>{coords}</coordinates>\n"
        "          </LinearRing>\n"
        "        </outerBoundaryIs>\n"
        "      </Polygon>\n"
        "    </Placemark>"
    )


def _kml_data_uri(kml: str) -> str:
    """Return a data URI containing KML content."""
    encoded = url_quote(kml)
    return f"data:application/vnd.google-earth.kml+xml,{encoded}"


def parse_flmd_file(content: str) -> Dict[str, str]:
    """Parse an FLMD (File Level Metadata) file and return a mapping of filename -> description.

    Examples:
        >>> parse_flmd_file("filename,file_description\\nfile1.csv,Soil moisture\\n")
        {'file1.csv': 'Soil moisture'}

    Args:
        content: The FLMD file content as a string

    Returns:
        Dictionary mapping filename to file description
    """
    if not isinstance(content, str):
        raise ValueError("Invalid FLMD CSV content: content must be a string")

    file_descriptions = {}
    try:
        reader = csv.DictReader(StringIO(content))
        if not reader.fieldnames:
            return file_descriptions

        # Find the columns for file name and description (case insensitive)
        filename_col = None
        description_col = None

        for field in reader.fieldnames:
            norm_field = _norm_header_key(field)
            if norm_field in ["filename", "file_name", "name"]:
                filename_col = field
            elif norm_field in ["filedescription", "file_description", "description"]:
                description_col = field

        if not filename_col or not description_col:
            return file_descriptions

        # Parse the rows
        for row in reader:
            filename = sanitize_tsv_field(row.get(filename_col, ""))
            description = sanitize_tsv_field(row.get(description_col, ""))

            if filename and description:
                file_descriptions[filename] = description

    except Exception as exc:
        raise ValueError(f"Invalid FLMD CSV content: {exc}") from exc

    return file_descriptions


class ESSDiveClient:
    """Client for interacting with the ESS-DIVE Dataset API."""

    BASE_URL = "https://api.ess-dive.lbl.gov"

    def __init__(self, api_token: Optional[str] = None):
        """
        Initialize the ESS-DIVE API client.

        Args:
            api_token: Optional API token for authenticated requests
        """
        self.api_token = api_token
        self.headers = {}
        if api_token:
            self.headers["Authorization"] = f"Bearer {api_token}"

    def _get_headers(self) -> Dict[str, str]:
        """Get headers for API requests."""
        return self.headers

    def _package_url(self, identifier: str, suffix: str = "") -> str:
        """Build a package endpoint URL for a dataset identifier."""
        encoded_identifier = quote(identifier, safe="")
        return f"{self.BASE_URL}/packages/{encoded_identifier}{suffix}"

    async def _get_json(self, url: str) -> Dict[str, Any]:
        """Fetch a JSON response from the ESS-DIVE API."""
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as client:
            response = await client.get(url, headers=self._get_headers())
            response.raise_for_status()
            return response.json()

    async def search_datasets(
        self,
        row_start: Optional[int] = None,
        page_size: Optional[int] = None,
        cursor: Optional[str] = None,
        is_public: Optional[bool] = None,
        creator: Optional[str] = None,
        provider_name: Optional[str] = None,
        text: Optional[str] = None,
        date_published: Optional[str] = None,
        begin_date: Optional[str] = None,
        end_date: Optional[str] = None,
        keywords: Optional[List[str]] = None,
        sort: Optional[str] = None,
        bbox: Optional[Union[str, List[float]]] = None,
        lat: Optional[float] = None,
        lon: Optional[float] = None,
        radius: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Search for datasets using the ESS-DIVE API.

        Args:
            row_start: Legacy row number to start on (for pagination)
            page_size: Number of results per page (max 100)
            cursor: Opaque cursor for follow-up pages of search results
            is_public: If True, only return public packages
            creator: Filter by dataset creator
            provider_name: Filter by dataset project/provider
            text: Full-text search across metadata fields
            date_published: Filter by publication date
            begin_date: Filter by temporal coverage window start date
            end_date: Filter by temporal coverage window end date
            keywords: Search for datasets with specific keywords
            sort: Sort order such as "name:asc" or "dateUploaded:desc,authorLastName:asc"
            bbox: Bounding box filter as "min_lat,min_lon,max_lat,max_lon" or [min_lat, min_lon, max_lat, max_lon]
            lat: Latitude for point-based nearby search
            lon: Longitude for point-based nearby search
            radius: Search radius in meters for point-based nearby search

        Returns:
            API response containing search results

        Examples:
            await client.search_datasets(text="soil carbon", page_size=5, is_public=True)
            await client.search_datasets(provider_name="NGEE Arctic", row_start=1, page_size=10)
            await client.search_datasets(text="soil carbon", cursor="opaque-cursor")
            await client.search_datasets(begin_date="2020", end_date="2021-06")
            await client.search_datasets(text="soil carbon", sort="name:asc")
            await client.search_datasets(bbox=[34.0, -119.0, 35.0, -117.0])
        """
        params: Dict[str, Any] = {}
        effective_row_start = 1 if row_start is None else row_start
        effective_page_size = 25 if page_size is None else page_size
        normalized_bbox = _validate_dataset_search_spatial_params(
            bbox=bbox,
            lat=lat,
            lon=lon,
            radius=radius,
        )

        # Cursor pagination supersedes legacy rowStart pagination.
        if cursor:
            params["cursor"] = cursor
            if page_size is not None:
                params["pageSize"] = page_size
        else:
            params["rowStart"] = effective_row_start
            params["pageSize"] = effective_page_size

        # Add optional parameters if provided
        if is_public is not None:
            params["isPublic"] = str(is_public).lower()
        if creator:
            params["creator"] = creator
        if provider_name:
            params["providerName"] = provider_name
        if text:
            params["text"] = text
        if date_published:
            params["datePublished"] = date_published
        if begin_date:
            params["beginDate"] = begin_date
        if end_date:
            params["endDate"] = end_date
        if keywords:
            params["keywords"] = keywords
        if sort:
            params["sort"] = sort
        if normalized_bbox:
            params["bbox"] = normalized_bbox
        if lat is not None:
            params["lat"] = lat
        if lon is not None:
            params["lon"] = lon
        if radius is not None:
            params["radius"] = radius

        url = f"{self.BASE_URL}/packages"
        LOGGER.debug("ESS-DIVE search request url=%s params=%s", url, params)

        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as client:
            response = await client.get(url, params=params, headers=self._get_headers())
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError:
                if _is_essdive_empty_search_response(response):
                    LOGGER.debug(
                        "ESS-DIVE search returned 404 with no matching datasets; "
                        "converting to an empty result set"
                    )
                    return _empty_dataset_search_result(
                        row_start=None if cursor else effective_row_start,
                        page_size=page_size if cursor else effective_page_size,
                        cursor=cursor,
                        is_public=is_public,
                        creator=creator,
                        provider_name=provider_name,
                        text=text,
                        date_published=date_published,
                        begin_date=begin_date,
                        end_date=end_date,
                        keywords=keywords,
                        sort=sort,
                        bbox=normalized_bbox,
                        lat=lat,
                        lon=lon,
                        radius=radius,
                    )
                raise
            result = response.json()
            LOGGER.debug(
                "ESS-DIVE search response total=%s count=%s",
                result.get("total"),
                len(result.get("result", [])) if isinstance(
                    result, dict) else "n/a",
            )
            return result

    async def get_dataset(self, identifier: str) -> Dict[str, Any]:
        """
        Get detailed information about a specific dataset.

        Args:
            identifier: The ESS-DIVE unique identifier

        Returns:
            API response containing dataset details

        Examples:
            await client.get_dataset("ess-dive-9ea5fe57db73c90-20241024T093714082510")
            await client.get_dataset("doi:10.15485/2453885")
        """
        url = self._package_url(identifier)
        LOGGER.debug("ESS-DIVE get dataset request url=%s", url)

        result = await self._get_json(url)
        LOGGER.debug("ESS-DIVE get dataset response id=%s",
                     result.get("id"))
        return result

    async def get_dataset_versions(
        self,
        identifier: str,
        page_size: Optional[int] = None,
        cursor: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        List visible versions of a dataset from newest to oldest.

        Args:
            identifier: The ESS-DIVE unique identifier or DOI
            page_size: Optional number of versions to return (API default: 10, max: 10)
            cursor: Optional opaque cursor from a previous versions response

        Returns:
            API response containing dataset versions and pagination cursors

        Examples:
            await client.get_dataset_versions("doi:10.15485/2453885", page_size=5)
            await client.get_dataset_versions(
                "ess-dive-9ea5fe57db73c90-20241024T093714082510",
                cursor="opaque-cursor",
            )
        """
        params: Dict[str, Any] = {}
        if page_size is not None:
            params["pageSize"] = page_size
        if cursor:
            params["cursor"] = cursor

        url = self._package_url(identifier, "/versions")
        LOGGER.debug(
            "ESS-DIVE get dataset versions request url=%s params=%s", url, params)

        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as client:
            response = await client.get(
                url,
                params=params or None,
                headers=self._get_headers(),
            )
            response.raise_for_status()
            result = response.json()

        LOGGER.debug(
            "ESS-DIVE get dataset versions response total=%s count=%s",
            result.get("total"),
            len(result.get("result", [])) if isinstance(
                result, dict) else "n/a",
        )
        return result

    async def get_dataset_status(self, identifier: str) -> Dict[str, Any]:
        """
        Get the status of a dataset (DOI minting, publication, visibility).

        Args:
            identifier: The ESS-DIVE unique identifier

        Returns:
            API response containing dataset status information

        Examples:
            await client.get_dataset_status("ess-dive-9ea5fe57db73c90-20241024T093714082510")
        """
        url = self._package_url(identifier, "/status")
        LOGGER.debug("ESS-DIVE get dataset status request url=%s", url)

        result = await self._get_json(url)
        LOGGER.debug(
            "ESS-DIVE get dataset status response keys=%s", list(result.keys()))
        return result

    async def get_dataset_permissions(self, identifier: str) -> Dict[str, Any]:
        """
        Get sharing permissions for a dataset.

        Args:
            identifier: The ESS-DIVE unique identifier

        Returns:
            API response containing dataset permissions information

        Examples:
            await client.get_dataset_permissions("ess-dive-9ea5fe57db73c90-20241024T093714082510")
        """
        url = self._package_url(identifier, "/share")
        LOGGER.debug("ESS-DIVE get dataset permissions request url=%s", url)

        result = await self._get_json(url)
        LOGGER.debug(
            "ESS-DIVE get dataset permissions response keys=%s", list(result.keys()))
        return result

    def format_results(
        self, results: Dict[str, Any], format_type: str = "summary"
    ) -> Union[str, Dict[str, Any]]:
        """
        Format search results into a more readable format.

        Args:
            results: The API response to format
            format_type: Type of formatting ('summary', 'detailed', 'raw')

        Returns:
            Formatted results as string or dict
        """
        if format_type == "raw":
            return results

        if "result" not in results:
            return "No results found or invalid response format."

        datasets = results["result"]
        total = results.get("total", 0)
        filtering = results.get("filtering")
        query = results.get("query", {}) if isinstance(
            results.get("query"), dict) else {}
        sort_value = query.get("sort")
        user_note = _format_result_user_note(results.get("user"))

        if filtering:
            native_total = filtering.get("native_total")
            scanned_results = filtering.get("scanned_results")
            header = (
                f"Found {total} datasets after local metadata filtering. "
                f"Scanned {scanned_results} API results"
            )
            if native_total is not None:
                header += f" from {native_total} native matches"
            header += ":\n\n"
        else:
            header = f"Found {total} datasets. Showing {len(datasets)} results:\n\n"

        if sort_value:
            header += f"Sort: {sort_value}\n\n"
        if user_note:
            header += f"{user_note}\n\n"

        if format_type == "summary":
            summary = header

            for i, dataset in enumerate(datasets, 1):
                ds_data = dataset.get("dataset", {})
                summary += f"{i}. {ds_data.get('name', 'Untitled')}\n"
                summary += f"   ID: {dataset.get('id', 'Unknown')}\n"
                if _should_show_is_public(dataset.get("isPublic"), results.get("user")):
                    summary += f"   isPublic: {dataset.get('isPublic')}\n"
                summary += f"   Published: {ds_data.get('datePublished', 'Unknown')}\n"
                links = [
                    _markdown_link("View dataset", dataset.get("viewUrl")),
                    _markdown_link("API record", dataset.get("url")),
                    _markdown_link("Previous version", dataset.get("previous")),
                    _markdown_link("Next version", dataset.get("next")),
                ]
                links = [link for link in links if link]
                if links:
                    summary += f"   Links: {' | '.join(links)}\n"
                if i < len(datasets):
                    summary += "\n"

            return summary

        elif format_type == "detailed":
            detailed = header

            for i, dataset in enumerate(datasets, 1):
                ds_data = dataset.get("dataset", {})
                detailed += f"{i}. {ds_data.get('name', 'Untitled')}\n"
                detailed += f"   ID: {dataset.get('id', 'Unknown')}\n"
                if _should_show_is_public(dataset.get("isPublic"), results.get("user")):
                    detailed += f"   isPublic: {dataset.get('isPublic')}\n"
                if dataset.get("dateUploaded"):
                    detailed += f"   dateUploaded: {dataset.get('dateUploaded')}\n"
                if dataset.get("dateModified"):
                    detailed += f"   dateModified: {dataset.get('dateModified')}\n"
                detailed += f"   Published: {ds_data.get('datePublished', 'Unknown')}\n"
                links = [
                    _markdown_link("View dataset", dataset.get("viewUrl")),
                    _markdown_link("API record", dataset.get("url")),
                    _markdown_link("Previous version", dataset.get("previous")),
                    _markdown_link("Next version", dataset.get("next")),
                ]
                links = [link for link in links if link]
                if links:
                    detailed += f"   Links: {' | '.join(links)}\n"

                # Add description if available
                description = ds_data.get("description", "")
                if isinstance(description, list):
                    description = " ".join(description)
                if description:
                    detailed += f"   Description: {description[:300]}{'...' if len(description) > 300 else ''}\n"

                # Add keywords if available
                keywords = ds_data.get("keywords", [])
                if keywords:
                    if isinstance(keywords, str):
                        keywords = [keywords]
                    detailed += f"   Keywords: {', '.join(keywords)}\n"

                alternate_names = _as_string_list(ds_data.get("alternateName"))
                if alternate_names:
                    detailed += f"   Alternate Names: {', '.join(alternate_names)}\n"

                temporal_coverage = _summarize_temporal_coverage(
                    ds_data.get("temporalCoverage")
                )
                if temporal_coverage:
                    detailed += f"   Temporal Coverage: {temporal_coverage}\n"

                spatial_coverage = _summarize_spatial_coverage(
                    ds_data.get("spatialCoverage")
                )
                if spatial_coverage:
                    detailed += (
                        f"   Spatial Coverage: {'; '.join(spatial_coverage[:2])}\n"
                    )

                variables = _as_string_list(ds_data.get("variableMeasured"))
                if variables:
                    detailed += f"   Variables Measured: {', '.join(variables[:6])}\n"

                techniques = _as_string_list(
                    ds_data.get("measurementTechnique"))
                if techniques:
                    detailed += (
                        f"   Measurement Techniques: "
                        f"{'; '.join(_truncate_text(item, 160) for item in techniques[:2])}\n"
                    )

                funders = []
                for funder in _as_list(ds_data.get("funder")):
                    if isinstance(funder, dict):
                        funders.extend(_as_string_list(funder.get("name")))
                    else:
                        funders.extend(_as_string_list(funder))
                if funders:
                    detailed += f"   Funders: {', '.join(funders)}\n"

                license_value = ds_data.get("license")
                if license_value:
                    detailed += f"   License: {license_value}\n"

                providers = _summarize_provider(ds_data.get("provider"))
                if providers:
                    detailed += f"   Provider: {'; '.join(providers)}\n"

                awards = _as_string_list(ds_data.get("award"))
                if awards:
                    detailed += f"   Award: {', '.join(awards)}\n"

                citation = dataset.get("citation")
                if citation:
                    detailed += f"   citation: {citation}\n"

                if i < len(datasets):
                    detailed += "\n"

            return detailed

        return results

    def format_dataset(
        self, result: Dict[str, Any], format_type: str = "detailed"
    ) -> Union[str, Dict[str, Any]]:
        """
        Format a single dataset record into a readable summary.

        Args:
            result: The API response from GET /packages/{identifier}
            format_type: Type of formatting ('summary', 'detailed', 'raw')

        Returns:
            Formatted dataset metadata as string or dict
        """
        if format_type == "raw":
            return result

        dataset = result.get("dataset")
        if not isinstance(dataset, dict):
            return "No dataset found or invalid response format."

        name = dataset.get("name", "Untitled")
        description = dataset.get("description", "")
        if isinstance(description, list):
            description = " ".join(description)

        doi = dataset.get("@id") or dataset.get("doi")
        content = f"# {name}\n\n"
        content += f"**id**: {result.get('id', 'Unknown')}\n"
        if doi:
            content += f"**doi**: {doi}\n"
        links = [
            _markdown_link("View dataset", result.get("viewUrl")),
            _markdown_link("API record", result.get("url")),
            _markdown_link("Previous version", result.get("previous")),
            _markdown_link("Next version", result.get("next")),
        ]
        links = [link for link in links if link]
        if links:
            content += f"**links**: {' | '.join(links)}\n"
        if result.get("dateUploaded"):
            content += f"**dateUploaded**: {result.get('dateUploaded')}\n"
        if result.get("dateModified"):
            content += f"**dateModified**: {result.get('dateModified')}\n"
        if "isPublic" in result:
            content += f"**isPublic**: {result.get('isPublic')}\n"
        if dataset.get("datePublished"):
            content += f"**datePublished**: {dataset.get('datePublished')}\n"
        if result.get("citation"):
            content += f"**citation**: {result.get('citation')}\n"
        content += "\n"

        if format_type == "summary":
            if description:
                content += f"## Description\n{description}\n"
            return content.rstrip()

        if description:
            content += f"## Description\n{description}\n\n"

        creators = dataset.get("creator", [])
        if not isinstance(creators, list):
            creators = [creators]

        if creators:
            content += "## Creators\n"
            for creator in creators:
                given_name = creator.get("givenName", "")
                family_name = creator.get("familyName", "")
                creator_name = f"{given_name} {family_name}".strip()
                affiliation = creator.get("affiliation", "")

                content += f"- {creator_name}"
                if affiliation:
                    content += f" ({affiliation})"
                content += "\n"
            content += "\n"

        keywords = dataset.get("keywords", [])
        if not isinstance(keywords, list):
            keywords = [keywords]

        if keywords:
            content += "## Keywords\n"
            content += ", ".join(keywords)
            content += "\n\n"

        alternate_names = _as_string_list(dataset.get("alternateName"))
        if alternate_names:
            content += "## Alternate Names / Identifiers\n"
            content += ", ".join(alternate_names)
            content += "\n\n"

        temporal_coverage = _summarize_temporal_coverage(
            dataset.get("temporalCoverage")
        )
        if temporal_coverage:
            content += "## Temporal Coverage\n"
            content += f"{temporal_coverage}\n\n"

        spatial_coverage = _summarize_spatial_coverage(
            dataset.get("spatialCoverage")
        )
        if spatial_coverage:
            content += "## Spatial Coverage\n"
            for location in spatial_coverage:
                content += f"- {location}\n"
            content += "\n"

        variables_measured = _as_string_list(dataset.get("variableMeasured"))
        if variables_measured:
            content += "## Variables Measured\n"
            content += ", ".join(variables_measured)
            content += "\n\n"

        measurement_techniques = _as_string_list(
            dataset.get("measurementTechnique")
        )
        if measurement_techniques:
            content += "## Measurement Techniques\n"
            for technique in measurement_techniques:
                content += f"- {_truncate_text(technique, 500)}\n"
            content += "\n"

        funders = []
        for funder in _as_list(dataset.get("funder")):
            if isinstance(funder, dict):
                funder_name = ", ".join(_organization_search_strings(funder))
                if funder_name:
                    funders.append(funder_name)
            else:
                funders.extend(_as_string_list(funder))
        if funders:
            content += "## Funders\n"
            for funder in funders:
                content += f"- {funder}\n"
            content += "\n"

        editor = dataset.get("editor")
        if isinstance(editor, dict):
            editor_details = _person_search_strings(editor)
            if editor_details:
                content += "## Contact\n"
                content += f"- {', '.join(editor_details)}\n\n"

        license_value = dataset.get("license")
        if license_value:
            content += "## License\n"
            content += f"{license_value}\n\n"

        providers = _summarize_provider(dataset.get("provider"))
        if providers:
            content += "## Provider\n"
            for provider in providers:
                content += f"- {provider}\n"
            content += "\n"

        awards = _as_string_list(dataset.get("award"))
        if awards:
            content += "## Award\n"
            for award in awards:
                content += f"- {award}\n"
            content += "\n"

        distribution = dataset.get("distribution", [])
        if distribution:
            content += "## Data Files\n"
            for file in distribution:
                file_name = file.get("name", "Unknown")
                file_size = file.get("contentSize", 0)
                file_format = file.get("encodingFormat", "Unknown")
                file_url = file.get("contentUrl", "Unknown")
                file_id = file.get("identifier", "Unknown")
                content += (
                    f"- {file_name} ({file_size} KB, {file_format}) "
                    f"URL: {file_url} ID: {file_id}\n"
                )

        return content

    def format_dataset_versions(
        self, results: Dict[str, Any], format_type: str = "summary"
    ) -> Union[str, Dict[str, Any]]:
        """
        Format dataset version history into a readable summary.

        Args:
            results: The API response to format
            format_type: Type of formatting ('summary', 'detailed', 'raw')

        Returns:
            Formatted version history as string or dict
        """
        if format_type == "raw":
            return results

        if "result" not in results:
            return "No version history found or invalid response format."

        versions = results["result"]
        total = results.get("total", 0)
        user_note = _format_result_user_note(results.get("user"))
        header = (
            f"Found {total} visible dataset versions. "
            f"Showing {len(versions)} results from newest to oldest:\n"
        )
        if user_note:
            header += f"{user_note}\n"

        if format_type == "summary":
            summary = f"{header}\n"

            for i, version in enumerate(versions, 1):
                dataset = version.get("dataset", {})
                doi = dataset.get("@id") or dataset.get("doi")
                summary += f"{i}. {dataset.get('name', 'Untitled')}\n"
                summary += f"   ID: {version.get('id', 'Unknown')}\n"
                if doi:
                    summary += f"   DOI: {doi}\n"
                if _should_show_is_public(version.get("isPublic"), results.get("user")):
                    summary += f"   isPublic: {version.get('isPublic')}\n"
                summary += f"   dateUploaded: {version.get('dateUploaded', 'Unknown')}\n"
                summary += f"   Published: {dataset.get('datePublished', 'Unknown')}\n"
                links = [
                    _markdown_link("View dataset", version.get("viewUrl")),
                    _markdown_link("API record", version.get("url")),
                    _markdown_link("Previous version", version.get("previous")),
                    _markdown_link("Next version", version.get("next")),
                ]
                links = [link for link in links if link]
                if links:
                    summary += f"   Links: {' | '.join(links)}\n"
                if i < len(versions):
                    summary += "\n"

            return summary

        if format_type == "detailed":
            detailed = f"{header}\n"

            for i, version in enumerate(versions, 1):
                dataset = version.get("dataset", {})
                doi = dataset.get("@id") or dataset.get("doi")
                detailed += f"{i}. {dataset.get('name', 'Untitled')}\n"
                detailed += f"   ID: {version.get('id', 'Unknown')}\n"
                if doi:
                    detailed += f"   DOI: {doi}\n"
                detailed += f"   dateUploaded: {version.get('dateUploaded', 'Unknown')}\n"
                detailed += f"   dateModified: {version.get('dateModified', 'Unknown')}\n"
                detailed += f"   Published: {dataset.get('datePublished', 'Unknown')}\n"
                if _should_show_is_public(version.get("isPublic"), results.get("user")):
                    detailed += f"   isPublic: {version.get('isPublic', 'Unknown')}\n"
                links = [
                    _markdown_link("View dataset", version.get("viewUrl")),
                    _markdown_link("API record", version.get("url")),
                    _markdown_link("Previous version", version.get("previous")),
                    _markdown_link("Next version", version.get("next")),
                ]
                links = [link for link in links if link]
                if links:
                    detailed += f"   Links: {' | '.join(links)}\n"

                description = dataset.get("description", "")
                if isinstance(description, list):
                    description = " ".join(description)
                if description:
                    detailed += (
                        f"   Description: {description[:300]}"
                        f"{'...' if len(description) > 300 else ''}\n"
                    )

                citation = version.get("citation")
                if citation:
                    detailed += f"   citation: {citation}\n"

                if version.get("next"):
                    detailed += f"   Newer Version URL: {version['next']}\n"
                if version.get("previous"):
                    detailed += f"   Older Version URL: {version['previous']}\n"

                if i < len(versions):
                    detailed += "\n"

            return detailed

        return results


# Helper functions for identifier conversion
def _normalize_doi(identifier: str) -> str:
    """Normalize a DOI to the standard format (doi:10.xxxx/...).

    Args:
        identifier: A DOI in any common format

    Returns:
        Normalized DOI in the format doi:10.xxxx/...

    Examples:
        >>> _normalize_doi("10.15485/2453885")
        'doi:10.15485/2453885'
        >>> _normalize_doi("https://doi.org/10.15485/2453885")
        'doi:10.15485/2453885'
    """
    identifier = identifier.strip()

    # Remove common DOI URL prefixes
    if identifier.startswith("https://doi.org/"):
        identifier = identifier.replace("https://doi.org/", "")
    elif identifier.startswith("http://doi.org/"):
        identifier = identifier.replace("http://doi.org/", "")
    elif identifier.startswith("doi.org/"):
        identifier = identifier.replace("doi.org/", "")

    # Add doi: prefix if not present
    if not identifier.startswith("doi:"):
        identifier = f"doi:{identifier}"

    return identifier


def doi_to_essdive_id(doi: str, api_token: Optional[str] = None) -> str:
    """Convert a DOI to an ESS-DIVE dataset ID by querying the ESS-DIVE API.

    Args:
        doi: A DOI in any common format (with or without doi: prefix or URLs)
        api_token: Optional API token for authenticated requests

    Returns:
        The ESS-DIVE dataset ID

    Examples:
        >>> doi_to_essdive_id("10.15485/2453885", api_token="TOKEN")
        'ess-dive-...'

    Raises:
        ValueError: If the DOI is not found or API call fails
    """
    # Normalize the DOI
    normalized_doi = _normalize_doi(doi)
    LOGGER.debug(
        "Converting DOI to ESS-DIVE ID doi=%s normalized=%s", doi, normalized_doi)

    # Create client and fetch dataset metadata
    client = ESSDiveClient(api_token=api_token)

    try:
        result = _run_in_new_event_loop(client.get_dataset(normalized_doi))
        essdive_id = result.get("id")
        if not essdive_id:
            raise ValueError(
                f"No dataset ID found in response for DOI: {doi}")
        return essdive_id
    except Exception as e:
        raise ValueError(
            f"Failed to convert DOI {doi} to ESS-DIVE ID: {str(e)}") from e


def essdive_id_to_doi(essdive_id: str, api_token: Optional[str] = None) -> str:
    """Convert an ESS-DIVE dataset ID to a DOI by querying the ESS-DIVE API.

    Args:
        essdive_id: An ESS-DIVE dataset identifier
        api_token: Optional API token for authenticated requests

    Returns:
        The DOI in the format doi:10.xxxx/...

    Examples:
        >>> essdive_id_to_doi("ess-dive-9ea5fe57db73c90-20241024T093714082510", api_token="TOKEN")
        'doi:10.15485/2453885'

    Raises:
        ValueError: If the ESS-DIVE ID is not found or API call fails
    """
    client = ESSDiveClient(api_token=api_token)
    LOGGER.debug("Converting ESS-DIVE ID to DOI essdive_id=%s", essdive_id)

    try:
        result = _run_in_new_event_loop(client.get_dataset(essdive_id))
        dataset_meta = result.get("dataset", {})
        # ESS-DIVE currently returns DOI in dataset["@id"]; keep "doi" as fallback.
        doi = dataset_meta.get("@id") or dataset_meta.get("doi")
        if not doi:
            raise ValueError(
                f"No DOI found in metadata for ESS-DIVE ID: {essdive_id}")
        # Normalize the DOI
        return _normalize_doi(doi)
    except Exception as e:
        raise ValueError(
            f"Failed to convert ESS-DIVE ID {essdive_id} to DOI: {str(e)}") from e


# ESS-DeepDive API functions
ESS_DEEPDIVE_BASE_URL = "https://fusion.ess-dive.lbl.gov/api/v1/deepdive"


def search_ess_deepdive(
    field_name: Optional[str] = None,
    field_definition: Optional[str] = None,
    field_value_text: Optional[str] = None,
    field_value_numeric: Optional[Union[int, float]] = None,
    field_value_date: Optional[str] = None,
    record_count_min: Optional[int] = None,
    record_count_max: Optional[int] = None,
    doi: Optional[List[str]] = None,
    row_start: int = 1,
    page_size: int = 25,
) -> Dict[str, Any]:
    """
    Search the ESS-DeepDive fusion database for data fields and values.

    Args:
        field_name: Search for a specific field name (max 100 chars)
        field_definition: Search field definitions (max 100 chars)
        field_value_text: Search for text field values (case insensitive)
        field_value_numeric: Filter by numeric value (between min and max summary values)
        field_value_date: Filter by date value (yyyy-mm-dd or yyyy-mm-ddTHH:MM:SS)
        record_count_min: Filter by minimum record count
        record_count_max: Filter by maximum record count
        doi: Filter by one or more DOIs (up to 100)
        row_start: The starting row for pagination (default: 1)
        page_size: Number of results per page (max: 100, default: 25)

    Returns:
        API response containing search results with field metadata

    Examples:
        >>> search_ess_deepdive(field_name="temperature", record_count_min=100)
        {...}
    """
    params: Dict[str, Any] = {
        "rowStart": row_start,
        "pageSize": min(page_size, 100),  # Enforce max limit
    }

    if field_name:
        params["fieldName"] = field_name
    if field_definition:
        params["fieldDefinition"] = field_definition
    if field_value_text:
        params["fieldValueText"] = field_value_text
    if field_value_numeric is not None:
        params["fieldValueNumeric"] = field_value_numeric
    if field_value_date:
        params["fieldValueDate"] = field_value_date
    if record_count_min is not None:
        params["recordCountMin"] = record_count_min
    if record_count_max is not None:
        params["recordCountMax"] = record_count_max
    if doi:
        params["doi"] = doi[:100]  # Enforce max 100 DOIs

    LOGGER.debug("ESS-DeepDive search request url=%s params=%s",
                 ESS_DEEPDIVE_BASE_URL, params)
    response = requests.get(
        ESS_DEEPDIVE_BASE_URL,
        params=params,
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    result = response.json()
    LOGGER.debug(
        "ESS-DeepDive search response pageCount=%s count=%s",
        result.get("pageCount"),
        len(result.get("results", [])) if isinstance(result, dict) else "n/a",
    )
    return result


def get_ess_deepdive_dataset(doi: str, file_path: str) -> Dict[str, Any]:
    """
    Get detailed field information for a specific dataset file in ESS-DeepDive.

    Args:
        doi: The DOI of the dataset (must include 'doi:' prefix, format: doi:10.xxxx/...)
        file_path: The dataset file path

    Returns:
        API response containing detailed field information

    Examples:
        >>> get_ess_deepdive_dataset("10.15485/2453885", "dataset.zip/data.csv")
        {...}
    """
    # Ensure DOI has the correct format
    if not doi.startswith("doi:"):
        doi = f"doi:{doi}"

    # Construct the URL with the doi:file_path format
    url = f"{ESS_DEEPDIVE_BASE_URL}/{doi}:{file_path}"
    LOGGER.debug("ESS-DeepDive dataset request url=%s", url)

    response = requests.get(url, timeout=REQUEST_TIMEOUT_SECONDS)
    response.raise_for_status()
    result = response.json()
    LOGGER.debug(
        "ESS-DeepDive dataset response doi=%s fields=%s",
        result.get("doi") if isinstance(result, dict) else "n/a",
        len(result.get("fields", [])) if isinstance(result, dict) else "n/a",
    )
    return result


def get_ess_deepdive_file(doi: str, file_path: str) -> Dict[str, Any]:
    """
    Retrieve detailed information about a specific file from ESS-DeepDive (Get-Dataset-File endpoint).

    This is an alias for get_ess_deepdive_dataset and returns the same information,
    including all field metadata and download URLs for the file.

    Args:
        doi: The DOI of the dataset (with or without 'doi:' prefix)
        file_path: The file path within the dataset

    Returns:
        API response containing file information, fields, and download metadata

    Examples:
        >>> get_ess_deepdive_file("doi:10.15485/2453885", "dataset.zip/data.csv")
        {...}
    """
    return get_ess_deepdive_dataset(doi, file_path)


def _summarize_essdeepdive_file_response(result: Dict[str, Any]) -> Dict[str, Any]:
    """Build a normalized summary view for ESS-DeepDive file responses."""
    summary = {
        "doi": result.get("doi"),
        # Current API uses data_file; keep legacy key fallback.
        "file_name": result.get("data_file") or result.get("file_name"),
        # Current API commonly returns data_file; keep explicit file_path fallback.
        "file_path": result.get("file_path") or result.get("data_file"),
    }

    fields = result.get("fields")
    if isinstance(fields, list):
        summary["total_fields"] = len(fields)
        summary["field_names"] = [f.get("fieldName") for f in fields]

    download = result.get("data_download")
    if isinstance(download, dict):
        summary["download_info"] = {
            "content_size_bytes": download.get("contentSize"),
            "encoding_format": download.get("encodingFormat")
            or download.get("encoding_format"),
            "content_url": download.get("contentUrl")
            or download.get("contentURL"),
        }

    return summary


def get_api_key(
    api_key: Optional[str] = None, token_file: Optional[str] = None
) -> Optional[str]:
    """
    Get an optional ESS-DIVE API token from a parameter, token file, or environment.

    Args:
        api_key: Optional API key provided directly.
        token_file: Optional path to a file containing the API key.

    Returns:
        The API key string, or None when no token is configured.
    """
    if api_key is None and token_file:
        try:
            with open(token_file, "r", encoding="utf-8") as handle:
                api_key = handle.read().strip()
        except OSError as exc:
            raise ValueError(
                f"Could not read ESS-DIVE token file: {token_file}"
            ) from exc

    if not api_key:
        api_key = os.getenv("ESSDIVE_API_TOKEN")

    return api_key or None


def _resolve_startup_api_token(
    api_key: Optional[str] = None,
    token_file: Optional[str] = None,
) -> Optional[str]:
    """Resolve startup auth config, falling back to anonymous mode on file errors."""
    try:
        return get_api_key(api_key, token_file=token_file)
    except ValueError as exc:
        LOGGER.warning(
            "%s Starting without ESS-DIVE auth; public dataset reads will still work.",
            exc,
        )
        return None


def main():
    """Main entry point for the MCP server."""
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description="Run an ESS-DIVE MCP server")
    parser.add_argument(
        "--token",
        "-t",
        help="Optional ESS-DIVE API token for authenticated/private-data requests (can also use ESSDIVE_API_TOKEN env var)",
    )
    parser.add_argument(
        "--token-file",
        help="Path to a file containing an optional ESS-DIVE API token",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging and include tracebacks in tool error responses",
    )
    args = parser.parse_args()

    verbose_mode = args.verbose or _is_truthy(os.getenv("ESSDIVE_MCP_VERBOSE"))
    _configure_logging(verbose_mode)

    api_token = _resolve_startup_api_token(args.token, token_file=args.token_file)

    LOGGER.info(
        "Starting ESS-DIVE MCP server (verbose=%s, authenticated=%s)",
        verbose_mode,
        bool(api_token),
    )

    # Create a FastMCP server
    server = FastMCP("essdive_mcp")

    # Create a client for the ESS-DIVE API with the provided token
    client = ESSDiveClient(api_token=api_token)
    pagination_store = PaginationStateStore()

    # Register tool functions
    @server.tool(name="search-datasets", description="Search for datasets in ESS-DIVE")
    async def search_datasets(
        query: Optional[str] = None,
        creator: Optional[str] = None,
        provider_name: Optional[str] = None,
        date_published: Optional[str] = None,
        begin_date: Optional[str] = None,
        end_date: Optional[str] = None,
        keywords: Optional[Union[str, List[str]]] = None,
        sort: Optional[str] = None,
        bbox: Optional[Union[str, List[float]]] = None,
        lat: Optional[float] = None,
        lon: Optional[float] = None,
        radius: Optional[float] = None,
        creator_affiliation: Optional[Union[str, List[str]]] = None,
        variable_measured: Optional[Union[str, List[str]]] = None,
        measurement_technique: Optional[Union[str, List[str]]] = None,
        funder: Optional[Union[str, List[str]]] = None,
        license: Optional[Union[str, List[str]]] = None,
        alternate_name: Optional[Union[str, List[str]]] = None,
        editor: Optional[Union[str, List[str]]] = None,
        file_format: Optional[Union[str, List[str]]] = None,
        file_name: Optional[Union[str, List[str]]] = None,
        file_url: Optional[Union[str, List[str]]] = None,
        cursor: Optional[str] = None,
        row_start: Optional[int] = None,
        page_size: Optional[int] = None,
        format: str = "summary",
        ctx: Context = None,
    ) -> str:
        """
        Search for datasets in the ESS-DIVE repository.

        Args:
            query: Search query text (full-text search)
            creator: Filter by dataset creator
            provider_name: Filter by dataset project/provider
            date_published: Filter by publication date (e.g., "[2016 TO 2023]")
            begin_date: Temporal coverage window start date (YYYY, YYYY-MM, or YYYY-MM-DD)
            end_date: Temporal coverage window end date (YYYY, YYYY-MM, or YYYY-MM-DD)
            keywords: Search for datasets with specific keywords (string or list of strings)
            sort: Optional sort string, e.g. "name:asc" or "dateUploaded:desc,authorLastName:asc"
            bbox: Bounding box search as "min_lat,min_lon,max_lat,max_lon" or [min_lat, min_lon, max_lat, max_lon]
            lat: Latitude for point-based nearby search
            lon: Longitude for point-based nearby search
            radius: Search radius in meters for point-based nearby search
            creator_affiliation: Local post-filter on creator affiliation text
            variable_measured: Local post-filter on variableMeasured values
            measurement_technique: Local post-filter on measurementTechnique text
            funder: Local post-filter on funder names/IDs
            license: Local post-filter on dataset license text/URL
            alternate_name: Local post-filter on alternateName values
            editor: Local post-filter on dataset contact/editor metadata
            file_format: Local post-filter on distribution encodingFormat values
            file_name: Local post-filter on distribution file names
            file_url: Local post-filter on distribution content URLs
            cursor: Opaque cursor for a follow-up page of search results
            row_start: Legacy row number to start on when not using cursor pagination
            page_size: Number of results per page; omit on cursor follow-up unless it matches the cursor
            format: Format of the results (summary, detailed, raw)

        Examples:
            search-datasets with query="soil carbon" and page_size=10
            search-datasets with creator="Smith" and provider_name="NGEE Arctic"
            search-datasets with begin_date="2020" and end_date="2021-06" and format="detailed"
            search-datasets with query="soil carbon" and sort="name:asc"
            search-datasets with query="BIONTE" and cursor="opaque-cursor"
            search-datasets with bbox=[34.0, -119.0, 35.0, -117.0]
            search-datasets with lat=37.7749 and lon=-122.4194 and radius=5000
            search-datasets with query="snowmelt" and creator_affiliation="Pennsylvania"
            search-datasets with provider_name="SPRUCE" and variable_measured=["temperature", "CO2"]

        Returns:
            Formatted search results
        """
        LOGGER.debug(
            "Tool search-datasets called query=%r creator=%r provider_name=%r begin_date=%r end_date=%r sort=%r cursor=%r bbox=%r lat=%r lon=%r radius=%r local_filters=%r row_start=%s page_size=%s format=%s",
            query,
            creator,
            provider_name,
            begin_date,
            end_date,
            sort,
            cursor,
            bbox,
            lat,
            lon,
            radius,
            {
                "creator_affiliation": creator_affiliation,
                "variable_measured": variable_measured,
                "measurement_technique": measurement_technique,
                "funder": funder,
                "license": license,
                "alternate_name": alternate_name,
                "editor": editor,
                "file_format": file_format,
                "file_name": file_name,
                "file_url": file_url,
            },
            row_start,
            page_size,
            format,
        )
        try:
            # Convert keywords to list if it's a string
            keywords_list = None
            if keywords:
                if isinstance(keywords, str):
                    keywords_list = [keywords]
                else:
                    keywords_list = keywords

            local_filters = {
                "creator_affiliation": _normalize_local_filter_values(creator_affiliation),
                "variable_measured": _normalize_local_filter_values(variable_measured),
                "measurement_technique": _normalize_local_filter_values(measurement_technique),
                "funder": _normalize_local_filter_values(funder),
                "license": _normalize_local_filter_values(license),
                "alternate_name": _normalize_local_filter_values(alternate_name),
                "editor": _normalize_local_filter_values(editor),
                "file_format": _normalize_local_filter_values(file_format),
                "file_name": _normalize_local_filter_values(file_name),
                "file_url": _normalize_local_filter_values(file_url),
            }

            # If query is provided but no specific text search parameter,
            # use query as the text search string.
            text = query if query else None

            search_kwargs = {
                "row_start": row_start,
                "page_size": page_size,
                "cursor": cursor,
                "is_public": _default_dataset_search_is_public(client.api_token),
                "creator": creator,
                "provider_name": provider_name,
                "text": text,
                "date_published": date_published,
                "begin_date": begin_date,
                "end_date": end_date,
                "keywords": keywords_list,
                "sort": sort,
                "bbox": bbox,
                "lat": lat,
                "lon": lon,
                "radius": radius,
            }
            result = await _execute_dataset_search_request(
                client,
                search_kwargs=search_kwargs,
                local_filters=local_filters,
            )
            pagination_store.save_search(
                session_id=ctx.session_id,
                search_kwargs=search_kwargs,
                local_filters=local_filters,
                format_type=format,
                result=result,
            )

            # Format the results
            formatted = client.format_results(result, format)
            return _render_formatted_output(formatted, format)

        except Exception as exc:
            return _tool_error_response(
                "search-datasets",
                exc,
                verbose=verbose_mode,
                context=_context_without_none(
                    {
                        "query": query,
                        "creator": creator,
                        "provider_name": provider_name,
                        "date_published": date_published,
                        "begin_date": begin_date,
                        "end_date": end_date,
                        "sort": sort,
                        "cursor": cursor,
                        "bbox": bbox,
                        "lat": lat,
                        "lon": lon,
                        "radius": radius,
                        "creator_affiliation": creator_affiliation,
                        "variable_measured": variable_measured,
                        "measurement_technique": measurement_technique,
                        "funder": funder,
                        "license": license,
                        "alternate_name": alternate_name,
                        "editor": editor,
                        "file_format": file_format,
                        "file_name": file_name,
                        "file_url": file_url,
                        "row_start": row_start,
                        "page_size": page_size,
                        "format": format,
                    }
                ),
            )

    @server.tool(
        name="next-search-page",
        description="Show the next page of the most recent dataset search",
    )
    async def next_search_page(format: Optional[str] = None, ctx: Context = None) -> str:
        """
        Show the next page of the most recent dataset search.

        This tool reuses the last dataset-search filters and paging context stored by
        `search-datasets`, so callers do not need to manage pagination cursors directly.

        Args:
            format: Optional override for the output format (summary, detailed, raw)

        Returns:
            Formatted next page of dataset search results
        """
        LOGGER.debug("Tool next-search-page called format=%s", format)
        try:
            search_kwargs, local_filters, format_type = (
                pagination_store.get_search_followup(
                    ctx.session_id, "next", format_override=format
                )
            )
            result = await _execute_dataset_search_request(
                client,
                search_kwargs=search_kwargs,
                local_filters=local_filters,
            )
            pagination_store.save_search(
                session_id=ctx.session_id,
                search_kwargs=search_kwargs,
                local_filters=local_filters,
                format_type=format_type,
                result=result,
            )
            formatted = client.format_results(result, format_type)
            return _render_formatted_output(formatted, format_type)
        except Exception as exc:
            return _tool_error_response(
                "next-search-page",
                exc,
                verbose=verbose_mode,
                context=_context_without_none({"format": format}),
            )

    @server.tool(
        name="previous-search-page",
        description="Show the previous page of the most recent dataset search",
    )
    async def previous_search_page(format: Optional[str] = None, ctx: Context = None) -> str:
        """
        Show the previous page of the most recent dataset search.

        This tool reuses the last dataset-search filters and paging context stored by
        `search-datasets`, so callers do not need to manage pagination cursors directly.

        Args:
            format: Optional override for the output format (summary, detailed, raw)

        Returns:
            Formatted previous page of dataset search results
        """
        LOGGER.debug("Tool previous-search-page called format=%s", format)
        try:
            search_kwargs, local_filters, format_type = (
                pagination_store.get_search_followup(
                    ctx.session_id, "previous", format_override=format)
            )
            result = await _execute_dataset_search_request(
                client,
                search_kwargs=search_kwargs,
                local_filters=local_filters,
            )
            pagination_store.save_search(
                session_id=ctx.session_id,
                search_kwargs=search_kwargs,
                local_filters=local_filters,
                format_type=format_type,
                result=result,
            )
            formatted = client.format_results(result, format_type)
            return _render_formatted_output(formatted, format_type)
        except Exception as exc:
            return _tool_error_response(
                "previous-search-page",
                exc,
                verbose=verbose_mode,
                context=_context_without_none({"format": format}),
            )

    @server.tool(
        name="get-dataset",
        description="Get detailed information about a specific dataset",
    )
    async def get_dataset(id: str, format: str = "detailed") -> str:
        """
        Get detailed information about a specific dataset.

        Args:
            id: ESS-DIVE dataset identifier
            format: Format of the results (summary, detailed, raw)

        Examples:
            get-dataset with id="ess-dive-9ea5fe57db73c90-20241024T093714082510"
            get-dataset with id="doi:10.15485/2529445" and format="raw"

        Returns:
            Formatted dataset information
        """
        LOGGER.debug("Tool get-dataset called id=%s format=%s", id, format)
        try:
            result = await client.get_dataset(id)
            formatted = client.format_dataset(result, format)
            if format == "raw":
                return json.dumps(formatted, indent=2)
            if isinstance(formatted, dict):
                return json.dumps(formatted, indent=2)
            return str(formatted)

        except Exception as exc:
            return _tool_error_response(
                "get-dataset",
                exc,
                verbose=verbose_mode,
                context=_context_without_none({"id": id, "format": format}),
            )

    @server.tool(
        name="get-dataset-status",
        description="Get publication/workflow status information for a specific dataset",
    )
    async def get_dataset_status_tool(id: str) -> str:
        """
        Get workflow/status information for a dataset from the status endpoint.

        Use this tool when the user explicitly asks for a dataset's status rather than
        its general metadata. For multiple datasets, call the tool once per identifier.
        This endpoint may require an ESS-DIVE API token and appropriate dataset access.

        Args:
            id: ESS-DIVE dataset identifier

        Examples:
            get-dataset-status with id="ess-dive-f78cb03d11550da-20260309T160313214"

        Returns:
            JSON string containing the dataset status response
        """
        LOGGER.debug("Tool get-dataset-status called id=%s", id)
        try:
            result = await client.get_dataset_status(id)
            return json.dumps(result, indent=2)
        except Exception as exc:
            return _tool_error_response(
                "get-dataset-status",
                exc,
                verbose=verbose_mode,
                context={"id": id},
            )

    @server.tool(
        name="get-dataset-versions",
        description="List visible versions of a specific dataset from newest to oldest",
    )
    async def get_dataset_versions_tool(
        id: str,
        page_size: Optional[int] = None,
        cursor: Optional[str] = None,
        format: str = "summary",
        ctx: Context = None,
    ) -> str:
        """
        List visible versions for a dataset from newest to oldest.

        Args:
            id: ESS-DIVE dataset identifier or DOI
            page_size: Optional number of versions to return (API default: 10, max: 10)
            cursor: Optional opaque cursor from a previous versions response
            format: Format of the results (summary, detailed, raw)

        Examples:
            get-dataset-versions with id="doi:10.15485/2529445"
            get-dataset-versions with id="doi:10.15485/2529445" and page_size=2
            get-dataset-versions with id="doi:10.15485/2529445" and cursor="opaque-cursor"

        Returns:
            Formatted dataset version history
        """
        LOGGER.debug(
            "Tool get-dataset-versions called id=%s page_size=%s cursor=%r format=%s",
            id,
            page_size,
            cursor,
            format,
        )
        try:
            result = await client.get_dataset_versions(
                id,
                page_size=page_size,
                cursor=cursor,
            )
            pagination_store.save_versions(
                session_id=ctx.session_id,
                identifier=id,
                format_type=format,
                result=result,
            )
            formatted = client.format_dataset_versions(result, format)
            return _render_formatted_output(formatted, format)

        except Exception as exc:
            return _tool_error_response(
                "get-dataset-versions",
                exc,
                verbose=verbose_mode,
                context=_context_without_none(
                    {
                        "id": id,
                        "page_size": page_size,
                        "cursor": cursor,
                        "format": format,
                    }
                ),
            )

    @server.tool(
        name="next-dataset-versions-page",
        description="Show the next page of the most recent dataset-version history request",
    )
    async def next_dataset_versions_page(format: Optional[str] = None, ctx: Context = None) -> str:
        """
        Show the next page of the most recent dataset-version history request.

        This tool reuses the last version-history paging context stored by
        `get-dataset-versions`, so callers do not need to manage pagination cursors
        directly.

        Args:
            format: Optional override for the output format (summary, detailed, raw)

        Returns:
            Formatted next page of dataset version history
        """
        LOGGER.debug("Tool next-dataset-versions-page called format=%s", format)
        try:
            identifier, cursor_value, format_type = (
                pagination_store.get_versions_followup(
                    ctx.session_id, "next", format_override=format)
            )
            result = await client.get_dataset_versions(
                identifier,
                cursor=cursor_value,
            )
            pagination_store.save_versions(
                session_id=ctx.session_id,
                identifier=identifier,
                format_type=format_type,
                result=result,
            )
            formatted = client.format_dataset_versions(result, format_type)
            return _render_formatted_output(formatted, format_type)
        except Exception as exc:
            return _tool_error_response(
                "next-dataset-versions-page",
                exc,
                verbose=verbose_mode,
                context=_context_without_none({"format": format}),
            )

    @server.tool(
        name="previous-dataset-versions-page",
        description="Show the previous page of the most recent dataset-version history request",
    )
    async def previous_dataset_versions_page(format: Optional[str] = None, ctx: Context = None) -> str:
        """
        Show the previous page of the most recent dataset-version history request.

        This tool reuses the last version-history paging context stored by
        `get-dataset-versions`, so callers do not need to manage pagination cursors
        directly.

        Args:
            format: Optional override for the output format (summary, detailed, raw)

        Returns:
            Formatted previous page of dataset version history
        """
        LOGGER.debug("Tool previous-dataset-versions-page called format=%s", format)
        try:
            identifier, cursor_value, format_type = (
                pagination_store.get_versions_followup(
                    ctx.session_id, "previous", format_override=format)
            )
            result = await client.get_dataset_versions(
                identifier,
                cursor=cursor_value,
            )
            pagination_store.save_versions(
                session_id=ctx.session_id,
                identifier=identifier,
                format_type=format_type,
                result=result,
            )
            formatted = client.format_dataset_versions(result, format_type)
            return _render_formatted_output(formatted, format_type)
        except Exception as exc:
            return _tool_error_response(
                "previous-dataset-versions-page",
                exc,
                verbose=verbose_mode,
                context=_context_without_none({"format": format}),
            )

    @server.tool(
        name="parse-flmd-file",
        description="Parse a File Level Metadata (FLMD) CSV file and extract file descriptions",
    )
    async def parse_flmd_file_tool(content: str) -> str:
        """
        Parse an FLMD (File Level Metadata) file and return a mapping of filenames to descriptions.

        FLMD files are CSV files that contain metadata about data files, with columns for
        filename and file description. This tool normalizes the CSV headers and extracts
        the filename-description mapping.

        Args:
            content: The FLMD CSV file content as a string

        Examples:
            parse-flmd-file with content="filename,file_description\nfile1.csv,Soil moisture\n"

        Returns:
            JSON string mapping filenames to their descriptions
        """
        content_length = len(content) if isinstance(content, str) else None
        LOGGER.debug(
            "Tool parse-flmd-file called content_length=%s", content_length)
        try:
            file_descriptions = parse_flmd_file(content)
            return json.dumps(file_descriptions, indent=2)
        except Exception as exc:
            return _tool_error_response(
                "parse-flmd-file",
                exc,
                verbose=verbose_mode,
                context={"content_length": content_length},
            )

    @server.tool(
        name="get-dataset-permissions",
        description="Get sharing permissions for a specific dataset",
    )
    async def get_dataset_permissions_tool(id: str) -> str:
        """
        Get sharing permissions information for a dataset.

        This endpoint returns the sharing permissions for a dataset, including
        who has access and what permissions they have.

        Args:
            id: ESS-DIVE dataset identifier

        Examples:
            get-dataset-permissions with id="ess-dive-9ea5fe57db73c90-20241024T093714082510"

        Returns:
            JSON string containing the dataset permissions
        """
        LOGGER.debug("Tool get-dataset-permissions called id=%s", id)
        try:
            result = await client.get_dataset_permissions(id)
            return json.dumps(result, indent=2)
        except Exception as exc:
            return _tool_error_response(
                "get-dataset-permissions",
                exc,
                verbose=verbose_mode,
                context={"id": id},
            )

    @server.tool(
        name="lookup-project-portal",
        description="Look up ESS-DIVE-related project names, acronyms, descriptions, and portal URLs",
    )
    def lookup_project_portal_tool(query: Optional[str] = None, limit: int = 10) -> str:
        """
        Look up project background information from the shared ESS-DIVE portal reference list.

        This is useful when users mention an acronym or project name, such as CHESS,
        and the agent needs a quick expansion plus a URL for more context.

        Args:
            query: Optional project acronym, name, or alias to search for
            limit: Maximum number of matches to return

        Examples:
            lookup-project-portal with query="CHESS"
            lookup-project-portal with query="COMPASS-FME"
            lookup-project-portal with query="East River"

        Returns:
            JSON string containing matching project reference entries
        """
        LOGGER.debug(
            "Tool lookup-project-portal called query=%r limit=%s", query, limit)
        try:
            result = search_project_portals(query=query, limit=limit)
            return json.dumps(result, indent=2)
        except Exception as exc:
            return _tool_error_response(
                "lookup-project-portal",
                exc,
                verbose=verbose_mode,
                context=_context_without_none(
                    {"query": query, "limit": limit}),
            )

    @server.tool(
        name="coords-to-map-links",
        description=(
            "Convert points or a bounding box to map links (geojson.io, OpenStreetMap, "
            "Google Maps, Google Earth KML)"
        ),
    )
    def coords_to_map_links(
        points: Optional[List[List[float]]] = None,
        bbox: Optional[List[float]] = None,
        zoom: Optional[int] = None,
    ) -> str:
        """
        Convert coordinates to viewable map links.

        Args:
            points: List of [lat, lon] points (e.g., [[38.92, -106.95], [38.93, -106.94]])
            bbox: [min_lat, min_lon, max_lat, max_lon]
            zoom: Optional zoom level for geojson.io center view (if provided)

        Examples:
            coords-to-map-links with points=[[38.9219, -106.9490]]
            coords-to-map-links with bbox=[38.9187, -106.9532, 38.9263, -106.9451]

        Returns:
            JSON string with map links, derived geometry info, and KML data URIs
        """
        points_count = len(points) if isinstance(points, list) else None
        LOGGER.debug(
            "Tool coords-to-map-links called points_count=%s bbox=%s zoom=%s",
            points_count,
            bbox,
            zoom,
        )
        try:
            if not points and not bbox:
                raise ValueError("Provide either points or bbox.")

            if points and any(len(p) != 2 for p in points):
                raise ValueError("Each point must be [lat, lon].")

            derived_bbox = bbox
            if not derived_bbox and points:
                derived_bbox = _bbox_from_points(points)

            if derived_bbox and len(derived_bbox) != 4:
                raise ValueError(
                    "bbox must be [min_lat, min_lon, max_lat, max_lon].")

            features: List[Dict[str, Any]] = []
            if points:
                features.extend(_geojson_for_points(points)["features"])
            if derived_bbox:
                features.append(
                    {
                        "type": "Feature",
                        "geometry": _geojson_for_bbox(derived_bbox),
                        "properties": {"type": "bbox"},
                    }
                )

            geojson_obj: Dict[str, Any] = {
                "type": "FeatureCollection",
                "features": features,
            }

            response: Dict[str, Any] = {
                "geojson": geojson_obj,
                "links": {
                    "geojson_io": _geojson_io_link(geojson_obj),
                },
            }

            if derived_bbox:
                response["bbox"] = derived_bbox
                response["links"]["openstreetmap_bbox"] = _osm_bbox_link(
                    derived_bbox)
                center_lat = (derived_bbox[0] + derived_bbox[2]) / 2
                center_lon = (derived_bbox[1] + derived_bbox[3]) / 2
                response["center"] = [center_lat, center_lon]
                response["links"]["google_maps_center"] = _google_maps_center_link(
                    response["center"], zoom=zoom
                )
                if zoom is not None:
                    response["links"]["geojson_io_center"] = (
                        f"https://geojson.io/#map={zoom}/{center_lat}/{center_lon}"
                    )

                center_kml = _kml_document(
                    "Center",
                    [_kml_point_placemark("Center", center_lat, center_lon)],
                )
                response["links"]["google_earth_kml_center"] = _kml_data_uri(
                    center_kml)

            if derived_bbox:
                bbox_kml = _kml_document(
                    "Bounding Box",
                    [_kml_bbox_placemark("Bounding Box", derived_bbox)],
                )
                response["links"]["google_earth_kml_bbox"] = _kml_data_uri(
                    bbox_kml)

            if points:
                point_placemarks = [
                    _kml_point_placemark(f"Point {idx + 1}", lat, lon)
                    for idx, (lat, lon) in enumerate(points)
                ]
                points_kml = _kml_document("Points", point_placemarks)
                response["links"]["google_earth_kml_points"] = _kml_data_uri(
                    points_kml)

            return json.dumps(response, indent=2)
        except Exception as exc:
            return _tool_error_response(
                "coords-to-map-links",
                exc,
                verbose=verbose_mode,
                context={
                    "points_count": points_count,
                    "bbox_provided": bbox is not None,
                    "zoom": zoom,
                },
            )

    @server.tool(
        name="doi-to-essdive-id",
        description="Convert a DOI to an ESS-DIVE dataset ID",
    )
    def doi_to_essdive_id_tool(doi: str) -> str:
        """
        Convert a Digital Object Identifier (DOI) to an ESS-DIVE dataset ID.

        This tool queries the ESS-DIVE API to retrieve the dataset metadata
        for a given DOI and returns the corresponding ESS-DIVE dataset identifier.

        The DOI can be provided in any common format:
        - doi:10.xxxx/...
        - 10.xxxx/...
        - https://doi.org/10.xxxx/...
        - http://doi.org/10.xxxx/...

        This is useful when you have a DOI but need to use tools that require
        the ESS-DIVE dataset ID instead.

        Args:
            doi: A DOI in any common format

        Examples:
            doi-to-essdive-id with doi="10.15485/2453885"
            doi-to-essdive-id with doi="https://doi.org/10.15485/2453885"

        Returns:
            JSON string containing the ESS-DIVE dataset ID
        """
        LOGGER.debug("Tool doi-to-essdive-id called doi=%s", doi)
        try:
            essdive_id = doi_to_essdive_id(doi, api_token=api_token)
            return json.dumps(
                {
                    "doi": doi,
                    "essdive_id": essdive_id,
                },
                indent=2,
            )
        except Exception as exc:
            return _tool_error_response(
                "doi-to-essdive-id",
                exc,
                verbose=verbose_mode,
                context={"doi": doi},
            )

    @server.tool(
        name="essdive-id-to-doi",
        description="Convert an ESS-DIVE dataset ID to a DOI",
    )
    def essdive_id_to_doi_tool(essdive_id: str) -> str:
        """
        Convert an ESS-DIVE dataset ID to a Digital Object Identifier (DOI).

        This tool queries the ESS-DIVE API to retrieve the dataset metadata
        for a given ESS-DIVE ID and returns the corresponding DOI.

        The returned DOI is normalized to the format: doi:10.xxxx/...

        This is useful when you have an ESS-DIVE dataset ID but need to use
        tools or services that require the DOI instead.

        Args:
            essdive_id: An ESS-DIVE dataset identifier

        Examples:
            essdive-id-to-doi with essdive_id="ess-dive-9ea5fe57db73c90-20241024T093714082510"

        Returns:
            JSON string containing the DOI
        """
        LOGGER.debug("Tool essdive-id-to-doi called essdive_id=%s", essdive_id)
        try:
            doi = essdive_id_to_doi(essdive_id, api_token=api_token)
            return json.dumps(
                {
                    "essdive_id": essdive_id,
                    "doi": doi,
                },
                indent=2,
            )
        except Exception as exc:
            return _tool_error_response(
                "essdive-id-to-doi",
                exc,
                verbose=verbose_mode,
                context={"essdive_id": essdive_id},
            )

    @server.tool(
        name="search-ess-deepdive",
        description="Search the ESS-DeepDive fusion database for data fields and variables",
    )
    def search_ess_deepdive_tool(
        field_name: Optional[str] = None,
        field_definition: Optional[str] = None,
        field_value_text: Optional[str] = None,
        field_value_numeric: Optional[Union[int, float]] = None,
        field_value_date: Optional[str] = None,
        record_count_min: Optional[int] = None,
        record_count_max: Optional[int] = None,
        doi: Optional[str] = None,
        row_start: int = 1,
        page_size: int = 25,
        max_pages: Optional[int] = None,
    ) -> str:
        """
        Search the ESS-DeepDive fusion database for data fields and values.

        The ESS-DeepDive database contains raw data from many ESS-DIVE datasets.
        Search by field names, definitions, values, or record counts.

        Args:
            field_name: Search for a specific field name (max 100 chars)
            field_definition: Search field definitions (max 100 chars)
            field_value_text: Search for text field values (case insensitive)
            field_value_numeric: Filter by numeric value
            field_value_date: Filter by date value (yyyy-mm-dd or yyyy-mm-ddTHH:MM:SS)
            record_count_min: Filter by minimum record count
            record_count_max: Filter by maximum record count
            doi: Filter by DOI (comma-separated for multiple)
            row_start: The starting row for pagination (default: 1)
            page_size: Number of results per page (max: 100, default: 25)
            max_pages: Maximum number of pages to fetch (optional, for large result sets)

        Examples:
            search-ess-deepdive with field_name="temperature" and record_count_min=100
            search-ess-deepdive with doi="10.15485/2453885" and field_definition="soil"

        Returns:
            JSON string containing search results with field metadata and pagination info.
            If results span multiple pages and max_pages is set, collects results across pages.
        """
        LOGGER.debug(
            "Tool search-ess-deepdive called field_name=%r doi=%r row_start=%s page_size=%s max_pages=%s",
            field_name,
            doi,
            row_start,
            page_size,
            max_pages,
        )
        try:
            # Parse DOI string if provided
            doi_list = None
            if doi:
                doi_list = [d.strip() for d in doi.split(",")]

            # If max_pages is specified, paginate through results
            if max_pages and max_pages > 1:
                all_results = []
                current_row = row_start
                pages_fetched = 0

                while pages_fetched < max_pages:
                    LOGGER.debug(
                        "search-ess-deepdive pagination loop page_index=%s current_row=%s",
                        pages_fetched + 1,
                        current_row,
                    )
                    result = search_ess_deepdive(
                        field_name=field_name,
                        field_definition=field_definition,
                        field_value_text=field_value_text,
                        field_value_numeric=field_value_numeric,
                        field_value_date=field_value_date,
                        record_count_min=record_count_min,
                        record_count_max=record_count_max,
                        doi=doi_list,
                        row_start=current_row,
                        page_size=page_size,
                    )

                    # Collect results from this page
                    if "results" in result:
                        all_results.extend(result["results"])

                    # Check if there are more pages
                    page_count = result.get("pageCount", 0)
                    if not page_count or page_count <= 1:
                        # No more pages available
                        break

                    pages_fetched += 1
                    current_row += page_size

                # Return combined results with metadata
                return json.dumps(
                    {
                        "results": all_results,
                        "total_results_fetched": len(all_results),
                        "pages_fetched": pages_fetched + 1,
                        "note": f"Fetched {pages_fetched + 1} pages. Use row_start and page_size to fetch additional pages.",
                    },
                    indent=2,
                )
            else:
                # Single page request
                result = search_ess_deepdive(
                    field_name=field_name,
                    field_definition=field_definition,
                    field_value_text=field_value_text,
                    field_value_numeric=field_value_numeric,
                    field_value_date=field_value_date,
                    record_count_min=record_count_min,
                    record_count_max=record_count_max,
                    doi=doi_list,
                    row_start=row_start,
                    page_size=page_size,
                )

                # Add helpful pagination info to response
                page_count = result.get("pageCount", 0)
                if page_count and page_count > 1:
                    result["pagination_info"] = {
                        "current_page": 1,
                        "total_pages": page_count,
                        "page_size": page_size,
                        "next_row_start": row_start + page_size,
                        "note": "Use max_pages parameter to automatically fetch all pages, or manually paginate using row_start",
                    }

                return json.dumps(result, indent=2)
        except Exception as exc:
            return _tool_error_response(
                "search-ess-deepdive",
                exc,
                verbose=verbose_mode,
                context=_context_without_none(
                    {
                        "field_name": field_name,
                        "field_definition": field_definition,
                        "field_value_text": field_value_text,
                        "field_value_numeric": field_value_numeric,
                        "field_value_date": field_value_date,
                        "record_count_min": record_count_min,
                        "record_count_max": record_count_max,
                        "doi": doi,
                        "row_start": row_start,
                        "page_size": page_size,
                        "max_pages": max_pages,
                    }
                ),
            )

    @server.tool(
        name="get-ess-deepdive-dataset",
        description="Get detailed field information for a specific dataset file in ESS-DeepDive",
    )
    def get_ess_deepdive_dataset_tool(doi: str, file_path: str) -> str:
        """
        Get detailed field information for a specific dataset file in ESS-DeepDive.

        This retrieves all fields and their definitions for a specific file in the
        ESS-DeepDive fusion database.

        Args:
            doi: The DOI of the dataset (with or without 'doi:' prefix)
            file_path: The file path within the dataset

        Examples:
            get-ess-deepdive-dataset with doi="10.15485/2453885" and file_path="dataset.zip/data.csv"

        Returns:
            JSON string containing detailed field information
        """
        LOGGER.debug(
            "Tool get-ess-deepdive-dataset called doi=%s file_path=%s",
            doi,
            file_path,
        )
        try:
            result = get_ess_deepdive_dataset(doi=doi, file_path=file_path)
            return json.dumps(result, indent=2)
        except Exception as exc:
            return _tool_error_response(
                "get-ess-deepdive-dataset",
                exc,
                verbose=verbose_mode,
                context={"doi": doi, "file_path": file_path},
            )

    @server.tool(
        name="get-ess-deepdive-file",
        description="Retrieve detailed information about a specific file from ESS-DeepDive",
    )
    def get_ess_deepdive_file_tool(doi: str, file_path: str) -> str:
        """
        Retrieve detailed information about a specific file from ESS-DeepDive (Get-Dataset-File endpoint).

        This endpoint returns comprehensive information about a data file, including:
        - All field names and their definitions
        - Data types and summary statistics for each field
        - File metadata and download information
        - Record counts and value ranges

        Use this after finding a file of interest from search-ess-deepdive results
        to get complete field-level metadata before downloading.

        Args:
            doi: The DOI of the dataset (with or without 'doi:' prefix, format: doi:10.xxxx/...)
            file_path: The file path within the dataset (e.g., "dataset.zip/data.csv")

        Examples:
            get-ess-deepdive-file with doi="doi:10.15485/2453885" and file_path="dataset.zip/data.csv"

        Returns:
            JSON string containing file information with all field metadata and download URLs
        """
        LOGGER.debug(
            "Tool get-ess-deepdive-file called doi=%s file_path=%s",
            doi,
            file_path,
        )
        try:
            result = get_ess_deepdive_file(doi=doi, file_path=file_path)

            # Extract relevant information for user-friendly display
            if isinstance(result, dict):
                summary = _summarize_essdeepdive_file_response(result)

                # Return complete result with helpful summary
                return json.dumps(
                    {
                        "summary": summary,
                        "complete_response": result,
                    },
                    indent=2,
                )

            return json.dumps(result, indent=2)
        except Exception as exc:
            return _tool_error_response(
                "get-ess-deepdive-file",
                exc,
                verbose=verbose_mode,
                context={"doi": doi, "file_path": file_path},
            )

    # Run the server
    asyncio.run(server.run_stdio_async())


if __name__ == "__main__":
    main()
