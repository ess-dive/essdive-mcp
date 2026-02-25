"""Integration tests that call live ESS-DIVE / ESS-DeepDive APIs."""

import os

import pytest

from essdive_mcp.main import (
    ESSDiveClient,
    doi_to_essdive_id,
    get_ess_deepdive_file,
    search_ess_deepdive,
)


pytestmark = pytest.mark.integration

TARGET_DATASET_ID = "ess-dive-7f9a048dfac0ade-20260122T002107310"


@pytest.fixture(scope="session")
def essdive_api_token() -> str:
    """Return ESS-DIVE API token or skip ESS-DIVE integration tests."""
    token = os.getenv("ESSDIVE_API_TOKEN")
    if not token:
        pytest.skip(
            "ESSDIVE_API_TOKEN is required for ESS-DIVE integration tests."
        )
    return token


@pytest.mark.asyncio
async def test_get_dataset_by_id_live(essdive_api_token: str):
    """The requested ESS-DIVE identifier should resolve to a real dataset."""
    client = ESSDiveClient(api_token=essdive_api_token)
    response = await client.get_dataset(TARGET_DATASET_ID)

    assert response["id"] == TARGET_DATASET_ID
    assert response.get("isPublic") is True
    assert response.get("viewUrl")

    dataset = response["dataset"]
    assert dataset["name"]
    assert dataset["@id"].startswith("doi:")
    assert isinstance(dataset.get("creator"), list) and dataset["creator"]
    assert isinstance(dataset.get("distribution"),
                      list) and dataset["distribution"]


@pytest.mark.asyncio
async def test_get_dataset_by_doi_live_matches_id(essdive_api_token: str):
    """DOI lookup from dataset metadata should resolve back to the same dataset ID."""
    client = ESSDiveClient(api_token=essdive_api_token)
    by_id = await client.get_dataset(TARGET_DATASET_ID)
    doi_identifier = by_id["dataset"]["@id"]

    by_doi = await client.get_dataset(doi_identifier)
    assert by_doi["id"] == TARGET_DATASET_ID


def test_doi_to_essdive_id_live(essdive_api_token: str):
    """The DOI from the target dataset should convert back to its ESS-DIVE ID."""
    # DOI captured from the target dataset metadata and expected to stay stable.
    doi = "doi:10.15485/2529445"
    resolved_id = doi_to_essdive_id(doi, api_token=essdive_api_token)
    assert resolved_id == TARGET_DATASET_ID


def test_search_ess_deepdive_live():
    """ESS-DeepDive live search should return a valid response shape."""
    response = search_ess_deepdive(field_name="temperature", page_size=5)

    assert isinstance(response, dict)
    assert "url" in response
    assert "pageCount" in response
    assert isinstance(response["results"], list)
    assert len(response["results"]) > 0

    first = response["results"][0]
    assert first["doi"].startswith("doi:")
    assert first["data_file"]


def test_get_ess_deepdive_file_live_from_search_result():
    """A DOI/file pair from search results should resolve to file-level metadata."""
    search_response = search_ess_deepdive(
        field_name="temperature", page_size=1)
    first = search_response["results"][0]

    file_response = get_ess_deepdive_file(first["doi"], first["data_file"])
    assert file_response["doi"] == first["doi"]
    assert file_response["data_file"] == first["data_file"]
    assert isinstance(file_response.get("fields"), list)
