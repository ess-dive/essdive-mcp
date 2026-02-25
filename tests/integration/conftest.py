"""Shared fixtures for live integration tests."""

import json
import os
from pathlib import Path
from typing import Any

import pytest


_FIXTURES_PATH = Path(__file__).parent / "fixtures" / "api_examples.json"


@pytest.fixture(scope="session")
def essdive_api_token() -> str:
    """Return ESS-DIVE API token or skip ESS-DIVE integration tests."""
    token = os.getenv("ESSDIVE_API_TOKEN")
    if not token:
        pytest.skip(
            "ESSDIVE_API_TOKEN is required for ESS-DIVE integration tests."
        )
    return token


@pytest.fixture(scope="session")
def api_examples() -> dict[str, Any]:
    """Load integration examples from fixtures."""
    with _FIXTURES_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)


@pytest.fixture(scope="session")
def essdive_dataset_examples(api_examples: dict[str, Any]) -> list[dict[str, str]]:
    """Return ESS-DIVE dataset examples from fixture file."""
    return api_examples["essdive"]["datasets"]


@pytest.fixture(scope="session")
def essdeepdive_search_examples(api_examples: dict[str, Any]) -> list[dict[str, Any]]:
    """Return ESS-DeepDive search query examples from fixture file."""
    return api_examples["essdeepdive"]["search_queries"]
