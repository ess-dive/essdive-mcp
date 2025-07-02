"""
MCP Server implementation for ESS-DIVE API using FastMCP.
"""
from typing import Any, Dict, List, Optional, Sequence, Union
import json
import re
import asyncio

from mcp.server.fastmcp import FastMCP
from mcp.types import Resource, Prompt, TextContent, ImageContent, EmbeddedResource, ReadResourceResult

from essdive_mcp.client import ESSDiveClient


class ESSDiveMCPServer:
    """MCP server implementation for ESS-DIVE API using FastMCP."""
    
    def __init__(self, name: str = "essdive-server", api_token: Optional[str] = None):
        """
        Initialize the ESS-DIVE MCP server.
        
        Args:
            name: Name of the MCP server
            api_token: Optional API token for authenticated ESS-DIVE API requests
        """
        self.server = FastMCP(name)
        self.client = ESSDiveClient(api_token)
        
        # Register resources
        self.server.add_resource(
            Resource(
                uri="essdive://search",
                name="ESS-DIVE Dataset Search",
                description="Search for datasets in ESS-DIVE"
            )
        )
        self.server.add_resource(
            Resource(
                uri="essdive://dataset-info",
                name="ESS-DIVE Dataset Information",
                description="Get detailed information about a specific dataset"
            )
        )
        
        # Register prompts
        self.server.add_prompt(
            Prompt(
                name="search-datasets",
                description="Search for datasets in ESS-DIVE",
                arguments=[
                    {"name": "query", "description": "Search query for datasets"}
                ]
            )
        )
        self.server.add_prompt(
            Prompt(
                name="get-dataset-info",
                description="Get detailed information about a specific dataset",
                arguments=[
                    {"name": "dataset_id", "description": "ID of the dataset to retrieve information for"}
                ]
            )
        )
        
        # Register handlers
        @self.server.read_resource
        async def read_resource_handler(uri: str) -> ReadResourceResult:
            return await self._read_resource(uri)
        
        @self.server.get_prompt
        async def get_prompt_handler(name: str, arguments: Optional[Dict[str, Any]] = None) -> str:
            return await self._get_prompt(name, arguments)
        
        # Register tool functions with decorators
        @self.server.tool(name="search-datasets", description="Search for datasets in ESS-DIVE")
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
            return await self._handle_search_datasets_tool(
                query, creator, provider_name, is_public, 
                date_published, keywords, row_start, page_size, format
            )
        
        @self.server.tool(name="get-dataset", description="Get detailed information about a specific dataset")
        async def get_dataset(id: str) -> str:
            """
            Get detailed information about a specific dataset.
            
            Args:
                id: ESS-DIVE dataset identifier
                
            Returns:
                Formatted dataset information
            """
            return await self._handle_get_dataset_tool(id)
    
    async def _read_resource(self, uri: str) -> ReadResourceResult:
        """Handle read resource requests."""
        if uri.startswith("essdive://search"):
            return await self._handle_search_resource(uri)
        elif uri.startswith("essdive://dataset-info"):
            return await self._handle_dataset_info(uri)
        
        # Default response for unknown resources
        return ReadResourceResult(
            content=f"Resource not found: {uri}",
            mime_type="text/plain"
        )
    
    async def _handle_search_resource(self, uri: str) -> ReadResourceResult:
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
            result = await self.client.search_datasets(is_public=True, page_size=5)
            formatted = self.client.format_results(result, "summary")
            return ReadResourceResult(
                content=formatted,
                mime_type="text/plain"
            )
        
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
        
        result = await self.client.search_datasets(**search_params)
        formatted = self.client.format_results(result, "detailed")
        
        return ReadResourceResult(
            content=formatted,
            mime_type="text/plain"
        )
    
    async def _handle_dataset_info(self, uri: str) -> ReadResourceResult:
        """Handle dataset info resource requests."""
        # Extract dataset ID from URI
        match = re.match(r"^essdive://dataset-info\?id=(.+)$", uri)
        if not match:
            return ReadResourceResult(
                content="Invalid dataset info URL. Format: essdive://dataset-info?id=<dataset-id>",
                mime_type="text/plain"
            )
        
        dataset_id = match.group(1)
        
        try:
            result = await self.client.get_dataset(dataset_id)
            
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
            
            return ReadResourceResult(
                content=content,
                mime_type="text/markdown"
            )
        
        except Exception as e:
            return ReadResourceResult(
                content=f"Error retrieving dataset information: {str(e)}",
                mime_type="text/plain"
            )
    
    async def _get_prompt(self, name: str, arguments: Optional[Dict[str, Any]] = None) -> str:
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
    
    async def _handle_search_datasets_tool(self, 
                                    query: Optional[str] = None,
                                    creator: Optional[str] = None,
                                    provider_name: Optional[str] = None,
                                    is_public: Optional[bool] = None,
                                    date_published: Optional[str] = None,
                                    keywords: Optional[List[str]] = None,
                                    row_start: int = 1,
                                    page_size: int = 10,
                                    format: str = "summary") -> str:
        """Handle search datasets tool."""
        try:
            # If query is provided but no specific text search parameter,
            # use the query as the text search
            text = None
            if query and not any([creator, provider_name, keywords]):
                text = query
            
            # Search for datasets
            result = await self.client.search_datasets(
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
            formatted = self.client.format_results(result, format)
            
            if format == "raw":
                return json.dumps(formatted, indent=2)
            else:
                return formatted
        
        except Exception as e:
            return f"Error searching for datasets: {str(e)}"
    
    async def _handle_get_dataset_tool(self, id: str) -> str:
        """Handle get dataset tool."""
        try:
            result = await self.client.get_dataset(id)
            
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
    
    def get_server(self):
        """Get the MCP server instance."""
        return self.server
    
    async def run_stdio(self):
        """Run the MCP server using stdio transport."""
        await self.server.run_stdio_async()
    
    async def run_sse(self, host: str = "localhost", port: int = 8000):
        """Run the MCP server using SSE transport."""
        await self.server.run_sse_async(host=host, port=port)