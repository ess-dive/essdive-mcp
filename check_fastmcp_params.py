#!/usr/bin/env python3
"""Helper script to check FastMCP method parameters."""

import inspect
import asyncio
from mcp.server.fastmcp import FastMCP

# Get function signatures for key methods
async def test_fastmcp():
    print("Checking FastMCP method signatures:")
    
    # Inspect add_resource method
    add_resource_sig = inspect.signature(FastMCP.add_resource)
    print(f"\nadd_resource signature: {add_resource_sig}")
    print(f"Parameters: {add_resource_sig.parameters}")
    
    # Create test instance
    print("\nCreating test FastMCP instance")
    server = FastMCP("test-server")
    
    # Try adding a resource using different methods
    print("\nTesting resource creation")
    try:
        # Method 1: Try using Resource object
        from mcp.types import Resource
        resource = Resource(url="test://resource1", name="Test Resource", description="Description")
        server.add_resource(resource)
        print("Method 1 successful: Added resource using Resource object")
    except Exception as e:
        print(f"Method 1 failed: {str(e)}")
    
    try:
        # Method 2: Try positional parameters
        server.add_resource("test://resource2", "Test Resource 2", "Description 2")
        print("Method 2 successful: Added resource using positional parameters")
    except Exception as e:
        print(f"Method 2 failed: {str(e)}")
    
    # Inspect add_tool method
    add_tool_sig = inspect.signature(FastMCP.add_tool)
    print(f"\nadd_tool signature: {add_tool_sig}")
    print(f"Parameters: {add_tool_sig.parameters}")
    
    # Try adding a tool
    print("\nTesting tool creation")
    try:
        server.add_tool(name="test-tool", description="Test tool", parameters=[{"name": "param1", "type": "string"}])
        print("Added tool successfully")
    except Exception as e:
        print(f"Adding tool failed: {str(e)}")
    
    # Test other key methods
    for method_name in ["add_prompt", "read_resource", "get_prompt", "call_tool"]:
        method = getattr(FastMCP, method_name)
        sig = inspect.signature(method)
        print(f"\n{method_name} signature: {sig}")
        print(f"Parameters: {sig.parameters}")

if __name__ == "__main__":
    asyncio.run(test_fastmcp())