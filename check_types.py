#!/usr/bin/env python3
"""Helper script to check available imports from mcp.types."""

import inspect

try:
    import mcp.types
    print("Available items in mcp.types:")
    for name, obj in inspect.getmembers(mcp.types):
        if not name.startswith('_'):
            obj_type = type(obj).__name__
            print(f"- {name}: {obj_type}")
except ImportError as e:
    print(f"Error importing mcp.types: {e}")

# Check for tool-related classes specifically
try:
    import mcp.types
    print("\nChecking specifically for tool-related classes:")
    for name, obj in inspect.getmembers(mcp.types):
        if 'tool' in name.lower() and not name.startswith('_'):
            obj_type = type(obj).__name__
            print(f"- {name}: {obj_type}")
except ImportError as e:
    print(f"Error in additional check: {e}")