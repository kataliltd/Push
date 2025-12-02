"""
DEBUG VERSION - Use this to see what structure n8n is passing

Copy this into your n8n Code Module to see the input structure
"""

import json

# Process each item in the n8n workflow
for item in items:
    # Get the input data
    input_data = item.json

    # Output debug information
    print("=== DEBUG INFO ===")
    print("Type of input_data:", type(input_data))
    print("Input data:", json.dumps(input_data, indent=2))

    # Check what keys exist if it's a dict
    if isinstance(input_data, dict):
        print("Keys in input_data:", list(input_data.keys()))

    # Don't modify the item, just pass it through
    item.json = {"debug_info": "See execution log above"}

return items
