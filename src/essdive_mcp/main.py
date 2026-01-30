#!/usr/bin/env python3
"""
ESS-DIVE MCP Server - Main entry point

This module implements a Model Context Protocol (MCP) server that provides
comprehensive tools for accessing and analyzing data from ESS-DIVE and ESS-DeepDive APIs.

MCP Tools Available:

**Dataset Search & Retrieval:**
  - search-datasets: Full-text search across ESS-DIVE datasets with filtering by creator,
    provider, publication date, and keywords. Supports pagination and multiple result formats.
  - get-dataset: Retrieve detailed metadata for a specific dataset including creators,
    keywords, description, and available data files.
  - get-dataset-permissions: Get sharing and access permission information for datasets.

**Identifier Conversion:**
  - doi-to-essdive-id: Convert Digital Object Identifiers (DOI) to ESS-DIVE dataset IDs.
    Handles multiple DOI formats (doi:10.xxxx, https://doi.org/10.xxxx, etc.).
  - essdive-id-to-doi: Convert ESS-DIVE dataset IDs to standardized DOI format.

**File-Level Metadata:**
  - parse-flmd-file: Parse File Level Metadata (FLMD) CSV files to extract filename and
    description mappings for dataset files.

**ESS-DeepDive Search & Analysis:**
  - search-ess-deepdive: Search the ESS-DeepDive fusion database for data fields by name,
    definition, value (text/numeric/date), and record count. Supports multi-page results.
  - get-ess-deepdive-dataset: Retrieve detailed field information and metadata for a
    specific file in the ESS-DeepDive database.
  - get-ess-deepdive-file: Get comprehensive file-level information including field names,
    data types, summary statistics, and download metadata from ESS-DeepDive.

Authentication:
  API token can be provided via --token flag or ESSDIVE_API_TOKEN environment variable.
"""
import asyncio
import os
import argparse
import json
import csv
import re
import requests
from io import StringIO
from typing import Dict, List, Optional, Any, Union
import httpx
from urllib.parse import quote

from fastmcp import FastMCP


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


