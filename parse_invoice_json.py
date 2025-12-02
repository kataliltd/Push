"""
Parse and clean invoice JSON data for n8n code module.

This script extracts invoice data from a nested JSON structure,
removes markdown formatting and escape characters, and returns clean JSON.
"""

import json
import re


def parse_invoice_json(input_data):
    """
    Parse invoice JSON from nested structure and clean it.

    Args:
        input_data: Either a JSON string or already parsed list/dict

    Returns:
        dict: Clean invoice data as a Python dictionary
    """
    # If input is a string, parse it first
    if isinstance(input_data, str):
        data = json.loads(input_data)
    else:
        data = input_data

    # Extract the text content from the nested structure
    # Expected structure: [{"content": [{"type": "text", "text": "..."}]}]
    if isinstance(data, list) and len(data) > 0:
        if "content" in data[0]:
            content_list = data[0]["content"]
            if len(content_list) > 0 and "text" in content_list[0]:
                text_content = content_list[0]["text"]
            else:
                raise ValueError("Expected 'text' field in content array")
        else:
            raise ValueError("Expected 'content' field in input data")
    else:
        raise ValueError("Expected input to be a non-empty list")

    # Remove markdown code block markers (```json and ```)
    text_content = re.sub(r'^```json\s*', '', text_content)
    text_content = re.sub(r'```\s*$', '', text_content)

    # Remove XML-like tags (<invoice_data> and </invoice_data>)
    text_content = re.sub(r'</?invoice_data>\s*', '', text_content)

    # Clean up any extra whitespace
    text_content = text_content.strip()

    # Parse the cleaned JSON string
    invoice_data = json.loads(text_content)

    return invoice_data


# For n8n Code Module
# Uncomment the section below when using in n8n

"""
# n8n Code Module Implementation
# The input is available in the 'items' array
# Each item has a 'json' property containing the data

for item in items:
    # Get the input data from the item
    input_data = item.json

    # Parse and clean the invoice data
    cleaned_data = parse_invoice_json(input_data)

    # Return the cleaned data
    item.json = cleaned_data

return items
"""


# Standalone usage example
if __name__ == "__main__":
    # Example input (as provided)
    example_input = '''[
  {
    "content": [
      {
        "type": "text",
        "text": "```json\\n<invoice_data>\\n{\\n  \\"invoice\\": {\\n    \\"invoice_number\\": \\"0012415278\\",\\n    \\"invoice_date\\": \\"29/09/25\\",\\n    \\"customer_account\\": \\"WE1573\\",\\n    \\"pages\\": [\\n      {\\n        \\"page\\": \\"1 of 4\\",\\n        \\"line_items\\": [\\n          {\\n            \\"date\\": \\"2025-09-22\\",\\n            \\"del_adv_number\\": \\"0012816646\\",\\n            \\"description\\": \\"A12M-STFCR 11 BORING BAR\\",\\n            \\"part_no\\": \\"PMT1060011P\\",\\n            \\"qty\\": \\"2\\",\\n            \\"price\\": \\"103.790\\",\\n            \\"unit\\": \\"EA\\",\\n            \\"discount\\": \\"0.00\\",\\n            \\"total_value\\": \\"207.58\\"\\n          },\\n          {\\n            \\"date\\": \\"2025-09-22\\",\\n            \\"del_adv_number\\": \\"0012816646\\",\\n            \\"description\\": \\"A12M-STFCR 11 BORING BAR\\",\\n            \\"part_no\\": \\"PMT1060011P\\",\\n            \\"qty\\": \\"1\\",\\n            \\"price\\": \\"103.790\\",\\n            \\"unit\\": \\"EA\\",\\n            \\"discount\\": \\"0.00\\",\\n            \\"total_value\\": \\"103.79\\"\\n          }\\n        ]\\n      }\\n    ]\\n  }\\n}\\n</invoice_data>\\n```"
      }
    ]
  }
]'''

    # Parse and clean the data
    result = parse_invoice_json(example_input)

    # Print the cleaned JSON
    print("Cleaned Invoice Data:")
    print(json.dumps(result, indent=2))
