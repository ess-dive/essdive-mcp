#!/usr/bin/env python3
"""
ESS-DIVE MCP Server - Main entry point

This script initializes and runs an MCP server for interacting with the ESS-DIVE API.
"""
import asyncio
import os
import argparse
from typing import List, Optional

from fastmcp import FastMCP

from client import ESSDiveClient


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

    # Get API token from CLI argument or environment variable
    api_token = args.token or os.getenv("ESSDIVE_API_TOKEN")

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
            import json
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

    # Run the server
    asyncio.run(server.run_stdio_async())


if __name__ == "__main__":
    main()
