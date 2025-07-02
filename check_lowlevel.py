#!/usr/bin/env python3
"""Helper script to check available imports from mcp.server.lowlevel."""

import inspect

try:
    import mcp.server.lowlevel
    print("Available items in mcp.server.lowlevel:")
    for name, obj in inspect.getmembers(mcp.server.lowlevel):
        if not name.startswith('_'):
            obj_type = type(obj).__name__
            print(f"- {name}: {obj_type}")
except ImportError as e:
    print(f"Error importing mcp.server.lowlevel: {e}")

# Also check for RequestContext which might be a replacement for ContextView
try:
    import mcp.server
    print("\nChecking other modules for context-related classes:")
    for module_name in ['mcp.server', 'mcp.types', 'mcp.server.context']:
        try:
            module = __import__(module_name, fromlist=['*'])
            print(f"\nItems in {module_name}:")
            for name, obj in inspect.getmembers(module):
                if 'context' in name.lower() and not name.startswith('_'):
                    obj_type = type(obj).__name__
                    print(f"- {name}: {obj_type}")
        except ImportError as e:
            print(f"Could not import {module_name}: {e}")
except ImportError as e:
    print(f"Error in additional imports: {e}")