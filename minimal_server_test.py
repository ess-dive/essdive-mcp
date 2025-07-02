#!/usr/bin/env python3
"""Test a minimal MCP server implementation."""

from mcp.server.lowlevel import Server
from mcp.types import Resource, ReadResourceResult

# Create a basic server
server = Server("test-server")

# Register resource handlers
@server.list_resources()
async def list_resources():
    return [Resource(
        url="test://hello",
        name="Hello Resource",
        description="A test resource"
    )]

# Try different ways to register read_resource handler

# Option 1: Using function parameter
try:
    @server.read_resource()
    async def read_resource1(url: str):
        if url == "test://hello":
            return ReadResourceResult(content="Hello, World!", mime_type="text/plain")
        return ReadResourceResult(content="Resource not found", mime_type="text/plain")
    print("Option 1 (no arguments) registered successfully")
except TypeError as e:
    print(f"Option 1 error: {str(e)}")

# Option 2: Using URL matcher
try:
    @server.read_resource
    async def read_resource2(url: str):
        if url == "test://hello":
            return ReadResourceResult(content="Hello, World!", mime_type="text/plain")
        return ReadResourceResult(content="Resource not found", mime_type="text/plain")
    print("Option 2 (decorator without parens) registered successfully")
except TypeError as e:
    print(f"Option 2 error: {str(e)}")

if __name__ == "__main__":
    print("Test completed")