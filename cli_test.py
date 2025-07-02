#!/usr/bin/env python3
"""
A simple script to test the ESS-DIVE MCP server using command line tools.
This script will run the 'mcp' command line tool to interact with our server.
"""
import subprocess
import os
import sys
import time
import json

def run_cmd(cmd, input_data=None):
    """Run a command and return the output."""
    print(f"\n> {cmd}")
    result = subprocess.run(cmd, shell=True, text=True, input=input_data, 
                           capture_output=True)
    if result.returncode != 0:
        print(f"Error: {result.stderr}")
        return None
    return result.stdout

def test_resources():
    """Test listing and accessing resources."""
    print("\n----- Testing Resources -----")
    
    # List resources
    resources = run_cmd("echo '{\"jsonrpc\": \"2.0\", \"id\": 1, \"method\": \"resources/list\"}' | mcp")
    print(resources)
    
    # Access a resource
    search = run_cmd("echo '{\"jsonrpc\": \"2.0\", \"id\": 2, \"method\": \"resources/read\", \"params\": {\"uri\": \"essdive://search\"}}' | mcp")
    print(search)

def test_prompts():
    """Test listing and getting prompts."""
    print("\n----- Testing Prompts -----")
    
    # List prompts
    prompts = run_cmd("echo '{\"jsonrpc\": \"2.0\", \"id\": 3, \"method\": \"prompts/list\"}' | mcp")
    print(prompts)
    
    # Get a prompt
    prompt = run_cmd("echo '{\"jsonrpc\": \"2.0\", \"id\": 4, \"method\": \"prompts/get\", \"params\": {\"name\": \"search-datasets\", \"arguments\": {\"query\": \"climate change\"}}}' | mcp")
    print(prompt)

def test_tools():
    """Test listing and calling tools."""
    print("\n----- Testing Tools -----")
    
    # List tools
    tools = run_cmd("echo '{\"jsonrpc\": \"2.0\", \"id\": 5, \"method\": \"tools/list\"}' | mcp")
    print(tools)
    
    # Call search tool
    search = run_cmd("echo '{\"jsonrpc\": \"2.0\", \"id\": 6, \"method\": \"tools/call\", \"params\": {\"name\": \"search-datasets\", \"arguments\": {\"query\": \"climate\", \"page_size\": 3}}}' | mcp")
    print(search)

def main():
    """Main entry point."""
    print("Testing ESS-DIVE MCP server...")
    
    # Wait a bit to ensure the server is running
    time.sleep(1)
    
    # Run tests
    test_resources()
    test_prompts()
    test_tools()
    
    print("\nTests completed!")

if __name__ == "__main__":
    main()