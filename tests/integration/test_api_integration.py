"""Integration tests that call live ESS-DIVE / ESS-DeepDive APIs."""

import pytest
import requests

from essdive_mcp.main import (
    ESSDiveClient,
    doi_to_essdive_id,
    get_ess_deepdive_file,
    search_ess_deepdive,
)


pytestmark = pytest.mark.integration


def _download_prefix(url: str, bytes_to_read: int) -> tuple[int, str, bytes]:
    """Download only a small prefix of a file for lightweight integration checks."""
    if bytes_to_read <= 0:
        raise ValueError("bytes_to_read must be positive")

    headers = {"Range": f"bytes=0-{bytes_to_read - 1}"}
    with requests.get(url, headers=headers, stream=True, timeout=30) as response:
        response.raise_for_status()
        content_type = response.headers.get("content-type", "")
        data = bytearray()
        for chunk in response.iter_content(chunk_size=min(1024, bytes_to_read)):
            if not chunk:
                continue
            data.extend(chunk)
            if len(data) >= bytes_to_read:
                break

        return response.status_code, content_type, bytes(data)


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


def test_essdeepdive_download_metadata_live(
    essdeepdive_download_examples: list[dict[str, int | str]],
):
    """Download metadata should include a retrievable content URL."""
    for example in essdeepdive_download_examples:
        search_response = search_ess_deepdive(
            field_name=str(example["field_name"]),
            page_size=int(example["page_size"]),
        )
        first = search_response["results"][0]
        file_response = get_ess_deepdive_file(first["doi"], first["data_file"])
        download_info = file_response["data_download"]

        assert isinstance(download_info, dict)
        assert download_info.get("contentUrl", "").startswith("https://")
        assert isinstance(download_info.get("name"),
                          str) and download_info["name"]
        assert download_info.get("contentSize") is not None


def test_essdeepdive_file_download_partial_read_live(
    essdeepdive_download_examples: list[dict[str, int | str]],
):
    """Download a small byte prefix from live ESS-DeepDive-linked files."""
    for example in essdeepdive_download_examples:
        search_response = search_ess_deepdive(
            field_name=str(example["field_name"]),
            page_size=int(example["page_size"]),
        )
        first = search_response["results"][0]
        file_response = get_ess_deepdive_file(first["doi"], first["data_file"])
        url = file_response["data_download"]["contentUrl"]
        requested_bytes = int(example["bytes_to_read"])

        status_code, content_type, blob = _download_prefix(
            url, requested_bytes)

        assert status_code in (200, 206)
        assert len(blob) > 0
        assert len(blob) <= requested_bytes + 1024

        # Most sample files are CSV; if we get text content, verify it is readable.
        if "text" in content_type or "csv" in content_type:
            text_prefix = blob.decode("utf-8", errors="replace")
            assert "," in text_prefix or "\t" in text_prefix
