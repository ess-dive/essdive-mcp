#!/usr/bin/env python3
"""
A simple client to test the ESS-DIVE MCP server.
"""
import asyncio
import json
import sys
import os
from typing import Dict, Any, List, Optional

# Add the src directory to the Python path so we can import packages if needed
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from mcp.client.stdio import stdio_client as Client


async def test_resources(client: Client):
    """Test listing and reading resources."""
    print("\n----- Testing Resources -----")
    
    # List resources
    print("\nListing resources:")
    resources = await client.list_resources()
    for resource in resources:
        print(f"- {resource.name}: {resource.uri}")
    
    # Read resources
    print("\nReading search resource:")
    search_result = await client.read_resource("essdive://search")
    print(search_result.content[:500] + "..." if len(search_result.content) > 500 else search_result.content)
    
    # Read resource with query
    print("\nReading search resource with query:")
    query_result = await client.read_resource("essdive://search?text=climate")
    print(query_result.content[:500] + "..." if len(query_result.content) > 500 else query_result.content)


async def test_prompts(client: Client):
    """Test listing and using prompts."""
    print("\n----- Testing Prompts -----")
    
    # List prompts
    print("\nListing prompts:")
    prompts = await client.list_prompts()
    for prompt in prompts:
        print(f"- {prompt.name}: {prompt.description}")
        print(f"  Arguments: {prompt.arguments}")
    
    # Get prompt
    print("\nGetting search prompt:")
    search_prompt = await client.get_prompt("search-datasets", {"query": "carbon sequestration"})
    print(search_prompt)
    
    print("\nGetting dataset info prompt:")
    dataset_prompt = await client.get_prompt("get-dataset-info", {"dataset_id": "example-id-123"})
    print(dataset_prompt)


async def test_tools(client: Client):
    """Test listing and calling tools."""
    print("\n----- Testing Tools -----")
    
    # List tools
    print("\nListing tools:")
    tools = await client.list_tools()
    for tool in tools:
        print(f"- {tool.name}: {tool.description}")
        print(f"  Parameters: {[p for p in tool.parameters]}")
    
    # Call search tool
    print("\nCalling search tool with query 'climate':")
    search_result = await client.call_tool("search-datasets", {"query": "climate", "page_size": 3})
    print(search_result.result[:500] + "..." if len(search_result.result) > 500 else search_result.result)
    
    # Extract an ID from the search results
    # This is a simple parsing attempt - might need adjustment based on actual output format
    lines = search_result.result.split('\n')
    dataset_id = None
    for line in lines:
        if line.strip().startswith("ID:"):
            dataset_id = line.strip().split("ID:")[1].strip()
            break
    
    # Call get-dataset tool if we found an ID
    if dataset_id:
        print(f"\nCalling get-dataset tool with ID '{dataset_id}':")
        dataset_result = await client.call_tool("get-dataset", {"id": dataset_id})
        print(dataset_result.result[:500] + "..." if len(dataset_result.result) > 500 else dataset_result.result)
    else:
        print("\nNo dataset ID found in search results")


async def main():
    """Main function to run tests."""
    # Connect to server
    print("Connecting to ESS-DIVE MCP server...")
    client = Client()
    await client.connect_stdio()
    
    try:
        # Run tests
        await test_resources(client)
        await test_prompts(client)
        await test_tools(client)
        
        print("\nTests completed successfully!")
    except Exception as e:
        print(f"\nError during testing: {e}")
    finally:
        # Disconnect
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())