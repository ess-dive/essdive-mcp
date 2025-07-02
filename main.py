#!/usr/bin/env python3
"""
ESS-DIVE MCP Server - Main entry point

This script initializes and runs an MCP server for interacting with the ESS-DIVE API.
"""
import asyncio
import sys
import os
import json
import re
import argparse
from typing import Dict, List, Optional, Any, Union

# Add the src directory to the Python path so we can import our package
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from mcp.server.fastmcp import FastMCP
from mcp.types import Resource, Prompt

from essdive_mcp.client import ESSDiveClient

# Parse command-line arguments
parser = argparse.ArgumentParser(description="Run an ESS-DIVE MCP server")
parser.add_argument("--token", "-t", help="ESS-DIVE API token for authenticated requests")
parser.add_argument("--name", default="essdive-server", help="Name of the MCP server")
args = parser.parse_args()

# Create a FastMCP server
server = FastMCP(args.name)

# Create a client for the ESS-DIVE API with the provided token
client = ESSDiveClient(api_token=args.token)

# Add resources
server.add_resource(
    Resource(
        uri="essdive://search",
        name="ESS-DIVE Dataset Search",
        description="Search for datasets in ESS-DIVE"
    )
)

server.add_resource(
    Resource(
        uri="essdive://dataset-info",
        name="ESS-DIVE Dataset Information",
        description="Get detailed information about a specific dataset"
    )
)

# Add prompts
server.add_prompt(
    Prompt(
        name="search-datasets",
        description="Search for datasets in ESS-DIVE",
        arguments=[
            {"name": "query", "description": "Search query for datasets"}
        ]
    )
)

server.add_prompt(
    Prompt(
        name="get-dataset-info",
        description="Get detailed information about a specific dataset",
        arguments=[
            {"name": "dataset_id", "description": "ID of the dataset to retrieve information for"}
        ]
    )
)

# Register resource handlers
@server.read_resource
async def handle_read_resource(uri: str):
    """Handle read resource requests."""
    if uri.startswith("essdive://search"):
        return await handle_search_resource(uri)
    elif uri.startswith("essdive://dataset-info"):
        return await handle_dataset_info(uri)
    
    # Default response for unknown resources
    return {"content": f"Resource not found: {uri}", "mime_type": "text/plain"}

async def handle_search_resource(uri: str):
    """Handle search resource requests."""
    # Parse query parameters from URI if they exist
    query_params = {}
    if "?" in uri:
        query_string = uri.split("?", 1)[1]
        for param in query_string.split("&"):
            if "=" in param:
                key, value = param.split("=", 1)
                query_params[key] = value
    
    # Default to a simple search if no parameters specified
    if not query_params:
        result = await client.search_datasets(is_public=True, page_size=5)
        formatted = client.format_results(result, "summary")
        return {"content": formatted, "mime_type": "text/plain"}
    
    # Process query parameters for search
    search_params = {}
    if "text" in query_params:
        search_params["text"] = query_params["text"]
    if "creator" in query_params:
        search_params["creator"] = query_params["creator"]
    if "provider_name" in query_params:
        search_params["provider_name"] = query_params["provider_name"]
    if "is_public" in query_params:
        search_params["is_public"] = query_params["is_public"].lower() == "true"
    if "keywords" in query_params:
        search_params["keywords"] = query_params["keywords"].split(",")
    
    result = await client.search_datasets(**search_params)
    formatted = client.format_results(result, "detailed")
    
    return {"content": formatted, "mime_type": "text/plain"}

async def handle_dataset_info(uri: str):
    """Handle dataset info resource requests."""
    # Extract dataset ID from URI
    match = re.match(r"^essdive://dataset-info\?id=(.+)$", uri)
    if not match:
        return {
            "content": "Invalid dataset info URL. Format: essdive://dataset-info?id=<dataset-id>", 
            "mime_type": "text/plain"
        }
    
    dataset_id = match.group(1)
    
    try:
        result = await client.get_dataset(dataset_id)
        
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
                name = f"{given_name} {family_name}".strip()
                affiliation = creator.get("affiliation", "")
                
                content += f"- {name}"
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
                
                content += f"- {file_name} ({file_size} KB, {file_format})\n"
        
        return {"content": content, "mime_type": "text/markdown"}
    
    except Exception as e:
        return {"content": f"Error retrieving dataset information: {str(e)}", "mime_type": "text/plain"}

# Register prompt handlers
@server.get_prompt
async def handle_get_prompt(name: str, arguments=None):
    """Handle get prompt requests."""
    arguments = arguments or {}
    
    if name == "search-datasets":
        query = arguments.get("query", "")
        prompt = f"""
        Search ESS-DIVE for datasets related to: {query}
        
        Please provide a summary of the top results and any relevant details about the datasets.
        """
        return prompt
    elif name == "get-dataset-info":
        dataset_id = arguments.get("dataset_id", "")
        prompt = f"""
        Provide detailed information about ESS-DIVE dataset with ID: {dataset_id}
        
        Include metadata, creators, keywords, and available data files.
        """
        return prompt
        
    return f"Unknown prompt: {name}"

# Register tool functions
@server.tool(name="search-datasets", description="Search for datasets in ESS-DIVE")
async def search_datasets(query: Optional[str] = None,
                    creator: Optional[str] = None,
                    provider_name: Optional[str] = None,
                    is_public: Optional[bool] = None,
                    date_published: Optional[str] = None,
                    keywords: Optional[List[str]] = None,
                    row_start: int = 1,
                    page_size: int = 10,
                    format: str = "summary") -> str:
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
            keywords=keywords
        )
        
        # Format the results
        formatted = client.format_results(result, format)
        
        if format == "raw":
            return json.dumps(formatted, indent=2)
        else:
            return formatted
    
    except Exception as e:
        return f"Error searching for datasets: {str(e)}"

@server.tool(name="get-dataset", description="Get detailed information about a specific dataset")
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
                name = f"{given_name} {family_name}".strip()
                affiliation = creator.get("affiliation", "")
                
                content += f"- {name}"
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
                
                content += f"- {file_name} ({file_size} KB, {file_format})\n"
        
        return content
    
    except Exception as e:
        return f"Error retrieving dataset information: {str(e)}"

async def main():
    """Run the server."""
    await server.run_stdio_async()

if __name__ == "__main__":
    asyncio.run(main())
