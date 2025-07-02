#!/usr/bin/env python3
"""
Minimal working ESS-DIVE MCP Server using FastMCP.
"""
import asyncio
import sys
import os

# Add the src directory to the Python path so we can import our package
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from mcp.server.fastmcp import FastMCP
from mcp.types import Resource, Prompt


# Create a simple FastMCP server
server = FastMCP("essdive-minimal-server")

# Add a resource
server.add_resource(
    Resource(
        uri="essdive://hello",
        name="Hello Resource",
        description="A test resource"
    )
)

# Add a prompt
server.add_prompt(
    Prompt(
        name="hello-prompt",
        description="A test prompt",
        arguments=[
            {"name": "name", "description": "Your name"}
        ]
    )
)

# Register handlers
@server.read_resource
async def read_resource(uri: str):
    if uri == "essdive://hello":
        return {"content": "Hello, World!", "mime_type": "text/plain"}
    return {"content": f"Resource not found: {uri}", "mime_type": "text/plain"}

@server.get_prompt
async def get_prompt(name: str, arguments=None):
    if name == "hello-prompt":
        user_name = arguments.get("name", "User") if arguments else "User"
        return f"Hello, {user_name}! This is a test prompt."
    return f"Unknown prompt: {name}"

@server.tool(name="hello-tool", description="A test tool")
async def hello_tool(name: str = "User"):
    """A simple test tool that says hello.
    
    Args:
        name: Your name
        
    Returns:
        A greeting message
    """
    return f"Hello, {name}! This is a test tool."


async def main():
    """Run the server."""
    await server.run_stdio_async()


if __name__ == "__main__":
    asyncio.run(main())