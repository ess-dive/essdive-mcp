#!/usr/bin/env python3
"""
A direct client to test the ESS-DIVE MCP server by communicating via JSON-RPC.
"""
import asyncio
import json
import subprocess
import sys
import os
from typing import Dict, Any

# Run the server in a subprocess
server_process = None

async def request(method: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
    """Send a JSON-RPC request to the server and wait for the response."""
    request_id = 1
    request_data = {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": method
    }
    if params:
        request_data["params"] = params
    
    print(f"\n> Request: {json.dumps(request_data)}")
    
    # Write the request to the server's stdin
    server_process.stdin.write(json.dumps(request_data).encode() + b"\n")
    await server_process.stdin.drain()
    
    # Read the response from the server's stdout
    response_line = await server_process.stdout.readline()
    if not response_line:
        return {"error": "No response from server"}
    
    try:
        response = json.loads(response_line.decode())
        print(f"> Response: {json.dumps(response)[:200]}...")
        return response
    except json.JSONDecodeError:
        return {"error": f"Invalid JSON response: {response_line.decode()}"}

async def test_resources():
    """Test listing and reading resources."""
    print("\n----- Testing Resources -----")
    
    # List resources
    print("\nListing resources:")
    resources_response = await request("resources/list")
    if "result" in resources_response:
        resources = resources_response["result"]
        for resource in resources:
            print(f"- {resource.get('name')}: {resource.get('uri')}")
    
    # Read resource
    print("\nReading search resource:")
    search_response = await request("resources/read", {"uri": "essdive://search"})
    if "result" in search_response:
        content = search_response["result"].get("content", "")
        print(content[:500] + "..." if len(content) > 500 else content)

async def test_prompts():
    """Test listing and getting prompts."""
    print("\n----- Testing Prompts -----")
    
    # List prompts
    print("\nListing prompts:")
    prompts_response = await request("prompts/list")
    if "result" in prompts_response:
        prompts = prompts_response["result"]
        for prompt in prompts:
            print(f"- {prompt.get('name')}: {prompt.get('description')}")
            print(f"  Arguments: {prompt.get('arguments')}")
    
    # Get prompt
    print("\nGetting search prompt:")
    prompt_response = await request("prompts/get", {
        "name": "search-datasets", 
        "arguments": {"query": "climate change"}
    })
    if "result" in prompt_response:
        print(prompt_response["result"])

async def test_tools():
    """Test listing and calling tools."""
    print("\n----- Testing Tools -----")
    
    # List tools
    print("\nListing tools:")
    tools_response = await request("tools/list")
    if "result" in tools_response:
        tools = tools_response["result"]
        for tool in tools:
            print(f"- {tool.get('name')}: {tool.get('description')}")
            print(f"  Parameters: {tool.get('parameters')}")
    
    # Call search tool
    print("\nCalling search tool:")
    search_response = await request("tools/call", {
        "name": "search-datasets", 
        "arguments": {"query": "climate", "page_size": 3}
    })
    if "result" in search_response:
        result = search_response["result"].get("result", "")
        print(result[:500] + "..." if len(result) > 500 else result)

async def main():
    """Run the tests."""
    global server_process
    
    print("Starting ESS-DIVE MCP server...")
    # Start the server in a subprocess
    server_process = await asyncio.create_subprocess_exec(
        "python", "main.py",
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    
    # Wait a bit for the server to start
    await asyncio.sleep(1)
    
    try:
        # Initialize the server
        print("\nInitializing server...")
        init_response = await request("initialize", {
            "capabilities": {
                "resources": {},
                "tools": {},
                "prompts": {}
            }
        })
        
        if "result" not in init_response:
            print(f"Error initializing server: {init_response}")
            return
        
        # Run the tests
        await test_resources()
        await test_prompts()
        await test_tools()
        
        print("\nTests completed successfully!")
    except Exception as e:
        print(f"Error during testing: {e}")
    finally:
        # Clean up
        if server_process:
            server_process.terminate()
            await server_process.wait()

if __name__ == "__main__":
    asyncio.run(main())