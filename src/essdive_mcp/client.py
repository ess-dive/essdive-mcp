"""
ESS-DIVE API Client for interacting with the ESS-DIVE dataset API.
"""
from typing import Dict, List, Optional, Any, Union
import httpx
from urllib.parse import quote


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
    
    async def search_datasets(self,
                        row_start: int = 1,
                        page_size: int = 25,
                        is_public: Optional[bool] = None,
                        creator: Optional[str] = None,
                        provider_name: Optional[str] = None,
                        text: Optional[str] = None,
                        date_published: Optional[str] = None,
                        keywords: Optional[List[str]] = None) -> Dict[str, Any]:
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
        params = {
            "rowStart": row_start,
            "pageSize": page_size
        }
        
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
        encoded_identifier = quote(identifier, safe='')
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
        encoded_identifier = quote(identifier, safe='')
        url = f"{self.BASE_URL}/packages/{encoded_identifier}/status"
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=self._get_headers())
            response.raise_for_status()
            return response.json()
    
    def format_results(self, results: Dict[str, Any], 
                      format_type: str = "summary") -> Union[str, Dict[str, Any]]:
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