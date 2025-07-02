#!/usr/bin/env python3
"""Helper script to check available imports from mcp modules."""

import inspect

try:
    import mcp.server.stdio
    print("Available items in mcp.server.stdio:")
    for name, obj in inspect.getmembers(mcp.server.stdio):
        if not name.startswith('_'):
            obj_type = type(obj).__name__
            print(f"- {name}: {obj_type}")
except ImportError as e:
    print(f"Error importing mcp.server.stdio: {e}")

try:
    from mcp.server import stdio
    print("\nAlternate import - Available items in mcp.server.stdio:")
    for name, obj in inspect.getmembers(stdio):
        if not name.startswith('_'):
            obj_type = type(obj).__name__
            print(f"- {name}: {obj_type}")
except ImportError as e:
    print(f"Error with alternate import: {e}")