def parse_flmd_file(content: str) -> Dict[str, str]:
    """Parse an FLMD (File Level Metadata) file and return a mapping of filename -> description.

    Args:
        content: The FLMD file content as a string

    Returns:
        Dictionary mapping filename to file description
    """
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
            filename = row.get(filename_col, "").strip()
            description = row.get(description_col, "").strip()

            if filename and description:
                file_descriptions[filename] = sanitize_tsv_field(description)

    except Exception as e:
        pass

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

    async def search_datasets(
        self,
        row_start: int = 1,
        page_size: int = 25,
        is_public: Optional[bool] = None,
        creator: Optional[str] = None,
        provider_name: Optional[str] = None,
        text: Optional[str] = None,
        date_published: Optional[str] = None,
        keywords: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Search for datasets using the ESS-DIVE API.

        Args:
            row_start: The row number to start on (for pagination)
            page_size: Number of results per page (max 100)
            is_public: If True, only return public packages
            creator: Filter by dataset creator
            provider_name: Filter by dataset project/provider
            text: Full-text search across metadata fields
            date_published: Filter by publication date
            keywords: Search for datasets with specific keywords

        Returns:
            API response containing search results
        """
        params: Dict[str, Any] = {}

        # Always include pagination parameters
        params["rowStart"] = row_start
        params["pageSize"] = page_size

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
        if keywords:
            params["keywords"] = keywords

        url = f"{self.BASE_URL}/packages"

        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params, headers=self._get_headers())
            response.raise_for_status()
            return response.json()

    async def get_dataset(self, identifier: str) -> Dict[str, Any]:
        """
        Get detailed information about a specific dataset.

        Args:
            identifier: The ESS-DIVE unique identifier

        Returns:
            API response containing dataset details
        """
        # URL encode the identifier to handle special characters
        encoded_identifier = quote(identifier, safe="")
        url = f"{self.BASE_URL}/packages/{encoded_identifier}"

        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=self._get_headers())
            response.raise_for_status()
            return response.json()

    async def get_dataset_status(self, identifier: str) -> Dict[str, Any]:
        """
        Get the status of a dataset (DOI minting, publication, visibility).

        Args:
            identifier: The ESS-DIVE unique identifier

        Returns:
            API response containing dataset status information
        """
        encoded_identifier = quote(identifier, safe="")
        url = f"{self.BASE_URL}/packages/{encoded_identifier}/status"

        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=self._get_headers())
            response.raise_for_status()
            return response.json()

    async def get_dataset_permissions(self, identifier: str) -> Dict[str, Any]:
        """
        Get sharing permissions for a dataset.

        Args:
            identifier: The ESS-DIVE unique identifier

        Returns:
            API response containing dataset permissions information
        """
        encoded_identifier = quote(identifier, safe="")
        url = f"{self.BASE_URL}/packages/{encoded_identifier}/share"

        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=self._get_headers())
            response.raise_for_status()
            return response.json()

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

        if format_type == "summary":
            summary = f"Found {total} datasets. Showing {len(datasets)} results:\n\n"

            for i, dataset in enumerate(datasets, 1):
                ds_data = dataset.get("dataset", {})
                summary += f"{i}. {ds_data.get('name', 'Untitled')}\n"
                summary += f"   ID: {dataset.get('id', 'Unknown')}\n"
                summary += f"   Published: {ds_data.get('datePublished', 'Unknown')}\n"
                summary += f"   URL: {dataset.get('viewUrl', 'Unknown')}\n"
                if i < len(datasets):
                    summary += "\n"

            return summary

        elif format_type == "detailed":
            detailed = f"Found {total} datasets. Showing {len(datasets)} results:\n\n"

            for i, dataset in enumerate(datasets, 1):
                ds_data = dataset.get("dataset", {})
                detailed += f"{i}. {ds_data.get('name', 'Untitled')}\n"
                detailed += f"   ID: {dataset.get('id', 'Unknown')}\n"
                detailed += f"   Published: {ds_data.get('datePublished', 'Unknown')}\n"
                detailed += f"   URL: {dataset.get('viewUrl', 'Unknown')}\n"

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

                if i < len(datasets):
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

    Raises:
        ValueError: If the DOI is not found or API call fails
    """
    # Normalize the DOI
    normalized_doi = _normalize_doi(doi)

    # Create client and fetch dataset metadata
    client = ESSDiveClient(api_token=api_token)

    try:
        # Use asyncio to run the async function
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(
                client.get_dataset(normalized_doi))
            essdive_id = result.get("id")
            if not essdive_id:
                raise ValueError(
                    f"No dataset ID found in response for DOI: {doi}")
            return essdive_id
        finally:
            loop.close()
    except Exception as e:
        raise ValueError(
            f"Failed to convert DOI {doi} to ESS-DIVE ID: {str(e)}")


def essdive_id_to_doi(essdive_id: str, api_token: Optional[str] = None) -> str:
    """Convert an ESS-DIVE dataset ID to a DOI by querying the ESS-DIVE API.

    Args:
        essdive_id: An ESS-DIVE dataset identifier
        api_token: Optional API token for authenticated requests

    Returns:
        The DOI in the format doi:10.xxxx/...

    Raises:
        ValueError: If the ESS-DIVE ID is not found or API call fails
    """
    client = ESSDiveClient(api_token=api_token)

    try:
        # Use asyncio to run the async function
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(client.get_dataset(essdive_id))
            dataset_meta = result.get("dataset", {})
            doi = dataset_meta.get("doi")
            if not doi:
                raise ValueError(
                    f"No DOI found in metadata for ESS-DIVE ID: {essdive_id}")
            # Normalize the DOI
            return _normalize_doi(doi)
        finally:
            loop.close()
    except Exception as e:
        raise ValueError(
            f"Failed to convert ESS-DIVE ID {essdive_id} to DOI: {str(e)}")


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

    response = requests.get(ESS_DEEPDIVE_BASE_URL, params=params)
    response.raise_for_status()
    return response.json()


def get_ess_deepdive_dataset(doi: str, file_path: str) -> Dict[str, Any]:
    """
    Get detailed field information for a specific dataset file in ESS-DeepDive.

    Args:
        doi: The DOI of the dataset (must include 'doi:' prefix, format: doi:10.xxxx/...)
        file_path: The dataset file path

    Returns:
        API response containing detailed field information
    """
    # Ensure DOI has the correct format
    if not doi.startswith("doi:"):
        doi = f"doi:{doi}"

    # Construct the URL with the doi:file_path format
    url = f"{ESS_DEEPDIVE_BASE_URL}/{doi}:{file_path}"

    response = requests.get(url)
    response.raise_for_status()
    return response.json()


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
    """
    return get_ess_deepdive_dataset(doi, file_path)


def get_api_key(
    api_key: Optional[str] = None, token_file: Optional[str] = None
) -> str:
    """
    Get ESS-DIVE API key from parameter, token file, or environment variable.

    Args:
        api_key: Optional API key provided directly.
        token_file: Optional path to a file containing the API key.

    Returns:
        The API key string.

    Raises:
        ValueError: If no API key is provided or found in environment.
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

    if not api_key:
        raise ValueError(
            "ESS-DIVE API key is required. Provide it with --token, --token-file, or set ESSDIVE_API_TOKEN."
        )

    return api_key


def main():
    """Main entry point for the MCP server."""
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description="Run an ESS-DIVE MCP server")
    parser.add_argument(
        "--token",
        "-t",
        help="ESS-DIVE API token for authenticated requests (can also use ESSDIVE_API_TOKEN env var)",
    )
    parser.add_argument(
        "--token-file",
        help="Path to a file containing the ESS-DIVE API token",
    )
    args = parser.parse_args()

    # Get and validate API token
    api_token = get_api_key(args.token, token_file=args.token_file)

    # Create a FastMCP server
    server = FastMCP("essdive_mcp")

    # Create a client for the ESS-DIVE API with the provided token
    client = ESSDiveClient(api_token=api_token)

    # Register tool functions
    @server.tool(name="search-datasets", description="Search for datasets in ESS-DIVE")
    async def search_datasets(
        query: Optional[str] = None,
        creator: Optional[str] = None,
        provider_name: Optional[str] = None,
        date_published: Optional[str] = None,
        keywords: Optional[Union[str, List[str]]] = None,
        row_start: int = 1,
        page_size: int = 25,
        format: str = "summary",
    ) -> str:
        """
        Search for datasets in the ESS-DIVE repository.

        Args:
            query: Search query text (full-text search)
            creator: Filter by dataset creator
            provider_name: Filter by dataset project/provider
            date_published: Filter by publication date (e.g., "[2016 TO 2023]")
            keywords: Search for datasets with specific keywords (string or list of strings)
            row_start: The row number to start on (for pagination)
            page_size: Number of results per page
            format: Format of the results (summary, detailed, raw)

        Returns:
            Formatted search results
        """
        try:
            # Convert keywords to list if it's a string
            keywords_list = None
            if keywords:
                if isinstance(keywords, str):
                    keywords_list = [keywords]
                else:
                    keywords_list = keywords

            # If query is provided but no specific text search parameter,
            # use the query as the text search
            text = None
            if query and not any([creator, provider_name, keywords_list]):
                text = query

            # Search for datasets (always search public datasets)
            result = await client.search_datasets(
                row_start=row_start,
                page_size=page_size,
                is_public=True,
                creator=creator,
                provider_name=provider_name,
                text=text,
                date_published=date_published,
                keywords=keywords_list,
            )

            # Format the results
            formatted = client.format_results(result, format)

            if format == "raw":
                return json.dumps(formatted, indent=2)
            elif isinstance(formatted, dict):
                return json.dumps(formatted, indent=2)
            else:
                return str(formatted)

        except Exception as e:
            return f"Error searching for datasets: {str(e)}"

    @server.tool(
        name="get-dataset",
        description="Get detailed information about a specific dataset",
    )
    async def get_dataset(id: str) -> str:
        """
        Get detailed information about a specific dataset.

        Args:
            id: ESS-DIVE dataset identifier

        Returns:
            Formatted dataset information
        """
        try:
            result = await client.get_dataset(id)

            # Format the result
            dataset = result.get("dataset", {})
            name = dataset.get("name", "Untitled")
            description = dataset.get("description", "")
            if isinstance(description, list):
                description = " ".join(description)

            # Format basic metadata
            content = f"# {name}\n\n"
            content += f"**ID**: {result.get('id', 'Unknown')}\n"
            content += f"**Published**: {dataset.get('datePublished', 'Unknown')}\n\n"
            content += f"## Description\n{description}\n\n"

            # Format creators
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

            # Format keywords
            keywords = dataset.get("keywords", [])
            if not isinstance(keywords, list):
                keywords = [keywords]

            if keywords:
                content += "## Keywords\n"
                content += ", ".join(keywords)
                content += "\n\n"

            # Format data files if available
            distribution = dataset.get("distribution", [])
            if distribution:
                content += "## Data Files\n"
                for file in distribution:
                    file_name = file.get("name", "Unknown")
                    file_size = file.get("contentSize", 0)
                    file_format = file.get("encodingFormat", "Unknown")
                    file_url = file.get("contentUrl", "Unknown")
                    file_id = file.get("identifier", "Unknown")
                    content += f"- {file_name} ({file_size} KB, {file_format}) URL: {file_url} ID: {file_id}\n"

            return content

        except Exception as e:
            return f"Error retrieving dataset information: {str(e)}"

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

        Returns:
            JSON string mapping filenames to their descriptions
        """
        try:
            file_descriptions = parse_flmd_file(content)
            return json.dumps(file_descriptions, indent=2)
        except Exception as e:
            return json.dumps(
                {"error": f"Error parsing FLMD file: {str(e)}"}, indent=2
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

        Returns:
            JSON string containing the dataset permissions
        """
        try:
            result = await client.get_dataset_permissions(id)
            return json.dumps(result, indent=2)
        except Exception as e:
            return json.dumps(
                {"error": f"Error retrieving dataset permissions: {str(e)}"},
                indent=2,
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

        Returns:
            JSON string containing the ESS-DIVE dataset ID
        """
        try:
            essdive_id = doi_to_essdive_id(doi, api_token=api_token)
            return json.dumps(
                {
                    "doi": doi,
                    "essdive_id": essdive_id,
                },
                indent=2,
            )
        except Exception as e:
            return json.dumps(
                {"error": f"Error converting DOI to ESS-DIVE ID: {str(e)}"},
                indent=2,
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

        Returns:
            JSON string containing the DOI
        """
        try:
            doi = essdive_id_to_doi(essdive_id, api_token=api_token)
            return json.dumps(
                {
                    "essdive_id": essdive_id,
                    "doi": doi,
                },
                indent=2,
            )
        except Exception as e:
            return json.dumps(
                {"error": f"Error converting ESS-DIVE ID to DOI: {str(e)}"},
                indent=2,
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

        Returns:
            JSON string containing search results with field metadata and pagination info.
            If results span multiple pages and max_pages is set, collects results across pages.
        """
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
        except Exception as e:
            return json.dumps(
                {"error": f"Error searching ESS-DeepDive: {str(e)}"},
                indent=2,
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

        Returns:
            JSON string containing detailed field information
        """
        try:
            result = get_ess_deepdive_dataset(doi=doi, file_path=file_path)
            return json.dumps(result, indent=2)
        except Exception as e:
            return json.dumps(
                {"error": f"Error retrieving ESS-DeepDive dataset: {str(e)}"},
                indent=2,
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

        Returns:
            JSON string containing file information with all field metadata and download URLs
        """
        try:
            result = get_ess_deepdive_file(doi=doi, file_path=file_path)

            # Extract relevant information for user-friendly display
            if isinstance(result, dict):
                # Create a summary if we have file information
                summary = {
                    "doi": result.get("doi"),
                    "file_name": result.get("file_name"),
                    "file_path": result.get("file_path"),
                }

                # Include fields information if available
                if "fields" in result:
                    summary["total_fields"] = len(result["fields"])
                    summary["field_names"] = [
                        f.get("fieldName") for f in result["fields"]]

                # Include download information if available
                if "data_download" in result:
                    download = result["data_download"]
                    summary["download_info"] = {
                        "content_size_bytes": download.get("contentSize"),
                        "encoding_format": download.get("encoding_format"),
                        "content_url": download.get("contentURL"),
                    }

                # Return complete result with helpful summary
                return json.dumps(
                    {
                        "summary": summary,
                        "complete_response": result,
                    },
                    indent=2,
                )

            return json.dumps(result, indent=2)
        except Exception as e:
            return json.dumps(
                {"error": f"Error retrieving ESS-DeepDive file: {str(e)}"},
                indent=2,
            )

    # Run the server
    asyncio.run(server.run_stdio_async())


if __name__ == "__main__":
    main()
