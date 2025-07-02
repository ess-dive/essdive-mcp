#!/usr/bin/env python3
"""Helper script to check the FastMCP module."""

import inspect

try:
    from mcp.server.fastmcp import FastMCP
    print("FastMCP exists and was imported successfully")
    
    print("\nMethods and attributes of FastMCP:")
    for name, obj in inspect.getmembers(FastMCP):
        if not name.startswith('_'):  # Skip private methods/attributes
            obj_type = type(obj).__name__
            print(f"- {name}: {obj_type}")
            
    # Try to create an instance to see if there are any required parameters
    print("\nTrying to create a FastMCP instance:")
    try:
        fast_mcp = FastMCP("test-server")
        print("Successfully created FastMCP instance with just a name parameter")
        
        # Check available decorators
        print("\nAvailable decorators on the instance:")
        for name, obj in inspect.getmembers(fast_mcp):
            if not name.startswith('_') and callable(obj) and name.startswith(('list_', 'read_', 'get_', 'call_')):
                print(f"- {name}")
    except Exception as e:
        print(f"Error creating FastMCP instance: {e}")
        
except ImportError as e:
    print(f"Error importing FastMCP: {e}")
    
    # Try to import mcp.server to see what modules are available
    try:
        import mcp.server
        print("\nAvailable modules in mcp.server:")
        for name, obj in inspect.getmembers(mcp.server):
            if not name.startswith('_'):
                obj_type = type(obj).__name__
                print(f"- {name}: {obj_type}")
    except ImportError as e:
        print(f"Error importing mcp.server: {e}")