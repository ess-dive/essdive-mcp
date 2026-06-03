#!/usr/bin/env python3
"""Refresh bundled ESS-DIVE project references from the Mule project registry."""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
from pathlib import Path
from typing import Any

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE_URL = "https://mule.ess-dive.lbl.gov/api/v1/project/?format=json"
DEFAULT_YAML_PATH = REPO_ROOT / ".agents" / "skills" / "references" / "essdive_projects.yaml"
DEFAULT_PYTHON_PATH = REPO_ROOT / "src" / "essdive_mcp" / "projects.py"


ASCII_REPLACEMENTS = {
    "\u2010": "-",
    "\u2011": "-",
    "\u2012": "-",
    "\u2013": "-",
    "\u2014": "-",
    "\u2018": "'",
    "\u2019": "'",
    "\u201c": '"',
    "\u201d": '"',
    "\u2026": "...",
    "\xa0": " ",
}


def _ascii_text(value: Any) -> str:
    """Return a clean ASCII string for stable committed references."""
    if value is None:
        return ""
    text = str(value).strip()
    for old, new in ASCII_REPLACEMENTS.items():
        text = text.replace(old, new)
    text = re.sub(r"\s+", " ", text)
    return text.encode("ascii", "ignore").decode("ascii").strip()


def _normalize_lookup_text(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def _unique_strings(values: list[str]) -> list[str]:
    unique: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = _ascii_text(value)
        key = _normalize_lookup_text(text)
        if text and key not in seen:
            seen.add(key)
            unique.append(text)
    return unique


def _load_current_projects(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle) or {}
    projects = payload.get("projects")
    if not isinstance(projects, list):
        raise ValueError(f"Expected 'projects' list in {path}")
    return [project for project in projects if isinstance(project, dict)]


def _load_mule_payload(source: str) -> dict[str, Any]:
    if source.startswith(("http://", "https://")):
        request = urllib.request.Request(
            source,
            headers={
                "Accept": "application/json",
                "User-Agent": "essdive-mcp project reference updater",
            },
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.load(response)

    with Path(source).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _project_keys(project: dict[str, Any]) -> set[str]:
    values = [
        _ascii_text(project.get("name")),
        _ascii_text(project.get("acronym")),
        *[_ascii_text(alias) for alias in project.get("aliases") or []],
    ]
    return {key for value in values if (key := _normalize_lookup_text(value))}


def _mule_project_keys(project: dict[str, Any]) -> set[str]:
    values = [
        _ascii_text(project.get("project_title")),
        _ascii_text(project.get("short_name")),
    ]
    return {key for value in values if (key := _normalize_lookup_text(value))}


def _append_alias(project: dict[str, Any], alias: str) -> None:
    aliases = project.get("aliases")
    if not isinstance(aliases, list):
        aliases = []
    project["aliases"] = _unique_strings([*aliases, alias])


def _copy_mule_metadata(target: dict[str, Any], mule_project: dict[str, Any]) -> None:
    metadata = {
        "mule_id": _ascii_text(mule_project.get("id")),
        "mule_url": _ascii_text(mule_project.get("url")),
        "sponsor_program_url": _ascii_text(mule_project.get("sponsor_program")),
        "project_type_url": _ascii_text(mule_project.get("project_type")),
    }
    for key, value in metadata.items():
        if value and not target.get(key):
            target[key] = value


def _mule_project_to_reference(project: dict[str, Any]) -> dict[str, Any] | None:
    title = _ascii_text(project.get("project_title"))
    short_name = _ascii_text(project.get("short_name"))
    if not title:
        return None

    aliases = []
    if short_name and _normalize_lookup_text(short_name) != _normalize_lookup_text(title):
        aliases.append(short_name)

    reference = {
        "name": title,
        "acronym": short_name,
        "aliases": aliases,
        "short_description": "ESS-DIVE project imported from the Mule project registry.",
        "portal_url": "",
        "url": "",
    }
    _copy_mule_metadata(reference, project)
    return reference


def merge_projects(
    current_projects: list[dict[str, Any]],
    mule_projects: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], int, int]:
    """Merge Mule projects into curated references, returning merged, added, enriched."""
    merged = list(current_projects)
    key_to_project: dict[str, dict[str, Any]] = {}

    for project in merged:
        for key in _project_keys(project):
            key_to_project.setdefault(key, project)

    added = 0
    enriched = 0
    for mule_project in mule_projects:
        keys = _mule_project_keys(mule_project)
        existing = next(
            (key_to_project[key] for key in keys if key in key_to_project),
            None,
        )
        if existing is not None:
            before = dict(existing)
            _copy_mule_metadata(existing, mule_project)
            short_name = _ascii_text(mule_project.get("short_name"))
            title = _ascii_text(mule_project.get("project_title"))
            if short_name and short_name != existing.get("acronym"):
                _append_alias(existing, short_name)
            if title and title != existing.get("name"):
                _append_alias(existing, title)
            if existing != before:
                enriched += 1
            for key in keys | _project_keys(existing):
                key_to_project.setdefault(key, existing)
            continue

        reference = _mule_project_to_reference(mule_project)
        if reference is None:
            continue
        merged.append(reference)
        added += 1
        for key in _project_keys(reference):
            key_to_project.setdefault(key, reference)

    return merged, added, enriched


def _write_yaml(projects: list[dict[str, Any]], path: Path) -> None:
    payload = {"projects": projects}
    text = yaml.safe_dump(
        payload,
        sort_keys=False,
        allow_unicode=False,
        width=120,
    )
    path.write_text(text, encoding="utf-8")


def _write_python(projects: list[dict[str, Any]], path: Path) -> None:
    lines = [
        '"""Shared ESS-DIVE project reference data bundled with the MCP package.',
        "",
        "Generated from .agents/skills/references/essdive_projects.yaml by",
        "scripts/update_essdive_projects.py.",
        '"""',
        "",
        "ESSDIVE_PROJECTS = [",
    ]
    for project in projects:
        lines.append("    {")
        for key, value in project.items():
            if isinstance(value, list):
                if not value:
                    lines.append(f"        {key!r}: [],")
                else:
                    lines.append(f"        {key!r}: [")
                    for item in value:
                        lines.append(f"            {item!r},")
                    lines.append("        ],")
            else:
                lines.append(f"        {key!r}: {value!r},")
        lines.append("    },")
    lines.append("]")
    lines.append("")
    text = "\n".join(lines)
    path.write_text(text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", default=DEFAULT_SOURCE_URL)
    parser.add_argument("--yaml-path", type=Path, default=DEFAULT_YAML_PATH)
    parser.add_argument("--python-path", type=Path, default=DEFAULT_PYTHON_PATH)
    args = parser.parse_args()

    current_projects = _load_current_projects(args.yaml_path)
    payload = _load_mule_payload(args.source)
    mule_projects = payload.get("result")
    if not isinstance(mule_projects, list):
        raise ValueError("Mule project payload did not contain a result list.")

    merged, added, enriched = merge_projects(current_projects, mule_projects)
    _write_yaml(merged, args.yaml_path)
    _write_python(merged, args.python_path)

    print(
        f"Merged {len(mule_projects)} Mule projects: "
        f"{added} added, {enriched} existing entries enriched, {len(merged)} total.",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
