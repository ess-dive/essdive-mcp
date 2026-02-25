"""Integration tests that call live ESS-DIVE / ESS-DeepDive APIs."""

import pytest

from essdive_mcp.main import (
    ESSDiveClient,
    doi_to_essdive_id,
    get_ess_deepdive_file,
    search_ess_deepdive,
)


pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_get_dataset_by_id_live(
    essdive_api_token: str,
    essdive_dataset_examples: list[dict[str, str]],
):
    """Fixture dataset IDs should resolve to full ESS-DIVE entries."""
    client = ESSDiveClient(api_token=essdive_api_token)
    for example in essdive_dataset_examples:
        response = await client.get_dataset(example["id"])

        assert response["id"] == example["id"]
        assert response.get("isPublic") is True
        assert response.get("viewUrl")

        dataset = response["dataset"]
        assert dataset["name"]
        assert dataset["@id"].startswith("doi:")
        assert dataset["@id"] == example["doi"]
        assert isinstance(dataset.get("creator"), list) and dataset["creator"]
        assert isinstance(dataset.get("distribution"),
                          list) and dataset["distribution"]


@pytest.mark.asyncio
async def test_get_dataset_by_doi_live_matches_id(
    essdive_api_token: str,
    essdive_dataset_examples: list[dict[str, str]],
):
    """Fixture DOIs should resolve back to the expected dataset IDs."""
    client = ESSDiveClient(api_token=essdive_api_token)
    for example in essdive_dataset_examples:
        by_doi = await client.get_dataset(example["doi"])
        assert by_doi["id"] == example["id"]


def test_doi_to_essdive_id_live(
    essdive_api_token: str,
    essdive_dataset_examples: list[dict[str, str]],
):
    """Fixture DOIs should convert to the expected ESS-DIVE IDs."""
    for example in essdive_dataset_examples:
        resolved_id = doi_to_essdive_id(
            example["doi"], api_token=essdive_api_token)
        assert resolved_id == example["id"]


def test_search_ess_deepdive_live(
    essdeepdive_search_examples: list[dict[str, int | str]],
):
    """Fixture ESS-DeepDive searches should return valid response shapes."""
    for example in essdeepdive_search_examples:
        response = search_ess_deepdive(**example)

        assert isinstance(response, dict)
        assert "url" in response
        assert "pageCount" in response
        assert isinstance(response["results"], list)
        assert len(response["results"]) > 0

        first = response["results"][0]
        assert first["doi"].startswith("doi:")
        assert first["data_file"]


def test_get_ess_deepdive_file_live_from_search_result(
    essdeepdive_search_examples: list[dict[str, int | str]],
):
    """A DOI/file pair from search results should resolve to file-level metadata."""
    query = dict(essdeepdive_search_examples[0])
    query["page_size"] = 1
    search_response = search_ess_deepdive(**query)
    first = search_response["results"][0]

    file_response = get_ess_deepdive_file(first["doi"], first["data_file"])
    assert file_response["doi"] == first["doi"]
    assert file_response["data_file"] == first["data_file"]
    assert isinstance(file_response.get("fields"), list)
