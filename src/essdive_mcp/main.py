#!/usr/bin/env python3
"""
ESS-DIVE MCP Server - Main entry point

This script initializes and runs an MCP server for interacting with the ESS-DIVE API.
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
        params: Dict[str, Any] = {"rowStart": row_start, "pageSize": page_size}

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


def get_api_key(api_key: Optional[str] = None) -> str:
    """
    Get ESS-DIVE API key from parameter or environment variable.

    Args:
        api_key: Optional API key provided directly.

    Returns:
        The API key string.

    Raises:
        ValueError: If no API key is provided or found in environment.
    """
    if api_key is None:
        api_key = os.getenv("ESSDIVE_API_TOKEN")

    if api_key is None:
        raise ValueError(
            "ESS-DIVE API key is required. Provide it with --token or set ESSDIVE_API_TOKEN environment variable."
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
    args = parser.parse_args()

    # Get and validate API token
    api_token = get_api_key(args.token)

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
        is_public: Optional[bool] = None,
        date_published: Optional[str] = None,
        keywords: Optional[List[str]] = None,
        row_start: int = 1,
        page_size: int = 10,
        format: str = "summary",
    ) -> str:
        """
        Search for datasets in the ESS-DIVE repository.

        Args:
            query: Search query text
            creator: Filter by dataset creator
            provider_name: Filter by dataset project/provider
            is_public: If true, only return public packages
            date_published: Filter by publication date
            keywords: Search for datasets with specific keywords
            row_start: The row number to start on (for pagination)
            page_size: Number of results per page (max 100)
            format: Format of the results (summary, detailed, raw)

        Returns:
            Formatted search results
        """
        try:
            # If query is provided but no specific text search parameter,
            # use the query as the text search
            text = None
            if query and not any([creator, provider_name, keywords]):
                text = query

            # Search for datasets
            result = await client.search_datasets(
                row_start=row_start,
                page_size=page_size,
                is_public=is_public,
                creator=creator,
                provider_name=provider_name,
                text=text,
                date_published=date_published,
                keywords=keywords,
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

    # Run the server
    asyncio.run(server.run_stdio_async())


if __name__ == "__main__":
    main()
